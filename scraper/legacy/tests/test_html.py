"""
Test script za analizu HTML strukture
"""

import requests
from bs4 import BeautifulSoup

url = "https://katalog.halubajska-zora.hr/pagesResults/rezultati.aspx?new=365"

response = requests.get(url)
soup = BeautifulSoup(response.content, 'html.parser')

# Pronađi sve div-ove koji sadrže knjige
print("Tražim strukturu knjiga...\n")

# Pokušaj 1: Pronađi sve img sa "vrsteGradje"
images = soup.find_all('img', src=lambda x: x and 'vrsteGradje' in x)
print(f"Pronađeno slika knjiga: {len(images)}\n")

# Pokušaj 2: Pronađi linkove
links = soup.find_all('a', href=lambda x: x and 'bibliografskiZapis' in x)
print(f"Pronađeno linkova: {len(links)}\n")

# Ispiši prvi link da vidimo strukturu
if links:
    first_link = links[0]
    print("PRVI LINK - STRUKTURA:")
    print(f"Tag: {first_link.name}")
    print(f"Href: {first_link.get('href')}")
    print(f"Title: {first_link.get('title')}")
    print(f"Text: {first_link.get_text(strip=True)}")
    print(f"\nParent tag: {first_link.parent.name}")
    
    # Pokušaj naći img unutar ili pored linka
    img = first_link.find('img')
    if img:
        print(f"Img alt: {img.get('alt')}")
    
    print("\n" + "="*50)
    print("HTML prvog linka:")
    print(first_link.prettify())