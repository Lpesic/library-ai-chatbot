import json
import urllib.parse
import os
from groq import Groq
from typing import Dict, Any

class AdvancedUrlBuilder:
    def __init__(self, api_key: str):
        self.client = Groq(api_key=api_key)
        self.base_url = "https://katalog.halubajska-zora.hr/pagesResults/rezultati.aspx?&searchById=40"
        
        # Učitavanje tvojih specifičnih JSON-ova
        self.languages = self._load_json('scraper/languages.json')
        self.categories = self._load_json('scraper/udk_categories.json')
        
        # Fiksni FID-ovi iz kataloga
        self.fid_map = {
            "sadrzaj": 14,
            "jezik": 5,
            "gradja": 2,
            "status": 13,
            "uzrast": 11,
            "autor": 1
        }

    def _load_json(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Greška pri učitavanju {path}: {e}")
            return {}

    def analyze_query(self, user_query: str) -> Dict[str, Any]:
        """Groq ekstrakcija keyworda i mapa prema tvojim JSON ključevima"""
        
        # Priprema opcija za AI da zna što točno smije odabrati
        lang_options = list(self.languages.keys())
        cat_options = list(self.categories.keys())

        system_prompt = f"""
        Ti si knjižnični analitičar. Pretvori korisnički upit u JSON filtre.
        
        DOSTUPNI JEZICI: {lang_options}
        DOSTUPNE KATEGORIJE: {cat_options}
        VRSTE GRAĐE: [knjiga, vizualna građa, igračka, zvučna građa]
        
        Pravila:
        1. 'pojam' je slobodni tekst (npr. ime autora ili naslov).
        2. 'status' postavi na 'za posudbu' ako korisnik želi nešto što je slobodno.
        3. 'jezik' i 'sadrzaj' MORAJU biti točni ključevi iz gore navedenih lista.
        
        Izlaz mora biti isključivo JSON:
        {{
            "pojam": string ili null,
            "jezik": string ili null,
            "sadrzaj": string ili null,
            "gradja": string ili null,
            "status": string ili null
        }}
        """

        response = self.client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)

    def build_url(self, metadata: Dict[str, Any]) -> str:
        """Sklapa finalni URL koristeći ur_param iz tvojih JSON-ova"""
        params = []
        idx = 0

        # 0. Slobodni pojam (Search PV)
        if metadata.get('pojam'):
            params.append(f"spv0={urllib.parse.quote(metadata['pojam'])}")
            params.append(f"spid0=40")

        # 1. Jezik (fid 5)
        lang_key = metadata.get('jezik')
        if lang_key in self.languages:
            val = self.languages[lang_key]['url_param']
            params.append(f"fid{idx}=5&fv{idx}={val}")
            idx += 1

        # 2. Sadržaj (fid 14)
        cat_key = metadata.get('sadrzaj')
        if cat_key in self.categories:
            val = self.categories[cat_key]['url_param']
            params.append(f"fid{idx}=14&fv{idx}={val}")
            idx += 1

        # 3. Građa (fid 2)
        if metadata.get('gradja'):
            val = urllib.parse.quote(metadata['gradja'])
            params.append(f"fid{idx}=2&fv{idx}={val}")
            idx += 1

        # 4. Status (fid 13)
        if metadata.get('status') == 'za posudbu':
            params.append(f"fid{idx}=13&fv{idx}=%23C179%23za+posudbu")
            idx += 1

        return f"{self.base_url}&{'&'.join(params)}"

def test_console():
    """Konzolni test za provjeru rada"""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("Postavi GROQ_API_KEY u env varijable!")
        return

    builder = AdvancedUrlBuilder(api_key)
    
    print("\n--- LIBRARY URL BUILDER TEST ---")
    
    while True:
        query = input("\nUnesi upit (ili 'exit' za kraj): ")
        if query.lower() == 'exit': break
        
        try:
            # 1. Analiza
            metadata = builder.analyze_query(query)
            
            # 2. Ispis shvaćenog
            print("\n" + "="*40)
            print("BOT JE SHVATIO:")
            for k, v in metadata.items():
                if v: print(f"   {k.upper()}: {v}")
            
            # 3. Generiranje URL-a
            final_url = builder.build_url(metadata)
            print("-" * 40)
            print(f"GENERIRANI URL:\n{final_url}")
            print("="*40)
            
        except Exception as e:
            print(f"Greška: {e}")

if __name__ == "__main__":
    test_console()