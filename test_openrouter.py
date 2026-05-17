import os
from dotenv import load_dotenv
import requests

load_dotenv()
key = os.environ.get("OPENROUTER_API_KEY")
print(f"API Key: {key[:10]}...")

r = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    },
    json={
        "model": "openrouter/auto",
        "messages": [{"role": "user", "content": "Merhaba, calisiyor musun?"}]
    },
    timeout=30
)
print("Status:", r.status_code)
data = r.json()
if r.status_code == 200:
    print("CEVAP:", data["choices"][0]["message"]["content"])
else:
    print("HATA:", data)

# Backend'in ayakta olup olmadigini da test et
try:
    health = requests.get("http://localhost:8000/api/health", timeout=5)
    print("\nBackend durumu:", health.json())
except Exception as e:
    print("\nBackend KAPALI veya ULASILAMIYOR:", e)
