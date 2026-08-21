import os
from groq import Groq

# Zamijeni s pravim ključem ako nije u okruženju
client = Groq(api_key=os.environ.get("GROQ_API_KEY", "TVOJ_GROQ_API_KLJUČ"))

try:
    models = client.models.list()
    print("Dostupni modeli na tvom računu:")
    for m in models.data:
        print(f"- {m.id}")
except Exception as e:
    print(f"Greška s API ključem: {e}")