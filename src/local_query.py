import os
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import json
import re
import numpy as np
from difflib import SequenceMatcher

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERSONNEL_FILE = os.path.join(PROJECT_ROOT, "data", "personnel_detailed.json")
FAQ_FILE = os.path.join(PROJECT_ROOT, "data", "faq.json")

# Pre-load data in memory for speed
_personnel_data = []
_faq_data = []
_faq_embeddings = []  # To be cached on first request

def load_personnel():
    global _personnel_data
    if not _personnel_data:
        path = PERSONNEL_FILE
        if not os.path.exists(path):
            path = os.path.join(PROJECT_ROOT, "data", "personnel.json")
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    _personnel_data = json.load(f)
                print(f"👥 Local Query: {len(_personnel_data)} personel kaydı yüklendi.")
            except Exception as e:
                print(f"⚠️ Personel verisi yüklenemedi: {e}")
    return _personnel_data

def load_faq():
    global _faq_data
    if not _faq_data:
        if os.path.exists(FAQ_FILE):
            try:
                with open(FAQ_FILE, 'r', encoding='utf-8') as f:
                    _faq_data = json.load(f)
                print(f"❓ Local Query: {len(_faq_data)} SSS (FAQ) kaydı yüklendi.")
            except Exception as e:
                print(f"⚠️ FAQ verisi yüklenemedi: {e}")
    return _faq_data

def normalize_turkish(text):
    if not text:
        return ""
    text = text.replace('İ', 'i').replace('I', 'i').replace('ı', 'i')
    text = text.lower()
    text = text.replace('ş', 's')
    text = text.replace('ğ', 'g')
    text = text.replace('ü', 'u')
    text = text.replace('ö', 'o')
    text = text.replace('ç', 'c')
    text = text.replace('â', 'a')
    text = text.replace('\u0307', '')  # Remove combining dot above
    # Remove punctuation
    text = re.sub(r'[^\w\s]', ' ', text)
    return " ".join(text.split())

def find_best_person(query, personnel_list):
    """
    Fuzzy searches for a person's name in the query.
    Returns the person object and a match score.
    """
    query_norm = normalize_turkish(query)
    query_words = query_norm.split()
    
    best_person = None
    best_score = 0.0
    
    for p in personnel_list:
        name_norm = normalize_turkish(p.get("name", ""))
        name_parts = name_norm.split()
        if not name_parts:
            continue
            
        # 1. Exact match of full name in query
        if name_norm in query_norm:
            score = 1.0 + (len(name_parts) * 0.1) # Boost longer matching names
            if score > best_score:
                best_score = score
                best_person = p
            continue
            
        # 2. Token overlap score
        matches = 0
        for part in name_parts:
            # Match parts (length >= 2)
            if len(part) >= 2:
                if len(part) <= 3:
                    # Strict exact word match for short name tokens (e.g., Ali, Cem, Koç)
                    if part in query_words:
                        matches += 1
                else:
                    # Prefix match with <= 2 characters suffix for longer tokens (e.g., Kadir -> Kadir'in)
                    if any(w == part or (w.startswith(part) and len(w) <= len(part) + 2) for w in query_words):
                        matches += 1
                
        if matches > 0:
            # Ratio of matched parts to total parts of name
            score = matches / len(name_parts)
            # Add small boost for longer names to resolve ties
            score += matches * 0.05
            if score > best_score:
                best_score = score
                best_person = p
                
    # Return best match if score is sufficiently high (at least one name token matches)
    # E.g., if query is "Kadir hocanın..." and name is "Kadir Tohma", score = 1/2 + 0.05 = 0.55
    if best_score >= 0.35:
        return best_person, best_score
    return None, 0.0

