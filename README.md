# İSTE Öğrenci Rehberi

İskenderun Teknik Üniversitesi öğrencileri için geliştirilmiş akıllı bir rehber sistemi. Akademik takvimden personel iletişim bilgilerine, sınav programlarından resmi dilekçe oluşturmaya kadar öğrenci hayatına dair her konuda doğrudan ve doğru cevaplar sunar.

---

## Ne Yapıyor?

Üniversitede bir şeye ihtiyaç duyduğunuzda genellikle birkaç farklı portalı, dekanlık kapısını ve bölüm sekreterini tek tek dolaşırsınız. Bu proje o döngüyü kırıyor.

Sistem; yönetmelikleri, ders programlarını, akademik takvimi, personel bilgilerini ve okul duyurularını tek bir araya getiriyor. Siz sadece soruyu soruyorsunuz, sistem gerekli kaynağa bakıp cevabı getiriyor.

---

## Özellikler

### Akıllı Soru-Cevap (RAG)
Dokümanlar vektör veritabanında (ChromaDB) saklanıyor. Bir soru sorulduğunda sistem önce ilgili bölümleri buluyor, ardından Gemini 2.5 Flash modeliyle bütünleşik bir cevap üretiyor. Cevabın hangi kaynaktan geldiği de gösteriliyor.

### Semantik Önbellek
Aynı ya da anlamca benzer sorular daha önce sorulduysa sistem modeli tekrar çağırmadan önbellekten cevabı döndürüyor. Bu hem hızı artırıyor hem de API maliyetini düşürüyor. Önbellek diske yazılıyor, uygulama yeniden başlatıldığında kaybolmuyor.

### Akademik Kadro Rehberi
Tüm akademik ve idari personelin bölümü, e-posta adresi, ofis saatleri ve görevleri sisteme yüklenmiş durumda. "Bilgisayar Mühendisliği bölüm başkanının ofis saatleri ne zaman?" gibi bir soruya doğrudan cevap alabiliyorsunuz.

### Dilekçe Oluşturma
Sağlık raporu veya mazeret belgesi yükleyince sistem belgeden gerekli bilgileri çıkarıyor ve size hazır bir mazeret sınavı dilekçesi üretiyor. Dilekçeyi PDF olarak indirip imzalamanız yeterli.

### Zimbra E-posta Entegrasyonu
Üniversite mail sistemiyle bağlantı kurulabiliyor. Gelen kutusundaki ödev bildirimlerini, son tarihlerini ve duyuruları asistan otomatik olarak takip edebiliyor.

### Canlı Duyurular
İSTE web sitesindeki duyurular düzenli aralıklarla çekiliyor ve asistana bağlam olarak ekleniyor. "Bu hafta yeni duyuru var mı?" gibi sorulara güncel cevaplar verebiliyor.

---

## Teknoloji Yığını

| Katman | Teknoloji |
|--------|-----------|
| Ön Yüz | React + Vite |
| Arka Uç | Python, FastAPI |
| Yapay Zeka | Gemini 2.5 Flash (OpenRouter üzerinden) |
| Vektör Veritabanı | ChromaDB |
| Gömme Modeli | `paraphrase-multilingual-MiniLM-L12-v2` |
| Orchestration | LangChain |
| PDF İşleme | fpdf2 |
| Veritabanı | SQLite (SQLAlchemy) |

---

## Kurulum

### Gereksinimler
- Python 3.10+
- Node.js 18+
- OpenRouter API anahtarı (Gemini 2.5 Flash için)
- Google API anahtarı (belge tarama özelliği için)

### Adımlar

**1. Repoyu klonlayın**
```bash
git clone https://github.com/alizng1n/ogrenci_rehberi.git
cd ogrenci_rehberi
```

**2. Python bağımlılıklarını kurun**
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**3. Ortam değişkenlerini ayarlayın**

Proje kök dizinine `.env` dosyası oluşturun:
```
OPENROUTER_API_KEY=your_openrouter_key
GOOGLE_API_KEY=your_google_key
```

**4. Dokümanları vektör veritabanına yükleyin**

`data/raw/` klasörüne PDF, DOCX veya TXT formatındaki dokümanları ekleyin, ardından:
```bash
python src/ingest.py
```

**5. Uygulamayı başlatın**

Windows için hazır başlatma betiği:
```bash
baslat.bat
```

Ya da manuel olarak:
```bash
# Arka uç
uvicorn src.server:app --reload --port 8000

# Ön yüz (ayrı terminalde)
cd frontend
npm install
npm run dev
```

Uygulama varsayılan olarak `http://localhost:5173` adresinde açılır.

---

## Proje Yapısı

```
ogrenci_rehberi/
├── src/
│   ├── server.py          # FastAPI arka uç, tüm API endpoint'leri
│   ├── rag_chain.py       # RAG zinciri ve LLM konfigürasyonu
│   ├── ingest.py          # Doküman yükleme ve vektörleştirme
│   ├── scrape_personnel.py # Personel verisi çekme
│   ├── zimbra_client.py   # Zimbra e-posta entegrasyonu
│   ├── database.py        # Veritabanı bağlantısı
│   └── models.py          # SQLAlchemy modelleri
├── frontend/              # React uygulaması
├── data/
│   ├── raw/               # Ham dokümanlar (PDF, TXT, DOCX)
│   ├── chroma/            # ChromaDB vektör veritabanı
│   └── personnel.json     # Akademik kadro verisi
├── requirements.txt
└── baslat.bat
```

---

## Nasıl Kullanılır?

Uygulama açıldığında sol menüden modüller arasında geçiş yapabilirsiniz:

- **Soru Sor & Danış**: Doğal dilde soru sorun. Kaynak göstererek cevap alırsınız.
- **Personel Rehberi**: Akademik ve idari kadroyu arayın, ofis saatlerine bakın.
- **Duyurular**: Güncel İSTE duyurularını takip edin.
- **Yaklaşan Görevler**: Zimbra'dan çekilen ödev ve teslim tarihlerinizi görün.
- **Dilekçe Asistanı**: Mazeret belgesi yükleyin, dilekçeyi otomatik oluşturun ve PDF olarak indirin.

---

## Notlar

- `data/semantic_cache.json` dosyası çalışma zamanında oluşturulur ve `.gitignore`'a eklenmiştir.
- Yeni doküman eklendiğinde `ingest.py`'yi tekrar çalıştırmanız gerekir.
- Personel verisi üniversite web sitesinden otomatik çekilebilir (`scrape_personnel.py`), ancak bu işlem site yapısına bağlıdır.
