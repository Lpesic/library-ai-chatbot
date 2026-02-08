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
        
    def format_availability_message(self, availability: dict) -> str:
        """
        Pretvara podatke o dostupnosti u lijepo formatiranu poruku za chat.
        """
        if "error" in availability:
            return "Žao mi je, trenutno ne mogu provjeriti status u katalogu. Molim vas pokušajte kasnije."

        if not availability.get('locations'):
            return f"Nažalost, trenutno ne mogu pronaći podatke o dostupnosti za knjigu: **{availability.get('title', 'Nepoznato')}**."
        
        msg = f"🔍 **Status za: {availability['title']}**\n"
        
        for loc in availability['locations']:
            # Logika za emojije na temelju statusa
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
    
    def _parse_locations(self, soup: BeautifulSoup) -> List[Dict]:
        locations = []

        all_tables = soup.find_all('table')
        logger.info(f"DEBUG: Ukupno tablica na stranici: {len(all_tables)}")
        
        for i, table in enumerate(all_tables):
            classes = table.get('class', [])
            logger.info(f"  Tablica {i}: class={classes}")
        
        # Pronađi glavnu tablicu s podacima
        table = soup.find('table', class_='tblData')
        
        if not table:
            logger.warning("Tablica 'tblData' nije pronađena!")
            
            # Pokušaj s alternativnim selectorima
            table = soup.find('table', {'id': 'tableBibliografskiZapis'})
            if table:
                logger.info("Pronađena tablica s ID 'tableBibliografskiZapis'")
            else:
                # Pokušaj bilo koju tablicu koja ima "Status" u headerima
                for t in all_tables:
                    if 'Status' in t.get_text():
                        table = t
                        logger.info(f"Pronađena tablica sa 'Status' tekstom")
                        break
        
        if not table:
            logger.error("Niti jedna tablica nije pronađena!")
            return locations

        # Pronađi glavnu tablicu s podacima
        table = soup.find('table', class_='tblData')
        
        if not table:
            logger.warning("Tablica 'tblData' nije pronađena.")
            return locations

        current_library = "Središnja knjižnica"
        rows = table.find_all('tr')

        for row in rows:
            # 1. Provjeri je li red naslov nove knjižnice (npr. Središnja knjižnica Marinići)
            lib_header = row.find('td', class_='tdKnjiznicaNaziv')
            if lib_header:
            # Uzimamo tekst prije prvog zareza ili linka
                current_library = lib_header.get_text(separator="|").split("|")[0].strip()
                continue

        # 2. Preskoči zaglavlja stupaca (Lokacija, Signatura, Status...)
            if "Signatura" in row.get_text() or "Ident" in row.get_text():
                continue

        # 3. Obradi red s podacima o knjizi
        cells = row.find_all('td')
        # Red s podacima obično ima 4-6 ćelija (ovisno o hidden-xs)
        if len(cells) >= 3 and not row.get('hidden'):
            # Provjeri ima li sliku ili 'posudbaLCP' gumb (to je tvoj status)
            status_info = self._parse_row_status(row)
            
            if status_info:
                # Dodajemo lokaciju specifičnog odjela (npr. "281 Opći fond")
                specific_dep = cells[0].get_text(strip=True)
                full_location = f"{current_library} ({specific_dep})"
                
                locations.append({
                    'location': f"{current_library} ({specific_dep})",
                    'signature': status_info.get('signature', 'N/A'),
                    'status': status_info.get('status', 'unknown'),
                    'note': status_info.get('note', ''),
                    'due_date': status_info.get('due_date', None)
                })                 
        return locations
    
    def _extract_location_name(self, text: str) -> str:
        """Čisti tekst lokacije od adrese i telefona"""
        import re
        
        # Ukloni adresu i telefon
        clean_text = re.sub(r',.*?tel:.*', '', text)
        
        # Ukloni broj i poštanski kod
        clean_text = re.sub(r',\s*\d+.*', '', clean_text)
        
        # Ako je ostalo prazno, vrati originalni text do prve zareze
        if not clean_text.strip():
            clean_text = text.split(',')[0]
        
        return clean_text.strip()

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
                    date_match = re.search(r'(\d{1,2}\.\d{1,2}\.\d{4})', status_cell.get_text())
                    due_date = date_match.group(1) if date_match else None
                    return {
                        'signature': signature,
                        'status': 'borrowed',
                        'note': f'Posuđeno do {due_date}'if due_date else 'Posuđeno',
                        'due_date': due_date
                    }

            # 3. FALLBACK (ako nema slike, provjeri tekst)
            if 'provjerite status' in status_text.lower():
                return {
                    'signature': signature, 
                    'status': 'unknown', 
                    'note': 'Status dostupan na upit (Provjerite status)'
                }   
            if 'dostupno' in status_text.lower():
                return {
                    'signature': signature, 'status': 'available', 'note': 'Dostupno'
                }
            return None # Ako ništa ne odgovara, preskoči red

        except Exception as e:
            logger.error(f"Error parsing row: {e}")
            return None

    def check_availability(self, book_id: str) -> Dict:
        """Provjeri dostupnost knjige po ID-u"""
        try:
            # 1. Prvo učitaj glavnu stranicu da dobiješ session cookie
            url = f"{self.base_url}/pagesResults/bibliografskiZapis.aspx?selectedId={book_id}"
            logger.info(f"Dohvaćam glavnu stranicu za session...")
            
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
            
            logger.info(f"Naslov: {title}")
            logger.info(f"Session cookies: {self.session.cookies}")
            
            # 2. Sada pozovi AJAX sa POST requestom i session cookieom
            locations = self._get_locations_ajax_post(book_id)
            
            return {
                'book_id': book_id,
                'title': title,
                'locations': locations
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

    def _get_locations_ajax_post(self, book_id: str) -> List[Dict]:
        """Dohvaća lokacije preko POST AJAX endpointa"""
        try:
            import random
            
            # POST na istu stranicu
            ajax_url = f"{self.base_url}/pagesResults/bibliografskiZapis.aspx"
            
            # Headers kao u browser requestu
            headers = {
                'Accept': 'text/html, */*; q=0.01',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'Origin': self.base_url,
                'Referer': f"{self.base_url}/pagesResults/bibliografskiZapis.aspx?selectedId={book_id}"
            }
            
            # POST data (form-urlencoded)
            data = {
                'action': 'getLokacije',
                'bibliografskiZapisId': book_id,
                'random': random.random()
            }
            
            logger.info(f"POST AJAX: {ajax_url}")
            
            response = self.session.post(
                ajax_url,
                data=data,
                headers=headers,
                timeout=10
            )
            
            response.raise_for_status()
            logger.info(f"AJAX response status: {response.status_code}")
            logger.info(f"Response length: {len(response.content)} bytes")
            
            response_text = response.text
            logger.info(f"Response text (prvih 500 chars): {response_text[:500]}")

            # Parsiraj HTML odgovor
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # DEBUG
            import os
            if os.path.exists('data'):
                with open('data/ajax_post_response.html', 'w', encoding='utf-8') as f:
                    f.write(soup.prettify())
                logger.info("✓ POST response spremljen u data/ajax_post_response.html")
            
            # Debug text
            all_tables = soup.find_all('table')
            logger.info(f"AJAX: Pronađeno {len(all_tables)} tablica")

            if len(all_tables) == 0:
                logger.warning(f"Nema tablica! Response: {response_text[:1000]}")
                      
            # Parsiraj lokacije
            locations = self._parse_ajax_locations(soup)
            
            return locations
            
        except Exception as e:
            logger.error(f"AJAX POST greška: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _parse_ajax_locations(self, soup: BeautifulSoup) -> List[Dict]:
        """Parsira lokacije iz AJAX POST odgovora"""
        locations = []
        
        all_tables = soup.find_all('table')
        logger.info(f"AJAX: Pronađeno {len(all_tables)} tablica")
        
        if not all_tables:
            return locations
        
        table = all_tables[0]
        rows = table.find_all('tr')
        
        logger.info(f"Tablica ima {len(rows)} redova")
        
        current_location = None
        
        for row_idx, row in enumerate(rows):
            cells = row.find_all('td')
            
            if not cells:
                continue
            
            logger.info(f"Red {row_idx}: {len(cells)} celija")
            
            # Ispiši prvih nekoliko celija
            for i, cell in enumerate(cells[:5]):
                text = cell.get_text(strip=True)[:50]
                logger.info(f"  Cell {i}: '{text}'")
            
            # 1. Provjeri je li ovo red sa lokacijom (sadrži "tel:")
            first_cell_text = cells[0].get_text(strip=True)
            
            if 'tel:' in first_cell_text:
                current_location = self._extract_location_name(first_cell_text)
                logger.info(f"→ Lokacija pronađena: {current_location}")
                continue
            
            # 2. Preskoči header red
            if len(cells) >= 3 and cells[0].get_text(strip=True) == 'Lokacija':
                logger.info("→ Header red (preskačem)")
                continue
            
            # 3. Red sa podacima (mora imati bar 3 celije)
            if current_location and len(cells) >= 3:
                location_detail = cells[0].get_text(strip=True)  # "281 Opći fond"
                signature = cells[1].get_text(strip=True)         # "K NESBOE v"
                status_td = cells[2]                               # Status TD
                
                logger.info(f"→ Data red: loc='{location_detail}', sig='{signature}'")
                
                # Parsiraj status
                status_info = self._parse_td_status(status_td, signature)
                
                if status_info:
                    logger.info(f"  ✓ Status parsiran: {status_info['status']} - {status_info['note']}")
                    
                    locations.append({
                        'location': f"{current_location} ({location_detail})",
                        'signature': status_info['signature'],
                        'status': status_info['status'],
                        'note': status_info['note'],
                        'due_date': status_info['due_date']
                    })
                else:
                    logger.warning(f"  ✗ Status NIJE parsiran")
        
        logger.info(f"Ukupno lokacija parsirano: {len(locations)}")
        return locations
    
    def _parse_td_status(self, status_td, signature: str) -> Dict:
        """Parsira status iz pojedinačnog TD elementa"""
        try:
            status_text = status_td.get_text(strip=True)
            status_img = status_td.find('img')
            
            # Provjeri sliku
            if status_img:
                img_src = status_img.get('src', '').lower()
                
                if 'posudjeno' in img_src or 'posuđeno' in img_src:
                    # Izvuci datum
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
            
            # Ako nema slike, provjeri text
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
                    'note': 'Dostupno (provjerite status)',
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
            logger.error(f"Greška pri parsiranju TD statusa: {e}")
            return None

if __name__ == "__main__":
    import json
    
    print("=" * 70)
    print("AVAILABILITY CHECKER - TEST")
    print("=" * 70)
    
    checker = AvailabilityChecker()
    
    # Test sa poznatim ID-jem
    test_book_id = "428003512"  # Error 404 knjiga
    
    print(f"\n📚 Testiram knjigu ID: {test_book_id}\n")
    
    availability = checker.check_availability(test_book_id)
    
    print("\n" + "=" * 70)
    print("RAW DATA:")
    print("=" * 70)
    print(json.dumps(availability, indent=2, ensure_ascii=False))
    
    print("\n" + "=" * 70)
    print("FORMATIRANA PORUKA ZA CHAT:")
    print("=" * 70)
    print(checker.format_availability_message(availability))
    
    print("\n" + "=" * 70)
    print("✓ Test završen")
    print("=" * 70)