def resolve_personnel_query(query):
    """
    Checks if query is about a teacher's office hours, email, or details.
    Returns a natural response if matched, otherwise None.
    """
    personnel = load_personnel()
    if not personnel:
        return None
        
    person, score = find_best_person(query, personnel)
    if not person:
        return None
        
    q_norm = normalize_turkish(query)
    name = person["name"]
    details = person.get("details", {})
    title = details.get("title", "").strip()
    title_prefix = f"{title} " if title else ""
    email = person.get("email", "").strip()
    
    # Format department
    dept = person.get("department", "")
    dept_mapping = {
        'BM': 'Bilgisayar Mühendisliği',
        'MDBF': 'Mühendislik Fakültesi',
        'EE': 'Elektrik-Elektronik Mühendisliği',
        'EEM': 'Elektrik-Elektronik Mühendisliği',
        'İİBF': 'İktisadi ve İdari Bilimler Fakültesi',
        'IIBF': 'İktisadi ve İdari Bilimler Fakültesi',
        'İME': 'İşletme Mühendisliği',
        'IME': 'İşletme Mühendisliği',
        'MM': 'Makine Mühendisliği',
        'İNM': 'İnşaat Mühendisliği',
        'INM': 'İnşaat Mühendisliği',
        'MAM': 'Malzeme Mühendisliği',
        'MMF': 'Mimarlık Fakültesi'
    }
    dept_name = dept_mapping.get(dept.strip().upper(), dept)
    dept_str = f" ({dept_name} Bölümü)" if dept_name else ""

    # Check Intents
    is_office_hours = any(w in q_norm for w in ["ofis", "saat", "gorusme", "bulurum", "nerede", "oda", "oda no", "ziyaret"])
    is_email = any(w in q_norm for w in ["mail", "e-posta", "eposta", "iletisim", "adres"])
    
    office_hours_list = details.get("office_hours", [])
    office_hours_str = ""
    if office_hours_list:
        office_hours_str = ", ".join([h.get("time", "") for h in office_hours_list if h.get("time")])
        
    # Default to office hours query or general query
    if is_office_hours or (not is_email):
        if office_hours_str:
            answer = f"**{title_prefix}{name}** hocanın{dept_str} ofis saatleri **{office_hours_str}** arasındadır."
        else:
            answer = f"**{title_prefix}{name}** hocanın{dept_str} sistemde kayıtlı belirli bir ofis saati bulunmamaktadır."
            
        if email:
            answer += f" Görüşmeye gitmeden önce kendisine **{email}** adresi üzerinden e-posta göndererek randevu almanız faydalı olabilir."
            
        # Add tasks/duties if available
        tasks = details.get("tasks", [])
        if tasks:
            duties = [f"{t.get('duty','')} ({t.get('unit','')})" for t in tasks if t.get('duty')]
            if duties:
                answer += f"\n\nHocanın üstlendiği idari görevler: {', '.join(duties)}."
                
        return {
            "answer": answer,
            "sources": [{"source": "Akademik Kadro Veritabanı", "page": "-", "content": f"{name} İletişim ve Ofis Saatleri"}]
        }
        
    elif is_email:
        if email:
            answer = f"**{title_prefix}{name}** hocanın e-posta adresi **{email}** şeklindedir."
            if office_hours_str:
                answer += f" Ayrıca kendisiyle görüşmek isterseniz ofis saatleri **{office_hours_str}** arasındadır."
        else:
            answer = f"**{title_prefix}{name}** hocanın e-posta adresi sistemde kayıtlı değildir."
            
        return {
            "answer": answer,
            "sources": [{"source": "Akademik Kadro Veritabanı", "page": "-", "content": f"{name} İletişim Bilgileri"}]
        }
        
    return None

