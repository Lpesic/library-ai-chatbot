"""
Availability Checker sa Playwright - SYNC
"""

from bs4 import BeautifulSoup
import logging
from typing import Dict, List
import asyncio
import re

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logging.warning("Playwright nije instaliran")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PlaywrightChecker:
    """Provjera dostupnosti sa Playwright"""
    
    def __init__(self):
        self.base_url = "https://katalog.halubajska-zora.hr"
        self.use_playwright = PLAYWRIGHT_AVAILABLE
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning("⚠️ Playwright biblioteka nije instalirana!")
        if not self.use_playwright:
            logger.warning("Playwright nije dostupan")
    
    async def check_availability(self, book_id: str) -> Dict:
        """Provjeri dostupnost knjige"""
        logger.info(f"--- START CHECK_AVAILABILITY za ID: {book_id} ---")

        if not PLAYWRIGHT_AVAILABLE:
            return {"error": "Playwright nije instaliran na serveru."}
        try:
            async with async_playwright() as p:
                logger.info("Playwright pokrenut, palim browser...")

                browser = await p.chromium.launch(
                headless=True, 
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled", "--single-process"]
                )
                context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                viewport={'width': 1280, 'height': 800}
                )
                page = await context.new_page()
                
                # URL
                url = f"{self.base_url}/pagesResults/bibliografskiZapis.aspx?selectedId={book_id}"
                logger.info(f"Playwright: učitavam {url}")
                
                await page.set_extra_http_headers({
                    "Accept-Language": "hr-HR,hr;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache"
                })

                response = await page.goto(url, wait_until="networkidle", timeout=60000)
                logger.info(f"Response status: {response.status if response else 'No response'}")
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                logger.info("Čekam 5 sekundi za AJAX load...")
                await asyncio.sleep(5) 
                await page.mouse.move(100, 100)
                await page.mouse.click(200, 200)            
                
                # Dohvati naslov
                title = "Nepoznato"
                try:
                    # Pokušaj uhvatiti naslov, ako ne uspije, nije kritično
                    if await page.locator("#divNaslov").count() > 0:
                        raw_title = await page.locator("#divNaslov").text_content()
                        if raw_title:
                            title = raw_title.split("/")[0].strip()
                        else:
                            title = "Nepoznato"
                except Exception as e:
                    logger.warning(f"Nisam uspio dohvatiti naslov: {e}")
                
                logger.info(f"Očišćen naslov: {title}")
                
                try:
                    # Čekamo do 10 sekundi da se tablica pojavi u DOM-u
                    await page.wait_for_selector(".tblData tr", timeout=10000)
                    logger.info("Tablica s podacima pronađena!")
                except Exception:
                    logger.warning("Tablica se nije pojavila na vrijeme, pokušavam uzeti content...")

                # Dohvati HTML
                html = await page.content()    
                await browser.close()
                browser = None
                
                # Parsiraj
                soup = BeautifulSoup(html, 'html.parser')
                locations = self._parse_locations(soup)
                logger.info(f"Broj pronađenih lokacija: {len(locations)}")
                
                return {
                    'book_id': book_id,
                    'title': title.strip() if title else "Nepoznato",
                    'locations': locations
                }
        
        except Exception as e:
            logger.error(f"Playwright greška: {e}")
            import traceback
            traceback.print_exc()

            if browser:
                await browser.close()

            return {
                'book_id': book_id,
                'title': 'Greška',
                'locations': [],
                'error': str(e)
            }
    
    def _parse_locations(self, soup: BeautifulSoup) -> List[Dict]:
        """Parsira lokacije"""
        locations = []
        
        table = soup.find('table', class_='tblData')
        
        if not table:
            all_tables = soup.find_all('table')
            if all_tables:
                table = all_tables[0]
        
        if not table:
            logger.warning("Nema tablice s podacima u HTML-u")
            return locations
        
        rows = table.find_all('tr')
        current_location = "Glavna zbirka"
        
        for row in rows:
            cells = row.find_all('td')     
            if not cells:
                continue
            
            first_cell = cells[0].get_text(strip=True)
            
            if first_cell == 'Lokacija':
                continue

            # Lokacija
            if 'tel:' in first_cell:
                import re
                clean = re.sub(r',.*?tel:.*', '', first_cell)
                clean = re.sub(r',\s*\d+.*', '', clean)
                current_location = clean.strip() or first_cell.split(',')[0]
                continue
            
            # Header
            if first_cell == 'Lokacija':
                continue
            
            # Data
            if current_location and len(cells) >= 3:
                loc_detail = cells[0].get_text(strip=True)
                signature = cells[1].get_text(strip=True)
                status_text = cells[2].get_text(strip=True)
                
                #Ako je red prazan, preskoči
                if not signature and not status_text:
                    continue

                # Parse status
                status_info = self._parse_status(status_text, signature)
                
                if status_info:
                    locations.append({
                        'location': f"{current_location} ({loc_detail})",
                        'signature': status_info['signature'],
                        'status': status_info['status'],
                        'note': status_info['note'],
                        'due_date': status_info['due_date']
                    })
        
        logger.info(f"Parsirano {len(locations)} lokacija")
        return locations
    
    def _parse_status(self, status_text: str, signature: str) -> Dict:
        """Parse status"""
        import re
        
        status_lower = status_text.lower()
        
        if 'posuđeno' in status_lower or 'posudeno' in status_lower:
            date_match = re.search(r'(\d{1,2}\.\d{1,2}\.\d{4})', status_text)
            due_date = date_match.group(1) if date_match else None
            
            return {
                'signature': signature,
                'status': 'borrowed',
                'note': f'Posuđeno do {due_date}' if due_date else 'Posuđeno',
                'due_date': due_date
            }
        
        elif 'provjerite' in status_lower or 'dostupno' in status_lower:
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
    
    def format_availability_message(self, availability: dict) -> str:
        """Format message"""
        if 'error' in availability:
            return f"⚠️ Došlo je do greške pri provjeri: {availability['error']}"
        
        book_title = availability.get('title', 'Nepoznato')
        book_id = availability.get('book_id')
        
        if not availability.get('locations'):
            return (f"📚 **{book_title}**\n\n"
                   f"Za dostupnost provjerite katalog:\n\n"
                   f"🔗 https://katalog.halubajska-zora.hr/pagesResults/bibliografskiZapis.aspx?selectedId={book_id}")
        
        msg = f"🔍 **Status za: {book_title}**\n\n"
        
        for loc in availability['locations']:
            status = loc.get('status', 'unknown')
            if status == 'available':
                emoji = "✅"
                text = "Slobodno"
            elif status == 'borrowed':
                emoji = "❌"
                due = loc.get('due_date')
                text = f"Posuđeno (rok: {due})" if due else "Posuđeno"
            else:
                emoji = "❓"
                text = "Nepoznato"

            msg += f"\n{emoji} **{loc['location']}**"
            msg += f"\n   Status: {text}"
            msg += f"\n   Signatura: `{loc.get('signature', 'N/A')}`\n"
        
        return msg

# Test
async def main():
    print("=" * 70)
    print("PLAYWRIGHT ASYNC TEST")
    print("=" * 70)
    
    checker = PlaywrightChecker()
    test_id = "428003512"
    
    # Moramo koristiti 'await'!
    result = await checker.check_availability(test_id)
    
    import json
    print("\nRAW DATA:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("\nPORUKA:")
    print(checker.format_availability_message(result))

if __name__ == "__main__":
    asyncio.run(main())