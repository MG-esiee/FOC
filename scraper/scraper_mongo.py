from pymongo import MongoClient
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime, timedelta
import time

# Connexion à MongoDB
client = MongoClient("mongodb://mongodb:27017")
db = client["odds_db"]
collection = db["matches"]

# Vider la collection avant scraping pour éviter les doublons
collection.delete_many({})

# Options Chrome
chrome_options = Options()
chrome_options.binary_location = "/usr/bin/chromium"
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1920,1080")

driver = webdriver.Chrome(
    service=Service("/usr/bin/chromedriver"),
    options=chrome_options
)

def parse_date(date_str):
    """Parse et normalise la date"""
    date_str = date_str.strip()
    today = datetime.now()
    
    if "Today" in date_str:
        # Format: "Today, 25 Jan" -> "25 Jan 2026"
        parts = date_str.split(',')
        if len(parts) > 1:
            return f"{parts[1].strip()} {today.year}"
        return f"{today.day} {today.strftime('%b')} {today.year}"
    
    if "Tomorrow" in date_str:
        tomorrow = today + timedelta(days=1)
        parts = date_str.split(',')
        if len(parts) > 1:
            return f"{parts[1].strip()} {today.year}"
        return f"{tomorrow.day} {tomorrow.strftime('%b')} {today.year}"
    
    parts = date_str.split()
    if len(parts) == 2:  # "30 Jan"
        return f"{date_str} {today.year}"
    
    return date_str

try:
    driver.get("https://www.oddsportal.com/soccer/france/ligue-1/")
    
    WebDriverWait(driver, 20).until(
        EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, "div[data-testid='game-row']")
        )
    )
    
    time.sleep(2)  # Attendre le chargement complet
    
    elements = driver.find_elements(
        By.CSS_SELECTOR,
        "div[data-testid='game-row'], div.text-black-main.font-main.w-full.truncate.text-xs.font-normal.leading-5"
    )
    
    seen_matches = set()
    current_date = None
    
    for el in elements:
        cls = el.get_attribute("class") or ""
        
        # Bloc date
        if "text-black-main" in cls and "truncate" in cls:
            date_text = el.text.strip()
            # Éviter de confondre scores avec dates
            if date_text and not any(x in date_text for x in [":", "–", "-"]) and len(date_text) > 3:
                current_date = parse_date(date_text)
            continue
        
        if not current_date:
            continue
        
        try:
            # Équipes
            teams = el.find_elements(By.CSS_SELECTOR, "p.participant-name.truncate")
            if len(teams) < 2:
                continue
            
            home_team = teams[0].text.strip()
            away_team = teams[1].text.strip()
            
            if not home_team or not away_team:
                continue
            
            # Heure ou statut du match
            try:
                time_element = el.find_element(By.CSS_SELECTOR, "div[data-testid='time-item'] p")
                match_time = time_element.text.strip()
            except:
                match_time = "00:00"
            
            # Détecter si le match est en cours (contient ' ou minute)
            is_live = "'" in match_time or match_time.lower() in ["ht", "ft", "pen"]
            
            # Pour les matchs en cours, on garde uniquement la dernière version
            # En utilisant uniquement home_team + away_team + date comme clé
            if is_live:
                match_id = f"{home_team}_{away_team}_{current_date}_LIVE"
            else:
                match_id = f"{home_team}_{away_team}_{current_date}_{match_time}"
            
            # Éviter les doublons strictement
            if match_id in seen_matches:
                continue
            seen_matches.add(match_id)
            
            # Cotes
            try:
                odds_elements = el.find_elements(By.CSS_SELECTOR, "div[data-testid^='odd-container'] p")
                odd_1 = odds_elements[0].text.strip() if len(odds_elements) >= 1 else "-"
                odd_x = odds_elements[1].text.strip() if len(odds_elements) >= 2 else "-"
                odd_2 = odds_elements[2].text.strip() if len(odds_elements) >= 3 else "-"
            except:
                odd_1 = odd_x = odd_2 = "-"
            
            # Scores - dans les divs avec classe hidden
            score_home = "0"
            score_away = "0"
            
            try:
                score_divs = el.find_elements(By.CSS_SELECTOR, "div.hidden[data-v-143a5c06]")
                if len(score_divs) >= 2:
                    score_home = score_divs[0].text.strip() if score_divs[0].text.strip() else "0"
                    score_away = score_divs[1].text.strip() if score_divs[1].text.strip() else "0"
            except:
                # Par défaut si erreur
                score_home = "0"
                score_away = "0"
            
            # Datetime pour tri
            try:
                # Nettoyer match_time des caractères spéciaux pour parsing
                clean_time = match_time
                if "'" in match_time or match_time in ["HT", "FT", "Pen"]:
                    clean_time = "00:00"  # Match en cours, on met une heure par défaut
                
                match_datetime = datetime.strptime(f"{current_date} {clean_time}", "%d %b %Y %H:%M")
            except:
                match_datetime = datetime(1970, 1, 1, 0, 0)
            
            match_data = {
                "home_team": home_team,
                "away_team": away_team,
                "date": current_date,
                "time": match_time,
                "odd_1": odd_1,
                "odd_x": odd_x,
                "odd_2": odd_2,
                "score_home": score_home,
                "score_away": score_away,
                "datetime": match_datetime,
                "is_live": is_live
            }
            
            # CLÉ UNIQUE : home_team + away_team + date (sans l'heure pour les matchs en cours)
            # Pour éviter les doublons de minutes différentes
            if is_live:
                collection.update_one(
                    {
                        "home_team": home_team,
                        "away_team": away_team,
                        "date": current_date
                    },
                    {"$set": match_data},
                    upsert=True
                )
            else:
                collection.update_one(
                    {
                        "home_team": home_team,
                        "away_team": away_team,
                        "date": current_date,
                        "time": match_time
                    },
                    {"$set": match_data},
                    upsert=True
                )
            
            print(f"✓ {current_date} {match_time} - {home_team} vs {away_team}")
            
        except Exception as e:
            print(f"Erreur: {e}")
            continue
    
    print(f"\n✓ {len(seen_matches)} matchs enregistrés")

except Exception as e:
    print(f"Erreur générale: {e}")
    import traceback
    traceback.print_exc()

finally:
    driver.quit()