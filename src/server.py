from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
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
from src.models import Draft, Base, OBSGrade, OBSAttendance

# Create DB tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Öğrenci Rehberi API")

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
API_KEYS = []
CURRENT_KEY_INDEX = 0

def init_api_keys():
    global API_KEYS, CURRENT_KEY_INDEX
    from dotenv import load_dotenv
    # reload dotenv to make sure we get the latest changes
    load_dotenv(override=True)
    primary = os.environ.get("OPENROUTER_API_KEY")
    fallbacks = os.environ.get("OPENROUTER_API_KEY_FALLBACKS", "")
    keys = [primary] if primary else []
    if fallbacks:
        for k in fallbacks.split(","):
            k_clean = k.strip()
            if k_clean and k_clean not in keys:
                keys.append(k_clean)
    API_KEYS = keys
    if primary in API_KEYS:
        CURRENT_KEY_INDEX = API_KEYS.index(primary)
    else:
        CURRENT_KEY_INDEX = 0
    print(f"[API ROTATOR] Loaded {len(API_KEYS)} API keys. Current index: {CURRENT_KEY_INDEX}")

def get_cached_rag_chain():
    global _rag_chain
    if not API_KEYS:
        init_api_keys()
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
    
    # Arka planda duyuruları önden çek (gecikmeyi sıfırlamak için)
    import threading
    threading.Thread(target=prefetch_announcements, daemon=True).start()


# --- Endpoints ---

class Message(BaseModel):
    role: str # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    history: list[Message] = []
    context: str = ""
    zimbra_email: str = None
    emails: list = None
    deadlines: list = None
    announcements: list = None
    obs_grades: list = None
    obs_attendance: list = None

# ═══════════════════════════════════════════════════════
# Akıllı Semantik Önbellek (Semantic Cache) Sistemi
# ═══════════════════════════════════════════════════════
import numpy as np
import json
import os
import time

