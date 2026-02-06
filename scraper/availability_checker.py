"""
Availability Checker - Provjera dostupnosti knjiga u stvarnom vremenu
"""

import requests
from bs4 import BeautifulSoup
import logging
from typing import Dict, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AvailabilityChecker:
    """Provjera dostupnosti knjige u knjižnici"""
    
    def __init__(self):
        self.base_url = "https://katalog.halubajska-zora.hr"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        })
    
    def check_availability(self, book_id: str) -> Dict:
        """
        Provjeri dostupnost knjige po ID-u
        
        Returns:
            {
                'book_id': str,
                'title': str,
                'locations': [
                    {
                        'location': str,
                        'signature': str,
                        'status': str,  # 'available', 'borrowed', 'unknown'
                        'note': str,
                        'due_date': str or None
                    }
                ]
            }
        """
        try:
            url = f"{self.base_url}/pagesResults/bibliografskiZapis.aspx?selectedId={book_id}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # DEBUG - spremi HTML
            logger.info(f"Dohvaćen HTML za knjigu {book_id}")

            # Dohvati naslov
            title_div = soup.find('div', {'id': 'divNaslov'})
            title = "Nepoznato"
            if title_div:
                title_span = title_div.find('span', class_='hidden')
                if title_span:
                    title = title_span.get_text(strip=True)
            
            # Dohvati lokacije
            locations = self._parse_locations(soup)
            
            return {
                'book_id': book_id,
                'title': title,
                'locations': locations
            }
            
        except Exception as e:
            logger.error(f"Greška pri provjeri dostupnosti: {e}")
            return {
                'book_id': book_id,
                'title': 'Greška',
                'locations': [],
                'error': str(e)
            }
        
def format_availability_message(self, availability: Dict) -> str:
        if not availability.get('locations'):
            return f"Nažalost, trenutno ne mogu pronaći podatke o dostupnosti za knjigu: {availability.get('title', 'Nepoznato')}."
        
        msg = f"🔍 **Dostupnost za: {availability['title']}**\n"
        for loc in availability['locations']:
            status_emoji = "✅" if loc['status'] == 'available' else "❌"
            status_text = "Dostupno" if loc['status'] == 'available' else f"Posuđeno (rok: {loc['due_date']})"
            msg += f"\n{status_emoji} **{loc['location']}**"
            msg += f"\n   Status: {status_text}"
            msg += f"\n   Signatura: `{loc['signature']}`\n"
        return msg        
    
def _parse_locations(self, soup: BeautifulSoup) -> List[Dict]:
    """Parsira lokacije i statuse iz HTML-a"""
    locations = []
    
    # Pronađi sve div-ove koji sadrže lokacijske informacije
    # Traži h3/h4 koji imaju naziv lokacije prije tablice
    all_divs = soup.find_all('div')
    
    for div in all_divs:
        # Traži h3 ili h4 sa lokacijom
        location_header = div.find(['h3', 'h4'])
        
        if location_header:
            location_text = location_header.get_text(strip=True)
            
            # Filtriraj samo prave lokacijske headinge
            if any(keyword in location_text for keyword in ['Knjižnica', 'Središnja', 'Ogranak', 'tel:']):
                location_name = self._extract_location_name(location_text)
                
                # Pronađi tablicu nakon headera (u istom div-u ili sljedećem)
                table = div.find('table') or location_header.find_next('table')
                
                if table:
                    # Traži sve redove u tablici
                    rows = table.find_all('tr')
                    
                    for row in rows[1:]:  # Preskoči header row
                        status_info = self._parse_row_status(row)
                        
                        if status_info:
                            locations.append({
                                'location': location_name,
                                'signature': status_info.get('signature', 'N/A'),
                                'status': status_info.get('status', 'unknown'),
                                'note': status_info.get('note', ''),
                                'due_date': status_info.get('due_date', None)
                            })
    
    return locations

def _parse_row_status(self, row) -> Dict:
    try:
        cells = row.find_all('td')
        if len(cells) < 3:
            return None

        signature = cells[1].get_text(strip=True)
        status_cell = cells[2]
        status_img = status_cell.find('img')
        status_text = status_cell.get_text(strip=True)
        
        # 1. PROVJERA ZA E-KNJIGU (Gumb/Onclick)
        # Tražimo bilo što što ima 'posudbaLCP' u HTML-u tog polja
        if 'posudbaLCP' in str(status_cell):
            return {
                'signature': signature,
                'status': 'available',
                'note': '📱 E-knjiga (dostupna za posudbu)',
                'due_date': None
            }

        # 2. PROVJERA PREKO SLIKE (src)
        if status_img:
            img_src = status_img.get('src', '').lower()
            
            # Ako je kvačica (za_posudbu.png)
            if 'za_posudbu' in img_src:
                return {
                    'signature': signature,
                    'status': 'available',
                    'note': 'Dostupno',
                    'due_date': None
                }
            
            # Ako je posuđeno (posudjeno.png)
            elif 'posudjeno' in img_src or 'posuđeno' in img_src:
                import re
                date_match = re.search(r'(\d{1,2}\.\d{1,2}\.\d{4})', status_text)
                due_date = date_match.group(1) if date_match else "nepoznat datum"
                return {
                    'signature': signature,
                    'status': 'borrowed',
                    'note': f'Posuđeno do {due_date}',
                    'due_date': due_date
                }

        # 3. FALLBACK (ako nema slike, provjeri tekst)
        if 'dostupno' in status_text.lower():
            return {
                'signature': signature, 'status': 'available', 'note': 'Dostupno'
            }
            
        return None # Ako ništa ne odgovara, preskoči red

    except Exception as e:
        logger.error(f"Error parsing row: {e}")
        return None

# Test
if __name__ == "__main__":
    checker = AvailabilityChecker()
    
    # Test sa knjigom koja ima poznati ID
    book_id = "418000451"  # Primjer iz tvog linka
    
    print("=" * 70)
    print(f"PROVJERA DOSTUPNOSTI - Book ID: {book_id}")
    print("=" * 70)
    
    availability = checker.check_availability(book_id)
    
    print("\nRaw data:")
    import json
    print(json.dumps(availability, indent=2, ensure_ascii=False))
    
    print("\n" + "=" * 70)
    print("FORMATIRANA PORUKA:")
    print("=" * 70)
    
    message = checker.format_availability_message(availability)
    print(message)