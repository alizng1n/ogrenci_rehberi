"""
ISTE Akademik Kadro Scraper
YOK Akademik + ISTE kendi sitesinden tum akademisyenleri toplar.
"""
import os
import json
import time
import re
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'personnel.json')


def scrape_all():
    print("=" * 60)
    print("ISTE Akademik Kadro Scraper")
    print("=" * 60)

    personnel = []
    seen = set()

    # 1) YOK Akademik'ten cek
    yok_count = scrape_from_yok(personnel, seen)
    print(f"\n[YOK] {yok_count} akademisyen alindi.")

    # 2) ISTE sitesinden tamamla (bolum bilgisi + eksik kisiler)
    iste_count = scrape_from_iste_site(personnel, seen)
    print(f"[ISTE] {iste_count} ek akademisyen alindi.")

    # Kaydet
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(personnel, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"[BITTI] Toplam {len(personnel)} akademisyen kaydedildi")
    print(f"{'=' * 60}")


def scrape_from_yok(personnel, seen):
    """YOK Akademik'ten tum sayfalari gezerek akademisyenleri toplar."""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

    driver = webdriver.Chrome(options=chrome_options)
    count_before = len(personnel)

    try:
        url = "https://akademik.yok.gov.tr/AkademikArama/view/searchResultviewListAuthorAndUniversities.jsp"
        print(f"[YOK] Sayfa aciliyor...")
        driver.get(url)
        time.sleep(3)

        # ISTE'yi bul ve tikla
        all_links = driver.find_elements(By.TAG_NAME, "a")
        iste_link = None
        for link in all_links:
            try:
                text = link.text.strip().upper()
                if "ISKENDERUN TEKNIK" in text or "SKENDERUN TEKN" in text:
                    iste_link = link
                    break
            except:
                continue

        if not iste_link:
            print("[YOK] ISTE bulunamadi!")
            driver.quit()
            return 0

        print("[YOK] ISTE bulundu, tiklaniyor...")
        driver.execute_script("arguments[0].click();", iste_link)
        time.sleep(4)

        # Sayfa sayfa gez
        page_num = 1
        max_pages = 25

        while page_num <= max_pages:
            print(f"  Sayfa {page_num} taraniyor...")
            rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr, #authorlistTb tr, .table tr")

            page_found = 0
            for row in rows:
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) < 2:
                        continue

                    # Isim: link icerisinde
                    name = ""
                    profile_url = ""
                    dept = ""
                    email = ""

                    # Profil linki ve isim
                    prof_links = row.find_elements(By.CSS_SELECTOR, "a[href*='authorId']")
                    if prof_links:
                        name = prof_links[0].text.strip()
                        profile_url = prof_links[0].get_attribute("href")

                    if not name:
                        # Alternatif: h4/strong
                        for cell in cells:
                            els = cell.find_elements(By.CSS_SELECTOR, "h4, strong, a")
                            for el in els:
                                t = el.text.strip()
                                if t and len(t) > 3 and not t.isdigit():
                                    name = t
                                    href = el.get_attribute("href") or ""
                                    if "authorId" in href:
                                        profile_url = href
                                    break
                            if name:
                                break

                    if not name or name in seen or len(name) < 3:
                        continue

                    # Bolum bilgisi (satir icinde / ile ayrilmis yol)
                    row_text = row.text
                    for line in row_text.split('\n'):
                        line = line.strip()
                        if "/" in line and len(line) > 10:
                            parts = [p.strip() for p in line.split("/")]
                            # Son kisim genelde bolum adi
                            if len(parts) >= 2:
                                dept = parts[-1]
                            break

                    # E-posta
                    mail_links = row.find_elements(By.CSS_SELECTOR, "a[href^='mailto:']")
                    if mail_links:
                        email = mail_links[0].get_attribute("href").replace("mailto:", "")
                    else:
                        em = re.search(r'[\w.+-]+@[\w.-]+\.\w+', row_text)
                        if em:
                            email = em.group()

                    if not email:
                        # slug'dan tahmin et
                        slug = name.lower().replace(" ", ".").replace("i", "i")
                        email = f"{slug}@iste.edu.tr"

                    seen.add(name)
                    personnel.append({
                        "name": name,
                        "department": dept,
                        "email": email,
                        "profile_url": profile_url
                    })
                    page_found += 1

                except Exception:
                    continue

            print(f"    +{page_found} kisi")

            if page_found == 0 and page_num > 1:
                break

            # Sonraki sayfaya gec
            page_num += 1
            try:
                pagination_links = driver.find_elements(By.CSS_SELECTOR, ".pagination a, .pagination li a")
                next_page = None

                for pl in pagination_links:
                    try:
                        txt = pl.text.strip()
                        # Sayfa numarasina gore tikla
                        if txt == str(page_num):
                            next_page = pl
                            break
                    except:
                        continue

                # Bulunamadiysa "sonraki" butonunu dene
                if not next_page:
                    for pl in pagination_links:
                        try:
                            txt = pl.text.strip()
                            aria = pl.get_attribute("aria-label") or ""
                            if ">" in txt or "next" in aria.lower() or "sonraki" in txt.lower():
                                next_page = pl
                                break
                        except:
                            continue

                if next_page:
                    driver.execute_script("arguments[0].scrollIntoView(true);", next_page)
                    time.sleep(0.5)
                    driver.execute_script("arguments[0].click();", next_page)
                    time.sleep(3)
                else:
                    print("  Pagination sonu.")
                    break

            except Exception as e:
                print(f"  Pagination hatasi: {str(e)[:60]}")
                break

    except Exception as e:
        print(f"[YOK HATA] {str(e)[:120]}")
    finally:
        try:
            driver.quit()
        except:
            pass

    return len(personnel) - count_before