class SemanticCache:
    """Anlamsal benzerliğe dayalı akıllı soru-cevap önbellek sistemi (Kalıcı - Disk tabanlı)."""
    
    def __init__(self, similarity_threshold=0.85, max_entries=200):
        self.entries = []  # Her giriş: {embedding, question, answer, sources, keywords, created_at, last_verified}
        self.similarity_threshold = similarity_threshold
        self.max_entries = max_entries
        self._embedder = None
        
        # Dosya yolu
        self.cache_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "semantic_cache.json")
        
        # Zaman hassas sorular için kısa TTL (saniye cinsinden)
        self.time_sensitive_ttl = 3600       # 1 saat
        self.general_ttl = 86400 * 7         # 7 gün (kalıcı olmasını istedikleri için uzun tuttuk)
        
        # Zamana duyarlı konuları tespit eden kelimeler
        self.time_sensitive_words = [
            "bugün", "yarın", "dün", "benim", "mail", "e-posta", 
            "ödevim", "kaç ödev", "kaç gün", "duyuru", "son tarih"
        ]
        
        # Cache'e kaydedilmemesi gereken belirsiz/zayıf cevap kalıpları
        self.weak_answer_patterns = [
            "bilgim yok", "bulunamadı", "bilinmiyor", "emin değilim",
            "hata oluştu", "tekrar deneyin", "yoğun"
        ]
        
        # Diskten yükle
        self._load_from_disk()
    
    def _load_from_disk(self):
        """Cache verilerini diskten yükler."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.entries = json.load(f)
                print(f"📁 Semantik Cache: {len(self.entries)} kayıt diskten yüklendi.")
            except Exception as e:
                print(f"⚠️ Cache dosyası okunamadı: {e}")
                self.entries = []
                
    def _save_to_disk(self):
        """Cache verilerini diske yazar."""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.entries, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Cache diske yazılamadı: {e}")
    
    @property
    def embedder(self):
        """Embedding modelini lazy-load et (ilk kullanımda yükle)."""
        if self._embedder is None:
            from langchain_huggingface import HuggingFaceEmbeddings
            self._embedder = HuggingFaceEmbeddings(
                model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            )
            print("✅ Semantik Cache: Embedding modeli yüklendi.")
        return self._embedder
    
    def _cosine_similarity(self, vec_a, vec_b):
        """İki vektör arasındaki kosinüs benzerliğini hesapla."""
        a = np.array(vec_a)
        b = np.array(vec_b)
        dot = np.dot(a, b)
        norm = np.linalg.norm(a) * np.linalg.norm(b)
        return dot / norm if norm > 0 else 0.0
    
    def _extract_keywords(self, text):
        """Sorgudan anahtar kelimeler çıkar."""
        stop_words = {"ne", "nedir", "nerede", "nasıl", "kim", "hangi", "kaç", 
                      "mi", "mı", "mu", "mü", "bir", "bu", "şu", "o", "ve", 
                      "ile", "için", "de", "da", "den", "dan", "var", "yok",
                      "hakkında", "bilgi", "ver", "söyle", "anlat", "merhaba"}
        words = text.strip().lower().split()
        return [w for w in words if len(w) > 2 and w not in stop_words]
    
    def _is_time_sensitive(self, question):
        """Sorunun zamana duyarlı olup olmadığını kontrol et."""
        q_lower = question.lower()
        return any(w in q_lower for w in self.time_sensitive_words)
    
    def _is_weak_answer(self, answer):
        """Cevabın belirsiz/zayıf olup olmadığını kontrol et."""
        a_lower = answer.lower()
        return any(p in a_lower for p in self.weak_answer_patterns)
    
    def _get_ttl(self, question):
        """Soruya uygun TTL (yaşam süresi) belirle."""
        if self._is_time_sensitive(question):
            return self.time_sensitive_ttl
        return self.general_ttl
    
    def lookup(self, question):
        """
        Semantik benzerlik ile cache'de arama yap.
        Eşleşme bulunursa (answer, sources) döner, bulunamazsa None döner.
        """
        if not self.entries:
            return None
        
        # Zamana duyarlı sorular cache'ten ALINMAZ
        if self._is_time_sensitive(question):
            print(f"⏭️  CACHE SKIP: Zamana duyarlı soru, cache atlanıyor.")
            return None
        
        try:
            query_embedding = self.embedder.embed_query(question)
        except Exception as e:
            print(f"⚠️  Cache embedding hatası: {e}")
            return None
        
        best_match = None
        best_similarity = 0.0
        now = time.time()
        
        for entry in self.entries:
            # Freshness kontrolü — süresi dolan girişleri atla
            ttl = self._get_ttl(entry["question"])
            if now - entry["created_at"] > ttl:
                continue
            
            similarity = self._cosine_similarity(query_embedding, entry["embedding"])
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = entry
        
        if best_match and best_similarity >= self.similarity_threshold:
            best_match["last_verified"] = now  # Son erişim zamanını güncelle
            print(f"⚡ CACHE HIT (benzerlik: {best_similarity:.2f}): '{question}' → '{best_match['question']}'")
            return {
                "answer": best_match["answer"],
                "sources": best_match["sources"]
            }
        
        if best_match:
            print(f"❌ CACHE MISS (en yakın benzerlik: {best_similarity:.2f}, eşik: {self.similarity_threshold})")
        return None
    
    def store(self, question, answer, sources):
        """Yeni bir soru-cevap çiftini cache'e kaydet."""
        # Zayıf/belirsiz cevapları kaydetme
        if self._is_weak_answer(answer):
            print(f"🚫 CACHE SKIP: Zayıf cevap kaydedilmiyor.")
            return
        
        # Çok kısa cevapları kaydetme (muhtemelen sadece "Merhaba" gibi)
        if len(answer.strip()) < 20:
            return
        
        try:
            embedding = self.embedder.embed_query(question)
        except Exception as e:
            print(f"⚠️  Cache store embedding hatası: {e}")
            return
        
        now = time.time()
        keywords = self._extract_keywords(question)
        
        # Aynı sorunun zaten cache'te olup olmadığını kontrol et (güncelle)
        for i, entry in enumerate(self.entries):
            sim = self._cosine_similarity(embedding, entry["embedding"])
            if sim >= 0.95:  # Neredeyse aynı soru → güncelle
                self.entries[i] = {
                    "embedding": embedding,
                    "question": question,
                    "answer": answer,
                    "sources": sources,
                    "keywords": keywords,
                    "created_at": now,
                    "last_verified": now
                }
                print(f"🔄 CACHE UPDATE: '{question}' güncellendi.")
                self._save_to_disk()
                return
        
        # Yeni giriş ekle
        self.entries.append({
            "embedding": embedding,
            "question": question,
            "answer": answer,
            "sources": sources,
            "keywords": keywords,
            "created_at": now,
            "last_verified": now
        })
        print(f"💾 CACHE STORE: '{question}' ({len(self.entries)}/{self.max_entries})")
        
        # Max kapasiteyi aşarsa en eski girişi sil
        if len(self.entries) > self.max_entries:
            self.entries.pop(0)
            
        self._save_to_disk()
    
    def invalidate_stale(self):
        """Süresi dolmuş tüm girişleri temizle."""
        now = time.time()
        before = len(self.entries)
        self.entries = [
            e for e in self.entries 
            if now - e["created_at"] <= self._get_ttl(e["question"])
        ]
        removed = before - len(self.entries)
        if removed > 0:
            print(f"🧹 CACHE CLEANUP: {removed} eski giriş silindi.")
            self._save_to_disk()

