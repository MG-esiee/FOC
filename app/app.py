from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
import os
from datetime import datetime
import subprocess

app = Flask(__name__)

# Connexion MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017/odds_db")
client = MongoClient(MONGO_URI)
db = client["odds_db"]
collection = db["matches"]

# Configuration des ligues
LEAGUES = {
    "ligue-1": {"name": "Ligue 1", "country": "France", "icon": "🇫🇷"},
    "premier-league": {"name": "Premier League", "country": "England", "icon": "🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    "la-liga": {"name": "La Liga", "country": "Spain", "icon": "🇪🇸"},
    "serie-a": {"name": "Serie A", "country": "Italy", "icon": "🇮🇹"},
    "bundesliga": {"name": "Bundesliga", "country": "Germany", "icon": "🇩🇪"}
}

@app.route("/")
@app.route("/<league_id>")
def home(league_id="ligue-1"):
    try:
        # Vérifier si la ligue existe
        if league_id not in LEAGUES:
            league_id = "ligue-1"
        
        # Récupérer les matchs de la ligue sélectionnée
        matches = list(collection.find({"league_id": league_id}))
        
        # Tri : matchs live en premier, puis par datetime
        matches.sort(key=lambda x: x.get("datetime", datetime.max))
        
        # Informations de la ligue
        league_info = LEAGUES[league_id]
        
    except Exception as e:
        matches = []
        league_info = LEAGUES["ligue-1"]
        print(f"Erreur MongoDB : {e}")
    
    return render_template(
        "index.html", 
        matches=matches,
        current_league=league_id,
        league_info=league_info,
        all_leagues=LEAGUES
    )

@app.route("/api/refresh/<league_id>")
def refresh_league(league_id):
    """API pour déclencher le scraping d'une ligue"""
    try:
        if league_id not in LEAGUES:
            return jsonify({"error": "Ligue inconnue"}), 400
        
        # Lancer le scraping en arrière-plan
        subprocess.Popen(["python", "scraper_mongo.py", league_id])
        
        return jsonify({"status": "success", "message": "Scraping démarré"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)