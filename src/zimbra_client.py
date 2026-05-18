"""
Zimbra E-Posta Entegrasyonu
İSTE Zimbra SOAP API ile iletişim kurarak gelen kutusu e-postalarını çeker ve sınıflandırır.
"""
import json
import os
import re
from datetime import datetime
from pythonzimbra.communication import Communication
from pythonzimbra.tools import auth

ZIMBRA_SOAP_URL = "https://eposta.iste.edu.tr/service/soap"

# Akademisyen e-posta listesini personnel.json'dan yükle
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _load_academic_emails():
    """Personnel veritabanından tüm akademisyen e-postalarını yükler."""
    emails = set()
    for fname in ["personnel_detailed.json", "personnel.json"]:
        path = os.path.join(PROJECT_ROOT, "data", fname)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for p in data:
                    email = p.get('email', '').strip().lower()
                    if email:
                        emails.add(email)
            except Exception:
                pass
            break
    return emails

# Duyuru kaynağı olarak bilinen e-posta kalıpları
ANNOUNCEMENT_PATTERNS = [
    "duyuru@", "bilgi@", "info@", "announcement@",
    "no-reply@", "sistem@", "system@",
    "haber@", "bulten@", "destek@",
    "ogrenciisleri@", "kayit@", "sinav@"
]

# Akademik kaynak olarak sayılacak özel adresler
ACADEMIC_SPECIAL = [
    "ubom.noreply@iste.edu.tr"
]

def classify_email(from_address: str, academic_emails: set) -> str:
    """
    E-postayı sınıflandırır.
    Returns: 'academic' | 'announcement' | 'other'
    """
    if not from_address:
        return 'other'
    
    addr = from_address.lower().strip()
    
    # Açılı parantez içinde gerçek e-posta adresini bul
    match = re.search(r'<(.+?)>', addr)
    if match:
        addr = match.group(1)
    
    # Özel akademik adresler (ubom.noreply vb.)
    if addr in ACADEMIC_SPECIAL:
        return 'academic'
    
    # Akademisyen listesinde mi? (önce kontrol et)
    if addr in academic_emails:
        return 'academic'
    
    # Duyuru kalıplarını kontrol et
    for pattern in ANNOUNCEMENT_PATTERNS:
        if pattern in addr:
            return 'announcement'
    
    # iste.edu.tr domaini ama listede değilse → muhtemelen idari/duyuru
    if addr.endswith('@iste.edu.tr'):
        return 'announcement'
    
    return 'other'


def zimbra_login(email: str, password: str) -> str:
    """
    Zimbra'ya giriş yapar ve auth token döndürür.
    Raises Exception on failure.
    """
    try:
        token = auth.authenticate(
            ZIMBRA_SOAP_URL,
            email,
            password,
            use_password=True
        )
        return token
    except Exception as e:
        raise Exception(f"Zimbra giriş başarısız: {str(e)}")


