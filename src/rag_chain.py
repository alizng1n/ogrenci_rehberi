import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
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
    
    # 3. Setup LLM (Google Gemini - hızlı ve günlük 1500 istek)
    llm = ChatGoogleGenerativeAI(
        model="gemini-flash-latest",
        temperature=0,
        google_api_key=os.environ.get("GOOGLE_API_KEY")
    )
    
    # 4. Answer question prompt (RAG prompt)
    qa_system_prompt = """Sen bir üniversitenin akademik mevzuat ve form/dilekçe asistanısın.
    Görevin, öğrencilerin akademik kurallar hakkındaki sorularını yanıtlamak ve ihtiyaç duyduklarında onlara özel dilekçe/form oluşturmaktır.
    
    Aşağıdaki kurallara KESİNLİKLE uy:
    1. Yalnızca sana verilen bağlam (context) bilgisini kullan. Bilgi yoksa uydurma.
    2. PROAKTİF YAKLAŞIM (Kullanıcıyı Anlama): Eğer kullanıcı bir derdini veya akademik problemini anlatırsa (örneğin "hastaydım sınava giremedim", "ders saydırmak istiyorum"), doğrudan kuralları kopyalayıp yapıştırmak yerine ÖNCE kullanıcının niyetini anla. Ona şefkatli ve çözüm odaklı yaklaşarak, "Geçmiş olsun, isterseniz sizin için bir Mazeret Sınavı Dilekçesi hazırlayabilirim?" şeklinde dilekçe/form önerek İNİSİYATİF AL.
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
    
    Bağlam:
    {context}"""
    
    qa_prompt = ChatPromptTemplate.from_messages([
        ("system", qa_system_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}")
    ])
    
    question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
    
    # 5. Build the final RAG chain (Direct retrieval to avoid extra LLM call)
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)
    
    return rag_chain
