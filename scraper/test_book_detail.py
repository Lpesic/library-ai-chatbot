"""
Test za parsiranje detaljne stranice knjige
"""

import requests
from bs4 import BeautifulSoup

# Testirajmo prvu knjigu
book_id = "164001707"
url = f"https://katalog.halubajska-zora.hr/pagesResults/bibliografskiZapis.aspx?selectedId={book_id}"

response = requests.get(url)
soup = BeautifulSoup(response.content, 'html.parser')

print("=" * 70)
print("ANALIZA DETALJNE STRANICE KNJIGE")
print("=" * 70)

# Pokušaj pronaći različite elemente
print("\n1. Tražim naslov...")
title_element = soup.find('h1')
if title_element:
    print(f"Naslov: {title_element.get_text(strip=True)}")

print("\n2. Tražim autora...")
# Autori su obično u span ili div sa određenom klasom
author_elements = soup.find_all('a', href=lambda x: x and 'autor' in x.lower())
for author in author_elements[:3]:
    print(f"Autor: {author.get_text(strip=True)}")

print("\n3. Tražim ISBN...")
# ISBN je obično u nekoj tablici ili div-u
text = soup.get_text()
import re
isbn_match = re.search(r'ISBN[:\s]+([0-9\-X]+)', text)
if isbn_match:
    print(f"ISBN: {isbn_match.group(1)}")

print("\n4. Tražim dostupnost...")
# Dostupnost - tražimo statusne informacije
status_elements = soup.find_all('span', class_=lambda x: x and 'status' in x.lower() if x else False)
for status in status_elements[:5]:
    print(f"Status: {status.get_text(strip=True)}")

print("\n5. Tražim opis/sažetak...")
# Opis je često u div-u sa klasom description ili summary
desc_elements = soup.find_all(['div', 'p'], class_=lambda x: x and any(word in x.lower() for word in ['opis', 'desc', 'summary', 'sazetak']) if x else False)
for desc in desc_elements[:2]:
    text = desc.get_text(strip=True)
    if len(text) > 50:
        print(f"Opis: {text[:200]}...")

print("\n6. Tražim tablicu s podacima...")
tables = soup.find_all('table')
print(f"Pronađeno tablica: {len(tables)}")
if tables:
    print("\nPrva tablica:")
    for row in tables[0].find_all('tr')[:5]:
        cells = row.find_all(['td', 'th'])
        if len(cells) >= 2:
            label = cells[0].get_text(strip=True)
            value = cells[1].get_text(strip=True)
            print(f"  {label}: {value}")

print("\n" + "=" * 70)
print("Spremam HTML za analizu...")
with open('data/book_detail_sample.html', 'w', encoding='utf-8') as f:
    f.write(soup.prettify())
print("Spremljeno u: data/book_detail_sample.html")
print("=" * 70)