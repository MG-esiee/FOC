from flask import Flask, render_template
from pymongo import MongoClient
import os
from datetime import datetime

app = Flask(__name__)

# Connexion MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017/odds_db")  # service Docker
client = MongoClient(MONGO_URI)
db = client["odds_db"]
collection = db["matches"]

@app.route("/")
def home():
    try:
        matches = list(collection.find())
        # Convertir date + heure en objet datetime pour trier
        for match in matches:
            try:
                match["datetime_obj"] = datetime.strptime(f"{match['date']} {match['time']}", "%d %b %Y %H:%M")
            except:
                match["datetime_obj"] = datetime.max  # pour les matchs sans date/heure
        # Tri par date puis heure
        matches.sort(key=lambda x: x["datetime_obj"])
    except Exception as e:
        matches = []
        print(f"Erreur MongoDB : {e}")
    return render_template("index.html", matches=matches)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
