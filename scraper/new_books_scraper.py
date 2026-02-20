"""
New Books Scraper - scrapa nove naslove iz knjižnice
"""

import httpx
from bs4 import BeautifulSoup
import logging
from typing import List, Dict
import os
from dotenv import load_dotenv
import re

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NewBooksScraper:
    """Scraper za nove naslove u knjižnici"""
    
    def __init__(self):
        self.base_url = "https://katalog.halubajska-zora.hr"
        self.scraper_api_key = os.getenv('SCRAPER_API_KEY')
    
    async def get_new_books(self, days: int = 365, limit: int = 10) -> List[Dict]:
        """
        Dohvati nove naslove iz knjižnice
        
        Args:
            days: Broj dana unazad (default 365)
            limit: Maksimalni broj rezultata (default 10)
            
        Returns:
            Lista knjiga: [{'title': ..., 'author': ..., 'date_added': ...}, ...]
        """
        
        try:
            new_books_url = f"{self.base_url}/pagesResults/rezultati.aspx?new={days}&sort=5"
            
            # Koristi ScraperAPI ako je dostupan
            if self.scraper_api_key:
                logger.info(f"Dohvaćam nove knjige preko ScraperAPI (zadnjih {days} dana)...")
                
                params = {
                    'api_key': self.scraper_api_key,
                    'url': new_books_url,
                    'country_code': 'hr'
                }
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(
                        "http://api.scraperapi.com/",
                        params=params
                    )
            else:
                # Fallback - direktan request
                logger.info(f"Dohvaćam nove knjige direktno...")
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(new_books_url)
            
            if response.status_code != 200:
                logger.error(f"HTTP error: {response.status_code}")
                return []
            
            logger.info(f"Response primljen: {len(response.text)} bytes")
            
            # Parsiraj HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            books = self._parse_books(soup, limit)
            
            logger.info(f"Parsirano {len(books)} novih knjiga")
            return books
        
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju novih knjiga: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _parse_books(self, soup: BeautifulSoup, limit: int) -> List[Dict]:
        """Parsira knjige iz HTML-a"""
        books = []
        
        # Pronađi sve div-ove sa klasom 'divBibZapis'
        book_divs = soup.find_all('div', class_='divBibZapis')
        
        logger.info(f"Pronađeno {len(book_divs)} knjiga")
        
        for book_div in book_divs[:limit]:
            try:
                # Naslov
                title_link = book_div.find('a', class_='aNaslovLink')
                title = title_link.get_text(strip=True) if title_link else "Nepoznato"
                
                # Book ID iz URL-a
                book_id = None
                if title_link and title_link.get('href'):
                    match = re.search(r'selectedId=(\d+)', title_link['href'])
                    if match:
                        book_id = match.group(1)
                
                # Autor
                author_link = book_div.find('a', class_='aAutor')
                author = author_link.get_text(strip=True) if author_link else "Nepoznat autor"
                
                # Nakladnik i godina - u tekstu nakon <br>
                publisher = None
                year = None
                
                desc_div = book_div.find('div', class_='rezultati-status')
                if desc_div:
                    text = desc_div.get_text()
                    
                    # Pronađi nakladnika (npr. "Zagreb : Mozaik knjiga, 2025.")
                    pub_match = re.search(r':\s*([^,]+),\s*(\d{4})', text)
                    if pub_match:
                        publisher = pub_match.group(1).strip()
                        year = pub_match.group(2)
                
                # Datum nabave (npr. "Nabavljeno 8. 2. 26.")
                date_added = None
                date_match = re.search(r'Nabavljeno\s+([\d\.]+\s+[\d\.]+\s+\d+\.?)', text)
                if date_match:
                    date_added = date_match.group(1).strip()
                
                # Status (Za posudbu / Posuđeno)
                status = "Nepoznato"
                status_span = book_div.find('span', class_='boldGreen')
                if status_span:
                    status = "Dostupno"
                else:
                    status_span = book_div.find('span', class_='boldRed')
                    if status_span:
                        status = "Posuđeno"
                
                book_info = {
                    'title': title,
                    'author': author,
                    'publisher': publisher,
                    'year': year,
                    'date_added': date_added,
                    'status': status,
                    'book_id': book_id
                }
                
                books.append(book_info)
                logger.info(f"  Parsirano: {title} - {author}")
            
            except Exception as e:
                logger.error(f"Greška pri parsiranju knjige: {e}")
                continue
        
        return books
    
    def format_new_books_message(self, books: List[Dict]) -> str:
        """Formatira poruku sa novim knjigama"""
        
        if not books:
            return ("📚 **Nove knjige**\n\n"
                   "Trenutno nema novih naslova u katalogu.\n\n"
                   "Provjerite katalog: https://katalog.halubajska-zora.hr")
        
        msg = f"📚 **Novi naslovi u knjižnici** ({len(books)} najnovijih):\n\n"
        
        for i, book in enumerate(books, 1):
            msg += f"{i}. **{book['title']}**\n"
            
            if book.get('author'):
                msg += f"\n   ✍️ {book['author']}"
            
            if book.get('year'):
                msg += f" ({book['year']})"
            
            if book.get('date_added'):
                msg += f"\n   📅 Nabavljeno: {book['date_added']}"
            
            if book.get('status'):
                if book['status'] == 'Dostupno':
                    msg += f"\n   ✅ {book['status']}"
                elif book['status'] == 'Posuđeno':
                    msg += f"\n   ❌ {book['status']}"
            
            msg += "\n\n"
        
        msg += "🔗 Svi novi naslovi: https://katalog.halubajska-zora.hr/pagesResults/rezultati.aspx?new=365"
        
        return msg


# Test
if __name__ == "__main__":
    import asyncio
    import json
    
    async def test():
        print("=" * 70)
        print("NEW BOOKS SCRAPER - TEST")
        print("=" * 70)
        
        scraper = NewBooksScraper()
        
        print("\n📚 Dohvaćam nove knjige...\n")
        
        books = await scraper.get_new_books(days=365, limit=10)
        
        print("\n" + "=" * 70)
        print("RAW DATA:")
        print("=" * 70)
        print(json.dumps(books, indent=2, ensure_ascii=False))
        
        print("\n" + "=" * 70)
        print("FORMATIRANA PORUKA:")
        print("=" * 70)
        print(scraper.format_new_books_message(books))
        
        print("\n✓ Done")
    
    asyncio.run(test())