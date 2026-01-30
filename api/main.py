"""
FastAPI Backend za Library Chatbot
REST API za chatbot i pretraživanje knjiga
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import sys
import os

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


# ==================== ENDPOINTS ====================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Library Chatbot API",
        "version": "1.0.0",
        "endpoints": {
            "chat": "/api/chat",
            "books": "/api/books/search",
            "book_details": "/api/books/{book_id}",
            "health": "/api/health"
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


# ==================== CHATBOT LOGIC ====================

def generate_response(user_message: str) -> str:
    """Generira odgovor na korisničku poruku (template-based)"""
    
    query_lower = user_message.lower()
    
    # 1. Pitanja o knjižnici
    if any(word in query_lower for word in ['učlaniti', 'članarina', 'upis']):
        return ("📚 Za učlanjenje trebate osobnu iskaznicu i pristupnicu. "
                "Članarina se plaća godišnje po kategorijama. "
                "Više na: https://www.halubajska-zora.hr")
    
    if any(word in query_lower for word in ['radno vrijeme', 'otvoreno', 'kada']):
        return ("⏰ Knjižnica radi radnim danima 8:00-20:00, subotom 8:00-14:00. "
                "Više detalja: https://www.halubajska-zora.hr")
    
    if any(word in query_lower for word in ['posuditi', 'posudba', 'koliko knjiga']):
        return ("📖 Možete posuditi do 4 knjige na 30 dana. "
                "Produženje je moguće ako knjiga nije rezervirana.")
    
    if any(word in query_lower for word in ['e-knjig', 'digitalne', 'online']):
        return ("💻 Da! Imamo e-knjige i audioknige putem ZaKi Book platforme. "
                "Do 4 naslova mjesečno na 4 uređaja.")
    
    # 2. Pretraživanje knjiga
    if any(word in query_lower for word in ['knjiga', 'knjige', 'autor']):
        keywords = extract_keywords(user_message)
        
        if keywords:
            books = []
            for keyword in keywords[:2]:
                books.extend(db.search_books(keyword, limit=3))
            
            if books:
                unique_books = {book['id']: book for book in books}.values()
                books_list = list(unique_books)[:3]
                
                response = f"Pronašao sam {len(books_list)} {'knjigu' if len(books_list) == 1 else 'knjige'}:\n\n"
                for book in books_list:
                    response += f"• {book['title']} - {book['author']}"
                    if book.get('year'):
                        response += f" ({book['year']})"
                    response += "\n"
                
                response += "\nZa dostupnost provjerite katalog: https://katalog.halubajska-zora.hr"
                return response
    
    # 3. Preporuke
    if any(word in query_lower for word in ['preporuči', 'preporuka', 'što čitati']):
        books = db.get_all_books(limit=3)
        if books:
            response = "Evo nekoliko preporuka:\n\n"
            for book in books:
                response += f"• {book['title']} - {book['author']}\n"
            return response
    
    # 4. Knowledge base search
    kb_results = kb.search(user_message, n_results=2)
    
    if kb_results and kb_results[0].get('distance', 1.0) < 0.7:
        content = kb_results[0]['content']
        if len(content) > 300:
            content = content[:300] + "..."
        
        return content + "\n\nViše na: https://www.halubajska-zora.hr"
    
    # 5. Default
    return ("Mogu vam pomoći s:\n"
            "• Informacijama o knjižnici\n"
            "• Pretraživanjem knjiga\n"
            "• Preporukama za čitanje\n\n"
            "Što vas zanima?")


def extract_keywords(query: str) -> list:
    """Izvlači ključne riječi"""
    stop_words = ['knjiga', 'knjige', 'autor', 'o', 'na', 'u', 'i', 'za', 'mi']
    words = re.findall(r'\w+', query.lower())
    return [w for w in words if w not in stop_words and len(w) > 2][:3]


# ==================== STARTUP ====================

@app.on_event("startup")
async def startup_event():
    """Pokreće se kad se API pokrene"""
    print("=" * 70)
    print("🚀 Library Chatbot API pokrenut!")
    print(f"📚 Knowledge base: {kb.get_count()} dokumenata")
    print(f"📖 Baza podataka: spremna")
    print("=" * 70)


@app.on_event("shutdown")
async def shutdown_event():
    """Pokreće se kad se API ugasi"""
    db.close()
    print("API ugašen")


# ==================== RUN ====================

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)