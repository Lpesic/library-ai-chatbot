"""
FAQ - Često postavljana pitanja o knjižnici
"""

FAQ_DATA = [
    {
        "question": "Kako se učlaniti u knjižnicu?",
        "answer": "Za učlanjenje u Narodnu knjižnicu Halubajska Zora potrebna vam je osobna iskaznica i ispunjena pristupnica. Članarina se plaća godišnje, a cijena ovisi o kategoriji (djeca, studenti, odrasli, umirovljenici).",
        "keywords": ["učlanjenje", "članarina", "pristupnica", "iskaznica", "upis"]
    },
    {
        "question": "Koliko knjiga mogu posuditi odjednom?",
        "answer": "Članovi mogu posuditi do 4 knjige istovremeno. Rok posudbe je 30 dana, s mogućnošću produženja ako knjiga nije rezervirana.",
        "keywords": ["posudba", "broj knjiga", "koliko", "limit", "4 knjige"]
    },
    {
        "question": "Kako mogu produžiti posudbu?",
        "answer": "Posudbu možete produžiti online putem sustava 'Moja iskaznica', telefonski ili osobno u knjižnici. Produženje je moguće ako knjiga nije rezervirana od strane drugog člana.",
        "keywords": ["produženje", "produži", "rok", "vratiti"]
    },
    {
        "question": "Što ako kasnim s vraćanjem knjige?",
        "answer": "Za svaki dan kašnjenja naplaćuje se kazna. Cijena kazne ovisi o vrsti građe. Preporučujemo pravovremeno vraćanje ili produženje posudbe.",
        "keywords": ["kašnjenje", "kazna", "zakasnio", "nisam vratio"]
    },
    {
        "question": "Koje su radne vrijeme knjižnice?",
        "answer": "Knjižnica radi radnim danima od 8:00 do 20:00, subotom od 8:00 do 14:00. Nedjeljom i praznikom je zatvoreno. Preporučujemo provjeru na web stranici za točne informacije.",
        "keywords": ["radno vrijeme", "kada radi", "otvoreno", "zatvoreno", "subota"]
    },
    {
        "question": "Kako mogu rezervirati knjigu?",
        "answer": "Knjige možete rezervirati online kroz katalog ili telefonski. Kada knjiga bude dostupna, dobit ćete obavijest emailom ili SMS-om.",
        "keywords": ["rezervacija", "rezerviraj", "naruči", "čekanje"]
    },
    {
        "question": "Ima li knjižnica e-knjige?",
        "answer": "Da! Knjižnica nudi pristup digitalnim knjigama i audioknjigama putem platforme ZaKi Book. Članovi mogu posuditi do 4 naslova mjesečno na 4 uređaja.",
        "keywords": ["e-knjige", "digitalne knjige", "audioknige", "online", "elektronske"]
    },
    {
        "question": "Mogu li koristiti računala u knjižnici?",
        "answer": "Da, knjižnica ima računala za javnu upotrebu. Potrebna je rezervacija, a korisnici mogu koristiti internet, Office pakete i pisače.",
        "keywords": ["računala", "internet", "wifi", "printer", "PC"]
    },
    {
        "question": "Gdje se nalazi knjižnica?",
        "answer": "Narodna knjižnica i čitaonica Halubajska Zora nalazi se u Rijeci. Točnu adresu i upute za dolazak možete pronaći na web stranici knjižnice.",
        "keywords": ["lokacija", "adresa", "gdje je", "kako doći", "rijeka"]
    },
    {
        "question": "Ima li programa za djecu?",
        "answer": "Da! Knjižnica organizira brojne programe za djecu: čitaonice, radionice, pripovijedanja, tematske izložbe i književne kvizove. Kalendar događanja možete pratiti na web stranici.",
        "keywords": ["djeca", "program", "radionice", "događanja", "aktivnosti"]
    }
]


def get_all_faqs():
    """Vrati sve FAQ-ove"""
    return FAQ_DATA


def search_faq(query: str, threshold: float = 0.3):
    """
    Pretraži FAQ po query-u
    Vraća najrelevantnije FAQ-ove
    """
    query_lower = query.lower()
    results = []
    
    for faq in FAQ_DATA:
        score = 0
        
        # Provjeri keywords
        for keyword in faq['keywords']:
            if keyword.lower() in query_lower:
                score += 2
        
        # Provjeri pitanje
        question_words = faq['question'].lower().split()
        query_words = query_lower.split()
        
        for word in query_words:
            if word in question_words:
                score += 1
        
        if score > 0:
            results.append({
                'question': faq['question'],
                'answer': faq['answer'],
                'score': score
            })
    
    # Sortiraj po score-u
    results.sort(key=lambda x: x['score'], reverse=True)
    
    return results[:3]  # Vrati top 3


# Test
if __name__ == "__main__":
    print("=" * 70)
    print("FAQ SYSTEM TEST")
    print("=" * 70)
    
    # Test queries
    test_queries = [
        "Kako se učlaniti?",
        "Koliko knjiga mogu posuditi?",
        "Imate li e-knjige?",
        "Radno vrijeme",
        "Kasnim s vraćanjem"
    ]
    
    for query in test_queries:
        print(f"\nQuery: '{query}'")
        results = search_faq(query)
        
        if results:
            print(f"Najbolji rezultat (score: {results[0]['score']}):")
            print(f"Q: {results[0]['question']}")
            print(f"A: {results[0]['answer'][:100]}...")
        else:
            print("Nema rezultata")
    
    print("\n" + "=" * 70)