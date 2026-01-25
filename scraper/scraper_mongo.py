from pymongo import MongoClient
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime

# Connexion à MongoDB
client = MongoClient("mongodb://mongodb:27017")
db = client["odds_db"]
collection = db["matches"]

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

driver.get("https://www.oddsportal.com/soccer/france/ligue-1/")
WebDriverWait(driver, 20).until(
    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[data-testid='game-row'], div.text-black-main"))
)

elements = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='game-row'], div.text-black-main.font-main.w-full.truncate.text-xs.font-normal.leading-5")

seen_matches = set()
current_date = None

def parse_date(date_str):
    date_str = date_str.strip()
    today = datetime.now()
    if "Today" in date_str:
        return f"{date_str.split(',')[1].strip()} {today.year}"
    parts = date_str.split()
    if len(parts) == 2:  # ex: "30 Jan"
        return f"{date_str} {today.year}"
    return date_str

for el in elements:
    # Si c'est une date
    if "text-black-main" in el.get_attribute("class"):
        current_date = parse_date(el.text)
        continue

    # Sinon c'est un match
    match = el
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

    # Heure
    try:
        match_time = match.find_element(By.CSS_SELECTOR, "div[data-testid='time-item'] p").text
    except:
        match_time = "00:00"

    # Cotes
    try:
        odds_elements = match.find_elements(By.CSS_SELECTOR, "div[data-testid^='odd-container'] p")
        if len(odds_elements) >= 3:
            odd_1 = odds_elements[0].text
            odd_x = odds_elements[1].text
            odd_2 = odds_elements[2].text
        else:
            odd_1 = odd_x = odd_2 = "-"
    except:
        odd_1 = odd_x = odd_2 = "-"

    # Scores
    try:
        score_elements = match.find_elements(By.CSS_SELECTOR, "div.hidden")
        score_home = score_elements[0].text if len(score_elements) >= 2 else "0"
        score_away = score_elements[1].text if len(score_elements) >= 2 else "0"
    except:
        score_home = "0"
        score_away = "0"

    # Datetime pour triage
    try:
        match_datetime = datetime.strptime(f"{current_date} {match_time}", "%d %b %Y %H:%M")
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
        "datetime": match_datetime
    }

    collection.update_one(
        {"home_team": home_team, "away_team": away_team},
        {"$set": match_data},
        upsert=True
    )

driver.quit()
print("Scraping terminé et stocké dans MongoDB !")