def scrape_from_iste_site(personnel, seen):
    """ISTE'nin kendi sitesinden personel bilgilerini ceker."""
    import requests
    from bs4 import BeautifulSoup

    count_before = len(personnel)

    faculties = [
        ("https://iste.edu.tr/mdbf", "Muhendislik ve Doga Bilimleri Fak."),
        ("https://iste.edu.tr/bhgidf", "Gemi Insaati ve Denizcilik Fak."),
        ("https://iste.edu.tr/dbtf", "Deniz Bilimleri ve Teknolojisi Fak."),
        ("https://iste.edu.tr/hubf", "Havacilik ve Uzay Bilimleri Fak."),
        ("https://iste.edu.tr/iybf", "Isletme ve Yonetim Bilimleri Fak."),
        ("https://iste.edu.tr/mf", "Mimarlik Fakultesi"),
        ("https://iste.edu.tr/tf", "Turizm Fakultesi"),
    ]

    for fac_url, fac_name in faculties:
        print(f"  [ISTE] {fac_name} taraniyor...")
        try:
            fr = requests.get(fac_url, timeout=10)
            fsoup = BeautifulSoup(fr.text, 'html.parser')

            dept_links = set()
            for a in fsoup.find_all('a'):
                href = a.get('href', '')
                if href and href.startswith('https://iste.edu.tr/') and len(href.split('/')) == 4:
                    slug = href.split('/')[-1]
                    if slug not in ['fakulteler', 'personel', 'iletisim', 'hakkinda', 'duyurular'] and fac_url.split('/')[-1] != slug:
                        dept_links.add(href)

            all_urls = [f"{fac_url}/personel"]
            for dept_url in dept_links:
                all_urls.append(f"{dept_url}/personel")

            for p_url in all_urls:
                try:
                    pr = requests.get(p_url, timeout=10)
                    if pr.status_code != 200:
                        continue
                    psoup = BeautifulSoup(pr.text, 'html.parser')
                    person_links = set()
                    for a in psoup.find_all('a'):
                        href = a.get('href', '')
                        if '/person/' in href:
                            person_links.add(href)

                    dept_slug = p_url.replace('/personel', '').split('/')[-1].upper()

                    for person_url in person_links:
                        slug = person_url.split('/')[-1]
                        name = slug.replace('-', ' ').title()

                        if name in seen:
                            continue
                        seen.add(name)

                        email = f"{slug.replace('-', '.')}@iste.edu.tr"

                        personnel.append({
                            "name": name,
                            "department": dept_slug,
                            "email": email,
                            "profile_url": person_url
                        })
                        print(f"    + {name} | {dept_slug}")

                except Exception:
                    continue
        except Exception as e:
            print(f"    [!] Hata: {str(e)[:80]}")

    return len(personnel) - count_before


if __name__ == "__main__":
    scrape_all()
