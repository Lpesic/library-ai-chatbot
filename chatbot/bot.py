"""
Library AI Chatbot - RAG powered
Chatbot koji koristi knowledge base i pretraživanje knjiga
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chatbot.knowledge_base import KnowledgeBase
import re


class LibraryChatbot:
    """AI Chatbot za knjižnicu sa RAG sistemom"""
    
    def __init__(self):
        self.kb = KnowledgeBase()
        
        # Učitaj knowledge base ako je prazan
        if self.kb.get_count() == 0:
            self._initialize_knowledge_base()
        
        print(f"✓ Chatbot inicijaliziran (Knowledge base: {self.kb.get_count()} dokumenata)")
    
    def _initialize_knowledge_base(self):
        """Inicijaliziraj knowledge base sa podacima"""
        import os
        
        if os.path.exists('data/membership_info.json'):
            self.kb.add_from_json('data/membership_info.json')
        
        if os.path.exists('data/website_all_pages.json'):
            self.kb.add_from_json('data/website_all_pages.json')
    
    def process_message(self, user_message: str) -> str:
        """Procesira poruku korisnika"""
        
        user_message_lower = user_message.lower()
        
        # 1. Pitanja o knjižnici (radno vrijeme, članstvo, pravila...)
        if self._is_library_info_question(user_message_lower):
            return self._handle_library_info(user_message)
        
        # 2. Pretraživanje knjiga
        if self._is_book_search_query(user_message_lower):
            return self._handle_book_query(user_message)
        
        # 3. Preporuke knjiga
        if any(word in user_message_lower for word in ['preporuči', 'preporuka', 'preporučuješ', 'predloži', 'što čitati']):
            return self._handle_book_recommendations(user_message)
        
        # 4. Provjeri dostupnost specifične knjige
        if 'dostupn' in user_message_lower or 'posuden' in user_message_lower:
            return self._handle_availability_check(user_message)
        
        # 5. Default - pokušaj s knowledge base-om
        kb_results = self.kb.search(user_message, n_results=2)
        if kb_results and kb_results[0].get('distance', 1.0) < 0.5:
            return self._format_kb_response(kb_results[0])
        
        # 6. Fallback odgovor
        return self._default_response()
    
    def _is_library_info_question(self, query: str) -> bool:
        """Provjeri je li pitanje o knjižnici"""
        keywords = [
            'kako', 'gdje', 'kada', 'koliko', 'što',
            'radno vrijeme', 'otvoreno', 'zatvoreno',
            'učlaniti', 'članarina', 'cijena', 'košta',
            'posuditi', 'posudba', 'vratiti', 'produžiti',
            'kazna', 'kašnjenje', 'rezervirati', 'rezervacija',
            'e-knjig', 'digitalne', 'audio', 'računal', 'wifi'
        ]
        return any(keyword in query for keyword in keywords)
    
    def _is_book_search_query(self, query: str) -> bool:
        """Provjeri je li upit o knjigama"""
        keywords = [
            'knjiga', 'knjige', 'knjigu',
            'autor', 'napisao',
            'naslov', 'zove se',
            'pronađi', 'nađi', 'traži',
            'imate', 'ima li', 'imaš'
        ]
        return any(keyword in query for keyword in keywords)
    
    def _handle_library_info(self, query: str) -> str:
        """Rukuje pitanjima o knjižnici koristeći RAG"""
        
        # Prvo pokušaj s FAQ-om
        #faq_results = search_faq(query)
        #if faq_results and faq_results[0]['score'] >= 2:
        #    return self._format_faq_response(faq_results[0])
        
        # Zatim knowledge base
        kb_results = self.kb.search(query, n_results=2)
        
        if kb_results:
            best_result = kb_results[0]
            
            # Ako je rezultat relevantan (niska distance)
            if best_result.get('distance', 1.0) < 0.7:
                return self._format_kb_response(best_result)
        
        return ("Nisam siguran u odgovor na to pitanje. "
                "Možete provjeriti na web stranici knjižnice: https://www.halubajska-zora.hr "
                "ili nazvati knjižnicu za detaljnije informacije.")
    
    def _handle_book_query(self, query: str) -> str:
        """Rukuje upitima o knjigama"""
        
        # Izvuci ključne riječi
        keywords = self._extract_keywords(query)
        
        if not keywords:
            return "Molim vas, navedite naslov, autora ili temu knjige koju tražite."
        
        # Pretraži bazu
        results = []
        for keyword in keywords:
            books = self.db.search_books(keyword, limit=5)
            results.extend(books)
        
        # Ukloni duplikate
        unique_books = {book['id']: book for book in results}.values()
        books_list = list(unique_books)[:5]
        
        if not books_list:
            return (f"Nisam pronašao knjige za '{' '.join(keywords)}'. "
                   f"Možete pretraživati katalog na: https://katalog.halubajska-zora.hr")
        
        # Formatiraj odgovor
        response = f"**Pronašao sam {len(books_list)} {'knjigu' if len(books_list) == 1 else 'knjige'}:**\n\n"
        
        for i, book in enumerate(books_list, 1):
            response += f"**{i}. {book['title']}**\n"
            response += f"   📚 Autor: {book['author']}\n"
            if book.get('year'):
                response += f"   📅 Godina: {book['year']}\n"
            if book.get('pages'):
                response += f"   📄 Stranica: {book['pages']}\n"
            if book.get('isbn'):
                response += f"   🔢 ISBN: {book['isbn']}\n"
            response += "\n"
        
        response += "\n💡 Za provjeru dostupnosti posjetite katalog ili nazovite knjižnicu."
        
        return response
    
    def _handle_book_recommendations(self, query: str) -> str:
        """Rukuje preporukama knjiga"""
        
        # Pokušaj izvući temu iz upita
        keywords = self._extract_keywords(query)
        
        if keywords:
            # Dohvati knjige po temi
            results = []
            for keyword in keywords:
                books = self.db.search_books(keyword, limit=3)
                results.extend(books)
            
            if results:
                unique_books = {book['id']: book for book in results}.values()
                books_list = list(unique_books)[:3]
                
                response = f"**Preporučujem vam:**\n\n"
                
                for i, book in enumerate(books_list, 1):
                    response += f"**{i}. {book['title']}** - {book['author']}\n"
                    if book.get('year'):
                        response += f"   Godina: {book['year']}\n"
                    response += "\n"
                
                return response
        
        # Ako nema specifične teme, daj popularne knjige
        popular_books = self.db.get_all_books(limit=5)
        
        if popular_books:
            response = "**Evo nekih popularnih naslova:**\n\n"
            for i, book in enumerate(popular_books[:3], 1):
                response += f"**{i}. {book['title']}** - {book['author']}\n\n"
            return response
        
        return "Možete pregledati najčitanije knjige na: https://katalog.halubajska-zora.hr"
    
    def _handle_availability_check(self, query: str) -> str:
        """Provjera dostupnosti knjige"""
        keywords = self._extract_keywords(query)
        
        if not keywords:
            return "Molim navedite naslov ili autora knjige."
        
        books = self.db.search_books(keywords[0], limit=1)
        
        if books:
            book = books[0]
            return (f"**{book['title']}** od {book['author']}\n\n"
                   f"Za provjeru trenutne dostupnosti i rezervaciju, "
                   f"molim provjerite katalog: https://katalog.halubajska-zora.hr")
        
        return "Nisam pronašao tu knjigu. Provjerite katalog za točnu dostupnost."
    
    def _format_faq_response(self, faq: dict) -> str:
        """Formatira FAQ odgovor"""
        return f"**{faq['question']}**\n\n{faq['answer']}"
    
    def _format_kb_response(self, result: dict) -> str:
        """Formatira odgovor iz knowledge base"""
        content = result['content']
        metadata = result.get('metadata', {})
        
        # Skrati odgovor ako je predug
        if len(content) > 500:
            # Nađi prirodni prekid (kraj rečenice)
            sentences = content[:500].split('. ')
            content = '. '.join(sentences[:-1]) + '.'
            if not content.endswith('.'):
                content += '...'
        
        response = content
        
        # Dodaj izvor ako postoji
        if metadata.get('source'):
            response += f"\n\n🔗 Više informacija: {metadata['source']}"
        
        return response
    
    def _extract_keywords(self, query: str) -> list:
        """Izvlači ključne riječi iz upita"""
        stop_words = [
            'knjiga', 'knjige', 'autor', 'o', 'na', 'u', 'i', 'za', 
            'preporuči', 'preporuka', 'imaš', 'ima', 'li', 'neku',
            'mi', 'me', 'se', 'je', 'koji', 'koja', 'koje',
            'neki', 'neka', 'neko', 'the', 'a', 'an'
        ]
        
        words = re.findall(r'\w+', query.lower())
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        return keywords[:3]
    
    def _default_response(self) -> str:
        """Default odgovor"""
        return ("**Dobrodošli u knjižnicu Halubajska Zora! 📚**\n\n"
                "Mogu vam pomoći s:\n"
                "• Informacijama o knjižnici (radno vrijeme, učlanjenje, posudba)\n"
                "• Pretraživanjem knjiga u katalogu\n"
                "• Preporukama za čitanje\n"
                "• Provjeri dostupnosti knjiga\n\n"
                "Što vas zanima?")
    
    def close(self):
        """Zatvori konekcije"""
        self.db.close()


# Test - Konzolni chat
if __name__ == "__main__":
    print("=" * 70)
    print("📚 LIBRARY CHATBOT - POWERED BY RAG")
    print("=" * 70)
    print("Upišite 'exit' za izlaz\n")
    
    chatbot = LibraryChatbot()
    
    # Testiraj sa nekim pitanjima
    test_questions = [
        "Kako se učlaniti u knjižnicu?",
        "Imaš li knjige o internetu?",
        "Preporuči mi nešto za čitati",
        "Radno vrijeme knjižnice?"
    ]
    
    print("🤖 Testiram chatbot sa primjerima...\n")
    for question in test_questions:
        print(f"Vi: {question}")
        response = chatbot.process_message(question)
        print(f"\nChatbot:\n{response}\n")
        print("-" * 70)
    
    # Interaktivni mod
    print("\n💬 Sada možete pitati što želite:\n")
    
    while True:
        user_input = input("Vi: ")
        
        if user_input.lower() in ['exit', 'quit', 'izlaz']:
            print("Doviđenja! 👋")
            break
        
        if not user_input.strip():
            continue
        
        response = chatbot.process_message(user_input)
        print(f"\nChatbot:\n{response}\n")
        print("-" * 70)
    
    chatbot.close()