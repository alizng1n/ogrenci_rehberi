from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import sys
import os
import re
import traceback
import io
import json
import shutil
import tempfile
from datetime import datetime, timedelta
from google import genai
from fpdf import FPDF
import time
import requests
from bs4 import BeautifulSoup

# Ensure src module is reachable
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.rag_chain import get_rag_chain
from langchain_core.messages import HumanMessage, AIMessage

from src.database import engine, get_db
from src.models import Draft, Base

# Create DB tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Akademik Mevzuat API")

# Setup CORS for local React development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to the frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Gemini GenAI client for document scanning (OCR)
api_key = os.environ.get("GOOGLE_API_KEY")
gemini_client = None
if api_key:
    try:
        gemini_client = genai.Client(api_key=api_key)
        print("Gemini GenAI client initialized successfully.")
    except Exception as e:
        print(f"Warning: Could not initialize Gemini GenAI client: {e}")

# RAG chain'i bir kere başlat ve bellekte tut (her istekte yeniden yükleme!)
_rag_chain = None

def get_cached_rag_chain():
    global _rag_chain
    if _rag_chain is None:
        print("Initializing RAG chain (first time only)...")
        _rag_chain = get_rag_chain()
        print("RAG chain initialized successfully.")
    return _rag_chain

# --- Seed Data Function ---
def seed_db(db: Session):
    if db.query(Draft).first() is None:
        mock_drafts = [
            Draft(
                title="Mazeret Sınavı Dilekçesi",
                description="COM-202 Veritabanı Yönetim Sistemleri dersi için sağlık raporuna dayalı detaylı mazeret sınavı başvuru taslağı.",
                status="ready",
                progress=100,
                updated_at=datetime.utcnow() - timedelta(hours=2)
            ),
            Draft(
                title="Ders Muafiyet Başvurusu",
                description="Önceki kurumdan alınan 3 giriş seviyesi kredisi için ders muafiyeti.",
                status="drafting",
                progress=75
            ),
            Draft(
                title="Erasmus Başvuru Dilekçesi",
                description="Güz dönemi öğrenim hareketliliği başvurusu.",
                status="archived",
                progress=100,
                updated_at=datetime.utcnow() - timedelta(days=180)
            ),
            Draft(
                title="Staj Muafiyet Formu",
                description="Yaz dönemi zorunlu staj muafiyeti.",
                status="finalized",
                progress=100,
                updated_at=datetime.utcnow() - timedelta(days=184)
            ),
            Draft(
                title="Yatay Geçiş Başvurusu",
                description="Merkezi yerleştirme puanı (Ek Madde-1) ile yatay geçiş.",
                status="review",
                progress=100,
                updated_at=datetime.utcnow() - timedelta(days=186)
            ),
        ]
        
        # Ekstra taslaklar (Toplamı 12 yapmak için)
        for i in range(6, 13):
            mock_drafts.append(
                Draft(
                    title=f"Eski Taslak {i}",
                    description="Tamamlanmamış veya iptal edilmiş taslak.",
                    status="archived",
                    progress=10
                )
            )
        db.add_all(mock_drafts)
        db.commit()

# Run seed on startup
@app.on_event("startup")
def startup_event():
    db = next(get_db())
    seed_db(db)
    # RAG chain'i sunucu başlarken hazırla (ilk isteği bekletmemek için)
    get_cached_rag_chain()

# --- Endpoints ---

