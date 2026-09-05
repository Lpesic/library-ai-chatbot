import asyncio
import json
import urllib.parse
import os
from typing import Dict, Any
from openai import AsyncOpenAI

class AdvancedUrlBuilder:
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(
            api_key=api_key, 
            base_url="https://api.sambanova.ai/v1"
        )
        self.base_url = "https://katalog.halubajska-zora.hr/pagesResults/rezultati.aspx?&searchById=1"
        
        # Učitavanje specifičnih JSON-ova
        self.languages = self._load_json('data/languages.json')
        self.categories = self._load_json('data/udk_categories.json')
        self.media_data = self._load_json('data/media_types.json')
        
        self.media_types = self.media_data.get('types', {})
        self.media_aliases = self.media_data.get('aliases', {})

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
            "opca_pretraga": 1,
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
            print(f"Greška pri učitavanju {path}: {e}", flush=True)
            return {}

    async def analyze_query(self, user_query: str) -> Dict[str, Any]:
        """Sambanova ekstrakcija keyworda i mapa prema JSON ključevima"""
        
        # Priprema opcija za AI da zna što točno smije odabrati
        lang_list = list(self.languages.keys())
        cat_list = list(self.categories.keys())
        age_list = list(self.ages.keys())
        media_list = list(self.media_types.keys())

        system_prompt = f"""
        Ti si knjižnični analitičar. Pretvori korisnički upit u JSON filtre.
        
        ### DOSTUPNE VRIJEDNOSTI (ENUM):
        - JEZIK: {lang_list}
        - SADRŽAJ: {cat_list}
        - UZRAST: {age_list}
        - GRAĐA: {media_list}
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
            - Ako kaže "novo" ili "zadnje", koristi 2026.
        5. **Građa:**
            - "film" ili "DVD" -> 'vizualna_gradja'
            - "CD" ili "glazba" -> koristi 'glazba'
            - "zvučna knjiga" ili "audio knjiga" -> 'zvucna_knjiga'
            - "novine" ili "časopis" -> 'periodika'
            - "atlas" ili "mapa" -> 'karte'
        6. **Top liste (Najčitanije):**
            - Dozvoljeni brojevi su ISKLJUČIVO: [7, 30, 90, 180, 365].
            - Ako korisnik kaže "zadnjih 10 dana", mapiraj na najblži (7).
            - Ako kaže "zadnja dva mjeseca", mapiraj na (90) ili (30).
            - "najčitanije", "popularno", "hitovi" -> koristi `top` parametar.
            - "tjedan" -> 7, "mjesec" -> 30, "tromjesečje" -> 90, "pola godine" -> 180, "godina" -> 365.
            
        7. **Sortiranje (sort):**
            - "po autoru", "abecedno pisci", "poredaj autore" -> `sort` na 1.
            - "po naslovu", "abecedno knjige", "poredaj po imenu" -> `sort` na 2.
            - Ako se traži "knjige iz 2024" ili "novo izdanje" -> postavi `godina` na 2024/2026, a `sort` ostavi null.
            - Ako se traži "pokaži najnovije", "što je tek stiglo", "sortiraj po novom" -> `sort` na 3, a `godina` ostavi null.
            - Ako kaže samo "novo", prioritet je `sort: 3` jer korisnici obično žele vidjeti zadnje obrađene knjige, a ne nužno samo one izdane ove godine.
            - Ako je u kombinaciji s `top` (najčitanije), zanemari ovo i koristi logiku za popularnost.

        ### STRIKTNA PRAVILA:
        - Ako korisnik ne spomene specifičan parametar, vrati `null` (ili praznu listu za lokaciju).
        - Ako korisnik traži "obje lokacije" ili "bilo gdje", koristi `["marinici", "viskovo"]`.
        - Ako korisnik traži autora, stavi puno ime u 'pojam', a ne u 'sadrzaj'.
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
            "dostupno_odmah": boolean,
            "top": integer ili null,
            "sort": integer ou null
        }}
        """
        
        response = await self.client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            model="Meta-Llama-3.3-70B-Instruct",
            temperature=0,
            response_format={"type": "json_object"}
        )
        metadata = json.loads(response.choices[0].message.content)
        # --- test print ---
        print("\n" + "═"*50)
        print("🤖 BOT JE SHVATIO:", flush=True)
        for k, v in metadata.items():
            if v is not None and v != [] and v != False:
                print(f"   ➤ {k.upper()}: {v}", flush=True)
        print("═"*50 + "\n", flush=True)
        # ---
        return metadata

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
            params.append(f"spid0=1")

        top_val = metadata.get('top')
        requested_sort = metadata.get('sort')
        allowed_tops = [7, 30, 90, 180, 365]
        if top_val:
            if top_val not in allowed_tops:
                top_val = min(allowed_tops, key=lambda x: abs(x - top_val))

            params.append(f"top={top_val}")
            params.append("sort=4") # Sortiraj po popularnosti

        elif requested_sort in [1, 2, 3]:
            params.append(f"sort={requested_sort}")

        else:
            # Default sortiranje
            params.append("sort=0")

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
        media_key = metadata.get('gradja')
        if media_key in self.media_aliases:
            media_key = self.media_aliases[media_key]
        if media_key in self.media_types:
            val = self.media_types[media_key]
            params.append(f"fid{idx}={self.fid_map['gradja']}&fv{idx}={val}")
            idx += 1

        # Godina (fid 3)
        requested_year = metadata.get('godina')
        if requested_year and requested_sort != 3:
            # Ako je korisnik tražio "zadnjih 5 godina", LLM će vratiti npr. 2025
            # jer se ne može slati više godina odjednom.
            year_code = self.get_year_code(int(requested_year))
            params.append(f"fid{idx}={self.fid_map['godina']}&fv{idx}={year_code}")
            idx += 1

        return f"{self.base_url}&{'&'.join(params)}"

async def test_console():
    """Konzolni test za provjeru rada"""
    api_key = os.getenv("SAMBANOVA_KEY")
    if not api_key:
        print("Postavi SAMBANOVA_KEY u env varijable!", flush=True)
        return

    builder = AdvancedUrlBuilder(api_key)
    
    print("\n--- LIBRARY URL BUILDER TEST ---")
    
    while True:
        query = input("\nUnesi upit (ili 'exit' za kraj): ")
        if query.lower() == 'exit': break
        
        try:
            # 1. Analiza
            metadata = await builder.analyze_query(query)
            
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
    asyncio.run(test_console())