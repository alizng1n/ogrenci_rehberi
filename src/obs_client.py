import os
import time
import re
import base64
import tempfile
import uuid
from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

OBS_LOGIN_URL = "https://obs.iste.edu.tr/oibs/std/login.aspx"

def save_debug_html(filename, content):
    """
    Sayfa kaynak kodlarını debug amacıyla yerel diskteki data klasörüne yazar.
    """
    try:
        debug_dir = r"c:\Users\Acer\Desktop\rag\data"
        os.makedirs(debug_dir, exist_ok=True)
        path = os.path.join(debug_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[OBS DEBUG] Debug dosyası kaydedildi: {path}")
    except Exception as e:
        print(f"[OBS DEBUG] Debug dosyası kaydedilirken hata: {e}")

def parse_grades_page(html_content):
    """
    BS4 ile not listesi sayfasını parse eder.
    Her satırı tarayarak başlık satırını bulur ve sütunları eşleştirir.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    tables = soup.find_all('table')
    
    grades = []
    for table in tables:
        rows = table.find_all('tr')
        if not rows:
            continue
            
        header_row = None
        headers = []
        for row in rows:
            row_cells = row.find_all(['th', 'td'])
            cell_texts = [c.text.strip().lower() for c in row_cells]
            joined_cells = "".join(cell_texts)
            
            # Başlık satırı tespiti
            is_header = any(k in joined_cells for k in ["ders", "vize", "ara sınav", "ara sinav", "final", "yıl sonu", "harf", "ortalama"])
            if is_header and ("ders" in joined_cells or "kod" in joined_cells):
                header_row = row
                headers = cell_texts
                break
                
        if header_row is None:
            continue
            
        # Sütun indekslerini tespit et
        col_indices = {
            "code": -1,
            "name": -1,
            "vize": -1,
            "final": -1,
            "average": -1,
            "letter": -1,
            "exams": -1
        }
        
        for idx, h in enumerate(headers):
            if "kod" in h:
                col_indices["code"] = idx
            elif "ders" in h or "ad" in h:
                col_indices["name"] = idx
            elif "vize" in h or "ara" in h:
                col_indices["vize"] = idx
            elif "final" in h or "yıl sonu" in h or "yılsonu" in h:
                col_indices["final"] = idx
            elif "ort" in h or "başarı" in h:
                col_indices["average"] = idx
            elif h in ["not", "notu"] or "harf" in h:
                col_indices["letter"] = idx
            elif "sınav" in h or "sinav" in h or "notları" in h or "notlari" in h:
                col_indices["exams"] = idx
                    
        # Ders adı veya ders kodunun en azından birinin olması şart
        if col_indices["name"] == -1 and col_indices["code"] == -1:
            continue
            
        header_idx = rows.index(header_row)
        for row in rows[header_idx + 1:]:
            cols = [c.text.strip() for c in row.find_all(['td', 'th'])]
            mapped_indices = [v for k, v in col_indices.items() if v != -1]
            if not mapped_indices or len(cols) < max(mapped_indices) + 1:
                continue
                
            course_code = cols[col_indices["code"]] if col_indices["code"] != -1 else ""
            course_name = cols[col_indices["name"]] if col_indices["name"] != -1 else ""
            avg_val = cols[col_indices["average"]] if col_indices["average"] != -1 else ""
            letter_val = cols[col_indices["letter"]] if col_indices["letter"] != -1 else ""
            
            # Sınav notlarını ayıkla (Vize & Final)
            vize_val = ""
            final_val = ""
            
            if col_indices["exams"] != -1 and len(cols) > col_indices["exams"]:
                exam_notes = cols[col_indices["exams"]].replace('\xa0', ' ').replace('\u00a0', ' ')
                
                vize_match = re.search(r'(?:ara sınav|vize|ara sinav)\s*:\s*(\d+|--|-)', exam_notes, re.IGNORECASE)
                if vize_match:
                    vize_val = vize_match.group(1)
                    
                final_match = re.search(r'(?:final|yıl sonu|yılsonu)\s*:\s*(\d+|--|-)', exam_notes, re.IGNORECASE)
                if final_match:
                    final_val = final_match.group(1)
            
            # Ayrı sütunlar varsa ve yukarıda bulunamadıysa fallback yap
            if not vize_val and col_indices["vize"] != -1 and len(cols) > col_indices["vize"]:
                vize_val = cols[col_indices["vize"]]
            if not final_val and col_indices["final"] != -1 and len(cols) > col_indices["final"]:
                final_val = cols[col_indices["final"]]
                
            if not course_name and not course_code:
                continue
                
            grades.append({
                "course_code": course_code,
                "course_name": course_name,
                "vize": vize_val,
                "final": final_val,
                "average": avg_val,
                "letter_grade": letter_val
            })
            
    return grades

def parse_attendance_page(html_content):
    """
    BS4 ile devamsızlık sayfasını parse eder.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    tables = soup.find_all('table')
    
    attendance = []
    for table in tables:
        rows = table.find_all('tr')
        if not rows:
            continue
            
        header_row = None
        headers = []
        for row in rows:
            row_cells = row.find_all(['th', 'td'])
            cell_texts = [c.text.strip().lower() for c in row_cells]
            joined_cells = "".join(cell_texts)
            
            is_header = any(k in joined_cells for k in ["devamsız", "devam", "teorik", "uygulama", "durum"])
            if is_header and ("ders" in joined_cells or "ad" in joined_cells or "kod" in joined_cells):
                header_row = row
                headers = cell_texts
                break
                
        if header_row is None:
            continue
            
        col_indices = {
            "name": -1,
            "teorik": -1,
            "uygulama": -1,
            "status": -1
        }
        
        for idx, h in enumerate(headers):
            if "ders" in h or "ad" in h:
                col_indices["name"] = idx
            elif "teorik" in h or "t sa" in h or "teorik saat" in h or ("devam" in h and "t" in h):
                col_indices["teorik"] = idx
            elif "uygulama" in h or "u sa" in h or "uygulama saat" in h or ("devam" in h and "u" in h):
                col_indices["uygulama"] = idx
            elif "durum" in h or "kaldı" in h or "geçti" in h:
                col_indices["status"] = idx
                
        header_idx = rows.index(header_row)
        for row in rows[header_idx + 1:]:
            cols = [c.text.strip() for c in row.find_all(['td', 'th'])]
            if len(cols) < max(col_indices.values()) + 1:
                continue
                
            course_name = cols[col_indices["name"]] if col_indices["name"] != -1 else ""
            teorik_val = cols[col_indices["teorik"]] if col_indices["teorik"] != -1 else "-"
            uygulama_val = cols[col_indices["uygulama"]] if col_indices["uygulama"] != -1 else "-"
            status_val = cols[col_indices["status"]] if col_indices["status"] != -1 else "Belirtilmemiş"
            
            if not course_name:
                continue
                
            attendance.append({
                "course_name": course_name,
                "teorik_devamsizlik": teorik_val,
                "uygulama_devamsizlik": uygulama_val,
                "status": status_val
            })
            
    return attendance

class OBSLoginSession:
    def __init__(self):
        self.session_id = str(uuid.uuid4())
        self.driver = None
        self.created_at = time.time()
        
    def start(self) -> str:
        """
        Tarayıcıyı başlatır, OBS giriş sayfasına gider, CAPTCHA elementinin
        ekran görüntüsünü alıp base64 string olarak döner. Tarayıcıyı kapatmaz.
        """
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        self.driver = webdriver.Chrome(options=chrome_options)
        
        try:
            print(f"[OBS SESSION - {self.session_id}] Sayfa yükleniyor...")
            self.driver.get(OBS_LOGIN_URL)
            
            # 5 dakikalık zaman aşımı yenileme butonu kontrolü
            try:
                btn_refresh = self.driver.find_element(By.ID, "btnRefresh")
                if btn_refresh.is_displayed():
                    print(f"[OBS SESSION - {self.session_id}] Zaman aşımı tespit edildi, sayfa yenileniyor...")
                    btn_refresh.click()
                    time.sleep(2)
            except:
                pass
                
            # Giriş formu elemanlarını bekle
            wait = WebDriverWait(self.driver, 10)
            wait.until(EC.presence_of_element_located((By.ID, "txtParamT01")))
            
            # CAPTCHA Görselini Kırp ve base64'e dönüştür
            captcha_element = self.driver.find_element(By.ID, "imgCaptchaImg")
            
            temp_dir = tempfile.gettempdir()
            temp_img_path = os.path.join(temp_dir, f"obs_captcha_temp_{self.session_id}.png")
            captcha_element.screenshot(temp_img_path)
            
            try:
                with open(temp_img_path, "rb") as image_file:
                    encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                return encoded_string
            finally:
                if os.path.exists(temp_img_path):
                    os.remove(temp_img_path)
                    
        except Exception as e:
            print(f"[OBS SESSION ERROR - {self.session_id}] Başlatma hatası: {e}")
            self.close()
            raise e
            
    def login_and_fetch(self, username, password, captcha_code) -> dict:
        """
        Açık tarayıcıyı kullanarak kullanıcı adı, şifre ve captcha kodunu girer,
        giriş yapar ve verileri (notlar ve devamsızlıklar) çekip tarayıcıyı kapatır.
        """
        if not self.driver:
            raise Exception("Tarayıcı oturumu başlatılmamış.")
            
        try:
            # Giriş alanlarını bul
            txt_username = self.driver.find_element(By.ID, "txtParamT01")
            txt_password = self.driver.find_element(By.ID, "txtParamT02")
            txt_captcha = self.driver.find_element(By.ID, "txtSecCode")
            
            # Bilgileri gir
            txt_username.clear()
            txt_username.send_keys(username)
            
            txt_password.click()
            time.sleep(0.5)
            txt_password.send_keys(password)
            
            txt_captcha.clear()
            txt_captcha.send_keys(captcha_code)
            
            # Giriş Yap
            btn_login = self.driver.find_element(By.ID, "btnLogin")
            print(f"[OBS SESSION - {self.session_id}] Giriş yapılıyor...")
            self.driver.execute_script("arguments[0].click();", btn_login)
            
            # Poll URL change and inject UniqueTabCheck bypass immediately
            start_time = time.time()
            bypassed = False
            while time.time() - start_time < 5:
                try:
                    curr_url = self.driver.current_url.lower()
                    if "login.aspx" not in curr_url:
                        self.driver.execute_script("""
                            window.UniqueTabCheck = function() { console.log('UniqueTabCheck bypassed window'); return true; };
                            if (window.top) {
                                window.top.UniqueTabCheck = function() { console.log('UniqueTabCheck bypassed top'); return true; };
                                window.top.UniqueTabCheckFirstLoad = 'bypassed';
                                window.top.UniqueTabCheckEveryLoad = 'bypassed';
                            }
                        """)
                        bypassed = True
                        break
                except:
                    pass
                time.sleep(0.05)
            
            print(f"[OBS SESSION - {self.session_id}] UniqueTabCheck bypass enjekte edildi: {bypassed}")
            
            # Kalan yüklenme payı
            time.sleep(3.0)
            
            # Hata mesajı var mı kontrol et
            try:
                lbl_sonuclar = self.driver.find_element(By.ID, "lblSonuclar")
                error_text = lbl_sonuclar.text.strip()
                if error_text:
                    raise Exception(f"OBS Giriş Hatası: {error_text}")
            except Exception as e:
                if "OBS Giriş Hatası" in str(e):
                    raise e
                    
            current_url = self.driver.current_url.lower()
            print(f"[OBS SESSION - {self.session_id}] Mevcut URL: {current_url}")
            
            if "login.aspx" in current_url:
                raise Exception("OBS girişi başarısız oldu (Hatalı şifre veya güvenlik kodu).")
                
            print(f"[OBS SESSION - {self.session_id}] Giriş başarılı! Ana sayfa kaynak kodu kaydediliyor...")
            landing_html = self.driver.page_source
            save_debug_html(f"landing_page_{self.session_id}.html", landing_html)
            
            # Yeniden enjekte et (sayfa tam yüklendiğinde garanti olsun diye)
            try:
                self.driver.execute_script("""
                    window.UniqueTabCheck = function() { return true; };
                    if (window.top) {
                        window.top.UniqueTabCheck = function() { return true; };
                        window.top.UniqueTabCheckFirstLoad = 'bypassed';
                        window.top.UniqueTabCheckEveryLoad = 'bypassed';
                    }
                """)
            except:
                pass

            # Notları Çek (IFRAME içinde sol menüden tıklayarak)
            grades = []
            print(f"[OBS SESSION - {self.session_id}] Notlar menü elemanına tıklanarak yükleniyor...")
            try:
                # Menüden "Not Listesi" bağlantısını bul
                links = self.driver.find_elements(By.TAG_NAME, "a")
                not_listesi_link = None
                for link in links:
                    try:
                        text = link.get_attribute("textContent") or ""
                        text = text.strip().lower()
                        # "haz." veya "hazırlık" içermediğinden emin ol (prep school not listesi değil)
                        if ("not listesi" in text or "notlar" in text) and "haz" not in text:
                            not_listesi_link = link
                            break
                    except:
                        pass
                
                if not_listesi_link:
                    print(f"[OBS SESSION - {self.session_id}] Not Listesi linki bulundu, tıklanıyor...")
                    self.driver.execute_script("arguments[0].click();", not_listesi_link)
                    
                    # Iframe'e geç
                    self.driver.switch_to.frame("IFRAME1")
                    
                    # Iframe URL'sinin notlistesi.aspx veya NotListesi içermesini bekle (JS ile location.href alarak)
                    print(f"[OBS SESSION - {self.session_id}] Not Listesi sayfasının yüklenmesi bekleniyor...")
                    WebDriverWait(self.driver, 10).until(
                        lambda d: "notlistesi" in d.execute_script("return window.location.href;").lower() or "not_listesi" in d.execute_script("return window.location.href;").lower()
                    )
                    
                    # Tablo render'ını bekle
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "table"))
                    )
                    time.sleep(1.5) # Ekstra render payı
                    
                    grades_html = self.driver.page_source
                    save_debug_html(f"grades_page_{self.session_id}.html", grades_html)
                    grades = parse_grades_page(grades_html)
                    print(f"[OBS SESSION - {self.session_id}] {len(grades)} ders notu kaydı çekildi.")
                else:
                    print(f"[OBS SESSION - {self.session_id}] Not Listesi menü bağlantısı bulunamadı! Mevcut linkler:")
                    for idx, link in enumerate(links[:50]):
                        try:
                            txt = link.text
                            tc = link.get_attribute("textContent")
                            oc = link.get_attribute("onclick")
                            print(f"  Link {idx}: text='{txt}', textContent='{tc}', onclick='{oc}'")
                        except:
                            pass
            except Exception as iframe_err:
                print(f"[OBS SESSION - {self.session_id}] Not listesi iframe geçiş/kazıma hatası: {iframe_err}")
            finally:
                self.driver.switch_to.default_content()
            
            # Devamsızlıkları Çek (IFRAME içinde sol menüden tıklayarak)
            attendance = []
            print(f"[OBS SESSION - {self.session_id}] Devamsızlık menü elemanına tıklanarak yükleniyor...")
            try:
                # Menüden "Devamsızlık Durumu" bağlantısını bul
                links = self.driver.find_elements(By.TAG_NAME, "a")
                devamsizlik_link = None
                for link in links:
                    try:
                        text = link.get_attribute("textContent") or ""
                        text = text.strip().lower()
                        if "devamsızlık" in text or "devam durum" in text:
                            # "haz" içermediğinden emin ol
                            if "haz" not in text:
                                devamsizlik_link = link
                                break
                    except:
                        pass
                
                if devamsizlik_link:
                    print(f"[OBS SESSION - {self.session_id}] Devamsızlık linki bulundu, tıklanıyor...")
                    self.driver.execute_script("arguments[0].click();", devamsizlik_link)
                    
                    # Iframe'e geç
                    self.driver.switch_to.frame("IFRAME1")
                    
                    # Iframe URL'sinin devamsizlik içermesini bekle (JS ile location.href alarak)
                    print(f"[OBS SESSION - {self.session_id}] Devamsızlık sayfasının yüklenmesi bekleniyor...")
                    WebDriverWait(self.driver, 10).until(
                        lambda d: "devamsizlik" in d.execute_script("return window.location.href;").lower() or "devam" in d.execute_script("return window.location.href;").lower()
                    )
                    
                    # Tablo render'ını bekle
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "table"))
                    )
                    time.sleep(1.5) # Ekstra render payı
                    
                    attendance_html = self.driver.page_source
                    save_debug_html(f"attendance_page_{self.session_id}.html", attendance_html)
                    attendance = parse_attendance_page(attendance_html)
                    print(f"[OBS SESSION - {self.session_id}] {len(attendance)} devamsızlık kaydı çekildi.")
                else:
                    print(f"[OBS SESSION - {self.session_id}] Devamsızlık menü bağlantısı bulunamadı! Mevcut linkler:")
                    for idx, link in enumerate(links[:50]):
                        try:
                            txt = link.text
                            tc = link.get_attribute("textContent")
                            oc = link.get_attribute("onclick")
                            print(f"  Link {idx}: text='{txt}', textContent='{tc}', onclick='{oc}'")
                        except:
                            pass
            except Exception as iframe_err:
                print(f"[OBS SESSION - {self.session_id}] Devamsızlık iframe geçiş/kazıma hatası: {iframe_err}")
            finally:
                self.driver.switch_to.default_content()
            
            return {
                "grades": grades,
                "attendance": attendance
            }
            
        finally:
            self.close()
            
    def close(self):
        """Tarayıcıyı kapatır."""
        if self.driver:
            print(f"[OBS SESSION - {self.session_id}] Tarayıcı kapatılıyor...")
            try:
                self.driver.quit()
            except Exception as e:
                print(f"[OBS SESSION - {self.session_id}] Kapatırken hata oluştu: {e}")
            self.driver = None
