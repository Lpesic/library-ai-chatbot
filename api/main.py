"""
FastAPI Backend za Library Chatbot
REST API za chatbot i pretraživanje knjiga
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, List
import sys
import os
import logging
import re
import httpx
from bs4 import BeautifulSoup
from api.groq_integration import LibraryChatbot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#path setup
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from scraper.availability_checker import ScraperAPIChecker
    from database.db_manager import DatabaseManager
    from chatbot.knowledge_base import KnowledgeBase
    from scraper.book_detail_parser import BookDetailParser
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
groq_key = os.getenv('GROQ_API_KEY')
GROQ_ENABLED = bool(groq_key)

availability_checker = ScraperAPIChecker()
book_detail_parser = BookDetailParser()
db = DatabaseManager()
kb = KnowledgeBase()

if GROQ_ENABLED:
    logger.info("Groq API key pronađen - ULTRA BRZO!")
    ai_chatbot = LibraryChatbot()
else:
    logger.warning("Groq API key nije postavljen")
    ai_chatbot = None

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
    history: Optional[List[Dict]] = None
    
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

@app.post("/api/chat", response_model=ChatResponse)
async def chat_ai(request: ChatRequest):
    """Groq-powered chat endpoint (NAJBRŽI!)"""
    if not ai_chatbot:
        raise HTTPException(
            status_code=503, 
            detail="AI chatbot nije konfiguriran. Postavi GROQ_API_KEY."
        )
    
    try:
        history = request.history[-10:] if request.history else []
        response = await ai_chatbot.chat(
            user_message=request.message,
            conversation_history=history
            )
        return {"response": response}
    
    except Exception as e:
        logger.error(f"AI chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
        print(f"Problem s bazom: {e}")
    
    if not all_books or len(all_books) == 0:
        print("Baza je prazna - učitavam knjige iz JSON-a...")
        
        # Učitaj iz JSON-a
        import glob
        json_files = glob.glob("data/books_catalog*.json")
        
        if json_files:
            count = db.import_from_json(json_files[0])
            print(f"Učitano {count} knjiga u bazu")
        else:
            print("Nema JSON fajlova za import!")
    else:
        print(f"Baza već sadrži knjige: {len(all_books)}")
    
    print(f"Knowledge base: {kb.get_count()} dokumenata")
    print(f"Baza podataka: spremna")
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