def resolve_email_query(query, emails):
    """
    Finds the latest email from a specific teacher requested by the user.
    """
    if not emails:
        return None
        
    q_norm = normalize_turkish(query)
    
    # Check if query is about email retrieval (e.g., "mail atmış", "mail yollamış", "hangi maili")
    is_mail_query = any(w in q_norm for w in ["mail", "e-posta", "eposta", "gonder", "yolla", "mesaj"])
    if not is_mail_query:
        return None
        
    # Find teacher names from the query using the personnel database
    personnel = load_personnel()
    if not personnel:
        return None
        
    person, score = find_best_person(query, personnel)
    if not person:
        return None
        
    name = person["name"]
    name_norm = normalize_turkish(name)
    name_parts = name_norm.split()
    
    # Find matching emails
    matching_emails = []
    for email_obj in emails:
        # Check from_name or from_address or body
        from_name = normalize_turkish(email_obj.get("from_name", ""))
        from_address = normalize_turkish(email_obj.get("from_address", ""))
        
        # Match if full name or any of the name parts match the sender
        if name_norm in from_name or name_norm in from_address or any(part in from_name for part in name_parts if len(part) > 2):
            matching_emails.append(email_obj)
            
    if not matching_emails:
        return {
            "answer": f"Zimbra gelen kutunuzda **{name}** hocadan gelen herhangi bir e-posta bulunamadı.",
            "sources": [{"source": "Zimbra E-Posta Entegrasyonu", "page": "-", "content": f"{name} için mail araması"}]
        }
        
    # Sort by date (latest first) - assuming date is in string format, let's reverse to get latest
    # The list is usually already sorted or we can just sort/take the first one
    latest_email = matching_emails[0]
    
    subject = latest_email.get("subject", "Konu Yok")
    date_str = latest_email.get("date", "")
    snippet = latest_email.get("snippet", latest_email.get("body", "İçerik bulunamadı."))
    # Clean HTML from snippet/body
    snippet = re.sub(r'<[^>]+>', ' ', snippet)
    snippet = " ".join(snippet.split())
    if len(snippet) > 250:
        snippet = snippet[:250] + "..."
        
    answer = f"**{name}** hocadan gelen son e-posta **\"{subject}\"** başlığıyla **{date_str}** tarihinde gönderilmiştir.\n\n"
    answer += f"**E-posta İçeriği/Özeti:**\n> {snippet}\n\n"
    answer += f"E-postanın tamamını okumak için yan menüden **Gelen E-postalar** sayfasına göz atabilirsiniz."
    
    return {
        "answer": answer,
        "sources": [{"source": "Zimbra E-Posta Entegrasyonu", "page": "-", "content": f"Gönderen: {name}, Konu: {subject}"}]
    }

def get_faq_match(query, embedder):
    """
    Uses semantic search (embeddings) to find matches in the pre-defined FAQ list.
    """
    global _faq_embeddings
    faq = load_faq()
    if not faq or not embedder:
        return None
        
    # Pre-embed FAQs if not cached
    if not _faq_embeddings:
        try:
            print("🧠 Pre-embedding FAQs...")
            questions = [item["question"] for item in faq]
            _faq_embeddings = embedder.embed_documents(questions)
            print("🧠 FAQ embedding complete.")
        except Exception as e:
            print(f"⚠️ FAQ embedding failed: {e}")
            return None
            
    try:
        query_emb = embedder.embed_query(query)
    except Exception as e:
        print(f"⚠️ Query embedding failed: {e}")
        return None
        
    # Cosine Similarity
    best_idx = -1
    best_sim = 0.0
    
    for idx, faq_emb in enumerate(_faq_embeddings):
        a = np.array(query_emb)
        b = np.array(faq_emb)
        dot = np.dot(a, b)
        norm = np.linalg.norm(a) * np.linalg.norm(b)
        sim = dot / norm if norm > 0 else 0.0
        
        if sim > best_sim:
            best_sim = sim
            best_idx = idx
            
    # If match exceeds similarity threshold (0.88), return pre-defined answer
    if best_sim >= 0.88 and best_idx != -1:
        matched_faq = faq[best_idx]
        print(f"🎯 FAQ SEMANTIC HIT (sim: {best_sim:.2f}): '{query}' → '{matched_faq['question']}'")
        return {
            "answer": matched_faq["answer"],
            "sources": [{"source": "Sıkça Sorulan Sorular (SSS)", "page": "-", "content": matched_faq["question"]}]
        }
        
    return None

