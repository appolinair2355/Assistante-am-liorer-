# Assista Kouamé — Déploiement Back4App Containers

## Prérequis
- Compte Back4App (https://www.back4app.com)
- Docker installé localement (pour tester)

## Fichiers importants
| Fichier | Rôle |
|---|---|
| `bot.py` | Code principal de la plateforme |
| `config.json` | Configuration IA, API, paramètres |
| `users.json` | Comptes utilisateurs enregistrés |
| `session.txt` | Session Telethon de l'admin |
| `users_data/` | Données par utilisateur (configs, groupes, secrétariat) |
| `secretary.json` | Base de contacts du secrétariat |

## Déploiement sur Back4App Containers

### Étape 1 — Créer une application Container
1. Connectez-vous sur https://www.back4app.com
2. Cliquez **"Build new app"** → **"Containers as a Service"**
3. Choisissez **"Deploy from GitHub"** ou **"Deploy from Docker"**

### Étape 2 — Upload via GitHub (recommandé)
1. Poussez ce dossier sur un repo GitHub **privé**
2. Connectez votre repo dans Back4App
3. Back4App détecte automatiquement le `Dockerfile`

### Étape 3 — Variables d'environnement
Dans l'interface Back4App → **"Environment Variables"**, ajoutez :
```
PORT=8080
```
*(Toutes les autres variables sont dans config.json)*

### Étape 4 — Port
Back4App utilisera le port **8080** (configuré dans le Dockerfile).

### Étape 5 — Ressources recommandées
- CPU : 0.5 vCPU minimum
- RAM : 512 MB minimum
- Stockage : Activez un volume persistant pour `/app/users_data`, `/app/config.json`, `/app/users.json`, `/app/session.txt`

## Test local avec Docker
```bash
docker-compose up --build
```

## ⚠️ Important — Persistance des données
Back4App Containers redémarre les conteneurs à chaque déploiement.
Les fichiers suivants DOIVENT être persistants (volume) sinon les données sont perdues :
- `users_data/` — configs et sessions utilisateurs
- `users.json` — comptes inscrits
- `config.json` — configuration
- `session.txt` — session Telethon admin
- `secretary.json` — historique secrétariat

## Variables d'environnement importantes
Toutes les valeurs sont préconfigurées. Si vous voulez personnaliser, ajoutez dans
Back4App → Settings → Environment Variables :
```
TELEGRAM_BOT_TOKEN=votre_token
TELEGRAM_API_HASH=votre_hash
TELEGRAM_SESSION=votre_session_string
GROQ_API_KEY=votre_cle_groq
PORT=8080
```

## Support
Plateforme développée par **Sossou Kouamé Apollinaire**