def fetch_inbox(token: str, limit: int = 100, offset: int = 0) -> list:
    """
    Zimbra gelen kutusundaki e-postaları çeker ve sınıflandırır.
    Returns list of email dicts.
    """
    academic_emails = _load_academic_emails()
    
    comm = Communication(ZIMBRA_SOAP_URL)
    search_request = comm.gen_request(token=token)
    search_request.add_request(
        'SearchRequest',
        {
            'query': 'in:inbox',
            'limit': str(limit),
            'offset': str(offset),
            'sortBy': 'dateDesc',
            'types': 'message',
            'fetch': '1'
        },
        'urn:zimbraMail'
    )
    
    response = comm.send_request(search_request)
    
    if response.is_fault():
        raise Exception(f"Zimbra arama hatası: {response.get_fault_message()}")
    
    result = response.get_response()
    
    # SearchResponse'dan mesajları çıkar
    search_resp = result.get('SearchResponse', {})
    messages_raw = search_resp.get('m', [])
    
    # Tek mesaj dict olarak dönebilir, listeye çevir
    if isinstance(messages_raw, dict):
        messages_raw = [messages_raw]
    
    emails = []
    for msg in messages_raw:
        # Gönderen bilgisini al
        from_addr = ''
        from_name = ''
        
        # e (email addresses) alanı
        e_list = msg.get('e', [])
        if isinstance(e_list, dict):
            e_list = [e_list]
        
        for e in e_list:
            if e.get('t') == 'f':  # 'f' = from
                from_addr = e.get('a', '')
                from_name = e.get('p', e.get('d', ''))
                break
        
        # Tarih (epoch ms → readable)
        date_ms = msg.get('d', 0)
        try:
            date_str = datetime.fromtimestamp(int(date_ms) / 1000).strftime('%d.%m.%Y %H:%M')
        except:
            date_str = ''
        
        # Konu
        subject = msg.get('su', '(Konu yok)')
        
        # Okundu mu?
        flags = msg.get('f', '')
        is_read = 'u' not in flags  # 'u' = unread
        
        # Sınıflandırma
        category = classify_email(from_addr, academic_emails)
        
        # E-posta gövdesini (body) çıkar
        body = ''
        mp = msg.get('mp', {})
        if isinstance(mp, dict):
            mp = [mp]
        if isinstance(mp, list):
            for part in mp:
                # text/plain veya text/html content
                ct = part.get('ct', '')
                if ct == 'text/plain' and part.get('content'):
                    body = part.get('content', '')
                    break
                elif ct == 'text/html' and part.get('content'):
                    body = part.get('content', '')
                # İç içe multipart kontrolü
                sub_parts = part.get('mp', [])
                if isinstance(sub_parts, dict):
                    sub_parts = [sub_parts]
                if isinstance(sub_parts, list):
                    for sp in sub_parts:
                        sct = sp.get('ct', '')
                        if sct == 'text/plain' and sp.get('content'):
                            body = sp.get('content', '')
                            break
                        elif sct == 'text/html' and sp.get('content'):
                            if not body:
                                body = sp.get('content', '')
        
        emails.append({
            'id': msg.get('id', ''),
            'subject': subject,
            'from_name': from_name,
            'from_address': from_addr,
            'date': date_str,
            'date_ms': date_ms,
            'is_read': is_read,
            'category': category,
            'snippet': msg.get('fr', '')[:150] if msg.get('fr') else '',
            'body': body
        })
    
    return emails


def fetch_message(token: str, msg_id: str) -> dict:
    """
    Tek bir e-postanın tam içeriğini çeker.
    """
    comm = Communication(ZIMBRA_SOAP_URL)
    msg_request = comm.gen_request(token=token)
    msg_request.add_request(
        'GetMsgRequest',
        {
            'm': {'id': msg_id, 'html': '1'}
        },
        'urn:zimbraMail'
    )
    
    response = comm.send_request(msg_request)
    
    if response.is_fault():
        raise Exception(f"Mesaj getirme hatası: {response.get_fault_message()}")
    
    result = response.get_response()
    msg = result.get('GetMsgResponse', {}).get('m', {})
    
    # Body çıkar
    body = ''
    mp = msg.get('mp', {})
    if isinstance(mp, dict):
        mp = [mp]
    if isinstance(mp, list):
        for part in mp:
            ct = part.get('ct', '')
            if ct == 'text/html' and part.get('content'):
                body = part.get('content', '')
                break
            elif ct == 'text/plain' and part.get('content'):
                body = part.get('content', '')
            sub_parts = part.get('mp', [])
            if isinstance(sub_parts, dict):
                sub_parts = [sub_parts]
            if isinstance(sub_parts, list):
                for sp in sub_parts:
                    sct = sp.get('ct', '')
                    if sct == 'text/html' and sp.get('content'):
                        body = sp.get('content', '')
                        break
                    elif sct == 'text/plain' and sp.get('content'):
                        if not body:
                            body = sp.get('content', '')
    
    return {
        'id': msg.get('id', ''),
        'subject': msg.get('su', ''),
        'body': body
    }