def extract_relevant_personnel_context(query):
    """
    Context Compression: Extracts only the database entry of the mentioned personnel 
    to avoid passing the entire 348KB personnel list to the LLM.
    """
    personnel = load_personnel()
    if not personnel:
        return ""
        
    person, score = find_best_person(query, personnel)
    if not person:
        return ""
        
    name = person.get("name", "")
    dept = person.get("department", "")
    email = person.get("email", "")
    details = person.get("details", {})
    title = details.get("title", "")
    office_hours = ", ".join([h.get("time", "") for h in details.get("office_hours", [])])
    tasks = "; ".join([f"{t.get('duty','')} ({t.get('unit','')})" for t in details.get("tasks", [])])
    
    context = f"Sorguyla İlgili Personel Bilgisi:\n- İsim: {title} {name}\n- Bölüm: {dept}\n- E-posta: {email}\n"
    if office_hours:
        context += f"- Ofis Saatleri: {office_hours}\n"
    if tasks:
        context += f"- Görevler: {tasks}\n"
        
    return context

def resolve_obs_query(query, grades, attendance):
    """
    Kullanıcının OBS notları ve devamsızlık durumları hakkındaki sorularını 
    yerel veri üzerinden anında yanıtlar.
    """
    if not grades and not attendance:
        return None
        
    q_norm = normalize_turkish(query)
    
    # Simülasyon/Geçme hesaplama sorularını yapay zeka (LLM) beyin çözmeli
    is_simulation = any(w in q_norm for w in ["almaliyim", "alirsam", "gecerim", "gecmek", "gecebileyim", "gecebilirim", "lazim", "hesapla", "simule", "kurtarir"])
    if is_simulation:
        return None
        
    # 1. Not/Sınav Sorguları
    is_grades_query = any(w in q_norm for w in ["not", "vize", "final", "ortalama", "harf", "ders notu", "notlar"])
    # 2. Devamsızlık Sorguları
    is_attendance_query = any(w in q_norm for w in ["devam", "devamsizlik", "devamsizligim", "kac gun", "kac saat", "sinir"])
    
    if is_grades_query:
        if not grades:
            return {
                "answer": "OBS sisteminden çekilmiş herhangi bir ders notu kaydınız bulunmamaktadır.",
                "sources": [{"source": "İSTE OBS Entegrasyonu", "page": "-", "content": "Ders notu araması"}]
            }
            
        answer = "**OBS Sisteminden Alınan Ders Notlarınız:**\n\n"
        answer += "| Ders Adı | Vize | Final | Ortalama | Harf Notu |\n"
        answer += "| :--- | :---: | :---: | :---: | :---: |\n"
        for g in grades:
            answer += f"| {g.get('course_name', '')} | {g.get('vize', '-')} | {g.get('final', '-')} | {g.get('average', '-')} | **{g.get('letter_grade', '-')}** |\n"
            
        return {
            "answer": answer,
            "sources": [{"source": "İSTE OBS Entegrasyonu", "page": "-", "content": "Güncel Not Durumu"}]
        }
        
    elif is_attendance_query:
        if not attendance:
            return {
                "answer": "OBS sisteminden çekilmiş herhangi bir devamsızlık kaydınız bulunmamaktadır.",
                "sources": [{"source": "İSTE OBS Entegrasyonu", "page": "-", "content": "Devamsızlık araması"}]
            }
            
        answer = "**OBS Sisteminden Alınan Devamsızlık Durumlarınız:**\n\n"
        answer += "| Ders Adı | Teorik Devamsızlık | Uygulama Devamsızlık | Durum |\n"
        answer += "| :--- | :---: | :---: | :---: |\n"
        for a in attendance:
            status = a.get('status', 'Belirtilmemiş')
            status_bold = f"**{status}**" if "kaldı" in status.lower() or "sınır" in status.lower() else status
            answer += f"| {a.get('course_name', '')} | {a.get('teorik_devamsizlik', '-')} | {a.get('uygulama_devamsizlik', '-')} | {status_bold} |\n"
            
        return {
            "answer": answer,
            "sources": [{"source": "İSTE OBS Entegrasyonu", "page": "-", "content": "Güncel Devamsızlık Durumu"}]
        }
        
    return None
