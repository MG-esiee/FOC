# FOC - First On Cotes

![FOC Logo](app/static/logo_FOC.png)

**FOC (First On Cotes)** est une application web temps réel qui scrape et affiche les cotes sportives des principales ligues européennes de football. Le site se met à jour automatiquement toutes les 10 secondes avec des données fraîches scrapées depuis OddsPortal.

---

## Table des matières

- [Fonctionnalités](#-fonctionnalités)
- [Technologies utilisées](#-technologies-utilisées)
- [Architecture](#-architecture)
- [Prérequis](#-prérequis)
- [Installation](#-installation)
- [Lancement](#-lancement)
- [Utilisation](#-utilisation)
- [API](#-api)
- [Configuration](#-configuration)
- [Dépannage](#-dépannage)
- [Auteurs](#-auteurs)

---

## Fonctionnalités

### Principales

- **Scraping automatique** des cotes depuis OddsPortal
- **Actualisation temps réel** toutes les 10 secondes (sans recharger la page)
- **Scraping initial** au démarrage de l'application
- **Auto-scraping** toutes les 3 minutes en arrière-plan
- **Détection des matchs live** avec badge "EN DIRECT"
- **Affichage des scores** en temps réel pour les matchs en cours
- **Tri intelligent** : matchs live en premier, puis par date/heure
- **Interface moderne** avec animations fluides
- **Fuseau horaire correct** (Europe/Paris)

### Ligues supportées

- 🇫🇷 **Ligue 1** (France)
- 🏴󠁧󠁢󠁥󠁮󠁧󠁿 **Premier League** (Angleterre)
- 🇪🇸 **La Liga** (Espagne)
- 🇮🇹 **Serie A** (Italie)
- 🇩🇪 **Bundesliga** (Allemagne)

### Fonctionnalités techniques

- **API REST** complète avec endpoints JSON
- **Base de données MongoDB** pour stockage des matchs
- **Nettoyage automatique** des matchs obsolètes
- **Gestion des doublons** et des matchs terminés
- **Retry automatique** en cas d'échec de scraping
- **Logs détaillés** pour le monitoring

---

## Technologies utilisées

### Backend

- **Python 3.11+**
- **Flask** - Framework web
- **Selenium** - Web scraping avec Chrome headless
- **MongoDB** - Base de données NoSQL
- **PyMongo** - Driver MongoDB pour Python

### Frontend

- **HTML5 / CSS3**
- **JavaScript (Vanilla)** - Pas de framework
- **Google Fonts** (Space Mono, Syne)
- **Animations CSS** personnalisées

### Infrastructure

- **Docker** & **Docker Compose**
- **Chrome/Chromium** avec ChromeDriver
- **MongoDB 7.0**

---

## Architecture

```
FOC/
├── app/
│   ├── app.py                 # Application Flask principale
│   ├── requirements.txt       # Dépendances Python (Flask)
│   ├── static/
│   │   ├── logo_FOC.png      # Logo
│   │   └── style.css         # Styles CSS
│   └── templates/
│       ├── index.html        # Page principale (matchs)
│       └── explore.html      # Page exploration par équipe
│
├── scraper/
│   ├── scraper_mongo.py      # Script de scraping Selenium
│   └── requirements.txt      # Dépendances Python (Selenium)
│
├── docker-compose.yml         # Configuration Docker
├── Dockerfile.flask          # Image Docker Flask
├── Dockerfile.scraper        # Image Docker Scraper
└── README.md                 # Ce fichier
```

### Flux de données

```
OddsPortal.com
      ↓
  Selenium (Chrome headless)
      ↓
  scraper_mongo.py (parsing)
      ↓
  MongoDB (stockage)
      ↓
  Flask API (endpoints JSON)
      ↓
  Frontend (affichage temps réel)
```

---

## Prérequis

### Logiciels requis

- **Docker Desktop** (Mac/Windows) ou **Docker Engine** (Linux)
- **Docker Compose** v2.0+
- **Git** (pour cloner le projet)

### Ports nécessaires

- **8000** - Application Flask
- **27017** - MongoDB

 Assurez-vous que ces ports sont libres avant de lancer l'application.

---

## Installation

### 1. Cloner le repository

```bash
git clone https://github.com/MG-esiee/FOC.git
cd FOC
```

### 2. Vérifier la structure

```bash
ls -la
# Vous devriez voir : app/, scraper/, docker-compose.yml
```

### 3. (Optionnel) Configurer les variables d'environnement

Le projet utilise les valeurs par défaut, mais vous pouvez personnaliser dans `docker-compose.yml` :

```yaml
environment:
  - MONGO_URI=mongodb://mongo:27017/odds_db
  - TZ=Europe/Paris
```

---

## 🎬 Lancement

### Démarrage rapide

```bash
# 1. Construire et démarrer tous les containers
docker-compose build
docker-compose up -d

# 2. Attendre 30 secondes que le scraping initial se termine
sleep 30

# 3. Vérifier que tout fonctionne
docker-compose ps
```

Vous devriez voir 3 containers "Up" :
- `flask_app` - Application web
- `mongo` - Base de données
- `scraper` - Service de scraping

### Accéder au site

Ouvrez votre navigateur :
```
http://localhost:8000
```

### Voir les logs en temps réel

```bash
# Logs de l'application Flask
docker-compose logs -f flask_app

# Logs du scraper
docker-compose logs -f scraper

# Tous les logs
docker-compose logs -f
```

### Arrêter l'application

```bash
# Arrêter les containers
docker-compose down

# Arrêter ET supprimer les données MongoDB
docker-compose down -v
```

---

## Utilisation

### Interface web

#### Page principale - Matchs

```
http://localhost:8000
http://localhost:8000/ligue-1
http://localhost:8000/premier-league
http://localhost:8000/la-liga
http://localhost:8000/serie-a
http://localhost:8000/bundesliga
```

**Fonctionnalités :**
- Liste des matchs en temps réel
- Badge "EN DIRECT" pour les matchs live
- Scores actualisés automatiquement
- Cotes (1, X, 2) pour chaque match
- Bouton "ACTUALISER" pour forcer un refresh
- Auto-refresh toutes les 10 secondes

#### Page exploration - Équipes

```
http://localhost:8000/explore/ligue-1
```

**Fonctionnalités :**
- Filtrer les matchs par équipe
- Visualiser l'historique d'une équipe
- Graphiques des cotes

### Console navigateur (F12)

Ouvrez la console pour voir les logs de l'auto-refresh :

```javascript
=================================
FOC - First On Cotes
Mode: Temps Réel Ultra-Rapide
Data refresh: 10 secondes
Auto-scraping: 3 minutes
=================================
[Fast-refresh] Mise à jour des données...
[Update] Récupération des nouvelles données...
[Update] Données reçues: {total: 99, live: 5, upcoming: 94}
```

---

## API

### Endpoints disponibles

#### 1. Statut de l'application

```bash
GET /api/status
```

**Réponse :**
```json
{
  "initial_scraping_done": true,
  "scraping_in_progress": false,
  "total_matches": 99
}
```

#### 2. Matchs d'une ligue

```bash
GET /api/matches/<league_id>
```

**Exemple :**
```bash
curl http://localhost:8000/api/matches/ligue-1
```

**Réponse :**
```json
{
  "status": "success",
  "league_id": "ligue-1",
  "league_name": "Ligue 1",
  "stats": {
    "total": 25,
    "live": 3,
    "upcoming": 22
  },
  "matches": [
    {
      "_id": "...",
      "league_id": "ligue-1",
      "home_team": "PSG",
      "away_team": "Lyon",
      "date": "08 Feb 2026",
      "time": "21:00",
      "odd_1": "1.45",
      "odd_x": "4.20",
      "odd_2": "6.50",
      "score_home": "0",
      "score_away": "0",
      "is_live": false
    }
  ],
  "updated_at": "2026-02-08T12:30:00"
}
```

#### 3. Liste des équipes

```bash
GET /api/teams/<league_id>
```

**Exemple :**
```bash
curl http://localhost:8000/api/teams/ligue-1
```

**Réponse :**
```json
{
  "status": "success",
  "league_id": "ligue-1",
  "teams": ["PSG", "Marseille", "Lyon", "Monaco", ...]
}
```

#### 4. Matchs d'une équipe

```bash
GET /api/team-matches/<league_id>?team=<team_name>
```

**Exemple :**
```bash
curl "http://localhost:8000/api/team-matches/ligue-1?team=PSG"
```

#### 5. Forcer un scraping

```bash
GET /api/refresh/<league_id>
```

**Exemple :**
```bash
curl http://localhost:8000/api/refresh/ligue-1
```

**Réponse :**
```json
{
  "status": "success",
  "message": "Scraping démarré",
  "league": "Ligue 1"
}
```

#### 6. Scraper toutes les ligues

```bash
GET /api/refresh-all
```

---

## Configuration

### Modifier la fréquence d'actualisation

#### Auto-refresh des données (frontend)

Dans `app/templates/index.html`, ligne ~17 du script JavaScript :

```javascript
}, 10000); // 10 secondes
// Changez en 5000 pour 5 secondes
// Changez en 30000 pour 30 secondes
```

#### Auto-scraping (backend)

Dans `app/app.py`, ligne ~105 :

```python
time.sleep(180)  # 3 minutes
# Changez en 120 pour 2 minutes
# Changez en 300 pour 5 minutes
```

### Modifier le fuseau horaire

Dans `scraper/scraper_mongo.py`, lignes 14-16 :

```python
import os
os.environ['TZ'] = 'Europe/Paris'  # Changez ici
time.tzset()
```

Fuseaux horaires disponibles :
- `Europe/Paris` (UTC+1/+2)
- `America/New_York` (EST/EDT)
- `Asia/Tokyo` (JST)
- etc.

### Ajouter une nouvelle ligue

Dans `scraper/scraper_mongo.py` et `app/app.py`, section `LEAGUES` :

```python
LEAGUES = {
    # Ligues existantes...
    "nouvelle-ligue": {
        "name": "Nouvelle Ligue",
        "url": "https://www.oddsportal.com/soccer/...",
        "country": "Pays",
        "icon": "🏴"
    }
}
```

---

## Dépannage

### Problème : Les containers ne démarrent pas

**Solution :**
```bash
# Voir les logs d'erreur
docker-compose logs

# Reconstruire les images
docker-compose build --no-cache
docker-compose up -d
```

### Problème : MongoDB ne démarre pas

**Cause possible :** Port 27017 déjà utilisé

**Solution :**
```bash
# Arrêter MongoDB local
brew services stop mongodb-community  # Mac
sudo systemctl stop mongod            # Linux

# Redémarrer Docker
docker-compose down
docker-compose up -d
```

### Problème : Les matchs ne s'affichent pas

**Vérification :**
```bash
# Vérifier le nombre de matchs en base
docker-compose exec mongo mongosh odds_db --eval "db.matches.countDocuments({})"

# Si 0, lancer un scraping manuel
docker-compose exec scraper python scraper_mongo.py ligue-1

# Vérifier à nouveau
docker-compose exec mongo mongosh odds_db --eval "db.matches.countDocuments({})"
```

### Problème : Décalage horaire de 1 heure

**Cause :** Fuseau horaire non configuré

**Solution :**

Vérifiez que `scraper/scraper_mongo.py` contient :
```python
import os
os.environ['TZ'] = 'Europe/Paris'
time.tzset()
```

Puis redémarrez :
```bash
docker-compose restart scraper
docker-compose exec scraper python scraper_mongo.py ligue-1
```

### Problème : Le scraping échoue (timeout, erreurs Selenium)

**Causes possibles :**
- Site OddsPortal temporairement indisponible
- Connexion internet lente
- Sélecteurs CSS modifiés sur OddsPortal

**Solutions :**
```bash
# Voir les logs détaillés
docker-compose logs scraper

# Augmenter le timeout dans scraper_mongo.py ligne 145
WebDriverWait(driver, 30)  # Passer à 60

# Retry manuel
docker-compose exec scraper python scraper_mongo.py ligue-1
```

### Problème : L'auto-refresh ne fonctionne pas

**Vérification :**
1. Ouvrir la console navigateur (F12)
2. Vérifier les logs JavaScript
3. Vérifier que `/api/matches/<league>` répond

**Solution :**
```bash
# Tester l'API manuellement
curl http://localhost:8000/api/matches/ligue-1

# Vider le cache du navigateur
Ctrl + Shift + R (Windows/Linux)
Cmd + Shift + R (Mac)
```

### Problème : "Port already in use"

**Solution :**
```bash
# Trouver le processus qui utilise le port 8000
lsof -i :8000  # Mac/Linux
netstat -ano | findstr :8000  # Windows

# Tuer le processus
kill -9 <PID>

# Ou changer le port dans docker-compose.yml
ports:
  - "8080:8000"  # Utiliser le port 8080 au lieu de 8000
```

---

## Commandes utiles

### Docker

```bash
# Voir les containers actifs
docker-compose ps

# Reconstruire les images
docker-compose build

# Voir les logs
docker-compose logs -f flask_app

# Se connecter dans un container
docker-compose exec flask_app bash

# Redémarrer un service
docker-compose restart flask_app

# Supprimer tout (containers + volumes)
docker-compose down -v
```

### MongoDB

```bash
# Compter les matchs
docker-compose exec mongo mongosh odds_db --eval "db.matches.countDocuments({})"

# Voir tous les matchs d'une ligue
docker-compose exec mongo mongosh odds_db --eval 'db.matches.find({league_id: "ligue-1"}).pretty()'

# Supprimer tous les matchs
docker-compose exec mongo mongosh odds_db --eval "db.matches.deleteMany({})"

# Voir les matchs live
docker-compose exec mongo mongosh odds_db --eval 'db.matches.find({is_live: true}).pretty()'
```

### Scraper

```bash
# Scraper une seule ligue
docker-compose exec scraper python scraper_mongo.py ligue-1

# Scraper toutes les ligues
docker-compose exec scraper python scraper_mongo.py

# Voir la version de Chrome
docker-compose exec scraper chromium --version
```

---

## Performance et optimisation

### Ressources utilisées

- **CPU** : Modéré (~30% pendant le scraping)
- **RAM** : ~500 MB (Chrome headless + Flask + MongoDB)
- **Réseau** : Modéré (~10 MB par scraping complet)

### Optimisations possibles

1. **Réduire la fréquence de scraping** : Passer de 3 à 5 minutes
2. **Scraper seulement la ligue active** : Au lieu de toutes les ligues
3. **Utiliser un cache Redis** : Pour les requêtes API fréquentes
4. **Pagination** : Pour les ligues avec beaucoup de matchs
5. **WebSockets** : Pour un vrai temps réel (au lieu de polling)

---

## Sécurité et bonnes pratiques

### Important en production

1. **Désactiver le mode debug** dans `app/app.py` :
   ```python
   app.run(host="0.0.0.0", port=8000, debug=False)
   ```

2. **Utiliser un serveur WSGI** (Gunicorn, uWSGI) au lieu du serveur Flask de dev

3. **Ajouter un reverse proxy** (Nginx) devant Flask

4. **Limiter le rate limiting** sur les endpoints API

5. **Ajouter de l'authentification** si l'application est publique

6. **Respecter les robots.txt** d'OddsPortal

---

## Possibles améliorations futures

### Fonctionnalités prévues

- [ ] **Historique des cotes** avec graphiques
- [ ] **Notifications** pour changements de cotes importants
- [ ] **Favoris** par équipe
- [ ] **Comparaison** de cotes entre bookmakers
- [ ] **Export PDF/Excel** des matchs
- [ ] **Mode sombre** pour l'interface
- [ ] **API GraphQL** en complément du REST
- [ ] **Application mobile** (React Native)
- [ ] **WebSockets** pour temps réel natif
- [ ] **Machine Learning** pour prédiction de résultats

---

## Auteurs

**Mateo Gallina et Timothée Crouzet** - ESIEE Paris
- GitHub: [@MG-esiee](https://github.com/MG-esiee)
- Github: [@TimotheeCrouzet](https://github.com/TimotheeCrouzet)
- Projet: [FOC - First On Cotes](https://github.com/MG-esiee/FOC)

---

##  Licence

Ce projet est un projet académique développé dans le cadre des études à l'ESIEE Paris.


---

## Contexte pédagogique

Ce projet a été développé dans le cadre d'un projet étudiant à l'ESIEE Paris. Il démontre :

- **Web scraping** avec Selenium
- **Architecture microservices** avec Docker
- **API REST** avec Flask
- **Base de données NoSQL** avec MongoDB
- **Frontend moderne** avec JavaScript vanilla
- **Temps réel** avec polling
- **DevOps** avec Docker Compose

---
