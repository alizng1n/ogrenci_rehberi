import json
import os
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_person_detail(person):
    url = person.get('profile_url')
    if not url:
        return person
        
    details = {
        "title": "",
        "yoksis": "",
        "orcid": "",
        "tasks": [],
        "office_hours": []
    }
    
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
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
                
        r_tasks = requests.get(f"{url}/tasks", timeout=10)
        if r_tasks.status_code == 200:
            soup_tasks = BeautifulSoup(r_tasks.text, 'html.parser')
            task_items = soup_tasks.select('nav.ilistNavigation ul li')
            for item in task_items:
                unit = item.select_one('div.ifirst')
                duty = item.select_one('div.isecond')
                if unit and duty:
                    details["tasks"].append({"unit": unit.text.strip(), "duty": duty.text.strip()})
                    
        r_office = requests.get(f"{url}/office-hours", timeout=10)
        if r_office.status_code == 200:
            soup_office = BeautifulSoup(r_office.text, 'html.parser')
            office_items = soup_office.select('nav.ilistNavigation ul li')
            for item in office_items:
                time_val = item.select_one('div.ifirst')
                desc = item.select_one('div.isecond')
                if time_val and desc:
                    details["office_hours"].append({"time": time_val.text.strip(), "description": desc.text.strip()})
                    
    except Exception as e:
        print(f"Error for {person['name']}: {e}")
        
    person['details'] = details
    return person

def main():
    personnel_path = os.path.join('data', 'personnel.json')
    if not os.path.exists(personnel_path):
        print("personnel.json not found")
        return
        
    with open(personnel_path, 'r', encoding='utf-8') as f:
        personnel = json.load(f)
        
    print(f"Enhancing {len(personnel)} personnel records...")
    
    enhanced = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(fetch_person_detail, p): p for p in personnel}
        for i, future in enumerate(as_completed(futures)):
            result = future.result()
            enhanced.append(result)
            if (i+1) % 50 == 0:
                print(f"Processed {i+1}/{len(personnel)}")
                
    out_path = os.path.join('data', 'personnel_detailed.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(enhanced, f, ensure_ascii=False, indent=2)
        
    print(f"Saved enhanced data to {out_path}")

if __name__ == '__main__':
    main()
