import os
import logging
import sqlite3
from typing import Dict, List, Optional
# Koristimo ISKLJUČIVO novi SDK
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class LibraryChatbot:
    def __init__(self):
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            logger.error("Nema API ključa u .env datoteci!")
            self.client = None
            return

        # Inicijalizacija novog klijenta
        self.client = genai.Client(api_key=api_key)
        
        # Koristimo model koji je tvoj test potvrdio
        self.model_id = 'models/gemini-flash-latest'

        self.system_prompt = """
        Ti si AI asistent Knjižnice Halubajska Zora. 
        Odgovaraj na hrvatskom jeziku.
        Radno vrijeme: Pon-Pet 08:00-20:00, Sub 08:00-14:00.
        """

        self.chat_session = self.client.chats.create(
            model=self.model_id,
            config=types.GenerateContentConfig(
                system_instruction=self.system_prompt,
                temperature=0.3,  # Niža temperatura = brži i konkretniji odgovori
                max_output_tokens=500, # Ograniči duljinu odgovora
                top_p=0.8,
                top_k=40
            )
        )

    def _db_search(self, query: str):
        try:
            conn = sqlite3.connect('data/library.db')
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # Tražimo po naslovu ili autoru
            cursor.execute("SELECT title, author FROM books WHERE title LIKE ? OR author LIKE ? LIMIT 5", 
                        (f'%{query}%', f'%{query}%'))
            results = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            # AKO JE LISTA PRAZNA, RECI MU TO JASNO:
            if not results:
                return "Nažalost, trenutno nemam takvih knjiga u bazi. Ponudi korisniku općenit savjet."
                
            return results
        except Exception as e:
            return f"Greška: {e}"

    async def chat(self, user_message: str) -> str:
        if not self.client:
            return "Greška s API klijentom."

        try:
            # 1. Prvi poziv Geminiju
            response = self.chat_session.send_message(message=user_message)
            
            # Provjera ima li uopće odgovora
            if not response.candidates or not response.candidates[0].content.parts:
                return "Nažalost, nisam uspio generirati odgovor."

            # Izvlačenje dijelova odgovora
            parts = response.candidates[0].content.parts
            
            # Provjeravamo ima li poziva funkcije (Function Call)
            function_call = next((part.function_call for part in parts if part.function_call), None)

            if function_call:
                logger.info(f"Model zove funkciju: {function_call.name}")
                
                # Izvrši pretragu u bazi
                db_result = self._db_search(function_call.args.get("query", ""))

                # 2. Drugi poziv Geminiju (šaljemo rezultat funkcije nazad)
                # Gemini će sada uzeti ono "Pozdrav..." i nastaviti s konkretnim knjigama
                final_response = self.chat_session.send_message(
                    message=[types.Part.from_function_response(
                        name=function_call.name,
                        response={"result": db_result}
                    )]
                )
                return final_response.text

            # Ako NIJE bilo poziva funkcije, samo vrati običan tekst
            return response.text

        except Exception as e:
            logger.error(f"Chat Error: {e}")
            import traceback
            traceback.print_exc()
            return "Došlo je do greške. Pokušajte ponovno."