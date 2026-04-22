import httpx
from bs4 import BeautifulSoup
import logging
import asyncio
import urllib.parse
from typing import Dict, List
import re

logger = logging.getLogger(__name__)

class FastAvailabilityChecker:
    """Brza provjera dostupnosti koristeći direktne URL filtere (bez ScraperAPI-ja)"""
    
    def __init__(self):
        self.base_url = "https://katalog.halubajska-zora.hr/pagesResults/rezultati.aspx"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }

    async def check_availability(self, book_title: str) -> Dict:
        try:
            logger.info(f"🔍 Ultra-brza provjera (paralelno): '{book_title}'")
            
            # POKRETANJE OBA UPITA ISTOVREMENO
            # Ovo prepolovljuje vrijeme čekanja
            tasks = [
                self._check_location(book_title, 'marinici'),
                self._check_location(book_title, 'viskovo')
            ]
            
            results = await asyncio.gather(*tasks)
            available_marinici, available_viskovo = results
            
            return self._format_result(book_title, available_marinici, available_viskovo)
        
        except Exception as e:
            logger.error(f"❌ Greška u FastAvailability: {e}")
            return {
                'found': False,
                'title': book_title,
                'message': f"Greška pri provjeri: {str(e)}"
            }

    async def _check_location(self, book_title: str, location: str) -> Dict:
        """
        Provjerava lokaciju i vraća detaljan status:
        - Što sve postoji (bez filtera)
        - Što je od toga dostupno (s filterom)
        """
        import re
        search_query = book_title.lower().strip()
        encoded_title = urllib.parse.quote(book_title)
        
        location_filters = {
            'marinici': '%23L281%23za+posudbu',
            'viskovo': '%23L282%23za+posudbu'
        }
        
        # URL-ovi
        url_all = f"{self.base_url}?searchById=1&spid0=1&spv0={encoded_title}"
        url_available = f"{url_all}&fid0=13&fv0={location_filters[location]}"

        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=10.0) as client:
                # 1. Prvo tražimo SVE što postoji pod tim imenom
                res_all = await client.get(url_all)
                soup_all = BeautifulSoup(res_all.text, 'html.parser')
                all_books = []
                for r in soup_all.select('.divBibZapis'):
                    t = r.select_one('.bibZapisOpis').get_text(" ", strip=True).split('/')[0].strip()
                    # Zadržavamo samo one koji su stvarno match (izbacujemo Westaway i slično)
                    if all(word in re.sub(r'[^\w\s]', ' ', t.lower()).split() for word in search_query.split()):
                        all_books.append(t)

                # 2. Zatim tražimo što je DOSTUPNO
                res_avail = await client.get(url_available)
                soup_avail = BeautifulSoup(res_avail.text, 'html.parser')
                available_books = []
                for r in soup_avail.select('.divBibZapis'):
                    t = r.select_one('.bibZapisOpis').get_text(" ", strip=True).split('/')[0].strip()
                    if all(word in re.sub(r'[^\w\s]', ' ', t.lower()).split() for word in search_query.split()):
                        available_books.append(t)

                return {
                    'existing': list(set(all_books)),
                    'available': list(set(available_books))
                }
        except Exception:
            return {'existing': [], 'available': []}

    def _format_result(self, book_query: str, marinici_res: Dict, viskovo_res: Dict) -> Dict:
        # Skupljamo sve naslove koji uopće postoje u bazi na obje lokacije
        svi_postojeći = list(set(marinici_res['existing'] + viskovo_res['existing']))
        svi_dostupni = list(set(marinici_res['available'] + viskovo_res['available']))
        
        clean_query = book_query.lower().strip()
        final_messages = []

        # Prolazimo kroz svaki naslov koji smo našli u bazi
        for naslov in svi_postojeći:
            lokacije = []
            if naslov in marinici_res['available']: lokacije.append("Marinići")
            if naslov in viskovo_res['available']: lokacije.append("Viškovo")

            if lokacije:
                final_messages.append(f"✅ '{naslov}' je dostupna ({' i '.join(lokacije)}).")
            else:
                # Ako naslov postoji u 'svi_postojeći' ali nije u 'available' listama
                final_messages.append(f"❌ '{naslov}' je trenutno posuđena.")

        if not final_messages:
            msg = f"❌ Pod upitom '{book_query}' nije pronađena nijedna knjiga."
        else:
            msg = "\n".join(final_messages)

        return {'message': msg}

if __name__ == "__main__":
    async def test():
        checker = FastAvailabilityChecker()
        # Testiramo točan match, posuđenu knjigu sa sličnim rezultatima i dugačak naslov
        test_books = ["Iz Vedra neba", "Vučji sat", "zov divljaštva"]
        
        for book in test_books:
            print(f"\n📚 Testiram: {book}")
            result = await checker.check_availability(book)
            print(f"💬 {result['message']}")

    async def main():
        await test()

    asyncio.run(main())