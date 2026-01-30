"""
Library Catalog Scraper - Halubajska Zora
Kompletni scraper sa detaljnim parsiranjem
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import logging
import re
import json
from typing import List, Dict
from book_detail_parser import BookDetailParser

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LibraryScraper:
    """Kompletan scraper za katalog knjižnice"""
    
    def __init__(self):
        self.base_url = "https://katalog.halubajska-zora.hr"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        })
        self.detail_parser = BookDetailParser(self.base_url)
        logger.info("Scraper inicijaliziran")
    
    def test_connection(self):
        """Testira connection na katalog"""
        try:
            url = f"{self.base_url}/pages/search.aspx"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            logger.info(f"✓ Uspješno povezan! Status: {response.status_code}")
            return True
            
        except Exception as e:
            logger.error(f"✗ Greška: {e}")
            return False
    
    def extract_book_info(self, link_element) -> Dict:
        """Izvlači osnovne informacije o knjizi iz HTML elementa"""
        try:
            img = link_element.find('img')
            if not img:
                return None
            
            alt_text = img.get('alt', '')
            href = link_element.get('href', '')
            book_id_match = re.search(r'selectedId=(\d+)', href)
            book_id = book_id_match.group(1) if book_id_match else None
            
            parts = alt_text.split(' / ')
            title = parts[0].strip() if parts else alt_text
            author = parts[1].split(';')[0].strip() if len(parts) > 1 else "N/A"
            
            book_info = {
                'id': book_id,
                'title': title,
                'author': author,
                'full_info': alt_text,
                'url': f"{self.base_url}/pagesResults/{href}"
            }
            
            return book_info
            
        except Exception as e:
            logger.error(f"Greška pri parsiranju knjige: {e}")
            return None
    
    def get_new_books(self, max_books: int = 50) -> List[Dict]:
        """Dohvaća nove knjige (samo osnovni podaci)"""
        try:
            url = f"{self.base_url}/pagesResults/rezultati.aspx?new=365"
            response = self.session.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            book_links = soup.find_all('a', href=lambda x: x and 'bibliografskiZapis' in x)
            
            books = []
            seen_ids = set()
            
            for link in book_links:
                book_info = self.extract_book_info(link)
                if book_info and book_info['id'] not in seen_ids:
                    books.append(book_info)
                    seen_ids.add(book_info['id'])
                    
                    if len(books) >= max_books:
                        break
            
            logger.info(f"Uspješno parsirano {len(books)} jedinstvenih knjiga")
            return books
            
        except Exception as e:
            logger.error(f"Greška: {e}")
            return []
    
    def scrape_catalog_full(self, max_books: int = 20, delay: float = 2.0):
        """
        Scrapa katalog sa SVIM detaljima
        
        Args:
            max_books: Maksimalan broj knjiga za scraping
            delay: Pauza između zahtjeva (sekunde) - budi pristojan!
        """
        logger.info(f"Započinjem potpuni scraping {max_books} knjiga...")
        
        # 1. Dohvati osnovne informacije
        basic_books = self.get_new_books(max_books=max_books)
        
        if not basic_books:
            logger.error("Nema knjiga za scraping")
            return []
        
        # 2. Za svaku knjigu dohvati detaljne informacije
        detailed_books = []
        
        for i, book in enumerate(basic_books, 1):
            logger.info(f"[{i}/{len(basic_books)}] Scrapam detalje: {book['title']}")
            
            try:
                # Dohvati detaljne informacije
                details = self.detail_parser.parse_book_detail(book['id'])
                
                # Spoji osnovne i detaljne informacije
                full_book_data = {**book, **details}
                detailed_books.append(full_book_data)
                
                # Pauza između zahtjeva
                if i < len(basic_books):
                    time.sleep(delay)
                    
            except Exception as e:
                logger.error(f"Greška pri scrapingu knjige {book['id']}: {e}")
                detailed_books.append(book)  # Dodaj barem osnovne podatke
        
        logger.info(f"✓ Scraping završen! Ukupno: {len(detailed_books)} knjiga")
        return detailed_books
    
    def save_to_csv(self, books: List[Dict], filename: str = 'data/books_catalog.csv'):
        """Sprema knjige u CSV (za jednostavne podatke)"""
        if not books:
            logger.warning("Nema knjiga za spremanje")
            return
        
        # Pripremi podatke za CSV (pretvorimo liste u stringove)
        books_for_csv = []
        for book in books:
            book_copy = book.copy()
            
            # Pretvori liste u stringove
            for key, value in book_copy.items():
                if isinstance(value, list):
                    if value and isinstance(value[0], dict):
                        # Lista dictionary-ja (npr. classifications)
                        book_copy[key] = ' | '.join([str(item) for item in value])
                    else:
                        # Obična lista (npr. subjects, tags)
                        book_copy[key] = ' | '.join(value)
            
            books_for_csv.append(book_copy)
        
        df = pd.DataFrame(books_for_csv)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        logger.info(f"✓ Spremljeno {len(books)} knjiga u {filename}")
    
    def save_to_json(self, books: List[Dict], filename: str = 'data/books_catalog.json'):
        """Sprema knjige u JSON (sa svim strukturama)"""
        if not books:
            logger.warning("Nema knjiga za spremanje")
            return
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(books, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✓ Spremljeno {len(books)} knjiga u {filename}")


# Test kod
if __name__ == "__main__":
    print("=" * 70)
    print("LIBRARY SCRAPER - FULL VERSION")
    print("=" * 70)
    
    scraper = LibraryScraper()
    
    # Test connection
    print("\n1. Testiram konekciju...")
    if not scraper.test_connection():
        print("Greška u konekciji!")
        exit(1)
    
    # Scrape samo 5 knjiga za test
    print("\n2. Scrapam 5 knjiga sa SVIM detaljima...")
    books = scraper.scrape_catalog_full(max_books=5, delay=1.5)
    
    # Spremanje
    print("\n3. Spremam podatke...")
    scraper.save_to_csv(books)
    scraper.save_to_json(books)
    
    # Prikaz rezultata
    print("\n" + "=" * 70)
    print("REZULTATI:")
    print("=" * 70)
    for i, book in enumerate(books, 1):
        print(f"\n{i}. {book.get('title', 'N/A')}")
        print(f"   Autor: {book.get('author', 'N/A')}")
        print(f"   ISBN: {book.get('isbn', 'N/A')}")
        print(f"   Stranica: {book.get('pages', 'N/A')}")
        print(f"   Tagovi: {', '.join(book.get('tags', [])[:3])}...")
    
    print("\n" + "=" * 70)
    print(f"✓ ZAVRŠENO!")
    print(f"Provjerite fajlove:")
    print(f"  - data/books_catalog.csv")
    print(f"  - data/books_catalog.json")
    print("=" * 70)