"""
FastAPI Backend za Library Chatbot
REST API za chatbot i pretraživanje knjiga
"""

from fastapi import FastAPI, HTTPException
from fastapi import Depends
from fastapi import Request
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
from contextlib import asynccontextmanager
from pathlib import Path
from api.groq_integration import LibraryChatbot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent

availability_checker = None
book_detail_parser = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    logger.info("Pokrećem aplikaciju...")

    app.state.http_client = httpx.AsyncClient(timeout=30.0)

    groq_key = os.getenv('GROQ_API_KEY')
    app.state.groq_enabled = bool(groq_key)

    if app.state.groq_enabled: 
        app.state.chatbot = LibraryChatbot()
        logger.info("AI chatbot spreman")
    else:
        app.state.chatbot = None
        logger.warning("AI chatbot nije aktivan")

    try:
        from scraper.availability_checker import ScraperAPIChecker
        from scraper.book_detail_parser import BookDetailParser

        app.state.availability_checker = ScraperAPIChecker()
        app.state.book_detail_parser = BookDetailParser()

    except ImportError as e:
        logger.error(f"Greška pri inicijalizaciji scrapera: {e}")
        app.state.availability_checker = None
        app.state.book_detail_parser = None

        # Fallback za lokalno testiranje ako struktura foldera varira
        sys.path.append(os.getcwd())
        
    yield

    # SHUTDOWN
    logger.info("Gasim aplikaciju...")
    await app.state.http_client.aclose()

# Inicijaliziraj FastAPI
app = FastAPI(
    title="Library Chatbot API",
    description="API za AI chatbot i pretraživanje knjiga",
    version="1.0.0",
    lifespan=lifespan
)
# CORS - omogućava frontendima da pristupa API-ju
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # U production stavi specifične domene "https://chat-widget.com"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

def get_chatbot(request: Request) -> LibraryChatbot:
    chatbot = request.app.state.chatbot
    if not chatbot:
        raise HTTPException(503, "AI chatbot nije dostupan")
    return chatbot

def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client

def get_availability_checker(request: Request):
    return request.app.state.availability_checker

async def search_catalog_for_book(query: str, request: Request) -> Dict:
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
              
        client = request.app.state.http_client
        response = await client.get(
            "http://api.scraperapi.com/",
            params=params
        )
        
        if response.status_code != 200:
            logger.error(f"ScraperAPI error: {response.status_code}")
            return None
        
        logger.info(f"Response: {len(response.text)} bytes")

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

@app.post("/api/chat", response_model=ChatResponse)
async def chat_ai(
    request: ChatRequest, 
    chatbot: LibraryChatbot = Depends(get_chatbot)
    ):
    """Groq-powered chat endpoint (NAJBRŽI!)"""
  
    try:
        history = (request.history or [])[-10:]
        response = await chatbot.chat(
            user_message=request.message,
            conversation_history=history
            )
        return {"response": response}
    
    except Exception as e:
        logger.error(f"AI chat error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail="Došlo je do greške pri obradi zahtjeva."
        )
    
@app.get("/health")
async def health(request: Request):
    return {
        "status": "ok",
        "ai": getattr(request.app.state, "groq_enabled", False),
        "http_client": request.app.state.http_client is not None
    }

frontend_dir = BASE_DIR / "frontend"

if frontend_dir.exists():
    # Glavni root vraća frontend
    @app.get("/", include_in_schema=False)
    async def root():
        return FileResponse(os.path.join(frontend_dir, "chatbot-widget.html"))
    
    # Mount static files
    app.mount("/frontend", StaticFiles(directory=frontend_dir), name="frontend")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
