"""
Database Manager za knjižnicu
SQLite baza podataka
"""

import sqlite3
import json
import logging
from typing import List, Dict, Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manager za SQLite bazu podataka"""
    
    def __init__(self, db_path: str = "data/library.db"):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self._connect()
        self._create_tables()
    
    def _connect(self):
        """Spoji se na bazu"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row  # Za pristup kolonama po imenu
            self.cursor = self.conn.cursor()
            logger.info(f"✓ Spojen na bazu: {self.db_path}")
        except Exception as e:
            logger.error(f"Greška pri spajanju na bazu: {e}")
            raise
    
    def _create_tables(self):
        """Kreira tablice ako ne postoje"""
        
        # Tablica za knjige
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                author TEXT,
                publisher TEXT,
                year TEXT,
                pages INTEGER,
                isbn TEXT,
                language TEXT,
                material_type TEXT,
                url TEXT,
                full_info TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tablica za autore (many-to-many)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS book_authors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id TEXT,
                author_name TEXT,
                author_role TEXT,
                FOREIGN KEY (book_id) REFERENCES books(id)
            )
        """)
        
        # Tablica za teme/subjects
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS book_subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id TEXT,
                subject TEXT,
                FOREIGN KEY (book_id) REFERENCES books(id)
            )
        """)
        
        # Tablica za tagove
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS book_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id TEXT,
                tag TEXT,
                FOREIGN KEY (book_id) REFERENCES books(id)
            )
        """)
        
        # Tablica za klasifikacije
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS book_classifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id TEXT,
                code TEXT,
                description TEXT,
                FOREIGN KEY (book_id) REFERENCES books(id)
            )
        """)
        
        # Tablica za napomene
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS book_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id TEXT,
                note TEXT,
                FOREIGN KEY (book_id) REFERENCES books(id)
            )
        """)
        
        # Tablica za dostupnost (za budućnost)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS book_availability (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id TEXT,
                status TEXT,
                location TEXT,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (book_id) REFERENCES books(id)
            )
        """)
        
        self.conn.commit()
        logger.info("✓ Tablice kreirane")
    
    def insert_book(self, book_data: Dict) -> bool:
        """Umetni knjigu u bazu"""
        try:
            # Glavna tablica
            self.cursor.execute("""
                INSERT OR REPLACE INTO books 
                (id, title, author, publisher, year, pages, isbn, language, 
                 material_type, url, full_info, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                book_data.get('id'),
                book_data.get('title'),
                book_data.get('author'),
                book_data.get('publisher'),
                book_data.get('year'),
                book_data.get('pages'),
                book_data.get('isbn'),
                book_data.get('language'),
                book_data.get('material_type'),
                book_data.get('url'),
                book_data.get('full_info'),
                datetime.now()
            ))
            
            book_id = book_data.get('id')
            
            # Obriši stare povezane podatke
            self.cursor.execute("DELETE FROM book_authors WHERE book_id = ?", (book_id,))
            self.cursor.execute("DELETE FROM book_subjects WHERE book_id = ?", (book_id,))
            self.cursor.execute("DELETE FROM book_tags WHERE book_id = ?", (book_id,))
            self.cursor.execute("DELETE FROM book_classifications WHERE book_id = ?", (book_id,))
            self.cursor.execute("DELETE FROM book_notes WHERE book_id = ?", (book_id,))
            
            # Dodaj ostale autore
            for author_info in book_data.get('other_authors', []):
                # Parse "Name (role)" format
                if '(' in author_info:
                    author_name = author_info.split('(')[0].strip()
                    author_role = author_info.split('(')[1].replace(')', '').strip()
                else:
                    author_name = author_info
                    author_role = 'contributor'
                
                self.cursor.execute("""
                    INSERT INTO book_authors (book_id, author_name, author_role)
                    VALUES (?, ?, ?)
                """, (book_id, author_name, author_role))
            
            # Dodaj subjects
            for subject in book_data.get('subjects', []):
                self.cursor.execute("""
                    INSERT INTO book_subjects (book_id, subject)
                    VALUES (?, ?)
                """, (book_id, subject))
            
            # Dodaj tagove
            for tag in book_data.get('tags', []):
                self.cursor.execute("""
                    INSERT INTO book_tags (book_id, tag)
                    VALUES (?, ?)
                """, (book_id, tag))
            
            # Dodaj klasifikacije
            for classification in book_data.get('classifications', []):
                if isinstance(classification, dict):
                    self.cursor.execute("""
                        INSERT INTO book_classifications (book_id, code, description)
                        VALUES (?, ?, ?)
                    """, (book_id, classification.get('code'), classification.get('description')))
            
            # Dodaj napomene
            for note in book_data.get('notes', []):
                self.cursor.execute("""
                    INSERT INTO book_notes (book_id, note)
                    VALUES (?, ?)
                """, (book_id, note))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Greška pri umetanju knjige {book_data.get('title')}: {e}")
            self.conn.rollback()
            return False
    
    def import_from_json(self, json_file: str) -> int:
        """Importaj knjige iz JSON fajla"""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                books = json.load(f)
            
            count = 0
            for book in books:
                if self.insert_book(book):
                    count += 1
            
            logger.info(f"✓ Importano {count}/{len(books)} knjiga")
            return count
            
        except Exception as e:
            logger.error(f"Greška pri importu: {e}")
            return 0
    
    def search_books(self, query: str, limit: int = 10) -> List[Dict]:
        """Pretraži knjige"""
        try:
            self.cursor.execute("""
                SELECT * FROM books 
                WHERE title LIKE ? OR author LIKE ? OR isbn LIKE ?
                LIMIT ?
            """, (f'%{query}%', f'%{query}%', f'%{query}%', limit))
            
            rows = self.cursor.fetchall()
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Greška pri pretraživanju: {e}")
            return []
    
    def get_book_by_id(self, book_id: str) -> Optional[Dict]:
        """Dohvati knjigu po ID-u sa svim detaljima"""
        try:
            # Osnovna knjiga
            self.cursor.execute("SELECT * FROM books WHERE id = ?", (book_id,))
            book_row = self.cursor.fetchone()
            
            if not book_row:
                return None
            
            book = dict(book_row)
            
            # Dodaj ostale autore
            self.cursor.execute("""
                SELECT author_name, author_role FROM book_authors WHERE book_id = ?
            """, (book_id,))
            book['other_authors'] = [
                f"{row['author_name']} ({row['author_role']})" 
                for row in self.cursor.fetchall()
            ]
            
            # Dodaj subjects
            self.cursor.execute("""
                SELECT subject FROM book_subjects WHERE book_id = ?
            """, (book_id,))
            book['subjects'] = [row['subject'] for row in self.cursor.fetchall()]
            
            # Dodaj tagove
            self.cursor.execute("""
                SELECT tag FROM book_tags WHERE book_id = ?
            """, (book_id,))
            book['tags'] = [row['tag'] for row in self.cursor.fetchall()]
            
            return book
            
        except Exception as e:
            logger.error(f"Greška pri dohvaćanju knjige: {e}")
            return None
    
    def get_all_books(self, limit: int = 100) -> List[Dict]:
        """Dohvati sve knjige"""
        try:
            self.cursor.execute("SELECT * FROM books LIMIT ?", (limit,))
            rows = self.cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Greška: {e}")
            return []
    
    def close(self):
        """Zatvori konekciju"""
        if self.conn:
            self.conn.close()
            logger.info("Baza zatvorena")


# Test
if __name__ == "__main__":
    print("=" * 70)
    print("DATABASE MANAGER TEST")
    print("=" * 70)
    
    db = DatabaseManager()
    
    # Importaj podatke iz JSON-a
    print("\n1. Importam podatke iz JSON-a...")
    import glob
    import os
    
    # Provjeri što ima u data folderu
    print(f"Trenutni direktorij: {os.getcwd()}")
    print(f"Sadržaj data foldera:")
    if os.path.exists("data"):
        files = os.listdir("data")
        for f in files:
            print(f"  - {f}")
    
    json_files = glob.glob("data/books_catalog_*.json")
    print(f"\nPronadjeno JSON fajlova: {len(json_files)}")
    
    if json_files:
        latest_json = max(json_files)  # Uzmi najnoviji
        print(f"Koristim: {latest_json}")
        count = db.import_from_json(latest_json)
        print(f"✓ Importano knjiga: {count}")
    else:
        print("❌ Nema JSON fajlova!")
        print("Pokušavam naći bilo koji JSON...")
        
        # Pokušaj pronaći bilo koji JSON
        all_json = glob.glob("data/*.json")
        if all_json:
            print(f"Pronađeno: {all_json}")
            count = db.import_from_json(all_json[0])
            print(f"✓ Importano knjiga: {count}")
        else:
            print("Molim, prvo pokreni scraper!")
    
    # Test pretraživanja
    print("\n2. Testiram pretraživanje...")
    results = db.search_books("internet")
    print(f"Pronađeno rezultata za 'internet': {len(results)}")
    for book in results[:3]:
        print(f"  - {book['title']} ({book['author']})")
    
    # Dohvati sve knjige
    print("\n3. Dohvaćam sve knjige...")
    all_books = db.get_all_books()
    print(f"Ukupno knjiga u bazi: {len(all_books)}")
    
    if all_books:
        print("\nPrvih nekoliko knjiga:")
        for book in all_books[:3]:
            print(f"  - {book['title']} by {book['author']}")
    
    print("\n" + "=" * 70)
    print("Baza funkcionira!")
    print("=" * 70)
    
    db.close()