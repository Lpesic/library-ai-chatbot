import sqlite3
import os

def find_book_with_description():
    db_path = "data/library.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Baza nije pronađena na putanji: {db_path}")
        return

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Tražimo prvu knjigu gdje description nije prazan i nije NULL
        query = "SELECT id, title, author, description FROM books WHERE description IS NOT NULL AND description != '' LIMIT 1"
        cursor.execute(query)
        book = cursor.fetchone()

        print("=" * 50)
        if book:
            print("✅ PRONAĐENA KNJIGA S OPISOM!")
            print(f"📍 ID: {book['id']}")
            print(f"📚 Naslov: {book['title']}")
            print(f"✍️ Autor: {book['author']}")
            print("-" * 50)
            print(f"📝 Opis (prvih 150 znakova): \n{book['description'][:150]}...")
            print("=" * 50)
            print("\n💡 KAKO TESTIRATI CHATBOTA?")
            print(f"Upiši botu: 'O čemu se radi u knjizi {book['title']}?'")
        else:
            print("❌ U bazi nema knjiga koje imaju spremljen opis.")
            print("Sve knjige u bazi trenutno imaju prazno polje 'description'.")
            
            # Provjera koliko uopće ima knjiga
            cursor.execute("SELECT COUNT(*) FROM books")
            total = cursor.fetchone()[0]
            print(f"\n📊 Ukupno knjiga u bazi: {total}")
        print("=" * 50)

        conn.close()
    except Exception as e:
        print(f"Greška: {e}")

if __name__ == "__main__":
    find_book_with_description()