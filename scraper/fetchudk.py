"""
Dohvati STVARNE UDK kategorije sa stranice kataloga
"""

import httpx
from bs4 import BeautifulSoup
import json
import re
import os
import urllib.parse

def fetch_udk_categories():
    """Dohvati sve UDK kategorije sa katalog stranice"""
    
    url = "https://katalog.halubajska-zora.hr/pagesMisc/Katalog.aspx"
    
    print(f"Dohvaćam UDK kategorije sa: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    response = httpx.get(url, timeout=30.0, follow_redirects=True, headers=headers)
    print(f"Status: {response.status_code}")
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Pronađi sve linkove sa fid0=14
    links_with_fid14 = soup.find_all('a', href=re.compile('fid0=14'))
    print(f"Pronađeno {len(links_with_fid14)} UDK kategorija\n")
    
    categories = {}
    
    for link in links_with_fid14:
        href = link.get('href', '')
        display_name = link.get_text(strip=True)
        
        if not display_name or not href:
            continue
        
        # Izvuci fv0 parametar
        fv0_match = re.search(r'fv0=([^&]+)', href)
        if not fv0_match:
            continue
        
        url_param = fv0_match.group(1)
        
        # Kreiraj ključ (lowercase)
        key = display_name.lower().strip()
        
        categories[key] = {
            'url_param': url_param,
            'display_name': display_name,
            'count': 0
        }
        
        print(f"  ✓ '{key}': {url_param}")
    
    print(f"\nUkupno: {len(categories)} kategorija")
    return categories

def save_categories(categories):
    """Spremi kategorije u JSON"""
    output_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'udk_categories.json'
    )
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(categories, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ Spremljeno u: {output_file}")

if __name__ == "__main__":
    print("=" * 70)
    print("UDK CATEGORIES FETCHER")
    print("=" * 70)
    
    categories = fetch_udk_categories()
    
    if categories:
        save_categories(categories)
        print("\nPrimjer kategorija:")
        for key in list(categories.keys())[:5]:
            print(f"  '{key}': {categories[key]}")
    else:
        print("❌ Nema kategorija!")