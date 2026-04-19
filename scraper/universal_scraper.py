import httpx
from bs4 import BeautifulSoup
import logging
import os
import re
import random
import urllib.parse
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class UniversalScraper:
    def __init__(self):
        self.base_url = "https://katalog.halubajska-zora.hr"
        self.scraper_api_key = os.getenv('SCRAPER_API_KEY')

    async def fetch_and_parse(self, url: str, limit: int = 8, random_selection: bool = False) -> List[Dict]:
        """
        Glavna metoda: Uzima URL (od Buildera), skrejpa ga i vraća listu knjiga.
        """
        try:
            # 1. Odluči hoće li koristiti ScraperAPI ili direktan request
            final_url = url
            params = {}
            
            if self.scraper_api_key:
                logger.info(f"Korištenje ScraperAPI za URL: {url}")
                final_url = "http://api.scraperapi.com/"
                params = {
                    'api_key': self.scraper_api_key,
                    'url': url,
                    'country_code': 'hr'
                }

            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.get(final_url, params=params)
            
            if response.status_code != 200:
                logger.error(f"Greška pri dohvaćanju: {response.status_code}")
                return []

            # 2. Parsiranje HTML-a
            soup = BeautifulSoup(response.text, 'html.parser')
            item_divs = soup.find_all('div', class_='divBibZapis')
            
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

                    # Status (Dostupno/Posuđeno)
                    status = "Dostupno" if item_div.find('span', class_='boldGreen') else "Posuđeno"
                    
                    # Vrsta građe (ikona)
                    type_img = item_div.find('img', class_='vrstaGradjeIkona')
                    item_type = type_img['alt'] if type_img and type_img.get('alt') else "Knjiga"

                    all_items.append({
                        'title': title,
                        'author': author,
                        'year': year,
                        'date_added': date_added,
                        'status': status,
                        'type': item_type
                    })
                except Exception as e:
                    continue

            # 3. Selekcija rezultata
            if random_selection and len(all_items) > limit:
                return random.sample(all_items, limit)
            return all_items[:limit]

        except Exception as e:
            logger.error(f"UniversalScraper Greška: {e}")
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
                msg += f"\n   📅 Nabavljeno: {item['date_added']}"
                
            status_emoji = "✅" if item['status'] == "Dostupno" else "❌"
            msg += f"\n   {status_emoji} {item['status']}\n\n"
        
        return msg