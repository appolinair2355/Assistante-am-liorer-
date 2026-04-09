"""
Bot Userbot — Plateforme SaaS Multi-Utilisateur
Multi-IA | Secrétariat | Organisation | Programme | Mode Furtif | Heure Bénin
Développé par Sossou Kouamé — @sossoukouameap
"""
import os, re, json, time, asyncio, logging, threading, urllib.request, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, date, timezone, timedelta
from pathlib import Path
from groq import Groq

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
#  CONSTANTES & CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

BENIN_TZ = timezone(timedelta(hours=1))

def benin_now() -> datetime:   return datetime.now(BENIN_TZ)
def benin_str(dt=None) -> str: return (dt or benin_now()).strftime("%d/%m/%Y %H:%M")
def benin_time() -> str:       return benin_now().strftime("%H:%M")

AI_META = {
    "groq":      {"name": "🟢 Groq — Llama 3.3 70B",       "model": "llama-3.3-70b-versatile"},
    "openai":    {"name": "🔵 OpenAI — GPT-4o Mini",        "model": "gpt-4o-mini"},
    "anthropic": {"name": "🟠 Anthropic — Claude 3 Haiku",  "model": "claude-3-haiku-20240307"},
    "gemini":    {"name": "🔴 Google — Gemini 2.0 Flash",   "model": "gemini-2.0-flash"},
    "mistral":   {"name": "🟣 Mistral AI — Small",          "model": "mistral-small-latest"},
}
AI_LIST = list(AI_META.keys())

CONFIG_FILE  = "config.json"
SESSION_FILE = "session.txt"
SECRETARY_FILE = "secretary.json"

DEV_SIGNATURE = "Développé par *Sossou Kouamé* — Contact : @sossoukouameap"

DEFAULT_CONFIG = {
    "credentials": {
        "telegram_api_id":   "",
        "telegram_api_hash":  "",
        "bot_token":          "",
        "telegram_session":   "",
        "admin_id":           "1190237801"
    },
    # Identité utilisateur (rempli automatiquement à la connexion)
    "user_name":          "",
    "user_username":      "",
    # Quotas & délais
    "daily_quota":        200,
    "quota_used_today":   0,
    "quota_date":         str(date.today()),
    "delay_seconds":      30,
    "reply_delay_seconds":10,
    # Modes
    "auto_reply_enabled": True,
    "stealth_mode":        True,
    # IA
    "active_ai":   "gemini",
    "ai_providers": {
        k: {"keys": [], "model": v["model"]}
        for k, v in AI_META.items()
    },
    # Données
    "daily_program":      [],
    "reminders":          [],
    "requests":           [],
    "baccara_strategies": [],
    "consignes":          [],
    "custom_buttons":     [],
    "knowledge_base": [
        "Mon nom et mes informations seront ajoutés ici — configurez via le menu ⚙️ Paramètres.",
    ]
}


def load_config() -> dict:
    if Path(CONFIG_FILE).exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if cfg.get("quota_date") != str(date.today()):
            cfg["quota_used_today"] = 0
            cfg["quota_date"] = str(date.today())
        for k, v in DEFAULT_CONFIG.items():
            if k not in cfg:
                cfg[k] = v
        cfg.setdefault("credentials", DEFAULT_CONFIG["credentials"].copy())
        cfg.setdefault("ai_providers", DEFAULT_CONFIG["ai_providers"].copy())
        cfg.setdefault("reminders", [])
        cfg.setdefault("requests", [])
        cfg.setdefault("baccara_strategies", [])
        cfg.setdefault("consignes", [])
        cfg.setdefault("custom_buttons", [])
        cfg.setdefault("stealth_mode", True)
        cfg.setdefault("active_ai", "gemini")
        cfg.setdefault("reply_delay_seconds", 10)
        cfg.setdefault("daily_quota", 200)
        # Nettoyer champs obsolètes
        cfg.pop("groq_api_key", None)
        cfg.pop("ai_model", None)
        cfg.pop("secretary_notes", None)
        if not isinstance(cfg.get("daily_program"), list):
            old = cfg.get("daily_program", "")
            cfg["daily_program"] = [old] if old else []
        for k in AI_LIST:
            cfg["ai_providers"].setdefault(k, DEFAULT_CONFIG["ai_providers"][k].copy())
            pdata = cfg["ai_providers"][k]
            # Migration ancien format "key" → "keys" (liste)
            if "key" in pdata and "keys" not in pdata:
                old_key = pdata.pop("key", "")
                pdata["keys"] = [old_key] if old_key else []
            pdata.setdefault("keys", [])
            pdata.pop("key", None)           # supprimer l'ancien champ s'il reste
            pdata.pop("quota_used", None)    # nettoyage champs obsolètes
            pdata.pop("quota_date", None)
        # Migration clé groq legacy
        legacy = cfg.get("groq_api_key") or cfg.get("credentials", {}).get("groq_api_key", "")
        if legacy:
            groq_keys = cfg["ai_providers"].setdefault("groq", {}).setdefault("keys", [])
            if legacy not in groq_keys:
                groq_keys.append(legacy)
        # Injection automatique GOOGLE_API_KEY depuis l'environnement
        _gkey = os.environ.get("GOOGLE_API_KEY", "").strip()
        if _gkey:
            gemini_keys = cfg["ai_providers"].setdefault("gemini", {}).setdefault("keys", [])
            if _gkey not in gemini_keys:
                gemini_keys.insert(0, _gkey)
            cfg.setdefault("active_ai", "gemini")
        save_config(cfg)
        return cfg
    _gkey = os.environ.get("GOOGLE_API_KEY", "").strip()
    if _gkey:
        DEFAULT_CONFIG["ai_providers"]["gemini"]["keys"] = [_gkey]
        DEFAULT_CONFIG["active_ai"] = "gemini"
    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG.copy()


def save_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def save_sec_log(sec_log: dict):
    """Sauvegarde sec_log sur disque (clés en str pour JSON)."""
    try:
        data = {str(k): v for k, v in sec_log.items()}
        with open(SECRETARY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"save_sec_log: {e}")


