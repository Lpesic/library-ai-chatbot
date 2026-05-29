import httpx
from bs4 import BeautifulSoup
import logging
import re
import random
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class UniversalScraper:
    def __init__(self):
        self.base_url = "https://katalog.halubajska-zora.hr"

    async def fetch_and_parse(self, url: str, limit: int = 10, random_selection: bool = False) -> List[Dict]:
        """
        Glavna metoda: Uzima URL (od Buildera), skrejpa ga i vraća listu knjiga.
        """
        try:
            # Dohvat granica
            headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'hr-HR,hr;q=0.9,en;q=0.8',
            }
            async with httpx.AsyncClient(
                timeout=45.0, 
                headers=headers, 
                follow_redirects=True,
                verify=False
                ) as client:
                first_page_url = f"{url}&currentPage=1"

                logger.info(f"Direktan request: {first_page_url[:120]}...")

                response = await client.get(first_page_url)
                response.raise_for_status()
            
            if response.status_code != 200:
                logger.error(f"Greška pri dohvaćanju: {response.status_code}")
                return []

            # 2. Parsiranje HTML-a
            soup = BeautifulSoup(response.text, 'html.parser')

            last_page = 1
            pager_links = soup.select("#divPagerBottom .aNumber")
            if pager_links:
                try:
                    # Uzimamo tekst zadnjeg broja (u tvom primjeru 1607)
                    last_page = int(pager_links[-1].get_text(strip=True))
                except:
                    last_page = 1
            
            # Određivanje ciljne stranice
            target_url = first_page_url # Default

            if random_selection and last_page > 1:
                # Izbjegavamo zadnju stranicu ako ih ima više (da ne bude poluprazna)
                high_bound = last_page - 1 if last_page > 2 else last_page
                random_page = random.randint(1, high_bound)
                
                # Sklapamo novi URL s nasumičnom stranicom
                target_url = f"{url}&currentPage={random_page}"
                logger.info(f"Deep Random: Odabrana stranica {random_page} od ukupno {last_page}")
                
                # Ponovni poziv na tu nasumičnu stranicu
                res = await client.get(target_url)
                soup = BeautifulSoup(res.text, 'html.parser')
            
            # Parsiranje rezultata
            item_divs = soup.find_all('div', class_='divBibZapis')
            logger.info(f"Pronađeno {len(item_divs)} rezultata na stranici")

            all_items = []
            for item_div in item_divs:
                try:
                    # Naslov i ID
                    title_link = item_div.find('a', class_='aNaslovLink')
                    title = title_link.get_text(strip=True) if title_link else "Nepoznato"
                    
                    # Autor
                    author_link = item_div.find('a', class_='aAutor')
                    author = author_link.get_text(strip=True) if author_link else "Nepoznat autor"
                    
                    # Opis (godina i nakladnik)
                    year = None
                    desc_div = item_div.find('div', class_='rezultati-status')
                    if desc_div:
                        text = desc_div.get_text()
                        year_match = re.search(r',\s*(\d{4})', text)
                        year = year_match.group(1) if year_match else None
                        
                        # Datum nabave (ako postoji - za nove knjige)
                        date_match = re.search(r'Nabavljeno\s+([\d\.]+\s+[\d\.]+\s+\d+\.?)', text)
                        date_added = date_match.group(1).strip() if date_match else None
                    else:
                        date_added = None
                    
                    # Vrsta građe (ikona)
                    type_img = item_div.find('img', class_='vrstaGradjeIkona')
                    item_type = type_img['alt'] if type_img and type_img.get('alt') else "Knjiga"

                    if len(all_items) == 0:
                        logger.info(f"Prvi rezultat: {title} ({item_type}) - {author}")

                    all_items.append({
                        'title': title,
                        'author': author,
                        'year': year,
                        'date_added': date_added,
                        'type': item_type
                    })
                except Exception as e:
                    logger.error(f"Parse item error: {e}")
                    continue

            logger.info(f"Parsirano {len(all_items)} stavki")

            # Selekcija rezultata
            if random_selection:
                random.shuffle(all_items)
                return all_items[:limit]
            
            return all_items[:limit]

        except Exception as e:
            logger.error(f"UniversalScraper Greška: {e}")
            import traceback
            traceback.print_exc()
            return []      
    
    def format_message(self, items: List[Dict], title_prefix: str) -> str:
        """
        Unificirano formatiranje poruke za korisnika.
        """
        if not items:
            return f"❌ Nažalost, nisam pronašao ništa za: **{title_prefix}**."

        msg = f" **{title_prefix}**\n"
        msg += "─" * 20 + "\n\n"
        
        for i, item in enumerate(items, 1):
            msg += f"{i}. **{item['title']}**\n"
            msg += f"    {item['author']}"
            if item['year']: msg += f" ({item['year']})"
            
            # Dodaj vrstu građe ako nije obična knjiga
            if item['type'] != 'Knjiga':
                msg += f"\n    {item['type']}"
                
            # Dodaj datum nabave ako ga ima (važno za nove knjige)
            if item['date_added']:
                msg += f"\n   Nabavljeno: {item['date_added']}"
                
            status_emoji = "✅" if item['status'] == "Dostupno" else "❌"
            msg += f"\n   {status_emoji} {item['status']}\n\n"
        
        return msg