"""
Availability Checker - Real-time book availability sa Selenium
"""

import requests
from bs4 import BeautifulSoup
import logging
from typing import Dict, List
import os

# Selenium imports
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logging.warning("Selenium nije dostupan - koristit će se requests fallback")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AvailabilityChecker:
    """Provjera dostupnosti knjige - sa Selenium fallback-om"""
    
    def __init__(self, use_selenium=None):
        self.base_url = "https://katalog.halubajska-zora.hr"
        
        # Auto-detect: koristi Selenium ako je dostupan
        if use_selenium is None:
            use_selenium = SELENIUM_AVAILABLE
        
        self.use_selenium = use_selenium and SELENIUM_AVAILABLE
        
        if self.use_selenium:
            logger.info("Koristim Selenium za scraping")
            self._setup_selenium()
        else:
            logger.info("Koristim requests za scraping")
            self.session = requests.Session()
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
    
    def _setup_selenium(self):
        """Setup Selenium Chrome driver"""
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        # Railway / Linux environment
        if os.getenv('RAILWAY_ENVIRONMENT') or os.path.exists('/usr/bin/chromium'):
            chrome_options.binary_location = "/usr/bin/chromium"
            service = Service("/usr/bin/chromedriver")
            logger.info("Koristim system chromium/chromedriver")
        else:
            # Lokalno - webdriver-manager
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
            logger.info("Koristim webdriver-manager")
        
        try:
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            logger.info("✓ Selenium Chrome driver inicijaliziran")
        except Exception as e:
            logger.error(f"Selenium greška: {e}")
            self.use_selenium = False
            # Inicijalizacija requests sessiona kao fallback
            self.session = requests.Session()
            self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
             })
    
    def check_availability(self, book_id: str) -> Dict:
        """Provjeri dostupnost knjige"""
        if self.use_selenium:
            return self._check_with_selenium(book_id)
        else:
            return self._check_with_requests(book_id)
    
    def _check_with_selenium(self, book_id: str) -> Dict:
        """Selenium pristup - čeka da se JavaScript izvrši"""
        try:
            url = f"{self.base_url}/pagesResults/bibliografskiZapis.aspx?selectedId={book_id}"
            
            logger.info(f"Selenium: Učitavam {url}")
            self.driver.get(url)
            
            # Čekaj naslov
            title_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "divNaslov"))
            )
            
            title_span = self.driver.find_element(By.CSS_SELECTOR, "#divNaslov span.hidden")
            title = title_span.text if title_span else "Nepoznato"
            
            logger.info(f"Naslov: {title}")
            
            # Čekaj da se tablice učitaju (AJAX)
            import time
            time.sleep(3)
            
            # Provjeri jesu li se tablice učitale
            try:
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "tblData"))
                )
                logger.info("✓ Tablice učitane")
            except:
                logger.warning("Timeout - tablice nisu učitane")
            
            # Dohvati HTML
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Parsiraj lokacije
            locations = self._parse_locations(soup)
            
            return {
                'book_id': book_id,
                'title': title,
                'locations': locations
            }
            
        except Exception as e:
            logger.error(f"Selenium greška: {e}")
            import traceback
            traceback.print_exc()
            return {
                'book_id': book_id,
                'title': 'Greška',
                'locations': [],
                'error': str(e)
            }
    
    def _check_with_requests(self, book_id: str) -> Dict:
        """Fallback - requests pristup (možda ne radi zbog bot protection)"""
        try:
            # Dohvati glavnu stranicu
            url = f"{self.base_url}/pagesResults/bibliografskiZapis.aspx?selectedId={book_id}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Dohvati naslov
            title_div = soup.find('div', {'id': 'divNaslov'})
            title = "Nepoznato"
            if title_div:
                title_span = title_div.find('span', class_='hidden')
                if title_span:
                    title = title_span.get_text(strip=True)
            
            # Pokušaj AJAX POST
            locations = self._get_locations_ajax_post(book_id)
            
            return {
                'book_id': book_id,
                'title': title,
                'locations': locations
            }
            
        except Exception as e:
            logger.error(f"Requests greška: {e}")
            return {
                'book_id': book_id,
                'title': 'Greška',
                'locations': [],
                'error': str(e)
            }
    
    def _get_locations_ajax_post(self, book_id: str) -> List[Dict]:
        """POST AJAX za lokacije"""
        try:
            import random
            
            ajax_url = f"{self.base_url}/pagesResults/bibliografskiZapis.aspx"
            
            headers = {
                'Accept': 'text/html, */*; q=0.01',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'Origin': self.base_url,
                'Referer': f"{self.base_url}/pagesResults/bibliografskiZapis.aspx?selectedId={book_id}"
            }
            
            data = {
                'action': 'getLokacije',
                'bibliografskiZapisId': book_id,
                'random': random.random()
            }
            
            response = self.session.post(ajax_url, data=data, headers=headers, timeout=10)
            response.raise_for_status()
            
            logger.info(f"AJAX response: {len(response.content)} bytes")
            
            if len(response.content) < 10:
                logger.warning("AJAX blokiran - response premalen")
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            return self._parse_locations(soup)
            
        except Exception as e:
            logger.error(f"AJAX greška: {e}")
            return []
    
    def _parse_locations(self, soup: BeautifulSoup) -> List[Dict]:
        """Parsira lokacije iz HTML-a"""
        locations = []
        
        table = soup.find('table', class_='tblData')
        
        if not table:
            all_tables = soup.find_all('table')
            if all_tables:
                table = all_tables[0]
        
        if not table:
            logger.warning("Nema tablica u HTML-u")
            return locations
        
        rows = table.find_all('tr')
        current_location = None
        
        for row in rows:
            cells = row.find_all('td')
            
            if not cells:
                continue
            
            first_cell_text = cells[0].get_text(strip=True)
            
            # Lokacija
            if 'tel:' in first_cell_text:
                current_location = self._extract_location_name(first_cell_text)
                continue
            
            # Header
            if first_cell_text == 'Lokacija':
                continue
            
            # Data red
            if current_location and len(cells) >= 3:
                location_detail = cells[0].get_text(strip=True)
                signature = cells[1].get_text(strip=True)
                status_td = cells[2]
                
                status_info = self._parse_td_status(status_td, signature)
                
                if status_info:
                    locations.append({
                        'location': f"{current_location} ({location_detail})",
                        'signature': status_info['signature'],
                        'status': status_info['status'],
                        'note': status_info['note'],
                        'due_date': status_info['due_date']
                    })
        
        logger.info(f"Parsirano {len(locations)} lokacija")
        return locations
    
    def _parse_td_status(self, status_td, signature: str) -> Dict:
        """Parsira status iz TD elementa"""
        try:
            status_text = status_td.get_text(strip=True)
            status_img = status_td.find('img')
            
            if status_img:
                img_src = status_img.get('src', '').lower()
                
                if 'posudjeno' in img_src or 'posuđeno' in img_src:
                    import re
                    date_match = re.search(r'(\d{1,2}\.\d{1,2}\.\d{4})', status_text)
                    due_date = date_match.group(1) if date_match else None
                    
                    return {
                        'signature': signature,
                        'status': 'borrowed',
                        'note': f'Posuđeno do {due_date}' if due_date else 'Posuđeno',
                        'due_date': due_date
                    }
                
                elif 'za_posudbu' in img_src or 'dostupno' in img_src:
                    return {
                        'signature': signature,
                        'status': 'available',
                        'note': 'Dostupno',
                        'due_date': None
                    }
            
            status_lower = status_text.lower()
            
            if 'posuđeno' in status_lower or 'posudeno' in status_lower:
                import re
                date_match = re.search(r'(\d{1,2}\.\d{1,2}\.\d{4})', status_text)
                due_date = date_match.group(1) if date_match else None
                
                return {
                    'signature': signature,
                    'status': 'borrowed',
                    'note': f'Posuđeno do {due_date}' if due_date else 'Posuđeno',
                    'due_date': due_date
                }
            
            elif 'provjerite' in status_lower:
                return {
                    'signature': signature,
                    'status': 'available',
                    'note': 'Dostupno',
                    'due_date': None
                }
            
            else:
                return {
                    'signature': signature,
                    'status': 'unknown',
                    'note': status_text,
                    'due_date': None
                }
        
        except Exception as e:
            logger.error(f"Greška: {e}")
            return None
    
    def _extract_location_name(self, text: str) -> str:
        """Čisti naziv lokacije"""
        import re
        clean_text = re.sub(r',.*?tel:.*', '', text)
        clean_text = re.sub(r',\s*\d+.*', '', clean_text)
        
        if not clean_text.strip():
            clean_text = text.split(',')[0]
        
        return clean_text.strip()
    
    def format_availability_message(self, availability: dict) -> str:
        """Formatira poruku"""
        book_title = availability.get('title', 'Nepoznato')
        book_id = availability.get('book_id')
        
        if not availability.get('locations'):
            return (f"📚 **{book_title}**\n\n"
                   f"Za trenutnu dostupnost, provjerite katalog:\n\n"
                   f"🔗 https://katalog.halubajska-zora.hr/pagesResults/bibliografskiZapis.aspx?selectedId={book_id}")
        
        msg = f"🔍 **Status za: {book_title}**\n\n"
        
        for loc in availability['locations']:
            status = loc.get('status', 'unknown')
            if status == 'available':
                status_emoji = "✅"
                status_text = "Slobodno"
            elif status == 'borrowed':
                status_emoji = "❌"
                due_date = loc.get('due_date')
                status_text = f"Posuđeno (rok: {due_date})" if due_date else "Posuđeno"
            else:
                status_emoji = "❓"
                status_text = "Nepoznato"

            msg += f"\n{status_emoji} **{loc['location']}**"
            msg += f"\n   Status: {status_text}"
            msg += f"\n   Signatura: `{loc.get('signature', 'N/A')}`\n"
        
        return msg
    
    def __del__(self):
        """Cleanup"""
        if hasattr(self, 'driver'):
            try:
                self.driver.quit()
            except:
                pass


# Test
if __name__ == "__main__":
    import json
    
    print("=" * 70)
    print("AVAILABILITY CHECKER - TEST")
    print("=" * 70)
    
    try:
        checker = AvailabilityChecker()
        
        test_book_id = "428003512"
        
        print(f"\n📚 Testiram knjigu ID: {test_book_id}\n")
        
        availability = checker.check_availability(test_book_id)
        
        print("\n" * 70)
        print("RAW DATA:")
        print("=" * 70)
        print(json.dumps(availability, indent=2, ensure_ascii=False))
        
        print("\n" + "=" * 70)
        print("FORMATIRANA PORUKA:")
        print("=" * 70)
        print(checker.format_availability_message(availability))
        
        print("\n✓ Test završen")
        
    except Exception as e:
        print(f"\n❌ GREŠKA: {e}")
        import traceback
        traceback.print_exc()