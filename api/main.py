"""
FastAPI Backend za Library Chatbot
REST API za chatbot i pretraživanje knjiga
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict
import sys
import os
import logging
import re
import httpx
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#path setup
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from scraper.availability_checker import ScraperAPIChecker
    from scraper.category_scraper import CategoryScraper
    from database.db_manager import DatabaseManager
    from chatbot.knowledge_base import KnowledgeBase
    from scraper.new_books_scraper import NewBooksScraper
except ImportError as e:
    logger.error(f"Greska pri importu modula: {e}")
    # Fallback za lokalno testiranje ako struktura foldera varira
    sys.path.append(os.getcwd())

# Dodaj parent directory u path

sys.path.insert(0, parent_dir)

# Inicijaliziraj FastAPI
app = FastAPI(
    title="Library Chatbot API",
    description="API za AI chatbot i pretraživanje knjiga",
    version="1.0.0"
)

# CORS - omogućava frontendima da pristupa API-ju
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # U production stavi specifične domene
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicijaliziraj bazu i knowledge base
availability_checker = ScraperAPIChecker()
new_books_scraper = NewBooksScraper()
category_scraper = CategoryScraper()
db = DatabaseManager()
kb = KnowledgeBase()

# Učitaj knowledge base ako je prazan
try:
    if kb.get_count() == 0:
        if os.path.exists('data/membership_info.json'):
            kb.add_from_json('data/membership_info.json')
        if os.path.exists('data/website_all_pages.json'):
            kb.add_from_json('data/website_all_pages.json')
except Exception as e:
    logger.warning(f"Nisam uspio inicijalizirati KB: {e}")

# Pydantic modeli za request/response
class ChatRequest(BaseModel):
    message: str
    
class ChatResponse(BaseModel):
    response: str
    
class BookSearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 10

class Book(BaseModel):
    id: str
    title: str
    author: str
    year: Optional[str] = None
    isbn: Optional[str] = None
    publisher: Optional[str] = None

# --- CHATBOT LOGIKA - POMOCNE FUNKCIJE

def extract_keywords(query: str) -> list:
    """Izvlači ključne riječi"""
    stop_words = ['knjiga', 'knjige', 'autor', 'o', 'na', 'u', 'i', 'za', 'mi']
    words = re.findall(r'\w+', query.lower())
    return [w for w in words if w not in stop_words and len(w) > 2][:3]

async def search_catalog_for_book(query: str) -> Dict:
    """
    Pretraži katalog knjižnice za knjigu
    Koristi se kad knjiga nije u lokalnoj bazi
    """
    try:
        scraper_api_key = os.getenv('SCRAPER_API_KEY')
        if not scraper_api_key:
            logger.warning("SCRAPER_API_KEY nije postavljen - ne mogu pretraživati katalog")
            return None
        
        import urllib.parse
        encoded_query = urllib.parse.quote(query, safe='')
               
        # URL za pretraživanje kataloga
        search_url = f"https://katalog.halubajska-zora.hr/pagesResults/rezultati.aspx?currentPage=1&searchById=1&sort=0&age=0&spid0=1&spv0={encoded_query}"
        
        params = {
            'api_key': scraper_api_key,
            'url': search_url,
            'country_code': 'hr',
            'render': 'false',
            'premium': 'false'
        }
              
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.get(
                "http://api.scraperapi.com/",
                params=params
            )
        
        if response.status_code != 200:
            logger.error(f"ScraperAPI error: {response.status_code}")
            return None
        
        logger.info(f"Response: {len(response.text)} bytes")

        #if os.path.exists('data'):
         #   with open('data/catalog_search_debug.html', 'w', encoding='utf-8') as f:
          #      f.write(response.text)
           # logger.info("✓ HTML spremljen u data/catalog_search_debug.html")
        #logger.info(f"HTML preview: {response.text[:500]}")

        soup = BeautifulSoup(response.text, 'html.parser')

        book_divs = soup.find_all('div', class_='divBibZapis')
        logger.info(f"Pronađeno {len(book_divs)} knjiga")

        if not book_divs:
            logger.warning("Nema rezultata pretrage")
            return None
        
        first_book = book_divs[0]
        title_link = first_book.find('a', class_='aNaslovLink')

        if not title_link:
            logger.warning("Nema title link-a")
            return None
        
        title = title_link.get_text(strip=True)
        href = title_link.get('href', '')
        match = re.search(r'selectedId=(\d+)', href)

        if not match:
            logger.warning(f"selectedId nije pronađen u: {href}")
            return None
        
        book_id = match.group(1)

        author = "Nepoznat autor"
        author_link = first_book.find('a', class_='aAutor')
        if author_link:
            author = author_link.get_text(strip=True)

        logger.info(f"✓ Pronađeno: {title} - {author} (ID: {book_id})")
                
        return {
            'book_id': book_id,
            'title': title,
            'author': author
        }
    
    except httpx.TimeoutException:
        logger.error("Timeout pri pretraživanju kataloga")
        return None
    
    except Exception as e:
        logger.error(f"Greška pri pretraživanju kataloga: {e}")
        import traceback
        traceback.print_exc()
        return None

async def generate_response(user_message: str) -> str:
    """Generira odgovor na korisničku poruku (template-based)"""
    
    query_lower = user_message.lower()
    #0. PROVJERA DOSTUPNOSTI 
    if any(word in query_lower for word in ['dostupn', 'posuden', 'je li', 'jel', 'ima li na', 'rezerv', 'status']):
        # Pokušaj pronaći naziv knjige
        # Jednostavna logika - traži knjigu po ključnim riječima
        keywords = extract_keywords(user_message)

        if keywords:
            # 1. Prvo pretraži bazu za ID knjige
            books = db.search_books(keywords[0], limit=3)
            
            if books:
                book = books[0]
                book_id = book['id']             
                
            else:
                # 2. Knjiga nije u bazi - scrape katalog
                logger.info(f"Knjiga '{keywords[0]}' nije u lokalnoj bazi - tražim u katalogu...")
                search_result = await search_catalog_for_book(keywords[0])
                
                if search_result:
                    book_id = search_result['book_id']
                else:
                    return (f"Nisam pronašao knjigu **'{keywords[0]}'** u katalogu.\n\n"
                        f"Provjerite katalog direktno:\n"
                        f"🔗 https://katalog.halubajska-zora.hr")
            try:
                # Provjeri dostupnost
                availability = await availability_checker.check_availability(book_id)
                return availability_checker.format_availability_message(availability)
            except Exception as e:
                logger.error(f"Greška pri provjeri dostupnosti: {e}")
                return "Trenutno ne mogu provjeriti status knjige u katalogu."
        else:
            return f"Nisam pronašao knjigu '{keywords[0]}'. Molim unesite točan naslov ili provjerite katalog."

    # 1. PREPORUKE - Provjeri PRVO (prije općih upita o knjigama)
    if any(word in query_lower for word in ['preporuč', 'preporuka', 'preporučuješ', 'predloži', 'što čitati', 'što da čitam', 'za čitanje', 'knjiga za']):

        # PRVO: Provjeri je li tražena specifična kategorija (ne-knjige)
        category_keywords = {
            # Igračke
            'igračk': 'igračke',
            'igrac': 'igračke',
            
            # Glazba
            'glazb': 'glazbena građa',
            'cd': 'glazbena građa',
            'musik': 'glazbena građa',
            'audio cd': 'glazbena građa',
            
            # Filmovi / Video
            'film': 'vizualna građa',
            'dvd': 'vizualna građa',
            'video': 'vizualna građa',
            
            # Audioknjige
            'audioknjig': 'zvučna građa',
            'audio knjig': 'zvučna građa',
            
            # E-knjige
            'e-knjig': 'e-knjiga',
            'eknjig': 'e-knjiga',
            'ebook': 'e-knjiga',
            'digital': 'e-knjiga',
            
            # Časopisi
            'časopis': 'časopis',
            'casopis': 'časopis',
            'magazin': 'časopis',
            'revij': 'časopis',
            
            # Note
            'not': 'notna građa',
            'partitur': 'notna građa',
            
            # Karte
            'kart': 'kartografska građa',
            'zemljovid': 'kartografska građa',
            'atlas': 'kartografska građa',
            
            # Grafika
            'grafik': 'grafička građa',
        }

        detected_category = None
        for keyword, category in category_keywords.items():
            if keyword in query_lower:
                detected_category = category
                break

        if detected_category:
            logger.info(f"KATEGORIJA: Detektirana - {detected_category}")
            items = await category_scraper.get_items_by_category(
                category=detected_category,
                limit=5,
                random_selection=True
            )
            return category_scraper.format_category_message(items, detected_category)        
       
        # INAČE: Pretraži knjige po temi
        keywords = extract_keywords(user_message)
        
        books = []
        if keywords and len(keywords) > 0:
            # Pretraži po temi
            for keyword in keywords[:2]:
                books.extend(db.search_books(keyword, limit=4))
        
        # Ako nema knjiga po temi ili nema teme, daj popularne
        if not books:
            books = db.get_all_books(limit=5)
        
        if books:
            # Ukloni duplikate
            unique_books = {book['id']: book for book in books}.values()
            books_list = list(unique_books)[:5]
            
            response = "📚 **Evo mojih preporuka:**\n\n"
            for i, book in enumerate(books_list, 1):
                response += f"{i}. **{book['title']}** - {book['author']}"
                if book.get('year'):
                    response += f" ({book['year']})"
                response += "\n"
            
            response += "\n💡 Za više detalja ili rezervaciju, provjerite katalog: https://katalog.halubajska-zora.hr"
            return response
        else:
            return "Trenutno nemam knjiga u bazi za preporuku. Provjerite katalog: https://katalog.halubajska-zora.hr"
    
    # 2. TRAZENJE PO TEMI
    if detected_category:
        logger.info(f"KATEGORIJA: Detektirana - {detected_category}")
        items = await category_scraper.get_items_by_category(
            category=detected_category,
            limit=5,
            random_selection=True
        )
        return category_scraper.format_category_message(items, detected_category) 
    
    # PROVJERA: Je li tražena tema/sadržaj (UDK)
    subject_keywords = [
        'psihologi', 'medicin', 'politi', 'povijes', 'socio', 'geograf',
        'biografij', 'lingvisti', 'jezik', 'etnograf', 'folklor', 'sport',
        'prav', 'filozof', 'ekonomij', 'zoologi', 'slikarst', 'računarst',
        'racunarst', 'arhitektur', 'biologi', 'kazališt', 'kazalist', 'fizik',
        'astrono', 'matemati', 'botanik', 'fotograf', 'budiz', 'islam',
        'kemij', 'arheologi', 'hrvatska književnost', 'hrvatska knjizevnost',
        'književnost', 'knjizevnost', 'prolegomen', 'kršćanst', 'krscanst',
        'odgoj', 'obrazovan', 'domaćinst', 'domacinst', 'glazb'
    ]

    detected_subject = None
    for keyword in subject_keywords:
        if keyword in query_lower:
            # Pronađi punu formu teme
            for udk_key in category_scraper.udk_categories.keys():
                if keyword in udk_key or udk_key in query_lower:
                    detected_subject = udk_key
                    break
            if detected_subject:
                break

    if detected_subject:
        logger.info(f"TEMA: Detektirana - {detected_subject}")
        items = await category_scraper.get_items_by_subject(
            subject=detected_subject,
            limit=8,
            random_selection=True
        )
        return category_scraper.format_subject_message(items, detected_subject)            
    
    # 2. Pitanja o knjižnici
    if any(word in query_lower for word in ['učlaniti', 'članarina', 'upis']):
        return ("📚 **Učlanjenje u knjižnicu**\n\n"
                "Za učlanjenje trebate osobnu iskaznicu i pristupnicu. "
                "Članarina se plaća godišnje po kategorijama.\n\n"
                "Više na: https://www.halubajska-zora.hr")
    
    if any(word in query_lower for word in ['radno vrijeme', 'otvoreno', 'kada', 'kada radi']):
        return ("⏰ **Radno vrijeme:**\n\n"
                "• Radnim danima: 8:00 - 20:00\n"
                "• Subotom: 8:00 - 14:00\n"
                "• Nedjeljom: zatvoreno\n\n"
                "Više na: https://www.halubajska-zora.hr")
    
    if any(word in query_lower for word in ['posuditi', 'posudba', 'koliko knjiga', 'rok posudbe']):
        return ("📖 **Posudba knjiga:**\n\n"
                "• Do 4 knjige istovremeno\n"
                "• Rok: 30 dana\n"
                "• Produženje moguće ako nije rezervirana\n\n"
                "Za rezervaciju: https://katalog.halubajska-zora.hr")
    
    if any(word in query_lower for word in ['e-knjig', 'digitalne', 'online', 'audio']):
        return ("💻 **E-knjige i audioknige:**\n\n"
                "Dostupne putem ZaKi Book platforme.\n"
                "• Do 4 naslova mjesečno\n"
                "• Na 4 uređaja\n\n"
                "Više: https://www.halubajska-zora.hr")
    
    if any(word in query_lower for word in ['kasn', 'kazna', 'zakasnio']):
        return ("⚠️ **Kašnjenje:**\n\n"
                "Za svaki dan kašnjenja naplaćuje se kazna.\n"
                "Preporučujemo pravovremeno vraćanje ili produženje!")
    
    if any(word in query_lower for word in ['produžiti', 'produženje']):
        return ("🔄 **Produženje posudbe:**\n\n"
                "Možete produžiti:\n"
                "• Online - 'Moja iskaznica'\n"
                "• Telefonski\n"
                "• Osobno\n\n"
                "Ako knjiga nije rezervirana.")
    
    # 3. Pretraživanje knjiga (specifično)
    if any(word in query_lower for word in ['knjiga o', 'knjige o', 'autor', 'naslov', 'imate li', 'imaš li']):
        keywords = extract_keywords(user_message)
        
        if keywords:
            books = []
            for keyword in keywords[:2]:
                books.extend(db.search_books(keyword, limit=5))
            
            if books:
                unique_books = {book['id']: book for book in books}.values()
                books_list = list(unique_books)[:5]
                
                response = f"🔍 **Pronašao sam {len(books_list)} {'knjigu' if len(books_list) == 1 else 'knjige'}:**\n\n"
                
                for i, book in enumerate(books_list, 1):
                    response += f"{i}. **{book['title']}**\n"
                    response += f"   📝 Autor: {book['author']}\n"
                    if book.get('year'):
                        response += f"   📅 {book['year']}\n"
                    if book.get('isbn'):
                        response += f"   📚 ISBN: {book['isbn']}\n"
                    response += "\n"
                
                response += "💡 Za dostupnost: https://katalog.halubajska-zora.hr"
                return response
    
    # 4. Knowledge base search
    kb_results = kb.search(user_message, n_results=2)
    
    if kb_results and kb_results[0].get('distance', 1.0) < 0.7:
        content = kb_results[0]['content']
        if len(content) > 300:
            content = content[:300] + "..."
        
        return content + "\n\nViše: https://www.halubajska-zora.hr"
    
    #5. NOVE KNJIGE
    if any(word in query_lower for word in ['nove knjige', 'novi naslovi', 'što ima novo', 'nova', 'novo', 'noviteti', 'prinove']):
        logger.info("NOVE KNJIGE: Dohvaćam...")
        books = await new_books_scraper.get_new_books(days=365, limit=8)
        return new_books_scraper.format_new_books_message(books)

    #6. NAJČITANIJE KNJIGE
    if any(word in query_lower for word in ['najčitan', 'najpopular', 'top knjig', 'popularne knjige', 'hitovi']):
        logger.info("NAJČITANIJE: Dohvaćam...")
        
        # Detektiraj period
        days = 30  # Default
        number_match = re.search(r'(\d+)\s*(dan|daN)', query_lower)
        if number_match:
            requested_days = int(number_match.group(1))
            # Mapiranje na najbliži validan period
            valid_periods = [7, 30, 90, 180, 365]
            days = min(valid_periods, key=lambda x: abs(x - requested_days))
            logger.info(f"Detektiran period: {requested_days} → mapiran na {days} dana")
        
        if any(word in query_lower for word in ['tjedan', 'sedmic', '7']):
            days = 7
        elif any(word in query_lower for word in ['mjesec', 'mjeseca', '30']) and '3' not in query_lower and '6' not in query_lower:
            days = 30
        elif any(word in query_lower for word in ['3 mjesec', 'tri mjesec', '90']):
            days = 90
        elif any(word in query_lower for word in ['6 mjesec', 'pola god', '180', 'šest mjesec']):
            days = 180
        elif any(word in query_lower for word in ['godin', 'godine', '365']):
            days = 365
        
        logger.info(f"Konačni period: {days} dana")
        
        books = await category_scraper.get_most_read(days=days, limit=10)
        return category_scraper.format_most_read_message(books, days)
   

    #POSLJEDNJE - Default
    return ("📚 **Dobrodošli!** Mogu vam pomoći s:\n\n"
            "• Informacijama o knjižnici (radno vrijeme, članstvo...)\n"
            "• Pretraživanjem knjiga po naslovu ili autoru\n"
            "• Preporukama za čitanje\n\n"
            "Što vas zanima?")


# ENDPOINTS 
@app.get("/api")
async def api_root():
    """API Root endpoint"""
    return {
        "message": "Library Chatbot API",
        "version": "1.0.0",
        "endpoints": {
            "chat": "/api/chat",
            "books": "/api/books/search",
            "book_details": "/api/books/{book_id}",
            "health": "/api/health",
            "docs": "/docs"
        }
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database": "connected",
        "knowledge_base_docs": kb.get_count()
    }

@app.get("/api/books/{book_id}/availability")
async def check_book_availability(book_id: str):
    """
    Provjeri dostupnost knjige u stvarnom vremenu koristeći asinkroni scraper.
    """
    try:
        availability = await availability_checker.check_availability(book_id)
        logger.info(f"Availability result for {book_id}: {availability}")
        message = availability_checker.format_availability_message(availability)    
        # Vraćamo JSON objekt, a ne samo običan string, 
        # kako bi frontend (data.response) to znao pročitati
        return {"response": message}
    except Exception as e:
        logger.error(f"AVAILABILITY ERROR: {e}")
        import traceback
        traceback.print_exc()
        # I u slučaju greške vraćamo JSON format da chatbot ne "pukne"
        return {"response": f"Trenutno ne mogu provjeriti dostupnost: {str(e)}"}

@app.get("/api/books/new")
async def get_new_books_endpoint(days: int = 365, limit: int = 10):
    """Dohvati nove knjige"""
    try:
        books = await new_books_scraper.get_new_books(days=days, limit=limit)
        return {
            "count": len(books),
            "books": books
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat endpoint - prima poruku korisnika i vraća odgovor
    """
    try:
        user_message = request.message.strip()
        
        if not user_message:
            raise HTTPException(status_code=400, detail="Poruka ne može biti prazna")
        
        # Generiraj odgovor (template-based za sada)
        response = await generate_response(user_message)
        
        return ChatResponse(response=response)
        
    except Exception as e:
        logger.error(f"API ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Python Error: {str(e)}")


