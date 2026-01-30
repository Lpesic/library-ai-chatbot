"""
Parser za detaljne informacije o knjizi
"""

import requests
from bs4 import BeautifulSoup
import re
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class BookDetailParser:
    """Parser za detaljnu stranicu knjige"""
    
    def __init__(self, base_url: str = "https://katalog.halubajska-zora.hr"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        })
    
    def parse_book_detail(self, book_id: str) -> Dict:
        """Parsira sve detalje o knjizi"""
        try:
            url = f"{self.base_url}/pagesResults/bibliografskiZapis.aspx?selectedId={book_id}"
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            book_data = {
                'id': book_id,
                'url': url,
                'title': self._extract_title(soup),
                'author': self._extract_author(soup),
                'other_authors': self._extract_other_authors(soup),
                'publisher': self._extract_publisher(soup),
                'year': self._extract_year(soup),
                'pages': self._extract_pages(soup),
                'isbn': self._extract_isbn(soup),
                'language': self._extract_language(soup),
                'subjects': self._extract_subjects(soup),
                'classifications': self._extract_classifications(soup),
                'tags': self._extract_tags(soup),
                'material_type': self._extract_material_type(soup),
                'notes': self._extract_notes(soup)
            }
            
            logger.info(f"Uspješno parsirano: {book_data['title']}")
            return book_data
            
        except Exception as e:
            logger.error(f"Greška pri parsiranju knjige {book_id}: {e}")
            return {'id': book_id, 'error': str(e)}
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Izvlači naslov knjige"""
        title_span = soup.find('span', {'itemprop': 'name'})
        if title_span:
            return title_span.get_text(strip=True)
        
        # Fallback - iz div-a
        title_div = soup.find('div', {'id': 'divNaslov'})
        if title_div:
            title_span = title_div.find('span', class_='hidden')
            if title_span:
                return title_span.get_text(strip=True)
        
        return "N/A"
    
    def _extract_author(self, soup: BeautifulSoup) -> str:
        """Izvlači glavnog autora"""
        rows = soup.find_all('div', class_='row')
        for row in rows:
            label = row.find('div', class_='tdBibliografskiZapisNaziv')
            if label and 'Autor' == label.get_text(strip=True):
                value_div = row.find('div', class_='tdCellValue')
                if value_div:
                    author_link = value_div.find('a', class_='aBibZapisAutor')
                    if author_link:
                        return author_link.get_text(strip=True)
        return "N/A"
    
    def _extract_other_authors(self, soup: BeautifulSoup) -> List[str]:
        """Izvlači ostale autore (prevoditelji, ilustratori...)"""
        authors = []
        rows = soup.find_all('div', class_='row')
        
        for row in rows:
            label = row.find('div', class_='tdBibliografskiZapisNaziv')
            if label and 'Ostali autori' == label.get_text(strip=True):
                value_div = row.find('div', class_='tdCellValue')
                if value_div:
                    author_link = value_div.find('a', class_='aBibZapisAutor')
                    role_text = value_div.get_text()
                    
                    # Izvuci autora i ulogu
                    if author_link:
                        author_name = author_link.get_text(strip=True)
                        # Traži ulogu u zagradama
                        role_match = re.search(r'\[(.*?)\]', role_text)
                        role = role_match.group(1) if role_match else "contributor"
                        authors.append(f"{author_name} ({role})")
        
        return authors
    
    def _extract_publisher(self, soup: BeautifulSoup) -> str:
        """Izvlači nakladnika"""
        rows = soup.find_all('div', class_='row')
        for row in rows:
            label = row.find('div', class_='tdBibliografskiZapisNaziv')
            if label and 'Nakladnik' in label.get_text():
                value_div = row.find('div', class_='tdCellValue')
                if value_div:
                    publisher_span = value_div.find('span', itemprop='name')
                    if publisher_span:
                        return publisher_span.get_text(strip=True)
        return "N/A"
    
    def _extract_year(self, soup: BeautifulSoup) -> str:
        """Izvlači godinu izdanja"""
        rows = soup.find_all('div', class_='row')
        for row in rows:
            label = row.find('div', class_='tdBibliografskiZapisNaziv')
            if label and 'Nakladnik' in label.get_text():
                value_div = row.find('div', class_='tdCellValue')
                if value_div:
                    text = value_div.get_text()
                    # Traži 4-znamenkastu godinu
                    year_match = re.search(r'\b(19|20)\d{2}\b', text)
                    if year_match:
                        return year_match.group(0)
        return "N/A"
    
    def _extract_pages(self, soup: BeautifulSoup) -> str:
        """Izvlači broj stranica"""
        rows = soup.find_all('div', class_='row')
        for row in rows:
            label = row.find('div', class_='tdBibliografskiZapisNaziv')
            if label and 'Materijalni opis' in label.get_text():
                value_div = row.find('div', class_='tdCellValue')
                if value_div:
                    text = value_div.get_text(strip=True)
                    # Izvuci broj stranica (npr. "352 str.")
                    pages_match = re.search(r'(\d+)\s*str', text)
                    if pages_match:
                        return pages_match.group(1)
        return "N/A"
    
    def _extract_isbn(self, soup: BeautifulSoup) -> str:
        """Izvlači ISBN"""
        isbn_span = soup.find('span', itemprop='isbn')
        if isbn_span:
            return isbn_span.get_text(strip=True)
        return "N/A"
    
    def _extract_language(self, soup: BeautifulSoup) -> str:
        """Izvlači jezik"""
        rows = soup.find_all('div', class_='row')
        for row in rows:
            label = row.find('div', class_='tdBibliografskiZapisNaziv')
            if label and 'Jezik' == label.get_text(strip=True):
                value_div = row.find('div', class_='tdCellValue')
                if value_div:
                    return value_div.get_text(strip=True)
        return "N/A"
    
    def _extract_subjects(self, soup: BeautifulSoup) -> List[str]:
        """Izvlači predmetne odrednice"""
        subjects = []
        rows = soup.find_all('div', class_='row')
        
        collecting = False
        for row in rows:
            label = row.find('div', class_='tdBibliografskiZapisNaziv')
            
            # Započni skupljanje kod "Predmetna odrednica"
            if label and 'Predmetna odrednica' in label.get_text():
                collecting = True
            
            # Prestani kod sljedećeg naziva
            if collecting and label and label.get_text(strip=True) and 'Predmetna odrednica' not in label.get_text():
                if label.get_text(strip=True) not in ['']:
                    break
            
            if collecting:
                value_div = row.find('div', class_='tdCellValue')
                if value_div:
                    subject_link = value_div.find('a')
                    if subject_link:
                        subjects.append(subject_link.get_text(strip=True))
        
        return subjects
    
    def _extract_classifications(self, soup: BeautifulSoup) -> List[Dict]:
        """Izvlači klasifikacijske oznake"""
        classifications = []
        rows = soup.find_all('div', class_='row')
        
        for row in rows:
            label = row.find('div', class_='tdBibliografskiZapisNaziv')
            if label and 'Klasifikacijska oznaka' in label.get_text():
                value_div = row.find('div', class_='tdCellValue')
                if value_div:
                    code_link = value_div.find('a')
                    if code_link:
                        code = code_link.get_text(strip=True)
                        # Opis je ostatak teksta nakon linka
                        description = value_div.get_text()
                        description = description.replace(code, '').strip()
                        classifications.append({
                            'code': code,
                            'description': description
                        })
        
        return classifications
    
    def _extract_tags(self, soup: BeautifulSoup) -> List[str]:
        """Izvlači tagove"""
        tags = []
        tag_div = soup.find('div', id='divOznakeTagoviTab')
        if tag_div:
            tag_links = tag_div.find_all('a')
            for tag_link in tag_links:
                tags.append(tag_link.get_text(strip=True))
        return tags
    
    def _extract_material_type(self, soup: BeautifulSoup) -> str:
        """Izvlači tip građe"""
        rows = soup.find_all('div', class_='row')
        for row in rows:
            label = row.find('div', class_='tdBibliografskiZapisNaziv')
            if label and 'Građa' == label.get_text(strip=True):
                value_div = row.find('div', class_='tdCellValue')
                if value_div:
                    return value_div.get_text(strip=True).replace('\n', ' ').strip()
        return "N/A"
    
    def _extract_notes(self, soup: BeautifulSoup) -> List[str]:
        """Izvlači napomene"""
        notes = []
        rows = soup.find_all('div', class_='row')
        for row in rows:
            label = row.find('div', class_='tdBibliografskiZapisNaziv')
            if label and 'Napomena' in label.get_text():
                value_div = row.find('div', class_='tdCellValue')
                if value_div:
                    notes.append(value_div.get_text(strip=True))
        return notes


# Test
if __name__ == "__main__":
    parser = BookDetailParser()
    
    # Test sa prvom knjigom
    book_id = "164001707"
    print(f"Parsiram knjigu ID: {book_id}\n")
    
    book_data = parser.parse_book_detail(book_id)
    
    print("=" * 70)
    print("REZULTATI PARSIRANJA:")
    print("=" * 70)
    for key, value in book_data.items():
        if isinstance(value, list):
            print(f"\n{key.upper()}:")
            for item in value:
                print(f"  - {item}")
        else:
            print(f"{key}: {value}")