from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
import os
from datetime import datetime
import subprocess
import threading
import time
from bson import ObjectId

app = Flask(__name__)

# Connexion MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017/odds_db")
client = MongoClient(MONGO_URI)
db = client["odds_db"]
collection = db["matches"]
bets_collection = db["bets"]  # ✅ NOUVELLE COLLECTION POUR LES PARIS

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
            print(f"[INIT] Scraping terminé avec des erreurs (code {result.returncode})")
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
                
                # ✅ Mettre à jour les résultats des paris après chaque scraping
                update_bets_results()
                
            except Exception as e:
                print(f"[BACKGROUND] ⚠️ Erreur: {e}")
    
    thread = threading.Thread(target=scrape_loop, daemon=True)
    thread.start()

def update_bets_results():
    """Mettre à jour les résultats des paris en cours"""
    try:
        # Récupérer tous les paris en cours
        pending_bets = list(bets_collection.find({"status": "pending"}))
        
        for bet in pending_bets:
            all_finished = True
            all_won = True
            
            for selection in bet['selections']:
                # Récupérer le match correspondant
                match = collection.find_one({
                    "league_id": selection['league_id'],
                    "home_team": selection['home_team'],
                    "away_team": selection['away_team']
                })
                
                if not match or not match.get('is_finished', False):
                    all_finished = False
                    break
                
                # Vérifier si la sélection est gagnante
                bet_type = selection['bet_type']
                score_home = int(match.get('score_home', 0))
                score_away = int(match.get('score_away', 0))
                
                won = False
                if bet_type == '1' and score_home > score_away:
                    won = True
                elif bet_type == 'X' and score_home == score_away:
                    won = True
                elif bet_type == '2' and score_home < score_away:
                    won = True
                
                if not won:
                    all_won = False
            
            # Mettre à jour le statut du pari
            if all_finished:
                new_status = "won" if all_won else "lost"
                bets_collection.update_one(
                    {"_id": bet['_id']},
                    {"$set": {"status": new_status, "resolved_at": datetime.now()}}
                )
                print(f"[BETS] Pari {bet['_id']} résolu: {new_status}")
        
    except Exception as e:
        print(f"[BETS] Erreur mise à jour paris: {e}")

@app.route("/")
@app.route("/<league_id>")
def home(league_id="ligue-1"):
    try:
        if league_id not in LEAGUES:
            league_id = "ligue-1"
        
        matches = list(collection.find({"league_id": league_id}))
        # Tri : Live en premier, puis à venir, puis terminés
        matches.sort(key=lambda x: (
            not x.get("is_live", False),      # Live d'abord
            x.get("is_finished", False),       # Puis à venir
            x.get("datetime", datetime.max)    # Puis par date
        ))
        
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

@app.route("/my-bets")
def my_bets():
    try:
        # On récupère tout pour vérifier
        all_pending = list(bets_collection.find({"status": "pending"}).sort("created_at", -1))
        all_finished = list(bets_collection.find({"status": {"$in": ["won", "lost"]}}).sort("resolved_at", -1))

        for bet in all_pending + all_finished:
            bet['_id'] = str(bet['_id'])
            # Vérification sécurisée du type avant strftime
            if 'created_at' in bet and isinstance(bet['created_at'], datetime):
                bet['created_at'] = bet['created_at'].strftime('%d/%m/%Y %H:%M')
            if 'resolved_at' in bet and isinstance(bet['resolved_at'], datetime):
                bet['resolved_at'] = bet['resolved_at'].strftime('%d/%m/%Y %H:%M')

        return render_template("my_bets.html", 
                               pending_bets=all_pending, 
                               finished_bets=all_finished, 
                               all_leagues=LEAGUES)
    except Exception as e:
        print(f"ERREUR AFFICHAGE PARIS : {e}")
        return f"Erreur interne : {e}", 500

@app.route("/api/matches/<league_id>")
def get_matches(league_id):
    """API pour récupérer les matchs en JSON (sans recharger la page)"""
    try:
        if league_id not in LEAGUES:
            return jsonify({"error": "Ligue inconnue"}), 400
        
        matches = list(collection.find({"league_id": league_id}))
        matches.sort(key=lambda x: (not x.get("is_live", False), x.get("datetime", datetime.max)))
        
        for match in matches:
            match['_id'] = str(match['_id'])
            if 'datetime' in match:
                match['datetime'] = match['datetime'].isoformat()
            if 'scraped_at' in match:
                match['scraped_at'] = match['scraped_at'].isoformat()
        
        total = len(matches)
        live = len([m for m in matches if m.get('is_live', False)])
        finished = len([m for m in matches if m.get('is_finished', False)])
        upcoming = total - live - finished

        return jsonify({
            "status": "success",
            "league_id": league_id,
            "league_name": LEAGUES[league_id]['name'],
            "stats": {
                "total": total,
                "live": live,
                "upcoming": upcoming,
                "finished": finished
            },
            "matches": matches,
            "updated_at": datetime.now().isoformat()
        })
                
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ NOUVELLE ROUTE : Placer un pari
@app.route("/api/place-bet", methods=["POST"])
def place_bet():
    try:
        data = request.get_json()
        # Debug pour voir ce que le serveur reçoit réellement
        print(f"DONNÉES REÇUES : {data}") 

        selections = data.get('selections', [])
        stake = float(data.get('stake', 10)) # Conversion forcée en float

        if not selections:
            return jsonify({"error": "Aucune sélection"}), 400

        total_odd = 1.0
        for s in selections:
            total_odd *= float(s['odd'])

        bet = {
            "selections": selections,
            "stake": stake,
            "total_odd": round(total_odd, 2),
            "potential_win": round(stake * total_odd, 2),
            "status": "pending",
            "created_at": datetime.now(), # Utilise datetime.now() sans strftime ici
            "resolved_at": None
        }

        result = bets_collection.insert_one(bet)
        print(f"PARI INSÉRÉ AVEC ID : {result.inserted_id}")
        
        return jsonify({"status": "success", "bet_id": str(result.inserted_id)})
    except Exception as e:
        print(f"ERREUR INSERTION : {e}")
        return jsonify({"error": str(e)}), 500

# ✅ NOUVELLE ROUTE : Récupérer les paris
@app.route("/api/my-bets")
def get_my_bets():
    """API pour récupérer tous les paris"""
    try:
        bets = list(bets_collection.find().sort("created_at", -1))
        
        for bet in bets:
            bet['_id'] = str(bet['_id'])
            if 'created_at' in bet:
                bet['created_at'] = bet['created_at'].isoformat()
            if 'resolved_at' in bet and bet['resolved_at']:
                bet['resolved_at'] = bet['resolved_at'].isoformat()
        
        return jsonify({
            "status": "success",
            "bets": bets
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
                update_bets_results()
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
        "total_matches": collection.count_documents({}),
        "total_bets": bets_collection.count_documents({})
    })

if __name__ == "__main__":
    # Scraping initial au démarrage
    initial_thread = threading.Thread(target=initial_scrape, daemon=True)
    initial_thread.start()
    
    # Scraping automatique
    start_background_scraping()
    
    # Démarrer Flask
    print("FOC - First On Cotes")
    print("Scraping initial en cours...")
    print("Auto-refresh: toutes les 3 minutes")
    app.run(host="0.0.0.0", port=8000, debug=True, use_reloader=False)