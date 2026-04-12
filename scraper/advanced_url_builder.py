import json
import urllib.parse
import os
from groq import Groq
from typing import Dict, Any

class AdvancedUrlBuilder:
    def __init__(self, api_key: str):
        self.client = Groq(api_key=api_key)
        self.base_url = "https://katalog.halubajska-zora.hr/pagesResults/rezultati.aspx?&searchById=40"
        
        # Učitavanje specifičnih JSON-ova
        self.languages = self._load_json('scraper/languages.json')
        self.categories = self._load_json('scraper/udk_categories.json')
        self.ages = self._load_json('data/ages.json')
        self.locations = {
            "marinici": "%23179%23281%23Sredi%c5%a1nja+knji%c5%benica+Marini%c4%87i",
            "viskovo": "%23179%23282%23Knji%c5%benica+Vi%c5%a1kovo"
        }
        self.statuses = {
            "marinici": "%23L281%23za+posudbu",
            "viskovo": "%23L282%23za+posudbu"
        }

        # Fiksni FID-ovi iz kataloga
        self.fid_map = {
            "autor": 1, 
            "gradja": 2,
            "godina": 3,
            "jezik": 5, 
            "uzrast": 11,
            "lokacija_pripadnost": 12, 
            "status_dostupnost": 13,  
            "sadrzaj": 14          
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
        lang_list = list(self.languages.keys())
        cat_list = list(self.categories.keys())
        age_list = list(self.ages.keys())

        system_prompt = f"""
        Ti si knjižnični analitičar. Pretvori korisnički upit u JSON filtre.
        
        ### DOSTUPNE VRIJEDNOSTI (ENUM):
        - JEZIK: {lang_list}
        - SADRŽAJ: {cat_list}
        - UZRAST: {age_list}
        - GRAĐA: [knjiga, vizualna građa, igračka, zvučna građa]
        - LOKACIJA: [marinici, viskovo]

        ### LOGIKA MAPIRANJA:
        1. **Lokacije (Sinonimi):**
           - 'marinici' = Središnja, Marinići, Glavna knjižnica, Centar.
           - 'viskovo' = Viškovo, Ogranak, Podružnica.
        2. **Dostupnost (dostupno_odmah):**
           - Postavi na `true` ako korisnik koristi: "slobodno", "za posudbu", "dostupno", "mogu podići", "na polici".
           - Inače postavi na `false`.
        3. **Uzrast (Kontekst):**
           - Bebe/jaslice -> 'mlada_predskolska'
           - Vrtić -> 'predskolska'
           - Školarci (niži) -> 'mlada_skolska'
           - Školarci (viši) -> 'skolska'
           - Tinejdžeri/Srednja škola -> 'mladi_odrasli'
           - Odrasli -> 'odrasli'
        4. **Godina:** - Pretvori tekstualne godine (npr. "devedeset peta") u broj (1995).
           - Ako kaže "novo" ili "zadnje", koristi 2025.

        ### STRIKTNA PRAVILA:
        - Ako korisnik ne spomene specifičan parametar, vrati `null` (ili praznu listu za lokaciju).
        - Ako korisnik traži "obje lokacije" ili "bilo gdje", koristi `["marinici", "viskovo"]`.
        - Ako korisnik traži autora, stavi ga u 'pojam', a ne u 'sadrzaj'.
        - IZLAZ MORA BITI ISKLJUČIVO ČISTI JSON.
        
        ### JSON SHEMA:
        {{
            "pojam": string ili null,
            "jezik": string ili null,
            "sadrzaj": string ili null,
            "uzrast": string ili null,
            "gradja": string ili null,
            "godina": integer ili null,
            "lokacija": array (npr. ["viskovo"]),
            "dostupno_odmah": boolean
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

    def get_year_code(self, year: int) -> str:
        """Automatski generira Metel kod za godinu"""
        # Referentna točka koju smo izvukli: 2025 je 997975
        base_code = 997975
        base_year = 2025
        diff = base_year - year
        target_code = base_code + diff
        return f"{target_code}_{year}"

    def build_url(self, metadata: Dict[str, Any]) -> str:
        """Sklapa finalni URL koristeći ur_param iz tvojih JSON-ova"""
        params = []
        idx = 0

        # Slobodni pojam (Search PV)
        if metadata.get('pojam'):
            params.append(f"spv0={urllib.parse.quote(metadata['pojam'])}")
            params.append(f"spid0=40")

        # Uzrast (fid 11)
        age_key = metadata.get('uzrast')
        if age_key in self.ages:
            # age_params je lista jer mlađa školska ima dva parametra
            age_params = self.ages[age_key].get('params', [])
            for p in age_params:
                params.append(f"fid{idx}={self.fid_map['uzrast']}&fv{idx}={p}")
                idx += 1

        # Jezik (fid 5)
        lang_key = metadata.get('jezik')
        if lang_key in self.languages:
            val = self.languages[lang_key]['url_param']
            params.append(f"fid{idx}={self.fid_map['jezik']}&fv{idx}={val}")
            idx += 1
        
        # Lokacija + status (fid 12 ili 13)
        requested_locs = metadata.get('lokacija') or []
        is_available = metadata.get('dostupno_odmah', False)

        for loc in requested_locs:
            if is_available:
                # Koristi FID 13 (Status: Za posudbu na toj lokaciji)
                val = self.statuses.get(loc)
                fid = self.fid_map["status_dostupnost"]
            else:
                # Koristi FID 12 (Lokacija)
                val = self.locations.get(loc)
                fid = self.fid_map["lokacija_pripadnost"]

            if val:
                params.append(f"fid{idx}={fid}&fv{idx}={val}")
                idx += 1

        # Sadržaj (fid 14)
        cat_key = metadata.get('sadrzaj')
        if cat_key in self.categories:
            val = self.categories[cat_key]['url_param']
            params.append(f"fid{idx}=14&fv{idx}={val}")
            idx += 1

        # Građa (fid 2)
        if metadata.get('gradja'):
            val = urllib.parse.quote(metadata['gradja'])
            params.append(f"fid{idx}={self.fid_map['gradja']}&fv{idx}={val}")
            idx += 1

        # Godina (fid 3)
        requested_year = metadata.get('godina')
        if requested_year:
            # Ako je korisnik tražio "zadnjih 5 godina", LLM će vratiti npr. 2025
            # jer se ne može slati više godina odjednom.
            year_code = self.get_year_code(int(requested_year))
            params.append(f"fid{idx}={self.fid_map['godina']}&fv{idx}={year_code}")
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