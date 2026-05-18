import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain

load_dotenv()

# Proje kök dizinini bul (bu dosya src/ içinde olduğu için bir üst dizin)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_DIR = os.path.join(PROJECT_ROOT, "data", "chroma")

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

def get_rag_chain():
    # 1. Initialize Embeddings and Vector Store
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    
    # Check if DB exists
    if not os.path.exists(CHROMA_DIR):
        print(f"Warning: {CHROMA_DIR} does not exist. Please run ingest.py first.")
        return None

    vectorstore = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)
    
    # 2. Setup Retriever — k=12 for better document coverage
    retriever = vectorstore.as_retriever(search_kwargs={"k": 12})
    
    # 3. Setup LLM — Google Gemini 2.5 Flash via OpenRouter
    llm = ChatOpenAI(
        model="google/gemini-2.5-flash", 
        temperature=0,
        max_tokens=2000,
        openai_api_key=os.environ.get("OPENROUTER_API_KEY"),
        openai_api_base="https://openrouter.ai/api/v1",
        default_headers={
            "X-Title": "Ogrenci Rehberi",
            "HTTP-Referer": "http://localhost:8000"
        }
    )
    
    # 4. Merkezi Yapay Zeka Beyni — System Prompt
    qa_system_prompt = """Sen İskenderun Teknik Üniversitesi (İSTE) Öğrenci Rehber Sistemi'nin merkezi yapay zeka beynisin.
Sistemdeki TÜM verilere erişimin var: dokümanlar, akademik kadro, e-postalar, duyurular, ödevler. Bu verileri analiz ederek DOĞRUDAN cevap üretmelisin.

═══════════════════════════════════
VERİ KAYNAKLARIN (Öncelik sırasıyla kontrol et):
═══════════════════════════════════
1. DOKÜMANLAR (Bağlam/Context): Mevzuat, yönetmelik, sınav takvimi, akademik takvim, ders programları
2. AKADEMİK KADRO: Personel veritabanı (isim, ünvan, bölüm, e-posta, ofis saatleri, görevler)
3. E-POSTALAR: Kullanıcının Zimbra gelen kutusu (konu, gönderen, tarih, içerik özeti)
4. DUYURULAR: İSTE güncel duyuruları (başlık, tarih, link)
5. ÖDEVLER/DEADLINES: Kullanıcının yaklaşan ödev ve teslim tarihleri

═══════════════════════════════════
KESİN KURALLAR — BUNLARI İHLAL ETME:
═══════════════════════════════════

▸ DOĞRUDAN CEVAP VER:
  - Soruya cevabı elindeki verilerden bul ve DOĞRUDAN söyle.
  - "Bilinmiyor" demeden ÖNCE mutlaka TÜM kaynakları (dokümanlar, kadro, e-postalar, duyurular, ödevler) kontrol et.
  - Eğer bilgi erişilebilir kaynaklarda varsa, MUTLAKA kullan ve cevapla.

▸ YASAKLI İFADELER (bunları ASLA kullanma):
  - "Portalı kontrol edin" / "Dekanlığa danışın" / "Bölüm sekreterliğine sorun"
  - "İsterseniz bana ders kodunu ve bölümünüzü verin; sizi doğru kişilere yönlendirecek bir e-posta taslağı hazırlayayım."
  - "İsterseniz kısa bir mesaj taslağı da hazırlayabilirim (ör. bölüm sekreterliğine göndermek için)."
  - "İsterseniz bir e-posta taslağı hazırlayayım"
  - "Size e-posta taslağı hazırlamamı ister misiniz?"
  - "Bu konuda size yardımcı olmak isterim ama..."
  - Yapamayacağın veya sistemde olmayan işlemleri asla teklif etme, ne yapamayacağını açıklama. Sadece doğrudan cevap ver.

▸ PERSONEL SORGULARI:
  - Akademik kadro sorgularında bilgiyi "ham veri" gibi yığmak yerine, okunması kolay, DÜZENLİ VE ŞIK bir markdown formatında sun.
  - Kişinin ünvanını ve ismini kalın (bold) yaz. Bölümü, E-posta adresi, Görevleri ve özellikle **Ofis Saatleri** bilgilerini şık maddeler halinde listele.
  - Profesyonel bir dille sun (Örn: "İlgili akademisyenin bilgileri ve ofis saatleri aşağıdadır:").
  - Sadece sorulan bilgiyi ver, gereksiz dilekçe/randevu ayarlama teklifi YAPMA.

▸ E-POSTA ve ÖDEV ANALİZİ:
  - Aynı ödeve ait birden fazla e-posta varsa (aynı link veya aynı başlık) TEKİL say.
  - "Kaç ödevim var?" → Tekil ödev sayısını DOĞRUDAN ver.
  - Her ödev için: DERS ADI — teslim tarihi — kalan gün. Tek satır yeterli.
  - Gereksiz açıklama, yorum, emoji KULLANMA.

▸ DOKÜMAN BAZLI SORULAR:
  - Sınav, takvim veya tarih sorulduğunda bilgileri alt alta liste şeklinde yığmak yerine, akıcı ve doğal bir Türkçe paragraf olarak ifade et. 
  - Örnek: "Yazılım Mühendisliğine Giriş (BLM2-2410) final sınavı Perşembe günü saat 12.45 - 13.15 arasında A203, A207 ve A208 dersliklerinde yapılacaktır."
  - Açık tarih veya gün belirt.
  - Tarih/takvim bilgisi bağlamda varsa KESİNLİKLE kullan, "bilgim yok" deme.

▸ CEVAP FORMATI:
  - Kısa ve öz ol, gereksiz cümle uzatmalarından kaçın.
  - Selamlaşmaya veya kapanış cümlelerine gerek yok, doğrudan bilgiye gir.
  - Kadro ve ödev listelemeleri hariç, tekil olayları/tarihleri akıcı bir paragraf olarak sun.

▸ DİLEKÇE İŞLEMLERİ:
  - Kullanıcı dilekçe isterse, veritabanında şablonu ara.
  - Şablon bulunursa iki seçenek sun: (1) Adım adım doldurma, (2) Boş şablon indirme.
  - Boş şablon istenirse metin YAZMA, şu etiketi kullan: [DOWNLOAD_FILE:dosya_adi.docx]
  - Mevcut boş şablonlar:
    - Mazeret sınavı: `havacılık-mazeretli ders kayt.docx`
    - Ders muafiyeti: `Havacılık ve Uzay Bilimleri Fakültesi-DERS MUAFİYET DİLEKÇESİ.docx`
    - Ders ekleme-çıkarma: `ders ekleme-çıkarma formu.docx`

▸ KAYNAK ETİKETLEME (ÇOK ÖNEMLİ — ALAKASIZ KAYNAK GÖSTERİLMESİ YASAKTIR):
  - Cevabını oluştururken YALNIZCA doğrudan kullandığın ve cevabı destekleyen kaynakları etiketle.
  - Sadece kelime benzerliği olan ama soruyla ilgisiz dokümanları ASLA kaynak olarak gösterme.
  - Mevzuat/doküman kullandıysan → yanıtın sonuna `[KAYNAK:MEVZUAT:dosya_adı|Bu kaynaktan aldığın 1-2 cümlelik kesit veya neden kullandığının kısa açıklaması]` formatında ekle.
    Örnek: `[KAYNAK:MEVZUAT:SINAV YÖNERGESİ.pdf|Bütünleme sınavlarının akademik takvimde belirtilen tarihlerde yapılacağı bilgisi kullanıldı.]`
  - Kadro veritabanı kullandıysan → yanıtın sonuna `[KAYNAK:KADRO]` ekle.
  - Hiçbir kaynaktan bilgi kullanmadıysan etiket ekleme.
  - Emin olmadığın veya yüzeysel eşleşen kaynakları KESİNLİKLE etiketleme.

Bağlam:
{context}

Akademik Kadro Bilgileri:
{personnel_text}"""
    
    # Load personnel data to inject into prompt
    personnel_text = "Personel bilgisi bulunamadı."
    personnel_path = os.path.join(PROJECT_ROOT, "data", "personnel_detailed.json")
    if not os.path.exists(personnel_path):
        personnel_path = os.path.join(PROJECT_ROOT, "data", "personnel.json")
        
    if os.path.exists(personnel_path):
        import json
        try:
            with open(personnel_path, 'r', encoding='utf-8') as f:
                d = json.load(f)
                
            def format_dept(dept_name):
                if not dept_name:
                    return 'Belirtilmemiş'
                d = str(dept_name).strip().upper()
                mapping = {
                    'BM': 'Bilgisayar Müh.',
                    'MDBF': 'Mühendislik Fak.',
                    'EE': 'Elektrik-Elektronik Müh.',
                    'EEM': 'Elektrik-Elektronik Müh.',
                    'İİBF': 'İktisadi ve İdari Bil. Fak.',
                    'IIBF': 'İktisadi ve İdari Bil. Fak.',
                    'İME': 'İşletme Müh.',
                    'IME': 'İşletme Müh.',
                    'MM': 'Makine Müh.',
                    'İNM': 'İnşaat Müh.',
                    'INM': 'İnşaat Müh.',
                    'MAM': 'Malzeme Müh.',
                    'MMF': 'Mimarlık Fak.'
                }
                return mapping.get(d, dept_name)

            depts = {}
            for p in d:
                dept = format_dept(p.get('department'))
                if dept:
                    depts[dept] = depts.get(dept, 0) + 1
                    
            stats_text = f"Sistemde toplam {len(d)} akademik/idari personel bulunmaktadır.\nBölümlere Göre Personel Sayıları:\n"
            for dept, count in depts.items():
                stats_text += f"- {dept}: {count} kişi\n"
                
            lines = []
            for p in d:
                dept = format_dept(p.get('department'))
                title = p.get('details', {}).get('title', '')
                office = ', '.join([o['time'] for o in p.get('details', {}).get('office_hours', [])])
                tasks_list = p.get('details', {}).get('tasks', [])
                tasks_str = '; '.join([f"{t.get('duty','')} ({t.get('unit','')})" for t in tasks_list]) if tasks_list else ''
                
                line = f"{title} {p['name']} - {dept} - E-Posta: {p.get('email', '')}"
                if office:
                    line += f" - Ofis Saatleri: {office}"
                if tasks_str:
                    line += f" - Görevler: {tasks_str}"
                lines.append(line)
                
            personnel_text = stats_text + "\n" + "\n".join(lines)
        except Exception as e:
            print(f"Error loading personnel data: {e}")

    qa_system_prompt = qa_system_prompt.replace("{personnel_text}", personnel_text)
    
    qa_prompt = ChatPromptTemplate.from_messages([
        ("system", qa_system_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}")
    ])
    
    question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
    
    # 5. Build the final RAG chain (Direct retrieval to avoid extra LLM call)
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)
    
    return rag_chain
