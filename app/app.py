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
bets_collection = db["bets"]

# Configuration des ligues
LEAGUES = {
    "ligue-1": {"name": "Ligue 1", "country": "France", "icon": "🇫🇷"},
    "premier-league": {"name": "Premier League", "country": "England", "icon": "🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    "la-liga": {"name": "La Liga", "country": "Spain", "icon": "🇪🇸"},
    "serie-a": {"name": "Serie A", "country": "Italy", "icon": "🇮🇹"},
    "bundesliga": {"name": "Bundesliga", "country": "Germany", "icon": "🇩🇪"}
}

# Variables globales pour suivre l'état
initial_scraping_done = False
scraping_in_progress = False
scraping_status = {
    "phase": "starting",  # starting, scraping, ready
    "message": "Initialisation...",
    "progress": 0,
    "leagues_done": 0,
    "total_leagues": len(LEAGUES)
}

def update_scraping_status(phase, message, progress=None):
    """Mettre à jour le statut du scraping pour l'afficher côté client"""
    global scraping_status
    scraping_status["phase"] = phase
    scraping_status["message"] = message
    if progress is not None:
        scraping_status["progress"] = progress
    print(f"[STATUS] {phase.upper()}: {message} ({progress}%)" if progress else f"[STATUS] {phase.upper()}: {message}")

def initial_scrape():
    """Scraping initial au démarrage de l'application"""
    global initial_scraping_done, scraping_in_progress, scraping_status
    
    if scraping_in_progress:
        print("[INIT] Scraping déjà en cours, abandon...")
        return
    
    scraping_in_progress = True
    update_scraping_status("starting", "Connexion à MongoDB...", 5)
    
    try:
        # Attendre que MongoDB soit prêt
        for i in range(10):
            try:
                client.server_info()
                print("[INIT] MongoDB connecté")
                update_scraping_status("starting", "MongoDB connecté", 10)
                break
            except:
                print(f"[INIT] ⏳ Attente MongoDB... ({i+1}/10)")
                update_scraping_status("starting", f"Attente MongoDB ({i+1}/10)...", 5 + i)
                time.sleep(2)
        
        # Lancer le scraping de toutes les ligues
        update_scraping_status("scraping", "Scraping des ligues en cours...", 20)
        print("[INIT] Lancement du scraping de toutes les ligues...")
        
        result = subprocess.run(
            ["python", "scraper/scraper_mongo.py"],
            timeout=300,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("[INIT]  Scraping initial terminé avec succès")
            print(result.stdout)
            update_scraping_status("ready", "Données chargées avec succès", 100)
        else:
            print(f"[INIT] Scraping terminé avec des erreurs (code {result.returncode})")
            print(result.stderr)
            update_scraping_status("ready", "Données partiellement chargées", 100)
        
        initial_scraping_done = True
        
    except subprocess.TimeoutExpired:
        print("[INIT]  Timeout du scraping initial (5 minutes)")
        update_scraping_status("ready", "Timeout - Données partielles", 100)
        initial_scraping_done = True
    except Exception as e:
        print(f"[INIT]  Erreur lors du scraping initial: {e}")
        update_scraping_status("ready", f"Erreur: {str(e)[:50]}", 100)
        initial_scraping_done = True
    finally:
        scraping_in_progress = False


def start_background_scraping():
    """Démarrer le scraping en arrière-plan toutes les 3 minutes"""
    def scrape_loop():
        # Attendre que le scraping initial soit terminé
        while not initial_scraping_done:
            time.sleep(5)
        
        print("[BACKGROUND]  Scraping automatique activé (toutes les 3 minutes)")
        
        while True:
            time.sleep(180)  # 3 minutes
            
            if scraping_in_progress:
                print("[BACKGROUND] Scraping déjà en cours, skip...")
                continue
            
            print("[BACKGROUND]  Scraping automatique...")
            try:
                subprocess.run(
                    ["python", "scraper/scraper_mongo.py"],
                    timeout=120,
                    capture_output=True
                )
                print("[BACKGROUND]  Scraping automatique terminé")
                
                # Mettre à jour les résultats des paris après chaque scraping
                update_bets_results()
                
            except Exception as e:
                print(f"[BACKGROUND]  Erreur: {e}")
    
    thread = threading.Thread(target=scrape_loop, daemon=True)
    thread.start()

def update_bets_results():
    """Mettre à jour les résultats des paris en cours"""
    try:
        pending_bets = list(bets_collection.find({"status": "pending"}))
        
        for bet in pending_bets:
            all_finished = True
            all_won = True
            
            for selection in bet['selections']:
                match = collection.find_one({
                    "league_id": selection['league_id'],
                    "home_team": selection['home_team'],
                    "away_team": selection['away_team']
                })
                
                if not match or not match.get('is_finished', False):
                    all_finished = False
                    break
                
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
        matches.sort(key=lambda x: (
            not x.get("is_live", False),
            x.get("is_finished", False),
            x.get("datetime", datetime.max)
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
        all_pending = list(bets_collection.find({"status": "pending"}).sort("created_at", -1))
        all_finished = list(bets_collection.find({"status": {"$in": ["won", "lost"]}}).sort("resolved_at", -1))

        for bet in all_pending + all_finished:
            bet['_id'] = str(bet['_id'])
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

@app.route("/api/place-bet", methods=["POST"])
def place_bet():
    try:
        data = request.get_json()
        print(f"DONNÉES REÇUES : {data}") 

        selections = data.get('selections', [])
        stake = float(data.get('stake', 10))

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
            "created_at": datetime.now(),
            "resolved_at": None
        }

        result = bets_collection.insert_one(bet)
        print(f"PARI INSÉRÉ AVEC ID : {result.inserted_id}")
        
        return jsonify({"status": "success", "bet_id": str(result.inserted_id)})
    except Exception as e:
        print(f"ERREUR INSERTION : {e}")
        return jsonify({"error": str(e)}), 500

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

@app.route("/graphics")
@app.route("/graphics/<league_id>")
def graphics(league_id="ligue-1"):
    """Page des graphiques et statistiques."""
    try:
        if league_id not in LEAGUES:
            league_id = "ligue-1"

        league_info = LEAGUES[league_id]
    except Exception as e:
        print(f"Erreur MongoDB : {e}")
        league_info = LEAGUES["ligue-1"]

    return render_template(
        "graphics.html",
        current_league=league_id,
        league_info=league_info,
        all_leagues=LEAGUES
    )

@app.route("/api/stats/<league_id>")
def get_stats(league_id):
    """API pour récupérer les statistiques d'une ligue"""
    try:
        if league_id not in LEAGUES:
            return jsonify({"error": "Ligue inconnue"}), 400

        matches = list(collection.find({"league_id": league_id}))
        
        # Statistiques par équipe
        team_stats = {}
        
        for match in matches:
            home_team = match.get('home_team')
            away_team = match.get('away_team')
            
            # Initialiser les équipes
            if home_team and home_team not in team_stats:
                team_stats[home_team] = {'played': 0, 'wins': 0, 'draws': 0, 'losses': 0}
            if away_team and away_team not in team_stats:
                team_stats[away_team] = {'played': 0, 'wins': 0, 'draws': 0, 'losses': 0}
            
            # Compter seulement les matchs terminés
            if match.get('is_finished'):
                score_home = int(match.get('score_home', 0))
                score_away = int(match.get('score_away', 0))
                
                if home_team:
                    team_stats[home_team]['played'] += 1
                    if score_home > score_away:
                        team_stats[home_team]['wins'] += 1
                    elif score_home == score_away:
                        team_stats[home_team]['draws'] += 1
                    else:
                        team_stats[home_team]['losses'] += 1
                
                if away_team:
                    team_stats[away_team]['played'] += 1
                    if score_away > score_home:
                        team_stats[away_team]['wins'] += 1
                    elif score_away == score_home:
                        team_stats[away_team]['draws'] += 1
                    else:
                        team_stats[away_team]['losses'] += 1
        
        # Stats générales
        total_matches = len(matches)
        finished = len([m for m in matches if m.get('is_finished')])
        live = len([m for m in matches if m.get('is_live')])
        
        # Récupérer les cotes (avec les bons noms de champs)
        odds_1 = []
        odds_x = []
        odds_2 = []
        
        for m in matches:
            try:
                if m.get('odd_1'):
                    odds_1.append(float(m.get('odd_1')))
                if m.get('odd_x'):
                    odds_x.append(float(m.get('odd_x')))
                if m.get('odd_2'):
                    odds_2.append(float(m.get('odd_2')))
            except:
                pass
        
        return jsonify({
            "status": "success",
            "league_id": league_id,
            "league_name": LEAGUES[league_id]['name'],
            "summary": {
                "total_matches": total_matches,
                "finished": finished,
                "live": live,
                "upcoming": total_matches - finished - live
            },
            "team_stats": team_stats,
            "odds": {
                "avg_1": round(sum(odds_1) / len(odds_1), 2) if odds_1 else 0,
                "avg_x": round(sum(odds_x) / len(odds_x), 2) if odds_x else 0,
                "avg_2": round(sum(odds_2) / len(odds_2), 2) if odds_2 else 0,
                "min_1": min(odds_1) if odds_1 else 0,
                "max_1": max(odds_1) if odds_1 else 0,
                "samples": len(odds_1)
            }
        })
    except Exception as e:
        print(f"Error in get_stats: {e}")
        return jsonify({"error": str(e)}), 500
        
        return jsonify({
            "status": "success",
            "league_id": league_id,
            "league_name": LEAGUES[league_id]['name'],
            "summary": {
                "total_matches": total_matches,
                "finished": finished,
                "live": live,
                "upcoming": total_matches - finished - live
            },
            "team_stats": team_stats,
            "odds": {
                "avg_odds_1": round(sum(odds_1) / len(odds_1), 2) if odds_1 else 0,
                "avg_odds_x": round(sum(odds_x) / len(odds_x), 2) if odds_x else 0,
                "avg_odds_2": round(sum(odds_2) / len(odds_2), 2) if odds_2 else 0
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/odds-distribution/<league_id>")
def get_odds_distribution(league_id):
    """API pour récupérer la distribution des cotes"""
    try:
        if league_id not in LEAGUES:
            return jsonify({"error": "Ligue inconnue"}), 400

        matches = list(collection.find({"league_id": league_id}))
        
        odds_1 = []
        odds_x = []
        odds_2 = []
        
        for m in matches:
            try:
                if m.get('odd_1'):
                    odds_1.append(float(m.get('odd_1')))
                if m.get('odd_x'):
                    odds_x.append(float(m.get('odd_x')))
                if m.get('odd_2'):
                    odds_2.append(float(m.get('odd_2')))
            except:
                pass
        
        return jsonify({
            "status": "success",
            "odds_1": odds_1,
            "odds_x": odds_x,
            "odds_2": odds_2
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/odds-extremes/<league_id>")
def get_odds_extremes(league_id):
    """API pour récupérer les 5 plus hautes et 5 plus basses cotes"""
    try:
        if league_id not in LEAGUES:
            return jsonify({"error": "Ligue inconnue"}), 400

        matches = list(collection.find({"league_id": league_id}))
        
        all_odds = []
        
        for m in matches:
            # Ajouter chaque cote avec le contexte du match
            try:
                if m.get('odd_1'):
                    all_odds.append({
                        'value': float(m.get('odd_1')),
                        'type': 'Domicile',
                        'home': m.get('home_team'),
                        'away': m.get('away_team'),
                        'date': m.get('date', '')
                    })
            except:
                pass
            try:
                if m.get('odd_x'):
                    all_odds.append({
                        'value': float(m.get('odd_x')),
                        'type': 'Nul',
                        'home': m.get('home_team'),
                        'away': m.get('away_team'),
                        'date': m.get('date', '')
                    })
            except:
                pass
            try:
                if m.get('odd_2'):
                    all_odds.append({
                        'value': float(m.get('odd_2')),
                        'type': 'Extérieur',
                        'home': m.get('home_team'),
                        'away': m.get('away_team'),
                        'date': m.get('date', '')
                    })
            except:
                pass
        
        # Trier et récupérer les extrêmes
        sorted_low = sorted(all_odds, key=lambda x: x['value'])[:5]
        sorted_high = sorted(all_odds, key=lambda x: x['value'], reverse=True)[:5]
        
        return jsonify({
            "status": "success",
            "lowest": sorted_low,
            "highest": sorted_high,
            "total_odds": len(all_odds)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/team-odds/<league_id>")
def get_team_odds(league_id):
    """API pour récupérer toutes les cotes d'une équipe et la moyenne de la ligue"""
    try:
        if league_id not in LEAGUES:
            return jsonify({"error": "Ligue inconnue"}), 400

        team = request.args.get("team", "").strip()
        if not team:
            return jsonify({"error": "Paramètre 'team' manquant"}), 400

        matches = list(collection.find({"league_id": league_id}))
        
        # Récupérer les cotes de l'équipe
        team_odds = []
        for m in matches:
            is_home = m.get('home_team') == team
            is_away = m.get('away_team') == team
            
            if is_home:
                try:
                    if m.get('odd_1'):
                        team_odds.append({
                            'value': float(m.get('odd_1')),
                            'type': 'Domicile',
                            'vs': m.get('away_team'),
                            'date': m.get('date', '')
                        })
                except:
                    pass
            elif is_away:
                try:
                    if m.get('odd_2'):
                        team_odds.append({
                            'value': float(m.get('odd_2')),
                            'type': 'Extérieur',
                            'vs': m.get('home_team'),
                            'date': m.get('date', '')
                        })
                except:
                    pass
        
        # Calculer les moyennes de la ligue
        all_odds_1 = []
        all_odds_x = []
        all_odds_2 = []
        for m in matches:
            try:
                if m.get('odd_1'):
                    all_odds_1.append(float(m.get('odd_1')))
                if m.get('odd_x'):
                    all_odds_x.append(float(m.get('odd_x')))
                if m.get('odd_2'):
                    all_odds_2.append(float(m.get('odd_2')))
            except:
                pass
        
        league_avg = {
            'domicile': round(sum(all_odds_1) / len(all_odds_1), 2) if all_odds_1 else 0,
            'nul': round(sum(all_odds_x) / len(all_odds_x), 2) if all_odds_x else 0,
            'exterieur': round(sum(all_odds_2) / len(all_odds_2), 2) if all_odds_2 else 0
        }
        
        return jsonify({
            "status": "success",
            "team": team,
            "team_odds": team_odds,
            "league_avg": league_avg
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/all-odds/<league_id>")
def get_all_odds(league_id):
    """API pour récupérer toutes les cotes de la ligue avec détails des matchs"""
    try:
        if league_id not in LEAGUES:
            return jsonify({"error": "Ligue inconnue"}), 400

        matches = list(collection.find({"league_id": league_id}))
        
        all_odds = []
        odds_with_details = []
        
        for m in matches:
            try:
                home = m.get('home_team', 'N/A')
                away = m.get('away_team', 'N/A')
                date = m.get('date', 'N/A')
                
                if m.get('odd_1'):
                    odd_val = float(m.get('odd_1'))
                    all_odds.append(odd_val)
                    odds_with_details.append({
                        "value": odd_val,
                        "home": home,
                        "away": away,
                        "type": "Domicile",
                        "date": date,
                        "match": f"{home} vs {away}"
                    })
                
                if m.get('odd_x'):
                    odd_val = float(m.get('odd_x'))
                    all_odds.append(odd_val)
                    odds_with_details.append({
                        "value": odd_val,
                        "home": home,
                        "away": away,
                        "type": "Nul",
                        "date": date,
                        "match": f"{home} vs {away}"
                    })
                
                if m.get('odd_2'):
                    odd_val = float(m.get('odd_2'))
                    all_odds.append(odd_val)
                    odds_with_details.append({
                        "value": odd_val,
                        "home": home,
                        "away": away,
                        "type": "Extérieur",
                        "date": date,
                        "match": f"{home} vs {away}"
                    })
            except:
                pass
        
        all_odds_sorted = sorted(all_odds)
        
        return jsonify({
            "status": "success",
            "all_odds": all_odds_sorted,
            "odds_with_details": odds_with_details,
            "min": min(all_odds) if all_odds else 0,
            "max": max(all_odds) if all_odds else 0,
            "avg": round(sum(all_odds) / len(all_odds), 2) if all_odds else 0,
            "count": len(all_odds)
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
        "total_bets": bets_collection.count_documents({}),
        "scraping_status": scraping_status
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
    print("⚡ Actualisation rapide: toutes les 10 secondes")
    app.run(host="0.0.0.0", port=8000, debug=True, use_reloader=False)