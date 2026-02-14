"""
Category Scraper - pretraživanje po kategorijama (vrsta građe)
"""

import httpx
from bs4 import BeautifulSoup
import logging
from typing import List, Dict
import os
from dotenv import load_dotenv
import re
import random

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CategoryScraper:
    """Scraper za pretraživanje po kategorijama"""
    
    def __init__(self):
        self.base_url = "https://katalog.halubajska-zora.hr"
        self.scraper_api_key = os.getenv('SCRAPER_API_KEY')
        
        # Mapa kategorija - friendly name → URL parametar
        self.categories = {
            # KNJIGA
            'knjiga': 'knjiga',
            'knjige': 'knjiga',
            'knjiga za': 'knjiga',
            
            # NAKLADNIČKI NIZ
            'nakladnički niz': 'nakladnički+niz',
            'nakladnicki niz': 'nakladnički+niz',
            'serija': 'nakladnički+niz',
            'niz': 'nakladnički+niz',
            
            # VIZUALNA GRAĐA
            'vizualna građa': 'vizualna+građa',
            'vizualna grada': 'vizualna+građa',
            'slike': 'vizualna+građa',
            'fotografije': 'vizualna+građa',
            'foto': 'vizualna+građa',
            
            # ČLANAK
            'članak': 'članak',
            'clanak': 'članak',
            'članci': 'članak',
            'clanci': 'članak',
            'artikl': 'članak',
            
            # E-KNJIGA
            'e-knjiga': 'e-knjiga',
            'eknjiga': 'e-knjiga',
            'e knjiga': 'e-knjiga',
            'digitalna knjiga': 'e-knjiga',
            'digitalne knjige': 'e-knjiga',
            'ebook': 'e-knjiga',
            'e-book': 'e-knjiga',
            
            # GLAZBENA GRAĐA
            'glazbena građa': 'zvučna+građa,+glazbena',
            'glazbena grada': 'zvučna+građa,+glazbena',
            'glazba': 'zvučna+građa,+glazbena',
            'muzika': 'zvučna+građa,+glazbena',
            'cd': 'zvučna+građa,+glazbena',
            'audio cd': 'zvučna+građa,+glazbena',
            
            # ELEKTRONIČKA GRAĐA
            'elektronička građa': 'elektronička+građa',
            'elektronicka grada': 'elektronička+građa',
            'digitalna građa': 'elektronička+građa',
            'digitalni sadržaj': 'elektronička+građa',
            
            # ZVUČNA GRAĐA (neglazbena)
            'zvučna građa': 'zvučna+građa,+neglazbena',
            'zvucna grada': 'zvučna+građa,+neglazbena',
            'audiobook': 'zvučna+građa,+neglazbena',
            'audio knjiga': 'zvučna+građa,+neglazbena',
            'audioknjiga': 'zvučna+građa,+neglazbena',
            
            # IGRAČKA
            'igračka': 'igračka',
            'igracka': 'igračka',
            'igračke': 'igračka',
            'igracke': 'igračka',
            'igra': 'igračka',
            'igre': 'igračka',
            
            # NOTNA GRAĐA
            'notna građa': 'notna+građa',
            'notna grada': 'notna+građa',
            'note': 'notna+građa',
            'partitura': 'notna+građa',
            'partiture': 'notna+građa',
            
            # KARTOGRAFSKA GRAĐA
            'kartografska građa': 'kartografska+građa',
            'kartografska grada': 'kartografska+građa',
            'karta': 'kartografska+građa',
            'karte': 'kartografska+građa',
            'zemljovid': 'kartografska+građa',
            'zemljovidi': 'kartografska+građa',
            'atlas': 'kartografska+građa',
            
            # ZVUČNA E-KNJIGA
            'zvučna e-knjiga': 'zvučna+e-knjiga',
            'zvucna e-knjiga': 'zvučna+e-knjiga',
            'audio e-knjiga': 'zvučna+e-knjiga',
            
            # ČASOPIS | PERIODIKA
            'časopis': 'časopis',
            'casopis': 'časopis',
            'časopisi': 'časopis',
            'casopisi': 'časopis',
            'periodika': 'časopis',
            'magazin': 'časopis',
            'revija': 'časopis',
            
            # TEMATSKI BROJ
            'tematski broj': 'tematski+broj',
            'tematski': 'tematski+broj',
            'specijalno izdanje': 'tematski+broj',
            
            # GRAFIČKA GRAĐA
            'grafička građa': 'grafička+građa',
            'graficka grada': 'grafička+građa',
            'grafike': 'grafička+građa',
            'grafika': 'grafička+građa',
            
            # OSTALO
            'ostalo': 'ostalo',
            'nekategorizirano': 'ostalo',
        }
    
    def get_category_param(self, query: str) -> str:
        """Pronađi URL parametar za kategoriju"""
        query_lower = query.lower().strip()
        
        # Direktno mapiranje
        if query_lower in self.categories:
            return self.categories[query_lower]
        
        # Parcijalno podudaranje
        for key, value in self.categories.items():
            if key in query_lower or query_lower in key:
                return value
        
        return None
    
    async def get_items_by_category(
        self, 
        category: str, 
        limit: int = 10,
        random_selection: bool = True
    ) -> List[Dict]:
        """
        Dohvati stavke iz kategorije
        
        Args:
            category: Naziv kategorije (npr. 'igračke', 'filmovi')
            limit: Broj rezultata
            random_selection: Ako True, vraća random izbor; ako False, prvih N
            
        Returns:
            Lista stavki
        """
        
        try:
            # Pronađi URL parametar
            category_param = self.get_category_param(category)
            
            if not category_param:
                logger.warning(f"Nepoznata kategorija: {category}")
                return []
            
            logger.info(f"Kategorija '{category}' → URL param: {category_param}")
            
            # URL za pretraživanje
            search_url = f"{self.base_url}/pagesResults/rezultati.aspx?action=search&fid0=2&fv0={category_param}"
            
            # Koristi ScraperAPI
            if self.scraper_api_key:
                logger.info(f"Dohvaćam kategoriju '{category}' preko ScraperAPI...")
                
                params = {
                    'api_key': self.scraper_api_key,
                    'url': search_url,
                    'country_code': 'hr'
                }
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(
                        "http://api.scraperapi.com/",
                        params=params
                    )
            else:
                # Fallback
                logger.info(f"Dohvaćam kategoriju direktno...")
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(search_url)
            
            if response.status_code != 200:
                logger.error(f"HTTP error: {response.status_code}")
                return []
            
            logger.info(f"Response: {len(response.text)} bytes")
            
            # Parsiraj
            soup = BeautifulSoup(response.text, 'html.parser')
            items = self._parse_items(soup, limit * 3)  # Dohvati 3x više za random selection
            
            logger.info(f"Parsirano {len(items)} stavki")
            
            # Random selection ako je traženo
            if random_selection and len(items) > limit:
                items = random.sample(items, limit)
                logger.info(f"Random odabrano {limit} stavki")
            else:
                items = items[:limit]
            
            return items
        
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju kategorije: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def get_most_read(
        self, 
        days: int = 30, 
        limit: int = 10
    ) -> List[Dict]:
        """
        Dohvati najčitanije knjige u zadnjih X dana
        
        Args:
            days: Vremensko razdoblje (7, 30, 90, 180, 365)
            limit: Broj rezultata
            
        Returns:
            Lista najčitanijih knjiga
        """
        
        try:
            # Validiraj period
            valid_periods = [7, 30, 90, 180, 365]
            if days not in valid_periods:
                # Pronađi najbliži validan period
                days = min(valid_periods, key=lambda x: abs(x - days))
                logger.info(f"Period prilagođen na {days} dana")
            
            logger.info(f"Dohvaćam najčitanije knjige (zadnjih {days} dana)...")
            
            # URL za najčitanije
            most_read_url = f"{self.base_url}/pagesResults/rezultati.aspx?top={days}"
            
            # Koristi ScraperAPI
            if self.scraper_api_key:
                params = {
                    'api_key': self.scraper_api_key,
                    'url': most_read_url,
                    'country_code': 'hr'
                }
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(
                        "http://api.scraperapi.com/",
                        params=params
                    )
            else:
                # Fallback
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(most_read_url)
            
            if response.status_code != 200:
                logger.error(f"HTTP error: {response.status_code}")
                return []
            
            logger.info(f"Response: {len(response.text)} bytes")
            
            # Parsiraj
            soup = BeautifulSoup(response.text, 'html.parser')
            books = self._parse_items(soup, limit)
            
            logger.info(f"Parsirano {len(books)} najčitanijih knjiga")
            
            return books
        
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju najčitanijih: {e}")
            import traceback
            traceback.print_exc()
            return []

    def format_most_read_message(
        self, 
        books: List[Dict], 
        days: int
    ) -> str:
        """Formatira poruku sa najčitanijim knjigama"""
        
        if not books:
            return (f"Nažalost, trenutno ne mogu dohvatiti najčitanije knjige.\n\n"
                f"Provjerite katalog: https://katalog.halubajska-zora.hr/pagesResults/rezultati.aspx?top={days}")
        
        # Period naziv
        period_names = {
            7: "tjedan dana",
            30: "mjesec dana", 
            90: "3 mjeseca",
            180: "6 mjeseci",
            365: "godinu dana"
        }
        
        period_name = period_names.get(days, f"{days} dana")
        
        msg = f"🔥 **Najčitanije knjige (zadnjih {period_name}):**\n\n"
        
        for i, book in enumerate(books, 1):
            msg += f"{i}. **{book['title']}**"
            
            if book.get('author'):
                msg += f"\n   ✍️ {book['author']}"
            
            if book.get('year'):
                msg += f" ({book['year']})"
            
            if book.get('status'):
                if book['status'] == 'Dostupno':
                    msg += f"\n   ✅ {book['status']}"
                elif book['status'] == 'Posuđeno':
                    msg += f"\n   ❌ {book['status']}"
            
            msg += "\n\n"
        
        msg += f"🔗 Sve najčitanije: https://katalog.halubajska-zora.hr/pagesResults/rezultati.aspx?top={days}"
        
        return msg 

    def _parse_items(self, soup: BeautifulSoup, limit: int) -> List[Dict]:
        """Parsira stavke iz HTML-a"""
        items = []
        
        # Pronađi sve div-ove sa rezultatima
        item_divs = soup.find_all('div', class_='divBibZapis')
        
        logger.info(f"Pronađeno {len(item_divs)} div-ova")
        
        for item_div in item_divs[:limit]:
            try:
                # Naslov
                title_link = item_div.find('a', class_='aNaslovLink')
                title = title_link.get_text(strip=True) if title_link else "Nepoznato"
                
                # Book/Item ID
                item_id = None
                if title_link and title_link.get('href'):
                    match = re.search(r'selectedId=(\d+)', title_link['href'])
                    if match:
                        item_id = match.group(1)
                
                # Autor (ako postoji)
                author = None
                author_link = item_div.find('a', class_='aAutor')
                if author_link:
                    author = author_link.get_text(strip=True)
                
                # Nakladnik i godina
                publisher = None
                year = None
                
                desc_div = item_div.find('div', class_='rezultati-status')
                if desc_div:
                    text = desc_div.get_text()
                    
                    # Pronađi nakladnika i godinu
                    pub_match = re.search(r':\s*([^,]+),\s*(\d{4})', text)
                    if pub_match:
                        publisher = pub_match.group(1).strip()
                        year = pub_match.group(2)
                
                # Status
                status = "Nepoznato"
                status_span = item_div.find('span', class_='boldGreen')
                if status_span:
                    status = "Dostupno"
                else:
                    status_span = item_div.find('span', class_='boldRed')
                    if status_span:
                        status = "Posuđeno"
                
                # Vrsta građe (iz ikone)
                item_type = "Nepoznato"
                type_img = item_div.find('img', class_='vrstaGradjeIkona')
                if type_img and type_img.get('alt'):
                    item_type = type_img['alt']
                
                item_info = {
                    'title': title,
                    'author': author,
                    'publisher': publisher,
                    'year': year,
                    'status': status,
                    'type': item_type,
                    'item_id': item_id
                }
                
                items.append(item_info)
                logger.info(f"  {title} ({item_type})")
            
            except Exception as e:
                logger.error(f"Greška pri parsiranju stavke: {e}")
                continue
        
        return items
    
    def format_category_message(
        self, 
        items: List[Dict], 
        category: str
    ) -> str:
        """Formatira poruku sa stavkama iz kategorije"""
        
        if not items:
            return (f"Nažalost, nisam pronašao stavke u kategoriji **{category}**.\n\n"
                   f"Provjerite katalog: https://katalog.halubajska-zora.hr")
        
        msg = f"🎯 **Preporuke iz kategorije: {category}**\n\n"
        
        for i, item in enumerate(items, 1):
            msg += f"{i}. **{item['title']}**"
            
            if item.get('author'):
                msg += f"\n   ✍️ {item['author']}"
            
            if item.get('year'):
                msg += f" ({item['year']})"
            
            if item.get('type'):
                msg += f"\n   📦 {item['type']}"
            
            if item.get('status'):
                if item['status'] == 'Dostupno':
                    msg += f"\n   ✅ {item['status']}"
                elif item['status'] == 'Posuđeno':
                    msg += f"\n   ❌ {item['status']}"
            
            msg += "\n\n"
        
        msg += f"🔗 Katalog: https://katalog.halubajska-zora.hr"
        
        return msg


# Test
if __name__ == "__main__":
    import asyncio
    import json
    
    async def test():
        print("=" * 70)
        print("CATEGORY SCRAPER - TEST")
        print("=" * 70)
        
        scraper = CategoryScraper()
        
        # Test različite kategorije
        test_categories = ['igračke', 'grafika', 'e-book']
        
        for category in test_categories:
            print(f"\n📦 Test kategorije: {category}")
            print("-" * 70)
            
            items = await scraper.get_items_by_category(
                category=category,
                limit=5,
                random_selection=True
            )

            print(scraper.format_category_message(items, category))

            print("\n" + "=" * 70)
            print("🔥 Test najčitanije: zadnjih 30 dana")
            print("-" * 70)

            most_read = await scraper.get_most_read(days=30, limit=5)

            print("\nRAW DATA:")
            print(json.dumps(most_read, indent=2, ensure_ascii=False))

            print("\nRAW DATA:")
            print(scraper.format_most_read_message(most_read, 30))
            
            print("\nFORMATIRANA PORUKA:")
            print("\n" + "=" * 70)
    
    asyncio.run(test())