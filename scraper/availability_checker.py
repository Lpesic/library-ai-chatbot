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
        
        # Pronađi sve tablice sa lokacijama
        # Traži h3/h4 headinge koji imaju naziv lokacije
        location_headers = soup.find_all(['h3', 'h4', 'strong'])
        
        for header in location_headers:
            header_text = header.get_text(strip=True)
            
            # Filtriraj samo lokacijske headinge (sadrže adresu ili tel)
            if 'tel:' in header_text or 'Knjižnica' in header_text or 'Središnja' in header_text:
                location_name = self._extract_location_name(header_text)
                
                # Pronađi tablicu nakon ovog headera
                table = header.find_next('table')
                
                if table:
                    # Traži red sa statusom
                    status_row = self._find_status_in_table(table)
                    
                    if status_row:
                        locations.append({
                            'location': location_name,
                            'signature': status_row.get('signature', 'N/A'),
                            'status': status_row.get('status', 'unknown'),
                            'note': status_row.get('note', ''),
                            'due_date': status_row.get('due_date', None)
                        })
        
        return locations
    
    def _extract_location_name(self, text: str) -> str:
        """Izvlači naziv lokacije iz headinga"""
        # Primjer: "Središnja knjižnica Marinići, Marinići 9, ..."
        # Uzmi samo prvi dio
        parts = text.split(',')
        if parts:
            return parts[0].strip()
        return text.strip()
    
    def _find_status_in_table(self, table) -> Dict:
        """Traži status u tablici"""
        try:
            rows = table.find_all('tr')
            
            for row in rows:
                cells = row.find_all('td')
                
                if len(cells) >= 3:
                    # Obično format: Lokacija | Signatura | Status | Napomena
                    signature = cells[1].get_text(strip=True) if len(cells) > 1 else 'N/A'
                    status_text = cells[2].get_text(strip=True) if len(cells) > 2 else ''
                    note = cells[3].get_text(strip=True) if len(cells) > 3 else ''
                    
                    # Parsiraj status
                    status_info = self._parse_status(status_text, note)
                    
                    return {
                        'signature': signature,
                        'status': status_info['status'],
                        'note': status_info['note'],
                        'due_date': status_info['due_date']
                    }
        except Exception as e:
            logger.error(f"Greška pri parsiranju tablice: {e}")
        
        return {}
    
    def _parse_status(self, status_text: str, note: str = '') -> Dict:
        """
        Parsira status tekst
        
        Returns:
            {
                'status': 'available' | 'borrowed' | 'unknown',
                'note': str,
                'due_date': str or None
            }
        """
        combined_text = (status_text + ' ' + note).lower()
        
        # Provjeri za različite statuse
        if 'posuđeno' in combined_text or 'posudeno' in combined_text:
            # Izvuci datum ako postoji
            import re
            date_match = re.search(r'(\d{1,2}\.\d{1,2}\.\d{4})', combined_text)
            due_date = date_match.group(1) if date_match else None
            
            return {
                'status': 'borrowed',
                'note': note,
                'due_date': due_date
            }
        
        elif 'provjerite' in combined_text:
            return {
                'status': 'available',
                'note': note,
                'due_date': None
            }
        
        elif 'dostupno' in combined_text or 'available' in combined_text:
            return {
                'status': 'available',
                'note': note,
                'due_date': None
            }
        
        else:
            return {
                'status': 'unknown',
                'note': status_text + ' ' + note,
                'due_date': None
            }
    
    def format_availability_message(self, availability: Dict) -> str:
        """Formatira poruku o dostupnosti za chatbot"""
        
        if 'error' in availability:
            return f"Žao mi je, nisam uspio provjeriti dostupnost knjige. Pokušajte ponovno."
        
        title = availability['title']
        locations = availability['locations']
        
        if not locations:
            return f"📚 **{title}**\n\nNisam uspio pronaći informacije o dostupnosti. Provjerite katalog: https://katalog.halubajska-zora.hr"
        
        message = f"📚 **{title}**\n\n"
        message += "📍 **Dostupnost po lokacijama:**\n\n"
        
        for loc in locations:
            location_name = loc['location']
            status = loc['status']
            due_date = loc['due_date']
            
            if status == 'available':
                message += f"✅ **{location_name}**\n"
                message += f"   Status: Dostupna\n"
                if loc['note']:
                    message += f"   Napomena: {loc['note']}\n"
            
            elif status == 'borrowed':
                message += f"❌ **{location_name}**\n"
                message += f"   Status: Posuđena"
                if due_date:
                    message += f" do {due_date}"
                message += "\n"
                message += f"   💡 Možete rezervirati knjigu\n"
            
            else:
                message += f"❓ **{location_name}**\n"
                message += f"   Status: {loc['note']}\n"
            
            message += "\n"
        
        message += "🔗 Katalog: https://katalog.halubajska-zora.hr"
        
        return message


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