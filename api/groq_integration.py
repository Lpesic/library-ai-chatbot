"""
Groq Integration - NAJBRŽA AI integracija
"""

import os, json, sys
import logging
import sqlite3
from typing import Dict, List, Optional
from groq import AsyncGroq

logger = logging.getLogger(__name__)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class LibraryChatbot:
    """Groq-powered library chatbot"""
    
    def load_membership_info(self) -> str:
        """Učitaj informacije o članstvu"""
        path = 'data/membership_info.json'
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'sections' in data:
                    all_text = []
                    for section in data['sections']:
                        title = section.get('title', '')
                        content = " ".join(section.get('content', []))
                        all_text.append(f"--- {title} ---\n{content}")
                    return "\n\n".join(all_text)
                
                return data.get('full_text', '')
        except Exception as e:
            print(f"Nisam uspio učitati membership_info.json: {e}")
            return ""

    def __init__(self):
        from scraper.advanced_url_builder import AdvancedUrlBuilder
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            logger.error("GROQ_API_KEY nije postavljen u .env!")
            self.client = None
            return
        self.url_builder = AdvancedUrlBuilder(api_key)

        # Async Groq client
        self.client = AsyncGroq(api_key=api_key)
        
        # Koristi Llama 3.3 70B - najbrži i najpametniji besplatni model
        self.model = "llama-3.3-70b-versatile"
        
        info = self.load_membership_info()
        # System prompt
        self.system_prompt = f"""
        Ti si AI asistent Knjižnice Halubajska Zora u Hrvatskoj.

        ### INFORMACIJE O KNJIŽNICI (Članstvo i pravila):
        {info}

        ### TVOJA ULOGA:
        - Pomažeš korisnicima s informacijama o knjižnici
        - Pretražuješ katalog knjiga
        - Provjereš dostupnost knjiga
        - Preporučuješ knjige

        ### PRAVILA:
        - UVIJEK odgovaraj na hrvatskom jeziku
        - Budi koncizan (2-4 rečenice)
        - Koristi dostupne funkcije za točne podatke - NE izmišljaj!
        - NE KORISTI 'search_catalog' za pitanja o radnom vremenu, članarini, lokaciji ili kontaktima.
        - Ako korisnik odgovara s "da", "ne", "ok" - poveži to s prethodnim pitanjem 

        ### DOSTUPNE FUNKCIJE:
        1. **search_catalog** - Pretraživanje kataloga po BILO KOJIM kriterijima:
        - Teme (psihologija, sport, medicina...)
        - Jezici (engleski, latinski, slovenski...)
        - Vrste građe (film, CD, igračka, e-knjiga...)
        - Noviteti (nove knjige)
        - Najpopularnije (top knjige)
        - Kombinacije (npr. "filmovi o medicini na slovenskom")

        2. **check_availability** - Provjera dostupnosti pojedine knjige

        3. **get_book_description** - Opis knjige (kad korisnik pita "o čemu se radi")

        4. **get_library_events** - Događaji, radionice, novosti. PRIMJERI:
        - "Što se događa u knjižnici?" → get_library_events(event_type="upcoming")
        - "Koje su radionice bile?" → get_library_events(event_type="past")
        - "Novosti u knjižnici" → get_library_events(event_type="all")

        ### PRAVILA ZA TOOL USE:
        - Kada pozivaš funkciji, koristi argumente SAMO u validnom JSON formatu
        - Nemoj dodavati nikakav tekst niti XML oznake poput '<function=' oko poziva alata
        - Ako koristiš 'search_catalog', upit treba biti običan string
        """
        
        # Function definitions (Groq podržava tool use!)
        self.tools = self._define_tools()

    def _define_tools(self):
        """Definiraj funkcije koje AI može koristiti"""
        
        return [
            # DOSTUPNOST
            {
                "type": "function",
                "function": {
                    "name": "check_availability",
                    "description": "Provjeri je li knjiga dostupna za posudbu i na kojim lokacijama.Koristi SAMO kad korisnik pita o dostupnosti, statusu ili je li knjiga posuđena",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "book_title": {
                                "type": "string",
                                "description": "Točan naslov knjige iz kataloga"
                            }
                        },
                        "required": ["book_title"]
                    }
                }
            },
            # OPIS KNJIGE
            {
                "type": "function",
                "function": {
                    "name": "get_book_description",
                    "description": "Dohvati opis/anotaciju knjige. Koristi kad korisnik pita 'o čemu se radi', 'opis knjige', 'radnja', 'tema knjige', 'sažetak'",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "book_title": {
                                "type": "string",
                                "description": "Naslov knjige"
                            },
                            "mode": {
                                "type": "string",
                                "description": "Tip opisa",
                                "enum": ["summary", "full"],
                                "default": "summary"
                            }
                        },
                        "required": ["book_title"]
                    }
                }
            },
            # PRETRAGA KNJIGA PO SVIM PARAMETRIMA - FILTERI I SORTIRANJE
            {
            "type": "function",
            "function": {
                "name": "search_catalog",
                "description": "Koristi isključivo za SVE upite o knjigama: pretraga po temi, jeziku, vrsti građe, novitetima, najčitanijima ili preporukama.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string", 
                            "description": "Originalni upit korisnika (npr. 'nove knjige na engleskom' ili 'psihologija')"
                        }
                    },
                    "required": ["query"]
                    }
                }
            },
            # DOGAĐAJI
            {
                "type": "function",
                "function": {
                    "name": "get_library_events",
                    "description": "Dohvati informacije o događajima, radionicama i novostima u knjižnici. Koristi kad korisnik pita o događanjima, radionicama, pričaonicama, novostima ili aktivnostima.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "event_type": {
                                "type": "string",
                                "description": "Tip događaja",
                                "enum": ["all", "upcoming", "past"],
                                "default": "all"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Broj događaja",
                                "default": 5
                            }
                        }
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
            return "Groq API nije konfiguriran. Postavi GROQ_API_KEY u .env datoteci."
        
        try:
            logger.info(f"Groq request: {user_message}")
            
            # Pripremi poruke
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "system", "content": "Tool calls must be valid JSON. No markdown, no tags."},
                {"role": "user", "content": user_message}
            ]

            if conversation_history:
                filtered_history = [
                    msg for msg in conversation_history
                    if msg.get("role") in ["user", "asistant"]
                ]
                messages.extend(filtered_history[-8:])
                logger.info(f"Dodao {len(filtered_history[-8:])} poruka iz povijesti")

            messages.append({"role": "user", "content": user_message})    
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
        import re

        # Dodaj AI-ov odgovor u povijest
        messages.append({
                "role": "assistant",
                "content": response_message.content or "",
                "tool_calls": response_message.tool_calls
            })
        
        # Izvršava funkcije
        for tool_call in response_message.tool_calls:
            function_name = tool_call.function.name
            raw_args = tool_call.function.arguments

            try:
                # Prvo pokušaj normalno
                function_args = json.loads(raw_args)
            except json.JSONDecodeError:
                logger.warning(f"Groq poslao loš format: {raw_args}. Pokušavam popraviti...")
                match = re.search(r'(\{.*\})', raw_args, re.DOTALL)
                if match:
                    try:
                        function_args = json.loads(match.group(1))
                    except:
                        continue
                else:
                    continue
            
            function_response = await self._execute_function(function_name, function_args)
            
            # Dodaj rezultat u povijest
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": function_name,
                "content": json.dumps(function_response, ensure_ascii=False)
            })
        
        # Pozovi Groq ponovno sa rezultatima
        try:
            final_response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.0, # za pozivanje funkcija treba nam manja maštovitost
                max_tokens=1000
            )
            return final_response.choices[0].message.content
        except Exception as e:
            logger.error(f"Greška u finalnom odgovoru: {e}")
            return "Pronašao sam rezultate, ali ih ne mogu prikazati. Pokušaj ponovno."
    
    async def _execute_function(self, function_name: str, function_args: Dict):
        """Izvršava pozvanu funkciju"""
                   
        from scraper.availability_checker import ScraperAPIChecker
        from scraper.book_detail_parser import BookDetailParser
        from scraper.advanced_url_builder import AdvancedUrlBuilder
        from scraper.universal_scraper import UniversalScraper
        from scraper.events_scraper import EventsScraper

        try:
            # PRETRAGA KATALOGA
            if function_name == "search_catalog":
                query = function_args.get("query")
                
                logger.info(f"RELEJ: Prosljeđujem '{query}' u AdvancedUrlBuilder")

                url_builder = AdvancedUrlBuilder(api_key=os.getenv('GROQ_API_KEY'))
                metadata = url_builder.analyze_query(query)
                target_url = url_builder.build_url(metadata)

                logger.info(f"URL: {target_url}")

                scraper = UniversalScraper()
                items = await scraper.fetch_and_parse(
                    target_url,
                    limit=8,
                    random_selection=True
                )

                return {
                "items": items, 
                "count": len(items),
                "query": query
            }

            # DOSTUPNOST
            elif function_name == "check_availability":
                book_title = function_args.get("book_title") or function_args.get("book_id")

                if book_title == 'None':
                    book_title = None

                logger.info(f"Provjera dostupnosti za: '{book_title}'")
                
                book_id = await self._find_book_id(book_title)

                if not book_id:
                    return {"error": f"Nisam pronašao knjigu '{book_title}'"}

                checker = ScraperAPIChecker()
                availability = await checker.check_availability(book_id)

                return availability
            
            # OPIS KNJIGE
            elif function_name == "get_book_description":
                book_title = function_args.get("book_title")
                
                logger.info(f"📖 Get description: '{book_title}'")
                
                # Pronađi book_id
                book_id = await self._find_book_id(book_title)
                
                if not book_id:
                    return {"error": f"Nisam pronašao knjigu '{book_title}'"}
                
                # Dohvati detalje
                parser = BookDetailParser()
                details = parser.parse_book_detail(book_id)
                
                if 'error' in details:
                    return {"error": "Ne mogu dohvatiti detalje knjige"}
                
                # AI generira opis
                description = await self._generate_smart_description(details)
                
                return {
                    "title": details.get('title'),
                    "author": details.get('author'),
                    "description": description,
                    "year": details.get('year'),
                    "url": details.get('url')
                }
            
            elif function_name == "get_library_events":
                limit = function_args.get("limit", 5)
                
                logger.info(f"📅 Dohvaćam događaje: limit={limit}")
                
                scraper = EventsScraper()
                events = await scraper.get_events(limit=limit)
                
                if not events:
                    return "Trenutno nema dostupnih informacija o događajima u knjižnici."
                
                # Formatiraj kao tekst
                result_text = f"Pronađeno {len(events)} događaja:\n\n"
                
                for i, event in enumerate(events, 1):
                    result_text += f"{i}. {event['title']}\n"
                    
                    if event.get('date_text'):
                        result_text += f"   📆 {event['date_text']}\n"
                    
                    # Kratak opis
                    desc = event.get('excerpt', '')
                    if len(desc) > 150:
                        desc = desc[:150] + "..."
                    
                    if desc:
                        result_text += f"   {desc}\n"
                    
                    # Puni opis (ako postoji)
                    if event.get('full_description'):
                        full_desc = event['full_description']
                        if len(full_desc) > 300:
                            full_desc = full_desc[:300] + "..."
                        result_text += f"   Detalji: {full_desc}\n"
                    
                    if event.get('url'):
                        result_text += f"   🔗 Više: {event['url']}\n"
                    
                    result_text += "\n"
                
                return result_text.strip()
         
            else:
                return {"error": f"Nepoznata funkcija: {function_name}"}
        
        except Exception as e:
            logger.error(f"Greška izvršenja funkcije: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e)} 
        
    async def _find_book_id(self, book_title: str) -> Optional[str]:
        """Pronađi book_id u bazi ili katalogu"""
        
        if not book_title or book_title == 'None':
            logger.warning("Pokušaj pretrage ID-a s praznim naslovom (None).")
            return None

        # 1. Pretraži bazu
        try:
            conn = sqlite3.connect('data/library.db')
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id FROM books 
                WHERE title LIKE ? 
                LIMIT 1
            """, (f'%{book_title}%',))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return row['id']
        
        except Exception as e:
            logger.error(f"DB search error: {e}")
        
        # 2. Pretraži katalog
        try:
            scraper_api_key = os.getenv('SCRAPER_API_KEY')
            if not scraper_api_key:
                return None
            
            import urllib.parse
            import httpx
            from bs4 import BeautifulSoup
            import re
            
            encoded_query = urllib.parse.quote(book_title, safe='')
            search_url = f"https://katalog.halubajska-zora.hr/pagesResults/rezultati.aspx?currentPage=1&searchById=1&sort=0&age=0&spid0=1&spv0={encoded_query}"
            
            params = {
                'api_key': scraper_api_key,
                'url': search_url,
                'country_code': 'hr',
                'render': 'false'
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get("http://api.scraperapi.com/", params=params)
            
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            book_divs = soup.find_all('div', class_='divBibZapis')
            
            if not book_divs:
                return None
            
            first_book = book_divs[0]
            title_link = first_book.find('a', class_='aNaslovLink')
            
            if not title_link:
                return None
            
            href = title_link.get('href', '')
            match = re.search(r'selectedId=(\d+)', href)
            
            if match:
                return match.group(1)
        
        except Exception as e:
            logger.error(f"Catalog search error: {e}")
        
        return None
    
    async def _generate_smart_description(self, book_data: Dict) -> str:
        """Generiraj pametan opis knjige pomoću AI-ja"""
        
        original_desc = book_data.get('description', '')
        has_desc = original_desc and original_desc != "Opis nije dostupan."
        
        if not has_desc:
            # Nema opisa - generiraj iz metapodataka
            context = f"""
            Naslov: {book_data.get('title')}
            Autor: {book_data.get('author')}
            Teme: {', '.join(book_data.get('subjects', [])[:3])}
            Tagovi: {', '.join(book_data.get('tags', []))}
            Opis iz kataloga: {original_desc if has_desc else "NEMA OPISA"}
            """
            
            prompt = f"""Na temelju metapodataka, napiši kratak, zanimljiv i informativan opis knjige (2-3 rečenice) na hrvatskom.
            Kombiniraj originalni opis (ako postoji) s temama i tagovima da objasniš čitatelju koju tematiku knjiga obrađuje.
            NEMOJ spominjati ID brojeve, signature ili interne oznake (npr. 55000313).
            
            PODACI:
            {context}

            ODGOVOR:"""
        else:
            # Ima opis - samo formatiraj
            prompt = f"""Preoblikuj ovaj opis u pregledne odlomke za chat (na hrvatskom), nemoj ništa izbaciti::

            {original_desc}"""
        
        try:
            response = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.1-8b-instant",
                temperature=0.7,
                max_tokens=300
            )
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            logger.error(f"AI description error: {e}")
            return original_desc if has_desc else "Opis nije dostupan."
        
# Quick test
if __name__ == "__main__":
    import asyncio
    
    async def test():
        print("=" * 70)
        print("GROQ CHATBOT TEST")
        print("=" * 70)
        
        chatbot = LibraryChatbot()
        
        test_queries = [
            "Koje knjige ima Jo Nesbo?",
            "Što ima novo?",
            "Preporuči mi psihologiju"
        ]
        
        for query in test_queries:
            print(f"\nUSER: {query}")
            print("-" * 70)
            
            response = await chatbot.chat(query)
            print(f"BOT: {response}\n")
    
    asyncio.run(test())