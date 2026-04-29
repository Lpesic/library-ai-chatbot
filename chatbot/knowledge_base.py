"""
Knowledge Base - RAG sistem za chatbot
Koristi ChromaDB za semantičko pretraživanje
"""

import json
import chromadb
from chromadb.config import Settings
import logging
from typing import List, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KnowledgeBase:
    """Knowledge base sa ChromaDB za semantičko pretraživanje"""
    
    def __init__(self, persist_directory: str = "data/chroma_db"):
        self.client = chromadb.Client(Settings(
            persist_directory=persist_directory,
            anonymized_telemetry=False
        ))
        
        # Kreiraj ili dohvati collection
        try:
            self.collection = self.client.get_collection("library_knowledge")
            logger.info("✓ Postojeća knowledge base učitana")
        except:
            self.collection = self.client.create_collection(
                name="library_knowledge",
                metadata={"description": "Library information and FAQ"}
            )
            logger.info("✓ Nova knowledge base kreirana")
    
    def add_from_json(self, json_file: str):
        """Dodaj dokumente iz JSON fajla"""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            documents = []
            metadatas = []
            ids = []
            
            # Ako je lista stranica
            if isinstance(data, list):
                for i, page in enumerate(data):
                    documents.append(page.get('content', ''))
                    metadatas.append({
                        'source': page.get('url', ''),
                        'title': page.get('title', 'Untitled')
                    })
                    ids.append(f"page_{i}")
            
            # Ako su sekcije
            elif isinstance(data, dict) and 'sections' in data:
                for i, section in enumerate(data['sections']):
                    # Spoji sadržaj sekcije
                    content = section['title'] + '\n\n' + '\n'.join(section.get('content', []))
                    
                    documents.append(content)
                    metadatas.append({
                        'source': data.get('url', ''),
                        'title': section['title']
                    })
                    ids.append(f"section_{i}")
            
            # Dodaj u collection
            if documents:
                self.collection.add(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids
                )
                logger.info(f"✓ Dodano {len(documents)} dokumenata")
            
        except Exception as e:
            logger.error(f"Greška pri dodavanju dokumenata: {e}")
    
    def search(self, query: str, n_results: int = 3) -> List[Dict]:
        """Pretraži knowledge base"""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            
            # Formatiraj rezultate
            formatted_results = []
            
            if results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    formatted_results.append({
                        'content': doc,
                        'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                        'distance': results['distances'][0][i] if 'distances' in results else None
                    })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Greška pri pretraživanju: {e}")
            return []
    
    def get_count(self) -> int:
        """Broj dokumenata u bazi"""
        return self.collection.count()
    
    def clear(self):
        """Obriši sve dokumente"""
        try:
            self.client.delete_collection("library_knowledge")
            self.collection = self.client.create_collection("library_knowledge")
            logger.info("✓ Knowledge base očišćena")
        except Exception as e:
            logger.error(f"Greška: {e}")
