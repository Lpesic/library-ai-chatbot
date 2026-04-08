"""
Groq Integration - NAJBRŽA AI integracija
"""

import os
import logging
import sqlite3
from typing import Dict, List, Optional
from groq import AsyncGroq

logger = logging.getLogger(__name__)


class LibraryChatbot:
    """Groq-powered library chatbot"""
    
    def __init__(self):
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            logger.error("GROQ_API_KEY nije postavljen u .env!")
            self.client = None
            return
        
        # Async Groq client
        self.client = AsyncGroq(api_key=api_key)
        
        # Koristi Llama 3.3 70B - najbrži i najpametniji besplatni model
        self.model = "llama-3.3-70b-versatile"
        
        # System prompt
        self.system_prompt = """
Ti si AI asistent Knjižnice Halubajska Zora u Hrvatskoj.

Tvoja uloga:
- Pomažeš korisnicima s informacijama o knjižnici
- Pretražuješ katalog knjiga
- Provjereš dostupnost knjiga
- Preporučuješ knjige

VAŽNO: Uvijek odgovaraj na hrvatskom jeziku.

Informacije o knjižnici:
- Radno vrijeme: Pon-Pet 8:00-20:00, Sub 8:00-14:00, Ned zatvoreno
- Članarina: Besplatna za stanovnike grada
- Posudba: Do 5 knjiga na 30 dana
- Web: https://katalog.halubajska-zora.hr

Budi koncizan - maksimalno 3-4 rečenice osim ako korisnik ne traži detaljno objašnjenje.
"""
        
        # Function definitions (Groq podržava tool use!)
        self.tools = self._define_tools()
    
    def _define_tools(self):
        """Definiraj funkcije koje AI može koristiti"""
        
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_books",
                    "description": "Pretraži knjige u katalogu prema naslovu ili autoru",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Ključna riječ za pretragu (naslov ili autor)"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Broj rezultata (default 5)",
                                "default": 5
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_availability",
                    "description": "Provjeri je li knjiga dostupna za posudbu i na kojim lokacijama",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "book_id": {
                                "type": "string",
                                "description": "ID knjige iz kataloga"
                            }
                        },
                        "required": ["book_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_new_books",
                    "description": "Dohvati najnovije nabavljene knjige u knjižnici",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "days": {
                                "type": "integer",
                                "description": "Period u danima (default 365)"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Broj knjiga (default 10)"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_most_read",
                    "description": "Dohvati najčitanije/najpopularnije knjige",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "days": {
                                "type": "integer",
                                "description": "Period: 7, 30, 90, 180 ili 365 dana"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_by_subject",
                    "description": "Pretraži knjige po tematskom području (psihologija, sport, povijest, medicina...)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subject": {
                                "type": "string",
                                "description": "Tematsko područje"
                            }
                        },
                        "required": ["subject"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_by_language",
                    "description": "Pretraži knjige na određenom jeziku",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "language": {
                                "type": "string",
                                "description": "Jezik (hrvatski, engleski, njemački, latinski...)"
                            }
                        },
                        "required": ["language"]
                    }
                }
            }
        ]
    
    async def chat(
        self, 
        user_message: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> str:
        """Chat sa Groq modelom"""
        
        if not self.client:
            return "⚠️ Groq API nije konfiguriran. Postavi GROQ_API_KEY u .env datoteci."
        
        try:
            logger.info(f"Groq request: {user_message}")
            
            # Pripremi poruke
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            # Pozovi Groq sa tool use
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tools,
                tool_choice="auto",  # AI odlučuje kad koristiti funkcije
                temperature=0.3,
                max_tokens=1000
            )
            
            response_message = response.choices[0].message
            
            # Provjeri ima li function calls
            if response_message.tool_calls:
                logger.info(f"Groq poziva {len(response_message.tool_calls)} funkcija")
                return await self._handle_function_calls(response_message, messages)
            
            # Obični odgovor
            return response_message.content
        
        except Exception as e:
            logger.error(f"Groq error: {e}")
            import traceback
            traceback.print_exc()
            return "Nažalost, došlo je do greške. Pokušaj ponovno."
    
    async def _handle_function_calls(self, response_message, messages: List[Dict]) -> str:
        """Obradi function calls"""
        
        # Dodaj AI-ov odgovor u povijest
        messages.append({
            "role": "assistant",
            "content": response_message.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in response_message.tool_calls
            ]
        })
        
        # Izvršava funkcije
        for tool_call in response_message.tool_calls:
            function_name = tool_call.function.name
            
            # Parse JSON argumenta
            import json
            function_args = json.loads(tool_call.function.arguments)
            
            logger.info(f"Executing: {function_name}({function_args})")
            
            # Pozovi funkciju
            function_response = await self._execute_function(function_name, function_args)
            
            # Dodaj rezultat u povijest
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": function_name,
                "content": str(function_response)
            })
        
        # Pozovi Groq ponovno sa rezultatima
        final_response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3,
            max_tokens=1000
        )
        
        return final_response.choices[0].message.content
    
    async def _execute_function(self, function_name: str, function_args: Dict):
        """Izvršava pozvanu funkciju"""
        
        # Import scrapers
        from scraper.availability_checker import ScraperAPIChecker
        from scraper.new_books_scraper import NewBooksScraper
        from scraper.category_scraper import CategoryScraper
        
        availability_checker = ScraperAPIChecker()
        new_books_scraper = NewBooksScraper()
        category_scraper = CategoryScraper()
        
        # Helper za database
        def search_books_db(query: str, limit: int = 5):
            try:
                conn = sqlite3.connect('data/library.db')
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, title, author, year, publisher 
                    FROM books 
                    WHERE title LIKE ? OR author LIKE ?
                    LIMIT ?
                """, (f'%{query}%', f'%{query}%', limit))
                
                rows = cursor.fetchall()
                conn.close()
                
                if not rows:
                    return {"books": [], "message": f"Nema rezultata za '{query}'"}
                
                return {
                    "books": [dict(row) for row in rows],
                    "count": len(rows)
                }
            except Exception as e:
                logger.error(f"DB error: {e}")
                return {"error": str(e)}
        
        try:
            # PRETRAGA KNJIGA
            if function_name == "search_books":
                query = function_args.get("query")
                limit = function_args.get("limit", 5)
                return search_books_db(query, limit)
            
            # DOSTUPNOST
            elif function_name == "check_availability":
                book_id = function_args.get("book_id")
                result = await availability_checker.check_availability(book_id)
                return result
            
            # NOVE KNJIGE
            elif function_name == "get_new_books":
                days = function_args.get("days", 365)
                limit = function_args.get("limit", 10)
                
                books = await new_books_scraper.get_new_books(days=days, limit=limit)
                return {"books": books, "count": len(books)}
            
            # NAJČITANIJE
            elif function_name == "get_most_read":
                days = function_args.get("days", 30)
                
                books = await category_scraper.get_most_read(days=days, limit=10)
                return {"books": books, "count": len(books)}
            
            # TEMA
            elif function_name == "search_by_subject":
                subject = function_args.get("subject")
                
                items = await category_scraper.get_items_by_subject(subject=subject, limit=8)
                return {"items": items, "count": len(items)}
            
            # JEZIK
            elif function_name == "search_by_language":
                language = function_args.get("language")
                
                items = await category_scraper.get_items_by_language(language=language, limit=8)
                return {"items": items, "count": len(items)}
            
            else:
                return {"error": f"Unknown function: {function_name}"}
        
        except Exception as e:
            logger.error(f"Function execution error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e)}


# Quick test
if __name__ == "__main__":
    import asyncio
    
    async def test():
        print("=" * 70)
        print("GROQ CHATBOT TEST")
        print("=" * 70)
        
        chatbot = LibraryChatbot()
        
        test_queries = [
            "Koje knjige ima Jo Nesbø?",
            "Što ima novo?",
            "Preporuči mi psihologiju"
        ]
        
        for query in test_queries:
            print(f"\nUSER: {query}")
            print("-" * 70)
            
            response = await chatbot.chat(query)
            print(f"BOT: {response}\n")
    
    asyncio.run(test())