"""
AI-Powered Library Chatbot sa OpenAI GPT
Finalna verzija za deployment
"""

import sys
import os
from dotenv import load_dotenv

load_dotenv()

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from database.db_manager import DatabaseManager
from chatbot.knowledge_base import KnowledgeBase
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
import re


class AIChatbot:
    """AI chatbot sa OpenAI GPT-4o-mini"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.kb = KnowledgeBase()
        
        # OpenAI setup
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "❌ OPENAI_API_KEY nije postavljen!\n"
                "Dodaj u .env file: OPENAI_API_KEY=sk-your-key-here\n"
                "Dobij key na: https://platform.openai.com/api-keys"
            )
        
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",  # Jeftin i brz model
            temperature=0.7,
            api_key=api_key
        )
        
        # Učitaj knowledge base
        if self.kb.get_count() == 0:
            self._initialize_knowledge_base()
        
        print(f"✓ AI Chatbot inicijaliziran (GPT-4o-mini)")
        print(f"✓ Knowledge base: {self.kb.get_count()} dokumenata")
    
    def _initialize_knowledge_base(self):
        """Inicijaliziraj knowledge base"""
        if os.path.exists('data/membership_info.json'):
            self.kb.add_from_json('data/membership_info.json')
        if os.path.exists('data/website_all_pages.json'):
            self.kb.add_from_json('data/website_all_pages.json')
    
    def chat(self, user_message: str) -> str:
        """
        Glavni chat metoda - koristi je za sve poruke
        
        Args:
            user_message: Poruka od korisnika
            
        Returns:
            AI generirani odgovor
        """
        
        # 1. Prikupi kontekst iz baze podataka
        context = self._gather_context(user_message)
        
        # 2. Kreiraj system prompt
        system_prompt = self._create_system_prompt()
        
        # 3. Pozovi OpenAI
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"""KONTEKST IZ BAZE:
{context}

KORISNIČKO PITANJE:
{user_message}

Odgovori na pitanje koristeći informacije iz konteksta. Budi koncizan i koristan.""")
        ]
        
        try:
            response = self.llm.invoke(messages)
            return response.content
        
        except Exception as e:
            return (f"Žao mi je, došlo je do greške pri generiranju odgovora. "
                   f"Molim pokušaj ponovno ili kontaktiraj knjižnicu direktno.")
    
    def _gather_context(self, query: str) -> str:
        """Prikuplja relevantni kontekst iz baze i knowledge base"""
        
        context_parts = []
        
        # 1. Pretraži knowledge base (informacije o knjižnici)
        kb_results = self.kb.search(query, n_results=3)
        
        if kb_results and kb_results[0].get('distance', 1.0) < 0.7:
            context_parts.append("=== INFORMACIJE O KNJIŽNICI ===")
            for i, result in enumerate(kb_results[:2], 1):
                content = result['content'][:300]
                title = result.get('metadata', {}).get('title', 'N/A')
                context_parts.append(f"\n[{title}]\n{content}...")
        
        # 2. Pretraži katalog knjiga (ako je relevantno)
        if self._is_book_query(query):
            keywords = self._extract_keywords(query)
            
            if keywords:
                books = []
                for keyword in keywords[:2]:
                    books.extend(self.db.search_books(keyword, limit=4))
                
                if books:
                    # Ukloni duplikate
                    unique_books = {book['id']: book for book in books}.values()
                    books_list = list(unique_books)[:5]
                    
                    context_parts.append("\n=== KNJIGE U KATALOGU ===")
                    for book in books_list:
                        book_info = f"- {book['title']} by {book['author']}"
                        if book.get('year'):
                            book_info += f" ({book['year']})"
                        if book.get('isbn'):
                            book_info += f" [ISBN: {book['isbn']}]"
                        context_parts.append(book_info)
        
        if not context_parts:
            return "Nema specifičnih informacija u bazi za ovo pitanje."
        
        return "\n".join(context_parts)
    
    def _is_book_query(self, query: str) -> bool:
        """Provjeri je li upit o knjigama"""
        book_keywords = [
            'knjiga', 'knjige', 'knjigu', 'autor', 'autora',
            'napisao', 'naslov', 'čitati', 'pročitati',
            'preporuči', 'preporuka', 'predloži',
            'ima li', 'imaš li', 'imate li'
        ]
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in book_keywords)
    
    def _create_system_prompt(self) -> str:
        """Kreira system prompt za AI"""
        return """Ti si AI asistent za Narodnu knjižnicu i čitaonicu Halubajska Zora u Rijeci, Hrvatska.

TVOJA ULOGA:
- Pomažeš korisnicima s informacijama o knjižnici
- Odgovaraš na pitanja o članstvu, posudbi, uslugama i radnom vremenu
- Preporučuješ i tražiš knjige iz kataloga
- Daješ prijateljne, profesionalne i korisne odgovore