class Message(BaseModel):
    role: str # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    history: list[Message] = []

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    rag_chain = get_cached_rag_chain()
    if not rag_chain:
        raise HTTPException(status_code=500, detail="RAG zinciri başlatılamadı. Lütfen veritabanının hazır olduğundan emin olun.")

    chat_history = []
    for msg in req.history:
        if msg.role == "user":
            chat_history.append(HumanMessage(content=msg.content))
        else:
            chat_history.append(AIMessage(content=msg.content))

    # Eğer API rate-limit (kota/429) kaynaklıysa, kısa denemelerle (exponential backoff) tekrar dene
    max_retries = 3
    backoff = 1
    response = None
    for attempt in range(max_retries):
        try:
            response = rag_chain.invoke({
                "input": req.message,
                "chat_history": chat_history
            })
            break
        except Exception as e:
            error_msg = str(e)
            is_rate_limit = (
                "429" in error_msg or
                "quota" in error_msg.lower() or
                "rate" in error_msg.lower() or
                "Resource has been exhausted" in error_msg
            )

            if is_rate_limit:
                print(f"[CHAT RATE LIMIT] attempt {attempt+1}/{max_retries}: {error_msg}")
                traceback.print_exc()
                if attempt < max_retries - 1:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                else:
                    return {
                        "answer": "⏳ Yapay zeka servisi şu an yoğun. Lütfen birkaç saniye bekleyip tekrar deneyin.",
                        "sources": []
                    }
            else:
                print(f"[CHAT ERROR] {error_msg}")
                traceback.print_exc()
                return {
                    "answer": f"Bir hata oluştu, lütfen tekrar deneyin. (Detay: {error_msg[:200]})",
                    "sources": []
                }

    # Başarılı yanıt alındıysa, sonucu formatla ve döndür
    if response is None:
        return {"answer": "Bir hata oluştu, lütfen tekrar deneyin.", "sources": []}

    answer = response.get("answer") if isinstance(response, dict) else response["answer"]
    source_docs = []
    for doc in response.get("context", []):
        source_docs.append({
            "source": doc.metadata.get("source", "Bilinmiyor"),
            "page": doc.metadata.get("page", "?"),
            "content": doc.page_content[:200] + "..."
        })

    return {
        "answer": answer,
        "sources": source_docs
    }

# --- DOCUMENT SCAN & PDF GENERATION ENDPOINTS ---

@app.post("/api/scan-document")
async def scan_document(file: UploadFile = File(...)):
    if not gemini_client:
        raise HTTPException(status_code=500, detail="Gemini API istemcisi başlatılamadı. Lütfen GOOGLE_API_KEY ortam değişkenini kontrol edin.")
        
    try:
        # Save uploaded file to a temporary file
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_path = temp_file.name
            
        print(f"Uploading file for scanning: {file.filename} -> {temp_path}")
        
        try:
            # Upload to Gemini (supports images and PDF)
            file_obj = gemini_client.files.upload(file=temp_path)
            
            prompt = """
            Sen İskenderun Teknik Üniversitesi (İSTE) için çalışan yardımcı bir idari yapay zekasın.
            Bu yüklenen sağlık raporunu veya mazeret belgesini dikkatlice incele.
            Belgedeki şu bilgileri kesin olarak tespit et ve bir JSON formatında döndür:
            1. Öğrencinin Adı Soyadı (fullname) - Eğer belgede ad soyad yoksa boş bırak.
            2. Mazeret Tarih Aralığı (date_range) - Örneğin '15.05.2026 - 17.05.2026' veya '15 Mayıs 2026 - 3 Gün'.
            3. Mazeret Gerekçesi / Tanı (reason) - Örneğin 'Gastroenterit', 'Akut Üst Solunum Yolu Enfeksiyonu' vb.
            4. Belgeyi Veren Kurum/Hastane (institution) - Örneğin 'İskenderun Devlet Hastanesi'.

            Ayrıca, bu bilgilere dayanarak İSTE Bölüm Başkanlığına sunulmak üzere resmi ve son derece profesyonel bir 'Mazeret Sınavı Dilekçesi' metni (petition_text) hazırla.
            Dilekçe metni şu şablona benzer resmi bir dille yazılmalıdır:
            'Fakülteniz/Yüksekokulunuz ilgili bölümü öğrencisiyim. [Tarih Aralığı] tarihleri arasında [Kurum Adı] tarafından verilen ekteki raporda belirtilen mazeretim (Tanı: [Tanı]) nedeniyle [Ders Kodu] kodlu ve [Ders Adı] isimli dersin yarıyıl içi (vize) sınavına katılamadım. Ekli mazeret belgemin kabul edilerek ilgili ders/dersler için mazeret sınav hakkı tanınması hususunda gereğini saygılarımla arz ederim.'

            DÖNDÜRÜLECEK JSON FORMATI:
            {
              "fullname": "Tespit edilen öğrenci adı soyadı",
              "date_range": "Tespit edilen tarih aralığı",
              "reason": "Tespit edilen tanı/gerekçe",
              "institution": "Tespit edilen kurum",
              "petition_title": "Mazeret Sınavı Başvuru Dilekçesi",
              "petition_text": "Hazırladığın profesyonel dilekçe gövde metni"
            }

            UYARI: Çıktıda JSON bloğu dışında HİÇBİR açıklama veya markdown kodu (örneğin ```json ... ```) OLMAMALIDIR. Sadece saf JSON string döndür.
            """
            
            print("File uploaded. Generating content from Gemini...")
            response = gemini_client.models.generate_content(
                model="gemini-flash-latest",
                contents=[file_obj, prompt]
            )
            
            response_text = response.text
            print(f"Gemini response: {response_text}")
            
            # Clean and parse JSON
            extracted_data = {}
            match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if match:
                try:
                    extracted_data = json.loads(match.group(0))
                except Exception as json_err:
                    print(f"Failed to parse JSON using regex: {json_err}")
            
            if not extracted_data:
                # Fallback if parsing completely fails
                extracted_data = {
                    "fullname": "",
                    "date_range": "",
                    "reason": "Mazeret Raporu",
                    "institution": "Sağlık Kurumu",
                    "petition_title": "Mazeret Sınavı Başvuru Dilekçesi",
                    "petition_text": response_text
                }
                
            return extracted_data
            
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Belge tarama sırasında hata oluştu: {str(e)}")