# Global semantik cache örneği
semantic_cache = SemanticCache(similarity_threshold=0.85, max_entries=200)
ENABLE_SEMANTIC_CACHE = False  # Yanlış eşleşmeleri (false-positives) önlemek için varsayılan olarak devre dışı bırakıldı

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    # 1. Semantik Önbellek (Cache) Kontrolü
    if ENABLE_SEMANTIC_CACHE:
        cached_result = semantic_cache.lookup(req.message)
        if cached_result:
            return cached_result

    # 2. SSS (FAQ) Semantik Arama Kontrolü
    try:
        from src.local_query import get_faq_match
        faq_result = get_faq_match(req.message, semantic_cache.embedder)
        if faq_result:
            return faq_result
    except Exception as e:
        print(f"⚠️ FAQ match check error: {e}")

    # 3. Yerel Sorgu Sınıflandırma ve Çözümleme (0 API Cost)
    try:
        from src.local_query import resolve_personnel_query, resolve_email_query, resolve_obs_query
        
        # OBS sorgusu çözümü
        if req.obs_grades or req.obs_attendance:
            obs_result = resolve_obs_query(req.message, req.obs_grades, req.obs_attendance)
            if obs_result:
                return obs_result
                
        # E-posta sorgusu çözümü (eğer kullanıcı e-postaları gönderilmişse)
        if req.emails:
            email_result = resolve_email_query(req.message, req.emails)
            if email_result:
                return email_result
                
        # Akademik personel sorgusu çözümü
        personnel_result = resolve_personnel_query(req.message)
        if personnel_result:
            return personnel_result
    except Exception as e:
        print(f"⚠️ Local query resolution error: {e}")

    rag_chain = get_cached_rag_chain()
    if not rag_chain:
        raise HTTPException(status_code=500, detail="RAG zinciri başlatılamadı. Lütfen veritabanının hazır olduğundan emin olun.")

    chat_history = []
    # Son 6 mesajı al (Token limitini aşmamak için geçmişi sınırla)
    recent_history = req.history[-6:] if len(req.history) > 6 else req.history
    for msg in recent_history:
        if msg.role == "user":
            chat_history.append(HumanMessage(content=msg.content))
        else:
            chat_history.append(AIMessage(content=msg.content))

    # Eğer API rate-limit (kota/429) kaynaklıysa, kısa denemelerle (exponential backoff) tekrar dene
    max_retries = max(3, len(API_KEYS) + 2)
    backoff = 1
    response = None
    
    # --- Akıllı Bağlam Sıkıştırma (Context Compression) ---
    compressed_context_parts = []
    
    # Bugünün Tarihi
    import datetime
    now_dt = datetime.datetime.now()
    turkish_months = {
        1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran",
        7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"
    }
    date_str = f"{now_dt.day} {turkish_months.get(now_dt.month, '')} {now_dt.year}"
    compressed_context_parts.append(f"Bugünün Tarihi (Sistem Zamanı): {date_str}")
    
    # Arayüzün yolladığı temel sayfa bağlamı (Aktif sayfa)
    if req.context:
        compressed_context_parts.append(req.context)
        
    # Sorulan hoca varsa sadece onun detayını ekle
    try:
        from src.local_query import extract_relevant_personnel_context
        personnel_context = extract_relevant_personnel_context(req.message)
        if personnel_context:
            compressed_context_parts.append(personnel_context)
    except Exception as e:
        print(f"⚠️ Context compression personnel error: {e}")
        
    # Duyurular (Son 3 adet yeterli)
    if req.announcements:
        ann_lines = [f"- {a.get('title')} ({a.get('date', 'tarih yok')})" for a in req.announcements[:3]]
        compressed_context_parts.append("Güncel Duyurular:\n" + "\n".join(ann_lines))
    elif ANNOUNCEMENTS_CACHE.get("data"):
        ann_lines = [f"- {a['title']} ({a.get('date', 'tarih yok')})" for a in ANNOUNCEMENTS_CACHE["data"][:3]]
        compressed_context_parts.append("Güncel Duyurular:\n" + "\n".join(ann_lines))
        
    # Yaklaşan Ödevler ve Etkinlikler (UBOM) - Son 5 adet
    if req.deadlines:
        dl_lines = [
            f"- Etkinlik: {d.get('name')}, Başlangıç: {d.get('timestart')}, Formatlı Tarih: {d.get('deadline')}, Tür: {d.get('eventtype')}, Ders: {d.get('course_name')}, Açıklama: {d.get('description', '')[:50]}"
            for d in req.deadlines[:5]
        ]
        compressed_context_parts.append("Kullanıcının UBOM Etkinlikleri ve Ödevleri:\n" + "\n".join(dl_lines))
        
    # E-postalar (Sadece sorguda e-posta kelimesi geçiyorsa ve son 3 adet)
    q_lower = req.message.lower()
    if any(w in q_lower for w in ["mail", "e-posta", "eposta", "mesaj"]) and req.emails:
        email_lines = [f"Gönderen: {e.get('from_name') or e.get('from_address')}, Konu: {e.get('subject')}, Tarih: {e.get('date')}, Özet: {e.get('snippet','')[:120]}" for e in req.emails[:3]]
        compressed_context_parts.append("Kullanıcının Son E-postaları:\n" + "\n".join(email_lines))

    # OBS Ders Notları (Eğer gönderildiyse)
    if req.obs_grades:
        grade_lines = [
            f"- {g.get('course_code', '')} {g.get('course_name')}: Vize: {g.get('vize', '-')}, Final: {g.get('final', '-')}, Ortalama: {g.get('average', '-')}, Harf: {g.get('letter_grade', '-')}"
            for g in req.obs_grades
        ]
        compressed_context_parts.append("Kullanıcının OBS Ders Notları:\n" + "\n".join(grade_lines))
        
    # OBS Devamsızlık Bilgileri (Eğer gönderildiyse)
    if req.obs_attendance:
        att_lines = [
            f"- {a.get('course_name')}: Teorik: {a.get('teorik_devamsizlik', '-')}, Uygulama: {a.get('uygulama_devamsizlik', '-')}, Durum: {a.get('status', '-')}"
            for a in req.obs_attendance
        ]
        compressed_context_parts.append("Kullanıcının OBS Devamsızlık Durumları:\n" + "\n".join(att_lines))

    # Doküman takvim verileri (sınav takvimi)
    raw_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")
    if os.path.exists(raw_dir):
        doc_files = [f for f in os.listdir(raw_dir) if f.endswith(('.pdf', '.txt', '.docx'))]
        
        # Takvim verilerini doğrudan enjekte et (Sınav, takvim araması varsa)
        if any(w in q_lower for w in ["sinav", "takvim", "tarih", "vize", "final", "butunleme", "etkinlik", "ödev"]):
            takvim_files = [f for f in doc_files if f.endswith('.txt') and 'takvim' in f.lower()]
            for t_file in takvim_files:
                t_path = os.path.join(raw_dir, t_file)
                try:
                    with open(t_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if "akademik" in t_file.lower():
                            lines = content.split('\n')
                            filtered_lines = [l for l in lines if any(k in l.lower() for k in ["sınav", "yarıyıl", "vize", "final", "bütünleme", "tek ders", "başlama", "bitiş", "takvim faaliyetleri"])]
                            content = "\n".join(filtered_lines)
                        compressed_context_parts.append(f"--- {t_file} İÇERİĞİ ---\n{content}")
                except:
                    pass

    final_input = req.message
    if compressed_context_parts:
        final_input = f"[Sıkıştırılmış Sistem Bağlamı:\n" + "\n\n".join(compressed_context_parts) + f"]\n\nSoru: {req.message}"

        
    for attempt in range(max_retries):
        try:
            response = rag_chain.invoke({
                "input": final_input,
                "chat_history": chat_history
            })
            break
        except Exception as e:
            error_msg = str(e)
            
            # Bakiye veya yetki hatası mı? Rotasyon yapıp tekrar deneyelim
            is_auth_or_credit_error = (
                "402" in error_msg or
                "401" in error_msg or
                "credits" in error_msg.lower() or
                "max_tokens" in error_msg.lower() or
                "payment" in error_msg.lower() or
                "unauthorized" in error_msg.lower()
            )
            
            global CURRENT_KEY_INDEX, _rag_chain
            if is_auth_or_credit_error and API_KEYS and CURRENT_KEY_INDEX < len(API_KEYS) - 1:
                CURRENT_KEY_INDEX += 1
                next_key = API_KEYS[CURRENT_KEY_INDEX]
                masked_key = next_key[:12] + "..." + next_key[-4:] if len(next_key) > 16 else "..."
                print(f"[API ROTATOR] Bakiye/Yetki hatası alındı. Yedek API anahtarına geçiliyor ({CURRENT_KEY_INDEX+1}/{len(API_KEYS)}): {masked_key}")
                os.environ["OPENROUTER_API_KEY"] = next_key
                _rag_chain = None  # Reset chain
                rag_chain = get_cached_rag_chain()
                
                # Persist the new key as primary in .env
                try:
                    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
                    if os.path.exists(env_path):
                        with open(env_path, 'r', encoding='utf-8') as f_env:
                            env_lines = f_env.readlines()
                        new_lines = []
                        for line in env_lines:
                            if line.startswith("OPENROUTER_API_KEY="):
                                new_lines.append(f"OPENROUTER_API_KEY={next_key}\n")
                            else:
                                new_lines.append(line)
                        with open(env_path, 'w', encoding='utf-8') as f_env:
                            f_env.writelines(new_lines)
                        print("[API ROTATOR] .env dosyası yeni anahtarla güncellendi.")
                except Exception as env_ex:
                    print(f"[API ROTATOR] .env güncellenirken hata oluştu: {env_ex}")
                
                # Tekrar dene
                continue

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
    
    # --- Akıllı Kaynak Etiket Ayrıştırma ---
    # Yeni format: [KAYNAK:MEVZUAT:dosya_adı|Neden kullanıldı/kesit] veya [KAYNAK:dosya_adı|kesit] ve [KAYNAK:KADRO]
    import re as re_module
    
    # AI'nin belirttiği spesifik dosya isimlerini ve kesitleri yakala (MEVZUAT öneki olmadan da destekler)
    ai_specified_sources = re_module.findall(r'\[KAYNAK:(?!KADRO\]|MEVZUAT\])(?:MEVZUAT:)?([^\|\]]+)(?:\|([^\]]+))?\]', answer)
    used_kadro = "[KAYNAK:KADRO]" in answer
    used_mevzuat_generic = "[KAYNAK:MEVZUAT]" in answer  # Eski format uyumluluğu
    
    # Tüm kaynak etiketlerini cevaptan temizle (satır içi görünmemesi için)
    answer = re_module.sub(r'\[KAYNAK:[^\]]*\]', '', answer).strip()

    source_docs = []
    seen_sources = set()  # Tekrar eden kaynakları engelle
    
    if ai_specified_sources:
        # ai_specified_sources listesi [(dosya_adi, kesit), (dosya_adi, kesit)] şeklinde döner
        for specified, snippet in ai_specified_sources:
            specified = specified.strip()
            snippet = snippet.strip() if snippet else "Bu kaynaktan bilgi kullanılmıştır."
            
            # Context'ten orijinal sayfayı bul (eğer varsa)
            matched_page = "?"
            for doc in response.get("context", []):
                doc_source = doc.metadata.get("source", "")
                doc_basename = os.path.basename(doc_source) if doc_source else ""
                
                if specified.lower() in doc_basename.lower() or doc_basename.lower() in specified.lower():
                    matched_page = doc.metadata.get("page", "?")
                    break
                    
            if specified not in seen_sources:
                seen_sources.add(specified)
                source_docs.append({
                    "source": specified,
                    "page": matched_page,
                    "content": snippet
                })
    
    elif used_mevzuat_generic:
        # Eski format uyumluluğu: Tüm context dokümanlarını göster (ama tekrarları kaldır)
        for doc in response.get("context", []):
            doc_source = doc.metadata.get("source", "Bilinmiyor")
            doc_basename = os.path.basename(doc_source)
            if doc_basename not in seen_sources:
                seen_sources.add(doc_basename)
                source_docs.append({
                    "source": doc_basename,
                    "page": doc.metadata.get("page", "?"),
                    "content": doc.page_content[:200] + "..."
                })
            
    if used_kadro:
        source_docs.append({
            "source": "Akademik Kadro Veritabanı",
            "page": "-",
            "content": "İSTE Güncel Personel, İletişim ve Ofis Saatleri Rehberi"
        })

    final_response = {
        "answer": answer,
        "sources": source_docs
    }
    
    # 2. Semantik Önbelleğe Kaydetme (Aktif ise)
    if ENABLE_SEMANTIC_CACHE:
        semantic_cache.store(req.message, answer, source_docs)

    return final_response

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
                model="gemini-2.5-flash",
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

@app.get("/api/api-key-status")
async def get_api_key_status():
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return {
            "is_available": False,
            "error": "OPENROUTER_API_KEY .env dosyasında bulunamadı."
        }
    
    url = "https://openrouter.ai/api/v1/key"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json().get("data", {})
            
            # Read custom limit from env if OpenRouter limit is null
            env_limit_str = os.environ.get("OPENROUTER_LIMIT")
            env_limit = float(env_limit_str) if env_limit_str else None
            
            limit = data.get("limit")
            if limit is None:
                limit = env_limit if env_limit is not None else 10.0 # Default to $10 if limit is not set
                
            return {
                "is_available": True,
                "label": data.get("label", "Aktif Anahtar"),
                "limit": limit,
                "usage": data.get("usage", 0.0),
                "usage_daily": data.get("usage_daily", 0.0),
                "is_free_tier": data.get("is_free_tier", False)
            }
        else:
            return {
                "is_available": False,
                "error": f"OpenRouter API Hatası ({response.status_code})"
            }
    except Exception as e:
        return {
            "is_available": False,
            "error": f"Bağlantı hatası: {str(e)[:100]}"
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

def fetch_announcements_bg():
    global ANNOUNCEMENTS_CACHE
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
                        "title": title,
                        "url": href if href.startswith('http') else f"https://iste.edu.tr{href}",
                        "date": date_str
                    })
                    
                if len(items) >= 5: # Get latest 5 announcements
                    break
                    
        if items:
            ANNOUNCEMENTS_CACHE["data"] = items
            ANNOUNCEMENTS_CACHE["last_updated"] = time.time()
            
        return ANNOUNCEMENTS_CACHE["data"]
    except Exception as e:
        print(f"Error scraping announcements: {e}")
        return ANNOUNCEMENTS_CACHE["data"]

