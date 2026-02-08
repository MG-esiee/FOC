from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
import os
from datetime import datetime
import subprocess
import threading
import time

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

# Variable globale pour suivre l'état du scraping initial
initial_scraping_done = False
scraping_in_progress = False

def initial_scrape():
    """Scraping initial au démarrage de l'application"""
    global initial_scraping_done, scraping_in_progress
    
    if scraping_in_progress:
        print("[INIT] Scraping déjà en cours, abandon...")
        return
    
    scraping_in_progress = True
    print("[INIT] SCRAPING INITIAL AU DÉMARRAGE")
    
    try:
        # Attendre que MongoDB soit prêt
        for i in range(10):
            try:
                client.server_info()
                print("[INIT] MongoDB connecté")
                break
            except:
                print(f"[INIT] ⏳ Attente MongoDB... ({i+1}/10)")
                time.sleep(2)
        
        # Lancer le scraping de toutes les ligues
        print("[INIT] 📡 Lancement du scraping de toutes les ligues...")
        result = subprocess.run(
            ["python", "scraper/scraper_mongo.py"],
            timeout=300,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("[INIT] Scraping initial terminé avec succès")
            print(result.stdout)
        else:
            print(f"[INIT]  Scraping terminé avec des erreurs (code {result.returncode})")
            print(result.stderr)
        
        initial_scraping_done = True
        
    except subprocess.TimeoutExpired:
        print("[INIT] Timeout du scraping initial (5 minutes)")
    except Exception as e:
        print(f"[INIT] Erreur lors du scraping initial: {e}")
    finally:
        scraping_in_progress = False
        print("=" * 60)

def start_background_scraping():
    """Démarrer le scraping en arrière-plan toutes les 3 minutes"""
    def scrape_loop():
        # Attendre que le scraping initial soit terminé
        while not initial_scraping_done:
            time.sleep(5)
        
        print("[BACKGROUND] 🔄 Scraping automatique activé (toutes les 3 minutes)")
        
        while True:
            time.sleep(180)  # 3 minutes
            
            if scraping_in_progress:
                print("[BACKGROUND] Scraping déjà en cours, skip...")
                continue
            
            print("[BACKGROUND] 🔄 Scraping automatique...")
            try:
                subprocess.run(
                    ["python", "scraper/scraper_mongo.py"],
                    timeout=120,
                    capture_output=True
                )
                print("[BACKGROUND] Scraping automatique terminé")
            except Exception as e:
                print(f"[BACKGROUND] ⚠️  Erreur: {e}")
    
    thread = threading.Thread(target=scrape_loop, daemon=True)
    thread.start()

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
        matches.sort(key=lambda x: (not x.get("is_live", False), x.get("datetime", datetime.max)))
        
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
        all_leagues=LEAGUES,
        initial_scraping_done=initial_scraping_done
    )

@app.route("/explore")
@app.route("/explore/<league_id>")
def explore(league_id="ligue-1"):
    """Page pour filtrer par équipe et visualiser les cotes."""
    try:
        if league_id not in LEAGUES:
            league_id = "ligue-1"

        matches = list(collection.find({"league_id": league_id}))
        matches.sort(key=lambda x: (not x.get("is_live", False), x.get("datetime", datetime.max)))

        teams = set()
        for match in matches:
            if match.get("home_team"):
                teams.add(match["home_team"])
            if match.get("away_team"):
                teams.add(match["away_team"])

        league_info = LEAGUES[league_id]
    except Exception as e:
        print(f"Erreur MongoDB : {e}")
        matches = []
        teams = set()
        league_info = LEAGUES["ligue-1"]

    return render_template(
        "explore.html",
        current_league=league_id,
        league_info=league_info,
        all_leagues=LEAGUES,
        teams=sorted(teams)
    )

