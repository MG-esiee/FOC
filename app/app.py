from flask import Flask, render_template
from pymongo import MongoClient
import os
from datetime import datetime

app = Flask(__name__)

# Connexion MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017/odds_db")
client = MongoClient(MONGO_URI)
db = client["odds_db"]
collection = db["matches"]

@app.route("/")
def home():
    try:
        matches = list(collection.find())
        
        # Utiliser directement le champ datetime du scraper
        # Tri : matchs live (datetime récent) EN PREMIER, puis futurs par ordre chrono
        matches.sort(key=lambda x: x.get("datetime", datetime.max))
        
    except Exception as e:
        matches = []
        print(f"Erreur MongoDB : {e}")
    
    return render_template("index.html", matches=matches)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)