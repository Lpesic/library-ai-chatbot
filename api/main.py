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
import os
import logging
import re
import asyncio
import uuid
import time

from pathlib import Path
from slowapi import Limiter

from slowapi.util import get_remote_address
from contextlib import asynccontextmanager

from slowapi.middleware import SlowAPIMiddleware
from fastapi.middleware.gzip import GZipMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()],
    force=True
)

from api.sambanova_integration import LibraryChatbot

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent

@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    logger.info("Pokrećem aplikaciju...")
    app.state.started_at = time.time()

    sambanova_key = os.getenv('SAMBANOVA_KEY')
    app.state.sambanova_enabled = bool(sambanova_key)

    if app.state.sambanova_enabled: 
        app.state.chatbot = LibraryChatbot()
        logger.info("AI chatbot spreman")
    else:
        app.state.chatbot = None
        logger.warning("AI chatbot nije aktivan")

    yield

    # SHUTDOWN
    logger.info("Gasim aplikaciju...")

# Inicijaliziraj FastAPI
app = FastAPI(
    title="Library Chatbot API",
    description="API za AI chatbot i pretraživanje knjiga",
    version="1.0.0",
    lifespan=lifespan
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# GZIP - komprimacija većih odgovora
app.add_middleware(GZipMiddleware, minimum_size=1000)

# REQUEST ID MIDDLEWARE
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id

    return response

# SECURITY HEADERS MIDDLEWARE
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    return response

# CORS - omogućava frontendima da pristupa API-ju jer ce domene frontenda i backenda biti razlicite
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # U produkciji će biti specifične domene "https://halubajska-zora.com"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#SLOWAPI
app.add_middleware(SlowAPIMiddleware)

# Pydantic modeli za request/response
class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict]] = None
    
class ChatResponse(BaseModel):
    response: str
    

def get_chatbot(request: Request) -> LibraryChatbot:
    chatbot = request.app.state.chatbot
    if not chatbot:
        raise HTTPException(503, "AI chatbot nije dostupan")
    return chatbot


# ENDPOINTS 

@app.post("/api/chat", response_model=ChatResponse)
@limiter.limit("10/minute")
async def chat_ai(
    request: Request,
    body: ChatRequest,
    chatbot: LibraryChatbot = Depends(get_chatbot)
):
    """SN-powered chat endpoint"""

    logger.info(f"[{request.state.request_id}] Incoming request")

    # ANTI-SPAM VALIDACIJA
    message = body.message
    logger.info(f"[{request.state.request_id}] Message length: {len(message)}")

    if not message or not message.strip():
        logger.warning(f"[{request.state.request_id}] EMPTY MESSAGE")
        raise HTTPException(status_code=400, detail="Ups! Poruka je prazna.")

    if len(message) > 2000:
        logger.warning(f"[{request.state.request_id}] MESSAGE TOO LONG: {len(message)}")
        raise HTTPException(status_code=400, detail="Ups! Poruka je preduga.")

    if len(message.strip()) < 2:
        logger.warning(f"[{request.state.request_id}] MESSAGE TOO SHORT")
        raise HTTPException(status_code=400, detail="Ups! Poruka je prekratka.")
    
    if len(re.sub(r"\W", "", message)) == 0:
        logger.warning(f"[{request.state.request_id}] INVALID SYMBOL-ONLY MESSAGE")
        raise HTTPException(400, "Ups! Ne mogu to razumjeti.")
  
    try:
        history = (body.history or [])[-10:]
        response = await asyncio.wait_for(
            chatbot.chat(
                user_message=body.message,
                conversation_history=history
            ),
            timeout=40
        )
        logger.info(f"[{request.state.request_id}] Response generated")

        return {"response": response}
    
    except asyncio.TimeoutError:
        logger.error(f"[{request.state.request_id}] Request timeout")
        raise HTTPException(
            status_code=504,
            detail="AI odgovor traje predugo."
        )
    
    except Exception as e:
        logger.error(
            f"[{request.state.request_id}] AI chat error: {e}",
            exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail="Došlo je do greške pri obradi zahtjeva.")
    
@app.get("/health")
async def health(request: Request):
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - request.app.state.started_at),
        "ai": getattr(request.app.state, "sambanova_enabled", False)
    }

@app.get("/favicon.png", include_in_schema=False)
async def favicon():
    return FileResponse("frontend/favicon.png")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon_ico():
    return FileResponse("frontend/favicon.png", media_type="image/png")

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
