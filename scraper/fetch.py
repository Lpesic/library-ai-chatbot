"""
Dohvati STVARNE UDK kategorije sa stranice kataloga
"""

import httpx
from bs4 import BeautifulSoup
import json
import re
import os

def fetch_udk_categories():
    """Dohvati sve UDK kategorije sa katalog stranice"""
    
    url = "https://katalog.halubajska-zora.hr/pagesMisc/Katalog.aspx"
    
    print(f"Dohvaćam UDK kategorije sa: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    response = httpx.get(url, timeout=30.0, follow_redirects=True, headers=headers, verify=False)
    print(f"Status: {response.status_code}")
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Pronađi sve linkove sa fid0=14
    links_with_fid14 = soup.find_all('a', href=re.compile('fid0=14'))
    print(f"Pronađeno {len(links_with_fid14)} UDK kategorija\n")
    
    categories = {}
    
    # Aliasi - kratki nazivi za duge kategorije
    aliases = {
        'sport': 'sport...na vodi...u zraku. konjički sport. sportski ribolov',
        'konjicki sport': 'sport...na vodi...u zraku. konjički sport. sportski ribolov',
        'ribolov': 'sport...na vodi...u zraku. konjički sport. sportski ribolov',
        'crtanje': 'crtanje. oblikovanje. primijenjena umjetnost, umjetnički obrt',
        'dizajn': 'crtanje. oblikovanje. primijenjena umjetnost, umjetnički obrt',
        'primijenjena umjetnost': 'crtanje. oblikovanje. primijenjena umjetnost, umjetnički obrt',
        'enciklopedije': 'enciklopedije. leksikoni. priručnici',
        'leksikoni': 'enciklopedije. leksikoni. priručnici',
        'prirucnici': 'enciklopedije. leksikoni. priručnici',
        'priručnici': 'enciklopedije. leksikoni. priručnici',
        'opca povijest': 'opća povijest',
        'opća povijest': 'opća povijest',
        'biografije': 'biografske i srodne studije',
        'udruge': 'organizacije i druge vrste suradnje',
        'organizacije': 'organizacije i druge vrste suradnje',
        'paleontologija': 'paleontologija',
        'kiparstvo': 'kiparstvo i srodne umjetnost',
        'novinarstvo': 'novine i novinarstvo',
        'novine': 'novine i novinarstvo',
        'grafika': 'grafička. umjetnost. grafika',
        'graficka umjetnost': 'grafička. umjetnost. grafika',
        'metafizika': 'pojedine grane metafizike',
        'logika': 'logika.epistemologija. spoznajna torija. logička metodologija',
        'epistemologija': 'logika.epistemologija. spoznajna torija. logička metodologija',
        'gradjevina': 'građevinski radovi',
        'građevina': 'građevinski radovi',
        'mehanika': 'mehanička tehnologija općenito',
        'duhovnost': 'suvremeni duhovni pokreti',
        'glazba': 'glazba općenito',        
        'filozofija': 'filozofija uma i filozofija duha',  
        'muzika': 'glazba općenito',
        'etika': 'moralna filozofija. etika. praktična filozofija',
    }
    
    for link in links_with_fid14:
        href = link.get('href', '')
        display_name = link.get_text(strip=True)
        
        if not display_name or not href:
            continue
        
        # Izvuci fv0 parametar
        fv0_match = re.search(r'fv0=(.+?)(?:&currentPage=\d+|&amp;currentPage=\d+|$)', href)
        if not fv0_match:
            continue
    
        url_param = fv0_match.group(1).strip()
        url_param = url_param.rstrip('&').rstrip()
        
        # UKLONI currentPage na kraju!
        url_param = re.sub(r'¤tPage=\d+$', '', url_param)
        url_param = re.sub(r'&currentPage=\d+$', '', url_param)
        url_param = url_param.rstrip('&')
        
        parent = link.find_parent('div', class_='fasetaWrap')
        count = 0
        if parent:
            count_div = parent.find('div', class_='spnFasetaBrojZapisa')
            if count_div:
                count_text = count_div.get_text(strip=True)
                count = int(count_text.replace('.', '').replace(',', ''))

        # Kreiraj ključ (lowercase)
        key = display_name.lower().strip()
        
        # Bez dijakritika
        key_ascii = (key
            .replace('š', 's').replace('č', 'c').replace('ć', 'c')
            .replace('ž', 'z').replace('đ', 'd')
        )
        
        entry = {
            'url_param': url_param,
            'display_name': display_name,
            'count': count
        }
        
        categories[key] = entry
        
        # Dodaj ASCII verziju ako je drugačija
        if key_ascii != key:
            categories[key_ascii] = entry
        
        print(f"  ✓ '{key}': {url_param[:60]}")
    
    # Dodaj aliase
    print("\n--- Dodajem aliase ---")
    for alias, target_key in aliases.items():
        if target_key in categories:
            categories[alias] = categories[target_key]
            print(f"  ✓ '{alias}' → '{target_key}'")
        else:
            print(f"  ✗ Target '{target_key}' ne postoji")
    
    print(f"\nUkupno: {len(categories)} kategorija (sa aliasima)")
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

def fetch_languages():
    """Dohvati sve jezike sa katalog stranice"""
    
    url = "https://katalog.halubajska-zora.hr/pagesMisc/Katalog.aspx"  
    print(f"\nDohvaćam jezike sa: {url}") 
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'} 
    response = httpx.get(url, timeout=30.0, follow_redirects=True, headers=headers, verify=False)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Pronađi sve linkove sa fid0=5 (jezik)
    links_with_fid5 = soup.find_all('a', href=re.compile('fid0=5'))
    print(f"Pronađeno {len(links_with_fid5)} jezika\n")
    
    languages = {}
    
    # Aliasi
    aliases = {
        'njemacki': 'njemački',
        'spanjolski': 'španjolski',
        'spanjolskom': 'španjolski',
        'slavenski': 'slovenski',
        'ceski': 'češki',
        'madjarski': 'mađarski',
        'engleski': 'engleski',
        'english': 'engleski',
        'njemacki': 'njemački',
        'german': 'njemački',
        'talijanski': 'talijanski',
        'italian': 'talijanski',
        'francuski': 'francuski',
        'french': 'francuski',
        'spanjolski': 'španjolski',
        'spanish': 'španjolski',
        'grcki': 'grčki',
        'greek': 'grčki',
        'latin': 'latinski',
        'bosanski': 'bosanski',
        'srpski': 'srpski',
        'hrvatski': 'hrvatski',
        'croatian': 'hrvatski',
        'serbian': 'srpski',
        'bosnian': 'bosanski',
        'slavenski': 'slovenski',
        'slovene': 'slovenski',
        'crnogorski': 'crnogorski',
        'makedonski': 'makedonski',
        'ruski': 'ruski',
        'russian': 'ruski',
        'kineski': 'kineski',
        'chinese': 'kineski',
        'japanski': 'japanski',
        'japanese': 'japanski',
    }
    
    for link in links_with_fid5:
        href = link.get('href', '')
        display_name = link.get_text(strip=True)  
        if not display_name or not href:
            continue
        
        #print(f"DEBUG href: {href[:100]}")
        fv0_match = re.search(r'fv0=(.+?)(?:&currentPage=\d+|&amp;currentPage=\d+|$)', href)
        if not fv0_match:
            continue
        
        url_param = fv0_match.group(1).strip()
        if '¤' in url_param:
            url_param = url_param.split('¤')[0]

        url_param = url_param.rstrip('&').rstrip()

        # Broj zapisa
        parent = link.find_parent('div', class_='fasetaWrap')
        count = 0
        if parent:
            count_div = parent.find('div', class_='spnFasetaBrojZapisa')
            if count_div:
                count_text = count_div.get_text(strip=True)
                count = int(count_text.replace('.', '').replace(',', ''))
        
        # Kreiraj ključ
        key = display_name.lower().strip()
        key_ascii = (key
            .replace('š', 's').replace('č', 'c').replace('ć', 'c')
            .replace('ž', 'z').replace('đ', 'd')
        )
        
        entry = {
            'url_param': url_param,
            'display_name': display_name,
            'count': count
        }
        
        languages[key] = entry
        if key_ascii != key:
            languages[key_ascii] = entry
        
        print(f"  ✓ '{key}' ({count}): {url_param}")
    
    # Dodaj aliase
    print("\n--- Dodajem jezične aliase ---")
    for alias, target_key in aliases.items():
        if target_key in languages:
            languages[alias] = languages[target_key]
            print(f"  ✓ '{alias}' → '{target_key}'")
    
    print(f"\nUkupno: {len(languages)} jezika (sa aliasima)")
    return languages

def save_languages(languages):
    """Spremi jezike u JSON"""
    output_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'languages.json')
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(languages, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ Spremljeno u: {output_file}")

if __name__ == "__main__":
    print("=" * 70)
    print("UDK CATEGORIES FETCHER")
    print("=" * 70)
    
    categories = fetch_udk_categories()
    
    if categories:
        save_categories(categories)
        
        print("\n--- TEST ALIASA ---")
        test_keys = ['sport', 'psihologija', 'povijest', 'glazba', 'filozofija', 'medicina']
        
        for key in test_keys:
            if key in categories:
                print(f"  ✓ '{key}': {categories[key]['display_name']}")
            else:
                print(f"  ✗ '{key}' - NIJE pronađen!")

    languages = fetch_languages()
    if languages:
        save_languages(languages)
    