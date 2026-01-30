"""
Web scraper za informacije sa stranice knjižnice
"""

import requests
from bs4 import BeautifulSoup
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WebsiteScraper:
    """Scraper za web stranicu knjižnice"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        })
    
    def scrape_membership_info(self):
        """Scrapa informacije o članstvu"""
        url = "https://www.halubajska-zora.hr/clanstvo-i-uvjeti-koristenja/"
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Dohvati glavni sadržaj
            content_div = soup.find('div', class_='entry-content')
            
            if not content_div:
                content_div = soup.find('article')
            
            if not content_div:
                logger.warning("Nije pronađen content div")
                return None
            
            # Izvuci tekst
            text_content = content_div.get_text(separator='\n', strip=True)
            
            # Izvuci sekcije
            sections = []
            current_section = None
            
            for element in content_div.find_all(['h2', 'h3', 'h4', 'p', 'ul', 'ol']):
                if element.name in ['h2', 'h3', 'h4']:
                    # Novi heading - nova sekcija
                    if current_section:
                        sections.append(current_section)
                    
                    current_section = {
                        'title': element.get_text(strip=True),
                        'content': []
                    }
                elif current_section:
                    # Dodaj sadržaj u trenutnu sekciju
                    text = element.get_text(strip=True)
                    if text:
                        current_section['content'].append(text)
            
            # Dodaj zadnju sekciju
            if current_section:
                sections.append(current_section)
            
            data = {
                'url': url,
                'full_text': text_content,
                'sections': sections
            }
            
            logger.info(f"✓ Scrapano {len(sections)} sekcija")
            return data
            
        except Exception as e:
            logger.error(f"Greška pri scrapingu: {e}")
            return None
    
    def scrape_multiple_pages(self, urls: list):
        """Scrapa više stranica"""
        all_data = []
        
        for url in urls:
            logger.info(f"Scrapam: {url}")
            
            try:
                response = self.session.get(url, timeout=10)
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Dohvati content
                content_div = soup.find('div', class_='entry-content') or soup.find('article')
                
                if content_div:
                    text = content_div.get_text(separator='\n', strip=True)
                    
                    # Dohvati naslov stranice
                    title_tag = soup.find('h1') or soup.find('title')
                    title = title_tag.get_text(strip=True) if title_tag else "Untitled"
                    
                    all_data.append({
                        'url': url,
                        'title': title,
                        'content': text
                    })
                    
                    logger.info(f"✓ Scrapano: {title}")
                    
            except Exception as e:
                logger.error(f"Greška pri scrapanju {url}: {e}")
        
        return all_data
    
    def save_to_json(self, data, filename='data/website_content.json'):
        """Spremi podatke u JSON"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"✓ Spremljeno u {filename}")


# Test
if __name__ == "__main__":
    print("=" * 70)
    print("WEBSITE SCRAPER TEST")
    print("=" * 70)
    
    scraper = WebsiteScraper()
    
    # Scrapa stranicu o članstvu
    print("\n1. Scrapam informacije o članstvu...")
    membership_data = scraper.scrape_membership_info()
    
    if membership_data:
        print(f"\n✓ Pronađeno {len(membership_data['sections'])} sekcija:")
        for section in membership_data['sections'][:5]:
            print(f"  - {section['title']}")
        
        # Spremi u JSON
        scraper.save_to_json(membership_data, 'data/membership_info.json')
    
    # Dodatne stranice koje možemo scrapati
    print("\n2. Scrapam dodatne stranice...")
    additional_urls = [
        "https://www.halubajska-zora.hr/clanstvo-i-uvjeti-koristenja/",
        "https://www.halubajska-zora.hr/usluge/",
    ]
    
    all_pages = scraper.scrape_multiple_pages(additional_urls)
    scraper.save_to_json(all_pages, 'data/website_all_pages.json')
    
    print("\n" + "=" * 70)
    print("✓ Scraping završen!")
    print("=" * 70)