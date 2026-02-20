from database.db_manager import DatabaseManager
from datetime import datetime

db = DatabaseManager()

# Podaci iz tvog HTML-a koji si poslao ranije
test_book = {
    'id': '145008433', # ID iz skrivenog polja u HTML-u
    'title': 'What if I never get over you (Prijevod)',
    'author': 'Toon, Paige',
    'publisher': 'Mozaik knjiga',
    'year': '2025',
    'pages': 363,
    'isbn': '9789531440790',
    'language': 'hrvatski',
    'material_type': 'knjiga',
    'url': 'https://link-do-knjiznice.hr',
    'full_info': 'Kompletan zapis...',
    'description': 'Putujući Europom, Ellie upozna Asha i njih dvoje provedu tri nezaboravna dana zajedno u Portugalu. Ellie mu povjeri kako je izgubila najbolju prijateljicu Stellu... (itd.)',
    'other_authors': ['Štambak, Dijana (prevoditeljica)'],
    'classifications': [{'code': '821.111-31', 'description': 'Engleska književnost. Romani.'}]
}

if db.insert_book(test_book):
    print("✅ Uspješno dodana knjiga s opisom u bazu!")
else:
    print("❌ Greška pri dodavanju.")

db.close()