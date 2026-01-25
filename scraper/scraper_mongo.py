from pymongo import MongoClient
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Connexion à MongoDB dans Docker
client = MongoClient("mongodb://mongodb:27017")  # utiliser le nom du service docker
db = client["odds_db"]
collection = db["matches"]


# Créer les options Chrome **avant** de les configurer
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


driver.get("https://www.oddsportal.com/soccer/france/ligue-1/")
WebDriverWait(driver, 20).until(
    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[data-testid='game-row']"))
)

matches_elements = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='game-row']")
seen_matches = set()

for match in matches_elements:
    try:
        teams = match.find_elements(By.CSS_SELECTOR, "p.participant-name.truncate")
        home_team = teams[0].text
        away_team = teams[1].text
    except:
        continue

    match_id = f"{home_team} vs {away_team}"
    if match_id in seen_matches:
        continue
    seen_matches.add(match_id)

    try:
        match_time = match.find_element(By.CSS_SELECTOR, "div[data-testid='time-item'] p").text
    except:
        match_time = "NON TROUVÉ"

    try:
        
        odds_elements = match.find_elements(By.CSS_SELECTOR, "div[data-testid^='odd-container'] p")
        if len(odds_elements) >= 3:
            odd_1 = odds_elements[0].text
            odd_x = odds_elements[1].text
            odd_2 = odds_elements[2].text
        else:
            odd_1 = odd_x = odd_2 = "NON TROUVÉ"

    except:
        odd_1 = odd_x = odd_2 = "NON TROUVÉ"

    match_data = {
        "home_team": home_team,
        "away_team": away_team,
        "time": match_time,
        "odd_1": odd_1,
        "odd_x": odd_x,
        "odd_2": odd_2
    }

    collection.update_one({"home_team": home_team, "away_team": away_team}, {"$set": match_data}, upsert=True)

driver.quit()
print("Scraping terminé et stocké dans MongoDB !")
