
import os
import logging
from typing import Dict, List, Optional
import google.generativeai as genai

logger = logging.getLogger(__name__)


class LibraryChatbot:
    """Gemini-powered library chatbot"""
    
    def __init__(self):
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY nije postavljen!")
        
        genai.configure(api_key=api_key)
        
        # Koristi besplatni Gemini 1.5 Flash
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
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
        
        # Definiraj funkcije (Gemini function declarations)
        self.tools = self._define_tools()
    
    def _define_tools(self):
        """Definiraj function declarations za Gemini"""
        
        return [
            {
                "function_declarations": [
                    {
                        "name": "search_books",
                        "description": "Pretraži knjige u katalogu",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "Ključna riječ za pretragu"
                                },
                                "limit": {
                                    "type": "integer",
                                    "description": "Broj rezultata",
                                    "default": 5
                                }
                            },
                            "required": ["query"]
                        }
                    },
                    {
                        "name": "check_availability",
                        "description": "Provjeri dostupnost knjige",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "book_id": {
                                    "type": "string",
                                    "description": "ID knjige"
                                }
                            },
                            "required": ["book_id"]
                        }
                    },
                    {
                        "name": "get_new_books",
                        "description": "Dohvati najnovije knjige",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "days": {
                                    "type": "integer",
                                    "description": "Broj dana unazad",
                                    "default": 365
                                },
                                "limit": {
                                    "type": "integer",
                                    "default": 10
                                }
                            }
                        }
                    }
                    # ... ostale funkcije ...
                ]
            }
        ]
    
    async def chat(
        self, 
        user_message: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> str:
        """Chat sa Gemini modelom"""
        
        try:
            # Pripremi povijest s system promptom
            chat = self.model.start_chat(history=[])
            
            # Dodaj system prompt kao prvi message
            chat.send_message(self.system_prompt)
            
            # Dodaj user message
            response = chat.send_message(
                user_message,
                tools=self.tools
            )
            
            # Provjeri function calls
            if response.candidates[0].content.parts[0].function_call:
                return await self._handle_function_call(response, chat)
            
            return response.text
        
        except Exception as e:
            logger.error(f"Gemini error: {e}")
            return "Nažalost, došlo je do greške. Pokušaj ponovno."
    
    async def _handle_function_call(self, response, chat):
        """Obradi Gemini function call"""
        
        function_call = response.candidates[0].content.parts[0].function_call
        function_name = function_call.name
        function_args = dict(function_call.args)
        
        logger.info(f"Gemini poziva: {function_name}({function_args})")
        
        # Pozovi funkciju
        result = await self._execute_function(function_name, function_args)
        
        # Vrati rezultat Geminiju
        response = chat.send_message(
            genai.protos.Content(
                parts=[genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=function_name,
                        response={"result": result}
                    )
                )]
            )
        )
        
        return response.text
    
    async def _execute_function(self, function_name: str, function_args: Dict):
        """Izvršava funkcije"""
        
        # Import scrapers
        from scraper.availability_checker import ScraperAPIChecker
        from scraper.new_books_scraper import NewBooksScraper
        # ... itd. (isti kod kao prije)
        
        # Implementacija funkcija
        if function_name == "search_books":
            # ...
            pass
        elif function_name == "check_availability":
            # ...
            pass
        # ... itd.