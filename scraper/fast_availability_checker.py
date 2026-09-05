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
        logger.info(f"🔍 Ultra-brza provjera (paralelno): '{book_title}'")
            
        search_query = book_title.lower().strip()
        encoded_title = urllib.parse.quote(book_title)

        url_all = f"{self.base_url}?searchById=1&spid0=1&spv0={encoded_title}"

        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=10.0, verify=False) as client:

                res_all = await client.get(url_all)
                soup_all = BeautifulSoup(res_all.text, 'html.parser')

                all_books = []
                ebooks = []

                # PRIMARNI SEARCH

                for r in soup_all.select('.divBibZapis'):
                    t = r.select_one('.bibZapisOpis').get_text(" ", strip=True).split('/')[0].strip()
                    # Zadržavamo samo one koji su stvarno match
                    if not all(word in re.sub(r'[^\w\s]', ' ', t.lower()).split() for word in search_query.split()):
                        continue
                
                    img_tag = r.select_one('.vrstaGradjeIkona')
                    is_ebook = False
                    
                    if img_tag:
                        src = img_tag.get('src', '').lower()
                        alt = img_tag.get('alt', '').lower()
                        if 'eknjiga' in src or 'e-knjiga' in alt:
                            is_ebook = True
                    
                    if is_ebook:
                            ebooks.append(t)
                    else:
                        all_books.append(t)

                # FALLBACK SEARCH (ako nema rezultata)

                if not all_books and not ebooks:
                    logger.info("Nema rezultata -> pokrećem fallback pretragu")

                    query_variants = self._generate_query_variants(book_title)

                    for variant in query_variants:
                        logger.info(f"Fallback pokušaj: '{variant}'")

                        encoded_variant = urllib.parse.quote(variant)
                        fallback_url = f"{self.base_url}?searchById=1&spid0=1&spv0={encoded_variant}"

                        res_fb = await client.get(fallback_url)
                        soup_fb = BeautifulSoup(res_fb.text, 'html.parser')

                        for r in soup_fb.select('.divBibZapis'):
                            t = r.select_one('.bibZapisOpis').get_text(" ", strip=True).split('/')[0].strip()

                            if variant.lower() in t.lower():
                                img_tag = r.select_one('.vrstaGradjeIkona')
                                is_ebook = False
                                
                                if img_tag:
                                    src = img_tag.get('src', '').lower()
                                    alt = img_tag.get('alt', '').lower()
                                    if 'eknjiga' in src or 'e-knjiga' in alt:
                                        is_ebook = True

                                if is_ebook:
                                    ebooks.append(t)
                                else:
                                    all_books.append(t)

                        if all_books or ebooks:
                            logger.info(f"Fallback uspio s: '{variant}'")
                            break

                # LOKACIJE

                tasks = [
                    self._check_location(book_title, 'marinici', client, search_query, all_books, ebooks, url_all),
                    self._check_location(book_title, 'viskovo', client, search_query, all_books, ebooks, url_all)
                ]
                
                available_marinici, available_viskovo = await asyncio.gather(*tasks)
                
                return self._format_result(book_title, available_marinici, available_viskovo)
        
        except Exception as e:
            logger.error(f"❌ Greška u FastAvailability: {e}")
            return {
                'found': False,
                'title': book_title,
                'message': f"Greška pri provjeri: {str(e)}"
            }

    async def _check_location(self, book_title: str, location: str, client, search_query, all_books, ebooks, url_all) -> Dict:
        """
        Provjerava lokaciju i vraća detaljan status:
        - Što sve postoji (bez filtera)
        - Što je od toga dostupno (s filterom)
        - Ako nađe e-knjigu, onda uvijek stavlja da je dostupna
        """
        
        location_filters = {
            'marinici': '%23L281%23za+posudbu',
            'viskovo': '%23L282%23za+posudbu'
        }
        
        # URL-ovi    
        url_available = f"{url_all}&fid0=13&fv0={location_filters[location]}"

        # tražimo SVE što postoji pod tim imenom 
        # 
        if not all_books and not ebooks:
            return {
                'existing': [],
                'available': [],
                'ebooks': []
            }    
        available_books = []
        if all_books:
            res_avail = await client.get(url_available)
            soup_avail = BeautifulSoup(res_avail.text, 'html.parser') 
            for r in soup_avail.select('.divBibZapis'):
                t = r.select_one('.bibZapisOpis').get_text(" ", strip=True).split('/')[0].strip()
                if all(word in re.sub(r'[^\w\s]', ' ', t.lower()).split() for word in search_query.split()):
                    available_books.append(t)
        
        return {
            'existing': list(set(all_books)),
            'available': list(set(available_books)),
            'ebooks': list(set(ebooks))
        }

    def _format_result(self, book_query: str, marinici_res: Dict, viskovo_res: Dict) -> Dict:
        # Skupljamo sve naslove koji uopće postoje u bazi na obje lokacije
        svi_postojeci = list(set(marinici_res['existing'] + viskovo_res['existing']))
        sve_eknjige = list(set(marinici_res['ebooks'] + viskovo_res['ebooks']))
        svi_postojeci = [n for n in svi_postojeci if n not in sve_eknjige]

        final_messages = []

        for naslov in sve_eknjige:
            final_messages.append(
                f"📱 '{naslov}' je e-knjiga — dostupna za online posudbu u bilo kojem trenutku putem digitalne platforme knjižnice.")

        # Prolazimo kroz svaki naslov koji smo našli u bazi
        for naslov in svi_postojeci:
            lokacije = []
            if naslov in marinici_res['available']: lokacije.append("Marinići")
            if naslov in viskovo_res['available']: lokacije.append("Viškovo")

            if lokacije:
                final_messages.append(f"✅ '{naslov}' je dostupna ({' i '.join(lokacije)}).")
            else:
                # Ako naslov postoji u 'svi_postojeci' ali nije u 'available' listama
                final_messages.append(f"❌ '{naslov}' je trenutno posuđena.")

        if not final_messages:
            msg = f"❌ Pod upitom '{book_query}' nije pronađena nijedna knjiga."
        else:
            msg = "\n".join(final_messages)

        return {'message': msg}
    
    def _generate_query_variants(self, query: str) -> List[str]:
        query = query.lower().strip()
        
        variants = []
        variants.append(query)

        # makni autora nakon "-"
        if "-" in query:
            variants.append(query.split("-")[0].strip())

        # makni zareze
        variants.append(query.replace(",", " "))

        # samo riječi >= 2
        words = query.split()
        if len(words) > 2:
            variants.append(" ".join(words[:2])) 

        return list(dict.fromkeys(variants))

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