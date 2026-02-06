"""
FastAPI Backend za Library Chatbot
REST API za chatbot i pretraživanje knjiga
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scraper.availability_checker import AvailabilityChecker
availability_checker = AvailabilityChecker()

# Dodaj parent directory u path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from database.db_manager import DatabaseManager
from chatbot.knowledge_base import KnowledgeBase
import re

# Inicijaliziraj FastAPI
app = FastAPI(
    title="Library Chatbot API",
    description="API za AI chatbot i pretraživanje knjiga",
    version="1.0.0"
)

# CORS - omogućava frontends da pristupa API-ju
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # U production stavi specifične domene
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicijaliziraj bazu i knowledge base
db = DatabaseManager()
kb = KnowledgeBase()

# Učitaj knowledge base ako je prazan
if kb.get_count() == 0:
    if os.path.exists('data/membership_info.json'):
        kb.add_from_json('data/membership_info.json')
    if os.path.exists('data/website_all_pages.json'):
        kb.add_from_json('data/website_all_pages.json')


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
    Provjeri dostupnost knjige u stvarnom vremenu
    """
    try:
        availability = availability_checker.check_availability(book_id)
        return availability
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
        response = generate_response(user_message)
        
        return ChatResponse(response=response)
        
    except Exception as e:
        print(f"SISTEMSKA GRESKA: {str(e)}") 
        raise HTTPException(status_code=500, detail=f"Python Error: {str(e)}")


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


# CHATBOT LOGIC

def generate_response(user_message: str) -> str:
    """Generira odgovor na korisničku poruku (template-based)"""
    
    query_lower = user_message.lower()
    #0. PROVJERA DOSTUPNOSTI 
    if any(word in query_lower for word in ['dostupn', 'posuden', 'je li', 'jel', 'ima li na', 'rezerv']):
        # Pokušaj pronaći naziv knjige
        # Jednostavna logika - traži knjigu po ključnim riječima
        keywords = extract_keywords(user_message)
        
        if keywords:
            # Pretraži bazu za ID knjige
            books = db.search_books(keywords[0], limit=1)
            
            if books:
                book = books[0]
                book_id = book['id']
                
                # Provjeri dostupnost
                availability = availability_checker.check_availability(book_id)
                return availability_checker.format_availability_message(availability)
            else:
                return f"Nisam pronašao knjigu '{keywords[0]}'. Molim unesite točan naslov ili provjerite katalog."
        else:
            return "Molim navedite naziv knjige čiju dostupnost želite provjeriti."    

    # 1. PREPORUKE - Provjeri PRVO (prije općih upita o knjigama)
    if any(word in query_lower for word in ['preporuč', 'preporuka', 'preporučuješ', 'predloži', 'što čitati', 'što da čitam', 'za čitanje', 'knjiga za']):
        # Izvuci temu ako postoji
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
    
    # 5. Default
    return ("📚 **Dobrodošli!** Mogu vam pomoći s:\n\n"
            "• Informacijama o knjižnici (radno vrijeme, članstvo...)\n"
            "• Pretraživanjem knjiga po naslovu ili autoru\n"
            "• Preporukama za čitanje\n\n"
            "Što vas zanima?")


def extract_keywords(query: str) -> list:
    """Izvlači ključne riječi"""
    stop_words = ['knjiga', 'knjige', 'autor', 'o', 'na', 'u', 'i', 'za', 'mi']
    words = re.findall(r'\w+', query.lower())
    return [w for w in words if w not in stop_words and len(w) > 2][:3]


# STARTUP

@app.on_event("startup")
async def startup_event():
    """Pokreće se kad se API pokrene"""
    print("=" * 70)
    print("🚀 Library Chatbot API pokrenut!")
    
    # Provjeri je li baza prazna
    all_books = db.get_all_books(limit=1)
    
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
    import os
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)