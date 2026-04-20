import httpx
from bs4 import BeautifulSoup
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class EventsScraper:
    def __init__(self):
        self.url = "https://www.halubajska-zora.hr/"
        # Dodajemo User-Agent da izgledamo kao pravi Chrome preglednik
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    async def get_events(self, limit: int = 5) -> List[Dict]:
        try:
            async with httpx.AsyncClient(headers=self.headers, follow_redirects=True, timeout=15.0) as client:
                response = await client.get(self.url)
                
                if response.status_code != 200:
                    logger.error(f"Greška kod dohvaćanja: {response.status_code}")
                    return []

                soup = BeautifulSoup(response.text, 'html.parser')
                events = []
                
                # Selektiramo sve elemente koji imaju data-post-id (to su tvoji članci iz HTML-a)
                articles = soup.select('div[data-post-id]')
                
                logger.info(f"Pronađeno potencijalnih artikala: {len(articles)}")

                for article in articles[:limit]:
                    # Naslov i URL
                    title_link = article.select_one('.sc_blogger_item_title a')
                    if not title_link: continue
                    
                    title = title_link.get_text(strip=True)
                    link = title_link.get('href', '')

                    # Datum (iz post_meta dijela)
                    date_elem = article.select_one('.post_date a')
                    date_text = date_elem.get_text(strip=True) if date_elem else "Nepoznat datum"

                    # Sažetak (excerpt)
                    excerpt_elem = article.select_one('.sc_blogger_item_excerpt')
                    excerpt = excerpt_elem.get_text(strip=True) if excerpt_elem else ""

                    events.append({
                        'title': title,
                        'url': link,
                        'date_text': date_text,
                        'excerpt': excerpt
                    })

                return events

        except Exception as e:
            logger.error(f"❌ Scraper Error: {e}")
            return []

# --- TEST SKRIPTA ---
if __name__ == "__main__":
    import asyncio
    
    async def run_test():
        scraper = EventsScraper()
        print(f"Skeniram: {scraper.url} ...")
        rezultati = await scraper.get_events(limit=3)
        
        if not rezultati:
            print("Nema rezultata. Možda stranica blokira direktan pristup?")
        else:
            for i, ev in enumerate(rezultati, 1):
                print(f"\n{i}. {ev['title']}")
                print(f"   Datum: {ev['date_text']}")
                print(f"   Link:  {ev['url']}")
                print(f"   Opis:  {ev['excerpt'][:100]}...")

    asyncio.run(run_test())