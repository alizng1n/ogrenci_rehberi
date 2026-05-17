import requests
import json
import sys

# Windows konsol encoding problemini coz
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

print("=== Backend Chat Endpoint Testi ===\n")

try:
    r = requests.post(
        "http://localhost:8000/api/chat",
        headers={"Content-Type": "application/json"},
        json={"message": "merhaba", "history": []},
        timeout=60
    )
    print(f"HTTP Status: {r.status_code}")
    data = r.json()
    print(f"CEVAP: {data.get('answer', 'YOK')}")
    print(f"KAYNAKLAR: {len(data.get('sources', []))} kaynak")
except requests.exceptions.ConnectionError as e:
    print(f"BAGLANTI HATASI: Backend ayakta degil!")
except requests.exceptions.Timeout:
    print("TIMEOUT: Backend 60 saniyede yanit vermedi.")
except Exception as e:
    print(f"HATA: {type(e).__name__}: {e}")