def load_sec_log() -> dict:
    """Charge sec_log depuis le disque (clés reconverties en int)."""
    try:
        if Path(SECRETARY_FILE).exists():
            with open(SECRETARY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {int(k): v for k, v in data.items()}
    except Exception as e:
        logger.warning(f"load_sec_log: {e}")
    return {}


def _get(cfg, env_key, cfg_path, default=""):
    return os.environ.get(env_key) or cfg.get("credentials", {}).get(cfg_path) or default


# ═══════════════════════════════════════════════════════════════════════════════
#  MULTI-UTILISATEUR — PLATEFORME SAAS
# ═══════════════════════════════════════════════════════════════════════════════

_orig_save_config  = save_config
_orig_save_sec_log = save_sec_log

SUPER_ADMIN_ID  = 1190237801
MULTI_BOT_TOKEN = "7653246287:AAH7-HVGo9EqUo8DWfhnleZSN3Y8Gp5_Nfg"
USERS_FILE      = "users.json"
USERS_DATA_DIR  = "users_data"

_USER_CONTEXTS: dict = {}
_USER_TELETHON: dict = {}
_REG_STATE:     dict = {}


def load_users() -> dict:
    try:
        if os.path.exists(USERS_FILE):
            return json.loads(Path(USERS_FILE).read_text())
    except Exception:
        pass
    return {}


def save_users(u: dict):
    Path(USERS_FILE).write_text(json.dumps(u, ensure_ascii=False, indent=2))


def user_registered(uid: int) -> bool:
    return str(uid) in load_users()


def user_blocked(uid: int) -> bool:
    if uid == SUPER_ADMIN_ID:
        return False   # L'administrateur principal ne peut jamais être bloqué
    return load_users().get(str(uid), {}).get("blocked", False)


def get_user_data(uid: int) -> dict:
    return load_users().get(str(uid), {})


def _uc_config_path(uid: int) -> str:
    os.makedirs(USERS_DATA_DIR, exist_ok=True)
    return f"{USERS_DATA_DIR}/{uid}_config.json"


def _uc_sec_path(uid: int) -> str:
    os.makedirs(USERS_DATA_DIR, exist_ok=True)
    return f"{USERS_DATA_DIR}/{uid}_sec.json"


def load_uc_config(uid: int) -> dict:
    p = _uc_config_path(uid)
    if os.path.exists(p):
        try:
            return json.loads(Path(p).read_text())
        except Exception:
            pass
    cfg = dict(DEFAULT_CONFIG)
    cfg["credentials"] = dict(DEFAULT_CONFIG["credentials"])
    cfg["credentials"]["admin_id"] = str(uid)
    return cfg


def save_uc_config(uid: int, cfg: dict):
    Path(_uc_config_path(uid)).write_text(json.dumps(cfg, ensure_ascii=False, indent=2))


def load_uc_sec(uid: int) -> dict:
    p = _uc_sec_path(uid)
    if os.path.exists(p):
        try:
            raw = json.loads(Path(p).read_text())
            return {int(k): v for k, v in raw.items()}
        except Exception:
            pass
    return {}


def save_uc_sec(uid: int, sec: dict):
    data = {str(k): v for k, v in sec.items()}
    Path(_uc_sec_path(uid)).write_text(json.dumps(data, ensure_ascii=False, indent=2))


def get_ctx(uid: int) -> dict:
    uid_str = str(uid)
    if uid_str not in _USER_CONTEXTS:
        cfg = load_uc_config(uid)
        sec = load_uc_sec(uid)
        _USER_CONTEXTS[uid_str] = {
            "config":          cfg,
            "sec_log":         sec,
            "conv_history":    {},
            "away_mode":       [False],
            "away_log":        {},
            "admin_chat_mode": [False],
            "admin_chat_hist": [],
        }
    return _USER_CONTEXTS[uid_str]


# ── Configs groupes/canaux par utilisateur ────────────────────────────────────

_GROUP_TASKS: dict = {}   # {uid_str: {chat_id_str: asyncio.Task}}


def _grp_config_path(uid: int) -> str:
    os.makedirs(USERS_DATA_DIR, exist_ok=True)
    return f"{USERS_DATA_DIR}/{uid}_groups.json"


def load_grp_configs(uid: int) -> dict:
    p = _grp_config_path(uid)
    if os.path.exists(p):
        try:
            return json.loads(Path(p).read_text())
        except Exception:
            pass
    return {}


def save_grp_configs(uid: int, data: dict):
    Path(_grp_config_path(uid)).write_text(json.dumps(data, ensure_ascii=False, indent=2))


def _parse_interval(text: str) -> int:
    """Convertit '2h', '30min', '90', '1h30' → minutes (int). Retourne 0 si invalide."""
    t = text.strip().lower().replace(" ", "")
    m = re.match(r'^(\d+)h(\d*)$', t)
    if m:
        return int(m.group(1)) * 60 + (int(m.group(2)) if m.group(2) else 0)
    m = re.match(r'^(\d+)(min|m)?$', t)
    if m:
        v = int(m.group(1))
        return v if v >= 1 else 0
    return 0


def _grp_save_wizard(uid: int, tmp: dict):
    """Sauvegarde la config groupe depuis l'état wizard tmp."""
    chat_id = tmp.get("chat_id", "")
    cid_str = str(chat_id)
    grp_cfgs = load_grp_configs(uid)
    grp_cfgs[cid_str] = {
        "chat_id":             chat_id,
        "title":               tmp.get("title", cid_str),
        "roles":               tmp.get("roles_selected", []),
        "group_info":          tmp.get("group_info", ""),
        "pub_text":            tmp.get("pub_text", ""),
        "pub_media":           tmp.get("pub_media", ""),
        "pub_interval_minutes":tmp.get("pub_interval_minutes", 120),
        "com_text":            tmp.get("com_text", ""),
        "com_media":           tmp.get("com_media", ""),
        "com_interval_minutes":tmp.get("com_interval_minutes", 60),
        "paused":              False,
        "created_at":          benin_str(),
        "bilan":               {"msgs_appris": 0, "msgs_envoyes": 0},
    }
    save_grp_configs(uid, grp_cfgs)


def _trigger_grp_handlers(uid: int):
    """Démarre les tâches de publication planifiée pour les nouveaux groupes."""
    uid_str  = str(uid)
    client   = _USER_TELETHON.get(uid_str)
    if not client:
        return
    grp_cfgs = load_grp_configs(uid)
    tasks    = _GROUP_TASKS.setdefault(uid_str, {})
    for cid_str, gcfg in grp_cfgs.items():
        if gcfg.get("paused"):
            continue
        for role in ("pub", "com"):
            if role in gcfg.get("roles", []):
                task_key = f"{cid_str}_{role}"
                existing = tasks.get(task_key)
                if existing and not existing.done():
                    continue
                t = asyncio.ensure_future(_grp_publisher(uid, client, int(cid_str), role))
                tasks[task_key] = t
        if "discuter" in gcfg.get("roles", []) and not gcfg.get("discuter_welcomed"):
            asyncio.ensure_future(_grp_discuter_welcome(uid, int(cid_str)))


async def _grp_discuter_welcome(uid: int, chat_id: int):
    """Envoie un message de bienvenue dans le groupe/canal quand le rôle Discussion est activé."""
    uid_str = str(uid)
    await asyncio.sleep(4)
    client = _USER_TELETHON.get(uid_str)
    if not client:
        return
    try:
        if not client.is_connected():
            return
    except Exception:
        return
    grp_cfgs = load_grp_configs(uid)
    gcfg = grp_cfgs.get(str(chat_id), {})
    if not gcfg or gcfg.get("paused") or gcfg.get("discuter_welcomed"):
        return
    try:
        me   = await client.get_me()
        name = me.first_name or "moi"
        grp_info = gcfg.get("group_info", "")
        if grp_info:
            intro = (f"👋 Bonjour à tous ! Je suis *{name}*, je suis là pour discuter avec vous "
                     f"sur le thème : _{grp_info}_\n\n"
                     f"Mentionnez-moi ou répondez à l'un de mes messages pour échanger ! 💬")
        else:
            intro = (f"👋 Bonjour à tous ! Je suis *{name}*, je suis là pour discuter avec vous. "
                     f"Mentionnez-moi ou répondez à l'un de mes messages pour échanger ! 💬")
        await client.send_message(chat_id, intro, parse_mode="md")
        grp_cfgs[str(chat_id)]["discuter_welcomed"] = True
        save_grp_configs(uid, grp_cfgs)
        logger.info(f"💬 Message de bienvenue envoyé — uid={uid} chat={chat_id}")
    except Exception as e:
        logger.warning(f"_grp_discuter_welcome uid={uid} chat={chat_id}: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
#  MULTI-IA : VÉRIFICATION & APPELS
# ═══════════════════════════════════════════════════════════════════════════════

def _http(url, payload, headers):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


# ── OpenWeatherMap — données météo en temps réel ─────────────────────────────────
_WEATHER_KEYWORDS = (
    "météo","meteo","temps qu'il fait","température","temperature",
    "il fait chaud","il fait froid","pluie","soleil","vent","nuage",
    "weather","forecast","climat","humidité","humidity",
)

def get_weather(city: str = "Cotonou", api_key: str = "") -> str:
    """Retourne une description météo lisible pour la ville donnée."""
    owm_key = api_key
    if not owm_key:
        cfg = load_config()
        owm_key = cfg.get("openweathermap_key", "")
    if not owm_key:
        return ""
    try:
        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?q={urllib.parse.quote(city)}&appid={owm_key}&units=metric&lang=fr"
        )
        req = urllib.request.Request(url, headers={"User-Agent":"TelegramBot/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.loads(r.read().decode())
        name    = d.get("name", city)
        temp    = d["main"]["temp"]
        feels   = d["main"]["feels_like"]
        hum     = d["main"]["humidity"]
        desc    = d["weather"][0]["description"].capitalize()
        wind_ms = d["wind"]["speed"]
        wind_km = round(wind_ms * 3.6)
        return (
            f"[MÉTÉO EN TEMPS RÉEL — {name}]\n"
            f"Condition : {desc}\n"
            f"Température : {temp:.1f}°C (ressenti {feels:.1f}°C)\n"
            f"Humidité : {hum}%\n"
            f"Vent : {wind_km} km/h\n"
        )
    except Exception as e:
        logger.debug(f"get_weather({city}) erreur: {e}")
        return ""

def detect_city_in_text(text: str, default: str = "Cotonou") -> str:
    """Extrait une ville mentionnée dans le texte, sinon retourne la ville par défaut."""
    cities = [
        "Cotonou","Porto-Novo","Parakou","Lomé","Abidjan","Dakar","Bamako",
        "Ouagadougou","Niamey","Accra","Lagos","Abuja","Douala","Yaoundé",
        "Paris","Lyon","Marseille","New York","London","Bruxelles",
    ]
    tl = text.lower()
    for c in cities:
        if c.lower() in tl:
            return c
    return default


# ── Quota tracking multi-clés (en mémoire) ─────────────────────────────────────
_quota_exhausted: dict = {}   # {(provider, idx): timestamp}
RATE_LIMIT_RESET_SECS = 60      # Gemini/Groq rate limit → retry après 60s
QUOTA_RESET_SECS      = 3600    # Crédits épuisés → retry après 1h

# ── File d'attente IA (sérialise les appels pour respecter le rate limit Gemini) ─
_ai_queue_lock = None           # asyncio.Lock initialisé dans run_userbot()
_ai_last_call_ts = [0.0]        # timestamp du dernier appel IA réussi
AI_CALL_MIN_INTERVAL = 4.5      # secondes min entre appels (≤ 13 RPM, safe pour 15 RPM)

def _is_quota_ok(provider: str, idx: int) -> bool:
    ts, reset = _quota_exhausted.get((provider, idx), (None, QUOTA_RESET_SECS))
    return ts is None or (time.time() - ts) > reset

def _mark_quota_exhausted(provider: str, idx: int, is_rate_limit: bool = False):
    reset = RATE_LIMIT_RESET_SECS if is_rate_limit else QUOTA_RESET_SECS
    _quota_exhausted[(provider, idx)] = (time.time(), reset)
    label = "limite de fréquence" if is_rate_limit else "quota/crédits épuisés"
    logger.warning(f"⚠️ {label} {provider}[{idx}] — retry dans {reset}s")

def _is_quota_error(e: Exception) -> bool:
    msg = str(e).lower()
    return any(k in msg for k in (
        "429", "quota", "rate limit", "rate_limit",
        "resource exhausted", "too many requests", "exceeded"
    ))

def _is_rate_limit_error(e: Exception) -> bool:
    """Distingue les rate limits temporaires (429 RPM) des quotas épuisés (crédits)."""
    msg = str(e).lower()
    is_429 = "429" in msg or "too many requests" in msg or "rate limit" in msg or "rate_limit" in msg
    is_quota = "quota" in msg or "resource exhausted" in msg or "exceeded your" in msg or "billing" in msg
    return is_429 and not is_quota


def verify_key(provider, api_key, model) -> tuple[bool, str]:
    # Vérification du format de la clé avant d'appeler l'API
    fmt_ok = {
        "groq":      api_key.startswith("gsk_"),
        "openai":    api_key.startswith(("sk-", "sk-proj-")),
        "anthropic": api_key.startswith("sk-ant-"),
        "gemini":    len(api_key) > 20,
        "mistral":   len(api_key) > 20,
    }
    if not fmt_ok.get(provider, True):
        return False, f"❌ Format de clé incorrect pour {provider}"

    # Gemini : ne pas faire d'appel test — la limite de fréquence (15 req/min) déclenche
    # systématiquement un 429 même sur une clé neuve. On valide seulement le format.
    if provider == "gemini":
        return True, (
            f"✅ Clé Gemini enregistrée — format valide.\n"
            f"Modèle : `{model}`\n"
            f"_La clé sera testée automatiquement au premier message reçu._"
        )

    try:
        if provider == "groq":
            c = Groq(api_key=api_key)
            c.chat.completions.create(model=model,
                messages=[{"role":"user","content":"Hi"}], max_tokens=5)
            return True, f"✅ Clé valide — Modèle : `{model}`"
        elif provider == "openai":
            r = _http("https://api.openai.com/v1/chat/completions",
                {"model": model, "messages": [{"role":"user","content":"Hi"}], "max_tokens": 5},
                {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
            return True, f"✅ Clé valide — Modèle : `{model}`\nTokens test : {r.get('usage',{}).get('total_tokens','?')}"
        elif provider == "anthropic":
            r = _http("https://api.anthropic.com/v1/messages",
                {"model": model, "max_tokens": 5, "messages": [{"role":"user","content":"Hi"}]},
                {"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"})
            return True, f"✅ Clé valide — Modèle : `{model}`"
        elif provider == "mistral":
            r = _http("https://api.mistral.ai/v1/chat/completions",
                {"model": model, "messages": [{"role":"user","content":"Hi"}], "max_tokens": 5},
                {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
            return True, f"✅ Clé valide — Modèle : `{model}`"
    except Exception as e:
        err = str(e)
        # 429 : deux cas différents
        is_rate_lim = "429" in err or "too many" in err.lower() or "rate limit" in err.lower()
        is_quota    = "quota" in err.lower() or "resource exhausted" in err.lower() or "billing" in err.lower()
        if is_rate_lim and not is_quota:
            return True, (
                f"✅ Clé acceptée — limite de fréquence temporaire (normal).\n"
                f"La clé fonctionnera dans quelques secondes automatiquement.\n"
                f"_Aucune action requise._"
            )
        if is_rate_lim or is_quota:
            return True, (
                f"⚠️ Clé acceptée — quota/crédits épuisés sur votre compte.\n"
                f"Rechargez votre compte {provider.capitalize()} ou créez une nouvelle clé.\n"
                f"`{err[:120]}`"
            )
        if "404" in err or "not found" in err.lower():
            return False, (
                f"❌ Modèle introuvable (404).\n"
                f"Le modèle `{model}` n'existe pas ou n'est pas disponible dans votre région.\n"
                f"Essayez de changer le modèle via ⚙️ Paramètres IA."
            )
        if any(k in err.lower() for k in ("401","403","unauthorized","invalid_api_key","authentication","expired","invalid_key","api_key_invalid")):
            return False, f"❌ Clé invalide ou expirée — vérifiez sur le tableau de bord {provider.capitalize()}\n`{err[:150]}`"
        return False, f"❌ Erreur inattendue\n`{err[:150]}`"
    return False, "Fournisseur inconnu"


async def ai_call(provider, api_key, model, system_prompt, messages,
                  max_tokens=400, temperature=0.80) -> str:
    loop = asyncio.get_event_loop()
    def _do():
        all_msgs = [{"role":"system","content":system_prompt}] + messages
        if provider == "groq":
            c = Groq(api_key=api_key)
            r = c.chat.completions.create(model=model, messages=all_msgs,
                max_tokens=max_tokens, temperature=temperature)
            return r.choices[0].message.content.strip()
        elif provider == "openai":
            r = _http("https://api.openai.com/v1/chat/completions",
                {"model":model,"messages":all_msgs,"max_tokens":max_tokens,"temperature":temperature},
                {"Authorization":f"Bearer {api_key}","Content-Type":"application/json"})
            return r["choices"][0]["message"]["content"].strip()
        elif provider == "anthropic":
            user_msgs = [m for m in messages if m["role"] in ("user","assistant")]
            r = _http("https://api.anthropic.com/v1/messages",
                {"model":model,"system":system_prompt,"messages":user_msgs,"max_tokens":max_tokens},
                {"x-api-key":api_key,"anthropic-version":"2023-06-01","Content-Type":"application/json"})
            return r["content"][0]["text"].strip()
        elif provider == "gemini":
            parts = [{"role":"user" if m["role"]=="user" else "model",
                      "parts":[{"text":m["content"]}]} for m in messages]
            r = _http(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
                {"system_instruction":{"parts":[{"text":system_prompt}]},"contents":parts,
                 "generationConfig":{"maxOutputTokens":max_tokens,"temperature":temperature}},
                {"Content-Type":"application/json"})
            return r["candidates"][0]["content"]["parts"][0]["text"].strip()
        elif provider == "mistral":
            r = _http("https://api.mistral.ai/v1/chat/completions",
                {"model":model,"messages":all_msgs,"max_tokens":max_tokens,"temperature":temperature},
                {"Authorization":f"Bearer {api_key}","Content-Type":"application/json"})
            return r["choices"][0]["message"]["content"].strip()
        raise ValueError(f"Fournisseur inconnu: {provider}")
    return await loop.run_in_executor(None, _do)


# ═══════════════════════════════════════════════════════════════════════════════
#  PROMPTS IA
# ═══════════════════════════════════════════════════════════════════════════════

SESSION_TIMEOUT = 3600

def _moment():
    h = benin_now().hour
    if 5 <= h < 12: return "matin"
    if 12 <= h < 14: return "midi"
    if 14 <= h < 18: return "après-midi"
    if 18 <= h < 22: return "soirée"
    return "nuit"

def _greeting():
    return {"matin":"Bonjour","midi":"Bonne journée","après-midi":"Bon après-midi",
            "soirée":"Bonsoir","nuit":"Bonsoir"}.get(_moment(),"Bonjour")

def _make_stealth_rule(name: str) -> str:
    return f"""
RÈGLES ABSOLUES (à ne jamais enfreindre) :
• Tu ES {name} — parle en 1ère personne (JE, MON, MA, MES…)
• JAMAIS de mention d'"assistante", "bot", "IA" ou "je suis absent"
• JAMAIS dire "je suis programmé comme ça", "c'est comme ça que je fonctionne" ou similaires
• Si on demande si tu es un bot → "Non, mon téléphone répond automatiquement 😄"
• Si la question est TROP PERSONNELLE → réponds UNIQUEMENT : "Un instant stp 😊" (maximum 3 fois par conversation — après, trouve une autre formule naturelle)
• Réponds dans la LANGUE de l'interlocuteur, même longueur que son message, ton naturel
• RÈGLE DE CADRAGE STRICT : réponds UNIQUEMENT à ce que la personne vient de dire ou demander — ni plus ni moins
• INTERDIT : "comment puis-je vous aider ?", "que puis-je faire pour vous ?", "avez-vous besoin d'aide ?" et toutes formules similaires
• Si la personne dit "cc", "salut", "bonjour" → réponds juste "cc 😊", "salut !" ou "bonjour !" et ATTENDS qu'elle parle en premier — ne relance PAS la conversation
• INTERDICTION ABSOLUE de parler de tes services, prix ou activités si la personne n'en parle pas
• Si elle dit "bien et toi ?" → réponds "Super bien !" ou "Ça va nickel !" rien de plus — STOP, attends qu'elle continue
• Si elle dit "ok", "d'accord", "merci" → réponds brièvement ("👍", "Parfait !", "De rien 😊") et attends qu'elle continue
• Suis le rythme et le sujet de la conversation — ne dévie JAMAIS vers autre chose sans invitation explicite
• Si la question porte sur une information précise → donne UNIQUEMENT cette information, sans ajouter d'autres détails
• Tu n'envoies PAS deux messages d'affilée — tu attends toujours que l'autre réponde avant de reparler"""


def _make_normal_rule(name: str) -> str:
    return f"""
RÈGLES ABSOLUES :
• Tu es l'assistante de {name}
• JAMAIS dire "je suis programmée comme ça" ou que tu es un bot/IA
• Réponds UNIQUEMENT à ce que la personne demande — ni plus ni moins
• INTERDIT : "comment puis-je vous aider ?", "que puis-je faire pour vous ?" et formules similaires
• Si la personne dit "cc", "salut", "bonjour" → réponds juste de la même façon et ATTENDS
• Ne parle des services de {name} QUE si la personne le demande explicitement
• "Un instant stp 😊" ne peut être utilisé que 3 fois MAXIMUM dans toute une conversation — varie les formules après
• Tu n'envoies jamais deux messages d'affilée — attends toujours que l'autre réponde
• Langue de l'interlocuteur, même longueur que son message, suit exactement le rythme"""


def build_prompt(contact_type: str, config: dict, style: dict = None,
                  projects_ctx: str = "", away_mode: bool = False,
                  away_history: str = "", weather_ctx: str = "") -> str:
    kb = "\n".join(f"• {x}" for x in config["knowledge_base"])
    progs  = config.get("daily_program", [])
    uname  = config.get("user_name", "") or "moi"
    prog_blk = (f"Programme du jour de {uname} :\n" + "\n".join(f"  - {p}" for p in progs)) if progs else ""
    moment = _moment()
    stealth = config.get("stealth_mode", True)
    rules = _make_stealth_rule(uname) if stealth else _make_normal_rule(uname)

    # Bloc style d'écriture avec ce contact
    style_block = ""
    if style:
        formality  = style.get("formality", "")
        tone       = style.get("tone", "")
        emojis     = style.get("uses_emojis", False)
        phrases    = style.get("typical_phrases", [])
        style_block = (
            f"\nSTYLE D'ÉCRITURE avec cette personne (reproduis-le exactement) :\n"
            f"• Ton : {formality} / {tone}\n"
            f"• Emojis : {'oui' if style.get('uses_emojis') else 'non'}\n"
            + (f"• Expressions typiques : {', '.join(phrases[:4])}\n" if phrases else "")
        )

    # Bloc contexte projets en cours
    proj_block = f"\nCONTEXTE PROJETS EN COURS avec cette personne :\n{projects_ctx}\n" \
                 if projects_ctx else ""

    # La knowledge base : disponible en référence, ne jamais pousser proactivement
    kb_ref = (
        f"\nSERVICES QUE TU PROPOSES (à mentionner SEULEMENT si la personne en parle ou le demande) :\n{kb}\n"
    )

    # Consignes spécifiques de l'administrateur
    consignes = config.get("consignes", [])
    consignes_block = ""
    if consignes:
        consignes_lines = "\n".join(f"  • {c['text']}" for c in consignes)
        consignes_block = (
            f"\nCONSIGNES SPÉCIALES DE L'ADMINISTRATEUR (PRIORITÉ ABSOLUE — respecte-les toujours) :\n"
            f"{consignes_lines}\n"
        )

    # Boutons personnalisés de l'administrateur
    custom_btns = config.get("custom_buttons", [])
    custom_btns_block = ""
    if custom_btns:
        lines = "\n".join(
            f"  • {b['name']} : {b['description']}"
            for b in custom_btns
        )
        custom_btns_block = (
            f"\nINFORMATIONS PERSONNALISÉES (RÈGLE STRICTE : utilise UNIQUEMENT ces informations telles quelles — ne les modifie pas, ne les complète pas, ne les inventes pas) :\n"
            f"{lines}\n"
            f"→ Si la question porte sur l'un de ces sujets, cite l'info EXACTE ci-dessus, rien de plus.\n"
        )

    # Stratégies Baccara : à partager UNIQUEMENT si demande explicite, et UNE seule à la fois
    strats = config.get("baccara_strategies", [])
    baccara_block = ""
    if strats:
        strat_lines = "\n".join(
            f"  Stratégie {i} — {s['name']} : {s['description']}"
            for i, s in enumerate(strats, 1)
        )
        baccara_block = (
            f"\nSTRATÉGIES BACCARA DISPONIBLES :\n{strat_lines}\n\n"
            f"RÈGLE : Ne partage ces stratégies QUE si la personne demande explicitement "
            f"une stratégie Baccara. Dans ce cas, donne-lui UNE SEULE stratégie "
            f"(la plus adaptée ou en commençant par la Stratégie 1). "
            f"Ne donne JAMAIS toutes les stratégies à la fois. "
            f"Si elle veut en savoir plus, elle demandera.\n"
        )

    # Bloc météo en temps réel (injecté seulement si disponible)
    weather_block = (
        f"\nINFO MÉTÉO EN TEMPS RÉEL (utilise-la si la question porte sur la météo) :\n{weather_ctx}\n"
    ) if weather_ctx else ""

    # ── MODE ABSENT : le bot prend le contrôle total ──────────────────────────
    if away_mode:
        hist_block = (
            f"\nHISTORIQUE RÉCENT DE CETTE CONVERSATION (tes messages = {uname}) :\n{away_history}\n"
            if away_history else ""
        )
        return (
            f"Tu ES {uname}. Tu réponds à sa place pendant son ABSENCE.\n"
            f"Il/elle ne sait pas encore que tu as répondu — il/elle verra ça à son retour.\n\n"
            f"MISSION : Répondre exactement comme {uname} le ferait :\n"
            f"• Reproduis parfaitement son style, son ton, ses expressions habituelles\n"
            f"• Réponds naturellement et humainement — jamais de réponses robotiques\n"
            f"• Si quelqu'un parle d'argent ou de budget limité pour un bot/service :\n"
            f"  → Note mentalement et réponds 'Ok, on voit ça ensemble bientôt 😊'\n"
            f"• Si quelqu'un dit 'n'oublie pas' ou 'rappelle-toi' → 'C'est noté ✍️'\n"
            f"• Si question trop technique ou sensible → 'Ok je reviens vers toi bientôt 😊'\n"
            f"• Réponds en {moment}\n"
            f"{weather_block}{consignes_block}{custom_btns_block}{hist_block}{style_block}{proj_block}{kb_ref}{baccara_block}\n{rules}"
        )

    if contact_type == "first":
        return (
            f"C'est le TOUT PREMIER message de cette personne. "
            f"Commence par '{_greeting()} !' puis réponds naturellement à ce qu'elle dit. "
            f"Ne parle PAS de tes services ni de Baccara dans ce premier message — "
            f"laisse d'abord la personne s'exprimer.\n"
            f"{weather_block}{consignes_block}{custom_btns_block}{prog_blk}{style_block}{proj_block}{kb_ref}{baccara_block}\n{rules}"
        )
    if contact_type == "returning":
        return (
            f"Cette personne revient après une pause. Re-salue-la naturellement.\n"
            f"Réponds à son message et ATTENDS qu'elle parle — ne pose PAS de questions spontanées.\n"
            f"Ne parle de tes services ou stratégies QUE si elle en parle en premier.\n"
            f"{weather_block}{consignes_block}{custom_btns_block}{prog_blk}{style_block}{proj_block}{kb_ref}{baccara_block}\n{rules}"
        )
    # ongoing : suit le fil exact de la discussion
    return (
        f"Continue la conversation naturellement. Réponds UNIQUEMENT à ce que la personne "
        f"vient de dire. Ne dévie jamais vers tes services, Baccara ou activités sauf si "
        f"elle en parle explicitement.\n"
        f"{weather_block}{consignes_block}{custom_btns_block}{style_block}{proj_block}{kb_ref}{baccara_block}\n{rules}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  HEALTH SERVER
# ═══════════════════════════════════════════════════════════════════════════════

def start_health_server():
    import json as _json
    _start_time = time.time()

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            uptime_s = int(time.time() - _start_time)
            h, m, s  = uptime_s // 3600, (uptime_s % 3600) // 60, uptime_s % 60
            body = _json.dumps({
                "status":  "ok",
                "service": "assistance-sossou",
                "uptime":  f"{h:02d}h{m:02d}m{s:02d}s",
                "time_benin": datetime.now(timezone(timedelta(hours=1))).strftime("%d/%m/%Y %H:%M"),
            }, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *a): pass

    port = int(os.environ.get("PORT", 5000))
    threading.Thread(
        target=HTTPServer(("0.0.0.0", port), H).serve_forever,
        daemon=True
    ).start()
    logger.info(f"Health-check HTTP sur le port {port}")


# ═══════════════════════════════════════════════════════════════════════════════
#  MODE SETUP
# ═══════════════════════════════════════════════════════════════════════════════

def run_setup_bot(BOT_TOKEN, API_ID, API_HASH, OWNER_ID, PHONE_NUMBER):
    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.errors import SessionPasswordNeededError

    auth = {}

    async def cmd_connect(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != OWNER_ID:
            await update.message.reply_text("❌ Accès refusé."); return
        phone = PHONE_NUMBER
        if context.args:
            raw = context.args[0].strip()
            phone = raw if raw.startswith("+") else "+"+raw
        if not phone:
            await update.message.reply_text(
                "📱 *Numéro requis !*\n\n"
                "Utilise la commande avec ton numéro :\n"
                "`/connect +22995501564`",
                parse_mode="Markdown"); return
        await update.message.reply_text(f"📤 Envoi du code au *{phone}*...", parse_mode="Markdown")
        try:
            client = TelegramClient(StringSession(), API_ID, API_HASH)
            await client.connect()
            result = await client.send_code_request(phone)
            auth[update.effective_user.id] = {"client":client,"phone":phone,
                "phone_code_hash":result.phone_code_hash,"awaiting_2fa":False}
            await update.message.reply_text("✅ Code envoyé !\n\nTapez `aa<code>` ex: `aa12345`",
                parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ {e}")

    async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if uid not in auth: return
        txt = (update.message.text or "").strip()
        if not txt.lower().startswith("aa"): return
        code = txt[2:].strip()
        if not code:
            await update.message.reply_text("❌ Code vide. Ex: `aa12345`", parse_mode="Markdown"); return
        s = auth[uid]
        try:
            await s["client"].sign_in(s["phone"], code=code, phone_code_hash=s["phone_code_hash"])
        except SessionPasswordNeededError:
            s["awaiting_2fa"] = True
            await update.message.reply_text("🔐 2FA requis. Tapez `pass <motdepasse>`", parse_mode="Markdown"); return
        except Exception as e:
            await update.message.reply_text(f"❌ {e}"); return
        await _finish(s["client"], update, uid)

    async def handle_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        s = auth.get(uid, {})
        if not s.get("awaiting_2fa"): return
        txt = (update.message.text or "").strip()
        if not txt.lower().startswith("pass "): return
        try:
            await s["client"].sign_in(password=txt[5:].strip())
            await _finish(s["client"], update, uid)
        except Exception as e:
            await update.message.reply_text(f"❌ {e}")

    async def _finish(client, update, uid):
        import sys
        ss = client.session.save()
        await client.disconnect()
        auth.pop(uid, None)
        Path(SESSION_FILE).write_text(ss)
        cfg = load_config()
        cfg.setdefault("credentials", {})["telegram_session"] = ss
        save_config(cfg)
        await update.message.reply_text(
            "✅ *CONNEXION RÉUSSIE !*\n\n🔄 Redémarrage en mode USERBOT dans 5s...\n\n"
            "Tapez /menu dans vos Messages Sauvegardés Telegram.",
            parse_mode="Markdown")
        # ── Envoyer la session en morceaux (utile pour Render) ──────────────
        try:
            header = (
                "🔑 *VOTRE SESSION TELEGRAM*\n\n"
                "⚠️ *Copiez cette chaîne et ajoutez-la dans Render*\n"
                "Variable : `TELEGRAM_SESSION`\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            )
            await update.message.reply_text(header, parse_mode="Markdown")
            # Envoyer la session par morceaux de 3000 caractères max
            chunk_size = 3000
            for i in range(0, len(ss), chunk_size):
                part = ss[i:i+chunk_size]
                num  = (i // chunk_size) + 1
                total = (len(ss) + chunk_size - 1) // chunk_size
                label = f"*Partie {num}/{total}* :\n`{part}`" if total > 1 else f"`{part}`"
                await update.message.reply_text(label, parse_mode="Markdown")
            await update.message.reply_text(
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "✅ Copiez la chaîne ci-dessus → Render → Environment → `TELEGRAM_SESSION`\n\n"
                "_Ainsi votre session survivra à chaque redéploiement._",
                parse_mode="Markdown")
        except Exception as _e:
            logger.warning(f"Impossible d'envoyer la session dans le chat : {_e}")
        # ── Redémarrage ──────────────────────────────────────────────────────
        def _restart():
            time.sleep(5)
            os.execv(sys.executable, [sys.executable]+sys.argv)
        threading.Thread(target=_restart, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("connect", cmd_connect))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"(?i)^pass "), handle_pass))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"(?i)^aa"), handle_code))

    # Compatibilité Python 3.12+ : s'assurer qu'une boucle asyncio existe
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    app.run_polling(drop_pending_updates=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  MODE USERBOT
# ═══════════════════════════════════════════════════════════════════════════════

def run_userbot(API_ID, API_HASH, BOT_TOKEN, GROQ_API_KEY, SESSION_STRING, OWNER_ID):
    from telethon import TelegramClient, events, Button
    from telethon.sessions import StringSession

    # ── État global ─────────────────────────────────────────────────────────────
    config          = load_config()
    sec_log: dict   = load_sec_log()   # Chargé depuis le disque, persistant entre redémarrages
    conv_history    = {}               # {user_id: [messages]}
    pending_tasks   = {}               # {chat_id: asyncio.Task}
    known_users     = set(sec_log.keys())   # Contacts déjà connus (restaurés depuis le disque)
    last_msg_time   = {}
    stopped_chats   = set()
    # ── Mode Absent ─────────────────────────────────────────────────────────────
    away_mode       = [False]          # [0] = bool — le bot prend le contrôle total
    away_mode_start = [0.0]            # [0] = timestamp du début du mode absent
    away_log: dict  = {}               # {uid: {"name":str,"msgs":[],"bot_replies":[]}}
    session_log: list = []             # Messages capturés pendant la session active (Répond à ma place)
    session_start_ts: list = [0.0]     # [0] = timestamp début de session
    global _ai_queue_lock
    _ai_queue_lock = asyncio.Lock()    # File d'attente IA — sérialise les appels
    logger.info(f"📂 Secrétariat chargé : {len(sec_log)} contacts, "
                f"{sum(len(v.get('msgs',[])) for v in sec_log.values())} messages")

    state = {
        "program_waiting":   False,
        "ai_waiting":        None,
        "param_waiting":     None,
        "remind_text":       None,
        "cbtn_tmp_name":     None,
        "cbtn_tmp_id":       None,
    }

    # ── Multi-utilisateur : context switcher ─────────────────────────────────────
    CURRENT_UID = [None]

    def save_config(cfg):
        u = CURRENT_UID[0]
        if u:
            save_uc_config(u, cfg)
            ctx = _USER_CONTEXTS.get(str(u))
            if ctx:
                ctx["config"].clear()
                ctx["config"].update(cfg)
        else:
            _orig_save_config(cfg)

    def save_sec_log(sec):
        u = CURRENT_UID[0]
        if u:
            save_uc_sec(u, sec)
            ctx = _USER_CONTEXTS.get(str(u))
            if ctx:
                ctx["sec_log"].clear()
                ctx["sec_log"].update(sec)
        else:
            _orig_save_sec_log(sec)

    def _switch_user_ctx(uid: int):
        CURRENT_UID[0] = uid
        ctx = get_ctx(uid)
        config.clear()
        config.update(ctx["config"])
        sec_log.clear()
        sec_log.update(ctx["sec_log"])
        away_mode[0] = ctx["away_mode"][0]
        away_log.clear()
        away_log.update(ctx["away_log"])

    # ── Migration clé Groq ───────────────────────────────────────────────────────
    if GROQ_API_KEY:
        groq_keys = config["ai_providers"]["groq"].setdefault("keys", [])
        if GROQ_API_KEY not in groq_keys:
            groq_keys.append(GROQ_API_KEY)
            save_config(config)

    # ── Helpers ──────────────────────────────────────────────────────────────────

    _ctrl_active  = [True]   # [False] si conflit 409 — désactive les envois locaux
    _client_ref   = [None]   # Référence partagée vers le client Telethon

    def _send_bot(text: str, parse_mode="Markdown"):
        if not _ctrl_active[0]:
            return
        try:
            payload = json.dumps({"chat_id": OWNER_ID, "text": text,
                                  "parse_mode": parse_mode}).encode()
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                data=payload, headers={"Content-Type":"application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=10): pass
        except Exception as e:
            logger.warning(f"send_bot: {e}")

    _ai_key_alerted = [False]   # Eviter de spammer la notif "clés manquantes"

    async def notify(text: str):
        if not _ctrl_active[0]:
            return
        if BOT_TOKEN:
            await asyncio.get_event_loop().run_in_executor(None, _send_bot, text)
        else:
            # Fallback : envoyer via le userbot lui-même (Saved Messages)
            tg = _client_ref[0]
            if tg:
                try:
                    await tg.send_message("me", text, parse_mode="md")
                except Exception as e:
                    logger.warning(f"notify fallback: {e}")
            else:
                logger.debug(f"notify (client non prêt) : {text[:80]}")

    def _get_ai():
        """Retourne (provider, première_clé_valide, model) pour affichage/stats."""
        ordered = [config.get("active_ai","groq")] + [k for k in AI_LIST if k != config.get("active_ai","groq")]
        for provider in ordered:
            pdata = config["ai_providers"].get(provider, {})
            model = pdata.get("model", AI_META[provider]["model"])
            for idx, key in enumerate(pdata.get("keys", [])):
                if key and _is_quota_ok(provider, idx):
                    return provider, key, model
        return "groq", GROQ_API_KEY, "llama-3.3-70b-versatile"

    async def smart_ai_call(system_prompt: str, messages: list,
                             max_tokens: int = 400, temperature: float = 0.80) -> str:
        """Appel IA sérialisé avec file d'attente pour respecter les limites Gemini (15 RPM).
        Un seul appel à la fois, espacé d'au moins AI_CALL_MIN_INTERVAL secondes."""
        async with _ai_queue_lock:
            # Respecter l'intervalle minimum entre appels
            elapsed = time.time() - _ai_last_call_ts[0]
            if elapsed < AI_CALL_MIN_INTERVAL:
                await asyncio.sleep(AI_CALL_MIN_INTERVAL - elapsed)

            ordered = [config.get("active_ai","groq")] + [k for k in AI_LIST if k != config.get("active_ai","groq")]
            last_err = None
            for provider in ordered:
                pdata = config["ai_providers"].get(provider, {})
                model = pdata.get("model", AI_META[provider]["model"])
                keys  = pdata.get("keys", [])
                for idx, key in enumerate(keys):
                    if not key or not _is_quota_ok(provider, idx):
                        continue
                    try:
                        result = await ai_call(provider, key, model, system_prompt, messages,
                                               max_tokens, temperature)
                        _ai_last_call_ts[0] = time.time()
                        return result
                    except Exception as e:
                        if _is_quota_error(e):
                            is_rl = _is_rate_limit_error(e)
                            _mark_quota_exhausted(provider, idx, is_rate_limit=is_rl)
                            if is_rl:
                                # Rate limit : attendre puis réessayer directement
                                wait = AI_CALL_MIN_INTERVAL * 3
                                logger.info(f"⏳ Rate limit {provider} — attente {wait:.0f}s…")
                                await asyncio.sleep(wait)
                                try:
                                    result = await ai_call(provider, key, model, system_prompt,
                                                           messages, max_tokens, temperature)
                                    _ai_last_call_ts[0] = time.time()
                                    _quota_exhausted.pop((provider, idx), None)
                                    return result
                                except Exception as e2:
                                    if _is_quota_error(e2):
                                        _mark_quota_exhausted(provider, idx, is_rate_limit=_is_rate_limit_error(e2))
                                        last_err = e2
                                        continue
                                    raise
                            last_err = e
                            continue
                        raise
            # Fallback : clé Groq intégrée si définie
            if GROQ_API_KEY:
                result = await ai_call("groq", GROQ_API_KEY, "llama-3.3-70b-versatile",
                                        system_prompt, messages, max_tokens, temperature)
                _ai_last_call_ts[0] = time.time()
                return result
            raise Exception("Toutes les clés IA sont épuisées ou non configurées") from last_err

    def _check_quota() -> bool:
        today = str(date.today())
        if config.get("quota_date") != today:
            config["quota_used_today"] = 0
            config["quota_date"] = today
        if config["quota_used_today"] >= config["daily_quota"]:
            return False
        config["quota_used_today"] += 1
        save_config(config)
        return True

    def _sec_log(user_id: int, name: str, role: str, text: str):
        if not text or not text.strip():
            return
        if user_id not in sec_log:
            sec_log[user_id] = {"name": name, "msgs": []}
        # Mettre à jour le nom si plus récent
        sec_log[user_id]["name"] = name
        entry = {"r": role, "t": text.strip()[:500], "d": benin_str()}
        sec_log[user_id]["msgs"].append(entry)
        if len(sec_log[user_id]["msgs"]) > 200:
            sec_log[user_id]["msgs"] = sec_log[user_id]["msgs"][-200:]
        # Ajouter à la session en cours (si bot actif)
        if config.get("auto_reply_enabled", True) or away_mode[0]:
            session_log.append({
                "uid":  user_id,
                "name": name,
                "role": role,   # "in" = message reçu, "out" = réponse bot
                "text": text.strip()[:500],
                "time": benin_str()
            })
        # Sauvegarde persistante sur disque
        save_sec_log(sec_log)

    # ── IA réponse ────────────────────────────────────────────────────────────────

    async def get_reply(user_id: int, text: str, contact_type: str,
                        is_away: bool = False) -> str:
        if not _check_quota():
            return "Un instant stp 😊" if config.get("stealth_mode", True) else \
                   "Mon assistant a atteint son quota journalier. Je vous réponds bientôt 🙏"

        # ── Pré-charger l'historique depuis le secrétariat si conv_history est vide ──
        # Cela donne au bot le contexte des échanges précédents même après redémarrage
        if user_id not in conv_history or not conv_history[user_id]:
            stored_msgs = sec_log.get(user_id, {}).get("msgs", [])
            if stored_msgs:
                uname = sec_log[user_id].get("name", f"ID:{user_id}")
                preloaded = []
                for m in stored_msgs[-18:]:   # 18 derniers messages max
                    role    = "assistant" if m["r"] == "out" else "user"
                    prefix  = "" if role == "assistant" else f"[{uname}] "
                    content = f"{prefix}{m['t']}"
                    preloaded.append({"role": role, "content": content})
                conv_history[user_id] = preloaded
                logger.debug(f"💬 Historique pré-chargé pour {uname}: {len(preloaded)} msgs")

        hist = conv_history.setdefault(user_id, [])
        hist.append({"role":"user","content":text})
        if len(hist) > 20:
            conv_history[user_id] = hist[-20:]

        # Récupérer le style appris pour ce contact
        contact_data  = sec_log.get(user_id, {})
        style         = contact_data.get("style")
        # Construire le contexte des projets en cours avec ce contact
        projects_ctx  = ""
        last_analysis = contact_data.get("last_analysis", {})
        if last_analysis.get("has_project") and last_analysis.get("projects"):
            proj_lines = [
                f"• {p['title']} ({p.get('status','?')})"
                for p in last_analysis["projects"]
                if p.get("status") in ("en_cours", "à_démarrer")
            ]
            if proj_lines:
                projects_ctx = "\n".join(proj_lines)

        # Historique de la conversation pour le mode absent
        away_history = ""
        if is_away:
            msgs = contact_data.get("msgs", [])[-15:]
            name = contact_data.get("name", f"ID:{user_id}")
            away_history = "\n".join(
                f"[{'SOSSOU' if m['r']=='out' else name.upper()}] {m['t'][:150]}"
                for m in msgs
            )

        # ── Injection météo en temps réel si la question est météo ───────────────
        weather_ctx = ""
        tl = text.lower()
        if any(kw in tl for kw in _WEATHER_KEYWORDS):
            city = detect_city_in_text(text, config.get("weather_default_city", "Cotonou"))
            loop2 = asyncio.get_event_loop()
            weather_ctx = await loop2.run_in_executor(None, get_weather, city)
            if weather_ctx:
                logger.debug(f"☁️ Météo injectée pour {city}")

        sys_p = build_prompt(contact_type, config, style=style, projects_ctx=projects_ctx,
                             away_mode=is_away, away_history=away_history,
                             weather_ctx=weather_ctx)
        try:
            reply = await smart_ai_call(sys_p, conv_history[user_id])
            conv_history[user_id].append({"role":"assistant","content":reply})
            return reply
        except Exception as e:
            err = str(e)
            needs_alert = any(k in err.lower() for k in (
                "401","unauthorized","expired","invalid","non configurées","épuisées"
            ))
            if needs_alert and not _ai_key_alerted[0]:
                _ai_key_alerted[0] = True
                await notify(
                    "⚠️ *Aucune clé IA fonctionnelle !*\n\n"
                    "L'assistante répond 'Un instant stp' à tous les messages car aucune clé API n'est configurée.\n\n"
                    "👉 *Solution :* envoie /menu → 🤖 Fournisseurs IA → ajoute au moins une clé (Groq, Gemini, etc.)\n\n"
                    f"_Erreur : {err[:150]}_"
                )
            return "Un instant stp 😊" if config.get("stealth_mode", True) else \
                   "Je suis momentanément indisponible. Je vous réponds dès que possible 🙏"

    # ── Extracteur organisation ───────────────────────────────────────────────────

    async def extract_request(user_id: int, name: str, text: str):
        prompt = (
            f"Message reçu de : {name}\nMessage : {text}\n\n"
            "Est-ce une DEMANDE DE SERVICE ou une QUESTION nécessitant un suivi (commande, formation, bot, stratégie, prix, RDV, etc.) ?\n"
            "Réponds en JSON strict UNIQUEMENT :\n"
            '{"is_request": true, "summary": "résumé court", "category": "formation|bot|stratégie|info|autre"}\n'
            'OU {"is_request": false}'
        )
        try:
            r = await smart_ai_call(
                "Analyse de message. Réponds en JSON strict.",
                [{"role":"user","content":prompt}], max_tokens=150, temperature=0.1)
            m = re.search(r'\{.*\}', r, re.DOTALL)
            if not m: return
            data = json.loads(m.group())
            if not data.get("is_request"): return
            req = {
                "id": int(time.time()),
                "contact": name, "contact_id": user_id,
                "text": text[:300],
                "summary": data.get("summary", text[:100]),
                "category": data.get("category", "autre"),
                "date": benin_str(),
                "status": "pending",
                "ai_suggestion": ""
            }
            config["requests"].append(req)
            save_config(config)
            logger.info(f"📋 Demande enregistrée : {req['summary']}")
        except Exception as e:
            logger.debug(f"extract_request: {e}")

    # ── Extracteur rappels (secrétariat) ──────────────────────────────────────────

    async def extract_reminder(contact_name: str, text: str):
        if len(text) < 8: return
        prompt = (
            f"Heure Bénin actuelle : {benin_str()}\n"
            f"Contact : {contact_name}\nMessage envoyé : {text}\n\n"
            "Y a-t-il une PROMESSE, ENGAGEMENT ou DEADLINE dans ce message ?\n"
            "JSON strict :\n"
            '{"has_reminder": true, "text": "...", "deadline": "YYYY-MM-DDTHH:MM ou null"}\n'
            'OU {"has_reminder": false}'
        )
        try:
            r = await smart_ai_call(
                "Analyse de promesses. Réponds en JSON strict.",
                [{"role":"user","content":prompt}], max_tokens=150, temperature=0.1)
            m = re.search(r'\{.*\}', r, re.DOTALL)
            if not m: return
            data = json.loads(m.group())
            if not data.get("has_reminder"): return
            rem = {
                "id": int(time.time()),
                "text": data.get("text", text[:100]),
                "contact": contact_name,
                "deadline": data.get("deadline"),
                "created": benin_str(),
                "notified": False
            }
            config["reminders"].append(rem)
            save_config(config)
            logger.info(f"📝 Rappel : {rem['text']}")
        except Exception as e:
            logger.debug(f"extract_reminder: {e}")

    # ── Analyse intelligente des conversations ─────────────────────────────────────

    # Cache anti-doublon : {user_id: timestamp_dernière_analyse}
    _analysis_cache: dict = {}
    ANALYSIS_COOLDOWN = 300   # 5 min minimum entre deux analyses du même contact

    async def smart_contact_analysis(user_id: int, name: str, new_msg: str):
        """
        Analyse approfondie d'une conversation :
        • Détecte le style d'écriture de BUZZ avec ce contact
        • Identifie les projets / engagements en cours
        • Envoie automatiquement au Secrétariat + Organisation si projet trouvé
        • Notifie BUZZ avec un résumé actionnable
        """
        now_ts = time.time()
        if now_ts - _analysis_cache.get(user_id, 0) < ANALYSIS_COOLDOWN:
            return                          # trop tôt, on attend
        _analysis_cache[user_id] = now_ts

        history = sec_log.get(user_id, {}).get("msgs", [])
        if len(history) < 3:
            return                          # pas assez d'historique

        # Construire l'historique pour l'analyse
        conv_lines = []
        for m in history[-30:]:
            role_label = "SOSSOU" if m["r"] == "out" else name.upper()
            conv_lines.append(f"[{role_label}] {m['t']}")
        conv_text = "\n".join(conv_lines)

        _uname = config.get("user_name", "") or "l'utilisateur"
        prompt = f"""Analyse cette conversation entre {_uname} et {name}.

HISTORIQUE :
{conv_text}

NOUVEAU MESSAGE DE {name.upper()} : {new_msg}

Réponds en JSON strict UNIQUEMENT :
{{
  "has_project": true/false,
  "projects": [
    {{
      "title": "titre court du projet",
      "status": "en_cours|à_démarrer|terminé",
      "actions_for_sossou": ["action concrète 1", "action 2"],
      "deadline": "YYYY-MM-DD ou null"
    }}
  ],
  "writing_style": {{
    "formality": "formel|semi-formel|informel|amical",
    "uses_emojis": true/false,
    "language": "français|anglais|autre",
    "typical_phrases": ["ex phrase 1", "ex phrase 2"],
    "tone": "professionnel|décontracté|enthousiaste|neutre"
  }},
  "urgent_actions": ["action urgente si applicable, sinon liste vide"],
  "notification": "1-2 phrases de résumé pour {_uname}, ou null si rien d'important"
}}"""

        try:
            r = await smart_ai_call(
                f"Tu es l'assistant intelligent de {_uname}. Analyse précise.",
                [{"role": "user", "content": prompt}],
                max_tokens=600, temperature=0.1)
            m_json = re.search(r'\{.*\}', r, re.DOTALL)
            if not m_json:
                return
            data = json.loads(m_json.group())

            # ── Sauvegarder le style + l'analyse dans sec_log ─────────────────
            if user_id not in sec_log:
                sec_log[user_id] = {"name": name, "msgs": []}
            sec_log[user_id]["style"]         = data.get("writing_style", {})
            sec_log[user_id]["last_analysis"] = data
            sec_log[user_id]["analysis_date"] = benin_str()
            logger.info(f"🔍 Analyse contact {name} : projet={data.get('has_project')}")

            # ── Si projet(s) détecté(s) → Organisation + Secrétariat ──────────
            notif_parts = []
            if data.get("has_project") and data.get("projects"):
                existing_summaries = {r["summary"] for r in config["requests"]}
                for proj in data["projects"]:
                    if proj.get("status") in ("en_cours", "à_démarrer"):
                        title = proj.get("title", "")
                        if title and title not in existing_summaries:
                            existing_summaries.add(title)
                            actions_txt = "\n".join(
                                f"• {a}" for a in proj.get("actions_for_sossou", []))
                            req = {
                                "id": int(time.time()),
                                "contact": name,
                                "contact_id": user_id,
                                "text": new_msg[:300],
                                "summary": title,
                                "category": "projet",
                                "date": benin_str(),
                                "status": "pending",
                                "ai_suggestion": actions_txt,
                                "deadline": proj.get("deadline")
                            }
                            config["requests"].append(req)
                            notif_parts.append(
                                f"📌 Projet : *{title}*\n"
                                + (f"   Actions : {actions_txt}" if actions_txt else "")
                                + (f"\n   Deadline : {proj['deadline']}" if proj.get("deadline") else "")
                            )
                            # ── Rappel si deadline ────────────────────────────
                            if proj.get("deadline"):
                                dl_str = proj["deadline"]
                                if "T" not in dl_str:
                                    dl_str += "T09:00"
                                config["reminders"].append({
                                    "id": int(time.time()) + 1,
                                    "text": f"Projet '{title}' avec {name}",
                                    "contact": name,
                                    "deadline": dl_str,
                                    "created": benin_str(),
                                    "notified": False
                                })
                if notif_parts:
                    save_config(config)

            # ── Notification à BUZZ ──────────────────────────────────────────
            notification = data.get("notification")
            urgent       = data.get("urgent_actions", [])
            if notification or notif_parts or urgent:
                lines = [f"🔔 *Analyse — {name}*\n"]
                if notification:
                    lines.append(notification)
                if notif_parts:
                    lines.append("\n📂 *Nouveaux projets ajoutés à l'Organisation :*")
                    lines.extend(notif_parts)
                if urgent:
                    lines.append("\n🎯 *Actions urgentes pour vous :*")
                    lines.extend(f"  ✅ {a}" for a in urgent)
                if notif_parts:
                    lines.append("\n_Consultez /menu → 📋 Organisation_")
                await notify("\n".join(lines))

        except Exception as e:
            logger.debug(f"smart_contact_analysis({name}): {e}")

    # ── Vérificateur de rappels ────────────────────────────────────────────────────

    async def reminder_checker():
        while True:
            try:
                await asyncio.sleep(60)
                now = benin_now()
                changed = False
                for r in config.get("reminders", []):
                    if r.get("notified") or not r.get("deadline"): continue
                    try:
                        dl = datetime.fromisoformat(r["deadline"]).replace(tzinfo=BENIN_TZ)
                    except Exception: continue
                    diff = (dl - now).total_seconds() / 60
                    if diff <= 30:
                        dl_str = dl.strftime("%d/%m à %H:%M")
                        prefix = "⏰ *RAPPEL DÉPASSÉ !*" if diff <= 0 else f"⏰ *Rappel dans {int(diff)} min !*"
                        await notify(f"{prefix}\n\n👤 {r.get('contact','?')}\n📌 {r.get('text','?')}\n"
                                     f"🕐 Échéance : {dl_str} (heure Bénin)\n\n_/menu → 📝 Rappels_")
                        if diff <= 0:
                            r["notified"] = True
                        changed = True
                if changed: save_config(config)
            except Exception as e:
                logger.debug(f"reminder_checker: {e}")

    # ── Génération du rapport "Quoi de neuf" ─────────────────────────────────────

    NOUBLIE_KEYWORDS = [
        "n'oublie pas", "noublie pas", "oublie pas", "rappelle-toi", "rappelle toi",
        "souviens-toi", "souviens toi", "comme on s'est dit", "comme convenu",
        "tu te souviens", "n'oublie surtout pas", "n oublie pas"
    ]

    async def handle_noublie_pas(uid: int, name: str, text_in: str):
        """Quand quelqu'un dit 'n'oublie pas', cherche le contexte et crée une note."""
        try:
            msgs = sec_log.get(uid, {}).get("msgs", [])[-30:]
            hist_lines = "\n".join(
                f"[{'SOSSOU' if m['r']=='out' else name.upper()}] {m['t'][:200]}"
                for m in msgs
            )
            prompt = (
                f"Conversation avec {name}:\n{hist_lines}\n\n"
                f"Message actuel : '{text_in}'\n\n"
                f"La personne dit de ne pas oublier quelque chose. "
                f"Résume EN UNE PHRASE ce dont il faut se souvenir (promesse, demande, accord). "
                f"Si rien de précis n'est mentionné dans l'historique, dis 'Vérifier avec {name}'."
            )
            note = await smart_ai_call(
                "Extraction de note importante.", [{"role":"user","content":prompt}],
                max_tokens=120, temperature=0.1)

            # Ajouter dans l'organisation
            req = {
                "id": int(time.time()),
                "contact": name, "contact_id": uid,
                "text": text_in[:300],
                "summary": f"⚠️ À ne pas oublier avec {name}: {note.strip()[:150]}",
                "category": "rappel",
                "date": benin_str(),
                "status": "pending",
                "ai_suggestion": ""
            }
            config["requests"].append(req)
            save_config(config)
            # Ajouter dans away_log si mode absent
            if away_mode[0]:
                slot = away_log.setdefault(uid, {"name": name, "msgs": [], "bot_replies": [], "notes": []})
                slot.setdefault("notes", []).append(note.strip()[:200])
            await notify(
                f"📌 *Note importante créée !*\n\n"
                f"👤 {name}\n"
                f"💬 Message : _{text_in[:100]}_\n\n"
                f"📝 Note : {note.strip()[:200]}\n\n"
                f"_Ajouté dans Organisation → Demandes_"
            )
        except Exception as e:
            logger.debug(f"handle_noublie_pas: {e}")

    async def generate_briefing() -> str:
        """Génère le rapport 'Quoi de neuf' pour BUZZ à son retour."""
        if not away_log:
            return "📭 Aucune conversation pendant ton absence."

        since = benin_str(datetime.fromtimestamp(away_mode_start[0], tz=BENIN_TZ)) \
                if away_mode_start[0] > 0 else "une période récente"

        sections = []
        for uid, d in away_log.items():
            name     = d.get("name", f"ID:{uid}")
            msgs     = d.get("msgs", [])
            replies  = d.get("bot_replies", [])
            notes    = d.get("notes", [])
            # Reconstruire la conversation pendant l'absence
            conv = []
            for m in msgs:
                conv.append(f"[{name.upper()}] {m['t'][:200]}")
            _uname_b = config.get("user_name", "") or "l'utilisateur"
            for r in replies:
                conv.append(f"[{_uname_b.upper()} (bot)] {r['t'][:200]}")
            sections.append({
                "name": name, "uid": uid,
                "conv": "\n".join(conv[-12:]),
                "nb_msgs": len(msgs),
                "nb_replies": len(replies),
                "notes": notes
            })

        _uname_b = config.get("user_name", "") or "l'utilisateur"
        # Demander à l'IA de faire un résumé intelligent
        convs_text = ""
        for s in sections:
            convs_text += (
                f"\n=== {s['name']} ({s['nb_msgs']} msg(s) reçus, "
                f"{s['nb_replies']} réponse(s) bot) ===\n"
                f"{s['conv']}\n"
            )
            if s["notes"]:
                convs_text += f"[NOTES IMPORTANTES] {'; '.join(s['notes'])}\n"

        prompt = (
            f"{_uname_b} vient de revenir après une absence. "
            f"Voici ce qui s'est passé depuis {since} :\n\n{convs_text}\n\n"
            f"Fais-lui un RAPPORT DE RETOUR complet et structuré :\n"
            f"1. Pour chaque personne : résume ce qu'elle voulait, l'humeur, les points importants\n"
            f"2. Ce que le bot a répondu en son nom (résumé)\n"
            f"3. Les ACTIONS URGENTES que {_uname_b} doit faire à son retour (rappels, réponses, bots à créer, etc.)\n"
            f"4. Les opportunités détectées (budget limité, demande de service, etc.)\n\n"
            f"Ton : direct, professionnel, actionnable. Commence par les plus urgents."
        )
        ai_summary = await smart_ai_call(
            f"Tu es la secrétaire personnelle de {_uname_b}. Tu lui fais un rapport de retour.",
            [{"role":"user","content":prompt}], max_tokens=900, temperature=0.3)

        nb_total = sum(len(d.get("msgs",[])) for d in away_log.values())
        names    = ", ".join(d.get("name","?") for d in away_log.values())
        return (
            f"📬 *QUOI DE NEUF — Rapport de retour*\n"
            f"_Période : depuis {since}_\n"
            f"_Contacts : {len(away_log)} personne(s) — {names}_\n"
            f"_Messages reçus : {nb_total}_\n\n"
            f"{ai_summary[:3000]}"
        )

    _last_sossou_activity = [time.time()]   # [0] = timestamp dernier msg sortant

    # ── Auto-réponse ───────────────────────────────────────────────────────────────

    async def auto_reply(client, chat_id, user_id, text, contact_type,
                         force_away: bool = False):
        try:
            is_away = force_away or away_mode[0]
            # En mode absent : délai fixe 10s ; sinon délai config
            if is_away:
                await asyncio.sleep(10)
            else:
                wait = config["delay_seconds"] if contact_type in ("first","returning") \
                       else config.get("reply_delay_seconds", 5)
                await asyncio.sleep(wait)
                if not config.get("auto_reply_enabled", True): return
                if chat_id in stopped_chats: return

            reply = await get_reply(user_id, text, contact_type, is_away=is_away)
            await client.send_message(chat_id, reply)
            name_log = sec_log.get(user_id, {}).get("name", f"ID:{user_id}")
            logger.info(f"🤖 RÉPONSE IA | À : {name_log} (ID:{user_id}) | Texte : {reply[:300]}")

            # Enregistrer la réponse du bot dans away_log
            if is_away:
                name = sec_log.get(user_id, {}).get("name", f"ID:{user_id}")
                slot = away_log.setdefault(user_id, {"name": name, "msgs": [], "bot_replies": []})
                slot["bot_replies"].append({
                    "t": reply[:300], "d": benin_str(), "in_msg": text[:200]
                })
                _sec_log(user_id, name, "out", reply)   # aussi dans secrétariat

        except asyncio.CancelledError: pass
        except Exception as e: logger.error(f"auto_reply: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    #  MENUS TELETHON (boutons inline)
    # ═══════════════════════════════════════════════════════════════════════════

    def mk_active_bot_panel():
        """Panneau rouge affiché quand le bot répond à la place de l'admin."""
        return (
            "🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴\n"
            "⛔️⛔️⛔️⛔️⛔️⛔️⛔️⛔️⛔️⛔️⛔️⛔️⛔️⛔️⛔️\n\n"
            "🤖  *BOT ACTIF — Il répond à ta place*\n\n"
            "Le bot gère tous tes messages automatiquement.\n"
            "Appuie sur STOP pour reprendre la main\n"
            "et accéder au menu.\n\n"
            "⛔️⛔️⛔️⛔️⛔️⛔️⛔️⛔️⛔️⛔️⛔️⛔️⛔️⛔️⛔️\n"
            "🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴"
        )

    def mk_main_menu():
        nb_strats    = len(config.get("baccara_strategies", []))
        nb_consignes = len(config.get("consignes", []))
        # Bouton Mode Absent
        if away_mode[0]:
            nb_away  = len(away_log)
            away_lbl = f"✅ Mode absent actif — {nb_away} conv(s) — DÉSACTIVER"
        else:
            away_lbl = "📵  Mode absent  (bot prend le contrôle total)"
        nb_cbtns = len(config.get("custom_buttons", []))
        return [
            [Button.inline("🤖  ▶️  Répond à ma place  ◀️  🤖", b"feu_vert_toggle")],
            [Button.inline("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", b"noop")],
            [Button.inline(f"📌  Consignes  ({nb_consignes})", b"consignes"),
             Button.inline("📝  Secrétariat", b"sec")],
            [Button.inline("📅  Programme", b"prog"),
             Button.inline("🤖  Fournisseurs IA", b"ai")],
            [Button.inline(f"🎲  Baccara  ({nb_strats})", b"strat"),
             Button.inline("⚙️  Paramètres", b"prm")],
            [Button.inline(f"🎛  Mes boutons  ({nb_cbtns})", b"cbtns"),
             Button.inline("📊  Stats & Statut", b"stats")],
            [Button.inline("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", b"noop")],
            [Button.inline(away_lbl, b"away_toggle")],
            [Button.inline("📬  Quoi de neuf ?", b"quoi_de_neuf")],
        ]

    def mk_custom_btns_menu():
        btns = config.get("custom_buttons", [])
        rows = []
        for b in btns:
            short_desc = b['description'][:40] + "…" if len(b['description']) > 40 else b['description']
            rows.append([
                Button.inline(f"✏️  {b['name']}", f"cbtnedit_{b['id']}".encode()),
                Button.inline("🗑", f"cbtndelete_{b['id']}".encode()),
            ])
        if not btns:
            rows.append([Button.inline("_Aucun bouton personnalisé pour l'instant_", b"noop")])
        rows.append([Button.inline("➕  Ajouter un nouveau bouton", b"cbtnadd")])
        rows.append([Button.inline("🔙 Menu principal", b"mm")])
        return rows

    def mk_consignes_menu():
        nb = len(config.get("consignes", []))
        return [
            [Button.inline(f"📋 Voir les {nb} consigne(s)", b"consignes_v")],
            [Button.inline("➕ Ajouter une consigne",      b"consignes_a")],
            [Button.inline("🗑 Tout effacer",              b"consignes_wipe")],
            [Button.inline("🔙 Menu principal",            b"mm")],
        ]

    def mk_org_menu():
        pending = sum(1 for r in config["requests"] if r["status"]=="pending")
        done    = sum(1 for r in config["requests"] if r["status"]=="done")
        return [
            [Button.inline(f"⏳ En attente ({pending})",     b"org_p"),
             Button.inline(f"✅ Traitées ({done})",          b"org_d")],
            [Button.inline("💡 Analyser & Proposer",        b"org_a"),
             Button.inline("🗑 Vider traitées",              b"org_c")],
            [Button.inline("🔙 Menu principal",             b"mm")],
        ]

    def text_sec_session() -> str:
        """Rapport de la session en cours ou dernière session."""
        if not session_log:
            is_active = config.get("auto_reply_enabled", True)
            if is_active:
                return "📟 *Session en cours*\n\n_Aucun message enregistré pour l'instant._"
            return (
                "📟 *Dernière session*\n\n"
                "_Aucune session enregistrée. Active le bot avec «Répond à ma place» pour démarrer._"
            )

        is_active = config.get("auto_reply_enabled", True)
        status = "🔴 Session en cours" if is_active else "✅ Dernière session terminée"

        # Regrouper par contact
        by_contact: dict = {}
        service_requests: list = []
        for m in session_log:
            uid = m["uid"]
            if uid not in by_contact:
                by_contact[uid] = {"name": m["name"], "msgs": []}
            by_contact[uid]["msgs"].append(m)

        lines = [f"📟 *Secrétariat — {status}*\n",
                 f"👥 {len(by_contact)} contact(s) | 💬 {len(session_log)} échange(s)\n"]

        # Détection des demandes de services (mots-clés)
        service_keywords = ["prix", "tarif", "combien", "formation", "bot", "stratégie",
                            "acheter", "commander", "payer", "service", "intéressé",
                            "interested", "how much", "cost", "buy", "want"]
        for uid, data in by_contact.items():
            cname = data["name"]
            msgs_in  = [m for m in data["msgs"] if m["role"] == "in"]
            msgs_out = [m for m in data["msgs"] if m["role"] == "out"]
            lines.append(f"\n👤 *{cname}*  ({len(msgs_in)} msg(s) reçu(s))")
            # Aperçu des messages
            for m in data["msgs"][-6:]:
                arrow = "← " if m["role"] == "in" else "→ "
                lines.append(f"  {arrow}{m['text'][:80]}")
            # Détecter demandes de services
            for m in msgs_in:
                if any(kw in m["text"].lower() for kw in service_keywords):
                    service_requests.append(f"• {cname} : _{m['text'][:100]}_")

        if service_requests:
            lines.append(f"\n\n🎯 *Demandes de services détectées ({len(service_requests)}) :*")
            lines.extend(service_requests[:10])

        return "\n".join(lines)[:4000]

    def mk_sec_menu():
        total    = sum(len(v["msgs"]) for v in sec_log.values())
        contacts = len(sec_log)
        with_proj = sum(1 for d in sec_log.values() if d.get("last_analysis",{}).get("has_project"))
        nb_session = len(session_log)
        is_active  = config.get("auto_reply_enabled", True)
        session_lbl = f"📟 Session en cours — {nb_session} msg(s)" if is_active \
                      else f"📟 Dernière session — {nb_session} msg(s)"
        return [
            [Button.inline(session_lbl, b"sec_session")],
            [Button.inline(f"📱 Contacts ({contacts}) — dont {with_proj} projets", b"sec_contacts")],
            [Button.inline(f"📚 Conversations ({total} messages)",  b"sec_c")],
            [Button.inline("💡 Analyser & Proposer solutions",      b"sec_a")],
            [Button.inline("📋 Résumé du jour (IA)",                b"sec_r")],
            [Button.inline("📝 Rappels enregistrés",                b"rem")],
            [Button.inline("🗑 Tout effacer (RAZ)",                 b"sec_wipe")],
            [Button.inline("🔙 Menu principal",                     b"mm")],
        ]

    def mk_prog_menu():
        progs = config.get("daily_program", [])
        count = len(progs)
        return [
            [Button.inline(f"📅 Voir programme ({count} tâches)", b"prog_v")],
            [Button.inline("➕ Ajouter une tâche",  b"prog_a"),
             Button.inline("🗑 Vider programme",    b"prog_c")],
            [Button.inline("🔙 Menu principal",     b"mm")],
        ]

    def mk_ai_menu():
        providers = config["ai_providers"]
        active    = config.get("active_ai","groq")
        stealth   = "🕵️ Furtif : ON" if config.get("stealth_mode",True) else "👁 Furtif : OFF"
        auto      = "✅ Auto-réponse : ON" if config.get("auto_reply_enabled",True) else "🛑 Auto-réponse : OFF"
        rows = []
        for i, k in enumerate(AI_LIST, 1):
            pdata     = providers.get(k, {})
            keys_list = [x for x in pdata.get("keys", []) if x]
            n_keys    = len(keys_list)
            has_key   = n_keys > 0
            is_act    = k == active
            icon      = "🔵" if is_act else ("✅" if has_key else "❌")
            name_short = AI_META[k]['name'].split('—')[0].strip()
            key_badge  = f" ({n_keys}🔑)" if n_keys > 1 else ""
            label      = f"{icon} {i}. {name_short}{key_badge}"
            rows.append([Button.inline(label, f"ai_{k}".encode())])
        rows.append([Button.inline(stealth, b"ai_st"), Button.inline(auto, b"ai_auto")])
        rows.append([Button.inline("🔙 Menu principal", b"mm")])
        return rows

    def mk_strat_menu():
        strats = config.get("baccara_strategies", [])
        return [
            [Button.inline(f"📋 Voir les {len(strats)} stratégie(s)", b"strat_v")],
            [Button.inline("➕ Ajouter une stratégie",                 b"strat_a")],
            [Button.inline("🔙 Menu principal",                        b"mm")],
        ]

    def text_strat_list() -> str:
        strats = config.get("baccara_strategies", [])
        if not strats:
            return (
                "🎲 *Stratégies Baccara*\n\n"
                "_Aucune stratégie enregistrée pour l'instant._\n\n"
                "Appuyez sur ➕ Ajouter pour en saisir une."
            )
        lines = [f"🎲 *Stratégies Baccara ({len(strats)})*\n"]
        for i, s in enumerate(strats, 1):
            name = s.get("name", f"Stratégie {i}")
            desc = s.get("description", "")
            lines.append(f"*{i}. {name}*\n   _{desc}_\n")
        lines.append("_Quand un contact demande une stratégie, le bot en donne une seule._")
        return "\n".join(lines)

    def mk_prm_menu():
        d  = config['delay_seconds']
        rd = config.get('reply_delay_seconds', 5)
        q  = config['daily_quota']
        qu = config['quota_used_today']
        return [
            [Button.inline(f"⏱ Délai absence : {d}s",          b"prm_d"),
             Button.inline(f"⚡ Délai réponse : {rd}s",          b"prm_r")],
            [Button.inline(f"🔢 Quota : {qu}/{q}/jour",          b"prm_q")],
            [Button.inline("📚 Base de connaissances",           b"prm_k")],
            [Button.inline("➕ Ajouter info",   b"prm_ka"),
             Button.inline("➖ Voir & supprimer", b"prm_kv")],
            [Button.inline("🔙 Menu principal", b"mm")],
        ]

    # ═══════════════════════════════════════════════════════════════════════════
    #  CONTENUS DES MENUS
    # ═══════════════════════════════════════════════════════════════════════════

    def text_org_pending() -> str:
        reqs = [r for r in config["requests"] if r["status"]=="pending"]
        if not reqs:
            return "📋 *Organisation — Demandes en attente*\n\n_Aucune demande en attente._"
        lines = [f"📋 *Organisation — {len(reqs)} demande(s) en attente*\n"]
        for i, r in enumerate(reqs, 1):
            cat = r.get("category","?")
            lines.append(
                f"*{i}.* [{r['date']}] {r['contact']}\n"
                f"   📌 {r['summary']}\n"
                f"   🏷 {cat}")
        lines.append(f"\n_Commandes : `/orgdone <n>` pour marquer comme traité_")
        return "\n".join(lines)

    def text_org_done() -> str:
        reqs = [r for r in config["requests"] if r["status"]=="done"]
        if not reqs:
            return "✅ *Organisation — Demandes traitées*\n\n_Aucune demande traitée._"
        lines = [f"✅ *Organisation — {len(reqs)} traitée(s)*\n"]
        for i, r in enumerate(reqs[-20:], 1):
            lines.append(f"*{i}.* {r['contact']} — {r['summary']} [{r['date']}]")
        return "\n".join(lines)

    def text_prog() -> str:
        progs = config.get("daily_program", [])
        if not progs:
            return "📅 *Programme du jour*\n\n_Aucune tâche enregistrée._\n\nAppuyez ➕ pour ajouter."
        lines = [f"📅 *Programme du jour — {benin_str(benin_now())[:10]}*\n"]
        for i, p in enumerate(progs, 1):
            lines.append(f"  {i}. {p}")
        return "\n".join(lines)

    def text_stats() -> str:
        used  = config["quota_used_today"]
        total = config["daily_quota"]
        pct   = int((used/total)*100) if total else 0
        st    = "✅ Active" if config.get("auto_reply_enabled",True) else "🛑 Arrêtée"
        stealth = "🕵️ ON" if config.get("stealth_mode",True) else "🔵 OFF"
        active = config.get("active_ai","groq")
        reqs_p = sum(1 for r in config["requests"] if r["status"]=="pending")
        rems   = len(config.get("reminders",[]))
        nb_conv = len(sec_log)
        nb_msgs = sum(len(v["msgs"]) for v in sec_log.values())
        ai_lines = []
        for k in AI_LIST:
            d         = config["ai_providers"].get(k, {})
            keys_list = [x for x in d.get("keys", []) if x]
            n_keys    = len(keys_list)
            s  = "✅" if n_keys > 0 else "❌"
            nb = f" ({n_keys}🔑)" if n_keys > 1 else ""
            a  = " ← ACTIF" if k==active else ""
            ai_lines.append(f"  {s} {AI_META[k]['name']}{nb}{a}")
        _uname_s = config.get("user_name", "") or "Bot"
        return (
            f"📊 *Stats — {_uname_s}*\n\n"
            f"🕐 Heure Bénin : {benin_time()}\n"
            f"🔄 Auto-réponse : {st} | Furtif : {stealth}\n"
            f"📈 Quota : {used}/{total} ({pct}%)\n"
            f"⏱ Délai : {config['delay_seconds']}s | Réponse : {config.get('reply_delay_seconds',5)}s\n"
            f"👥 Contacts : {len(known_users)}\n\n"
            f"📋 Demandes en attente : {reqs_p}\n"
            f"📝 Rappels actifs : {rems}\n"
            f"📚 Conversations : {nb_conv} contacts, {nb_msgs} messages\n\n"
            f"🤖 *IA :*\n" + "\n".join(ai_lines)
        )

    def text_contacts_list() -> str:
        """Vue de tous les contacts enregistrés avec statut d'analyse."""
        if not sec_log:
            return "📱 *Contacts enregistrés*\n\n_Aucun contact pour l'instant._"
        lines = [f"📱 *Contacts enregistrés — {len(sec_log)} contact(s)*\n"]
        for uid, d in list(sec_log.items()):
            nb_msgs = len(d.get("msgs", []))
            name    = d.get("name", f"ID:{uid}")
            last    = d["msgs"][-1]["t"][:50] if d.get("msgs") else "—"
            has_analysis = "last_analysis" in d
            has_project  = d.get("last_analysis", {}).get("has_project", False)
            style        = d.get("style", {})
            formality    = style.get("formality", "")
            ana_icon     = ("📌" if has_project else "✅") if has_analysis else "⏳"
            lines.append(
                f"{ana_icon} *{name}* — {nb_msgs} msg(s)\n"
                + (f"   Style : {formality}\n" if formality else "")
                + f"   Dernier : _{last[:50]}_\n"
            )
        lines.append("\n_Cliquez sur un contact dans le menu pour voir le détail._")
        return "\n".join(lines)

    def text_contact_detail(uid: int) -> str:
        """Détail d'un contact : historique + analyse."""
        d = sec_log.get(uid)
        if not d:
            return "❌ Contact introuvable."
        name   = d.get("name", f"ID:{uid}")
        msgs   = d.get("msgs", [])
        style  = d.get("style", {})
        ana    = d.get("last_analysis", {})
        ana_dt = d.get("analysis_date", "")

        lines = [f"👤 *{name}* — {len(msgs)} message(s)\n"]

        # Historique récent
        lines.append("📜 *Historique récent :*")
        for m in msgs[-15:]:
            r   = "➡️ Vous" if m["r"] == "out" else f"⬅️ {name}"
            lines.append(f"  [{m.get('d','')}] {r}: _{m['t'][:80]}_")

        # Style détecté
        if style:
            lines.append(f"\n🎨 *Style détecté :*")
            lines.append(f"  Ton : {style.get('formality','')} / {style.get('tone','')}")
            lines.append(f"  Emojis : {'oui' if style.get('uses_emojis') else 'non'}")
            phrases = style.get("typical_phrases", [])
            if phrases:
                lines.append(f"  Expressions : {', '.join(phrases[:3])}")

        # Projets détectés
        if ana.get("has_project") and ana.get("projects"):
            lines.append(f"\n📂 *Projets détectés* (analyse du {ana_dt}) :")
            for p in ana["projects"]:
                lines.append(f"  📌 *{p.get('title','?')}* [{p.get('status','?')}]")
                for a in p.get("actions_for_sossou", []):
                    lines.append(f"      ✅ {a}")
                if p.get("deadline"):
                    lines.append(f"      📅 Deadline : {p['deadline']}")
        elif ana:
            lines.append(f"\n_Aucun projet détecté (analysé le {ana_dt})_")

        # Actions urgentes
        urgent = ana.get("urgent_actions", [])
        if urgent:
            lines.append(f"\n🎯 *Actions urgentes :*")
            for a in urgent:
                lines.append(f"  ✅ {a}")

        return "\n".join(lines)

    def mk_sec_contacts_menu():
        """Menu avec bouton par contact pour voir le détail."""
        rows = []
        for uid, d in list(sec_log.items()):
            name = d.get("name", f"ID:{uid}")
            has_proj = d.get("last_analysis", {}).get("has_project", False)
            icon = "📌" if has_proj else "👤"
            rows.append([Button.inline(f"{icon} {name}", f"sec_ct_{uid}".encode())])
        rows.append([Button.inline("🔙 Secrétariat", b"sec")])
        return rows

    async def text_sec_analyze(client) -> str:
        if not sec_log:
            return "📝 *Secrétariat*\n\n_Aucune conversation enregistrée pour l'instant._"
        summary_parts = []
        for uid, data in list(sec_log.items())[-5:]:
            name = data["name"]
            msgs = data["msgs"][-10:]
            conv = "\n".join(f"[{m['r'].upper()}] {m['t']}" for m in msgs)
            summary_parts.append(f"Contact : {name}\n{conv}")
        all_text = "\n\n---\n\n".join(summary_parts)
        _uname_sec = config.get("user_name", "") or "l'utilisateur"
        prompt = (
            f"Voici des conversations récentes de {_uname_sec} :\n\n{all_text}\n\n"
            "En tant que secrétaire intelligent, analyse ces conversations et propose :\n"
            "1. Un résumé des points importants\n"
            "2. Des actions recommandées\n"
            "3. Des opportunités commerciales détectées\n"
            "4. Des réponses suggérées si nécessaire\n\n"
            "Sois concis et actionnable. Réponds en français."
        )
        try:
            return await smart_ai_call(
                f"Tu es le secrétaire intelligent de {_uname_sec}.",
                [{"role":"user","content":prompt}], max_tokens=600, temperature=0.5)
        except Exception as e:
            return f"❌ Erreur analyse : {e}"

    async def text_sec_resume() -> str:
        if not sec_log:
            return "📤 *Résumé du jour*\n\n_Aucune conversation aujourd'hui._"
        all_contacts = []
        for uid, data in sec_log.items():
            name = data["name"]
            nb   = len(data["msgs"])
            inc  = sum(1 for m in data["msgs"] if m["r"]=="in")
            out  = sum(1 for m in data["msgs"] if m["r"]=="out")
            last = data["msgs"][-1]["t"][:80] if data["msgs"] else ""
            all_contacts.append(f"- {name} : {nb} messages ({inc} reçus, {out} envoyés)\n  Dernier : {last}")
        contacts_text = "\n".join(all_contacts)
        _uname_res = config.get("user_name", "") or "l'utilisateur"
        prompt = (
            f"Conversations du jour de {_uname_res} :\n{contacts_text}\n\n"
            "Fais un résumé exécutif en 5-8 lignes max avec :\n"
            "• Ce qui s'est passé\n• Ce qui est urgent\n• Actions à faire"
        )
        try:
            result = await smart_ai_call(
                f"Tu es le secrétaire de {_uname_res}. Résumé exécutif.",
                [{"role":"user","content":prompt}], max_tokens=400, temperature=0.4)
            return f"📤 *Résumé du jour — {benin_str(benin_now())[:10]}*\n\n{result}"
        except Exception as e:
            return f"❌ Erreur résumé : {e}"

    async def text_org_analyze() -> str:
        reqs = [r for r in config["requests"] if r["status"]=="pending"]
        if not reqs:
            return "📋 *Analyse Organisation*\n\n_Aucune demande en attente à analyser._"
        req_text = "\n".join(
            f"- [{r['category']}] {r['contact']} : {r['summary']}" for r in reqs)
        _uname_org = config.get("user_name", "") or "l'utilisateur"
        prompt = (
            f"{_uname_org} a {len(reqs)} demandes en attente :\n{req_text}\n\n"
            "En tant que conseiller, propose :\n"
            "1. La priorité de traitement\n"
            "2. Les actions concrètes à faire pour chaque demande\n"
            "3. Des réponses types suggérées\n"
            "4. Des opportunités commerciales\n\n"
            "Sois concis et pratique."
        )
        try:
            result = await smart_ai_call(
                f"Tu es le conseiller commercial de {_uname_org}.",
                [{"role":"user","content":prompt}], max_tokens=600, temperature=0.5)
            return f"💡 *Analyse Organisation*\n\n{result}"
        except Exception as e:
            return f"❌ Erreur : {e}"

    def text_reminders() -> str:
        rems = config.get("reminders", [])
        if not rems:
            return "📝 *Rappels*\n\n_Aucun rappel enregistré._\n\n_Le secrétaire extrait automatiquement vos promesses._"
        lines = [f"📝 *Rappels ({len(rems)})*\n"]
        for i, r in enumerate(rems, 1):
            done = "✅" if r.get("notified") else "⏳"
            dl   = r.get("deadline","—")
            if dl and dl != "—":
                try:
                    dt = datetime.fromisoformat(dl).replace(tzinfo=BENIN_TZ)
                    dl = dt.strftime("%d/%m à %H:%M (Bénin)")
                except: pass
            lines.append(f"{done} *{i}.* {r.get('contact','?')}\n   📌 {r.get('text','?')}\n   🕐 {dl}")
        lines.append("\n_`/donenote <n>` | `/deletenote <n>`_")
        return "\n".join(lines)

    # ═══════════════════════════════════════════════════════════════════════════
    #  CLIENT TELETHON
    # ═══════════════════════════════════════════════════════════════════════════

    async def _main():
        _has_client = False
        client = None
        try:
            if SESSION_STRING:
                client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
                await client.connect()
                if not await client.is_user_authorized():
                    raise ValueError("Session non autorisée")
                _client_ref[0] = client
                _has_client = True
                # Sauvegarder le prénom de l'utilisateur si pas encore défini
                try:
                    _me0 = await client.get_me()
                    if not config.get("user_name"):
                        config["user_name"]     = getattr(_me0, "first_name", "") or ""
                        config["user_username"] = getattr(_me0, "username",   "") or ""
                        save_config(config)
                except Exception:
                    pass
            else:
                logger.info("ℹ️ Aucune session admin — le bot PTB démarre en mode inscription")
        except Exception as e:
            err = str(e)
            logger.error(f"❌ Session invalide : {e}")
            try:
                Path(SESSION_FILE).write_text("")
                if "two different IP" in err or "non autorisée" in err.lower() or "not authorized" in err.lower():
                    cfg2 = load_config()
                    cfg2.setdefault("credentials", {})["telegram_session"] = ""
                    save_config(cfg2)
                logger.warning("🗑 Session effacée — le bot PTB continue en mode inscription")
            except Exception:
                pass
            _has_client = False
            client = None

        # ── Client factice si pas de session (laisse les @client.on fonctionner) ──
        if not _has_client:
            class _DummyClient:
                def on(self, *a, **kw):
                    return lambda fn: fn
            client = _DummyClient()

        # ── Chargement de l'historique Telegram au démarrage ─────────────────
        async def load_telegram_history():
            """Importe les derniers messages des conversations privées dans sec_log.
            Prudent : max 25 dialogs, 30 messages chacun, pause entre chaque."""
            await asyncio.sleep(3)   # Laisser le bot s'initialiser d'abord
            try:
                nb_dialogs = 0
                nb_msgs    = 0
                dialogs_done = 0
                async for dialog in client.iter_dialogs(limit=50):
                    if dialogs_done >= 25:
                        break          # Max 25 conversations privées
                    if not dialog.is_user:
                        continue       # ignorer groupes et canaux
                    entity = dialog.entity
                    if getattr(entity, "bot", False):
                        continue       # ignorer les bots
                    uid  = entity.id
                    name = (f"{getattr(entity,'first_name','') or ''} "
                            f"{getattr(entity,'last_name','') or ''}").strip() or f"ID:{uid}"

                    # Ne pas re-charger si déjà bien rempli (> 20 msgs)
                    existing_count = len(sec_log.get(uid, {}).get("msgs", []))
                    if existing_count >= 20:
                        known_users.add(uid)
                        dialogs_done += 1
                        continue

                    existing_texts = {m["t"] for m in sec_log.get(uid, {}).get("msgs", [])}
                    new_msgs = []
                    try:
                        async for msg in client.iter_messages(entity, limit=30):
                            if not msg.text or not msg.text.strip():
                                continue
                            role = "out" if msg.out else "in"
                            ts   = benin_str(msg.date.astimezone(BENIN_TZ) if msg.date else benin_now())
                            t    = msg.text.strip()[:500]
                            if t not in existing_texts:
                                new_msgs.append({"r": role, "t": t, "d": ts})
                                existing_texts.add(t)
                    except Exception:
                        pass   # Flood wait géré par Telethon automatiquement

                    if new_msgs:
                        new_msgs.reverse()   # Ordre chronologique
                        if uid not in sec_log:
                            sec_log[uid] = {"name": name, "msgs": []}
                        sec_log[uid]["name"] = name
                        sec_log[uid]["msgs"] = new_msgs + sec_log[uid]["msgs"]
                        sec_log[uid]["msgs"] = sec_log[uid]["msgs"][-200:]
                        nb_msgs += len(new_msgs)
                        nb_dialogs += 1

                    known_users.add(uid)
                    dialogs_done += 1
                    await asyncio.sleep(0.5)   # Pause pour éviter le flood

                if nb_dialogs > 0:
                    save_sec_log(sec_log)
                total_contacts = len(sec_log)
                total_msgs = sum(len(v.get("msgs",[])) for v in sec_log.values())
                logger.info(f"📥 Historique chargé : {nb_dialogs} nouvelles convs, "
                            f"{nb_msgs} msgs. Total : {total_contacts} contacts, {total_msgs} msgs")
            except Exception as e:
                logger.warning(f"load_telegram_history: {e}")

        if _has_client:
            asyncio.get_event_loop().create_task(load_telegram_history())
            logger.info("🔄 Chargement historique Telegram en arrière-plan...")

        # ── Messages entrants ─────────────────────────────────────────────────

        @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
        async def on_in(event):
            sender = await event.get_sender()
            if not sender or getattr(sender,"bot",False): return
            chat_id = event.chat_id
            uid     = sender.id
            now     = time.time()
            name    = (f"{getattr(sender,'first_name','') or ''} "
                       f"{getattr(sender,'last_name','') or ''}").strip() or f"ID:{uid}"

            # Secrétariat : enregistrer le message
            text_in = event.text or ""
            _sec_log(uid, name, "in", text_in)

            # Log visible dans la console
            logger.info(f"📨 MESSAGE REÇU | De : {name} (ID:{uid}) | Texte : {text_in[:300] or '[média/non-texte]'}")

            first_contact = uid not in known_users
            last_time     = last_msg_time.get(uid, 0)
            is_returning  = (not first_contact) and ((now - last_time) > SESSION_TIMEOUT)
            last_msg_time[uid] = now

            if first_contact:
                contact_type = "first"
                known_users.add(uid)
                conv_history.pop(uid, None)
                # Notifier l'admin
                try:
                    await notify(
                        f"🔔 *Nouveau contact !*\n\n"
                        f"👤 {name}\n🆔 ID: {uid}\n\n"
                        f"Message : _{text_in[:100]}_\n\n"
                        f"Auto-réponse dans {config['delay_seconds']}s.")
                except: pass
            elif is_returning:
                contact_type = "returning"
                conv_history.pop(uid, None)
            else:
                contact_type = "ongoing"

            # Enregistrer dans away_log si mode absent
            if away_mode[0]:
                slot = away_log.setdefault(uid, {"name": name, "msgs": [], "bot_replies": [], "notes": []})
                slot["msgs"].append({"t": text_in[:300], "d": benin_str()})

            # Extraction de demandes (organisation) + analyse intelligente
            # Délai échelonné pour éviter les appels IA simultanés (rate limit Gemini)
            if text_in:
                async def _delayed_extract(u, n, t):
                    await asyncio.sleep(8)
                    await extract_request(u, n, t)
                async def _delayed_analysis(u, n, t):
                    await asyncio.sleep(18)
                    await smart_contact_analysis(u, n, t)
                asyncio.create_task(_delayed_extract(uid, name, text_in))
                asyncio.create_task(_delayed_analysis(uid, name, text_in))

            # Détection "n'oublie pas / rappelle-toi"
            text_low = text_in.lower()
            if any(kw in text_low for kw in NOUBLIE_KEYWORDS):
                asyncio.create_task(handle_noublie_pas(uid, name, text_in))

            # Annuler tâche précédente
            t = pending_tasks.get(chat_id)
            if t and not t.done(): t.cancel()

            # Mode absent → toujours répondre ; sinon vérifier auto_reply_enabled
            if away_mode[0]:
                pending_tasks[chat_id] = asyncio.create_task(
                    auto_reply(client, chat_id, uid, text_in, contact_type, force_away=True))
            elif config.get("auto_reply_enabled", True) and chat_id not in stopped_chats:
                pending_tasks[chat_id] = asyncio.create_task(
                    auto_reply(client, chat_id, uid, text_in, contact_type))

        # ── Messages sortants ──────────────────────────────────────────────────

        @client.on(events.NewMessage(outgoing=True, func=lambda e: e.is_private))
        async def on_out(event):
            text = event.text or ""
            if text.startswith("/"): return

            # Capture états en attente
            if state["param_waiting"] == "addprog" and text:
                state["param_waiting"] = None
                progs = config.setdefault("daily_program", [])
                progs.append(text.strip())
                save_config(config)
                await event.respond(f"✅ Tâche ajoutée !\n\n{text_prog()}", buttons=mk_prog_menu())
                return

            if state["param_waiting"] == "delay" and text.strip().isdigit():
                config["delay_seconds"] = int(text.strip())
                save_config(config)
                state["param_waiting"] = None
                await event.respond(f"✅ Délai absence : *{config['delay_seconds']}s*",
                                    buttons=mk_prm_menu())
                return

            if state["param_waiting"] == "replydelay" and text.strip().isdigit():
                config["reply_delay_seconds"] = int(text.strip())
                save_config(config)
                state["param_waiting"] = None
                await event.respond(f"✅ Délai réponse : *{config['reply_delay_seconds']}s*",
                                    buttons=mk_prm_menu())
                return

            if state["param_waiting"] == "quota" and text.strip().isdigit():
                config["daily_quota"] = int(text.strip())
                save_config(config)
                state["param_waiting"] = None
                await event.respond(f"✅ Quota : *{config['daily_quota']}/jour*",
                                    buttons=mk_prm_menu())
                return

            if state["param_waiting"] == "addinfo" and text:
                config["knowledge_base"].append(text.strip())
                save_config(config)
                state["param_waiting"] = None
                await event.respond(f"✅ Info ajoutée !\n_{text.strip()}_", buttons=mk_prm_menu())
                return

            if state["param_waiting"] == "consigne_add" and text:
                consigne = {"id": int(time.time()), "text": text.strip()}
                config.setdefault("consignes", []).append(consigne)
                save_config(config)
                state["param_waiting"] = None
                nb = len(config["consignes"])
                await event.respond(
                    f"✅ *Consigne #{nb} enregistrée !*\n\n_{text.strip()}_\n\n"
                    f"Le bot la respectera à partir de maintenant.",
                    buttons=mk_consignes_menu())
                return

            if state["param_waiting"] == "addstrat" and text:
                raw = text.strip()
                # Format attendu : "Nom | Description" ou juste "Description"
                if "|" in raw:
                    nom, desc = raw.split("|", 1)
                    nom  = nom.strip()
                    desc = desc.strip()
                else:
                    # Numéro automatique si pas de nom donné
                    n = len(config.get("baccara_strategies", [])) + 1
                    nom  = f"Stratégie {n}"
                    desc = raw
                strat_obj = {"name": nom, "description": desc}
                config.setdefault("baccara_strategies", []).append(strat_obj)
                save_config(config)
                state["param_waiting"] = None
                await event.respond(
                    f"✅ Stratégie enregistrée !\n\n"
                    f"*{nom}*\n_{desc}_",
                    buttons=mk_strat_menu()
                )
                return

            if state["param_waiting"] == "remind" and text:
                if "|" in text:
                    nt, dl_t = text.split("|", 1)
                    try:
                        dl_dt = datetime.fromisoformat(dl_t.strip()).replace(tzinfo=BENIN_TZ)
                        dl_iso = dl_dt.strftime("%Y-%m-%dT%H:%M")
                    except:
                        dl_iso = dl_t.strip()
                else:
                    nt, dl_iso = text, None
                config["reminders"].append({
                    "id": int(time.time()), "text": nt.strip(), "contact": "Manuel",
                    "deadline": dl_iso, "created": benin_str(), "notified": False
                })
                save_config(config)
                state["param_waiting"] = None
                await event.respond(f"✅ Rappel ajouté !", buttons=mk_sec_menu())
                return

            # ── Boutons personnalisés : étape 1 (nom) ────────────────────────────
            if state["param_waiting"] == "cbtn_name" and text:
                state["cbtn_tmp_name"] = text.strip()
                state["param_waiting"] = "cbtn_desc"
                await event.respond(
                    f"✅ Nom enregistré : *{text.strip()}*\n\n"
                    f"📝 Maintenant décris ce que l'assistante doit savoir/dire sur ce sujet.\n\n"
                    f"_Exemple : «La formation Baccara coûte 90$, dure 2 semaines, "
                    f"accessible en ligne, je réponds aux questions dès que possible.»_")
                return

            # ── Boutons personnalisés : étape 2 (description) ────────────────────
            if state["param_waiting"] == "cbtn_desc" and text:
                name = state.get("cbtn_tmp_name", "Sans nom")
                new_btn = {
                    "id":          int(time.time()),
                    "name":        name,
                    "description": text.strip()
                }
                config.setdefault("custom_buttons", []).append(new_btn)
                save_config(config)
                state["param_waiting"] = None
                state["cbtn_tmp_name"] = None
                nb = len(config["custom_buttons"])
                await event.respond(
                    f"🎛 *Bouton créé avec succès !*\n\n"
                    f"📌 Nom : *{name}*\n"
                    f"📝 Description : _{text.strip()}_\n\n"
                    f"L'assistante comprendra désormais les questions sur « {name} » "
                    f"et répondra intelligemment à ta place.",
                    buttons=mk_custom_btns_menu())
                return

            # ── Boutons personnalisés : modification (description) ───────────────
            if state["param_waiting"] == "cbtn_edit_desc" and text:
                bid = state.get("cbtn_tmp_id")
                btns = config.get("custom_buttons", [])
                btn = next((b for b in btns if b["id"] == bid), None)
                if btn:
                    btn["description"] = text.strip()
                    save_config(config)
                    await event.respond(
                        f"✅ *Bouton mis à jour !*\n\n"
                        f"📌 *{btn['name']}*\n"
                        f"📝 _{text.strip()}_\n\n"
                        f"L'assistante utilisera cette nouvelle description.",
                        buttons=mk_custom_btns_menu())
                else:
                    await event.respond("❌ Bouton introuvable.", buttons=mk_custom_btns_menu())
                state["param_waiting"] = None
                state["cbtn_tmp_id"]   = None
                return

            if state["ai_waiting"] and text:
                provider = state["ai_waiting"]
                state["ai_waiting"] = None
                await event.delete()
                await event.respond("🔍 Vérification...")
                loop = asyncio.get_event_loop()
                model = config["ai_providers"][provider].get("model", AI_META[provider]["model"])
                ok, info = await loop.run_in_executor(None, verify_key, provider, text.strip(), model)
                if not ok:
                    await event.respond(f"❌ Clé invalide\n\n{info}", buttons=mk_ai_menu())
                else:
                    new_key = text.strip()
                    keys_list = config["ai_providers"][provider].setdefault("keys", [])
                    if new_key not in keys_list:
                        keys_list.append(new_key)
                    config["active_ai"] = provider
                    save_config(config)
                    masked   = new_key[:8]+"..."+new_key[-4:]
                    n_keys   = len(keys_list)
                    await event.respond(
                        f"✅ *{AI_META[provider]['name']}* — clé ajoutée !\n\n"
                        f"Clé : `{masked}`\n{info}\n\n"
                        f"Total clés pour ce fournisseur : *{n_keys}*\n"
                        f"_(bascule automatique si quota épuisé)_", buttons=mk_ai_menu())
                return

            # Mettre à jour l'horodatage d'activité de BUZZ
            _last_sossou_activity[0] = time.time()

            # Annuler auto-réponse si admin répond manuellement
            chat_id = event.chat_id
            t = pending_tasks.get(chat_id)
            if t and not t.done(): t.cancel()

            # Secrétariat + rappels
            if text and len(text) > 5:
                try:
                    ent  = await event.get_chat()
                    cname = (f"{getattr(ent,'first_name','') or ''} "
                             f"{getattr(ent,'last_name','') or ''}").strip() or f"Chat:{chat_id}"
                    _sec_log(chat_id, cname, "out", text)
                    asyncio.create_task(extract_reminder(cname, text))
                except: pass

        # ── Callbacks Telethon (boutons) ──────────────────────────────────────

        @client.on(events.CallbackQuery)
        async def on_cb(event):
            data = event.data.decode("utf-8")
            await event.answer()

            if data == "noop":
                return

            if data == "mm":
                if config.get("auto_reply_enabled", True):
                    await event.edit(mk_active_bot_panel(),
                                     buttons=[[Button.inline("🔵   ⏹  STOP — Reprendre la main  ⏹   🔵", b"feu_vert_toggle")]])
                else:
                    await event.edit(f"🏠 *Menu Principal — {config.get('user_name','Mon Bot')}*\n\nChoisissez une section :",
                                     buttons=mk_main_menu())

            elif data == "org":
                await event.edit("📋 *Organisation*\nGestion des demandes clients :",
                                 buttons=mk_org_menu())
            elif data == "org_p":
                await event.edit(text_org_pending(), buttons=mk_org_menu())
            elif data == "org_d":
                await event.edit(text_org_done(), buttons=mk_org_menu())
            elif data == "org_a":
                await event.edit("💡 Analyse en cours...", buttons=None)
                result = await text_org_analyze()
                await event.edit(result, buttons=mk_org_menu())
            elif data == "org_c":
                config["requests"] = [r for r in config["requests"] if r["status"]!="done"]
                save_config(config)
                await event.edit("✅ Demandes traitées supprimées.", buttons=mk_org_menu())

            elif data == "sec":
                total = sum(len(v["msgs"]) for v in sec_log.values())
                nb_s  = len(session_log)
                is_active = config.get("auto_reply_enabled", True)
                sess_info = f"🔴 Session active — {nb_s} msg(s)" if is_active \
                            else f"📟 Dernière session — {nb_s} msg(s)"
                await event.edit(
                    f"📝 *Secrétariat — Centre de contrôle*\n\n"
                    f"📚 {len(sec_log)} contacts | {total} messages\n"
                    f"🕐 {benin_time()} (heure Bénin)\n"
                    f"{sess_info}\n\n"
                    f"Choisissez une action :", buttons=mk_sec_menu())

            elif data == "sec_session":
                await event.edit(text_sec_session(), buttons=[
                    [Button.inline("🔄 Actualiser", b"sec_session")],
                    [Button.inline("🗑 Vider la session", b"sec_session_clear")],
                    [Button.inline("🔙 Secrétariat", b"sec")],
                ])

            elif data == "sec_session_clear":
                session_log.clear()
                await event.edit(
                    "🗑 *Session vidée.*\n\nLes messages de session ont été effacés.",
                    buttons=[[Button.inline("🔙 Secrétariat", b"sec")]])

            elif data == "sec_contacts":
                await event.edit(text_contacts_list(), buttons=mk_sec_contacts_menu())

            elif data.startswith("sec_ct_"):
                try:
                    ct_uid = int(data.split("sec_ct_")[1])
                except:
                    await event.answer("❌ Contact invalide", alert=True); return
                detail = text_contact_detail(ct_uid)
                cname  = sec_log.get(ct_uid, {}).get("name", f"ID:{ct_uid}")
                await event.edit(detail[:3800], buttons=[
                    [Button.inline("🔍 Forcer analyse IA maintenant", f"sec_ana_{ct_uid}".encode())],
                    [Button.inline("🔙 Contacts",   b"sec_contacts")],
                    [Button.inline("🔙 Secrétariat", b"sec")],
                ])

            elif data.startswith("sec_ana_"):
                try:
                    ct_uid = int(data.split("sec_ana_")[1])
                except:
                    await event.answer("❌ Contact invalide", alert=True); return
                ct_data = sec_log.get(ct_uid, {})
                cname   = ct_data.get("name", f"ID:{ct_uid}")
                if len(ct_data.get("msgs", [])) < 3:
                    await event.answer("⚠️ Pas assez de messages (min 3)", alert=True); return
                # Réinitialiser le cooldown pour forcer l'analyse
                _analysis_cache.pop(ct_uid, None)
                await event.edit(f"🔍 Analyse en cours pour *{cname}*...", buttons=None)
                last_msg = ct_data["msgs"][-1]["t"] if ct_data.get("msgs") else "—"
                await smart_contact_analysis(ct_uid, cname, last_msg)
                detail = text_contact_detail(ct_uid)
                await event.edit(detail[:3800], buttons=[
                    [Button.inline("🔍 Re-analyser", f"sec_ana_{ct_uid}".encode())],
                    [Button.inline("🔙 Contacts",    b"sec_contacts")],
                    [Button.inline("🔙 Secrétariat", b"sec")],
                ])

            elif data == "sec_c":
                if not sec_log:
                    await event.edit("📚 *Conversations*\n\n_Aucune conversation enregistrée._",
                                     buttons=mk_sec_menu())
                    return
                lines = [f"📚 *Conversations du jour*\n"]
                for uid, d in list(sec_log.items())[-10:]:
                    nb = len(d["msgs"])
                    last = d["msgs"][-1]["t"][:60] if d["msgs"] else "—"
                    lines.append(f"👤 *{d['name']}* ({nb} msgs)\n   _{last}_\n")
                await event.edit("\n".join(lines), buttons=mk_sec_menu())
            elif data == "sec_a":
                await event.edit("💡 Analyse en cours...", buttons=None)
                result = await text_sec_analyze(client)
                await event.edit(result[:3000], buttons=mk_sec_menu())
            elif data == "sec_r":
                await event.edit("📤 Génération du résumé...", buttons=None)
                result = await text_sec_resume()
                await event.edit(result[:3000], buttons=mk_sec_menu())

            elif data == "sec_wipe":
                nb = len(sec_log)
                nb_msgs = sum(len(v.get("msgs",[])) for v in sec_log.values())
                await event.edit(
                    f"⚠️ *Effacer toutes les données ?*\n\n"
                    f"Cela supprimera définitivement :\n"
                    f"• {nb} contact(s) enregistré(s)\n"
                    f"• {nb_msgs} message(s) archivé(s)\n"
                    f"• Toutes les analyses IA\n\n"
                    f"_Cette action est irréversible._",
                    buttons=[
                        [Button.inline("✅ Oui, tout effacer", b"sec_wipe_ok")],
                        [Button.inline("❌ Annuler",            b"sec")],
                    ])

            elif data == "sec_wipe_ok":
                sec_log.clear()
                conv_history.clear()
                known_users.clear()
                _analysis_cache.clear()
                save_sec_log(sec_log)
                _ai_key_alerted[0] = False  # Réactiver les alertes clé IA
                await event.edit(
                    "✅ *Données effacées avec succès !*\n\n"
                    "Toutes les conversations et contacts ont été supprimés.\n"
                    "L'assistante repart de zéro.",
                    buttons=[[Button.inline("🔙 Menu principal", b"mm")]])

            elif data == "rem":
                await event.edit(text_reminders(), buttons=[
                    [Button.inline("➕ Ajouter un rappel", b"rem_a")],
                    [Button.inline("🔙 Secrétariat", b"sec")],
                ])
            elif data == "rem_a":
                state["param_waiting"] = "remind"
                await event.edit(
                    "📝 *Ajouter un rappel*\n\n"
                    "Envoyez : `texte | YYYY-MM-DD HH:MM`\n"
                    "Ex : `Finir bot de Jean | 2026-03-22 23:59`\n\n"
                    "_(date/heure Bénin)_")

            # ── Mode Absent ────────────────────────────────────────────────────
            elif data == "away_toggle":
                if away_mode[0]:
                    # Désactiver
                    away_mode[0] = False
                    nb = len(away_log)
                    await event.edit(
                        f"🔴 *Mode Absent désactivé*\n\n"
                        f"📊 Pendant ton absence : {nb} personne(s) ont écrit.\n\n"
                        f"Tape *📬 Quoi de neuf ?* pour voir le rapport complet.",
                        buttons=[
                            [Button.inline("📬 Quoi de neuf ?", b"quoi_de_neuf")],
                            [Button.inline("🔙 Menu", b"mm")],
                        ])
                else:
                    # Activer
                    away_mode[0]       = True
                    away_mode_start[0] = time.time()
                    away_log.clear()
                    await event.edit(
                        f"📵 *Je suis occupé — Bot activé !*\n\n"
                        f"✅ Le bot répond à ta place dès maintenant.\n\n"
                        f"⏱ Délai naturel : 10 secondes avant chaque réponse\n"
                        f"🧠 Connaît ton style d'écriture et tes projets\n"
                        f"📝 Note tout ce qui se dit dans le secrétariat\n"
                        f"📌 Détecte les *\"n'oublie pas\"* → crée des notes auto\n"
                        f"💰 Détecte les demandes de budget limité → alerte\n\n"
                        f"_Quand tu reviens → *📬 Quoi de neuf ?* pour le rapport complet._",
                        buttons=[
                            [Button.inline("📬 Quoi de neuf ? (rapport)", b"quoi_de_neuf")],
                            [Button.inline("🔙 Menu", b"mm")],
                        ])

            # ── Quoi de neuf ────────────────────────────────────────────────────
            elif data == "quoi_de_neuf":
                if not away_log:
                    await event.edit(
                        "📭 *Aucune conversation enregistrée pendant ton absence.*\n\n"
                        "Active d'abord le Mode Absent, puis reviens ici pour voir le rapport.",
                        buttons=[[Button.inline("🔙 Menu", b"mm")]])
                    return
                await event.edit("📬 *Génération du rapport en cours...*", buttons=None)
                briefing = await generate_briefing()
                # Reset après lecture
                away_log.clear()
                await event.edit(
                    briefing[:4000],
                    buttons=[
                        [Button.inline("🔄 Réactiver Mode Absent", b"away_toggle")],
                        [Button.inline("📋 Organisation", b"org")],
                        [Button.inline("🔙 Menu", b"mm")],
                    ])

            # ── Répond à ma place / STOP ───────────────────────────────────────
            elif data == "feu_vert_toggle":
                config["auto_reply_enabled"] = not config.get("auto_reply_enabled", True)
                save_config(config)
                if config["auto_reply_enabled"]:
                    stopped_chats.clear()
                    session_log.clear()
                    session_start_ts[0] = time.time()
                    await event.edit(
                        mk_active_bot_panel(),
                        buttons=[
                            [Button.inline("🔵   ⏹  STOP — Reprendre la main  ⏹   🔵", b"feu_vert_toggle")],
                        ])
                else:
                    await event.edit(
                        "✅ *Bot mis en pause*\n\n"
                        "Le bot n'envoie plus de réponses automatiques.\n\n"
                        "⏳ Le menu apparaît dans 5 secondes...",
                        buttons=None)
                    async def _show_menu_after_delay():
                        await asyncio.sleep(5)
                        try:
                            await event.delete()
                        except Exception:
                            pass
                        await client.send_message(
                            "me",
                            f"🏠 *Menu Principal — {config.get('user_name','Mon Bot')}*\n\nChoisissez une section :",
                            buttons=mk_main_menu())
                    asyncio.ensure_future(_show_menu_after_delay())

            # ── Consignes ──────────────────────────────────────────────────────
            elif data == "consignes":
                nb = len(config.get("consignes", []))
                await event.edit(
                    f"📌 *Consignes ({nb})*\n\n"
                    f"Définis ici ce que le bot doit respecter :\n"
                    f"• _Ex : si ID:67799 t'envoie un message, dis-lui que je ne suis pas là_\n"
                    f"• _Ex : ne propose jamais les formations à Jean_\n"
                    f"• _Ex : si quelqu'un demande le prix, dis que c'est 25$_\n\n"
                    f"Ces instructions ont une priorité absolue sur tout le reste.",
                    buttons=mk_consignes_menu())

            elif data == "consignes_v":
                consignes = config.get("consignes", [])
                if not consignes:
                    await event.edit(
                        "📌 *Consignes*\n\n_Aucune consigne enregistrée._\n\n"
                        "Appuie sur ➕ pour en ajouter.",
                        buttons=mk_consignes_menu())
                    return
                lines = ["📌 *Consignes actives* — le bot les respecte toujours :\n"]
                del_buttons = []
                for i, c in enumerate(consignes, 1):
                    lines.append(f"*{i}.* {c['text']}")
                    del_buttons.append([Button.inline(
                        f"🗑 Supprimer #{i}", f"consignes_del_{i-1}".encode())])
                del_buttons.append([Button.inline("🔙 Consignes", b"consignes")])
                await event.edit("\n".join(lines)[:4000], buttons=del_buttons)

            elif data == "consignes_a":
                state["param_waiting"] = "consigne_add"
                await event.edit(
                    "📌 *Nouvelle consigne*\n\n"
                    "Envoie-moi la consigne à respecter :\n\n"
                    "_Exemples :_\n"
                    "• `si ID:67799 t'écrit, dis-lui que je ne suis pas disponible`\n"
                    "• `ne mentionne jamais les prix sans que le client demande`\n"
                    "• `si quelqu'un parle de remise, dis que le prix est fixe`",
                    buttons=[[Button.inline("❌ Annuler", b"consignes")]])

            elif data == "consignes_wipe":
                config["consignes"] = []
                save_config(config)
                await event.edit("🗑 *Toutes les consignes ont été supprimées.*",
                                 buttons=mk_consignes_menu())

            elif data.startswith("consignes_del_"):
                idx = int(data.split("_")[-1])
                consignes = config.get("consignes", [])
                if 0 <= idx < len(consignes):
                    removed = consignes.pop(idx)
                    save_config(config)
                    await event.edit(
                        f"🗑 Consigne supprimée :\n_{ removed['text'][:200]}_",
                        buttons=mk_consignes_menu())
                else:
                    await event.edit("❌ Consigne introuvable.", buttons=mk_consignes_menu())

            # ── Boutons personnalisés ──────────────────────────────────────────
            elif data == "cbtns":
                nb = len(config.get("custom_buttons", []))
                await event.edit(
                    f"🎛 *Mes boutons personnalisés*  ({nb})\n\n"
                    f"Crée des sujets que l'assistante connaît parfaitement.\n"
                    f"Elle répondra automatiquement aux questions des gens sur ces sujets.\n\n"
                    f"_Exemple : «Prix de formation», «Livraison», «Horaires»…_",
                    buttons=mk_custom_btns_menu())

            elif data == "cbtnadd":
                state["param_waiting"] = "cbtn_name"
                state["cbtn_tmp_name"] = None
                await event.edit(
                    "🎛 *Nouveau bouton personnalisé*\n\n"
                    "**Étape 1/2 — Donne un nom à ce bouton :**\n\n"
                    "_Exemples : «Prix de formation», «Délai de livraison», «Contact WhatsApp»_\n\n"
                    "➡️ Tape le nom et envoie-le :")

            elif data.startswith("cbtnedit_"):
                try:
                    bid = int(data.split("cbtnedit_")[1])
                except:
                    await event.answer("❌ ID invalide", alert=True); return
                btn = next((b for b in config.get("custom_buttons", []) if b["id"] == bid), None)
                if not btn:
                    await event.answer("❌ Bouton introuvable", alert=True); return
                state["param_waiting"] = "cbtn_edit_desc"
                state["cbtn_tmp_id"]   = bid
                await event.edit(
                    f"✏️ *Modifier le bouton : {btn['name']}*\n\n"
                    f"Description actuelle :\n_{btn['description']}_\n\n"
                    f"📝 Envoie la nouvelle description :")

            elif data.startswith("cbtndelete_"):
                try:
                    bid = int(data.split("cbtndelete_")[1])
                except:
                    await event.answer("❌ ID invalide", alert=True); return
                btns = config.get("custom_buttons", [])
                btn = next((b for b in btns if b["id"] == bid), None)
                if btn:
                    config["custom_buttons"] = [b for b in btns if b["id"] != bid]
                    save_config(config)
                    await event.edit(
                        f"🗑 *Bouton supprimé : {btn['name']}*\n\n"
                        f"L'assistante ne connaît plus ce sujet.",
                        buttons=mk_custom_btns_menu())
                else:
                    await event.edit("❌ Bouton introuvable.", buttons=mk_custom_btns_menu())

            # ── Stratégies Baccara ─────────────────────────────────────────────
            elif data == "strat":
                await event.edit(text_strat_list(), buttons=mk_strat_menu())

            elif data == "strat_v":
                strats = config.get("baccara_strategies", [])
                if not strats:
                    await event.edit(
                        "🎲 *Stratégies Baccara*\n\n_Aucune stratégie enregistrée._",
                        buttons=mk_strat_menu())
                    return
                # Afficher avec bouton supprimer pour chacune
                lines = [f"🎲 *Stratégies enregistrées ({len(strats)})*\n"]
                for i, s in enumerate(strats, 1):
                    lines.append(f"*{i}. {s.get('name','')}*\n   _{s.get('description','')}_\n")
                del_buttons = [
                    [Button.inline(f"🗑 Supprimer #{i} — {s.get('name','')[:25]}",
                                   f"strat_del_{i-1}".encode())]
                    for i, s in enumerate(strats, 1)
                ]
                del_buttons.append([Button.inline("🔙 Stratégies", b"strat")])
                await event.edit("\n".join(lines), buttons=del_buttons)

            elif data == "strat_a":
                state["param_waiting"] = "addstrat"
                await event.edit(
                    "🎲 *Ajouter une stratégie Baccara*\n\n"
                    "Deux formats possibles :\n\n"
                    "**Format complet** (avec nom) :\n"
                    "`Nom de la stratégie | Description détaillée`\n\n"
                    "**Format simple** (nom automatique) :\n"
                    "`Description de la stratégie directement`\n\n"
                    "_Exemple : `Même carte | Quand le joueur reçoit la même carte deux fois, "
                    "miser sur cette carte au jeu suivant.`_"
                )

            elif data.startswith("strat_del_"):
                try:
                    idx = int(data.split("strat_del_")[1])
                except:
                    await event.answer("❌ Index invalide", alert=True); return
                strats = config.get("baccara_strategies", [])
                if 0 <= idx < len(strats):
                    removed = strats.pop(idx)
                    save_config(config)
                    await event.edit(
                        f"🗑 Stratégie supprimée : *{removed.get('name','')}*",
                        buttons=mk_strat_menu()
                    )
                else:
                    await event.answer("❌ Stratégie introuvable", alert=True)

            elif data == "prog":
                await event.edit(text_prog(), buttons=mk_prog_menu())
            elif data == "prog_v":
                await event.edit(text_prog(), buttons=mk_prog_menu())
            elif data == "prog_a":
                state["param_waiting"] = "addprog"
                await event.edit("📅 *Ajouter une tâche*\n\nTapez votre tâche dans le prochain message :")
            elif data == "prog_c":
                config["daily_program"] = []
                save_config(config)
                await event.edit("✅ Programme vidé.", buttons=mk_prog_menu())

            elif data == "ai":
                await event.edit("🤖 *Fournisseurs IA*\n\nCliquez pour configurer une clé :",
                                 buttons=mk_ai_menu())
            elif data == "ai_st":
                config["stealth_mode"] = not config.get("stealth_mode", True)
                save_config(config)
                _uname_st = config.get("user_name", "") or "l'utilisateur"
                status = f"🕵️ ON — Je réponds comme {_uname_st} lui-même" if config["stealth_mode"] \
                         else "🔵 OFF — Je me présente comme l'assistante"
                await event.edit(f"Mode furtif : *{status}*", buttons=mk_ai_menu())
            elif data == "ai_auto":
                config["auto_reply_enabled"] = not config.get("auto_reply_enabled", True)
                save_config(config)
                if config["auto_reply_enabled"]:
                    stopped_chats.clear()
                status = "✅ Activée" if config["auto_reply_enabled"] else "🛑 Désactivée"
                await event.edit(f"Auto-réponse : *{status}*", buttons=mk_ai_menu())
            elif data.startswith("ai_"):
                provider = data[3:]
                if provider in AI_META:
                    state["ai_waiting"] = provider
                    pdata     = config["ai_providers"].get(provider, {})
                    keys_list = [x for x in pdata.get("keys", []) if x]
                    n_keys    = len(keys_list)
                    keys_info = "\n".join(
                        f"  🔑 Clé {i+1}: `{k[:8]}...{k[-4:]}`"
                        for i, k in enumerate(keys_list)
                    ) if keys_list else "  _Aucune clé configurée_"
                    urls = {"groq":"console.groq.com/keys","openai":"platform.openai.com/api-keys",
                            "anthropic":"console.anthropic.com","gemini":"aistudio.google.com/app/apikey",
                            "mistral":"console.mistral.ai/api-keys"}
                    await event.edit(
                        f"🔑 *{AI_META[provider]['name']}*\n\n"
                        f"Clés configurées ({n_keys}) :\n{keys_info}\n\n"
                        f"Envoyez une *nouvelle clé* pour l'ajouter à la liste.\n"
                        f"_(bascule automatique si une clé est épuisée)_\n\n"
                        f"🔗 {urls.get(provider,'')}")

            elif data == "stats":
                await event.edit(text_stats(), buttons=[
                    [Button.inline("🔄 Actualiser", b"stats")],
                    [Button.inline("🔙 Menu", b"mm")],
                ])

            elif data == "prm":
                await event.edit("⚙️ *Paramètres*", buttons=mk_prm_menu())
            elif data == "prm_d":
                state["param_waiting"] = "delay"
                await event.edit(
                    f"⏱ *Délai absence actuel : {config['delay_seconds']}s*\n\n"
                    f"Envoyez le nouveau délai en secondes (ex: `30`) :")
            elif data == "prm_r":
                state["param_waiting"] = "replydelay"
                await event.edit(
                    f"⚡ *Délai réponse actuel : {config.get('reply_delay_seconds',5)}s*\n\n"
                    f"Envoyez le nouveau délai en secondes (ex: `5`) :")
            elif data == "prm_q":
                state["param_waiting"] = "quota"
                await event.edit(
                    f"🔢 *Quota actuel : {config['daily_quota']}/jour*\n"
                    f"Utilisé aujourd'hui : {config['quota_used_today']}\n\n"
                    f"Envoyez le nouveau quota (ex: `200`) :")
            elif data == "prm_k":
                kb = config["knowledge_base"]
                lines = [f"📚 *Base de connaissances ({len(kb)} entrées)*\n"]
                for i, x in enumerate(kb, 1):
                    lines.append(f"{i}. {x}")
                await event.edit("\n".join(lines), buttons=[
                    [Button.inline("➕ Ajouter", b"prm_ka"),
                     Button.inline("⚙️ Paramètres", b"prm")],
                    [Button.inline("🔙 Menu", b"mm")],
                ])
            elif data == "prm_ka":
                state["param_waiting"] = "addinfo"
                await event.edit("➕ *Ajouter une information*\n\nTapez l'info à ajouter :")
            elif data == "prm_kv":
                kb = config["knowledge_base"]
                lines = [f"📚 *Base de connaissances*\n"]
                for i, x in enumerate(kb, 1):
                    lines.append(f"`/removeinfo {i}` — {x[:80]}")
                await event.edit("\n".join(lines), buttons=[[Button.inline("🔙 Paramètres", b"prm")]])

        # ── Commandes textuelles ───────────────────────────────────────────────

        @client.on(events.NewMessage(outgoing=True, pattern=r"^/menu(\s|$)"))
        async def cmd_menu(event):
            if config.get("auto_reply_enabled", True):
                await event.respond(
                    mk_active_bot_panel(),
                    buttons=[[Button.inline("🔵   ⏹  STOP — Reprendre la main  ⏹   🔵", b"feu_vert_toggle")]])
            else:
                await event.respond(
                    f"🏠 *Menu Principal — {config.get('user_name','Mon Bot')}*\n\n"
                    f"🕐 {benin_time()} (heure Bénin)\n"
                    f"Furtif : {'🕵️' if config.get('stealth_mode',True) else '🔵'}\n\n"
                    f"Choisissez une section :", buttons=mk_main_menu())

        @client.on(events.NewMessage(outgoing=True, pattern=r"^/orgdone\s+(\d+)$"))
        async def cmd_orgdone(event):
            idx = int(event.pattern_match.group(1)) - 1
            pending = [r for r in config["requests"] if r["status"]=="pending"]
            if not (0 <= idx < len(pending)):
                await event.respond(f"❌ Numéro invalide (1 à {len(pending)})"); return
            pending[idx]["status"] = "done"
            save_config(config)
            await event.respond(f"✅ Marqué comme traité :\n_{pending[idx]['summary']}_")

        @client.on(events.NewMessage(outgoing=True, pattern=r"^/stop(\s|$)"))
        async def cmd_stop(event):
            args = (event.text or "").strip().split()[1:]
            if args and args[0].lstrip("-").isdigit():
                stopped_chats.add(int(args[0]))
                await event.respond(f"🛑 Auto-réponse arrêtée pour `{args[0]}`")
            else:
                config["auto_reply_enabled"] = False; save_config(config)
                await event.respond("🛑 Auto-réponse *désactivée*.\n`/resume` pour réactiver.")

        @client.on(events.NewMessage(outgoing=True, pattern=r"^/resume(\s|$)"))
        async def cmd_resume(event):
            args = (event.text or "").strip().split()[1:]
            if args and args[0].lstrip("-").isdigit():
                stopped_chats.discard(int(args[0]))
                await event.respond(f"✅ Auto-réponse réactivée pour `{args[0]}`")
            else:
                config["auto_reply_enabled"] = True; save_config(config)
                stopped_chats.clear()
                await event.respond("✅ Auto-réponse *réactivée*.")

        @client.on(events.NewMessage(outgoing=True, pattern=r"^/donenote\s+(\d+)$"))
        async def cmd_donenote(event):
            idx = int(event.pattern_match.group(1)) - 1
            rems = config.get("reminders", [])
            if not (0 <= idx < len(rems)):
                await event.respond(f"❌ Invalide (1 à {len(rems)})"); return
            rems[idx]["notified"] = True; save_config(config)
            await event.respond(f"✅ Fait : _{rems[idx].get('text','?')}_")

        @client.on(events.NewMessage(outgoing=True, pattern=r"^/deletenote\s+(\d+)$"))
        async def cmd_deletenote(event):
            idx = int(event.pattern_match.group(1)) - 1
            rems = config.get("reminders", [])
            if not (0 <= idx < len(rems)):
                await event.respond(f"❌ Invalide (1 à {len(rems)})"); return
            removed = rems.pop(idx); save_config(config)
            await event.respond(f"✅ Supprimé : _{removed.get('text','?')}_")

        @client.on(events.NewMessage(outgoing=True, pattern=r"^/removeinfo\s+(\d+)$"))
        async def cmd_removeinfo(event):
            idx = int(event.pattern_match.group(1)) - 1
            kb  = config["knowledge_base"]
            if not (0 <= idx < len(kb)):
                await event.respond(f"❌ Invalide (1 à {len(kb)})"); return
            removed = kb.pop(idx); save_config(config)
            await event.respond(f"✅ Supprimé : _{removed}_")

        @client.on(events.NewMessage(outgoing=True, pattern=r"^/help(\s|$)"))
        async def cmd_help(event):
            await event.respond(
                "🛠 *Commandes — Tapez /menu pour les boutons*\n\n"
                "📋 *Organisation :*\n"
                "• `/orgdone <n>` — Marquer demande comme traitée\n\n"
                "📝 *Secrétariat & Rappels :*\n"
                "• `/donenote <n>` — Marquer rappel fait\n"
                "• `/deletenote <n>` — Supprimer rappel\n\n"
                "🔄 *Auto-réponse :*\n"
                "• `/stop` / `/resume` — Global\n"
                "• `/stop <chat_id>` / `/resume <chat_id>` — Par chat\n\n"
                "📚 *Base de connaissances :*\n"
                "• `/removeinfo <n>` — Supprimer une info\n\n"
                "🏠 `/menu` — Menu principal avec boutons")

        # ═══════════════════════════════════════════════════════════════════════
        #  BOT DE CONTRÔLE (chat privé du bot Telegram)
        # ═══════════════════════════════════════════════════════════════════════

        # Vérifie si une autre instance (déploiement) monopolise déjà le token
        def _bot_token_free(token: str) -> bool:
            """Retourne True si le token est disponible (aucun autre polling actif)."""
            try:
                import urllib.request as _ur, json as _js
                req = _ur.Request(
                    f"https://api.telegram.org/bot{token}/getUpdates?timeout=0&limit=1",
                    headers={"Content-Type": "application/json"}, method="GET")
                with _ur.urlopen(req, timeout=8) as r:
                    return True   # 200 OK → token libre
            except Exception as e:
                if "409" in str(e) or "Conflict" in str(e):
                    return False  # token déjà utilisé par le déploiement
                return True       # autre erreur → on tente quand même

        # Si une instance déployée occupe déjà le token, on désactive le bot de contrôle
        # local pour éviter les conflits 409 permanents. Le userbot Telethon reste actif.
        _effective_bot_token = BOT_TOKEN
        if BOT_TOKEN and not _bot_token_free(BOT_TOKEN):
            logger.warning(
                "⚠️ Bot de contrôle ignoré : une instance déployée est déjà active "
                "(token occupé). Le userbot Telethon reste pleinement fonctionnel."
            )
            _ctrl_active[0] = False
            _effective_bot_token = ""

        if _effective_bot_token:
            from telegram import (Update as _U, InlineKeyboardButton as _IKB,
                                  InlineKeyboardMarkup as _IKM)
            from telegram.ext import (Application as _App, CommandHandler as _CH,
                                      MessageHandler as _MH, filters as _F,
                                      ContextTypes as _CT, CallbackQueryHandler as _CQH)

            ctrl = _App.builder().token(BOT_TOKEN).build()
            ctrl_state: dict = {}        # {user_id: {step, data}}
            admin_chat_mode  = [False]   # True = mode discussion avec l'assistante
            admin_chat_hist  = []        # historique de la discussion admin-assistante

            def _owner(fn):
                async def w(update: _U, context: _CT.DEFAULT_TYPE):
                    if update.effective_user and update.effective_user.id == OWNER_ID:
                        await fn(update, context)
                return w

            # ── Générateurs de claviers pour le control bot ───────────────────

            def bk_active_bot():
                return _IKM([[_IKB("🔵   ⏹  STOP — Reprendre la main  ⏹   🔵",
                                   callback_data="feu_vert_toggle")]])

            def bk_main():
                _uid = CURRENT_UID[0]
                _acm = get_ctx(_uid)["admin_chat_mode"] if _uid else [False]
                if away_mode[0]:
                    nb_away  = len(away_log)
                    away_btn = _IKB(f"✅ Mode absent actif — {nb_away} conv(s) — DÉSACTIVER",
                                    callback_data="away_toggle")
                else:
                    away_btn = _IKB("📵  Mode absent  (bot prend le contrôle total)",
                                    callback_data="away_toggle")
                nb_strats    = len(config.get("baccara_strategies", []))
                nb_consignes = len(config.get("consignes", []))
                custom_btns  = config.get("custom_buttons", [])
                nb_cbtns     = len(custom_btns)
                chat_lbl = "🟢 Discuter avec l'assistante — ACTIF (envoie un msg)" \
                           if _acm[0] else "💬 Discuter avec l'assistante"
                rows = [
                    [_IKB("🤖  ▶️  Répond à ma place  ◀️  🤖", callback_data="feu_vert_toggle")],
                    [_IKB(f"📌  Consignes  ({nb_consignes})", callback_data="consignes"),
                     _IKB("📝  Secrétariat", callback_data="sec")],
                    [_IKB("📅  Programme", callback_data="prog"),
                     _IKB("🤖  Fournisseurs IA", callback_data="ai")],
                    [_IKB(f"🎲  Baccara  ({nb_strats})", callback_data="strat"),
                     _IKB("⚙️  Paramètres", callback_data="prm")],
                    [_IKB(f"🎛  Mes boutons  ({nb_cbtns})", callback_data="cbtns"),
                     _IKB("📊  Stats & Statut", callback_data="stats")],
                ]
                # Boutons personnalisés affichés directement sur l'accueil
                if custom_btns:
                    for b in custom_btns:
                        rows.append([_IKB(f"🔘  {b['name']}", callback_data=f"cbtnshow_{b['id']}")])
                rows += [
                    [away_btn],
                    [_IKB("🎤  Transcrire un audio en texte", callback_data="transcribe_help")],
                    [_IKB(chat_lbl, callback_data="admin_chat_toggle")],
                    [_IKB("📬  Quoi de neuf ?", callback_data="quoi_de_neuf")],
                    [_IKB("➕  Ajouter à un groupe/canal", callback_data="add_to_group")],
                ]
                if _uid == SUPER_ADMIN_ID:
                    rows.append([_IKB("👑  Admin — Gérer les utilisateurs", callback_data="admin_panel")])
                return _IKM(rows)

            def bk_org():
                p = sum(1 for r in config["requests"] if r["status"]=="pending")
                d = sum(1 for r in config["requests"] if r["status"]=="done")
                return _IKM([
                    [_IKB(f"⏳ En attente ({p})", callback_data="org_p"),
                     _IKB(f"✅ Traitées ({d})",   callback_data="org_d")],
                    [_IKB("💡 Analyser & Proposer", callback_data="org_a"),
                     _IKB("🗑 Vider traitées",       callback_data="org_c")],
                    [_IKB("🔙 Menu",                callback_data="mm")],
                ])

            def bk_sec():
                # Toujours lire les données fraîches depuis le disque
                _uid_now  = CURRENT_UID[0]
                _live_sec = load_uc_sec(_uid_now) if _uid_now else sec_log
                total     = sum(len(v.get("msgs", [])) for v in _live_sec.values())
                contacts  = len(_live_sec)
                nb_audio  = sum(
                    1 for v in _live_sec.values()
                    for m in v.get("msgs", []) if m.get("audio"))
                return _IKM([
                    [_IKB(f"📚 Conversations ({contacts} contacts)", callback_data="sec_c")],
                    [_IKB(f"🎤 Transcriptions audio  ({nb_audio})", callback_data="sec_audio")],
                    [_IKB("💡 Analyser & Proposer solutions",        callback_data="sec_a")],
                    [_IKB("📋 Résumé du jour (IA)",                  callback_data="sec_r")],
                    [_IKB("📝 Rappels",                              callback_data="rem")],
                    [_IKB("🗑 Tout effacer (RAZ)",                   callback_data="sec_wipe")],
                    [_IKB("➕ Ajouter rappel manuel",                callback_data="rem_a"),
                     _IKB("🔙 Menu",                                 callback_data="mm")],
                ])

            def bk_prog():
                progs = config.get("daily_program", [])
                return _IKM([
                    [_IKB(f"📅 Voir programme ({len(progs)} tâches)", callback_data="prog_v")],
                    [_IKB("➕ Ajouter une tâche", callback_data="prog_a"),
                     _IKB("🗑 Vider",              callback_data="prog_c")],
                    [_IKB("🔙 Menu",               callback_data="mm")],
                ])

            def bk_ai():
                providers = config["ai_providers"]
                active    = config.get("active_ai","groq")
                stealth   = "🕵️ Furtif : ON" if config.get("stealth_mode",True) else "👁 Furtif : OFF"
                auto      = "✅ Auto : ON" if config.get("auto_reply_enabled",True) else "🛑 Auto : OFF"
                rows = []
                for i, k in enumerate(AI_LIST, 1):
                    d         = providers.get(k, {})
                    keys_list = [x for x in d.get("keys", []) if x]
                    n_keys    = len(keys_list)
                    has_key   = n_keys > 0
                    is_act    = k == active
                    icon      = "🔵" if is_act else ("✅" if has_key else "❌")
                    name_short = AI_META[k]["name"].split("—")[0].strip()
                    badge      = f" ({n_keys}🔑)" if n_keys > 1 else ""
                    rows.append([_IKB(f"{icon} {i}. {name_short}{badge}", callback_data=f"ai_{k}")])
                rows.append([_IKB(stealth, callback_data="ai_st"),
                             _IKB(auto,    callback_data="ai_auto")])
                rows.append([_IKB("🔙 Menu", callback_data="mm")])
                return _IKM(rows)

            def bk_prm():
                d  = config["delay_seconds"]
                rd = config.get("reply_delay_seconds",5)
                q  = config["daily_quota"]
                qu = config["quota_used_today"]
                return _IKM([
                    [_IKB(f"⏱ Délai absence : {d}s", callback_data="prm_d"),
                     _IKB(f"⚡ Délai réponse : {rd}s", callback_data="prm_r")],
                    [_IKB(f"🔢 Quota : {qu}/{q}/j",    callback_data="prm_q")],
                    [_IKB("📚 Base de connaissances",   callback_data="prm_k")],
                    [_IKB("➕ Ajouter info",  callback_data="prm_ka"),
                     _IKB("📝 Voir & suppr.", callback_data="prm_kv")],
                    [_IKB("🔙 Menu",          callback_data="mm")],
                ])

            def bk_strat():
                strats = config.get("baccara_strategies", [])
                return _IKM([
                    [_IKB(f"📋 Voir les {len(strats)} stratégie(s)", callback_data="strat_v")],
                    [_IKB("➕ Ajouter une stratégie",                 callback_data="strat_a")],
                    [_IKB("🔙 Menu",                                  callback_data="mm")],
                ])

            def bk_consignes():
                nb = len(config.get("consignes", []))
                return _IKM([
                    [_IKB(f"📋 Voir les {nb} consigne(s)", callback_data="consignes_v")],
                    [_IKB("➕ Ajouter une consigne",       callback_data="consignes_a")],
                    [_IKB("🗑 Tout effacer",               callback_data="consignes_wipe")],
                    [_IKB("🔙 Menu",                       callback_data="mm")],
                ])

            def bk_cbtns():
                btns = config.get("custom_buttons", [])
                rows = []
                for b in btns:
                    rows.append([
                        _IKB(f"✏️ {b['name']}", callback_data=f"cbtnedit_{b['id']}"),
                        _IKB("🗑",              callback_data=f"cbtndelete_{b['id']}"),
                    ])
                if not btns:
                    rows.append([_IKB("_(aucun bouton)_", callback_data="noop")])
                rows.append([_IKB("➕ Ajouter un nouveau bouton", callback_data="cbtnadd")])
                rows.append([_IKB("🔙 Menu", callback_data="mm")])
                return _IKM(rows)

            # ── Wizard d'inscription multi-utilisateur ────────────────────────

            async def _send_reg_step(msg, uid):
                step = _REG_STATE.get(uid, {}).get("step", "ask_api_hash")
                if step == "ask_api_hash":
                    await msg.reply_text(
                        "👋 *Bienvenue sur la plateforme d'auto-réponse personnelle !*\n\n"
                        "Pour configurer votre bot auto-répondeur personnel, j'ai besoin "
                        "de vos identifiants Telegram.\n\n"
                        "📋 *Étape 1/4 — API Hash*\n\n"
                        "🔗 Rendez-vous sur : https://my.telegram.org/apps\n"
                        "Créez une application et copiez votre *api\\_hash* :",
                        parse_mode="Markdown")

            async def _handle_reg_wizard(update, uid, text, context):
                state = _REG_STATE.get(uid)
                if not state:
                    return
                step = state.get("step", "ask_api_hash")

                if step == "ask_api_hash":
                    if len(text.strip()) < 8:
                        await update.message.reply_text(
                            "❌ API Hash invalide (trop court). Réessayez.", parse_mode="Markdown")
                        return
                    state["api_hash"] = text.strip()
                    state["step"] = "ask_api_id"
                    await update.message.reply_text(
                        "✅ *API Hash enregistré !*\n\n"
                        "📋 *Étape 2/4 — API ID*\n\n"
                        "C'est un nombre entier (ex: `12345678`).\n"
                        "Copiez votre *api\\_id* et envoyez-le :",
                        parse_mode="Markdown")

                elif step == "ask_api_id":
                    if not text.strip().isdigit():
                        await update.message.reply_text(
                            "❌ L'API ID doit être un nombre entier. Réessayez.")
                        return
                    state["api_id"] = text.strip()
                    state["step"] = "ask_phone"
                    await update.message.reply_text(
                        "✅ *API ID enregistré !*\n\n"
                        "📋 *Étape 3/4 — Numéro de téléphone*\n\n"
                        "Envoyez votre numéro Telegram avec l'indicatif pays :\n"
                        "Exemple : `+22995501564`",
                        parse_mode="Markdown")

                elif step == "ask_phone":
                    phone = text.strip()
                    if not phone.startswith("+"):
                        phone = "+" + phone
                    await update.message.reply_text(
                        f"📤 Connexion à Telegram avec *{phone}*...", parse_mode="Markdown")
                    try:
                        from telethon import TelegramClient as _TC2
                        from telethon.sessions import StringSession as _SS2
                        cl2 = _TC2(_SS2(), int(state["api_id"]), state["api_hash"])
                        await cl2.connect()
                        result = await cl2.send_code_request(phone)
                        state["client"] = cl2
                        state["phone"]  = phone
                        state["pch"]    = result.phone_code_hash
                        state["step"]   = "ask_code"
                        await update.message.reply_text(
                            "✅ *Code envoyé !*\n\n"
                            "📋 *Étape 4/4 — Code de vérification*\n\n"
                            "Entrez le code reçu sur Telegram avec le préfixe `aa` :\n"
                            "Exemple : `aa12345`",
                            parse_mode="Markdown")
                    except Exception as e:
                        _REG_STATE.pop(uid, None)
                        await update.message.reply_text(
                            f"❌ *Erreur de connexion :* `{e}`\n\n"
                            "Vérifiez vos API\\_ID et API\\_HASH, puis recommencez avec /start",
                            parse_mode="Markdown")

                elif step == "ask_code":
                    if not text.strip().lower().startswith("aa"):
                        await update.message.reply_text(
                            "❌ Préfixe `aa` requis.\nExemple : `aa12345`", parse_mode="Markdown")
                        return
                    code = text.strip()[2:].strip()
                    cl2 = state["client"]
                    try:
                        from telethon.errors import SessionPasswordNeededError as _SPNE
                        await cl2.sign_in(state["phone"], code=code,
                                          phone_code_hash=state["pch"])
                        await _finish_registration(update, uid, cl2, state, context)
                    except _SPNE:
                        state["step"] = "ask_2fa"
                        await update.message.reply_text(
                            "🔐 *Vérification en 2 étapes activée*\n\n"
                            "Envoyez votre mot de passe avec le préfixe `pass ` :\n"
                            "Exemple : `pass MonMotDePasse`",
                            parse_mode="Markdown")
                    except Exception as e:
                        await update.message.reply_text(
                            f"❌ Code invalide : `{e}`\n\nRéessayez.", parse_mode="Markdown")

                elif step == "ask_2fa":
                    if not text.strip().lower().startswith("pass "):
                        await update.message.reply_text(
                            "❌ Format requis : `pass votre_mot_de_passe`", parse_mode="Markdown")
                        return
                    password = text.strip()[5:].strip()
                    cl2 = state["client"]
                    try:
                        await cl2.sign_in(password=password)
                        await _finish_registration(update, uid, cl2, state, context)
                    except Exception as e:
                        await update.message.reply_text(
                            f"❌ Mot de passe incorrect : `{e}`\n\nRéessayez.",
                            parse_mode="Markdown")

            async def _finish_registration(update, uid, cl2, state, context):
                from telethon.sessions import StringSession as _SS3
                ss = cl2.session.save()
                try:
                    me = await cl2.get_me()
                except Exception:
                    me = None
                await cl2.disconnect()
                _REG_STATE.pop(uid, None)

                users = load_users()
                users[str(uid)] = {
                    "api_id":      state["api_id"],
                    "api_hash":    state["api_hash"],
                    "session":     ss,
                    "phone":       state.get("phone", ""),
                    "tg_username": getattr(me, "username", "") or "",
                    "tg_name":     getattr(me, "first_name", "") or str(uid),
                    "tg_id":       getattr(me, "id", uid),
                    "blocked":     False,
                    "registered_at": benin_str(),
                }
                save_users(users)
                _uc_init = load_uc_config(uid)
                _uc_init["user_name"]     = getattr(me, "first_name", "") or str(uid)
                _uc_init["user_username"] = getattr(me, "username", "") or ""
                save_uc_config(uid, _uc_init)
                get_ctx(uid)

                name = getattr(me, "first_name", str(uid))
                uname = getattr(me, "username", "")
                await update.message.reply_text(
                    f"✅ *INSCRIPTION RÉUSSIE !*\n\n"
                    f"👤 Connecté en tant que : *{name}*"
                    f"{' (@' + uname + ')' if uname else ''}\n\n"
                    f"🔑 *Votre session (sauvegardez-la !) :*",
                    parse_mode="Markdown")

                chunk_size = 3000
                for i in range(0, len(ss), chunk_size):
                    part = ss[i:i + chunk_size]
                    num  = (i // chunk_size) + 1
                    tot  = (len(ss) + chunk_size - 1) // chunk_size
                    lbl  = f"*Partie {num}/{tot}*:\n`{part}`" if tot > 1 else f"`{part}`"
                    await update.message.reply_text(lbl, parse_mode="Markdown")

                asyncio.ensure_future(_run_user_telethon(uid))
                await asyncio.sleep(2)
                _switch_user_ctx(uid)

                # ── Message de bienvenue personnalisé ──────────────────────────
                prenom = (getattr(me, "first_name", "") or name or str(uid)).split()[0]
                await context.bot.send_message(
                    chat_id=uid,
                    text=(
                        f"👋 *Bienvenue, {prenom} !*\n\n"
                        f"Je suis ton assistante intelligente — je vais répondre à ta place "
                        f"dans tes conversations Telegram, apprendre ton style et gérer tes contacts.\n\n"
                        f"⚡ *Pour que je fonctionne, j'ai besoin d'une clé IA.*\n\n"
                        f"Voici comment faire :\n"
                        f"1️⃣ Appuie sur *🤖 Fournisseurs IA* dans le menu ci-dessous\n"
                        f"2️⃣ Choisis un fournisseur (Groq, OpenAI, Gemini…)\n"
                        f"3️⃣ Colle ta clé API — c'est gratuit chez la plupart !\n\n"
                        f"_Sans clé IA je ne peux pas répondre à tes contacts._ 🙏"
                    ),
                    parse_mode="Markdown")
                await asyncio.sleep(1)
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"🏠 *Menu Principal*\n\n🕐 {benin_time()} (heure Bénin)",
                    reply_markup=bk_main(),
                    parse_mode="Markdown")

            # ── /start & /menu ────────────────────────────────────────────────

            async def bc_start(update: _U, context: _CT.DEFAULT_TYPE):
                uid = update.effective_user.id

                if uid in _REG_STATE:
                    await _send_reg_step(update.message, uid)
                    return

                if not user_registered(uid):
                    _REG_STATE[uid] = {"step": "ask_api_hash"}
                    await _send_reg_step(update.message, uid)
                    return

                if user_blocked(uid):
                    await update.message.reply_text(
                        "🚫 Votre accès a été bloqué par l'administrateur.")
                    return

                _switch_user_ctx(uid)
                _uname_start = config.get("user_name", "") or "Mon Bot"
                if config.get("auto_reply_enabled", True):
                    await update.message.reply_text(
                        mk_active_bot_panel(),
                        reply_markup=bk_active_bot(), parse_mode="Markdown")
                else:
                    await update.message.reply_text(
                        f"🏠 *Menu Principal — {_uname_start}*\n\n"
                        f"🕐 {benin_time()} (heure Bénin)\n"
                        f"Mode furtif : {'🕵️ ON' if config.get('stealth_mode',True) else '🔵 OFF'}\n\n"
                        f"Choisissez une section :\n\n"
                        f"_{DEV_SIGNATURE}_",
                        reply_markup=bk_main(), parse_mode="Markdown")

            # ── Callbacks control bot ─────────────────────────────────────────

            async def bc_cb(update: _U, context: _CT.DEFAULT_TYPE):
                q = update.callback_query
                await q.answer()
                uid = q.from_user.id
                d   = q.data

                if not user_registered(uid):
                    try:
                        await q.edit_message_text(
                            "❌ Vous n'êtes pas enregistré.\nEnvoyez /start pour vous inscrire.")
                    except Exception:
                        pass
                    return
                if user_blocked(uid):
                    try:
                        await q.edit_message_text("🚫 Votre accès a été bloqué.")
                    except Exception:
                        pass
                    return

                _switch_user_ctx(uid)
                _ctx = get_ctx(uid)
                _acm = _ctx["admin_chat_mode"]
                _ach = _ctx["admin_chat_hist"]

                async def edit(text, kb=None):
                    try:
                        await q.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
                    except Exception:
                        pass

                if d == "noop":
                    return

                # ── Panneau Admin (SUPER_ADMIN seulement) ──────────────────────
                if uid == SUPER_ADMIN_ID and d == "admin_panel":
                    users = load_users()
                    if not users:
                        await edit(
                            "👑 *Panneau Admin*\n\nAucun utilisateur enregistré.",
                            _IKM([[_IKB("🔙 Menu", callback_data="mm")]]))
                        return
                    lines = ["👑 *Panneau Admin — Utilisateurs*\n"]
                    rows  = []
                    for u_id, u_data in users.items():
                        name    = u_data.get("tg_name", "?")
                        phone   = u_data.get("phone", "?")
                        status  = "🔴 Bloqué" if u_data.get("blocked") else "🟢 Actif"
                        reg_at  = u_data.get("registered_at", "")
                        lines.append(f"• `{u_id}` — {name} ({phone}) — {status}\n  📅 {reg_at}")
                        if u_data.get("blocked"):
                            rows.append([_IKB(f"🟢 Débloquer {name}", callback_data=f"admin_unblock_{u_id}")])
                        else:
                            rows.append([_IKB(f"🔴 Bloquer {name}", callback_data=f"admin_block_{u_id}")])
                    rows.append([_IKB("🔙 Menu", callback_data="mm")])
                    await edit("\n".join(lines)[:4000], _IKM(rows))
                    return

                if uid == SUPER_ADMIN_ID and d.startswith("admin_block_"):
                    target = d.replace("admin_block_", "")
                    if int(target) == SUPER_ADMIN_ID:
                        await edit("⚠️ Impossible de bloquer l'administrateur principal.",
                                   _IKM([[_IKB("🔙 Admin", callback_data="admin_panel")]]))
                        return
                    users = load_users()
                    if target in users:
                        users[target]["blocked"] = True
                        save_users(users)
                        tc = _USER_TELETHON.pop(target, None)
                        if tc:
                            try:
                                await tc.disconnect()
                            except Exception:
                                pass
                        try:
                            await context.bot.send_message(
                                int(target),
                                "🚫 *Votre accès a été suspendu.*\n\n"
                                "Pour toute réclamation, veuillez écrire à l'administrateur.\n\n"
                                f"_{DEV_SIGNATURE}_",
                                parse_mode="Markdown")
                        except Exception:
                            pass
                    await edit(f"🔴 Utilisateur `{target}` bloqué.",
                               _IKM([[_IKB("🔙 Admin", callback_data="admin_panel")]]))
                    return

                if uid == SUPER_ADMIN_ID and d.startswith("admin_unblock_"):
                    target = d.replace("admin_unblock_", "")
                    users = load_users()
                    if target in users:
                        users[target]["blocked"] = False
                        save_users(users)
                        asyncio.ensure_future(_run_user_telethon(int(target)))
                    await edit(f"🟢 Utilisateur `{target}` débloqué.",
                               _IKM([[_IKB("🔙 Admin", callback_data="admin_panel")]]))
                    return

                # ── Gestion groupes/canaux ─────────────────────────────────────
                if d == "add_to_group":
                    grp_cfgs = load_grp_configs(uid)
                    rows = []
                    if grp_cfgs:
                        for cid_str, gcfg in grp_cfgs.items():
                            title   = gcfg.get("title", cid_str)
                            roles   = gcfg.get("roles", [])
                            rl_icon = "📢" if "pub" in roles else ""
                            rl_icon += "💬" if "discuter" in roles else ""
                            rl_icon += "📣" if "com" in roles else ""
                            paused  = gcfg.get("paused", False)
                            st_icon = "⏸" if paused else "▶️"
                            rows.append([_IKB(f"{st_icon} {rl_icon} {title[:25]}", callback_data=f"grp_view_{cid_str}")])
                    rows.append([_IKB("➕ Nouveau groupe / canal", callback_data="grp_new")])
                    rows.append([_IKB("🔙 Menu", callback_data="mm")])
                    txt = (f"📡 *Mes groupes & canaux configurés*\n\n"
                           f"{'Aucun groupe configuré pour l\'instant.\n\n' if not grp_cfgs else ''}"
                           f"Appuyez sur un groupe pour le gérer, ou ajoutez-en un nouveau.")
                    await edit(txt, _IKM(rows))
                    return

                if d == "grp_new":
                    ctrl_state[uid] = {"step": "grp_chatid"}
                    await edit(
                        "➕ *Nouveau groupe / canal*\n\n"
                        "Envoyez l'*ID* ou le *@username* du groupe/canal.\n\n"
                        "_Comment trouver l'ID ? Ajoutez @userinfobot dans votre groupe, "
                        "il vous affichera l'ID négatif (ex: -1001234567890)_\n\n"
                        "Ou envoyez simplement `@mongroupe` si le groupe est public.",
                        _IKM([[_IKB("🔙 Retour", callback_data="add_to_group")]]))
                    return

                if d.startswith("grp_view_"):
                    cid_str  = d.replace("grp_view_", "")
                    grp_cfgs = load_grp_configs(uid)
                    gcfg     = grp_cfgs.get(cid_str, {})
                    if not gcfg:
                        await edit("❌ Groupe introuvable.", _IKM([[_IKB("🔙", callback_data="add_to_group")]]))
                        return
                    roles   = gcfg.get("roles", [])
                    paused  = gcfg.get("paused", False)
                    role_txt = []
                    if "pub" in roles:
                        role_txt.append(f"📢 Publicité — toutes les {gcfg.get('pub_interval_minutes', 120)} min")
                    if "discuter" in roles:
                        role_txt.append("💬 Discussion — répond aux membres")
                    if "com" in roles:
                        role_txt.append(f"📣 Communication — toutes les {gcfg.get('com_interval_minutes', 60)} min")
                    bilan  = gcfg.get("bilan", {})
                    nb_lu  = bilan.get("msgs_appris", 0)
                    nb_env = bilan.get("msgs_envoyes", 0)
                    rows   = [
                        [_IKB("⏸ Mettre en pause" if not paused else "▶️ Reprendre",
                               callback_data=f"grp_pause_{cid_str}")],
                        [_IKB("📊 Bilan IA du groupe", callback_data=f"grp_bilan_{cid_str}")],
                        [_IKB("🗑 Supprimer ce groupe", callback_data=f"grp_del_{cid_str}")],
                        [_IKB("🔙 Retour", callback_data="add_to_group")],
                    ]
                    await edit(
                        f"📡 *{gcfg.get('title', cid_str)}*\n\n"
                        f"🆔 ID : `{cid_str}`\n"
                        f"🎭 Rôles actifs :\n" + "\n".join(f"  • {r}" for r in role_txt) + "\n\n"
                        f"📚 Appris : {nb_lu} messages\n"
                        f"📤 Envoyés : {nb_env} messages\n"
                        f"{'⏸ En pause' if paused else '▶️ Actif'}",
                        _IKM(rows))
                    return

                if d.startswith("grp_pause_"):
                    cid_str  = d.replace("grp_pause_", "")
                    grp_cfgs = load_grp_configs(uid)
                    if cid_str in grp_cfgs:
                        grp_cfgs[cid_str]["paused"] = not grp_cfgs[cid_str].get("paused", False)
                        save_grp_configs(uid, grp_cfgs)
                        st = "⏸ mise en pause" if grp_cfgs[cid_str]["paused"] else "▶️ reprise"
                        await edit(f"✅ Configuration {st}.", _IKM([[_IKB("🔙", callback_data=f"grp_view_{cid_str}")]]))
                    return

                if d.startswith("grp_del_"):
                    cid_str  = d.replace("grp_del_", "")
                    grp_cfgs = load_grp_configs(uid)
                    grp_cfgs.pop(cid_str, None)
                    save_grp_configs(uid, grp_cfgs)
                    # Annuler les tâches planifiées
                    tasks = _GROUP_TASKS.get(str(uid), {})
                    for role in ("pub", "com"):
                        t = tasks.pop(f"{cid_str}_{role}", None)
                        if t:
                            t.cancel()
                    await edit("🗑 Groupe supprimé.", _IKM([[_IKB("🔙", callback_data="add_to_group")]]))
                    return

                if d.startswith("grp_bilan_"):
                    cid_str  = d.replace("grp_bilan_", "")
                    grp_cfgs = load_grp_configs(uid)
                    gcfg     = grp_cfgs.get(cid_str, {})
                    if not gcfg:
                        await edit("❌ Groupe introuvable.", _IKM([[_IKB("🔙", callback_data="add_to_group")]]))
                        return
                    # Générer le bilan IA
                    grp_sec_key = f"grp_{cid_str}"
                    u_sec       = load_uc_sec(uid)
                    grp_msgs    = u_sec.get(grp_sec_key, {}).get("msgs", [])
                    if not grp_msgs:
                        await edit("📊 Aucun message appris dans ce groupe pour l'instant.",
                                   _IKM([[_IKB("🔙", callback_data=f"grp_view_{cid_str}")]]))
                        return
                    sample = grp_msgs[-50:]
                    txt_sample = "\n".join(f"[{m.get('d','')}] {m.get('a','?')}: {m.get('t','')[:80]}"
                                           for m in sample)
                    sys_bilan = (
                        "Tu es un assistant analytique. Analyse les messages suivants d'un groupe Telegram "
                        "et fournis un bilan structuré : 1) Thèmes principaux discutés, "
                        "2) Ambiance générale (ton, engagement), 3) Points importants à retenir, "
                        "4) Opportunités ou actions recommandées. Sois concis et utile. Réponds en français."
                    )
                    try:
                        bilan_rep = await smart_ai_call(sys_bilan,
                            [{"role": "user", "content": f"Messages du groupe:\n{txt_sample}"}])
                        await edit(f"📊 *Bilan IA — {gcfg.get('title', cid_str)}*\n\n{bilan_rep[:3500]}",
                                   _IKM([[_IKB("🔙", callback_data=f"grp_view_{cid_str}")]]))
                    except Exception as be:
                        await edit(f"❌ Erreur IA : {str(be)[:200]}",
                                   _IKM([[_IKB("🔙", callback_data=f"grp_view_{cid_str}")]]))
                    return

                # Sélection des rôles (wizard inline)
                if d.startswith("grp_role_toggle_"):
                    role     = d.replace("grp_role_toggle_", "")
                    st_grp   = ctrl_state.get(uid, {})
                    tmp      = st_grp.get("grp_tmp", {})
                    selected = tmp.get("roles_selected", [])
                    if role in selected:
                        selected.remove(role)
                    else:
                        if len(selected) < 2:
                            selected.append(role)
                        else:
                            await q.answer("⚠️ Maximum 2 rôles à la fois.", show_alert=True)
                            return
                    tmp["roles_selected"] = selected
                    ctrl_state[uid] = {**st_grp, "grp_tmp": tmp}
                    roles_map = {"pub": "📢 Publicité", "discuter": "💬 Discussion", "com": "📣 Communication"}
                    rows_r    = []
                    for rk, rl in roles_map.items():
                        chk = "✅ " if rk in selected else "⬜ "
                        rows_r.append([_IKB(f"{chk}{rl}", callback_data=f"grp_role_toggle_{rk}")])
                    rows_r.append([_IKB("✔️ Valider les rôles", callback_data="grp_roles_done")])
                    rows_r.append([_IKB("🔙 Annuler", callback_data="add_to_group")])
                    await edit(
                        f"🎭 *Choisissez les rôles* (max 2)\n\n"
                        f"• 📢 *Publicité* : Envoyer des publications à intervalles réguliers\n"
                        f"• 💬 *Discussion* : Répondre aux membres du groupe (IA)\n"
                        f"• 📣 *Communication* : Envoyer un message régulier\n\n"
                        f"Sélectionnés : {', '.join(roles_map[r] for r in selected) or 'aucun'}",
                        _IKM(rows_r))
                    return

                if d == "grp_roles_done":
                    st_grp   = ctrl_state.get(uid, {})
                    tmp      = st_grp.get("grp_tmp", {})
                    selected = tmp.get("roles_selected", [])
                    if not selected:
                        await q.answer("⚠️ Choisissez au moins un rôle.", show_alert=True)
                        return
                    tmp["roles_selected"] = selected
                    # Toujours demander les infos du groupe/canal d'abord
                    ctrl_state[uid] = {**st_grp, "step": "grp_info", "grp_tmp": tmp}
                    await edit(
                        "ℹ️ *Informations sur votre groupe/canal* _(facultatif)_\n\n"
                        "Décrivez brièvement le sujet ou l'objectif de ce groupe/canal.\n"
                        "L'IA utilisera ces informations pour mieux discuter avec vos membres.\n\n"
                        "_Ex : « Vente de vêtements féminins », « Fans de football », « Conseils business »_\n\n"
                        "Envoyez votre description ou appuyez sur *Ignorer*.",
                        _IKM([[_IKB("⏭ Ignorer", callback_data="grp_info_skip")],
                              [_IKB("🔙 Retour", callback_data="add_to_group")]]))
                    return

                if d == "grp_info_skip":
                    st_grp   = ctrl_state.get(uid, {})
                    tmp      = st_grp.get("grp_tmp", {})
                    selected = tmp.get("roles_selected", [])
                    tmp["group_info"] = ""
                    # Prochain step selon rôles
                    if "pub" in selected:
                        ctrl_state[uid] = {**st_grp, "step": "grp_pub_text", "grp_tmp": tmp}
                        await edit(
                            "📢 *Publicité — Texte de la publication*\n\n"
                            "Envoyez le texte que le bot doit publier dans le groupe/canal.\n"
                            "_Vous pouvez utiliser des emojis et du formatage Markdown._",
                            _IKM([[_IKB("🔙 Retour", callback_data="add_to_group")]]))
                    elif "com" in selected:
                        ctrl_state[uid] = {**st_grp, "step": "grp_com_text", "grp_tmp": tmp}
                        await edit(
                            "📣 *Communication — Message à envoyer*\n\n"
                            "Envoyez le message de communication régulier.",
                            _IKM([[_IKB("🔙 Retour", callback_data="add_to_group")]]))
                    else:
                        _grp_save_wizard(uid, tmp)
                        ctrl_state.pop(uid, None)
                        await edit(
                            f"✅ *Groupe configuré !*\n\n"
                            f"🆔 `{tmp.get('chat_id', '')}` — {tmp.get('title', '')}\n"
                            f"🎭 Rôle : 💬 Discussion (IA)\n\n"
                            f"Le bot va apprendre des échanges et répondre aux mentions.",
                            _IKM([[_IKB("📡 Mes groupes", callback_data="add_to_group")]]))
                        _trigger_grp_handlers(uid)
                    return

                # Skip media (pub)
                if d == "grp_pub_skip_media":
                    st_grp = ctrl_state.get(uid, {})
                    tmp    = st_grp.get("grp_tmp", {})
                    tmp["pub_media"] = ""
                    ctrl_state[uid]  = {**st_grp, "step": "grp_pub_interval", "grp_tmp": tmp}
                    await edit(
                        "⏱ *Intervalle de publication*\n\n"
                        "À quelle fréquence envoyer cette publication ?\n"
                        "_Ou tapez librement : `2h`, `30min`, `90`, `4h`_",
                        _IKM([
                            [_IKB("1 min",  callback_data="grp_int_1"),
                             _IKB("2 min",  callback_data="grp_int_2"),
                             _IKB("5 min",  callback_data="grp_int_5")],
                            [_IKB("10 min", callback_data="grp_int_10"),
                             _IKB("15 min", callback_data="grp_int_15"),
                             _IKB("30 min", callback_data="grp_int_30")],
                            [_IKB("1h",     callback_data="grp_int_60"),
                             _IKB("2h",     callback_data="grp_int_120"),
                             _IKB("6h",     callback_data="grp_int_360")],
                            [_IKB("12h",    callback_data="grp_int_720"),
                             _IKB("24h",    callback_data="grp_int_1440")],
                            [_IKB("🔙 Annuler", callback_data="add_to_group")],
                        ]))
                    return

                # Skip media (com)
                if d == "grp_com_skip_media":
                    st_grp = ctrl_state.get(uid, {})
                    tmp    = st_grp.get("grp_tmp", {})
                    tmp["com_media"] = ""
                    ctrl_state[uid]  = {**st_grp, "step": "grp_com_interval", "grp_tmp": tmp}
                    await edit(
                        "⏱ *Intervalle de communication*\n\n"
                        "À quelle fréquence envoyer ce message ?\n"
                        "_Ou tapez librement : `2h`, `30min`, `90`, `4h`_",
                        _IKM([
                            [_IKB("1 min",  callback_data="grp_int_com_1"),
                             _IKB("2 min",  callback_data="grp_int_com_2"),
                             _IKB("5 min",  callback_data="grp_int_com_5")],
                            [_IKB("10 min", callback_data="grp_int_com_10"),
                             _IKB("15 min", callback_data="grp_int_com_15"),
                             _IKB("30 min", callback_data="grp_int_com_30")],
                            [_IKB("1h",     callback_data="grp_int_com_60"),
                             _IKB("2h",     callback_data="grp_int_com_120"),
                             _IKB("6h",     callback_data="grp_int_com_360")],
                            [_IKB("12h",    callback_data="grp_int_com_720"),
                             _IKB("24h",    callback_data="grp_int_com_1440")],
                            [_IKB("🔙 Annuler", callback_data="add_to_group")],
                        ]))
                    return

                # Boutons d'intervalle rapide (pub + com)
                if d.startswith("grp_int_com_") or d.startswith("grp_int_"):
                    is_com  = d.startswith("grp_int_com_")
                    minutes = int(d.replace("grp_int_com_", "").replace("grp_int_", ""))
                    st_grp  = ctrl_state.get(uid, {})
                    tmp     = st_grp.get("grp_tmp", {})
                    if is_com:
                        tmp["com_interval_minutes"] = minutes
                        _grp_save_wizard(uid, tmp)
                        ctrl_state.pop(uid, None)
                        roles_disp = " + ".join(
                            {"pub": "📢 Publicité", "discuter": "💬 Discussion", "com": "📣 Communication"}.get(r, r)
                            for r in tmp.get("roles_selected", []))
                        await edit(
                            f"✅ *Groupe configuré !*\n\n"
                            f"📡 *{tmp.get('title', '')}*\n"
                            f"🎭 Rôles : {roles_disp}\n"
                            f"📣 Communication toutes les {minutes} min",
                            _IKM([[_IKB("📡 Mes groupes", callback_data="add_to_group")]]))
                        _trigger_grp_handlers(uid)
                    else:
                        tmp["pub_interval_minutes"] = minutes
                        if "com" in tmp.get("roles_selected", []):
                            ctrl_state[uid] = {**st_grp, "step": "grp_com_text", "grp_tmp": tmp}
                            await edit(
                                "📣 *Communication — Message à envoyer*\n\n"
                                "Envoyez le message de communication régulier.",
                                _IKM([[_IKB("🔙 Annuler", callback_data="add_to_group")]]))
                        else:
                            _grp_save_wizard(uid, tmp)
                            ctrl_state.pop(uid, None)
                            roles_disp = " + ".join(
                                {"pub": "📢 Publicité", "discuter": "💬 Discussion", "com": "📣 Communication"}.get(r, r)
                                for r in tmp.get("roles_selected", []))
                            await edit(
                                f"✅ *Groupe configuré !*\n\n"
                                f"📡 *{tmp.get('title', '')}*\n"
                                f"🎭 Rôles : {roles_disp}\n"
                                f"📢 Publication toutes les {minutes} min",
                                _IKM([[_IKB("📡 Mes groupes", callback_data="add_to_group")]]))
                            _trigger_grp_handlers(uid)
                    return

                if d == "feu_vert_toggle":
                    config["auto_reply_enabled"] = not config.get("auto_reply_enabled", True)
                    save_config(config)
                    if config["auto_reply_enabled"]:
                        stopped_chats.clear()
                        await edit(mk_active_bot_panel(), bk_active_bot())
                    else:
                        await edit(
                            "✅ *Bot mis en pause*\n\n"
                            "Le bot n'envoie plus de réponses automatiques.\n\n"
                            "⏳ Le menu apparaît dans 5 secondes...",
                            None)
                        _stop_msg = q.message
                        _stop_chat = q.message.chat_id
                        async def _ptb_show_menu_after_delay():
                            await asyncio.sleep(5)
                            try:
                                await _stop_msg.delete()
                            except Exception:
                                pass
                            await context.bot.send_message(
                                chat_id=_stop_chat,
                                text=f"🏠 *Menu Principal — {config.get('user_name','Mon Bot')}*\n\nChoisissez une section :",
                                reply_markup=bk_main(),
                                parse_mode="Markdown")
                        asyncio.ensure_future(_ptb_show_menu_after_delay())
                    return

                if d == "mm":
                    if config.get("auto_reply_enabled", True):
                        await edit(mk_active_bot_panel(), bk_active_bot())
                    else:
                        _uname_mm = config.get("user_name", "") or "Mon Bot"
                        await edit(f"🏠 *Menu Principal — {_uname_mm}*\n\n🕐 {benin_time()} (heure Bénin)", bk_main())
                elif d == "org":
                    await edit("📋 *Organisation* — Gestion des demandes clients", bk_org())
                elif d == "org_p":
                    await edit(text_org_pending(), bk_org())
                elif d == "org_d":
                    await edit(text_org_done(), bk_org())
                elif d == "org_a":
                    await edit("💡 Analyse en cours...", None)
                    result = await text_org_analyze()
                    await edit(result[:4000], bk_org())
                elif d == "org_c":
                    config["requests"] = [r for r in config["requests"] if r["status"]!="done"]
                    save_config(config)
                    await edit("✅ Demandes traitées supprimées.", bk_org())
                elif d == "sec":
                    t = sum(len(v["msgs"]) for v in sec_log.values())
                    await edit(f"📝 *Secrétariat*\n\n{len(sec_log)} contacts | {t} messages", bk_sec())
                elif d == "sec_c":
                    if not sec_log:
                        await edit("📚 Aucune conversation enregistrée.", bk_sec()); return
                    lines = ["📚 *Conversations du jour*\n"]
                    for uid2, dat in list(sec_log.items())[-10:]:
                        nb = len(dat["msgs"])
                        last = dat["msgs"][-1]["t"][:60] if dat["msgs"] else "—"
                        lines.append(f"👤 *{dat['name']}* ({nb} msgs)\n_{last}_\n")
                    await edit("\n".join(lines)[:4000], bk_sec())
                elif d == "sec_a":
                    await edit("💡 Analyse IA en cours...", None)
                    result = await text_sec_analyze(client)
                    await edit(result[:4000], bk_sec())
                elif d == "sec_r":
                    await edit("📤 Génération du résumé...", None)
                    result = await text_sec_resume()
                    await edit(result[:4000], bk_sec())
                elif d == "sec_wipe":
                    nb = len(sec_log)
                    nb_msgs = sum(len(v.get("msgs",[])) for v in sec_log.values())
                    kb = _IKM([
                        [_IKB("✅ Oui, tout effacer", callback_data="sec_wipe_ok")],
                        [_IKB("❌ Annuler",            callback_data="sec")],
                    ])
                    await edit(
                        f"⚠️ *Effacer toutes les données ?*\n\n"
                        f"Cela supprimera définitivement :\n"
                        f"• {nb} contact(s) enregistré(s)\n"
                        f"• {nb_msgs} message(s) archivé(s)\n"
                        f"• Toutes les analyses IA\n\n"
                        f"_Cette action est irréversible._", kb)
                elif d == "sec_wipe_ok":
                    sec_log.clear()
                    conv_history.clear()
                    known_users.clear()
                    _analysis_cache.clear()
                    save_sec_log(sec_log)
                    _ai_key_alerted[0] = False
                    kb = _IKM([[_IKB("🔙 Menu", callback_data="mm")]])
                    await edit(
                        "✅ *Données effacées avec succès !*\n\n"
                        "Toutes les conversations et contacts ont été supprimés.\n"
                        "L'assistante repart de zéro.", kb)
                # ── Transcriptions audio ──────────────────────────────────────
                elif d == "sec_audio":
                    # Lire les données FRAÎCHES depuis le disque
                    _live_sec = load_uc_sec(uid)
                    audio_contacts = [
                        (cid, data)
                        for cid, data in _live_sec.items()
                        if any(m.get("audio") for m in data.get("msgs", []))
                    ]
                    if not audio_contacts:
                        await edit(
                            "🎤 *Transcriptions audio*\n\n"
                            "Aucun audio reçu pour l'instant.\n\n"
                            "_Les audios de tes contacts seront transcrits automatiquement "
                            "dès qu'un contact t'envoie un message vocal._",
                            _IKM([[_IKB("🔙 Secrétariat", callback_data="sec")]]))
                    else:
                        rows = []
                        for cid, data in audio_contacts:
                            nb_a = sum(1 for m in data.get("msgs", []) if m.get("audio"))
                            name = data.get("name", str(cid))
                            rows.append([_IKB(
                                f"🎤 {name}  ({nb_a} audio{'s' if nb_a > 1 else ''})",
                                callback_data=f"sec_audio_{cid}")])
                        rows.append([_IKB("🔙 Secrétariat", callback_data="sec")])
                        total_audio = sum(
                            1 for data in _live_sec.values()
                            for m in data.get("msgs", []) if m.get("audio"))
                        await edit(
                            f"🎤 *Transcriptions audio* — {total_audio} au total\n\n"
                            f"Choisissez un contact pour voir ses audios transcrits :",
                            _IKM(rows))

                elif d.startswith("sec_audio_"):
                    try:
                        cid_key  = d.replace("sec_audio_", "")
                        # Lire les données FRAÎCHES depuis le disque
                        _live_sec = load_uc_sec(uid)
                        try:
                            contact_data = _live_sec.get(int(cid_key)) or _live_sec.get(cid_key)
                        except Exception:
                            contact_data = _live_sec.get(cid_key)
                        if not contact_data:
                            await edit("❌ Contact introuvable.",
                                       _IKM([[_IKB("🔙 Audios", callback_data="sec_audio")]]))
                        else:
                            audios = [m for m in contact_data.get("msgs", []) if m.get("audio")]
                            name   = contact_data.get("name", cid_key)
                            if not audios:
                                await edit(f"🎤 Aucun audio transcrit pour *{name}* pour l'instant.",
                                           _IKM([[_IKB("🔙 Audios", callback_data="sec_audio")]]))
                            else:
                                lines = [f"🎤 *Audios transcrits — {name}*\n"]
                                for m in audios[-30:]:
                                    lines.append(f"🕐 `{m.get('d','?')}`")
                                    lines.append(f"_{m.get('t','')}_")
                                    lines.append("")
                                text_out = "\n".join(lines)
                                if len(text_out) > 4000:
                                    text_out = text_out[:4000] + "\n\n_[tronqué]_"
                                await edit(text_out,
                                           _IKM([[_IKB("🔙 Liste contacts", callback_data="sec_audio")],
                                                 [_IKB("🔙 Secrétariat",   callback_data="sec")]]))
                    except Exception as _ea:
                        await edit(f"❌ Erreur : {_ea}",
                                   _IKM([[_IKB("🔙", callback_data="sec_audio")]]))

                elif d == "rem":
                    kb = _IKM([[_IKB("🔙 Secrétariat", callback_data="sec")]])
                    await edit(text_reminders(), kb)
                elif d == "rem_a":
                    ctrl_state[uid] = {"step":"remind"}
                    await edit("📝 *Ajouter un rappel*\n\nEnvoyez : `texte | YYYY-MM-DD HH:MM`\n"
                               "Ex : `Finir bot Jean | 2026-03-22 23:59`")
                elif d == "prog":
                    await edit(text_prog(), bk_prog())
                elif d == "prog_v":
                    await edit(text_prog(), bk_prog())
                elif d == "prog_a":
                    ctrl_state[uid] = {"step":"addprog"}
                    await edit("📅 *Ajouter une tâche*\n\nEnvoyez la tâche :")
                elif d == "prog_c":
                    config["daily_program"] = []; save_config(config)
                    await edit("✅ Programme vidé.", bk_prog())
                elif d == "ai":
                    await edit("🤖 *Fournisseurs IA*\n\nCliquez pour configurer :", bk_ai())
                elif d == "ai_st":
                    config["stealth_mode"] = not config.get("stealth_mode", True)
                    save_config(config)
                    s = f"🕵️ ON — Je réponds comme {config.get('user_name','toi')}" if config["stealth_mode"] else "🔵 OFF — Assistante"
                    await edit(f"Mode furtif : *{s}*", bk_ai())
                elif d == "ai_auto":
                    config["auto_reply_enabled"] = not config.get("auto_reply_enabled", True)
                    save_config(config)
                    if config["auto_reply_enabled"]: stopped_chats.clear()
                    s = "✅ Activée" if config["auto_reply_enabled"] else "🛑 Désactivée"
                    await edit(f"Auto-réponse : *{s}*", bk_ai())
                elif d.startswith("ai_"):
                    provider = d[3:]
                    if provider in AI_META:
                        ctrl_state[uid] = {"step":"ai_key","provider":provider}
                        pdata     = config["ai_providers"].get(provider, {})
                        keys_list = [x for x in pdata.get("keys", []) if x]
                        n_keys    = len(keys_list)
                        keys_info = "\n".join(
                            f"  🔑 Clé {i+1}: `{k[:8]}...{k[-4:]}`"
                            for i, k in enumerate(keys_list)
                        ) if keys_list else "  _Aucune clé configurée_"
                        urls = {"groq":"console.groq.com/keys","openai":"platform.openai.com/api-keys",
                                "anthropic":"console.anthropic.com","gemini":"aistudio.google.com/app/apikey",
                                "mistral":"console.mistral.ai/api-keys"}
                        await edit(
                            f"🔑 *{AI_META[provider]['name']}*\n\n"
                            f"Clés configurées ({n_keys}) :\n{keys_info}\n\n"
                            f"Envoyez une *nouvelle clé* pour l'ajouter.\n"
                            f"_(bascule automatique si quota épuisé)_\n"
                            f"🔗 {urls.get(provider,'')}")
                elif d == "stats":
                    await edit(text_stats(), _IKM([
                        [_IKB("🔄 Actualiser", callback_data="stats")],
                        [_IKB("🔙 Menu",        callback_data="mm")],
                    ]))
                elif d == "prm":
                    await edit("⚙️ *Paramètres*", bk_prm())
                elif d == "prm_d":
                    ctrl_state[uid] = {"step":"delay"}
                    await edit(f"⏱ Délai absence actuel : *{config['delay_seconds']}s*\n\nEnvoyez le nouveau délai (ex: `30`) :")
                elif d == "prm_r":
                    ctrl_state[uid] = {"step":"replydelay"}
                    await edit(f"⚡ Délai réponse actuel : *{config.get('reply_delay_seconds',5)}s*\n\nEnvoyez (ex: `5`) :")
                elif d == "prm_q":
                    ctrl_state[uid] = {"step":"quota"}
                    await edit(f"🔢 Quota actuel : *{config['daily_quota']}/jour*\n\nEnvoyez le nouveau quota :")
                elif d == "prm_k":
                    kb2 = config["knowledge_base"]
                    lines = [f"📚 *Base ({len(kb2)} entrées)*\n"]
                    for i, x in enumerate(kb2, 1):
                        lines.append(f"{i}. {x[:80]}")
                    mk = _IKM([[_IKB("➕ Ajouter", callback_data="prm_ka"),
                                _IKB("⚙️ Paramètres", callback_data="prm")]])
                    await edit("\n".join(lines)[:4000], mk)
                elif d == "prm_ka":
                    ctrl_state[uid] = {"step":"addinfo"}
                    await edit("➕ *Ajouter une information*\n\nTapez l'info :")
                elif d == "prm_kv":
                    kb2 = config["knowledge_base"]
                    lines = [f"📚 *Base ({len(kb2)} entrées)*\n"]
                    for i, x in enumerate(kb2, 1):
                        lines.append(f"`/removeinfo {i}` — {x[:70]}")
                    mk = _IKM([[_IKB("🔙 Paramètres", callback_data="prm")]])
                    await edit("\n".join(lines)[:4000], mk)

                elif d == "away_toggle":
                    if away_mode[0]:
                        # Désactiver
                        away_mode[0] = False
                        duree = int(time.time() - away_mode_start[0])
                        h, m  = duree // 3600, (duree % 3600) // 60
                        nb    = len(away_log)
                        await edit(
                            f"🟢 *Mode Occupé désactivé*\n\n"
                            f"⏱ Durée : {h}h{m:02d}m\n"
                            f"💬 Conversations gérées : {nb}\n\n"
                            f"Tape *Quoi de neuf ?* pour le rapport complet.",
                            _IKM([
                                [_IKB("📬 Quoi de neuf ? (rapport complet)", callback_data="quoi_de_neuf")],
                                [_IKB("🔙 Menu", callback_data="mm")],
                            ])
                        )
                    else:
                        # Activer
                        away_mode[0]       = True
                        away_mode_start[0] = time.time()
                        away_log.clear()
                        await edit(
                            f"📵 *Je suis occupé — Bot activé !*\n\n"
                            f"✅ Le bot répond à ta place dès maintenant.\n\n"
                            f"⏱ Délai naturel : 10 secondes avant chaque réponse\n"
                            f"🧠 Connaît ton style d'écriture et tes projets\n"
                            f"📝 Note tout ce qui se dit dans le secrétariat\n"
                            f"📌 Détecte les *\"n'oublie pas\"* → crée des notes auto\n\n"
                            f"_Quand tu reviens → appuie sur le bouton pour l'arrêter._",
                            _IKM([
                                [_IKB("🛑 Arrêter (je suis de retour)", callback_data="away_toggle")],
                                [_IKB("🔙 Menu", callback_data="mm")],
                            ])
                        )

                elif d == "transcribe_help":
                    await edit(
                        "🎤 *Transcrire un audio en texte*\n\n"
                        "C'est simple — *envoie directement* ici :\n\n"
                        "🎙 Un *message vocal* (bouton micro dans Telegram)\n"
                        "🎵 Un *fichier audio* (mp3, m4a, ogg, wav...)\n\n"
                        "Le bot te renvoie immédiatement le texte en français.\n\n"
                        "_Fonctionne avec toutes les langues — le bot détecte automatiquement._",
                        _IKM([[_IKB("🔙 Menu", callback_data="mm")]])
                    )

                elif d == "quoi_de_neuf":
                    if not away_log:
                        await edit(
                            "📬 *Quoi de neuf ?*\n\n"
                            "Aucune conversation en mode absent pour l'instant.\n"
                            "Active d'abord *📵 Je suis occupé* pour que le bot gère tes messages.",
                            _IKM([[_IKB("🔙 Menu", callback_data="mm")]])
                        )
                    else:
                        await edit("⏳ *Génération du rapport en cours...*\n\nAnalyse de toutes les conversations...", None)
                        nb = len(away_log)
                        conv_lines = []
                        for uid2, msgs in list(away_log.items())[-8:]:
                            name = sec_log.get(str(uid2), {}).get("name", f"Contact {uid2}")
                            conv_lines.append(f"👤 *{name}* — {len(msgs)} msg(s)")
                            for m2 in msgs[-2:]:
                                conv_lines.append(f"  › _{m2[:80]}_")
                        conv_txt = "\n".join(conv_lines)
                        _uname_aw = config.get("user_name", "") or "l'utilisateur"
                        prompt = (
                            f"Voici les conversations gérées pendant l'absence de {_uname_aw} "
                            f"({nb} contacts) :\n\n{conv_txt}\n\n"
                            f"Fais un BREF rapport : points importants, promesses détectées, "
                            f"actions requises. Max 200 mots."
                        )
                        try:
                            rapport = await smart_ai_call(
                                f"Tu es le secrétaire intelligent de {_uname_aw}.",
                                [{"role":"user","content":prompt}],
                                max_tokens=400, temperature=0.5)
                        except Exception:
                            rapport = conv_txt
                        away_log.clear()
                        await edit(
                            f"📬 *Rapport — Quoi de neuf ?*\n\n{rapport[:3800]}",
                            _IKM([[_IKB("🔙 Menu", callback_data="mm")]])
                        )

                elif d == "coach":
                    nb_convs = len(sec_log)
                    await edit(
                        f"🎓 *Rapport Coaching*\n\n{nb_convs} conversation(s) analysées.\n\n"
                        f"_Le rapport est généré automatiquement quand tu es inactif 5+ min._",
                        _IKM([
                            [_IKB("🔄 Forcer l'analyse maintenant", callback_data="coach_force")],
                            [_IKB("🔙 Menu", callback_data="mm")],
                        ])
                    )

                elif d == "coach_force":
                    await edit("🎓 *Analyse coaching en cours...*", None)
                    try:
                        msgs_out = []
                        for dat in list(sec_log.values())[-5:]:
                            for m2 in dat["msgs"]:
                                if m2.get("r") == "out":
                                    msgs_out.append(m2["t"])
                        if not msgs_out:
                            await edit("Pas encore de messages sortants à analyser.", _IKM([[_IKB("🔙 Menu", callback_data="mm")]]))
                        else:
                            sample = "\n".join(msgs_out[-15:])
                            _uname_coach = config.get("user_name", "") or "l'utilisateur"
                            prompt = (
                                f"Analyse ces messages envoyés par {_uname_coach} à ses contacts :\n\n{sample}\n\n"
                                f"Donne un coaching bref : fautes d'orthographe, meilleures formulations, "
                                f"opportunités manquées. Max 200 mots."
                            )
                            rapport = await smart_ai_call(
                                f"Tu es le coach personnel de {_uname_coach}.",
                                [{"role":"user","content":prompt}],
                                max_tokens=400, temperature=0.5)
                            await edit(
                                f"🎓 *Coaching IA*\n\n{rapport[:3800]}",
                                _IKM([
                                    [_IKB("🗑 Supprimer ce rapport", callback_data="coach_del")],
                                    [_IKB("🔙 Menu", callback_data="mm")],
                                ]))
                    except Exception as e:
                        await edit(f"❌ Erreur : {e}", _IKM([[_IKB("🔙 Menu", callback_data="mm")]]))

                elif d == "coach_del":
                    try:
                        await query.message.delete()
                    except Exception:
                        await edit("🗑 Rapport supprimé.", _IKM([[_IKB("🔙 Menu", callback_data="mm")]]))

                # ── Consignes ──────────────────────────────────────────────────
                elif d == "consignes":
                    nb = len(config.get("consignes", []))
                    await edit(
                        f"📌 *Consignes de comportement*\n\n"
                        f"Ces instructions guident le comportement du bot.\n"
                        f"Actuellement : *{nb}* consigne(s) enregistrée(s).\n\n"
                        f"Choisissez une action :", bk_consignes())

                elif d == "consignes_v":
                    consignes = config.get("consignes", [])
                    if not consignes:
                        txt = "📌 *Consignes*\n\n_Aucune consigne enregistrée._"
                    else:
                        lines = [f"📌 *Consignes ({len(consignes)})*\n"]
                        for i, c in enumerate(consignes, 1):
                            lines.append(f"*{i}.* {c}\n  `/delconsigne {i}`")
                        txt = "\n".join(lines)
                    await edit(txt[:4000], bk_consignes())

                elif d == "consignes_a":
                    ctrl_state[uid] = {"step": "consigne_add"}
                    await edit("📌 *Ajouter une consigne*\n\nEnvoyez le texte de la consigne :")

                elif d == "consignes_wipe":
                    config["consignes"] = []
                    save_config(config)
                    await edit("🗑 Toutes les consignes ont été effacées.", bk_consignes())

                elif d.startswith("consignes_del_"):
                    try:
                        idx = int(d.split("consignes_del_")[1]) - 1
                        consignes = config.get("consignes", [])
                        if 0 <= idx < len(consignes):
                            removed = consignes.pop(idx)
                            save_config(config)
                            await edit(f"🗑 Consigne supprimée :\n_{removed}_", bk_consignes())
                        else:
                            await edit("❌ Index invalide.", bk_consignes())
                    except Exception:
                        await edit("❌ Erreur.", bk_consignes())

                # ── Stratégies Baccara ─────────────────────────────────────────
                elif d == "strat":
                    strats = config.get("baccara_strategies", [])
                    await edit(
                        f"🎲 *Baccara — Stratégies gratuites*\n\n"
                        f"Enregistrez ici des stratégies que vous pouvez offrir gratuitement "
                        f"à toute personne intéressée.\n\n"
                        f"📦 {len(strats)} stratégie(s) enregistrée(s)\n\n"
                        f"Choisissez une action :", bk_strat())

                elif d == "strat_v":
                    strats = config.get("baccara_strategies", [])
                    if not strats:
                        txt = (
                            "🎲 *Stratégies Baccara*\n\n"
                            "_Aucune stratégie enregistrée pour l'instant._\n\n"
                            "Appuyez sur ➕ Ajouter pour en créer une."
                        )
                    else:
                        lines = [f"🎲 *Stratégies Baccara ({len(strats)})*\n"]
                        for i, s in enumerate(strats, 1):
                            name = s.get("name", f"Stratégie {i}")
                            desc = s.get("description", "")
                            lines.append(f"*{i}. {name}*\n   _{desc}_\n  `/delstrat {i}`")
                        lines.append("\n_Quand un contact demande une stratégie, le bot en donne une gratuitement._")
                        txt = "\n".join(lines)
                    await edit(txt[:4000], bk_strat())

                elif d == "strat_a":
                    ctrl_state[uid] = {"step": "strat_name"}
                    await edit("🎲 *Nouvelle stratégie Baccara*\n\nStep 1/2 — Envoyez le *nom* de la stratégie :")

                elif d.startswith("strat_del_"):
                    try:
                        idx = int(d.split("strat_del_")[1]) - 1
                        strats = config.get("baccara_strategies", [])
                        if 0 <= idx < len(strats):
                            removed = strats.pop(idx)
                            save_config(config)
                            await edit(f"🗑 Stratégie supprimée :\n*{removed.get('name','')}*", bk_strat())
                        else:
                            await edit("❌ Index invalide.", bk_strat())
                    except Exception:
                        await edit("❌ Erreur.", bk_strat())

                # ── Affichage d'un bouton personnalisé depuis l'accueil ────────
                elif d.startswith("cbtnshow_"):
                    try:
                        bid  = int(d.split("cbtnshow_")[1])
                        btns = config.get("custom_buttons", [])
                        b    = next((x for x in btns if x["id"] == bid), None)
                        if b:
                            await edit(
                                f"🔘 *{b['name']}*\n\n"
                                f"{b['description']}",
                                _IKM([
                                    [_IKB("✏️ Modifier", callback_data=f"cbtnedit_{bid}")],
                                    [_IKB("🔙 Accueil",  callback_data="mm")],
                                ]))
                        else:
                            await edit("❌ Bouton introuvable.", bk_main())
                    except Exception:
                        await edit("❌ Erreur.", bk_main())

                # ── Mes boutons personnalisés ──────────────────────────────────
                elif d == "cbtns":
                    btns = config.get("custom_buttons", [])
                    await edit(
                        f"🎛 *Mes boutons personnalisés* ({len(btns)})\n\n"
                        f"Ces boutons donnent au bot des informations précises à partager.\n"
                        f"Le bot cite l'information exacte — sans inventer.\n\n"
                        f"Choisissez une action :", bk_cbtns())

                elif d == "cbtnadd":
                    ctrl_state[uid] = {"step": "cbtn_name"}
                    await edit(
                        "🎛 *Nouveau bouton personnalisé*\n\n"
                        "Step 1/2 — Envoyez le *nom* du bouton :\n"
                        "_(ex : Prix formations, Lien WhatsApp, Tarif bot)_")

                elif d.startswith("cbtnedit_"):
                    try:
                        bid = int(d.split("cbtnedit_")[1])
                        btns = config.get("custom_buttons", [])
                        b = next((x for x in btns if x["id"] == bid), None)
                        if b:
                            ctrl_state[uid] = {"step": "cbtn_edit_desc", "cbtn_tmp_id": bid}
                            await edit(
                                f"✏️ *Modifier : {b['name']}*\n\n"
                                f"Description actuelle :\n_{b['description']}_\n\n"
                                f"Envoyez la nouvelle description :")
                        else:
                            await edit("❌ Bouton introuvable.", bk_cbtns())
                    except Exception:
                        await edit("❌ Erreur.", bk_cbtns())

                elif d.startswith("cbtndelete_"):
                    try:
                        bid = int(d.split("cbtndelete_")[1])
                        btns = config.get("custom_buttons", [])
                        b = next((x for x in btns if x["id"] == bid), None)
                        if b:
                            config["custom_buttons"] = [x for x in btns if x["id"] != bid]
                            save_config(config)
                            await edit(f"🗑 Bouton *{b['name']}* supprimé.", bk_cbtns())
                        else:
                            await edit("❌ Bouton introuvable.", bk_cbtns())
                    except Exception:
                        await edit("❌ Erreur.", bk_cbtns())

                # ── Session secrétariat ────────────────────────────────────────
                elif d == "sec_session":
                    await edit(text_sec_session(), _IKM([
                        [_IKB("🔄 Actualiser",      callback_data="sec_session")],
                        [_IKB("🗑 Vider la session", callback_data="sec_session_clear")],
                        [_IKB("🔙 Secrétariat",      callback_data="sec")],
                    ]))

                elif d == "sec_session_clear":
                    session_log.clear()
                    await edit(
                        "🗑 *Session vidée.*\n\nLes messages de session ont été effacés.",
                        _IKM([[_IKB("🔙 Secrétariat", callback_data="sec")]]))

                elif d == "sec_contacts":
                    lines = ["📚 *Contacts enregistrés*\n"]
                    for uid2, dat in list(sec_log.items())[-20:]:
                        nb2 = len(dat.get("msgs", []))
                        lines.append(f"👤 *{dat.get('name','?')}* — {nb2} msg(s)")
                    if not sec_log:
                        lines.append("_Aucun contact enregistré._")
                    await edit("\n".join(lines)[:4000], _IKM([[_IKB("🔙 Secrétariat", callback_data="sec")]]))

                # ── Mode discussion admin-assistante ──────────────────────────
                elif d == "admin_chat_toggle":
                    _acm[0] = not _acm[0]
                    if _acm[0]:
                        _ach.clear()
                        nb_sec  = sum(len(v["msgs"]) for v in sec_log.values())
                        nb_conv = len(sec_log)
                        nb_req  = len(config.get("requests", []))
                        nb_pend = sum(1 for r in config.get("requests", []) if r["status"] == "pending")
                        intro = (
                            f"💬 *Mode discussion avec l'assistante activé !*\n\n"
                            f"Parle-lui directement. Elle a accès à :\n"
                            f"• Toutes tes conversations ({nb_conv} contacts, {nb_sec} messages)\n"
                            f"• Tes demandes en cours ({nb_pend}/{nb_req} en attente)\n"
                            f"• Tes stratégies, consignes, programme du jour\n\n"
                            f"_Tu peux lui demander ses conseils, ce qu'elle a compris, "
                            f"tester ses réponses, ou juste discuter librement._\n\n"
                            f"👉 Envoie ton premier message ci-dessous.\n"
                            f"Appuie sur le bouton ci-dessous pour quitter."
                        )
                        await edit(intro, _IKM([
                            [_IKB("🔴 Quitter le mode discussion", callback_data="admin_chat_toggle")],
                            [_IKB("🔙 Menu", callback_data="mm")],
                        ]))
                    else:
                        _ach.clear()
                        await edit(
                            "💬 *Mode discussion terminé.*\n\n_Conversation effacée._",
                            _IKM([[_IKB("🏠 Menu", callback_data="mm")]]))

            # ── Messages texte control bot ─────────────────────────────────────

            async def bc_msg(update: _U, context: _CT.DEFAULT_TYPE):
                uid  = update.effective_user.id
                text = (update.message.text or "").strip()

                # ── Wizard d'inscription (priorité absolue) ──────────────────
                if uid in _REG_STATE:
                    await _handle_reg_wizard(update, uid, text, context)
                    return

                if not user_registered(uid):
                    await update.message.reply_text(
                        "👋 Bienvenue ! Envoyez /start pour vous inscrire.")
                    return

                if user_blocked(uid):
                    await update.message.reply_text("🚫 Accès bloqué.")
                    return

                _switch_user_ctx(uid)
                _ctx2 = get_ctx(uid)
                _acm2 = _ctx2["admin_chat_mode"]
                _ach2 = _ctx2["admin_chat_hist"]

                st   = ctrl_state.get(uid, {})
                step = st.get("step")

                # ── Mode discussion admin-assistante (prioritaire sur tout le reste) ──
                if _acm2[0] and not step:
                    if text.strip().lower() in ("/stop", "stop", "quitter", "/quitter"):
                        _acm2[0] = False
                        _ach2.clear()
                        await update.message.reply_text(
                            "💬 Mode discussion terminé.",
                            reply_markup=_IKM([[_IKB("🏠 Menu", callback_data="mm")]]),
                            parse_mode="Markdown")
                        return

                    await update.message.chat.send_action("typing")

                    # Construire le contexte admin complet pour l'assistante
                    nb_contacts = len(sec_log)
                    nb_msgs     = sum(len(v["msgs"]) for v in sec_log.values())
                    requests    = config.get("requests", [])
                    nb_pend     = sum(1 for r in requests if r["status"]=="pending")
                    nb_done     = sum(1 for r in requests if r["status"]=="done")
                    kb          = "\n".join(f"  • {x}" for x in config.get("knowledge_base",[]))
                    consignes   = "\n".join(f"  • {c['text']}" for c in config.get("consignes",[]))
                    strats      = config.get("baccara_strategies", [])
                    strats_txt  = "\n".join(f"  • {s['name']}: {s['description'][:80]}" for s in strats[:5])
                    prog        = "\n".join(f"  - {p}" for p in config.get("daily_program",[]))
                    # Résumé des dernières conversations
                    last_convs = []
                    for uid2, dat in list(sec_log.items())[-5:]:
                        last_msgs = dat.get("msgs",[])[-3:]
                        excerpts  = " | ".join(m["t"][:50] for m in last_msgs)
                        last_convs.append(f"  [{dat.get('name','?')}] {excerpts}")
                    convs_txt = "\n".join(last_convs) if last_convs else "  Aucune"

                    _uname_adm = config.get("user_name", "") or "l'utilisateur"
                    admin_sys = (
                        f"Tu es l'assistante IA de {_uname_adm}. "
                        f"Tu parles directement à TON PATRON — {_uname_adm} lui-même — qui te teste et discute avec toi.\n\n"
                        f"CONTEXTE ACTUEL ({benin_time()}) :\n"
                        f"• Contacts: {nb_contacts} | Messages traités: {nb_msgs}\n"
                        f"• Demandes clients: {nb_pend} en attente, {nb_done} traitées\n\n"
                        f"DERNIÈRES CONVERSATIONS :\n{convs_txt}\n\n"
                        f"PROFIL DE SOSSOU :\n{kb}\n\n"
                        f"{'CONSIGNES ACTIVES :\\n' + consignes + chr(10) if consignes else ''}"
                        f"{'STRATÉGIES BACCARA :\\n' + strats_txt + chr(10) if strats_txt else ''}"
                        f"{'PROGRAMME DU JOUR :\\n' + prog + chr(10) if prog else ''}\n"
                        f"COMPORTEMENT :\n"
                        f"• Sois directe, honnête, perspicace et naturelle avec ton patron\n"
                        f"• Partage tes observations sur les conversations, tes recommandations, tes impressions\n"
                        f"• Si il teste ta réponse, réponds comme tu répondrais à un contact\n"
                        f"• Si il discute librement, discute librement sans te limiter\n"
                        f"• Tu peux exprimer ta 'personnalité' d'assistante, être un peu chaleureuse\n"
                        f"• Réponds en français, concis et pertinent"
                    )

                    _ach2.append({"role": "user", "content": text})
                    if len(_ach2) > 30:
                        _ach2[:] = _ach2[-30:]

                    try:
                        reply = await smart_ai_call(admin_sys, list(_ach2))
                        _ach2.append({"role": "assistant", "content": reply})
                        stop_kb = _IKM([[_IKB("🔴 Quitter la discussion", callback_data="admin_chat_toggle")]])
                        await update.message.reply_text(
                            f"🤖 {reply}",
                            reply_markup=stop_kb,
                            parse_mode="Markdown")
                    except Exception as e:
                        await update.message.reply_text(f"❌ Erreur IA: {str(e)[:200]}")
                    return

                if step == "ai_key":
                    provider = st["provider"]
                    ctrl_state.pop(uid, None)
                    await update.message.reply_text(f"🔍 Vérification *{AI_META[provider]['name']}*...",
                        parse_mode="Markdown")
                    loop = asyncio.get_event_loop()
                    model = config["ai_providers"][provider].get("model", AI_META[provider]["model"])
                    ok, info = await loop.run_in_executor(None, verify_key, provider, text.strip(), model)
                    if not ok:
                        await update.message.reply_text(f"❌ Clé invalide\n\n{info}",
                            reply_markup=bk_ai(), parse_mode="Markdown")
                    else:
                        new_key = text.strip()
                        keys_list = config["ai_providers"][provider].setdefault("keys", [])
                        if new_key not in keys_list:
                            keys_list.append(new_key)
                        config["active_ai"] = provider
                        save_config(config)
                        masked = new_key[:8]+"..."+new_key[-4:]
                        n_keys = len(keys_list)
                        await update.message.reply_text(
                            f"✅ *{AI_META[provider]['name']}* — clé ajoutée !\n\n"
                            f"Clé : `{masked}`\n{info}\n\n"
                            f"Total clés : *{n_keys}* _(bascule auto si quota épuisé)_",
                            reply_markup=bk_ai(), parse_mode="Markdown")

                elif step == "addprog":
                    ctrl_state.pop(uid, None)
                    progs = config.setdefault("daily_program", [])
                    progs.append(text.strip()); save_config(config)
                    await update.message.reply_text(f"✅ Tâche ajoutée !\n\n{text_prog()}",
                        reply_markup=bk_prog(), parse_mode="Markdown")

                elif step == "delay":
                    if text.strip().isdigit():
                        ctrl_state.pop(uid, None)
                        config["delay_seconds"] = int(text.strip()); save_config(config)
                        await update.message.reply_text(f"✅ Délai absence : *{config['delay_seconds']}s*",
                            reply_markup=bk_prm(), parse_mode="Markdown")
                    else:
                        await update.message.reply_text("❌ Veuillez envoyer un nombre (ex: `30`)",
                            parse_mode="Markdown")

                elif step == "replydelay":
                    if text.strip().isdigit():
                        ctrl_state.pop(uid, None)
                        config["reply_delay_seconds"] = int(text.strip()); save_config(config)
                        await update.message.reply_text(f"✅ Délai réponse : *{config['reply_delay_seconds']}s*",
                            reply_markup=bk_prm(), parse_mode="Markdown")

                elif step == "quota":
                    if text.strip().isdigit():
                        ctrl_state.pop(uid, None)
                        config["daily_quota"] = int(text.strip()); save_config(config)
                        await update.message.reply_text(f"✅ Quota : *{config['daily_quota']}/jour*",
                            reply_markup=bk_prm(), parse_mode="Markdown")

                elif step == "addinfo":
                    ctrl_state.pop(uid, None)
                    config["knowledge_base"].append(text.strip()); save_config(config)
                    await update.message.reply_text(f"✅ Info ajoutée !\n_{text.strip()}_",
                        reply_markup=bk_prm(), parse_mode="Markdown")

                elif step == "strat_name":
                    ctrl_state[uid] = {"step": "strat_desc", "strat_tmp_name": text.strip()}
                    await update.message.reply_text(
                        f"🎲 *Nouvelle stratégie — {text.strip()}*\n\n"
                        f"Step 2/2 — Envoyez la *description* de la stratégie :",
                        parse_mode="Markdown")

                elif step == "strat_desc":
                    name = st.get("strat_tmp_name", "Stratégie")
                    ctrl_state.pop(uid, None)
                    strats = config.setdefault("baccara_strategies", [])
                    strats.append({"id": int(time.time()), "name": name, "description": text.strip()})
                    save_config(config)
                    await update.message.reply_text(
                        f"✅ *Stratégie enregistrée !*\n\n"
                        f"🎲 *{name}*\n_{text.strip()}_\n\n"
                        f"Elle sera partagée gratuitement par le bot à ceux qui en font la demande.",
                        reply_markup=bk_strat(), parse_mode="Markdown")

                elif step == "consigne_add":
                    ctrl_state.pop(uid, None)
                    consignes = config.setdefault("consignes", [])
                    consignes.append(text.strip())
                    save_config(config)
                    await update.message.reply_text(
                        f"✅ *Consigne ajoutée !*\n\n_{text.strip()}_",
                        reply_markup=bk_consignes(), parse_mode="Markdown")

                elif step == "cbtn_name":
                    ctrl_state[uid] = {"step": "cbtn_desc", "cbtn_tmp_name": text.strip()}
                    await update.message.reply_text(
                        f"🎛 *Nouveau bouton : {text.strip()}*\n\n"
                        f"Step 2/2 — Envoyez maintenant la *description* complète :\n"
                        f"_(ex : Prix bot Telegram : 15 000 FCFA/mois. Paiement Mobile Money.)_",
                        parse_mode="Markdown")

                elif step == "cbtn_desc":
                    name = st.get("cbtn_tmp_name", "Bouton")
                    ctrl_state.pop(uid, None)
                    btns = config.setdefault("custom_buttons", [])
                    btns.append({"id": int(time.time()), "name": name, "description": text.strip()})
                    save_config(config)
                    await update.message.reply_text(
                        f"✅ *Bouton créé !*\n\n"
                        f"🎛 *{name}*\n_{text.strip()}_\n\n"
                        f"Le bot utilisera cette info exacte quand c'est pertinent.",
                        reply_markup=bk_cbtns(), parse_mode="Markdown")

                elif step == "cbtn_edit_desc":
                    bid = st.get("cbtn_tmp_id")
                    ctrl_state.pop(uid, None)
                    btns = config.get("custom_buttons", [])
                    b = next((x for x in btns if x["id"] == bid), None)
                    if b:
                        old_name = b["name"]
                        b["description"] = text.strip()
                        save_config(config)
                        await update.message.reply_text(
                            f"✅ *Bouton mis à jour !*\n\n"
                            f"🎛 *{old_name}*\n_{text.strip()}_",
                            reply_markup=bk_cbtns(), parse_mode="Markdown")
                    else:
                        await update.message.reply_text("❌ Bouton introuvable.",
                            reply_markup=bk_cbtns(), parse_mode="Markdown")

                elif step == "remind":
                    ctrl_state.pop(uid, None)
                    if "|" in text:
                        nt, dl_t = text.split("|",1)
                        try:
                            dl_dt = datetime.fromisoformat(dl_t.strip()).replace(tzinfo=BENIN_TZ)
                            dl_iso = dl_dt.strftime("%Y-%m-%dT%H:%M")
                        except:
                            dl_iso = dl_t.strip()
                    else:
                        nt, dl_iso = text, None
                    config["reminders"].append({
                        "id": int(time.time()), "text": nt.strip(), "contact": "Manuel (bot)",
                        "deadline": dl_iso, "created": benin_str(), "notified": False
                    })
                    save_config(config)
                    await update.message.reply_text(f"✅ Rappel ajouté !\n📌 {nt.strip()}",
                        reply_markup=bk_sec(), parse_mode="Markdown")

                # ═══ Wizard Groupe / Canal ══════════════════════════════════════
                elif step == "grp_chatid":
                    raw_cid  = text.strip()
                    chat_id  = None
                    title    = raw_cid
                    # Résolution via client Telethon de l'utilisateur
                    t_client = _USER_TELETHON.get(str(uid))
                    if t_client:
                        try:
                            from telethon.tl.types import Channel, Chat
                            entity = await t_client.get_entity(
                                int(raw_cid) if raw_cid.lstrip("-").isdigit() else raw_cid)
                            chat_id = entity.id if hasattr(entity, "id") else None
                            title   = getattr(entity, "title", raw_cid) or raw_cid
                            # Telegram stocke les supergroups/canaux avec préfixe -100
                            if hasattr(entity, "access_hash") and isinstance(entity, (Channel, Chat)):
                                if chat_id > 0:
                                    chat_id = int(f"-100{chat_id}")
                        except Exception as er:
                            logger.warning(f"grp_chatid resolve: {er}")
                    if not chat_id:
                        # Essai brut si c'est déjà un ID négatif
                        if raw_cid.lstrip("-").isdigit():
                            chat_id = int(raw_cid)
                        else:
                            await update.message.reply_text(
                                "❌ Impossible de trouver ce groupe/canal.\n\n"
                                "Envoyez l'ID numérique (ex: `-1001234567890`) ou "
                                "assurez-vous que votre compte est bien membre de ce groupe.",
                                parse_mode="Markdown")
                            return
                    ctrl_state[uid] = {
                        "step": "grp_roles",
                        "grp_tmp": {"chat_id": chat_id, "title": title, "roles_selected": []}
                    }
                    roles_map = {"pub": "📢 Publicité", "discuter": "💬 Discussion", "com": "📣 Communication"}
                    rows_r = []
                    for rk, rl in roles_map.items():
                        rows_r.append([_IKB(f"⬜ {rl}", callback_data=f"grp_role_toggle_{rk}")])
                    rows_r.append([_IKB("✔️ Valider les rôles", callback_data="grp_roles_done")])
                    rows_r.append([_IKB("🔙 Annuler", callback_data="add_to_group")])
                    await update.message.reply_text(
                        f"✅ Groupe trouvé : *{title}*\n`{chat_id}`\n\n"
                        f"🎭 *Choisissez les rôles* (max 2) :\n\n"
                        f"• 📢 *Publicité* : Publication automatique à intervalles réguliers\n"
                        f"• 💬 *Discussion* : Le bot répond aux membres (IA) et apprend\n"
                        f"• 📣 *Communication* : Message régulier à envoyer",
                        reply_markup=_IKM(rows_r), parse_mode="Markdown")

                elif step == "grp_info":
                    st_grp   = ctrl_state.get(uid, {})
                    tmp      = st_grp.get("grp_tmp", {})
                    selected = tmp.get("roles_selected", [])
                    tmp["group_info"] = text.strip()[:300]
                    if "pub" in selected:
                        ctrl_state[uid] = {**st_grp, "step": "grp_pub_text", "grp_tmp": tmp}
                        await update.message.reply_text(
                            "📢 *Publicité — Texte de la publication*\n\n"
                            "Envoyez le texte que le bot doit publier dans le groupe/canal.\n"
                            "_Vous pouvez utiliser des emojis et du formatage Markdown._",
                            reply_markup=_IKM([[_IKB("🔙 Annuler", callback_data="add_to_group")]]),
                            parse_mode="Markdown")
                    elif "com" in selected:
                        ctrl_state[uid] = {**st_grp, "step": "grp_com_text", "grp_tmp": tmp}
                        await update.message.reply_text(
                            "📣 *Communication — Message à envoyer*\n\n"
                            "Envoyez le message de communication régulier.",
                            reply_markup=_IKM([[_IKB("🔙 Annuler", callback_data="add_to_group")]]),
                            parse_mode="Markdown")
                    else:
                        _grp_save_wizard(uid, tmp)
                        ctrl_state.pop(uid, None)
                        await update.message.reply_text(
                            f"✅ *Groupe configuré !*\n\n"
                            f"🆔 `{tmp.get('chat_id', '')}` — {tmp.get('title', '')}\n"
                            f"🎭 Rôle : 💬 Discussion (IA)\n\n"
                            f"Le bot va apprendre des échanges et répondre aux mentions.",
                            reply_markup=_IKM([[_IKB("📡 Mes groupes", callback_data="add_to_group")]]),
                            parse_mode="Markdown")
                        _trigger_grp_handlers(uid)

                elif step == "grp_pub_text":
                    st_grp = ctrl_state.get(uid, {})
                    tmp    = st_grp.get("grp_tmp", {})
                    tmp["pub_text"] = text.strip()
                    ctrl_state[uid] = {**st_grp, "step": "grp_pub_media", "grp_tmp": tmp}
                    await update.message.reply_text(
                        "🖼 *Photo ou vidéo pour la publication ?* _(facultatif)_\n\n"
                        "Envoyez une *photo* ou une *vidéo* qui sera jointe à chaque publication.\n\n"
                        "👉 Ou appuyez sur *Ignorer* pour continuer sans média.",
                        reply_markup=_IKM([
                            [_IKB("⏭ Ignorer — texte seul", callback_data="grp_pub_skip_media")],
                            [_IKB("🔙 Annuler", callback_data="add_to_group")],
                        ]), parse_mode="Markdown")

                elif step == "grp_pub_interval":
                    st_grp = ctrl_state.get(uid, {})
                    tmp    = st_grp.get("grp_tmp", {})
                    minutes = _parse_interval(text)
                    if not minutes:
                        await update.message.reply_text(
                            "❌ Format invalide. Envoyez par ex. `2h`, `30min`, ou `90`.",
                            parse_mode="Markdown")
                        return
                    tmp["pub_interval_minutes"] = minutes
                    # Prochain step
                    if "com" in tmp.get("roles_selected", []):
                        ctrl_state[uid] = {**st_grp, "step": "grp_com_text", "grp_tmp": tmp}
                        await update.message.reply_text(
                            "📣 *Communication — Message à envoyer*\n\n"
                            "Envoyez le message de communication régulier.",
                            reply_markup=_IKM([[_IKB("🔙 Annuler", callback_data="add_to_group")]]),
                            parse_mode="Markdown")
                    else:
                        _grp_save_wizard(uid, tmp)
                        ctrl_state.pop(uid, None)
                        roles_disp = " + ".join(
                            {"pub": "📢 Publicité", "discuter": "💬 Discussion", "com": "📣 Communication"}.get(r, r)
                            for r in tmp.get("roles_selected", []))
                        await update.message.reply_text(
                            f"✅ *Groupe configuré !*\n\n"
                            f"📡 *{tmp.get('title', '')}*\n"
                            f"🎭 Rôles : {roles_disp}\n"
                            f"📢 Publication toutes les {minutes} min",
                            reply_markup=_IKM([[_IKB("📡 Mes groupes", callback_data="add_to_group")]]),
                            parse_mode="Markdown")
                        _trigger_grp_handlers(uid)

                elif step == "grp_com_text":
                    st_grp = ctrl_state.get(uid, {})
                    tmp    = st_grp.get("grp_tmp", {})
                    tmp["com_text"] = text.strip()
                    ctrl_state[uid] = {**st_grp, "step": "grp_com_media", "grp_tmp": tmp}
                    await update.message.reply_text(
                        "🖼 *Photo ou vidéo pour la communication ?* _(facultatif)_\n\n"
                        "Envoyez une *photo* ou une *vidéo* qui sera jointe à chaque message de communication.\n\n"
                        "👉 Ou appuyez sur *Ignorer* pour continuer sans média.",
                        reply_markup=_IKM([
                            [_IKB("⏭ Ignorer — texte seul", callback_data="grp_com_skip_media")],
                            [_IKB("🔙 Annuler", callback_data="add_to_group")],
                        ]), parse_mode="Markdown")

                elif step == "grp_com_interval":
                    st_grp = ctrl_state.get(uid, {})
                    tmp    = st_grp.get("grp_tmp", {})
                    minutes = _parse_interval(text)
                    if not minutes:
                        await update.message.reply_text(
                            "❌ Format invalide. Envoyez par ex. `2h`, `30min`, ou `90`.",
                            parse_mode="Markdown")
                        return
                    tmp["com_interval_minutes"] = minutes
                    _grp_save_wizard(uid, tmp)
                    ctrl_state.pop(uid, None)
                    roles_disp = " + ".join(
                        {"pub": "📢 Publicité", "discuter": "💬 Discussion", "com": "📣 Communication"}.get(r, r)
                        for r in tmp.get("roles_selected", []))
                    await update.message.reply_text(
                        f"✅ *Groupe configuré !*\n\n"
                        f"📡 *{tmp.get('title', '')}*\n"
                        f"🎭 Rôles : {roles_disp}\n",
                        reply_markup=_IKM([[_IKB("📡 Mes groupes", callback_data="add_to_group")]]),
                        parse_mode="Markdown")
                    _trigger_grp_handlers(uid)

            async def bc_media(update, context):
                """Gère l'envoi d'une photo ou vidéo dans le wizard groupe (pub_media / com_media)."""
                if not update.effective_user:
                    return
                uid = update.effective_user.id
                if not user_registered(uid):
                    return
                _switch_user_ctx(uid)
                step = ctrl_state.get(uid, {}).get("step", "")
                if step not in ("grp_pub_media", "grp_com_media"):
                    return
                st_grp = ctrl_state.get(uid, {})
                tmp    = st_grp.get("grp_tmp", {})
                role_key = "pub" if step == "grp_pub_media" else "com"
                # Télécharger la photo ou vidéo
                try:
                    os.makedirs(f"users_data/{uid}/media", exist_ok=True)
                    if update.message.photo:
                        file_obj = await context.bot.get_file(
                            update.message.photo[-1].file_id)
                        path = f"users_data/{uid}/media/{role_key}_{int(time.time())}.jpg"
                        await file_obj.download_to_drive(path)
                    elif update.message.video:
                        file_obj = await context.bot.get_file(
                            update.message.video.file_id)
                        path = f"users_data/{uid}/media/{role_key}_{int(time.time())}.mp4"
                        await file_obj.download_to_drive(path)
                    else:
                        return
                    tmp[f"{role_key}_media"] = path
                    logger.info(f"🖼 Média {role_key} sauvegardé : {path}")
                except Exception as e:
                    await update.message.reply_text(
                        f"❌ Impossible de télécharger le fichier : {e}")
                    return
                # Passer à l'étape intervalle
                if role_key == "pub":
                    ctrl_state[uid] = {**st_grp, "step": "grp_pub_interval", "grp_tmp": tmp}
                    await update.message.reply_text(
                        "✅ *Média enregistré !*\n\n"
                        "⏱ *Intervalle de publication*\n\n"
                        "À quelle fréquence envoyer cette publication ?\n"
                        "_Ou tapez librement : `2h`, `30min`, `90`, `4h`_",
                        reply_markup=_IKM([
                            [_IKB("1 min",  callback_data="grp_int_1"),
                             _IKB("2 min",  callback_data="grp_int_2"),
                             _IKB("5 min",  callback_data="grp_int_5")],
                            [_IKB("10 min", callback_data="grp_int_10"),
                             _IKB("15 min", callback_data="grp_int_15"),
                             _IKB("30 min", callback_data="grp_int_30")],
                            [_IKB("1h",     callback_data="grp_int_60"),
                             _IKB("2h",     callback_data="grp_int_120"),
                             _IKB("6h",     callback_data="grp_int_360")],
                            [_IKB("12h",    callback_data="grp_int_720"),
                             _IKB("24h",    callback_data="grp_int_1440")],
                            [_IKB("🔙 Annuler", callback_data="add_to_group")],
                        ]), parse_mode="Markdown")
                else:
                    ctrl_state[uid] = {**st_grp, "step": "grp_com_interval", "grp_tmp": tmp}
                    await update.message.reply_text(
                        "✅ *Média enregistré !*\n\n"
                        "⏱ *Intervalle de communication*\n\n"
                        "À quelle fréquence envoyer ce message ?\n"
                        "_Ou tapez librement : `2h`, `30min`, `90`, `4h`_",
                        reply_markup=_IKM([
                            [_IKB("1 min",  callback_data="grp_int_com_1"),
                             _IKB("2 min",  callback_data="grp_int_com_2"),
                             _IKB("5 min",  callback_data="grp_int_com_5")],
                            [_IKB("10 min", callback_data="grp_int_com_10"),
                             _IKB("15 min", callback_data="grp_int_com_15"),
                             _IKB("30 min", callback_data="grp_int_com_30")],
                            [_IKB("1h",     callback_data="grp_int_com_60"),
                             _IKB("2h",     callback_data="grp_int_com_120"),
                             _IKB("6h",     callback_data="grp_int_com_360")],
                            [_IKB("12h",    callback_data="grp_int_com_720"),
                             _IKB("24h",    callback_data="grp_int_com_1440")],
                            [_IKB("🔙 Annuler", callback_data="add_to_group")],
                        ]), parse_mode="Markdown")

            async def bc_voice(update, context):
                """Transcrit un audio/vocal envoyé par l'utilisateur au bot de contrôle."""
                if not update.effective_user:
                    return
                uid = update.effective_user.id
                if not user_registered(uid):
                    return
                msg = update.message
                # Récupérer le fichier (vocal ou audio)
                if msg.voice:
                    file_obj = await context.bot.get_file(msg.voice.file_id)
                    fname    = "voice.ogg"
                    mime     = "audio/ogg"
                elif msg.audio:
                    file_obj = await context.bot.get_file(msg.audio.file_id)
                    fname    = msg.audio.file_name or "audio.mp3"
                    mime     = msg.audio.mime_type or "audio/mpeg"
                else:
                    return
                # Indicateur de traitement
                wait_msg = await msg.reply_text("🎤 _Transcription en cours..._",
                                                parse_mode="Markdown")
                try:
                    # Télécharger en mémoire
                    import io as _io
                    buf = _io.BytesIO()
                    await file_obj.download_to_memory(buf)
                    audio_bytes = buf.getvalue()
                    if not audio_bytes:
                        await wait_msg.edit_text("❌ Fichier audio vide ou illisible.")
                        return
                    # Obtenir la clé Groq
                    _switch_user_ctx(uid)
                    cfg_u    = get_ctx(uid)["config"]
                    ai_provs = cfg_u.get("ai_providers", {})
                    _gcfg_ai = load_config().get("ai_providers", {})
                    groq_keys = (ai_provs.get("groq", {}).get("keys") or
                                 _gcfg_ai.get("groq", {}).get("keys") or [])
                    groq_key = next((k for k in groq_keys if k), None)
                    if not groq_key:
                        await wait_msg.edit_text(
                            "❌ Aucune clé Groq configurée.\n\n"
                            "Ajoutez une clé dans ⚙️ Fournisseurs IA → Groq.")
                        return
                    # Transcription Whisper (sync dans executor)
                    def _do_transcribe():
                        from groq import Groq as _GQ
                        gc  = _GQ(api_key=groq_key)
                        res = gc.audio.transcriptions.create(
                            file=(fname, audio_bytes, mime),
                            model="whisper-large-v3",
                            language="fr",
                        )
                        return res.text
                    import asyncio as _aio
                    transcribed = await _aio.get_event_loop().run_in_executor(
                        None, _do_transcribe)
                    if not transcribed or not transcribed.strip():
                        await wait_msg.edit_text("⚠️ Aucun texte détecté dans cet audio.")
                        return
                    transcribed = transcribed.strip()
                    await wait_msg.edit_text(
                        f"🎤 *Transcription*\n\n{transcribed}",
                        parse_mode="Markdown")
                except Exception as _ve:
                    logger.error(f"bc_voice uid={uid}: {_ve}")
                    await wait_msg.edit_text(
                        f"❌ Erreur de transcription : {_ve}")

            ctrl.add_handler(_CH("start",   bc_start))
            ctrl.add_handler(_CH("menu",    bc_start))
            ctrl.add_handler(_CQH(bc_cb))
            ctrl.add_handler(_MH(_F.VOICE | _F.AUDIO, bc_voice))
            ctrl.add_handler(_MH(_F.PHOTO | _F.VIDEO, bc_media))
            ctrl.add_handler(_MH(_F.TEXT & ~_F.COMMAND, bc_msg))

            # Gestionnaire d'erreur : si 409 Conflict (instance déployée active),
            # on stoppe proprement le polling local et on cède la main au déploiement.
            from telegram.error import Conflict as _TGConflict

            async def _ctrl_error_handler(update, context):
                if isinstance(context.error, _TGConflict):
                    if _ctrl_active[0]:
                        _ctrl_active[0] = False
                        logger.warning(
                            "⚠️ 409 Conflict — instance déployée déjà active. "
                            "Polling local arrêté. Le userbot Telethon reste fonctionnel."
                        )
                        try:
                            await ctrl.updater.stop()
                        except Exception:
                            pass
                else:
                    logger.error(f"Erreur bot de contrôle : {context.error}")

            ctrl.add_error_handler(_ctrl_error_handler)

            await ctrl.initialize()
            await ctrl.start()
            await ctrl.updater.start_polling(drop_pending_updates=True)
            logger.info("✅ Bot de contrôle actif")

        # ── Notification de démarrage ──────────────────────────────────────────
        try:
            active  = config.get("active_ai", "gemini")
            ai_name = AI_META.get(active, {}).get("name", active)
            has_keys = any(
                len(config["ai_providers"].get(p, {}).get("keys", [])) > 0
                for p in AI_META
            )
            ai_status = f"🤖 IA : {ai_name}" if has_keys else "⚠️ Aucune clé IA — configure via /menu → 🤖 Fournisseurs IA"
            _uname_notif = config.get("user_name", "") or "Bot"
            await notify(
                f"✅ *Bot {_uname_notif} — ACTIF !*\n\n"
                f"{ai_status}\n"
                f"🕵️ Furtif : {'ON' if config.get('stealth_mode',True) else 'OFF'}\n"
                f"🕐 Heure Bénin : {benin_time()}\n\n"
                f"👉 Tapez /menu pour les commandes"
            )
        except Exception as _e:
            logger.debug(f"Notification démarrage : {_e}")

        asyncio.create_task(reminder_checker())

        # ── Démarrage des userbots des utilisateurs enregistrés ───────────────
        _all_users = load_users()
        if _all_users:
            logger.info(f"🚀 Démarrage de {len(_all_users)} userbot(s) utilisateurs...")
            for _u_id_str, _u_data in _all_users.items():
                if not _u_data.get("blocked"):
                    asyncio.create_task(_run_user_telethon(int(_u_id_str)))

        try:
            if _has_client:
                await client.run_until_disconnected()
            else:
                # Pas de session admin — on garde le bot PTB actif indéfiniment
                logger.info("✅ Bot PTB actif en mode inscription (sans session Telethon admin)")
                while True:
                    await asyncio.sleep(60)
        finally:
            if _effective_bot_token:
                try:
                    await ctrl.updater.stop()
                    await ctrl.stop()
                    await ctrl.shutdown()
                except: pass

    asyncio.run(_main())


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS ASYNCHRONES — GROUPES & NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════════════════════

async def _notify_user(uid: int, msg: str):
    """Envoie une notification à l'utilisateur via le bot de contrôle PTB."""
    try:
        from telegram import Bot as _TGBot
        bot = _TGBot(token=MULTI_BOT_TOKEN)
        await bot.send_message(chat_id=uid, text=msg, parse_mode="Markdown")
    except Exception as e:
        logger.warning(f"_notify_user uid={uid}: {e}")


async def _grp_publisher(uid: int, client, chat_id: int, role: str):
    """Tâche planifiée — envoie pub ou com dans un groupe à intervalle régulier."""
    uid_str = str(uid)
    first   = True
    while True:
        grp_cfgs = load_grp_configs(uid)
        gcfg     = grp_cfgs.get(str(chat_id), {})
        if not gcfg or role not in gcfg.get("roles", []) or gcfg.get("paused") or user_blocked(uid):
            break
        interval_min = gcfg.get(f"{role}_interval_minutes", 120)
        text_to_send = gcfg.get(f"{role}_text", "")
        if not text_to_send:
            break
        # Attendre l'intervalle (sauf au premier lancement)
        if not first:
            await asyncio.sleep(interval_min * 60)
        else:
            first = False
            # Première fois : attendre 10 secondes avant le premier envoi
            await asyncio.sleep(10)
        # Vérifier à nouveau après l'attente
        grp_cfgs = load_grp_configs(uid)
        gcfg     = grp_cfgs.get(str(chat_id), {})
        if not gcfg or role not in gcfg.get("roles", []) or gcfg.get("paused") or user_blocked(uid):
            break
        try:
            cl_check = _USER_TELETHON.get(uid_str)
            if not cl_check or not cl_check.is_connected():
                break
            media_path = gcfg.get(f"{role}_media", "")
            if media_path and os.path.exists(media_path):
                await cl_check.send_file(chat_id, media_path,
                                         caption=text_to_send or None)
            else:
                await cl_check.send_message(chat_id, text_to_send)
            # Incrémenter compteur
            grp_cfgs[str(chat_id)]["bilan"]["msgs_envoyes"] = \
                grp_cfgs[str(chat_id)]["bilan"].get("msgs_envoyes", 0) + 1
            save_grp_configs(uid, grp_cfgs)
            logger.info(f"📤 {role} envoyé → chat={chat_id} uid={uid}")
        except Exception as e:
            err_s = str(e).lower()
            # Entité introuvable (ID user, groupe supprimé, bot non-membre, etc.)
            if "peeruser" in err_s or "input entity" in err_s or "channel/supergroup" in err_s \
                    or "not found" in err_s or "chat not found" in err_s or "peer" in err_s:
                logger.warning(f"_grp_publisher uid={uid} chat={chat_id}: entité invalide — pause auto")
                try:
                    _gcfg2 = load_grp_configs(uid)
                    if str(chat_id) in _gcfg2:
                        _gcfg2[str(chat_id)]["paused"] = True
                        save_grp_configs(uid, _gcfg2)
                    asyncio.ensure_future(_notify_user(uid,
                        f"⚠️ *Publication automatique pausée*\n\n"
                        f"Le groupe/chat `{chat_id}` est introuvable ou inaccessible.\n"
                        f"Vérifiez que c'est bien un groupe ou canal, et que votre compte y est membre.\n\n"
                        f"➡️ Menu → ➕ Ajouter à un groupe/canal pour reconfigurer."))
                except Exception:
                    pass
                break
            logger.error(f"_grp_publisher uid={uid} chat={chat_id} role={role}: {e}")
            # Erreur de connexion → arrêter
            if "disconnected" in err_s or "flood" in err_s:
                break
            await asyncio.sleep(60)


# ═══════════════════════════════════════════════════════════════════════════════
#  USERBOT PAR UTILISATEUR (tâche asyncio indépendante)
# ═══════════════════════════════════════════════════════════════════════════════

async def _run_user_telethon(uid: int):
    """Lance et gère le client Telethon pour un utilisateur enregistré."""
    from telethon import TelegramClient, events
    from telethon.sessions import StringSession

    uid_str   = str(uid)
    user_data = get_user_data(uid)
    if not user_data or user_data.get("blocked"):
        return

    session  = user_data.get("session", "")
    api_id   = user_data.get("api_id", "")
    api_hash = user_data.get("api_hash", "")
    if not all([session, api_id, api_hash]):
        return

    existing = _USER_TELETHON.get(uid_str)
    if existing:
        try:
            if existing.is_connected():
                return
        except Exception:
            pass

    try:
        client = TelegramClient(StringSession(session), int(api_id), api_hash)
        await client.start()
        _USER_TELETHON[uid_str] = client
        tg_name = user_data.get("tg_name", str(uid))
        logger.info(f"✅ Userbot démarré — uid={uid} ({tg_name})")

        # ── Sauvegarder le prénom réel de l'utilisateur dans son config ──────
        try:
            _me_info = await client.get_me()
            _uc = load_uc_config(uid)
            if not _uc.get("user_name"):
                _uc["user_name"]     = getattr(_me_info, "first_name", "") or tg_name
                _uc["user_username"] = getattr(_me_info, "username",   "") or ""
                save_uc_config(uid, _uc)
                logger.info(f"  user_name sauvegardé : {_uc['user_name']}")
        except Exception as _err:
            logger.debug(f"get_me() user_name: {_err}")

        @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
        async def _on_msg(event):
            if user_blocked(uid):
                return
            ctx = get_ctx(uid)
            cfg = ctx["config"]
            if not cfg.get("auto_reply_enabled", False):
                return
            sender = await event.get_sender()
            if not sender or getattr(sender, "bot", False):
                return
            raw = event.raw_text or ""
            if not raw.strip():
                return

            contact_id   = event.sender_id
            contact_name = getattr(sender, "first_name", str(contact_id)) or str(contact_id)
            sec          = ctx["sec_log"]

            if contact_id not in sec:
                sec[contact_id] = {"name": contact_name, "msgs": []}
            sec[contact_id]["name"] = contact_name
            sec[contact_id]["msgs"].append({"r": "in", "t": raw[:500], "d": benin_str()})
            if len(sec[contact_id]["msgs"]) > 200:
                sec[contact_id]["msgs"] = sec[contact_id]["msgs"][-200:]
            save_uc_sec(uid, sec)

            n_msgs  = len(sec[contact_id]["msgs"])
            ctype   = "first" if n_msgs <= 1 else "ongoing"

            today = str(date.today())
            if cfg.get("quota_date") != today:
                cfg["quota_used_today"] = 0
                cfg["quota_date"] = today
            if cfg.get("quota_used_today", 0) >= cfg.get("daily_quota", 200):
                return
            cfg["quota_used_today"] = cfg.get("quota_used_today", 0) + 1
            save_uc_config(uid, cfg)

            delay = cfg.get("reply_delay_seconds", 10) if n_msgs > 1 else cfg.get("delay_seconds", 30)
            await asyncio.sleep(delay)

            ch = ctx["conv_history"].setdefault(contact_id, [])
            ch.append({"role": "user", "content": raw})
            if len(ch) > 20:
                ctx["conv_history"][contact_id] = ch[-20:]

            weather_ctx = ""
            tl = raw.lower()
            if any(kw in tl for kw in _WEATHER_KEYWORDS):
                city = detect_city_in_text(raw, cfg.get("weather_default_city", "Cotonou"))
                wkey = cfg.get("openweathermap_key", "")
                loop2 = asyncio.get_event_loop()
                weather_ctx = await loop2.run_in_executor(
                    None, lambda: get_weather(city, api_key=wkey))

            style = sec[contact_id].get("style")
            sys_p = build_prompt(ctype, cfg, style=style, weather_ctx=weather_ctx)

            try:
                active_ai  = cfg.get("active_ai", "groq")
                ai_provs   = cfg.get("ai_providers", {})
                # Fallback vers les clés globales si l'utilisateur n'en a pas
                _global_ai = load_config().get("ai_providers", {})
                for _p, _pd in _global_ai.items():
                    if not ai_provs.get(_p, {}).get("keys"):
                        ai_provs.setdefault(_p, {})["keys"]  = _pd.get("keys", [])
                        ai_provs[_p]["model"] = _pd.get("model", AI_META.get(_p, {}).get("model", ""))
                ordered    = [active_ai] + [k for k in AI_LIST if k != active_ai]
                reply       = None
                key_expired = False
                for provider in ordered:
                    pdata = ai_provs.get(provider, {})
                    keys  = [k for k in pdata.get("keys", []) if k]
                    if not keys:
                        continue
                    model       = pdata.get("model", AI_META[provider]["model"])
                    _got_reply  = False
                    for _key in keys:
                        try:
                            reply = await ai_call(provider, _key, model, sys_p,
                                                  ctx["conv_history"][contact_id])
                            _got_reply = True
                            break
                        except Exception as ai_e:
                            err_s = str(ai_e).lower()
                            if any(kw in err_s for kw in ("invalid_api_key","expired","unauthorized","401","quota")):
                                key_expired = True
                                asyncio.ensure_future(_notify_user(uid,
                                    f"⚠️ *Clé IA expirée ou invalide* — Fournisseur : `{provider}`\n\n"
                                    f"Rendez-vous dans le menu → 🤖 Fournisseurs IA pour mettre à jour votre clé."))
                            continue
                    if _got_reply:
                        break

                if not reply:
                    return

                ctx["conv_history"][contact_id].append({"role": "assistant", "content": reply})
                sec[contact_id]["msgs"].append({"r": "out", "t": reply[:500], "d": benin_str()})
                save_uc_sec(uid, sec)

                await asyncio.sleep(max(1, cfg.get("delay_seconds", 2)))
                await event.reply(reply)

            except Exception as exc:
                logger.error(f"Erreur AI reply uid={uid}: {exc}")

        # ── Handler audio / voix (messages privés) ────────────────────────────
        @client.on(events.NewMessage(
            incoming=True,
            func=lambda e: e.is_private and bool(
                getattr(e.message, "voice", None) or
                getattr(e.message, "audio", None))))
        async def _on_audio_msg(event):
            if user_blocked(uid):
                return
            ctx  = get_ctx(uid)
            cfg  = ctx["config"]
            sender = await event.get_sender()
            if not sender or getattr(sender, "bot", False):
                return
            contact_id   = event.sender_id
            contact_name = getattr(sender, "first_name", str(contact_id)) or str(contact_id)
            sec = ctx["sec_log"]
            if contact_id not in sec:
                sec[contact_id] = {"name": contact_name, "msgs": []}
            sec[contact_id]["name"] = contact_name
            try:
                audio_bytes = await event.message.download_media(bytes=True)
                if not audio_bytes:
                    return
                # Clé Groq (globale en fallback)
                ai_provs  = cfg.get("ai_providers", {})
                _gcfg_ai  = load_config().get("ai_providers", {})
                groq_keys = (ai_provs.get("groq", {}).get("keys") or
                             _gcfg_ai.get("groq", {}).get("keys") or [])
                groq_key  = next((k for k in groq_keys if k), None)
                if not groq_key:
                    logger.warning(f"_on_audio_msg uid={uid}: pas de clé Groq pour Whisper")
                    return
                # Transcription Whisper via Groq (appel sync dans executor)
                def _transcribe():
                    from groq import Groq as _Groq
                    gc = _Groq(api_key=groq_key)
                    res = gc.audio.transcriptions.create(
                        file=("voice.ogg", audio_bytes, "audio/ogg"),
                        model="whisper-large-v3",
                        language="fr",
                    )
                    return res.text
                transcribed = await asyncio.get_event_loop().run_in_executor(None, _transcribe)
                if not transcribed or not transcribed.strip():
                    return
                transcribed = transcribed.strip()
                # Sauvegarder la transcription dans le secrétariat
                sec[contact_id]["msgs"].append({
                    "r": "audio_in",
                    "t": transcribed[:1000],
                    "d": benin_str(),
                    "audio": True,
                })
                if len(sec[contact_id]["msgs"]) > 200:
                    sec[contact_id]["msgs"] = sec[contact_id]["msgs"][-200:]
                save_uc_sec(uid, sec)
                logger.info(f"🎤 Audio transcrit — uid={uid} contact={contact_id}")
                # Notifier l'admin
                await _notify_user(uid,
                    f"🎤 *Audio reçu — {contact_name}*\n\n"
                    f"_{transcribed[:500]}_\n\n"
                    f"🕐 {benin_str()}")
            except Exception as _ae:
                logger.error(f"_on_audio_msg uid={uid}: {_ae}")

        # ── Handler groupe / canal ─────────────────────────────────────────────
        @client.on(events.NewMessage(incoming=True,
                                     func=lambda e: not e.is_private))
        async def _on_grp_msg(event):
            if user_blocked(uid):
                return
            chat_id_str = str(event.chat_id)
            grp_cfgs    = load_grp_configs(uid)
            gcfg        = grp_cfgs.get(chat_id_str)
            if not gcfg or gcfg.get("paused"):
                return
            roles  = gcfg.get("roles", [])
            raw    = event.raw_text or ""
            if not raw.strip():
                return
            sender = await event.get_sender()
            sender_name = getattr(sender, "first_name",
                                  getattr(sender, "title", "?")) or "?"
            # ── Apprentissage : stocker dans sec_log par groupe ────────────────
            u_sec       = load_uc_sec(uid)
            grp_key     = f"grp_{chat_id_str}"
            if grp_key not in u_sec:
                u_sec[grp_key] = {"name": gcfg.get("title", chat_id_str), "msgs": []}
            u_sec[grp_key]["msgs"].append({
                "r": "in", "a": sender_name, "t": raw[:500], "d": benin_str()
            })
            if len(u_sec[grp_key]["msgs"]) > 500:
                u_sec[grp_key]["msgs"] = u_sec[grp_key]["msgs"][-500:]
            save_uc_sec(uid, u_sec)
            # Mettre à jour compteur bilan
            grp_cfgs[chat_id_str]["bilan"] = grp_cfgs[chat_id_str].get("bilan", {})
            grp_cfgs[chat_id_str]["bilan"]["msgs_appris"] = \
                grp_cfgs[chat_id_str]["bilan"].get("msgs_appris", 0) + 1
            save_grp_configs(uid, grp_cfgs)

            # ── Rôle "discuter" : répondre aux mentions / réponses ─────────────
            if "discuter" not in roles:
                return
            me      = await client.get_me()
            my_id   = me.id
            my_name = (me.username or "").lower()
            # Détecte mention ou reply à un message du bot
            is_mention = my_name and f"@{my_name}" in raw.lower()
            is_reply_to_me = False
            if event.reply_to_msg_id:
                try:
                    replied = await event.get_reply_message()
                    if replied and replied.sender_id == my_id:
                        is_reply_to_me = True
                except Exception:
                    pass
            if not is_mention and not is_reply_to_me:
                return

            ctx     = get_ctx(uid)
            cfg_u   = ctx["config"]
            # Construire contexte depuis les derniers messages du groupe
            recent_grp = u_sec.get(grp_key, {}).get("msgs", [])[-20:]
            grp_context = "\n".join(
                f"{m.get('a','?')}: {m.get('t','')}" for m in recent_grp)
            grp_info_txt = gcfg.get("group_info", "")
            grp_info_block = (
                f"\nSujet/contexte défini par l'administrateur du groupe : {grp_info_txt}\n"
                if grp_info_txt else ""
            )
            grp_sys = (
                f"Tu participes à un groupe/canal Telegram nommé '{gcfg.get('title', '')}'. "
                f"Tu dois t'exprimer naturellement dans ce groupe, comme un membre actif. "
                f"Ne te présente jamais comme un bot ou une IA. "
                f"Réponds de façon courte, engageante, en accord avec le sujet du groupe. "
                f"{grp_info_block}"
                f"Voici le contexte récent du groupe :\n{grp_context}\n\n"
                f"Réponds uniquement au dernier message qui te mentionne ou te répond."
            )
            ch_grp = ctx["conv_history"].setdefault(f"grp_{chat_id_str}", [])
            ch_grp.append({"role": "user", "content": f"{sender_name}: {raw}"})
            if len(ch_grp) > 15:
                ctx["conv_history"][f"grp_{chat_id_str}"] = ch_grp[-15:]

            active_ai = cfg_u.get("active_ai", "groq")
            ai_provs  = cfg_u.get("ai_providers", {})
            # Fallback vers les clés globales si l'utilisateur n'en a pas
            _global_ai2 = load_config().get("ai_providers", {})
            for _p2, _pd2 in _global_ai2.items():
                if not ai_provs.get(_p2, {}).get("keys"):
                    ai_provs.setdefault(_p2, {})["keys"]  = _pd2.get("keys", [])
                    ai_provs[_p2]["model"] = _pd2.get("model", AI_META.get(_p2, {}).get("model", ""))
            ordered   = [active_ai] + [k for k in AI_LIST if k != active_ai]
            grp_reply = None
            for provider in ordered:
                pdata      = ai_provs.get(provider, {})
                keys       = [k for k in pdata.get("keys", []) if k]
                if not keys:
                    continue
                model      = pdata.get("model", AI_META[provider]["model"])
                _got_grp   = False
                for _key2 in keys:
                    try:
                        grp_reply = await ai_call(provider, _key2, model, grp_sys,
                                                  ctx["conv_history"][f"grp_{chat_id_str}"])
                        _got_grp = True
                        break
                    except Exception as ai_e2:
                        err_s = str(ai_e2).lower()
                        if any(kw in err_s for kw in ("invalid_api_key","expired","unauthorized","401","quota")):
                            asyncio.ensure_future(_notify_user(uid,
                                f"⚠️ *Clé IA expirée* — Fournisseur : `{provider}`\n"
                                f"Mettez à jour votre clé dans le menu → 🤖 Fournisseurs IA"))
                        continue
                if _got_grp:
                    break

            if not grp_reply:
                return
            ctx["conv_history"][f"grp_{chat_id_str}"].append(
                {"role": "assistant", "content": grp_reply})
            await asyncio.sleep(2)
            try:
                await event.reply(grp_reply)
                grp_cfgs = load_grp_configs(uid)
                if str(chat_id_str) in grp_cfgs:
                    grp_cfgs[str(chat_id_str)]["bilan"]["msgs_envoyes"] = \
                        grp_cfgs[str(chat_id_str)]["bilan"].get("msgs_envoyes", 0) + 1
                    save_grp_configs(uid, grp_cfgs)
            except Exception as rep_e:
                logger.error(f"grp reply uid={uid}: {rep_e}")

        # ── Démarrer les tâches de publication planifiée ───────────────────────
        _trigger_grp_handlers(uid)

        await client.run_until_disconnected()

    except Exception as exc:
        logger.error(f"Erreur Telethon uid={uid}: {exc}")
        _USER_TELETHON.pop(uid_str, None)


# ═══════════════════════════════════════════════════════════════════════════════
#  POINT D'ENTRÉE
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    _cp = {}
    try:
        import config as _cfg_mod
        _cp = {k: getattr(_cfg_mod, k, "") for k in (
            "TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_BOT_TOKEN",
            "ADMIN_ID", "PHONE_NUMBER", "GROQ_API_KEY", "TELEGRAM_SESSION")}
    except Exception:
        pass

    cfg          = load_config()
    PHONE_NUMBER = _get(cfg, "PHONE_NUMBER", "phone_number",
                        str(_cp.get("PHONE_NUMBER", "") or ""))
    OWNER_ID     = SUPER_ADMIN_ID
    API_ID       = int(_get(cfg, "TELEGRAM_API_ID", "telegram_api_id",
                            str(_cp.get("TELEGRAM_API_ID", "") or "29177661")))
    API_HASH     = _get(cfg, "TELEGRAM_API_HASH", "telegram_api_hash",
                        str(_cp.get("TELEGRAM_API_HASH", "") or "a8639172fa8d35dbfd8ea46286d349ab"))
    BOT_TOKEN    = MULTI_BOT_TOKEN
    GROQ_API_KEY = _get(cfg, "GROQ_API_KEY", "groq_api_key",
                        str(_cp.get("GROQ_API_KEY", "") or ""))

    SESSION_STRING = _get(cfg, "TELEGRAM_SESSION", "telegram_session",
                          str(_cp.get("TELEGRAM_SESSION", "") or "")).strip()

    if not SESSION_STRING and os.path.exists(SESSION_FILE):
        SESSION_STRING = Path(SESSION_FILE).read_text().strip()
        if SESSION_STRING:
            logger.info("📄 Session admin chargée depuis session.txt")

    if SESSION_STRING:
        try:
            from telethon.sessions import StringSession as _SS
            _SS(SESSION_STRING)
        except Exception:
            logger.warning("⚠️ Session admin invalide, abandon.")
            SESSION_STRING = ""

    if not API_ID or not API_HASH:
        raise ValueError("TELEGRAM_API_ID et TELEGRAM_API_HASH requis.")

    start_health_server()

    logger.info(f"🚀 Plateforme multi-utilisateurs — bot token: {BOT_TOKEN[:20]}...")

    if SESSION_STRING:
        logger.info("✅ Session admin chargée → Mode USERBOT complet")
    else:
        logger.info("ℹ️ Pas de session admin — Démarrage en mode inscription (bot PTB actif)")
    run_userbot(API_ID, API_HASH, BOT_TOKEN, GROQ_API_KEY, SESSION_STRING, OWNER_ID)
