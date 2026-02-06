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
            with open('data/availability_debug.html', 'w', encoding='utf-8') as f:
                f.write(soup.prettify())
            print("✓ HTML spremljen u data/availability_debug.html")

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
    """Parsira jedan red tablice sa statusom"""
    try:
        cells = row.find_all('td')
        
        if len(cells) < 3:
            return None
        
        # Struktura: Lokacija | Signatura | Status | Napomena | ...
        location_cell = cells[0].get_text(strip=True)  # npr. "282 Opći fond"
        signature = cells[1].get_text(strip=True)      # npr. "K NESBOE v"
        status_cell = cells[2]                          # HTML element sa statusom
        
        # Dohvati status text
        status_text = status_cell.get_text(strip=True)
        
        # Provjeri ima li sliku za status
        status_img = status_cell.find('img')
        
        # Parsiraj status
        if status_img:
            img_src = status_img.get('src', '')
            
            if 'posudjeno' in img_src or 'posuđeno' in img_src:
                # Izvuci datum
                import re
                date_match = re.search(r'(\d{1,2}\.\d{1,2}\.\d{4})', status_text)
                due_date = date_match.group(1) if date_match else None
                
                return {
                    'signature': signature,
                    'status': 'borrowed',
                    'note': status_text,
                    'due_date': due_date,
                    'location_detail': location_cell
                }
            
            elif 'dostupno' in img_src:
                return {
                    'signature': signature,
                    'status': 'available',
                    'note': status_text,
                    'due_date': None,
                    'location_detail': location_cell
                }
        
        # Ako nema slike, provjeri tekst
        status_lower = status_text.lower()
        
        if 'posuđeno' in status_lower or 'posudeno' in status_lower:
            import re
            date_match = re.search(r'(\d{1,2}\.\d{1,2}\.\d{4})', status_text)
            due_date = date_match.group(1) if date_match else None
            
            return {
                'signature': signature,
                'status': 'borrowed',
                'note': status_text,
                'due_date': due_date,
                'location_detail': location_cell
            }
        
        elif 'provjerite' in status_lower:
            return {
                'signature': signature,
                'status': 'available',
                'note': 'Provjerite status - vjerojatno dostupna',
                'due_date': None,
                'location_detail': location_cell
            }
        
        elif 'dostupno' in status_lower:
            return {
                'signature': signature,
                'status': 'available',
                'note': status_text,
                'due_date': None,
                'location_detail': location_cell
            }
        
        else:
            # Nepoznat status
            return {
                'signature': signature,
                'status': 'unknown',
                'note': status_text,
                'due_date': None,
                'location_detail': location_cell
            }
        
    except Exception as e:
        logger.error(f"Greška pri parsiranju reda: {e}")
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