STIL KOMUNIKACIJE:
- Piši na hrvatskom jeziku
- Budi koncizan - maksimalno 3-4 rečenice (osim kad preporučuješ knjige)
- Koristi emoji umjereno za prijateljski ton (📚 🔍 📖 ⏰)
- Obraćaj se korisniku na "Vi"

PRAVILA:
1. KORISTI SAMO informacije iz konteksta koji ti je pružen
2. Ako informacija NIJE u kontekstu, reci: "Za ovu informaciju preporučujem da nazovete knjižnicu ili provjerite web stranicu: https://www.halubajska-zora.hr"
3. NEMOJ izmišljati podatke o cijenama, točnim vremenima ili pravilima
4. Kada preporučuješ knjige, UVIJEK navedi naslov i autora
5. Za rezervacije i dostupnost UVIJEK uputi na katalog ili knjižničare

PRIMJERI DOBRIH ODGOVORA:

Pitanje: "Kako se učlaniti?"
Odgovor: "Za učlanjenje trebate osobnu iskaznicu i ispunjenu pristupnicu. Članarina se plaća godišnje prema kategoriji (djeca, studenti, odrasli). Za točne cijene i detalje posjetite knjižnicu ili provjerite web stranicu. 📚"

Pitanje: "Imaš li knjige o internetu?"
Odgovor: "Da, imam nekoliko naslova:
- 'Error 404: jeste li spremni za svijet bez interneta?' by Esther Paniagua (2025)
- [ostale knjige iz konteksta]

Za provjeru dostupnosti provjerite katalog na https://katalog.halubajska-zora.hr 🔍"

Pitanje: "Koliko košta članarina?"
Odgovor: "Cijena članarine ovisi o kategoriji člana. Za točne cijene preporučujem da nazovete knjižnicu ili provjerite web stranicu, jer cijene se povremeno ažuriraju."

ODGOVARAJ PRIRODNO, KORISNO I PROFESIONALNO!"""
    
    def _extract_keywords(self, query: str) -> list:
        """Izvlači ključne riječi iz upita"""
        stop_words = [
            'knjiga', 'knjige', 'knjigu', 'autor', 'autora',
            'o', 'na', 'u', 'i', 'za', 'od', 'do', 'sa', 's',
            'preporuči', 'preporuka', 'imaš', 'ima', 'li',
            'mi', 'me', 'se', 'je', 'si', 'bio', 'bila',
            'koji', 'koja', 'koje', 'nekakva', 'neki', 'neka', 'neko'
        ]
        
        # Izvuci riječi
        words = re.findall(r'\w+', query.lower())
        
        # Filtriraj stop words i kratke riječi
        keywords = [
            word for word in words 
            if word not in stop_words and len(word) > 2
        ]
        
        return keywords[:3]  # Max 3 ključne riječi
    
    def close(self):
        """Zatvori bazu podataka"""
        self.db.close()


# Test
if __name__ == "__main__":
    print("=" * 70)
    print("🤖 AI LIBRARY CHATBOT - OpenAI GPT-4o-mini")
    print("=" * 70)
    
    try:
        chatbot = AIChatbot()
        
        # Automatski testovi
        test_questions = [
            "Kako se učlaniti u knjižnicu?",
            "Koje je radno vrijeme?",
            "Imaš li knjige o internetu?",
            "Preporuči mi nešto za čitati",
            "Koliko knjiga mogu posuditi odjednom?"
        ]
        
        print("\n🧪 Automatski testovi:\n")
        
        for i, question in enumerate(test_questions, 1):
            print(f"[Test {i}/5]")
            print(f"📝 Pitanje: {question}")
            print("⏳ Generiram odgovor...")
            
            response = chatbot.chat(question)
            
            print(f"🤖 Odgovor:\n{response}\n")
            print("-" * 70)
        
        # Interaktivni chat
        print("\n💬 INTERAKTIVNI MOD")
        print("Upiši 'exit' za izlaz\n")
        
        while True:
            user_input = input("Vi: ").strip()
            
            if user_input.lower() in ['exit', 'quit', 'izlaz', 'bye']:
                print("\n👋 Doviđenja! Hvala što koristite usluge knjižnice.")
                break
            
            if not user_input:
                continue
            
            print("⏳ Razmišljam...")
            response = chatbot.chat(user_input)
            print(f"\n🤖 Chatbot:\n{response}\n")
            print("-" * 70)
        
        chatbot.close()
        
    except ValueError as e:
        print(f"\n{e}")
    except Exception as e:
        print(f"\n❌ Neočekivana greška: {e}")