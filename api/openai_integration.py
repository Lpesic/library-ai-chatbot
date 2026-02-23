"""
OpenAI Integration - Function calling za library chatbot
"""

import os
from typing import Dict, List, Optional
import logging
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class LibraryChatbot:
    """OpenAI-powered library chatbot sa function calling"""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.model = "gpt-4o-mini"  # Ili gpt-4o za bolju kvalitetu
        
        # System prompt
        self.system_prompt = """
Ti si AI asistent Knjižnice Halubajska Zora u Hrvatskoj.

Tvoja uloga:
- Pomažeš korisnicima s informacijama o knjižnici
- Pretražuješ katalog knjiga
- Provjereš dostupnost knjiga
- Preporučuješ knjige prema interesima korisnika
- Daješ informacije o radnom vremenu, učlanjenju i uslugama

Ponašanje:
- Uvijek budi ljubazan i profesionalan
- Odgovaraj na hrvatskom jeziku
- Ako ne znaš odgovor, reci to iskreno
- Za specifične upite koristi dostupne funkcije

Informacije o knjižnici:
- Radno vrijeme: Pon-Pet 8:00-20:00, Sub 8:00-14:00, Ned zatvoreno
- Članarina: Besplatna za stanovnike grada
- Posudba: Do 5 knjiga na 30 dana
- Web: https://katalog.halubajska-zora.hr
"""
        
        # Definiraj sve dostupne funkcije
        self.tools = self._define_tools()
    
    def _define_tools(self) -> List[Dict]:
        """Definiraj sve funkcije koje chatbot može koristiti"""
        
        return [
            # 1. PRETRAGA KNJIGA
            {
                "type": "function",
                "function": {
                    "name": "search_books",
                    "description": "Pretraži knjige u katalogu prema ključnoj riječi, autoru ili naslovu",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Ključna riječ za pretragu (naslov, autor, tema)"
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
            
            # 2. PROVJERA DOSTUPNOSTI
            {
                "type": "function",
                "function": {
                    "name": "check_availability",
                    "description": "Provjeri je li knjiga dostupna za posudbu",
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
            
            # 3. OPIS KNJIGE
            {
                "type": "function",
                "function": {
                    "name": "get_book_details",
                    "description": "Dohvati detaljne informacije o knjizi (opis, autor, godina, ISBN...)",
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
            
            # 4. NOVE KNJIGE
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
                                "description": "Broj dana unazad (default 365)",
                                "default": 365
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Broj knjiga (default 10)",
                                "default": 10
                            }
                        }
                    }
                }
            },
            
            # 5. NAJČITANIJE KNJIGE
            {
                "type": "function",
                "function": {
                    "name": "get_most_read",
                    "description": "Dohvati najčitanije/najpopularnije knjige u određenom periodu",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "days": {
                                "type": "integer",
                                "description": "Period u danima: 7, 30, 90, 180, 365",
                                "enum": [7, 30, 90, 180, 365],
                                "default": 30
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Broj knjiga",
                                "default": 10
                            }
                        }
                    }
                }
            },
            
            # 6. PRETRAGA PO KATEGORIJI
            {
                "type": "function",
                "function": {
                    "name": "search_by_category",
                    "description": "Pretraži knjige po vrsti građe (knjiga, DVD, CD, igračka...)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "description": "Vrsta građe",
                                "enum": ["knjiga", "igračke", "dvd", "cd", "časopis", "e-knjiga"]
                            },
                            "limit": {
                                "type": "integer",
                                "default": 8
                            }
                        },
                        "required": ["category"]
                    }
                }
            },
            
            # 7. PRETRAGA PO SADRŽAJU (UDK)
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
                                "description": "Tematsko područje",
                                "enum": [
                                    "književnost", "hrvatska književnost", "psihologija", 
                                    "medicina", "sport", "povijest", "politika", 
                                    "filozofija", "ekonomija", "glazba", "slikarstvo",
                                    "geografija", "biologija", "matematika", "fizika",
                                    "astronomija", "kemija", "računarstvo", "arhitektura"
                                ]
                            },
                            "limit": {
                                "type": "integer",
                                "default": 8
                            }
                        },
                        "required": ["subject"]
                    }
                }
            },
            
            # 8. PRETRAGA PO JEZIKU
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
                                "description": "Jezik knjige",
                                "enum": [
                                    "hrvatski", "engleski", "njemački", "talijanski",
                                    "francuski", "španjolski", "latinski", "grčki",
                                    "srpski", "bosanski", "ruski", "kineski"
                                ]
                            },
                            "limit": {
                                "type": "integer",
                                "default": 8
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
        """
        Glavna chat funkcija sa function calling
        
        Args:
            user_message: Poruka korisnika
            conversation_history: Opciona povijest razgovora
            
        Returns:
            Odgovor chatbota
        """
        
        try:
            # Pripremi poruke
            messages = [{"role": "system", "content": self.system_prompt}]
            
            if conversation_history:
                messages.extend(conversation_history)
            
            messages.append({"role": "user", "content": user_message})
            
            logger.info(f"OpenAI request: {user_message}")
            
            # Pozovi OpenAI
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tools,
                tool_choice="auto",  # GPT odlučuje kad koristiti funkcije
                temperature=0.7
            )
            
            response_message = response.choices[0].message
            
            # Provjeri je li GPT pozvao funkciju
            if response_message.tool_calls:
                logger.info(f"GPT poziva {len(response_message.tool_calls)} funkcija")
                return await self._handle_function_calls(
                    response_message, 
                    messages
                )
            else:
                # Direktan odgovor bez funkcija
                return response_message.content
        
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            return "Nažalost, došlo je do greške. Molim pokušajte ponovno."
    
    async def _handle_function_calls(
        self, 
        response_message, 
        messages: List[Dict]
    ) -> str:
        """Obradi function calls od GPT-a"""
        
        # Dodaj GPT-ov odgovor u povijest
        messages.append({
            "role": "assistant",
            "content": response_message.content,
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
            function_args = eval(tool_call.function.arguments)  # JSON parse
            
            logger.info(f"Executing: {function_name}({function_args})")
            
            # Pozovi odgovarajuću funkciju
            function_response = await self._execute_function(
                function_name, 
                function_args
            )
            
            # Dodaj rezultat u povijest
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(function_response)
            })
        
        # Pozovi GPT ponovno sa rezultatima funkcija
        second_response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7
        )
        
        return second_response.choices[0].message.content
    
    async def _execute_function(
        self, 
        function_name: str, 
        function_args: Dict
    ) -> Dict:
        """Izvršava pozvan funkciju - ovo povezujemo sa našim scraperima"""
        
        # Import scrapers OVDJE (da izbjegnemo circular import)
        from scraper.availability_checker import ScraperAPIChecker
        from scraper.new_books_scraper import NewBooksScraper
        from scraper.category_scraper import CategoryScraper
        from scraper.book_detail_parser import BookDetailParser
        import sqlite3
        
        availability_checker = ScraperAPIChecker()
        new_books_scraper = NewBooksScraper()
        category_scraper = CategoryScraper()
        book_detail_parser = BookDetailParser()

        def search_books_db(query: str, limit: int = 5):
            """Pretraži knjige u SQLite bazi"""
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
            
            return [dict(row) for row in rows]
        
        try:
            # PRETRAGA KNJIGA
            if function_name == "search_books":
                query = function_args.get("query")
                limit = function_args.get("limit", 5)
                
                books = search_books_db(query, limit=limit)
                
                if not books:
                    return {"books": [], "message": f"Nema rezultata za '{query}'"}
                
                return {
                    "books": books,
                    "count": len(books)
                }
            
            # DOSTUPNOST
            elif function_name == "check_availability":
                book_id = function_args.get("book_id")
                result = await availability_checker.check_availability(book_id)
                return result
            
            # DETALJI KNJIGE
            elif function_name == "get_book_details":
                book_id = function_args.get("book_id")
                result = book_detail_parser.parse_book_detail(book_id)
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
                limit = function_args.get("limit", 10)
                
                books = await category_scraper.get_most_read(days=days, limit=limit)
                return {"books": books, "count": len(books)}
            
            # KATEGORIJA
            elif function_name == "search_by_category":
                category = function_args.get("category")
                limit = function_args.get("limit", 8)
                
                items = await category_scraper.get_items_by_category(
                    category=category, 
                    limit=limit
                )
                return {"items": items, "count": len(items)}
            
            # SADRŽAJ (UDK)
            elif function_name == "search_by_subject":
                subject = function_args.get("subject")
                limit = function_args.get("limit", 8)
                
                items = await category_scraper.get_items_by_subject(
                    subject=subject,
                    limit=limit
                )
                return {"items": items, "count": len(items)}
            
            # JEZIK
            elif function_name == "search_by_language":
                language = function_args.get("language")
                limit = function_args.get("limit", 8)
                
                items = await category_scraper.get_items_by_language(
                    language=language,
                    limit=limit
                )
                return {"items": items, "count": len(items)}
            
            else:
                return {"error": f"Unknown function: {function_name}"}
        
        except Exception as e:
            logger.error(f"Function execution error: {e}")
            return {"error": str(e)}


# Test
if __name__ == "__main__":
    import asyncio
    
    async def test():
        print("=" * 70)
        print("OPENAI CHATBOT TEST")
        print("=" * 70)
        
        chatbot = LibraryChatbot()
        
        test_queries = [
            "Koje knjige ima Jo Nesbø?",
            "Je li Vučji sat dostupan?",
            "O čemu se radi u knjizi Vučji sat?",
            "Što ima novo u knjižnici?",
            "Najčitanije knjige ovaj mjesec?",
            "Preporuči mi psihologiju",
            "Knjige na engleskom?"
        ]
        
        for query in test_queries:
            print(f"\n{'='*70}")
            print(f"USER: {query}")
            print(f"{'-'*70}")
            
            response = await chatbot.chat(query)
            print(f"BOT: {response}")
    
    asyncio.run(test())