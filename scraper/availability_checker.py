"""
Availability Checker HTTPX ScraperAPI
"""
import httpx
from bs4 import BeautifulSoup
import logging
from typing import Dict, List
import asyncio
import os
from dotenv import load_dotenv 

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ScraperAPIChecker:
    """Provjera dostupnosti sa HTTPX ScraperAPI"""
    
    def __init__(self):
        self.base_url = "https://katalog.halubajska-zora.hr"
        self.headers = {
            "Host": "katalog.halubajska-zora.hr",
            "Connection": "keep-alive",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": self.base_url,
            "Referer": self.base_url + "/pagesResults/bibliografskiZapis.aspx",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "hr-HR,hr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua": '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
        }
        self.scraper_api_key = os.getenv('SCRAPER_API_KEY')
        if not self.scraper_api_key:
            logger.warning("SCRAPER_API_KEY nije postavljen - scraping neće raditi")
    
    async def check_availability(self, book_id: str) -> Dict:
        """Provjeri dostupnost knjige"""
        if not self.scraper_api_key:
            return {
                'book_id': book_id,
                'title': 'Greška',
                'locations': [],
                'error': 'ScraperAPI key nije postavljen'
            }     
        
        try: 
            main_url = f"{self.base_url}/pagesResults/bibliografskiZapis.aspx?selectedId={book_id}"
            params = {
                'api_key': self.scraper_api_key,
                'url': main_url,
                'render': 'true', 
                'country_code': 'hr'  # Koristi HR proxy
            }
            logger.info(f"Dohvaćam stranicu preko ScraperAPI (render=true)...")

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(
                    "http://api.scraperapi.com/",
                    params=params
                )
                if response.status_code != 200:
                    logger.error(f"ScraperAPI error: {response.status_code}")
                    return {
                        'book_id': book_id,
                        'title': 'Greška',
                        'locations': [],
                        'error': f'HTTP {response.status_code}'
                    }
                logger.info(f"Response primljen: {len(response.text)} bytes")

                soup = BeautifulSoup(response.text, 'html.parser')

                title = "Nepoznato"
                title_elem = soup.select_one("#divNaslov span.hidden")
                if title_elem:
                    title = title_elem.get_text(strip=True).split('/')[0].strip()
                logger.info(f"Naslov: {title}")

                locations = self._parse_locations(soup)

                return {
                    'book_id': book_id,
                    'title': title,
                    'locations': locations,
                }
                
        except httpx.ReadTimeout:
            logger.error("Timeout - ScraperAPI predugo odgovara")
            return {
                'book_id': book_id,
                'title': 'Timeout',
                'locations': [],
                'error': 'Request timeout - pokušaj ponovno'
            }
        
        except Exception as e:
            logger.error(f"Greška: {e}")
            import traceback
            traceback.print_exc()
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
            logger.info(f"Pronađeno {len(all_tables)} tablica")
            if all_tables:
                table = all_tables[0]
        
        if not table:
            logger.warning("Nema tablice u HTML-u")
            return locations

        rows = soup.find_all('tr')
        logger.info(f"Tablica ima {len(rows)} redova")
        current_location = None
        
        for row in rows:
            cells = row.find_all(['td'])  
            if not cells:
                continue
            first_cell = cells[0].get_text(strip=True)

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
                    logger.info(f"  Parsiran status: {status_info['status']}")
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
    print("HTTPX ASYNC TEST")
    print("=" * 70)
    
    checker = ScraperAPIChecker()
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