# --- ENDPOINTS

@app.post("/api/books/search")
async def search_books(request: BookSearchRequest):
    """
    Pretraži knjige u katalogu
    """
    try:
        books = db.search_books(request.query, limit=request.limit)
        
        return {
            "query": request.query,
            "count": len(books),
            "books": books
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/books/{book_id}")
async def get_book(book_id: str):
    """
    Dohvati detaljne informacije o knjizi
    """
    try:
        book = db.get_book_by_id(book_id)
        
        if not book:
            raise HTTPException(status_code=404, detail="Knjiga nije pronađena")
        
        return book
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/books/popular")
async def get_popular_books(limit: int = 10):
    """
    Dohvati popularne knjige
    """
    try:
        books = db.get_all_books(limit=limit)
        return {
            "count": len(books),
            "books": books
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- STARTUP / SHUTDOWN

@app.on_event("startup")
async def startup_event():
    """Pokreće se kad se API pokrene"""
    print("=" * 70)
    print("🚀 Library Chatbot API pokrenut!")
    try:
        # Provjeri je li baza prazna
        all_books = db.get_all_books(limit=1)
    except Exception as e:
        print(f"⚠️ Problem s bazom: {e}")
    
    if not all_books or len(all_books) == 0:
        print("⚠️ Baza je prazna - učitavam knjige iz JSON-a...")
        
        # Učitaj iz JSON-a
        import glob
        json_files = glob.glob("data/books_catalog*.json")
        
        if json_files:
            count = db.import_from_json(json_files[0])
            print(f"✅ Učitano {count} knjiga u bazu")
        else:
            print("❌ Nema JSON fajlova za import!")
    else:
        print(f"✅ Baza već sadrži knjige: {len(all_books)}")
    
    print(f"📚 Knowledge base: {kb.get_count()} dokumenata")
    print(f"📖 Baza podataka: spremna")
    print("=" * 70)


@app.on_event("shutdown")
async def shutdown_event():
    """Pokreće se kad se API ugasi"""
    db.close()
    print("API ugašen")

import asyncio
from api.main import search_catalog_for_book
async def test():
    result = await search_catalog_for_book("čovpas")
    print(result)

frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

if os.path.exists(frontend_dir):
    # Glavni root vraća frontend
    @app.get("/", include_in_schema=False)
    async def root():
        return FileResponse(os.path.join(frontend_dir, "chatbot-widget.html"))
    
    # Mount static files
    app.mount("/frontend", StaticFiles(directory=frontend_dir), name="frontend")

if __name__ == "__main__":
    import uvicorn
    asyncio.run(test())
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)


