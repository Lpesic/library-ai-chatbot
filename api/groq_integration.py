"""
Groq Integration - NAJBRŽA AI integracija
"""

import os, json, sys, re
import logging
from typing import Dict, List, Optional
from groq import AsyncGroq

logging.basicConfig(level=logging.INFO)
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
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            logger.error("GROQ_API_KEY nije postavljen u .env!")
            self.client = None
            return

        self.client = AsyncGroq(api_key=api_key)
        
        self.tool_model = "llama-3.3-70b-versatile"
        self.fast_model = "llama-3.1-8b-instant"
        
        self.info = self.load_membership_info()
        self.system_prompt = self._build_system_prompt()
        self.tools = self._define_tools()
    
    def _build_system_prompt(self):
        return f"""
        Ti si AI asistent Knjižnice Halubajska Zora u Hrvatskoj.

        ### INFORMACIJE O KNJIŽNICI (Članstvo i pravila):
        {self.info}

        ### TVOJA ULOGA:
        - Pomažeš korisnicima s informacijama o knjižnici, katalogu i događajima.
        - Koristiš dostupne alate za točne podatke.
        - Odgovaraš na hrvatskom jeziku, ljubazno i koncizno (2-4 rečenice).

        ### PRAVILA:
        - PAMTI KONTEKST: Ako korisnik kaže "da" ili "može", odnosi se na tvoj prethodni prijedlog.
        - DOSLJEDNOST: Koristi informacije koje ti vrate funkcije kao jedini izvor istine.
        - BEZ NAGAĐANJA: Ako funkcija ne vrati podatak (npr. o dostupnosti), nemoj ga izmišljati.
        - LIMIT REZULTATA: Max 10 rezultata po upitu, ako korisnik traži nemoguć broj rezultata, prilagodi ga i objasni zašto
        - TOOL CALLING RULES: When you need to use a tool, use the internal function calling mechanism ONLY.
        - Ako korisnik pita o pravilima posudbe, članarini, radnom vremenu, kontaktu ili općim informacijama o knjižnici — odgovori DIREKTNO iz informacija o knjižnici, ne koristi alate.
        - NEVER output text like '<function=...>' or 'function_name "arg": "val"'.
        - When calling a tool, provide ONLY the JSON arguments.

        Primjer ISPRAVNOG tool calla:
        
            "name": "get_book_description",
            "arguments": 
                "book_title": "Vučji sat",
                "mode": "summary"
        
        """
        
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
                            "description": "Originalni upit korisnika (npr. 'nove knjige na engleskom' ili 'psihologija')"
                            },
                        "limit": {
                            "type": ["integer", "string"],
                            "description": "Koliko rezultata korisnik želi",
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
                    "description": "Dohvati informacije kada korisnik pita o događajima, radionicama, pričaonicama, novostima ili aktivnostima u knjižnici.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": ["integer", "string"],
                                "description": "Broj događaja (npr. '3').",
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
                                "type": ["integer", "string"],
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
            
            messages = [{"role": "system", "content": self.system_prompt}]

            logger.info(f"📨 Šaljem Groq-u {len(messages)} poruka:")
            for i, msg in enumerate(messages):
                role = msg.get("role", "?")
                content = str(msg.get("content", ""))[:100]
                has_tools = "tool_calls" in msg
                
                logger.info(f"  [{i}] {role}: {content}... (has_tool_calls: {has_tools})")    

            if conversation_history:
                for msg in conversation_history[-4:]:
                    if msg.get("role") in ["user", "assistant"] and not msg.get("tool_calls"):
                        content = msg.get("content")
                        if content:   
                            clean_content = self._clean_json_artifacts(str(content))
                            messages.append({"role": msg["role"], "content": clean_content})

            messages.append({"role": "user", "content": user_message})

            # Pozovi Groq sa tool use
            response = await self.client.chat.completions.create(
                model=self.tool_model,
                messages=messages,
                tools=self.tools, 
                tool_choice="auto",  # AI odlučuje kad koristiti funkcije
                temperature=0.0
            )
            
            response_message = response.choices[0].message
            
            # Provjeri ima li function calls
            if response_message.tool_calls:
                tool_calls = response_message.tool_calls[:1]
                return await self._handle_function_calls(tool_calls, messages)
            
            # Obični odgovor
            return response_message.content
        
        except Exception as e:
            if "tool_use_failed" in str(e):
                logger.warning("Tool failed → retry sa prisilnim pravilnim tipovima")

            if "<function=" in str(e):
                messages.append({
                    "role": "system",
                    "content": "NE koristi <function=...>. Koristi isključivo JSON tool_calls format."
                })

                retry = await self.client.chat.completions.create(
                    model=self.tool_model,
                    messages=messages,
                    tools=self.tools,
                    tool_choice="auto",
                    temperature=0.0
                )

                msg = retry.choices[0].message

                if msg.tool_calls:
                    return await self._handle_function_calls(msg.tool_calls[:1], messages)

                return msg.content
        
            raise e
    
    async def _handle_function_calls(self, tool_calls, messages: List[Dict]) -> str:
        """Obradi function calls"""

        # Dodaj AI-ov odgovor u povijest
        messages.append({
            "role": "assistant",
            "tool_calls": [
                {
                    "id": t.id,
                    "type": "function",
                    "function": {
                        "name": t.function.name,
                        "arguments": t.function.arguments
                    }
                } for t in tool_calls
            ]
        })
        
        # Izvršava funkcije
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            raw_args = tool_call.function.arguments

            try:
                function_args = json.loads(raw_args)
            except json.JSONDecodeError:
                logger.warning(f"Popravljam JSON argumenata za {function_name}")
                function_args = self.extract_clean_json(raw_args) or {}       
            
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
                model=self.fast_model,
                messages=messages,
                temperature=0.5
            )

            final_text = final_response.choices[0].message.content
            final_text = self._clean_json_artifacts(final_text)

            return final_text 
        
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

                raw_limit = function_args.get("limit", 5)

                try:
                    requested_limit = int(raw_limit)
                except (ValueError, TypeError):
                    requested_limit = 5

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
            import urllib.parse
            import httpx
            from bs4 import BeautifulSoup
            import re
            
            encoded_query = urllib.parse.quote(book_title, safe='')
            search_url = f"https://katalog.halubajska-zora.hr/pagesResults/rezultati.aspx?currentPage=1&searchById=1&sort=0&age=0&spid0=1&spv0={encoded_query}"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "hr-HR,hr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Referer": "https://katalog.halubajska-zora.hr/",
                "Connection": "keep-alive"
            }
            
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(search_url, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"Katalog vratio status {response.status_code}")
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
                model=self.fast_model,
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
        
    def extract_clean_json(self, text):    
        # Traži bilo što što se nalazi unutar vitičastih zagrada { ... }
        try:
            match = re.search(r'(\{.*\})', text, re.DOTALL)
            if match:
                return json.loads(match.group(1))  # Vraća rječnik: {"query": "filmovi o politici"}
        except:
            return None
        return None
    
    def _clean_json_artifacts(self, text: str) -> str:
        """
        Ukloni JSON artefakte iz Groq odgovora
        
        Primjeri:
        - {"book_title":"X","mode":"summary"}
        - {"query":"nešto"}
        - <function=...>
        """
        import re
        
        if not text:
            return text
        
        # 1. Ukloni JSON objekte ({"key":"value",...})
        # Pattern: { bilo_što } ali NE unutar normalnog teksta
        cleaned = re.sub(r'\s*\{["\']?\w+["\']?\s*:\s*["\']?[^}]+["\']?\}\s*', '', text)
        
        # 2. Ukloni XML-like tagove (<function=...>)
        cleaned = re.sub(r'<function[^>]*>.*?</function>', '', cleaned, flags=re.DOTALL)
        cleaned = re.sub(r'<[^>]+>', '', cleaned)
        
        # 3. Ukloni trostruke ili više razmaka
        cleaned = re.sub(r'\s{3,}', ' ', cleaned)
        
        # 4. Trim
        cleaned = cleaned.strip()
        
        if cleaned != text:
            logger.info(f"Očišćen JSON artefakt: {len(text)} → {len(cleaned)} chars")
        
        return cleaned
        
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