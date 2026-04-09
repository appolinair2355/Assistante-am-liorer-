# config.py — Credentials du bot (préconfigurés)
# Les variables d'environnement ont priorité, sinon valeurs par défaut intégrées
import os

def _env(key, default=""):
    """Lit l'env var; retourne default si absent OU vide."""
    return os.environ.get(key, "").strip() or default

TELEGRAM_API_ID    = int(_env("TELEGRAM_API_ID",    "29177661"))
TELEGRAM_API_HASH  = _env("TELEGRAM_API_HASH",       "a8639172fa8d35dbfd8ea46286d349ab")
TELEGRAM_BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN",      "7653246287:AAH7-HVGo9EqUo8DWfhnleZSN3Y8Gp5_Nfg")
ADMIN_ID           = int(_env("ADMIN_ID",            "1190237801"))
PHONE_NUMBER       = _env("PHONE_NUMBER",            "+22995501564")
PORT               = int(_env("PORT",                "8080"))
GROQ_API_KEY       = _env("GROQ_API_KEY",            "")
GEMINI_API_KEY     = _env("GEMINI_API_KEY",          "")
TELEGRAM_SESSION   = _env("TELEGRAM_SESSION",        "")