@app.route("/api/matches/<league_id>")
def get_matches(league_id):
    """API pour récupérer les matchs en JSON (sans recharger la page)"""
    try:
        if league_id not in LEAGUES:
            return jsonify({"error": "Ligue inconnue"}), 400
        
        # Récupérer les matchs
        matches = list(collection.find({"league_id": league_id}))
        
        # Tri : matchs live en premier, puis par datetime
        matches.sort(key=lambda x: (not x.get("is_live", False), x.get("datetime", datetime.max)))
        
        # Convertir ObjectId en string pour JSON
        for match in matches:
            match['_id'] = str(match['_id'])
            # Convertir datetime en string
            if 'datetime' in match:
                match['datetime'] = match['datetime'].isoformat()
            if 'scraped_at' in match:
                match['scraped_at'] = match['scraped_at'].isoformat()
        
        # Stats
        total = len(matches)
        live = len([m for m in matches if m.get('is_live', False)])
        upcoming = total - live
        
        return jsonify({
            "status": "success",
            "league_id": league_id,
            "league_name": LEAGUES[league_id]['name'],
            "stats": {
                "total": total,
                "live": live,
                "upcoming": upcoming
            },
            "matches": matches,
            "updated_at": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/teams/<league_id>")
def get_teams(league_id):
    """API pour récupérer la liste des équipes d'une ligue."""
    try:
        if league_id not in LEAGUES:
            return jsonify({"error": "Ligue inconnue"}), 400

        matches = list(collection.find({"league_id": league_id}))
        teams = set()
        for match in matches:
            if match.get("home_team"):
                teams.add(match["home_team"])
            if match.get("away_team"):
                teams.add(match["away_team"])

        return jsonify({
            "status": "success",
            "league_id": league_id,
            "teams": sorted(teams)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/team-matches/<league_id>")
def get_team_matches(league_id):
    """API pour récupérer les matchs d'une équipe."""
    try:
        if league_id not in LEAGUES:
            return jsonify({"error": "Ligue inconnue"}), 400

        team = request.args.get("team", "").strip()
        if not team:
            return jsonify({"error": "Paramètre 'team' manquant"}), 400

        matches = list(collection.find({
            "league_id": league_id,
            "$or": [{"home_team": team}, {"away_team": team}]
        }))

        matches.sort(key=lambda x: (not x.get("is_live", False), x.get("datetime", datetime.max)))

        for match in matches:
            match["_id"] = str(match["_id"])
            if "datetime" in match:
                match["datetime"] = match["datetime"].isoformat()
            if "scraped_at" in match:
                match["scraped_at"] = match["scraped_at"].isoformat()

        return jsonify({
            "status": "success",
            "league_id": league_id,
            "team": team,
            "count": len(matches),
            "matches": matches
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/refresh/<league_id>")
def refresh_league(league_id):
    """API pour déclencher le scraping d'une ligue"""
    try:
        if league_id not in LEAGUES:
            return jsonify({"error": "Ligue inconnue"}), 400
        
        # Lancer le scraping en arrière-plan (non-bloquant)
        def run_scraper():
            try:
                print(f"[Scraping] Démarrage {LEAGUES[league_id]['name']}...", flush=True)
                result = subprocess.run(
                    ["python", "scraper/scraper_mongo.py", league_id],
                    timeout=120
                )
                if result.returncode != 0:
                    print(f"[Scraping] Erreur (code {result.returncode})", flush=True)
                else:
                    print(f"[Scraping] {LEAGUES[league_id]['name']} terminé", flush=True)
            except Exception as e:
                print(f"[Scraping] Erreur: {e}")
        
        thread = threading.Thread(target=run_scraper, daemon=True)
        thread.start()
        
        return jsonify({
            "status": "success", 
            "message": "Scraping démarré",
            "league": LEAGUES[league_id]['name']
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/refresh-all")
def refresh_all():
    """API pour scraper TOUTES les ligues"""
    try:
        def run_scraper():
            global scraping_in_progress
            scraping_in_progress = True
            try:
                subprocess.run(
                    ["python", "scraper/scraper_mongo.py"],
                    timeout=300,
                    capture_output=True
                )
                print("[Scraping] Toutes les ligues terminées")
            except Exception as e:
                print(f"[Scraping] Erreur: {e}")
            finally:
                scraping_in_progress = False
        
        thread = threading.Thread(target=run_scraper, daemon=True)
        thread.start()
        
        return jsonify({
            "status": "success",
            "message": "Scraping de toutes les ligues démarré"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/status")
def get_status():
    """API pour vérifier le statut du scraping"""
    return jsonify({
        "initial_scraping_done": initial_scraping_done,
        "scraping_in_progress": scraping_in_progress,
        "total_matches": collection.count_documents({})
    })

if __name__ == "__main__":
    # scraping intial au démarrage
    initial_thread = threading.Thread(target=initial_scrape, daemon=True)
    initial_thread.start()
    
    # scraping auto
    start_background_scraping()
    
    # Démarrer Flask
    print("FOC - First On Cotes")
    print("Scraping initial en cours...")
    print("Auto-refresh: toutes les 3 minutes")
    app.run(host="0.0.0.0", port=8000, debug=True, use_reloader=False)