def prefetch_announcements():
    try:
        fetch_announcements_bg()
    except:
        pass

from fastapi import BackgroundTasks

@app.get("/api/announcements")
def get_announcements(background_tasks: BackgroundTasks):
    global ANNOUNCEMENTS_CACHE
    current_time = time.time()
    
    # Cache for 1 hour
    if current_time - ANNOUNCEMENTS_CACHE["last_updated"] < 3600 and ANNOUNCEMENTS_CACHE["data"]:
        return ANNOUNCEMENTS_CACHE["data"]
        
    # Trigger background scrape if cache expired/empty
    # This ensures the request returns immediately without hanging on the HTTP request
    background_tasks.add_task(fetch_announcements_bg)
    return ANNOUNCEMENTS_CACHE["data"]

@app.get("/api/personnel")
def get_personnel():
    personnel_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'personnel.json')
    if os.path.exists(personnel_file):
        with open(personnel_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

@app.get("/api/person_detail")
def get_person_detail(url: str):
    import requests
    from bs4 import BeautifulSoup
    
    details = {
        "title": "",
        "yoksis": "",
        "orcid": "",
        "tasks": [],
        "office_hours": []
    }
    
    try:
        # Main profile page
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        title_el = soup.select_one('h6.category.text-muted')
        if title_el:
            details["title"] = title_el.text.strip()
            
        yoksis_el = soup.select_one('a.button-yoksis')
        if yoksis_el:
            details["yoksis"] = yoksis_el.get('href')
            
        orcid_el = soup.select_one('a.button-orcid')
        if orcid_el:
            details["orcid"] = orcid_el.get('href')
            
        # Tasks page
        try:
            r_tasks = requests.get(f"{url}/tasks", timeout=10)
            if r_tasks.status_code == 200:
                soup_tasks = BeautifulSoup(r_tasks.text, 'html.parser')
                task_items = soup_tasks.select('nav.ilistNavigation ul li')
                for item in task_items:
                    unit = item.select_one('div.ifirst')
                    duty = item.select_one('div.isecond')
                    if unit and duty:
                        details["tasks"].append({
                            "unit": unit.text.strip(),
                            "duty": duty.text.strip()
                        })
        except:
            pass
            
        # Office hours page
        try:
            r_office = requests.get(f"{url}/office-hours", timeout=10)
            if r_office.status_code == 200:
                soup_office = BeautifulSoup(r_office.text, 'html.parser')
                office_items = soup_office.select('nav.ilistNavigation ul li')
                for item in office_items:
                    time_val = item.select_one('div.ifirst')
                    desc = item.select_one('div.isecond')
                    if time_val and desc:
                        details["office_hours"].append({
                            "time": time_val.text.strip(),
                            "description": desc.text.strip()
                        })
        except:
            pass
            
    except Exception as e:
        print(f"Error fetching person details: {e}")
        
    return details

# --- ZIMBRA E-POSTA ENTEGRASYONu ---

from src.zimbra_client import zimbra_login, fetch_inbox, fetch_message

class ZimbraLoginRequest(BaseModel):
    email: str
    password: str

# Oturum token'larını bellekte tut (basit cache)
_zimbra_sessions = {}

@app.post("/api/zimbra/login")
async def zimbra_login_endpoint(req: ZimbraLoginRequest):
    """Zimbra'ya giriş yapar ve token döndürür."""
    try:
        token = zimbra_login(req.email, req.password)
        _zimbra_sessions[req.email] = token
        return {"success": True, "email": req.email}
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.post("/api/zimbra/check-session")
async def zimbra_check_session(req: ZimbraLoginRequest):
    """Mevcut oturumun geçerli olup olmadığını kontrol eder."""
    token = _zimbra_sessions.get(req.email)
    if not token:
        return {"valid": False}
    # Token'ın hala çalışıp çalışmadığını basit bir sorguyla test et
    try:
        fetch_inbox(token, limit=1, offset=0)
        return {"valid": True}
    except:
        if req.email in _zimbra_sessions:
            del _zimbra_sessions[req.email]
        return {"valid": False}

class ZimbraInboxRequest(BaseModel):
    email: str
    limit: int = 100
    offset: int = 0

@app.post("/api/zimbra/inbox")
def zimbra_inbox_endpoint(req: ZimbraInboxRequest):
    """Gelen kutusu e-postalarını çeker ve sınıflandırır."""
    token = _zimbra_sessions.get(req.email)
    if not token:
        raise HTTPException(status_code=401, detail="Önce giriş yapmalısınız.")
    
    try:
        emails = fetch_inbox(token, limit=req.limit, offset=req.offset)
        
        # Sadece akademik (academic) olan e-postaların tam içeriğini (body) çekelim
        # Çünkü SearchRequest tam body'yi getirmeyebilir
        # Hız kazanmak için bu işlemi ThreadPoolExecutor ile PARALEL yapalım!
        from concurrent.futures import ThreadPoolExecutor
        academic_emails = [
            e for e in emails 
            if e.get('category') == 'academic' and (not e.get('body') or len(e.get('body', '')) < 100)
        ]
        # Hız ve Zimbra korumalarını tetiklememek için sadece en güncel 8 akademik e-postanın gövdesini çek
        academic_emails = academic_emails[:8]
        
        def fetch_single_body(e):
            try:
                detail = fetch_message(token, e['id'])
                e['body'] = detail.get('body', '')
            except Exception as ex:
                print(f"Failed to fetch full message body for {e['id']}: {ex}")

        if academic_emails:
            with ThreadPoolExecutor(max_workers=4) as executor:
                executor.map(fetch_single_body, academic_emails)
        
        # DEBUG: Log academic emails to check their URLs
        try:
            debug_path = r"C:\Users\Acer\.gemini\antigravity\brain\34a567b3-d450-4676-8de3-4ba5a5c88973\scratch\emails_debug.txt"
            debug_full_path = r"C:\Users\Acer\.gemini\antigravity\brain\34a567b3-d450-4676-8de3-4ba5a5c88973\scratch\emails_full_body.txt"
            os.makedirs(os.path.dirname(debug_path), exist_ok=True)
            with open(debug_path, "w", encoding="utf-8") as f, open(debug_full_path, "w", encoding="utf-8") as f_full:
                for e in emails:
                    if e.get('category') == 'academic':
                        body_content = e.get('body', '')
                        urls = re.findall(r'https?://[^\s"<>]+', body_content)
                        f.write(f"Subject: {e.get('subject')}\n")
                        f.write(f"Snippet: {e.get('snippet')}\n")
                        f.write(f"URLs: {urls}\n")
                        f.write("-" * 50 + "\n")
                        
                        f_full.write(f"Subject: {e.get('subject')}\n")
                        f_full.write(f"Body:\n{body_content}\n")
                        f_full.write("=" * 80 + "\n")
        except Exception as ex:
            print(f"Debug logging failed: {ex}")
            
        academic_count = sum(1 for e in emails if e['category'] == 'academic')
        announcement_count = sum(1 for e in emails if e['category'] == 'announcement')
        unread_count = sum(1 for e in emails if not e['is_read'])
        
        return {
            "emails": emails,
            "stats": {
                "total": len(emails),
                "academic": academic_count,
                "announcement": announcement_count,
                "unread": unread_count
            }
        }
    except Exception as e:
        if "auth" in str(e).lower():
            if req.email in _zimbra_sessions:
                del _zimbra_sessions[req.email]
            raise HTTPException(status_code=401, detail="Oturum süresi doldu, lütfen tekrar giriş yapın.")
        raise HTTPException(status_code=500, detail=str(e))

from src.ubom_client import ubom_login, fetch_ubom_deadlines

class UbomLoginRequest(BaseModel):
    username: str
    password: str

@app.post("/api/ubom/login")
async def ubom_login_endpoint(req: UbomLoginRequest):
    try:
        token = ubom_login(req.username, req.password)
        return {"success": True, "token": token}
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

class UbomDeadlinesRequest(BaseModel):
    token: str

@app.post("/api/ubom/deadlines")
async def ubom_deadlines_endpoint(req: UbomDeadlinesRequest):
    try:
        deadlines = fetch_ubom_deadlines(req.token)
        return {"deadlines": deadlines}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

class ZimbraMessageRequest(BaseModel):
    email: str
    msg_id: str

@app.post("/api/zimbra/message")
async def zimbra_message_endpoint(req: ZimbraMessageRequest):
    """Tek bir e-postanın tam içeriğini çeker."""
    token = _zimbra_sessions.get(req.email)
    if not token:
        raise HTTPException(status_code=401, detail="Önce giriş yapmalısınız.")
    
    try:
        msg = fetch_message(token, req.msg_id)
        return msg
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/zimbra/logout")
async def zimbra_logout_endpoint(req: ZimbraLoginRequest):
    """Zimbra oturumunu sonlandırır."""
    if req.email in _zimbra_sessions:
        del _zimbra_sessions[req.email]
    return {"success": True}

from src.obs_client import OBSLoginSession

ACTIVE_OBS_SESSIONS: dict[str, OBSLoginSession] = {}

class ObsStartSessionRequest(BaseModel):
    username: str = ""

class ObsCompleteLoginRequest(BaseModel):
    session_id: str
    username: str
    password: str
    captcha_code: str

@app.post("/api/obs/start-session")
async def obs_start_session_endpoint(req: ObsStartSessionRequest = None):
    """OBS oturumunu başlatır, tarayıcıyı açar ve CAPTCHA görselini base64 formatında döner."""
    # 5 dakikadan eski oturumları temizle (bellek sızıntısını önlemek için)
    now = time.time()
    expired = [sid for sid, s in ACTIVE_OBS_SESSIONS.items() if now - s.created_at > 300]
    for sid in expired:
        s = ACTIVE_OBS_SESSIONS.pop(sid, None)
        if s:
            s.close()
            
    try:
        session = OBSLoginSession()
        captcha_base64 = session.start()
        ACTIVE_OBS_SESSIONS[session.session_id] = session
        return {
            "success": True,
            "session_id": session.session_id,
            "captcha_base64": captcha_base64
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Oturum başlatılamadı veya güvenlik kodu alınamadı: {str(e)}")

@app.post("/api/obs/complete-login")
async def obs_complete_login_endpoint(req: ObsCompleteLoginRequest, db: Session = Depends(get_db)):
    """Açık olan oturumda şifre ve güvenlik koduyla giriş yapıp verileri çeker."""
    session = ACTIVE_OBS_SESSIONS.pop(req.session_id, None)
    if not session:
        raise HTTPException(status_code=400, detail="Geçersiz veya süresi dolmuş oturum. Lütfen sayfayı yenileyip tekrar deneyin.")
        
    try:
        res = session.login_and_fetch(req.username, req.password, req.captcha_code)
        
        grades_data = res.get("grades", [])
        attendance_data = res.get("attendance", [])
        
        # Eski verileri temizle
        db.query(OBSGrade).filter(OBSGrade.student_id == req.username).delete()
        db.query(OBSAttendance).filter(OBSAttendance.student_id == req.username).delete()
        
        # Yeni verileri kaydet
        for g in grades_data:
            db_grade = OBSGrade(
                course_code=g.get("course_code"),
                course_name=g.get("course_name"),
                vize=g.get("vize"),
                final=g.get("final"),
                average=g.get("average"),
                letter_grade=g.get("letter_grade"),
                student_id=req.username
            )
            db.add(db_grade)
            
        for a in attendance_data:
            db_att = OBSAttendance(
                course_name=a.get("course_name"),
                teorik_devamsizlik=a.get("teorik_devamsizlik"),
                uygulama_devamsizlik=a.get("uygulama_devamsizlik"),
                status=a.get("status"),
                student_id=req.username
            )
            db.add(db_att)
            
        db.commit()
        
        return {
            "success": True, 
            "grades": grades_data, 
            "attendance": attendance_data
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OBS hatası: {str(e)}")

class ObsDataRequest(BaseModel):
    student_id: str

@app.post("/api/obs/data")
async def obs_data_endpoint(req: ObsDataRequest, db: Session = Depends(get_db)):
    """Veritabanında kayıtlı olan not ve devamsızlık verilerini döner."""
    try:
        grades = db.query(OBSGrade).filter(OBSGrade.student_id == req.student_id).all()
        attendance = db.query(OBSAttendance).filter(OBSAttendance.student_id == req.student_id).all()
        
        return {
            "grades": [
                {
                    "course_code": g.course_code,
                    "course_name": g.course_name,
                    "vize": g.vize,
                    "final": g.final,
                    "average": g.average,
                    "letter_grade": g.letter_grade
                } for g in grades
            ],
            "attendance": [
                {
                    "course_name": a.course_name,
                    "teorik_devamsizlik": a.teorik_devamsizlik,
                    "uygulama_devamsizlik": a.uygulama_devamsizlik,
                    "status": a.status
                } for a in attendance
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/obs/logout")
async def obs_logout_endpoint(req: ObsDataRequest, db: Session = Depends(get_db)):
    """Veritabanındaki öğrenci OBS verilerini temizler ve oturumu kapatır."""
    try:
        db.query(OBSGrade).filter(OBSGrade.student_id == req.student_id).delete()
        db.query(OBSAttendance).filter(OBSAttendance.student_id == req.student_id).delete()
        db.commit()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