class SaveDraftRequest(BaseModel):
    title: str
    fullname: str
    date_range: str
    reason: str
    institution: str

@app.post("/api/save-draft")
async def save_draft(req: SaveDraftRequest, db: Session = Depends(get_db)):
    try:
        new_draft = Draft(
            title=req.title,
            description=f"{req.fullname} adlı öğrencinin {req.date_range} tarihlerindeki mazeret belgesine dayalı dilekçesi ({req.reason} - {req.institution}).",
            status="ready",
            progress=100,
            updated_at=datetime.utcnow()
        )
        db.add(new_draft)
        db.commit()
        db.refresh(new_draft)
        return {"status": "success", "draft_id": new_draft.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class GeneratePDFRequest(BaseModel):
    title: str
    fullname: str
    student_id: str
    phone: str
    department: str
    course_code: str
    course_name: str
    reason: str
    date_range: str
    institution: str
    petition_text: str

class PetitionPDF(FPDF):
    def header(self):
        pass

@app.post("/api/generate-pdf")
async def generate_pdf(req: GeneratePDFRequest):
    try:
        pdf = PetitionPDF()
        pdf.add_page()
        
        # Load Arial font supporting Turkish
        font_path = r"C:\Windows\Fonts\arial.ttf"
        pdf.add_font("ArialTR", "", font_path)
        pdf.add_font("ArialTR", "B", font_path)
        
        pdf.set_font("ArialTR", "B", 14)
        pdf.cell(0, 10, "İSKENDERUN TEKNİK ÜNİVERSİTESİ", new_x="LMARGIN", new_y="NEXT", align="C")
        
        pdf.set_font("ArialTR", "B", 12)
        pdf.cell(0, 8, f"{req.department.upper()} DEKANLIĞINA / MÜDÜRLÜĞÜNE", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.cell(0, 6, "İskenderun", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(10)
        
        # Date (Right aligned)
        pdf.set_font("ArialTR", "", 10)
        current_date = datetime.now().strftime("%d/%m/%Y")
        pdf.cell(0, 6, f"Tarih: {current_date}", new_x="LMARGIN", new_y="NEXT", align="R")
        pdf.ln(5)
        
        # Student Info block (Left aligned)
        pdf.set_font("ArialTR", "B", 10)
        pdf.cell(40, 6, "Öğrenci Adı Soyadı : ", align="L")
        pdf.set_font("ArialTR", "", 10)
        pdf.cell(0, 6, req.fullname, new_x="LMARGIN", new_y="NEXT", align="L")
        
        pdf.set_font("ArialTR", "B", 10)
        pdf.cell(40, 6, "Öğrenci Numarası   : ", align="L")
        pdf.set_font("ArialTR", "", 10)
        pdf.cell(0, 6, req.student_id, new_x="LMARGIN", new_y="NEXT", align="L")
        
        pdf.set_font("ArialTR", "B", 10)
        pdf.cell(40, 6, "Bölümü             : ", align="L")
        pdf.set_font("ArialTR", "", 10)
        pdf.cell(0, 6, req.department, new_x="LMARGIN", new_y="NEXT", align="L")
        
        pdf.set_font("ArialTR", "B", 10)
        pdf.cell(40, 6, "Telefon Numarası   : ", align="L")
        pdf.set_font("ArialTR", "", 10)
        pdf.cell(0, 6, req.phone, new_x="LMARGIN", new_y="NEXT", align="L")
        pdf.ln(10)
        
        # Subject
        pdf.set_font("ArialTR", "B", 11)
        pdf.cell(20, 6, "KONU : ", align="L")
        pdf.set_font("ArialTR", "", 11)
        pdf.cell(0, 6, f"Mazeret Sınavı Talebi ({req.course_code} - {req.course_name})", new_x="LMARGIN", new_y="NEXT", align="L")
        pdf.ln(8)
        
        # Body paragraph
        pdf.set_font("ArialTR", "", 11)
        
        body = req.petition_text
        if not body:
            body = f"Fakülteniz/Yüksekokulunuz {req.department} Bölümü {req.student_id} numaralı öğrencisiyim. " \
                   f"Öğrenim görmekte olduğum {req.course_code} kodlu ve '{req.course_name}' isimli dersin yarıyıl içi (vize) sınavına, " \
                   f"{req.date_range} tarihlerini kapsayan ve {req.institution} tarafından verilen ekteki mazeret/sağlık raporunda belirtilen mazeretim nedeniyle katılamadım. " \
                   f"Mevzuat gereğince ilgili ders/dersler için mazeret sınav hakkı tanınması hususunda gereğini ve bilgilerinizi saygılarımla arz ederim."
                   
        pdf.multi_cell(0, 7, body, new_x="LMARGIN", new_y="NEXT", align="J")
        pdf.ln(15)
        
        # Signature block (Right aligned)
        pdf.set_font("ArialTR", "B", 11)
        pdf.cell(110) # spacing to push right
        pdf.cell(0, 6, "İmza", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.cell(110)
        pdf.set_font("ArialTR", "", 11)
        pdf.cell(0, 6, req.fullname, new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(15)
        
        # Enclosures (Left aligned)
        pdf.set_font("ArialTR", "B", 10)
        pdf.cell(0, 6, "EKLER:", new_x="LMARGIN", new_y="NEXT", align="L")
        pdf.set_font("ArialTR", "", 10)
        pdf.cell(0, 6, f"1. Mazeret Belgesi / Rapor Fotokopisi ({req.institution} onaylı, {req.date_range} tarihli)", new_x="LMARGIN", new_y="NEXT", align="L")
        
        pdf_bytes = pdf.output()
        
        return StreamingResponse(
            io.BytesIO(pdf_bytes), 
            media_type="application/pdf", 
            headers={"Content-Disposition": f"attachment; filename=dilekce_{req.student_id}.pdf"}
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"PDF oluşturma hatası: {str(e)}")

# --- End of Scan and PDF endpoints ---

@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_db)):
    total = db.query(Draft).count()
    ready = db.query(Draft).filter(Draft.status == "ready").count()
    review = db.query(Draft).filter(Draft.status == "review").count()
    
    # Calculate AI Efficiency: Simple mock metric (94 + up to 5 based on some ratio)
    # Just to show dynamic but high number
    ai_efficiency = 90 + min(total, 9)
    
    return {
        "total": total,
        "ready": ready,
        "review": review,
        "efficiency": ai_efficiency
    }

@app.get("/api/drafts")
async def get_drafts(db: Session = Depends(get_db)):
    drafts = db.query(Draft).order_by(Draft.updated_at.desc()).all()
    
    result = []
    for d in drafts:
        result.append({
            "id": d.id,
            "title": d.title,
            "description": d.description,
            "status": d.status,
            "progress": d.progress,
            "updated_at": d.updated_at.isoformat()
        })
    return result

@app.get("/api/sources")
async def get_sources():
    raw_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")
    if not os.path.exists(raw_dir):
        return []
    
    files = []
    for f in os.listdir(raw_dir):
        if f.endswith(('.pdf', '.txt', '.docx')):
            files.append(f)
    return files

@app.get("/api/download-source")
async def download_source(filename: str):
    from fastapi.responses import FileResponse
    import urllib.parse
    
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    raw_dir = os.path.join(project_root, "data", "raw")
    archive_dir = os.path.join(project_root, "data", "archive")
    
    # Fuzzy matcher helper
    def find_file(directory: str, target: str) -> str:
        if not os.path.exists(directory):
            return None
            
        t_lower = target.lower()
        # Clean target string for alphanumeric comparison
        t_clean = re.sub(r'[^a-z0-9]', '', t_lower)
        
        for f in os.listdir(directory):
            f_lower = f.lower()
            f_clean = re.sub(r'[^a-z0-9]', '', f_lower)
            
            # Check direct or cleaned matching
            if t_clean in f_clean or f_clean in t_clean:
                return f
                
            # Heuristics for special Turkish university forms with character encoding issues
            if "mazeret" in t_lower and "mazeret" in f_lower:
                return f
            if "muafiyet" in t_lower and "muaf" in f_lower:
                return f
            if "ekleme" in t_lower and "ekleme" in f_lower:
                return f
        return None

    # Search in data/raw/
    matched_name = find_file(raw_dir, filename)
    if matched_name:
        file_path = os.path.join(raw_dir, matched_name)
        return FileResponse(
            file_path, 
            filename=filename, # Return the clean UTF-8 name to the user's browser
            headers={"Content-Disposition": f"attachment; filename={urllib.parse.quote(filename)}"}
        )
        
    # Search in data/archive/
    matched_archive = find_file(archive_dir, filename)
    if matched_archive:
        file_path = os.path.join(archive_dir, matched_archive)
        return FileResponse(
            file_path, 
            filename=filename,
            headers={"Content-Disposition": f"attachment; filename={urllib.parse.quote(filename)}"}
        )
        
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

ANNOUNCEMENTS_CACHE = {
    "data": [],
    "last_updated": 0
}

@app.get("/api/announcements")
async def get_announcements():
    global ANNOUNCEMENTS_CACHE
    current_time = time.time()
    
    # Cache for 1 hour
    if current_time - ANNOUNCEMENTS_CACHE["last_updated"] < 3600 and ANNOUNCEMENTS_CACHE["data"]:
        return ANNOUNCEMENTS_CACHE["data"]
        
    try:
        r = requests.get('https://iste.edu.tr/duyuru-merkezi/oidb', timeout=10)
        r.encoding = 'utf-8'
        soup = BeautifulSoup(r.text, 'html.parser')
        
        items = []
        pattern = re.compile(r'duyuru-merkezi/oidb/\d{4}/\d{2}/\d{2}/\d+')
        seen = set()
        
        for a in soup.find_all('a'):
            href = a.get('href', '')
            if pattern.search(href):
                title = a.text.strip()
                if not title:
                    title = ' '.join(a.stripped_strings)
                    
                if len(title) > 5 and href not in seen:
                    seen.add(href)
                    # Try to find date from href
                    date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', href)
                    date_str = ""
                    if date_match:
                        date_str = f"{date_match.group(3)}.{date_match.group(2)}.{date_match.group(1)}"
                        
                    items.append({
                        'title': title,
                        'href': href,
                        'date': date_str
                    })
                    
                if len(items) >= 5: # Get latest 5 announcements
                    break
                    
        if items:
            ANNOUNCEMENTS_CACHE["data"] = items
            ANNOUNCEMENTS_CACHE["last_updated"] = current_time
            
        return ANNOUNCEMENTS_CACHE["data"]
    except Exception as e:
        print(f"Error scraping announcements: {e}")
        return ANNOUNCEMENTS_CACHE["data"]
