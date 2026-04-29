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
        
        self.model = "llama-3.3-70b-versatile"
        
        info = self.load_membership_info()
        # System prompt
        self.system_prompt = f"""
        Ti si AI asistent Knjižnice Halubajska Zora u Hrvatskoj.

        ### INFORMACIJE O KNJIŽNICI (Članstvo i pravila):
        {info}

        ### TVOJA ULOGA:
        - Pomažeš korisnicima s informacijama o knjižnici, katalogu i događajima.
        - Koristiš dostupne alate za točne podatke.
        - Odgovaraš na hrvatskom jeziku, ljubazno i koncizno (2-4 rečenice).

        ### PRAVILA:
        - PAMTI KONTEKST: Ako korisnik kaže "da" ili "može", odnosi se na tvoj prethodni prijedlog.
        - DOSLJEDNOST: Koristi informacije koje ti vrate funkcije kao jedini izvor istine.
        - BEZ NAGAĐANJA: Ako funkcija ne vrati podatak (npr. o dostupnosti), nemoj ga izmišljati.
        - LIMIT REZULTATA: Max 10 rezultata po upitu, ako korisnik traži nemoguć broj rezultata, prilagodi ga i objasni zašto
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
                    "description": "Provjeri dostupnost SAMO JEDNE knjige za posudbu i na kojim lokacijama. Koristi SAMO kad korisnik pita o dostupnosti, statusu ili je li knjiga posuđena",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "book_title": {
                                "type": "string",
                                "description": "Naslov knjige za koju korisnik želi provjeriti dostupnost"
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
                                "description": "Naslov knjige za koju korisnik želi opis"
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
                "description": "Pretražuje samo bazu fizičkih knjiga ili građe: pretraga po naslovu, temi, autoru, jeziku, vrsti građe, godini, novitetima, najčitanijima ili preporukama. Ovdje NEMA informacija o radionicama, vijestima ili događajima.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string", 
                            "description": "Originalni upit korisnika (npr. 'nove knjige na engleskom' ili 'psihologija')",
                            "default": 5,
                            "minimum": 1,
                            "maximum": 10
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
                            "limit": {
                                "type": "integer",
                                "description": "Broj događaja",
                                "default": 5,
                                "minimum": 1,
                                "maximum": 10
                            }
                        }
                    }
                }
            },
            # SLIČNE KNJIGE
            {
                "type": "function",
                "function": {
                    "name": "get_similar_books",
                    "description": "Koristi SAMO kad korisnik traži slične knjige, ili 'nešto kao X'.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "book_title": {
                                "type": "string",
                                "description": "Naslov knjige za koju tražimo slične"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Broj preporuka. VAŽNO: Pošalji isključivo kao cijeli broj (npr. 3, a ne '3').",
                                "default": 3,
                                "minimum": 1,
                                "maximum": 10
                            }
                        },
                        "required": ["book_title"]
                    }
                }
            },
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
            ]

            logger.info(f"📨 Šaljem Groq-u {len(messages)} poruka:")
            for i, msg in enumerate(messages):
                role = msg.get("role", "?")
                content = str(msg.get("content", ""))[:100]
                has_tools = "tool_calls" in msg
                
                logger.info(f"  [{i}] {role}: {content}... (has_tool_calls: {has_tools})")    

            if conversation_history:
                filtered_history = [
                    msg for msg in conversation_history
                    if msg.get("role") in ["user", "assistant"]
                    and "tool_calls" not in msg
                    and msg.get("content")
                ]
                messages.extend(filtered_history[-8:])
                logger.info(f"Dodao {len(filtered_history[-8:])} poruka iz povijesti")

            messages.append({
                "role": "system",
                "content": "Use ONLY JSON format for tool calls. Example: {\"name\": \"search_catalog\", \"arguments\": {\"query\": \"text\"}}"
            })
            messages.append({"role": "user", "content": user_message})    
            # Pozovi Groq sa tool use
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tools, 
                tool_choice="auto",  # AI odlučuje kad koristiti funkcije
                temperature=0.1,
                max_tokens=1000
            )
            
            response_message = response.choices[0].message
            
            # Provjeri ima li function calls
            if response_message.tool_calls:
                if len(response_message.tool_calls) > 1:
                    logger.warning(f"Bot je htio izvršiti {len(response_message.tool_calls)} funkcija. Režem na 1.")
                    response_message.tool_calls = response_message.tool_calls[:1]
                # -----------------------
                
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

            if str(raw_args).strip().startswith('<') and str(raw_args).strip().endswith('>'):
                logger.warning(f"Detektiran XML format, čistim: {raw_args}")
                function_args = self.extract_clean_json(raw_args) # Poziva tvoju funkciju
            else:
                try:
                    # Prvo pokušaj normalno
                    function_args = json.loads(raw_args)
                except json.JSONDecodeError:
                    logger.warning(f"JSONDecodeError na: {raw_args}. Pokušavam extract...")
                    function_args = self.extract_clean_json(raw_args)
            
            if function_args is None:
                logger.error(f"Kritična greška: Neuspješno dekodiranje argumenata za {function_name}")
                continue
            
            function_response = await self._execute_function(function_name, function_args)
            response_str = str(function_response)
            logger.info(f"Funkcija vratila: {response_str[:200]}...")

            uputa = function_response.pop("uputa", None) if isinstance(function_response, dict) else None

            # Dodaj rezultat u povijest
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": function_name,
                "content": json.dumps(function_response, ensure_ascii=False)
            })

            if uputa:
                current_content = json.loads(messages[-1]["content"])
                if isinstance(current_content, dict):
                    current_content["_internal_note"] = uputa
                    messages[-1]["content"] = json.dumps(current_content, ensure_ascii=False)
        
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
                   
        try:
            # PRETRAGA KATALOGA
            if function_name == "search_catalog":
                query = function_args.get("query") or function_args.get("book_title")
                
                logger.info(f"Prosljeđujem '{query}' u AdvancedUrlBuilder")

                from scraper.advanced_url_builder import AdvancedUrlBuilder
                url_builder = AdvancedUrlBuilder(api_key=os.getenv('GROQ_API_KEY'))
                metadata = url_builder.analyze_query(query)
                target_url = url_builder.build_url(metadata)

                logger.info(f"URL: {target_url}")

                is_new_or_top = metadata.get('sort') == 3 or metadata.get('top') is not None
                should_randomize = not is_new_or_top

                from scraper.universal_scraper import UniversalScraper
                scraper = UniversalScraper()

                requested_limit = function_args.get("limit", 8)
                safe_limit = self._validate_limit(requested_limit, default=5, max_limit=10)

                items = await scraper.fetch_and_parse(
                    target_url,
                    limit=safe_limit,
                    random_selection=should_randomize
                )

                note = ""
                if isinstance(requested_limit, int) and requested_limit > 10:
                    note = f"\n\n💡 Napomena: Tražili ste {requested_limit} knjiga, ali prikazujem najboljih {safe_limit}."

                return {
                "items": items, 
                "count": len(items),
                "query": query,
                "note": note,
                "uputa": (
                    "Ovo su rezultati pretrage iz kataloga. "
                    "Prikaži ih kao preglednu listu (Naslov - Autor). "
                    "VAŽNO: Ovi podaci NE SADRŽE informaciju o dostupnosti. "
                    "Zato NIKADA nemoj nagađati jesu li knjige dostupne ili posuđene. "
                    "Navedi što je pronađeno, a možeš i ponuditi korisniku da provjeriš dostupnost za konkretne rezultate ili ponuditi dati opis."
                )
            }

            # DOSTUPNOST
            elif function_name == "check_availability":
                book_title = function_args.get("book_title") or function_args.get("query") or function_args.get("search_query")

                if not book_title or book_title == 'None':
                    return {"error": "Niste naveli naslov knjige za provjeru."}

                logger.info(f"Pokrećem FastAvailabilityChecker za: '{book_title}'")
                
                from scraper.fast_availability_checker import FastAvailabilityChecker
                checker = FastAvailabilityChecker()

                availability_data = await checker.check_availability(book_title)

                return {
                    "podaci": availability_data,
                    "uputa": (
                        "Ovo su podaci o dostupnosti u stvarnom vremenu. "
                        "Koristi ✅ za dostupno i ❌ za posuđeno. Obavezno navedi lokacije dostupnosti (Marinići ili Viškovo)."
                        "Ako postoje slični naslovi koji su dostupni, predloži ih kao alternativu"
                    )
                }
            
            # OPIS KNJIGE
            elif function_name == "get_book_description":
                book_title = function_args.get("book_title")
                
                logger.info(f"📖 Get description: '{book_title}'")
                
                # Pronađi book_id
                book_id = await self._find_book_id(book_title)
                
                if not book_id:
                    return {"error": f"Nisam pronašao knjigu '{book_title}'"}
                
                # Dohvati detalje
                from scraper.book_detail_parser import BookDetailParser
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
            
            # DOGAĐAJI
            elif function_name == "get_library_events":
                if function_args is None:
                    function_args = {}

                requested_limit = function_args.get("limit", 5)
                limit = self._validate_limit(requested_limit, default=5, max_limit=10)
                
                logger.info(f"📅 Dohvaćam događaje: limit={limit}")
                
                from scraper.events_scraper import EventsScraper
                scraper = EventsScraper()
                events = await scraper.get_events(limit=limit)
                
                if not events:
                    return {
                        "data": "Trenutno nema dostupnih informacija o događajima u knjižnici.",
                        "uputa": "Obavijesti korisnika da trenutno nema planiranih događanja, ali neka prati web stranicu za novosti."
                    }
                
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
                    
                    if event.get('url'):
                        result_text += f"   🔗 Više: {event['url']}\n"
                    
                    result_text += "\n"
                
                return {
                    "data": result_text.strip(),
                    "uputa": (
                        "Predstavi ove događaje korisniku na ljubazan način. "
                        "Ako ih ima više, spomeni samo najvažnije detalje. "
                        "Ako korisnik traži specifičan događaj ili detalje, opiši ga."
                        "Obavezno zadrži linkove i datume onako kako su navedeni."
                    )
                }
            
            # SLIČNE KNJIGE
            elif function_name == "get_similar_books":
                import re
                from scraper.book_detail_parser import BookDetailParser
                
                book_title = function_args.get("book_title")

                requested_limit = function_args.get("limit", 5)
                limit = self._validate_limit(requested_limit, default=5, max_limit=10)
                
                logger.info(f"Tražim preporuke za: '{book_title}'")
                
                # 2. Pronađi ID knjige
                raw_id = await self._find_book_id(book_title)
                
                if not raw_id:
                    return {"error": f"Nisam pronašao knjigu '{book_title}'"}
                
                # 3. FIX: Čišćenje ID-a i korištenje clean_id varijable
                match = re.search(r'(\d+)', str(raw_id))
                if match:
                    clean_id = match.group(1)
                else:
                    return {"error": "Neispravan format ID-a knjige."}
                
                # 4. Dohvati detalje (proslijedi OČIŠĆENI clean_id)
                parser = BookDetailParser()
                details = parser.parse_book_detail(clean_id)
                
                recommendations = details.get('recommendations', {})
                all_recs = []

                # 5. LOGIKA: Spajamo 'Prema posudbi' i 'Od istoga autora'
                for section in recommendations:
                    if isinstance(recommendations[section], list):
                        all_recs.extend(recommendations[section])

                # 6. FALLBACK: Ako su preporuke prazne, koristi TAGOVE
                source = "katalog_recommendations"
                used_tag = None

                if not all_recs:
                    logger.info(f"Preporuke prazne za '{book_title}', provjeravam tagove...")
                    tags = details.get('tags', [])
                    
                    if tags:
                        used_tag = tags[0] 
                        logger.info(f"Pokrećem pretragu za tag: {used_tag}")
                        
                        tag_results = await self._search_by_tag(used_tag)
                        
                        # Filtriraj da ne preporučiš istu knjigu (usporedba ID-eva)
                        all_recs = [b for b in tag_results if str(b.get('id')) != clean_id]
                        source = "tag_search"
                    else:
                        return {"message": f"Za knjigu '{book_title}' trenutno nema preporuka ni tagova."}

                # 7. Formatiraj odgovor za AI
                return {
                    "original_book": details.get('title', book_title),
                    "recommendations": all_recs[:limit],
                    "source": source,
                    "used_tag": used_tag
                }

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
        
        # Pretraži katalog
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
        
    def _validate_limit(self, limit_arg, default: int = 5, max_limit: int = 10) -> int:
        """
        Validira limit parametar i vraća siguran broj
        
        Args:
            limit_arg: Vrijednost iz function_args
            default: Default vrijednost ako je invalid
            max_limit: Maksimalan dozvoljen limit
        
        Returns:
            Validirani limit (min 1, max max_limit)
        """
        try:
            limit = int(limit_arg)
            
            # Min 1, max max_limit
            if limit < 1:
                logger.warning(f"Limit {limit} < 1, koristim 1")
                return 1
            
            if limit > max_limit:
                logger.warning(f"Limit {limit} > {max_limit}, koristim {max_limit}")
                return max_limit
            
            return limit
        
        except (ValueError, TypeError):
            logger.warning(f"Invalid limit '{limit_arg}', koristim default {default}")
            return default
        
    def extract_clean_json(text):
        import re
        # Traži bilo što što se nalazi unutar vitičastih zagrada { ... }
        match = re.search(r'\{.*\}', text)
        if match:
            json_str = match.group(0)
            return json.loads(json_str)  # Vraća rječnik: {"query": "filmovi o politici"}
        return None
        
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