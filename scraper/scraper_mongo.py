from pymongo import MongoClient
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from datetime import datetime, timedelta
import time
import sys
import traceback

# Configuration des ligues
LEAGUES = {
    "ligue-1": {
        "name": "Ligue 1",
        "url": "https://www.oddsportal.com/soccer/france/ligue-1/",
        "country": "France"
    },
    "premier-league": {
        "name": "Premier League",
        "url": "https://www.oddsportal.com/soccer/england/premier-league/",
        "country": "England"
    },
    "la-liga": {
        "name": "La Liga",
        "url": "https://www.oddsportal.com/soccer/spain/laliga/",
        "country": "Spain"
    },
    "serie-a": {
        "name": "Serie A",
        "url": "https://www.oddsportal.com/soccer/italy/serie-a/",
        "country": "Italy"
    },
    "bundesliga": {
        "name": "Bundesliga",
        "url": "https://www.oddsportal.com/soccer/germany/bundesliga/",
        "country": "Germany"
    }
}

def parse_date(date_str):
    """Parse et normalise la date"""
    try:
        date_str = date_str.strip()
        today = datetime.now()
        
        if "Today" in date_str:
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
        if len(parts) == 2:
            return f"{date_str} {today.year}"
        
        return date_str
    except Exception as e:
        print(f"[WARN] Erreur parsing date '{date_str}': {e}")
        return None

def scrape_league(league_id, league_info, collection, max_retries=3):
    """Scrape une ligue spécifique avec retry"""
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                print(f"[RETRY] Tentative {attempt + 1}/{max_retries} pour {league_info['name']}...")
                time.sleep(5)  # Attendre avant de réessayer
            else:
                print(f"\n[INFO] Scraping {league_info['name']}...")
            
            # Options Chrome
            chrome_options = Options()
            chrome_options.binary_location = "/usr/bin/chromium"
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            driver = None
            
            try:
                driver = webdriver.Chrome(
                    service=Service("/usr/bin/chromedriver"),
                    options=chrome_options
                )
                
                driver.get(league_info['url'])
                
                # Attendre le chargement avec timeout plus long
                try:
                    WebDriverWait(driver, 30).until(
                        EC.presence_of_all_elements_located(
                            (By.CSS_SELECTOR, "div[data-testid='game-row']")
                        )
                    )
                except TimeoutException:
                    print(f"[WARN] Timeout lors du chargement de {league_info['name']}, réessai...")
                    raise
                
                # Attendre que la page soit stable
                time.sleep(3)
                
                # Scroll pour charger tout le contenu
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
                
                elements = driver.find_elements(
                    By.CSS_SELECTOR,
                    "div[data-testid='game-row'], div.text-black-main.font-main.w-full.truncate.text-xs.font-normal.leading-5"
                )
                
                if not elements:
                    print(f"[WARN] Aucun élément trouvé pour {league_info['name']}")
                    raise Exception("Aucun match trouvé")
                
                seen_matches = set()
                current_date = None
                matches_count = 0
                errors_count = 0
                
                for idx, el in enumerate(elements):
                    try:
                        cls = el.get_attribute("class") or ""
                        
                        # Bloc date
                        if "text-black-main" in cls and "truncate" in cls:
                            date_text = el.text.strip()
                            if date_text and not any(x in date_text for x in [":", "–", "-"]) and len(date_text) > 3:
                                parsed_date = parse_date(date_text)
                                if parsed_date:
                                    current_date = parsed_date
                            continue
                        
                        if not current_date:
                            continue
                        
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
                        
                        # Détecter si le match est en cours ou terminé
                        is_live = "'" in match_time or match_time.lower() == "ht"
                        is_finished = match_time.lower() in ["ft", "fin", "finished", "aet", "pen"]
                        
                        # Ignorer les matchs terminés
                        if is_finished:
                            # Supprimer le match terminé de la base
                            collection.delete_one({
                                "league_id": league_id,
                                "home_team": home_team,
                                "away_team": away_team,
                                "date": current_date
                            })
                            continue
                        
                        # Match ID unique - Pour les live, on utilise uniquement league+teams+date
                        # pour éviter les doublons à chaque minute
                        if is_live:
                            match_id = f"{league_id}_{home_team}_{away_team}_{current_date}_LIVE"
                        else:
                            match_id = f"{league_id}_{home_team}_{away_team}_{current_date}_{match_time}"
                        
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
                        
                        # Scores
                        score_home = "0"
                        score_away = "0"
                        
                        try:
                            score_divs = el.find_elements(By.CSS_SELECTOR, "div.hidden[data-v-143a5c06]")
                            if len(score_divs) >= 2:
                                score_home = score_divs[0].text.strip() if score_divs[0].text.strip() else "0"
                                score_away = score_divs[1].text.strip() if score_divs[1].text.strip() else "0"
                        except:
                            pass
                        
                        # Datetime pour tri
                        try:
                            if is_live:
                                match_datetime = datetime.now()
                            else:
                                match_datetime = datetime.strptime(f"{current_date} {match_time}", "%d %b %Y %H:%M")
                        except:
                            match_datetime = datetime.now()
                        
                        match_data = {
                            "league_id": league_id,
                            "league_name": league_info['name'],
                            "country": league_info['country'],
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
                            "is_live": is_live,
                            "scraped_at": datetime.now()
                        }
                        
                        # Clé unique
                        if is_live:
                            collection.update_one(
                                {
                                    "league_id": league_id,
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
                                    "league_id": league_id,
                                    "home_team": home_team,
                                    "away_team": away_team,
                                    "date": current_date,
                                    "time": match_time
                                },
                                {"$set": match_data},
                                upsert=True
                            )
                        
                        matches_count += 1
                        
                    except StaleElementReferenceException:
                        errors_count += 1
                        continue
                    except Exception as e:
                        errors_count += 1
                        if errors_count <= 3:  # Afficher seulement les 3 premières erreurs
                            print(f"[WARN] Erreur sur un match (élément {idx}): {str(e)[:100]}")
                        continue
                
                print(f"[OK] {league_info['name']}: {matches_count} matchs scrapés ({errors_count} erreurs ignorées)")
                return matches_count
                
            finally:
                if driver:
                    driver.quit()
                    
        except Exception as e:
            print(f"[ERROR] Tentative {attempt + 1} échouée pour {league_info['name']}: {str(e)[:200]}")
            if attempt == max_retries - 1:
                print(f"[FAIL] Impossible de scraper {league_info['name']} après {max_retries} tentatives")
                traceback.print_exc()
                return 0
            continue
    
    return 0

