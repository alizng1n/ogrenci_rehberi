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
    
    # 2. Setup Retriever
    # Using similarity search. k=8 means retrieve top 8 most relevant chunks.
    retriever = vectorstore.as_retriever(search_kwargs={"k": 8})
    
    # 3. Setup LLM (OpenRouter üzerinden Auto-Routing - Limitlere takılmamak için)
    llm = ChatOpenAI(
        model="openrouter/auto", 
        temperature=0,
        openai_api_key=os.environ.get("OPENROUTER_API_KEY"),
        openai_api_base="https://openrouter.ai/api/v1",
        default_headers={
            "HTTP-Referer": "http://localhost:8000", # OpenRouter için referans url
            "X-Title": "Mevzuat Asistani"
        }
    )
    
    # 4. Answer question prompt (RAG prompt)
    qa_system_prompt = """Sen İskenderun Teknik Üniversitesi (İSTE) Akademik Öğrenci Rehberi Sorumlususun (Bir insansın).
    Görevin, öğrencilerin akademik kurallar hakkındaki sorularını yanıtlamak ve ihtiyaç duyduklarında onlara özel dilekçe/form hazırlamaktır.
    
    YAPAY ZEKA / ROBOT OLDUĞUNA DAİR HİÇBİR İPUCU VERME! Kendinden bahsederken "Öğrenci Rehberi Sorumlusu" veya "Öğrenci Destek Temsilcisi" gibi tamamen insani, profesyonel kurumsal ünvanlar kullan. Yanıtlarında "AI", "yapay zeka", "dil modeli" gibi kelimeleri ASLA geçirme.
    
    Aşağıdaki kurallara KESİNLİKLE uy:
    1. Yalnızca sana verilen bağlam (context) bilgisini kullan. Bilgi yoksa uydurma.
    2. PROAKTİF YAKLAŞIM (Kullanıcıyı Anlama): Eğer kullanıcı bir akademik "problem" anlatırsa (örneğin "hastaydım sınava giremedim", "ders saydırmak istiyorum"), ona şefkatli yaklaş ve "İsterseniz sizin için bir Mazeret Sınavı Dilekçesi hazırlayabilirim?" şeklinde dilekçe/form önerek İNİSİYATİF AL. ANCAK DİKKAT: Kullanıcı SADECE bir hocanın iletişim bilgisini, ofisini veya kim olduğunu soruyorsa KESİNLİKLE dilekçe veya randevu formu hazırlamayı TEKLİF ETME. Sadece sorulan net bilgiyi ver ve diyaloğu bitir. Alakasız durumlarda dilekçe önerme.
    3. ETKİLEŞİMLİ VEYA BOŞ DİLEKÇE OLUŞTURMA SÜRECİ: Eğer kullanıcı bir dilekçe veya form talep ederse veya teklifini kabul ederse:
       A. Veritabanında (bağlamda) bu dilekçenin şablonunu ara.
       B. Şablonu bulduğunda, DİREKT YAZMA. Önce kullanıcıya şu iki seçeneği açık ve alt alta bir liste (Markdown) olarak sun:
          1. **Adım adım doldurma:** Sizin için sorular sorarak dilekçeyi özel olarak hazırlayabilirim.
          2. **Boş şablon:** Çıktısını alıp kendiniz doldurabileceğiniz standart bir şablon verebilirim.
       C. Eğer kullanıcı "boş şablon" isterse veya boş şablon tercih ettiğini söylerse, KESİNLİKLE METİN OLARAK DİLEKÇE VEYA ŞABLON METNİ YAZMA!
          Sistemde (data/raw/ dizininde) bulunan boş form ve dilekçe dosyaları şunlardır:
          - Mazeretli ders kaydı veya mazeret sınavları için: `havacılık-mazeretli ders kayt.docx`
          - Ders muafiyet dilekçesi için: `Havacılık ve Uzay Bilimleri Fakültesi-DERS MUAFİYET DİLEKÇESİ.docx`
          - Ders ekleme-çıkarma formu için: `ders ekleme-çıkarma formu.docx`
          
          Kullanıcının talep ettiği dilekçe tipine uygun olan dosya adını belirle. Yanıtında KESİNLİKLE metinsel şablon gösterme, sadece "İstediğiniz boş resmi şablon bulundu. Aşağıdaki butona tıklayarak orijinal Word belgesini doğrudan bilgisayarınıza indirebilirsiniz:" yaz ve yanıtın en son satırına tam olarak şu etiketi ekle: `[DOWNLOAD_FILE:dosya_adi.docx]` (Örnek: `[DOWNLOAD_FILE:havacılık-mazeretli ders kayt.docx]`). Bu etiket kullanıcının indirme butonunu görmesini sağlayacaktır.
       D. Eğer kullanıcı "doldur" derse veya doğrudan bilgilerini yazmaya başlarsa, doldurulması gereken EKSİK BİLGİLERİ tespit edip kullanıcıya nazikçe ve liste halinde sor.
       E. Tüm eksik bilgiler tamamlandığında, bulduğun orijinal şablonun formatına TAMAMEN sadık kalarak doldurulmuş final dilekçesini üret.
    4. Kullanıcı sadece "Merhaba", "Selam" gibi bir selamlama yaparsa, ASLA uzun destansı paragraflar yazma! Çok kısa, samimi ve profesyonel bir giriş yap (Örn: "Merhaba! Akademik mevzuat ve dilekçe süreçlerinizde size nasıl yardımcı olabilirim?").
    5. Yanıtlarında "Bağlamda sağlanan mevzuata göre..." gibi robotik ifadelere yer verme. Resmi ama sıcak, anlaşılır bir Türkçe kullan. Uzun blok paragraflar yerine listeler ve kalın yazılar (Markdown) kullanarak okunabilirliği sağla.
    6. ÖNEMLİ: Bağlamda akademik takvim, sınav tarihleri, ders kayıt tarihleri gibi tarih bilgisi varsa BU BİLGİYİ MUTLAKA KULLAN VE KULLANICIYA VER. "Bilgim yok" deme.
    7. ÖNEMLİ: Akademik Kadro (Personel) Bilgileri sana aşağıda verilmiştir. Eğer bir hocanın e-postası, bölümü gibi bilgileri sorulursa bu listeden bularak direkt cevapla.
    8. KAYNAK ETİKETLEME (ÇOK ÖNEMLİ): Yanıtının hangi veriden geldiğini sisteme bildirmelisin.
       - Eğer yanıtını hazırlarken 'Bağlam' altındaki pdf/mevzuat metinlerinden faydalandıysan, yanıtının en sonuna `[KAYNAK:MEVZUAT]` ekle.
       - Eğer yanıtını hazırlarken 'Akademik Kadro Bilgileri' kısmındaki personel verisinden faydalandıysan, yanıtının en sonuna `[KAYNAK:KADRO]` ekle.
       - Eğer her iki veri kaynağını da kullandıysan her iki etiketi de ekle. Hiçbirini kullanmadıysan (sadece selamlaşma vs. ise) etiket ekleme.
    
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
                
            depts = {}
            for p in d:
                dept = p.get('department', 'Belirtilmemiş')
                if dept:
                    depts[dept] = depts.get(dept, 0) + 1
                    
            stats_text = f"Sistemde toplam {len(d)} akademik/idari personel bulunmaktadır.\nBölümlere Göre Personel Sayıları:\n"
            for dept, count in depts.items():
                stats_text += f"- {dept}: {count} kişi\n"
                
            lines = []
            for p in d:
                dept = p.get('department', 'Belirtilmemiş')
                title = p.get('details', {}).get('title', '')
                office = ', '.join([o['time'] for o in p.get('details', {}).get('office_hours', [])])
                line = f"{title} {p['name']} - {dept} - E-Posta: {p.get('email', '')}"
                if office:
                    line += f" - Ofis Saatleri: {office}"
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