def main():
    # Connexion MongoDB
    try:
        client = MongoClient("mongodb://mongodb:27017", serverSelectionTimeoutMS=5000)
        client.server_info()  # Test de connexion
        db = client["odds_db"]
        collection = db["matches"]
        print("[OK] Connexion MongoDB établie")
    except Exception as e:
        print(f"[FAIL] Impossible de se connecter à MongoDB: {e}")
        sys.exit(1)
    
    # Nettoyer les matchs de plus de 3 heures (probablement terminés)
    three_hours_ago = datetime.now() - timedelta(hours=3)
    deleted = collection.delete_many({
        "is_live": True,
        "datetime": {"$lt": three_hours_ago}
    })
    if deleted.deleted_count > 0:
        print(f"[INFO] {deleted.deleted_count} ancien(s) match(s) live nettoyé(s)")
    
    # Récupérer la ligue à scraper depuis les arguments
    if len(sys.argv) > 1:
        league_id = sys.argv[1]
        if league_id in LEAGUES:
            # Scraper une seule ligue
            scrape_league(league_id, LEAGUES[league_id], collection)
        else:
            print(f"[ERROR] Ligue inconnue: {league_id}")
            print(f"Ligues disponibles: {', '.join(LEAGUES.keys())}")
    else:
        # Scraper toutes les ligues
        print("[INFO] Scraping de toutes les ligues...")
        total = 0
        failed = []
        
        for league_id, league_info in LEAGUES.items():
            count = scrape_league(league_id, league_info, collection)
            total += count
            if count == 0:
                failed.append(league_info['name'])
            time.sleep(3)  # Pause entre chaque ligue
        
        print(f"\n[OK] Total: {total} matchs scrapés")
        if failed:
            print(f"[WARN] Ligues échouées: {', '.join(failed)}")

if __name__ == "__main__":
    main()