# === Imports (clean) ===
import os, re, ssl, json, time, math, smtplib, secrets, unicodedata, mimetypes, hashlib, threading
from io import BytesIO
from pathlib import Path
from datetime import datetime, timedelta, date
from collections import defaultdict
from urllib.parse import urlparse, parse_qs, urljoin

from flask import (
    Flask, render_template, request, redirect, url_for, flash, g, jsonify,
    session, send_from_directory, Response
)
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from PIL import Image, ImageOps
from deep_translator import GoogleTranslator
import requests
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect, CSRFError, generate_csrf

from threading import Lock
from services.ai_writer import generate_draft
from services.ai_variants import list_variants, assign_variant

import mimetypes



load_dotenv()

# === Google Sheets webhook sync (for reviews) ===
GOOGLE_WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbwmZsRz_qU9oX7Kl_4G19CZHM2eRw9fqs5r01zNSB_ZCFiZAS_sH4LgjzeMTXyMA9QikQ/exec"
GOOGLE_WEBHOOK_SECRET = os.environ.get("GOOGLE_WEBHOOK_SECRET", "")

# === Locks ===
REVIEWS_JSON_LOCK = Lock()


# ------------------------------
# קבועים כלליים (שפה/בניית קישורי סטטיק)
# ------------------------------
SUPPORTED_LANGS = ("he", "en", "ru")   # בשימוש ב-smart_alias וב-sitemap
SMART_ALIAS_RESERVED = {
    "estimate": "estimate",
}
ASSETS_V = os.environ.get("ASSETS_V", "1055")  # גרסת נכסים (cache-busting)


# ------------------------------
# קבועים ותיקיות
# ------------------------------
TRANSLATIONS_FOLDER = os.path.join(os.path.dirname(__file__), 'translations')

# בסיס הפרויקט: התיקייה שבה נמצא קובץ זה
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = str(BASE_DIR / 'static')

# תיקיית הנתונים – בתוך הפרויקט (data)
DATA_FOLDER = str(BASE_DIR / 'data')

# === Analytics (אירועים) ===
ANALYTICS_DIR = os.path.join(DATA_FOLDER, 'analytics')
os.makedirs(ANALYTICS_DIR, exist_ok=True)

# קובצי pending ו-approved שמאחסנים בקשות ועובדים מאושרים
PENDING_FILE = os.path.join(DATA_FOLDER, 'pending.json')
APPROVED_FILE = os.path.join(DATA_FOLDER, 'approved.json')

# תיקיית ההעלאות (תמונות/וידאו) בתוך static/upload_pending
UPLOAD_FOLDER = str(BASE_DIR / 'static' / 'upload_pending')

# קריאת כתובת המייל וסיסמאות ממשתני סביבה
EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS', '')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', '')  # סיסמת אפליקציה

# --- Admin Login ---
# סיסמת מנהל מוגדרת במשתנה סביבה ADMIN_PASSWORD
ADMIN_PASSWORD_HASH = os.environ.get('ADMIN_PASSWORD_HASH', '')

# יצירת התיקיות במידת הצורך
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DATA_FOLDER, exist_ok=True)

# וידאו – נשמור תחת static/upload_pending/videos
VIDEO_UPLOAD_SUBDIR = os.path.join(UPLOAD_FOLDER, 'videos')
os.makedirs(VIDEO_UPLOAD_SUBDIR, exist_ok=True)
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm', 'ogg'}
MAX_VIDEO_MB = 50  # רף רך – אופציונלי

# דומיין בסיס של האתר (בפרודקשן עדכן לדומיין הסופי)
BASE_DOMAIN = os.environ.get('BASE_DOMAIN', 'https://baley-mikzoa.co.il')

INVITE_KEY = os.environ.get('INVITE_KEY', 'dev-invite')

# --- OG target languages ---
OG_LANGS = ("he", "en", "ru")

# ------------------------------
# נתוני ערים
# ------------------------------
cities_coords = {
    "תל אביב": (32.0853, 34.7818),
    "ירושלים": (31.7683, 35.2137),
    "חיפה": (32.7940, 34.9896),
    "באר שבע": (31.2518, 34.7913),
    "פתח תקווה": (32.0840, 34.8878),
    "נתניה": (32.3326, 34.8593),
    "אשדוד": (31.8014, 34.6439),
    "ראשון לציון": (31.9574, 34.7997),
}

# ------------------------------
# מיפויים שפות
# ------------------------------
field_map_en_to_he = {
    "renovations": "שיפוצים",
    "plumbers": "אינסטלטורים",
    "electricians": "חשמלאים",
    "locksmiths": "מנעולנים",
}
city_map_en_to_he = {
    "tel aviv": "תל אביב",
    "jerusalem": "ירושלים",
    "haifa": "חיפה",
    "beer sheva": "באר שבע",
}

# ------------------------------
# שדות – רוסית
# ------------------------------
field_map_ru_to_he = {
    "ремонт": "שיפוצים",
    "ремонты": "שיפוצים",  # רבים
    "сантехник": "אינסטלטורים",
    "сантехники": "אינסטלטורים",  # רבים
    "электрики": "חשמלאים",
    "электрик": "חשמלאים",  # יחיד
    "слесарь": "מנעולנים",
    "слесари": "מנעולנים",  # רבים
}

# ------------------------------
# ערים – רוסית
# ------------------------------
city_map_ru_to_he = {
    "тель авив": "תל אביב",
    "тель-авив": "תל אביב",  # עם מקף
    "иерусалим": "ירושלים",
    "хаифа": "חיפה",
    "беэр шева": "באר שבע",
    "беэр-шева": "באר שבע",  # עם מקף
}

# -------- היפוך מפות: HE -> EN/RU --------
field_map_he_to_en = {he: en for en, he in field_map_en_to_he.items()}
field_map_he_to_ru = {}
for ru, he in field_map_ru_to_he.items():
    field_map_he_to_ru.setdefault(he, ru)
city_map_he_to_en = {he: en for en, he in city_map_en_to_he.items()}
city_map_he_to_ru = {}
for ru, he in city_map_ru_to_he.items():
    city_map_he_to_ru.setdefault(he, ru)






# ---- קנוניזציה של תחומים + תרגומים קבועים ----
CANON_FIELDS_HE = ("שיפוצים", "אינסטלטורים", "חשמלאים", "מנעולנים")

FIELD_I18N = {
    "שיפוצים":      {"he": "שיפוצים",      "en": "Renovations",  "ru": "ремонт"},
    "אינסטלטורים":  {"he": "אינסטלטורים",  "en": "Plumbers",     "ru": "сантехники"},
    "חשמלאים":      {"he": "חשמלאים",      "en": "Electricians",  "ru": "электрики"},
    "מנעולנים":     {"he": "מנעולנים",     "en": "Locksmiths",    "ru": "слесари"},
}

def _canon_he_field(s: str) -> str:
    """מאחד יחיד/רבים/וריאציות לעברית-רבים הקנונית באתר."""
    s = (s or "").strip()
    mapping = {
        "חשמלאי": "חשמלאים", "חשמלאים": "חשמלאים",
        "אינסטלטור": "אינסטלטורים", "אינסטלטורים": "אינסטלטורים",
        "שיפוצניק": "שיפוצים", "שיפוצים": "שיפוצים",
        "מנעולן": "מנעולנים", "מנעולנים": "מנעולנים",
    }
    return mapping.get(s, s)

def normalize_worker_fields(w: dict) -> dict:
    """
    דואג ש־field בעברית יהיה קנוני-ברבים, ושדות התרגום ימולאו/יתוקנו לפי המיפוי.
    משנה את המילון במקום ומחזיר אותו.
    """
    he = _canon_he_field(w.get("field") or w.get("field_he") or "")
    if not he:
        return w
    i18n = FIELD_I18N.get(he, {"he": he, "en": he, "ru": he})
    w["field"]    = i18n["he"]
    w["field_en"] = i18n["en"]
    w["field_ru"] = i18n["ru"]
    return w


# === NEW: מעשיר אובייקט עובד לעמוד הפרופיל ===
def enrich_worker_for_profile(w: dict, lang: str = "he") -> dict:
    # תיאור ארוך: סדר עדיפויות כך שתמיד יהיה טקסט מלא
    long_bio = (
        w.get("description_long")
        or w.get("bio_full")
        or w.get("description")
        or w.get("about_long")
        or w.get("about")
        or w.get("ai_draft_bio")
        or ""
    )
    w["about"] = (long_bio or "").strip()

    # “מה אני עושה” – ניקח כל מה שקיים: services_list/ai_draft_services/sub_services
    services = (
        w.get("specializations")
        or w.get("services_list")
        or w.get("ai_draft_services")
        or w.get("sub_services")
        or []
    )
    w["specializations"] = [s.strip() for s in services if isinstance(s, str) and s.strip()]

    # איזורי שירות – אם לא קיים, ניפול ל-active_cities + עיר בסיס (ללא כפילויות)
    if not w.get("service_areas"):
        areas = list(dict.fromkeys((w.get("active_cities") or []) + ([w.get("base_city")] if w.get("base_city") else [])))
        w["service_areas"] = [a for a in areas if a]

    # טקסט ניסיון
    exp = int(w.get("experience") or 0)
    if exp:
        if lang == "he":
            w["experience_text"] = f"{exp} שנות ניסיון"
        elif lang == "en":
            w["experience_text"] = f"{exp} years of experience"
        else:
            w["experience_text"] = f"{exp} лет опыта"

    return w


def localize_field_slug(he_value, lang):
    """מקבל תחום בעברית ומחזיר סלג (kebab-case) בשפת ה־UI"""
    if not he_value:
        return 'all'
    if lang == 'en':
        out = field_map_he_to_en.get(he_value, he_value)
    elif lang == 'ru':
        out = field_map_he_to_ru.get(he_value, he_value)
    else:
        out = he_value  # he
    return to_kebab_slug(out)


def localize_city_slug(he_value, lang):
    """מקבל עיר בעברית ומחזיר סלג (kebab-case) בשפת ה־UI"""
    if not he_value:
        return None
    if lang == 'en':
        out = city_map_he_to_en.get(he_value, he_value)
    elif lang == 'ru':
        out = city_map_he_to_ru.get(he_value, he_value)
    else:
        out = he_value  # he
    return to_kebab_slug(out)


def localize_service_slug(service_key: str, lang: str) -> str:
    meta = SERVICE_REGISTRY.get(service_key, {})
    label = meta.get(lang) or meta.get("he") or service_key
    return to_kebab_slug(label)


# ------------------------------
# עזרי קריאה/כתיבה קבצים
# ------------------------------
def read_json_file(path):
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def write_json_file(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ------------------------------
# פונקציות עזר
# ------------------------------


# ------------------------------
# AI Draft: עזרי וריאנטים (דפדוף בטיוטה)
# ------------------------------
def _pre_worker_id(item: dict) -> str:
    """
    מזהה יציב לפנדינג (לפני שיש worker_id אמיתי):
    name|company|phone|field -> md5[:12]
    """
    src = f"{item.get('name','')}|{item.get('company_name','')}|{item.get('phone','')}|{item.get('field','')}"
    return hashlib.md5(src.encode('utf-8','ignore')).hexdigest()[:12]

def _bump_variant_cursor(pre_id: str, total: int = 7) -> int:
    """
    כל קליק על 'צור טיוטת AI' מקדם את המצביע (cursor) ומחזיר את האינדקס הבא (0..total-1).
    נשמר ב-session כדי שיעבדו כמה אדמינים במקביל בלי קונפליקטים בקבצים.
    """
    cursors = session.get("ai_vcur", {})
    i = int(cursors.get(pre_id, -1))
    i = (i + 1) % max(1, total)
    cursors[pre_id] = i
    session["ai_vcur"] = cursors
    session.modified = True
    return i




def _safe_url(endpoint, **values):
    """
    url_for בטוח: מזריק lang, משתמש ב-url_for_lang אם קיים, ולא זורק חריגה.
    """
    lang = getattr(g, "current_lang", None) or (request.view_args.get("lang") if request.view_args else None)
    if lang:
        values.setdefault("lang", lang)
    # נסה url_for_lang אם מוגדר בפרויקט
    try:
        if 'url_for_lang' in globals() and callable(globals().get('url_for_lang')):
            return url_for_lang(endpoint, **values)
    except Exception:
        pass
    # נפילה ל-url_for רגיל
    try:
        return url_for(endpoint, **values)
    except Exception:
        return None


def build_breadcrumb_ctx(worker: dict, lang: str = "he") -> dict:
    """
    Home › <CategoryLabel> / <CityLabel> › <WorkerName>
    מקורות לקטגוריה/עיר: session → request.args → שדות worker (fallback).
    הקישור לקטגוריה/עיר מצביע לעמוד הרשימה (show_workers) אם אפשר.
    """
    # --- labels (מוצגות למשתמש) ---
    cat_label = (
        session.get("last_search_category_label")
        or request.args.get("category_label")
        or worker.get("field_display")
        or worker.get("field_translated")
        or worker.get("field")
    )
    city_label = (
        session.get("last_search_city_label")
        or request.args.get("city_label")
        or worker.get("city")
        or worker.get("base_city")
    )

    # --- slugs (לינקים אחורה לעמוד הרשימה) ---
    cat_slug = (
        session.get("last_search_category_slug")
        or request.args.get("category")
        or (worker.get("field") and localize_field_slug(worker.get("field"), lang))
    )
    city_slug = (
        session.get("last_search_city_slug")
        or request.args.get("city")
        or (worker.get("base_city") and localize_city_slug(worker.get("base_city"), lang))
    )

    # --- crumbs ---
    home = {"label": "דף הבית", "href": _safe_url("home")}
    cat_city = None
    if cat_label:
        label = f"{cat_label}" + (f" / {city_label}" if city_label else "")
        href = None
        try:
            href = _safe_url("show_workers", field=cat_slug, area=city_slug)  # העמוד שלך לרשימות
        except Exception:
            href = None
        cat_city = {"label": label, "href": href}

    worker_name = worker.get("company_name") or worker.get("name") or "פרופיל עובד"

    return {"home": home, "cat_city": cat_city, "worker": {"label": worker_name}}





def slugify(value):
    """ממיר מחרוזת לכל אותיות קטנות, מחליף רווחים ב-dash ומסיר תווים מיוחדים"""
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    value = re.sub(r'[-\s]+', '-', value)
    return value


def deslugify(slug, lang_map):
    """ממיר slug חזרה לשם המקורי לפי מפה נתונה"""
    for name, original in lang_map.items():
        if slugify(name) == slug:
            return original
    return slug


def format_phone(phone):
    if not phone:
        return ''
    phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    if phone.startswith('0'):
        phone = '+972' + phone[1:]
    return phone


def normalize_slug(text):
    if not text:
        return None
    text = text.strip().lower()
    # להתייחס גם ל־- וגם ל־_ כרווחים
    text = re.sub(r'[_\-\u05BE\u2013\u2014]+', ' ', text)
    # לצמצם רווחים מרובים
    text = re.sub(r'\s+', ' ', text)
    # להשאיר רק אותיות/ספרות/רווחים: לטיני + עברית + רוסית
    text = re.sub(r'[^0-9a-z\u0590-\u05FF\u0400-\u04FF\s]', '', text)
    return text


def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # רדיוס כדור הארץ בק"מ
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def get_cities_in_radius(base_city, radius_km):
    if base_city not in cities_coords:
        return []
    base_lat, base_lon = cities_coords[base_city]
    cities_in_range = []
    for city, (lat, lon) in cities_coords.items():
        if haversine(base_lat, base_lon, lat, lon) <= radius_km:
            cities_in_range.append(city)
    return cities_in_range


def get_latest_review(worker_id, lang='he'):
    reviews_file = os.path.join(DATA_FOLDER, 'worker_reviews.json')
    if not os.path.exists(reviews_file):
        return None
    try:
        with open(reviews_file, 'r', encoding='utf-8') as f:
            all_reviews = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return None
    worker_reviews = [r for r in all_reviews if str(r.get('worker_id')) == str(worker_id)]
    if not worker_reviews:
        return None
    worker_reviews.sort(key=lambda x: x.get('date', ''), reverse=True)
    latest = worker_reviews[0]
    # אם יש תרגומים שמורים ב־JSON
    if 'translations' in latest and lang in latest['translations']:
        latest['text'] = latest['translations'][lang]
    return latest


def get_all_reviews(worker_id, lang=None):
    """ מחזיר את כל הביקורות עבור עובד לפי worker_id. פרמטר lang נשמר כדי להתאים לקריאות קיימות אך אינו בשימוש. """
    reviews_file = os.path.join(DATA_FOLDER, 'worker_reviews.json')
    if not os.path.exists(reviews_file):
        return []
    try:
        with open(reviews_file, 'r', encoding='utf-8') as f:
            all_reviews = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []
    # השוואה כ-string כדי למנוע בעיות עם סוגי נתונים שונים
    worker_id_str = str(worker_id)
    return [r for r in all_reviews if str(r.get('worker_id')) == worker_id_str]


def translate_review(text, source_lang='he', target_langs=['en','ru']):
    """ מקבלת טקסט בעברית ומחזירה מילון עם כל השפות הרצויות.
    text: מחרוזת הביקורת
    source_lang: שפת המקור ('iw' עבור עברית)
    target_langs: רשימת שפות לתרגום
    """
    translations = { 'he': text }  # תמיד שומר את המקור בעברית
    for lang in target_langs:
        try:
            translated = GoogleTranslator(source=source_lang, target=lang).translate(text)
            translations[lang] = translated
        except Exception as e:
            # במקרה של שגיאה, נשאיר את המקור
            translations[lang] = text
    return translations



def sync_review_to_sheets(new_review: dict, lang="he"):
    """
    שולח את הביקורת לשורה ב-Google Sheets (Webhook) כולל תרגומים (he/en/ru).
    """
    text_he = (new_review.get("translations", {}) or {}).get("he") or new_review.get("text") or ""
    # אם אין תרגומים מוכנים – נתרגם כאן, בעדינות עם try/except
    text_en = (new_review.get("translations", {}) or {}).get("en")
    text_ru = (new_review.get("translations", {}) or {}).get("ru")

    if not text_en:
        try:
            text_en = GoogleTranslator(source="iw", target="en").translate(text_he)
        except Exception:
            text_en = text_he
    if not text_ru:
        try:
            text_ru = GoogleTranslator(source="iw", target="ru").translate(text_he)
        except Exception:
            text_ru = text_he

    payload = {
        "secret": GOOGLE_WEBHOOK_SECRET,
        "review_id": new_review.get("review_id"),
        "worker_id": new_review.get("worker_id"),
        "author": new_review.get("author"),
        "rating": new_review.get("rating"),
        "title": new_review.get("title", ""),
        "text": text_he,
        "lang": "he",
        "source": "site",
        "text_en": text_en,
        "text_ru": text_ru,
    }

    try:
        requests.post(GOOGLE_WEBHOOK_URL, json=payload, timeout=5)
    except Exception as e:
        print("Sheets sync failed:", e)




def allowed_video_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_VIDEO_EXTENSIONS


def is_safe_url(target):
    """וולידציה שכתובת חזרה (next) מצביעה לאותו דומיין/פרוטוקול"""
    test = urlparse(urljoin(request.host_url, target))
    return test.scheme in ("http", "https") and test.netloc == urlparse(request.host_url).netloc


def to_kebab_slug(s):
    if not s:
        return None
    s = s.strip().lower()
    # רווחים/קו תחתי -> מקף
    s = re.sub(r'[\s_\u05BE\u2013\u2014]+', '-', s)
    # להשאיר אותיות לטיניות/מספרים/קווים/עברית/רוסית
    s = re.sub(r'[^-\w\u0400-\u04FF\u0590-\u05FF]', '', s)
    # ניקוי מקפים כפולים וקצוות
    s = re.sub(r'-{2,}', '-', s).strip('-')
    return s


def _analytics_daily_path(dt=None):
    dt = dt or datetime.utcnow()
    return os.path.join(ANALYTICS_DIR, dt.strftime('%Y-%m-%d') + '.jsonl')


def log_analytics_event(event: str, worker_id: str, page_path: str = None) -> bool:
    """ רושם אירוע לוג יומי ב-JSON Lines.
    - צפיות בפרופיל (view) נספרות פעם ב-30 דק' פר סשן לעובד.
    - קליקים נספרים תמיד.
    """
    if not worker_id:
        return False

    if event == 'view':
        last_views = session.get('last_views', {})
        now = time.time()
        key = f'v:{worker_id}'
        prev = last_views.get(key, 0)
        if now - prev < 30 * 60:
            return False
        last_views[key] = now
        session['last_views'] = last_views

    rec = {
        "ts": datetime.utcnow().isoformat(timespec='seconds') + 'Z',
        "event": event,
        "worker_id": str(worker_id),
        "sid": session.get('sid'),
        "ua": request.headers.get('User-Agent', '')[:200],
        "path": page_path or request.path
    }
    try:
        with open(_analytics_daily_path(), 'a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        return True
    except Exception:
        return False



def _norm_alias(s: str) -> str:
    s = normalize_slug(s or "")
    # הופך רווחים למקף כדי להשוות כמו slug
    s = re.sub(r"\s+", "-", s.strip())
    return s

# --- נרדפים לתחומים (key=צורת החיפוש כפי שמקלידים; value=שם קנוני בעברית) ---
_FIELD_ALIASES_RAW = {
    "he": {
        "שיפוצניק": "שיפוצים", "שיפוץ": "שיפוצים", "קבלן-שיפוצים": "שיפוצים",
        "אינסטלטור": "אינסטלטורים", "אינסטלציה": "אינסטלטורים", "שרברב": "אינסטלטורים",
        "חשמלאי": "חשמלאים", "חשמל": "חשמלאים",
        "מנעולן": "מנעולנים", "פריצה-לדלת": "מנעולנים",
    },
    "en": {
        "renovation": "שיפוצים", "renovations": "שיפוצים", "remodeling": "שיפוצים",
        "contractor": "שיפוצים", "renovation-contractor": "שיפוצים",
        "plumber": "אינסטלטורים", "plumbing": "אינסטלטורים", "plumbers": "אינסטלטורים",
        "drain-cleaning": "אינסטלטורים", "clog": "אינסטלטורים",
        "electrician": "חשמלאים", "electricians": "חשמלאים", "electrical": "חשמלאים",
        "locksmith": "מנעולנים", "locksmiths": "מנעולנים", "lock-opening": "מנעולנים",
    },
    "ru": {
        "ремонт": "שיפוצים", "ремонты": "שיפוצים", "ремонт-квартир": "שיפוצים", "отделка": "שיפוצים",
        "сантехник": "אינסטלטורים", "сантехники": "אינסטלטורים", "сантехника": "אינסטלטורים",
        "засор": "אינסטלטורים", "прочистка": "אינסטלטורים",
        "электрик": "חשמלאים", "электрики": "חשמלאים", "электромонтаж": "חשמלאים",
        "слесарь": "מנעולנים", "вскрытие-замков": "מנעולנים",
    },
}

# --- נרדפים לערים (value=שם קנוני בעברית לפי cities_coords שלך) ---
_CITY_ALIASES_RAW = {
    "he": {
        "תל-אביב": "תל אביב", "ת״א": "תל אביב",
        "ראשלצ": "ראשון לציון", "רשלצ": "ראשון לציון","תלאביב": "תל אביב",
    },
    "en": {
        "tel-aviv": "תל אביב", "telaviv": "תל אביב",
        "jerusalem": "ירושלים",
        "beer-sheva": "באר שבע", "beersheba": "באר שבע",
        "haifa": "חיפה",
        "rishon-lezion": "ראשון לציון", "rishon-le-zion": "ראשון לציון",
        "petah-tikva": "פתח תקווה", "petach-tikva": "פתח תקווה",
        "netanya": "נתניה",
        "ashdod": "אשדוד",
    },
    "ru": {
        "тель-авив": "תל אביב", "тель авив": "תל אביב",
        "иерусалим": "ירושלים",
        "беэр-шева": "באר שבע", "беэр шева": "באר שבע",
        "хаифа": "חיפה",
        "ришон-лецион": "ראשון לציון", "ришон лецион": "ראשון לציון",
        "петах-тиква": "פתח תקווה", "петах тиква": "פתח תקווה",
        "нетания": "נתניה",
        "ашдод": "אשדוד",
    },
}

# === STEP 1a: enrich _FIELD_ALIASES_RAW aggressively (HE/EN/RU) ===
_FIELD_ALIASES_RAW["he"].update({
    # אינסטלטורים
    "סתימה": "אינסטלטורים", "פתיחת סתימות": "אינסטלטורים", "נזילה": "אינסטלטורים",
    "תיקון נזילות": "אינסטלטורים", "צנרת": "אינסטלטורים", "התקנת ברז": "אינסטלטורים",
    "ברז": "אינסטלטורים", "דוד מים": "אינסטלטורים", "דוד": "אינסטלטורים",
    "ביוב": "אינסטלטורים", "שאיבת סתימה": "אינסטלטורים",
    # חשמלאים
    "קצר חשמל": "חשמלאים", "קצר": "חשמלאים", "לוח חשמל": "חשמלאים",
    "התקנת תאורה": "חשמלאים", "תאורה": "חשמלאים", "שקע": "חשמלאים",
    "החלפת שקע": "חשמלאים", "חיווט": "חשמלאים",
    # שיפוצים
    "צבע": "שיפוצים", "צביעה": "שיפוצים", "קרמיקה": "שיפוצים", "רצף": "שיפוצים",
    "שבירת קיר": "שיפוצים", "חיפוי": "שיפוצים", "גבס": "שיפוצים",
    # מנעולנים
    "פריצת דלת": "מנעולנים", "פתיחת דלת": "מנעולנים", "צילינדר": "מנעולנים",
    "החלפת צילינדר": "מנעולנים", "שכפול מפתחות": "מנעולנים", "מנעול תקוע": "מנעולנים",
})

_FIELD_ALIASES_RAW["en"].update({
    # Plumbers
    "drain": "אינסטלטורים", "drain cleaning": "אינסטלטורים", "unclogging": "אינסטלטורים",
    "clog": "אינסטלטורים", "clogged drain": "אינסטלטורים",
    "leak": "אינסטלטורים", "leak repair": "אינסטלטורים",
    "pipe": "אינסטלטורים", "faucet": "אינסטלטורים",
    "faucet installation": "אינסטלטורים", "water heater": "אינסטלטורים",
    "sewer": "אינסטלטורים",
    # Electricians
    "short circuit": "חשמלאים", "breaker": "חשמלאים", "tripped breaker": "חשמלאים",
    "outlet": "חשמלאים", "replace outlet": "חשמלאים",
    "install light": "חשמלאים", "lighting": "חשמלאים", "panel": "חשמלאים",
    # Renovations
    "painting": "שיפוצים", "tiling": "שיפוצים", "drywall": "שיפוצים",
    "bathroom remodel": "שיפוצים",
    # Locksmiths
    "door opening": "מנעולנים", "unlock door": "מנעולנים", "lock": "מנעולנים",
    "locksmith": "מנעולנים", "key duplication": "מנעולנים",
    "cylinder replacement": "מנעולנים",
})

_FIELD_ALIASES_RAW["ru"].update({
    # Сантехники
    "засор": "אינסטלטורים", "прочистка": "אינסטלטורים", "устранение засора": "אינסטלטורים",
    "протечка": "אינסטלטורים", "ремонт течи": "אינסטלטורים", "труба": "אינסטלטורים",
    "смеситель": "אינסטלטורים", "водонагреватель": "אינסטלטורים",
    # Электрики
    "короткое замыкание": "חשמלאים", "автомат": "חשמלאים", "щиток": "חשמלאים",
    "розетка": "חשמלאים", "освещение": "חשמלאים", "проводка": "חשמלאים",
    # Ремонт/Отделка
    "покраска": "שיפוצים", "плитка": "שיפוצים", "гипсокартон": "שיפוצים", "ремонт ванной": "שיפוצים",
    # Слесари (замки)
    "вскрытие дверей": "מנעולנים", "вскрыть дверь": "מנעולנים", "замок": "מנעולנים",
    "ключ": "מנעולנים", "замена личинки": "מנעולנים",
})
# === END STEP 1a ===


# הופך את המפתחות ל-normalized אחיד
FIELD_ALIASES = {L: {_norm_alias(k): v for k, v in d.items()} for L, d in _FIELD_ALIASES_RAW.items()}
CITY_ALIASES  = {L: {_norm_alias(k): v for k, v in d.items()} for L, d in _CITY_ALIASES_RAW.items()}

def resolve_field_alias(q: str, lang: str) -> str | None:
    """מנסה לזהות קטגוריה קנונית בעברית מכל ביטוי שקשור אליה.
    1) חיפוש ישיר במילון נרדפים (לפי שפת ה-URL ואז שאר השפות)
    2) Fallback היגיון תבניות (סאבסטרינגים נפוצים HE/EN/RU)
    """
    key = _norm_alias(q)
    if not key:
        return None

    # 1) Lookup ישיר במילונים
    for L in (lang, "he", "en", "ru"):
        res = FIELD_ALIASES.get(L, {}).get(key)
        if res:
            return res

    # 2) Heuristic fallback
    k = key  # כבר נורמלנו ל-lower ומקפים במקום רווחים

    def has_any(tokens):
        return any(t in k for t in tokens)

    # אינסטלטורים
    if has_any((
        "plumb","drain","clog","leak","pipe","faucet","heater","sewer",
        "סתימ","נזיל","צנרת","ברז","דוד","ביוב",
        "сантех","засор","прочист","протеч","теч","водонагр","труба","смесител"
    )):
        return "אינסטלטורים"

    # חשמלאים
    if has_any((
        "electr","wiring","breaker","fuse","short","outlet","panel","light",
        "חשמל","קצר","לוח","תאור","שקע","חיווט",
        "электр","щит","розет","замык","провод","освещ"
    )):
        return "חשמלאים"

    # שיפוצים
    if has_any((
        "reno","remod","til","paint","drywall","bathroom",
        "שיפוצ","צבע","קרמ","רצף","גבס","חיפוי","שבירת",
        "ремонт","отдел","плитк","гипсокарт","ванн"
    )):
        return "שיפוצים"

    # מנעולנים
    if has_any((
        "lock","unlock","door","cylinder","key",
        "מנעול","פריצ","צילינד","מפתח",
        "слесар","вскрыт","замок","личинк","двер"
    )):
        return "מנעולנים"

    return None

def resolve_city_alias(q: str, lang: str) -> str | None:
    """מחזיר שם קנוני בעברית לעיר, אם זוהה נרדף/שם; אחרת None."""
    key = _norm_alias(q)
    if not key:
        return None

    # 1) לוקאפ רגיל: קודם השפה מה-URL ואז שאר השפות
    res = CITY_ALIASES.get(lang, {}).get(key)
    if res:
        return res
    for L in ("he", "en", "ru"):
        if L == lang:
            continue
        res = CITY_ALIASES.get(L, {}).get(key)
        if res:
            return res

    # 2) Fallback: התאמה כשהסרת מפרידים (רווח/מקף/קו-תחתי/מקאף/מקף ארוך)
    def _strip_seps(s: str) -> str:
        return re.sub(r'[\s_\-\u05BE\u2013\u2014]+', '', s or '')

    key_ns = _strip_seps(key)

    # 2a) השוואה מול כל האליאסים בכל השפות אחרי הסרת מפרידים
    for d in CITY_ALIASES.values():
        for alias_key, he_name in d.items():
            if _strip_seps(alias_key) == key_ns:
                return he_name

    # 2b) השוואה מול שמות הערים הקנוניים עצמם (cities_coords)
    for he_city in cities_coords.keys():
        if _strip_seps(_norm_alias(he_city)) == key_ns:
            return he_city

    return None

# ===== END STEP 2 helpers =====


# ========= Service Registry =========
SERVICE_REGISTRY = {
    "drain-cleaning": {
        "field_he": "אינסטלטורים",
        "he": "פתיחת סתימות", "en": "Drain cleaning", "ru": "Устранение засора",
        "synonyms": {
            "he": ["סתימה", "שאיבת סתימה", "ניקוי קו"],
            "en": ["unclogging", "clogged drain", "drain blockage"],
            "ru": ["прочистка", "засор", "чистка трубы"]
        }
    },
    "leak-repair": {
        "field_he": "אינסטלטורים",
        "he": "תיקון נזילות", "en": "Leak repair", "ru": "Ремонт течи",
        "synonyms": {"he": ["נזילה", "איתור נזילה"], "en": ["pipe leak"], "ru": ["протечка", "течь"]}
    },
    "door-opening": {
        "field_he": "מנעולנים",
        "he": "פריצת דלת", "en": "Door opening", "ru": "Вскрытие дверей",
        "synonyms": {"he": ["פתיחת דלת"], "en": ["unlock door"], "ru": ["открыть дверь"]}
    },
    "cylinder-replacement": {
        "field_he": "מנעולנים",
        "he": "החלפת צילינדר", "en": "Cylinder replacement", "ru": "Замена личинки",
        "synonyms": {"he": ["צילינדר"], "en": ["lock cylinder"], "ru": ["личинка замка"]}
    },
    "short-circuit": {
        "field_he": "חשמלאים",
        "he": "קצר חשמל", "en": "Short circuit", "ru": "Короткое замыкание",
        "synonyms": {"he": ["קפיצת פקק"], "en": ["tripped breaker"], "ru": ["выбило автомат"]}
    },
    "install-light": {
        "field_he": "חשמלאים",
        "he": "התקנת תאורה", "en": "Install lighting", "ru": "Монтаж освещения",
        "synonyms": {"he": ["נברשת", "גוף תאורה"], "en": ["light fixture"], "ru": ["светильник"]}
    },
    "bathroom-remodel": {
        "field_he": "שיפוצים",
        "he": "שיפוץ אמבטיה", "en": "Bathroom remodel", "ru": "Ремонт ванной",
        "synonyms": {"he": ["חדר רחצה"], "en": ["bath remodel"], "ru": ["ванная"]}
    },
}


# --- Price preset (price_prest) helpers ---
NICHE_HE_TO_KEY = {
    "חשמלאים": "electrician",
    "אינסטלטורים": "plumber",
    "מנעולנים": "locksmith",
    "שיפוצים": "renovations",
    # חדשות – כדי שהמחירון יעבוד גם עבור דפים כאלה:
    "טכנאי מזגנים": "hvac",
    "צבעי": "painter",
    "הנדימן": "handyman",
    "שיפוצניק/הנדימן": "handyman",
}


def _niche_key_from_worker(w: dict) -> str:
    he = (w.get("field") or w.get("field_he") or "").strip()
    if he in NICHE_HE_TO_KEY:
        return NICHE_HE_TO_KEY[he]

    # היוריסטיקות עדינות – אם השדה לא קנוני
    s = he
    if "מזגן" in s:      return "hvac"
    if "צבע" in s:       return "painter"
    if "הנדימן" in s or "שיפוצניק" in s: return "handyman"

    # פולבאק: 4 הנישות הישנות (אם יש וריאציה)
    if "חשמל" in s:      return "electrician"
    if "אינסט" in s:     return "plumber"
    if "מנעול" in s:     return "locksmith"
    if "שיפו" in s:      return "renovations"
    return ""

def build_price_items_for_worker(worker: dict, lang: str = "he", limit: int = 6) -> list[str]:
    """
    גרסה פשוטה: לא פונה לרשת.
    לוקחת את הנישה מהעובד → קוראת translations/<lang>/price_prest.json → בונה רשימת שורות.
    """
    # המפה כבר קיימת אצלך למעלה:
    # NICHE_HE_TO_KEY = { "חשמלאים": "electrician", "אינסטלטורים": "plumber", "מנעולנים": "locksmith", "שיפוצים": "renovations" }
    he_field = (worker.get("field") or worker.get("field_he") or "").strip()
    niche_key = NICHE_HE_TO_KEY.get(he_field, "")
    if not niche_key:
        return []

    return get_price_items_from_translations(niche_key, lang=lang, limit=limit)




# מפה מכל שם/כינוי → מפתח שירות (נרמול כמו ה"נרדפים" של התחומים)
SERVICE_ALIASES = {}
for key, meta in SERVICE_REGISTRY.items():
    SERVICE_ALIASES[_norm_alias(key)] = key
    for lng in ("he","en","ru"):
        lbl = meta.get(lng)
        if lbl:
            SERVICE_ALIASES[_norm_alias(lbl)] = key
        for s in meta.get("synonyms", {}).get(lng, []):
            SERVICE_ALIASES[_norm_alias(s)] = key

def resolve_service_key(token: str) -> str | None:
    if not token:
        return None
    return SERVICE_ALIASES.get(_norm_alias(token))
# ===================================


# -----------------------------
# Jinja filters for video embed
# -----------------------------
def _youtube_id(url: str):
    try:
        p = urlparse(url)
        host = (p.netloc or "").lower()
        if "youtu.be" in host:
            return p.path.lstrip("/") or None
        if "youtube.com" in host:
            # /watch?v=ID
            if p.path == "/watch":
                return parse_qs(p.query).get("v", [None])[0]
            # /shorts/ID
            if p.path.startswith("/shorts/"):
                parts = [s for s in p.path.split("/") if s]
                return parts[1] if len(parts) > 1 else None
            # /embed/ID
            if p.path.startswith("/embed/"):
                parts = [s for s in p.path.split("/") if s]
                return parts[1] if len(parts) > 1 else None
        return None
    except Exception:
        return None


def _vimeo_id(url: str):
    try:
        p = urlparse(url)
        host = (p.netloc or "").lower()
        if "vimeo.com" in host:
            parts = [s for s in p.path.split("/") if s]
            # מזהה בסיסי (מספרי) של וימאו
            return parts[0] if parts and parts[0].isdigit() else None
        return None
    except Exception:
        return None


def to_embed_url(url: str):
    """ מחזיר URL להטמעה:
    - YouTube -> https://www.youtube.com/embed/ID
    - Vimeo -> https://player.vimeo.com/video/ID
    - אחר -> מחזיר את המקור (למשל MP4 ישמש ל-<video>)
    """
    if not url:
        return None
    url = url.strip()
    yt = _youtube_id(url)
    if yt:
        return f"https://www.youtube.com/embed/{yt}?rel=0&modestbranding=1"
    vm = _vimeo_id(url)
    if vm:
        return f"https://player.vimeo.com/video/{vm}"
    return url


def video_kind(url: str):
    """ מזהה את סוג הווידאו לצורך טמפלט: מחזיר 'mp4' / 'youtube' / 'vimeo' / 'unknown' """
    if not url:
        return "unknown"
    u = url.strip().lower()
    if u.endswith((".mp4", ".webm", ".ogg")):
        return "mp4"
    if "youtu" in u:
        return "youtube"
    if "vimeo" in u:
        return "vimeo"
    return "unknown"


def register_jinja_filters(flask_app):
    """רישום הפילטרים לסביבת Jinja לאחר יצירת האפליקציה."""
    flask_app.jinja_env.filters['to_embed_url'] = to_embed_url
    flask_app.jinja_env.filters['video_kind'] = video_kind

# ------------------------------
# ניהול שפה ותרגומים
# ------------------------------
def load_translations(lang):
    try:
        endpoint = request.endpoint or 'home'
        file_name = f"{endpoint}.json"
        path = os.path.join(TRANSLATIONS_FOLDER, lang, file_name)
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}



# --- i18n helper: load bundle by name (e.g., 'request') ---
from functools import lru_cache

@lru_cache(maxsize=128)
def _load_bundle(lang: str, bundle: str) -> dict:
    """
    loads translations/<lang>/<bundle>.json  (e.g., translations/he/request.json)
    returns {} if missing
    """
    try:
        path = os.path.join(TRANSLATIONS_FOLDER, lang, f"{bundle}.json")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}
    

def get_price_items_from_translations(niche_key: str, lang: str = "he", limit: int = 6) -> list[str]:
    """
    קורא translations/<lang>/price_prest.json ובונה ['שם פריט: מחיר', ...]
    לפי הנישה (electrician/plumber/locksmith/renovations).
    מצפה לזוגות מפתחות:
      "<prefix>.<item>"  ו- "<prefix>.<item>.price"
    """
    data = _load_bundle(lang, "price_prest") or {}  # טוען את קובץ התרגום
    prefix = f"{niche_key}."

    rows = []
    for k, label in data.items():
        if not k.startswith(prefix):
            continue
        if k.endswith(".price"):
            continue
        price = data.get(f"{k}.price")
        if label and price:
            rows.append((k, f"{label}: {price}"))

    # ביקשנו קודם "עלות ביקור"
    rows.sort(key=lambda kv: (0 if kv[0].endswith(".visit_fee") else 1, kv[0]))
    return [v for _, v in rows[:max(1, limit)]]




def t(key: str, bundle: str | None = None) -> str:
    """
    t('pro_req.title', 'request') -> reads translations/<lang>/request.json
    t('some.key')                 -> falls back to current endpoint's bundle via g.translations
    """
    lang = getattr(g, "current_lang", "he")
    if bundle:
        data = _load_bundle(lang, bundle)
    else:
        # fallback: use the endpoint-based dict already loaded into g.translations
        data = getattr(g, "translations", {}) or load_translations(lang)
    return data.get(key, key)



# ------------------------------
# Flask App
# ------------------------------
# במקום: app = Flask(__name__)
app = Flask(__name__, static_folder=None) 
# JSON יפה בעברית
app.config["JSON_AS_ASCII"] = False
app.config["JSON_SORT_KEYS"] = False

app.static_folder = STATIC_DIR
mimetypes.add_type('text/css', '.css')
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('font/woff2', '.woff2')
mimetypes.add_type('font/woff', '.woff')
mimetypes.add_type('image/svg+xml', '.svg')
mimetypes.add_type('video/mp4', '.mp4')
mimetypes.add_type('image/jpeg', '.jpg')
mimetypes.add_type('image/jpeg', '.jpeg')
mimetypes.add_type('image/png', '.png')
mimetypes.add_type('image/gif', '.gif')
mimetypes.add_type('image/webp', '.webp')

csrf = CSRFProtect(app)
app.config['WTF_CSRF_TIME_LIMIT'] = 60 * 60 * 2  # אופציונלי: תוקף טוקן שעתיים
app.permanent_session_lifetime = timedelta(minutes=15)  # שנה לזמן שתרצה
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-change-me')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_VIDEO_MB * 1024 * 1024  # מגביל קבצים ל-50MB (אותו ערך כמו MAX_VIDEO_MB)
register_jinja_filters(app)

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config['PREFERRED_URL_SCHEME'] = 'https'















@app.after_request
def _force_img_content_type(resp):
    """
    רץ על כל תגובה; אם הנתיב הוא /img/... – מכריח Content-Type של תמונה
    ומוסיף דגלים שמונעים מ-after_request אחרים (כמו inline CSS) לגעת בזה.
    בנוסף מוסיף כותרות דיבאג.
    """
    try:
        path = (request.path or "")
        if not path.startswith("/img/"):
            return resp

        # נוודא שאפשר לשנות את הגוף/כותרות (למקרה של passthrough)
        resp.direct_passthrough = False

        # אם בטעות נהיה text/html או משהו שלא image/* – תקן לפי הפרמטרים/Accept
        ct = (resp.headers.get("Content-Type") or "").lower()
        if not ct.startswith("image/"):
            fmt_req = (request.args.get("format") or "auto").lower()
            accept = (request.headers.get("Accept") or "").lower()

            if fmt_req == "png":
                new_ct = "image/png"
            elif fmt_req == "webp" or ("image/webp" in accept and fmt_req in ("auto", "webp")):
                new_ct = "image/webp"
            else:
                new_ct = "image/jpeg"

            resp.headers["Content-Type"] = new_ct

        # דגלים חשובים + כותרות דיבאג
        resp.headers["X-Bypass-Inline"] = "1"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
        resp.headers.setdefault("Vary", "Accept")
        resp.headers["X-Img-Force"] = "1"
        resp.headers["X-Which-After"] = "_force_img_content_type"

        return resp
    except Exception:
        return resp





@csrf.exempt
@app.route("/img/<path:filename>")
def img_proxy(filename):
    # פרמטרים
    w = request.args.get("w", type=int)
    h = request.args.get("h", type=int)
    fit = (request.args.get("fit") or "cover").lower()
    q = max(1, min(request.args.get("q", default=80, type=int), 95))
    fmt_req = (request.args.get("format") or "auto").lower()

    # קובץ מקור בתוך static
    safe = filename.lstrip("/").replace("\\", "/")
    src_path = os.path.join(app.static_folder, safe)
    if not os.path.isfile(src_path):
        resp = Response(b"Not Found", 404, {
            "Content-Type": "text/plain; charset=utf-8",
            "X-Bypass-Inline": "1",
        })
        resp.headers["X-Which-Route"] = "/img"
        return resp

    # קביעת פורמט יציאה
    accept = (request.headers.get("Accept") or "").lower()
    if fmt_req == "auto":
        fmt_out = "WEBP" if "image/webp" in accept else "JPEG"
    else:
        fmt_out = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}.get(fmt_req, "JPEG")
    ct = {"JPEG": "image/jpeg", "WEBP": "image/webp", "PNG": "image/png"}[fmt_out]

    # עיבוד ושינוי גודל
    try:
        with Image.open(src_path) as im:
            if fmt_out == "JPEG":
                if im.mode in ("RGBA", "LA"):
                    bg = Image.new("RGB", im.size, (255, 255, 255))
                    bg.paste(im, mask=im.split()[-1])
                    im = bg
                else:
                    im = im.convert("RGB")
            else:
                if im.mode not in ("RGB", "RGBA"):
                    im = im.convert("RGBA" if "A" in im.getbands() else "RGB")

            if w or h:
                if not w and h:
                    w = int(h * (im.width / im.height))
                if not h and w:
                    h = int(w / (im.width / im.height))
                size = (w or im.width, h or im.height)
                out = ImageOps.contain(im, size, Image.LANCZOS) if fit == "contain" \
                      else ImageOps.fit(im, size, Image.LANCZOS, centering=(0.5, 0.5))
            else:
                out = im

            buf = BytesIO()
            save_kwargs = {}
            if fmt_out == "JPEG":
                save_kwargs.update(quality=q, optimize=True, progressive=False)
            elif fmt_out == "WEBP":
                save_kwargs.update(quality=q, method=6)
            elif fmt_out == "PNG":
                save_kwargs.update(optimize=True)
            out.save(buf, fmt_out, **save_kwargs)
            buf.seek(0)
    except Exception:
        resp = Response(b"Image processing error", 500, {
            "Content-Type": "text/plain; charset=utf-8",
            "X-Bypass-Inline": "1",
        })
        resp.headers["X-Which-Route"] = "/img"
        return resp

    # תגובה: MIME נכון + דגלים + דיבאג
    resp = Response(buf.getvalue(), mimetype=ct)
    resp.headers["Content-Type"] = ct
    resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Bypass-Inline"] = "1"
    resp.headers["Vary"] = "Accept"
    resp.headers["X-Which-Route"] = "/img"
    return resp














@csrf.exempt
@app.get("/api/diag-static")
def api_diag_static():
    rel = (request.args.get("path") or "").lstrip("/").replace("..", "")
    full = os.path.join(STATIC_DIR, rel)
    exists = os.path.isfile(full)
    ext = os.path.splitext(rel)[1].lower()
    guessed, _ = mimetypes.guess_type(rel)
    info = {
        "input": rel,
        "fullpath": full,
        "exists": bool(exists),
        "ext": ext,
        "mimetype_guess": guessed,
        "size_bytes": None,
        "is_image_openable": None,
        "pil_format": None,
        "static_url": url_for("static", filename=rel),
    }
    if exists:
        try:
            info["size_bytes"] = os.path.getsize(full)
            with Image.open(full) as im:
                info["is_image_openable"] = True
                info["pil_format"] = im.format
        except Exception as e:
            info["is_image_openable"] = False
            info["pil_error"] = repr(e)

    resp = jsonify(info)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Bypass-Inline"] = "1"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp



@app.get("/api/debug/report")
def api_debug_report():
    """
    מחזיר דוח דיאגנוסטיקה על קבצי תמונות וסטטיים.
    אפשר לפתוח בדפדפן: /api/debug/report
    """
    import traceback
    results = {}
    try:
        # רשימת קבצים לבדיקה
        files = [
            "photo1.jpg",
            "photo2.jpg",
            "logo.jpeg",
            "flags/israel-flag-png-large.png",
            "flags/united-states-of-america-flag-png-large.png",
            "flags/russia-flag-png-large.png"
        ]
        for f in files:
            full = os.path.join(STATIC_DIR, f)

            exists = os.path.isfile(full)
            info = {"exists": exists}
            if exists:
                try:
                    info["size_bytes"] = os.path.getsize(full)
                    with Image.open(full) as im:
                        info["pil_format"] = im.format
                        info["pil_size"] = im.size
                except Exception as e:
                    info["pil_error"] = repr(e)
            results[f] = info
    except Exception as e:
        results["__error__"] = traceback.format_exc()
    return jsonify({"ok": True, "results": results})




@csrf.exempt
@app.get("/api/diag-img-proxy")
def api_diag_img_proxy():
    filename = (request.args.get("file") or "").lstrip("/")
    w = request.args.get("w", type=int)
    h = request.args.get("h", type=int)
    fit = (request.args.get("fit") or "cover").lower()
    q = request.args.get("q", default=80, type=int)
    fmt_req = (request.args.get("format") or "auto").lower()

    src_path = os.path.join(STATIC_DIR, filename)

    exists = os.path.isfile(src_path)

    accept = (request.headers.get("Accept") or "").lower()
    if fmt_req == "auto":
        fmt_out = "WEBP" if "image/webp" in accept else "JPEG"
    else:
        m = {"jpg":"JPEG","jpeg":"JPEG","png":"PNG","webp":"WEBP"}
        fmt_out = m.get(fmt_req, "JPEG")

    ct = {"JPEG":"image/jpeg","WEBP":"image/webp","PNG":"image/png"}.get(fmt_out, "image/jpeg")

    payload = {
        "input": {"file": filename, "w": w, "h": h, "fit": fit, "q": q, "format": fmt_req},
        "source": {"fullpath": src_path, "exists": bool(exists)},
        "decision": {"fmt_out": fmt_out, "content_type": ct},
        "notes": [
            "תגובה אמיתית של /img תחזיר X-Bypass-Inline=1 ו-Content-Type לפי decision.content_type",
            "exists=False → /img יחזיר 404",
        ]
    }

    resp = jsonify(payload)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Bypass-Inline"] = "1"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


@app.route("/static/<path:filename>", endpoint="static")
def serve_static(filename):
    resp = send_from_directory(STATIC_DIR, filename)
    guessed = mimetypes.guess_type(filename)[0]
    if guessed:
        resp.headers["Content-Type"] = guessed
    resp.headers["X-Bypass-Inline"] = "1"
    resp.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp







# ---- Static URL helper (absolute + version) ----

def static_url(path: str) -> str:
    path = str(path).lstrip("/")  # בלי // כפול
    url = url_for("static", filename=path)  # יחסי! בלי _external
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}v={ASSETS_V}"

def static_abs(path: str) -> str:
    path = str(path).lstrip("/")
    url = url_for("static", filename=path, _external=True, _scheme="https")
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}v={ASSETS_V}"

def static_rel(path: str) -> str:
    """Relative static URL with cache-busting version, no scheme/host -> avoids Mixed Content."""
    path = str(path).lstrip("/")
    url = url_for("static", filename=path)  # יחסי!
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}v={ASSETS_V}"

@app.context_processor
def inject_static_url():
    return dict(static_url=static_url, static_abs=static_abs, static_rel=static_rel, BUILD=ASSETS_V)

# --- Serve /static/* early with correct Content-Type (iOS/Safari strict) ---
# --- Serve /static/* early with correct Content-Type (iOS/Safari strict) ---
# --- Serve /static/* early with correct Content-Type (iOS/Safari strict) ---
# --- Serve /static/* early with correct Content-Type (iOS/Safari strict) ---




# ראוט סטטי מפורש – עוקף כל התנהגות אחרת



# -------- OG images: ensure 1200x630 --------
def _og_dir():
    """תקיית static/og בתוך האפליקציה."""
    return os.path.join(app.root_path, "static", "og")

def _fallback_image():
    """ תמונת fallback אם חסרה תמונת OG לשפה מסוימת. עדכן אם תרצה תמונה אחרת (לדוגמה og-default.jpg). """
    return os.path.join(app.root_path, "static", "photo1.jpg")

def ensure_og_image(lang: str):
    """ דואג ש-static/og/home-<lang>.jpg יהיה קיים וב-1200x630.
        אם חסר/בגודל שגוי – יוצר/מתקן (cover crop) ושומר כ-JPEG איכותי. """
    og_dir = _og_dir()
    os.makedirs(og_dir, exist_ok=True)
    target = os.path.join(og_dir, f"home-{lang}.jpg")
    # אם יש כבר קובץ, ננסה לבדוק גודל; אם אין – נשתמש בפולבאק
    src = target if os.path.exists(target) else _fallback_image()

    # אם כבר קיים ובגודל נכון — לא נוגעים
    try:
        if os.path.exists(target):
            with Image.open(target) as t:
                if t.size == (1200, 630):
                    return
    except Exception:
        # לא ניתן לפתוח/תמונה פגומה — ניצור מחדש
        pass

    # יצירה/תיקון
    try:
        with Image.open(src) as im:
            out = ImageOps.fit(im.convert("RGB"), (1200, 630), Image.LANCZOS, centering=(0.5, 0.5))
            out.save(target, "JPEG", quality=85, optimize=True, progressive=True)
    except Exception as e:
        # לא מפיל את השרת; רק לוג
        app.logger.warning(f"OG resize failed for {lang}: {e}")

OG_IMAGES_READY = False

@app.before_request
def _ensure_og_images_once():
    global OG_IMAGES_READY
    if OG_IMAGES_READY:
        return
    for lang in OG_LANGS:
        ensure_og_image(lang)
    OG_IMAGES_READY = True

# -------- SEO: Meta defaults (OG/Twitter/Canonical) --------
def absolute_url(rel_path: str) -> str:
    return f"{BASE_DOMAIN.rstrip('/')}{rel_path}"

@app.context_processor
def inject_meta_defaults():
    # טקסטי ברירת מחדל (אפשר לשפר/לתרגם בהמשך)
    default_title = "בעלי מקצוע בקליק"
    default_desc = "בעלי מקצוע בקליק – האתר שיעזור לך למצוא בקלות שיפוצניקים, חשמלאים, אינסטלטורים ומנעולנים אמינים, זמינים ואיכותיים בכל הארץ."
    # תמונת שיתוף: כרגע נשתמש בלוגו הקיים; מומלץ בהמשך 1200x630 בשם og-default.jpg
    img_rel = url_for('static', filename='logo.jpeg')
    # כתובת קנונית מלאה לעמוד הנוכחי
    canonical = absolute_url(request.path or '/')
    return dict(
        meta_title=default_title,
        meta_description=default_desc,
        meta_image=absolute_url(img_rel),
        meta_url=canonical
    )


@app.context_processor
def inject_csrf():
    return dict(csrf_token=generate_csrf)


def load_reviews_keys(lang):
    try:
        path = os.path.join(TRANSLATIONS_FOLDER, lang, 'reviews_keys.json')
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}


@app.before_request
def set_language():
    lang = request.args.get('lang') or request.cookies.get('lang')
    if not lang:
        path_parts = request.path.strip('/').split('/')
        if path_parts and path_parts[0] in ['he', 'en', 'ru']:
            lang = path_parts[0]
    if not lang:
        lang = 'he'
    lang = normalize_lang(lang)
    g.current_lang = lang

    # --- מזהה סשן אנונימי (למניעת ספירה כפולה + ניתוחים) ---
    if 'sid' not in session:
        session['sid'] = secrets.token_hex(16)

    # טעינת תרגומים רגילים + מפתחות ביקורות
    g.translations = load_translations(lang)
    g.translations.update(load_reviews_keys(lang))

# הגנה על כל מה שמתחת ל-/admin/ (כולל /admin/analysis)
@app.before_request
def protect_admin_area():
    p = request.path or ''
    if p.startswith('/admin'):
        # לא חוסמים את עמודי ההתחברות/התנתקות
        if request.endpoint in ('admin_login', 'admin_logout', 'admin_logout_beacon'):
            return

        # אם לא מחובר — מפנים למסך login עם next מלא (כולל query string אם יש)
        if not session.get('is_admin'):
            next_url = request.full_path if request.query_string else request.path
            return redirect(url_for('admin_login', next=next_url))




def _(key):
    return g.translations.get(key, key)
app.jinja_env.globals.update(_=_)
app.jinja_env.globals.update(t=t)





@app.context_processor
def inject_slug_helpers():
    def field_slug_from_he(he_value):
        return localize_field_slug(he_value, g.get('current_lang', 'he'))
    def city_slug_from_he(he_value):
        return localize_city_slug(he_value, g.get('current_lang', 'he'))
    return dict(field_slug=field_slug_from_he, city_slug=city_slug_from_he)

# ------------------------------
# Routes – עמודים
# ------------------------------
@app.route('/')
def redirect_to_default_lang():
    return redirect(url_for('home', lang='he'))

@app.route('/<lang>/')
def home(lang):
    g.current_lang = lang
    return render_template('home.html')

@app.route('/<lang>/why-us')
def why_us(lang):
    return render_template('why-us.html')

@app.route('/<lang>/works')
def works(lang):
    g.current_lang = lang
    return render_template('works.html')

@app.route("/<lang>/niches")
def niches(lang):
    g.current_lang = lang
    return render_template("niches.html")

@app.route("/<lang>/contact")
def contact(lang):
    g.current_lang = lang
    return render_template("contact.html")

# -------- Legal pages (with lang) --------
@app.route('/<lang>/privacy')
def privacy(lang):
    g.current_lang = lang
    return render_template('legal/privacy.html')

@app.route('/<lang>/terms')
def terms(lang):
    g.current_lang = lang
    return render_template('legal/terms.html')

@app.route('/<lang>/cookies')
def cookies(lang):
    g.current_lang = lang
    return render_template('legal/cookies.html')

@app.route('/<lang>/accessibility')
def accessibility(lang):
    g.current_lang = lang
    return render_template('legal/accessibility.html')

# -------- Fallbacks (no-lang) -> redirect to current lang --------
@app.route('/privacy')
def privacy_fallback():
    return redirect(url_for('privacy', lang=getattr(g, 'current_lang', 'he')))

@app.route('/terms')
def terms_fallback():
    return redirect(url_for('terms', lang=getattr(g, 'current_lang', 'he')))

@app.route('/cookies')
def cookies_fallback():
    return redirect(url_for('cookies', lang=getattr(g, 'current_lang', 'he')))

@app.route('/accessibility')
def accessibility_fallback():
    return redirect(url_for('accessibility', lang=getattr(g, 'current_lang', 'he')))




# ודא שבתחילת הקובץ יש: import ssl import time import smtplib
@app.route('/<lang>/send-message', methods=['POST'])
def send_message(lang):
    is_ajax = (request.headers.get('X-Requested-With', '').lower() in ('fetch', 'xmlhttprequest'))
    try:
        # --- HONEYPOT ---
        if (request.form.get('website') or '').strip():
            if is_ajax:
                return jsonify({"ok": False, "error": "honeypot"}), 400
            flash('הייתה בעיה בשליחת ההודעה.', 'error')
            return redirect(url_for('contact', lang=lang))

        # נתונים
        name    = (request.form.get('name')    or '').strip()
        email   = (request.form.get('email')   or '').strip()
        message = (request.form.get('message') or '').strip()

        # בניית הודעה
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = EMAIL_ADDRESS
        msg['Subject'] = f'New message from {name}'
        if email:
            msg['Reply-To'] = email
        body = f"Name: {name}\nEmail: {email}\nMessage:\n{message}"
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        # ==== שליחה ברקע במרוץ 465/587: המהיר מנצח ====
        def _bg_send_race(m):
            stop = threading.Event()
            ctx = ssl.create_default_context()
            try:
                # מונע מו"מ על גרסאות TLS ישנות
                ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            except Exception:
                pass

            def via_465():
                try:
                    t0 = time.perf_counter()
                    with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=ctx, timeout=5, local_hostname='localhost') as s:
                        if stop.is_set(): return
                        s.ehlo('localhost')
                        s.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                        if stop.is_set(): return
                        s.send_message(m)
                        print(f"MAIL OK via 465 in {int((time.perf_counter()-t0)*1000)}ms")
                        stop.set()
                except Exception as e:
                    print("SMTP 465 failed:", repr(e))

            def via_587():
                try:
                    t0 = time.perf_counter()
                    with smtplib.SMTP('smtp.gmail.com', 587, timeout=6, local_hostname='localhost') as s:
                        if stop.is_set(): return
                        s.ehlo('localhost')
                        s.starttls(context=ctx)
                        s.ehlo('localhost')
                        s.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                        if stop.is_set(): return
                        s.send_message(m)
                        print(f"MAIL OK via 587 in {int((time.perf_counter()-t0)*1000)}ms")
                        stop.set()
                except Exception as e:
                    print("SMTP 587 failed:", repr(e))

            t1 = threading.Thread(target=via_465, daemon=True)
            t2 = threading.Thread(target=via_587, daemon=True)
            t1.start(); t2.start()

            # Watchdog: אם אף ערוץ לא הצליח עד 10 שניות – כותבים ללוג
            def watchdog():
                if not stop.wait(10):
                    try:
                        logp = os.path.join(DATA_FOLDER, 'email_errors.log')
                        with open(logp, 'a', encoding='utf-8') as f:
                            f.write(f"{datetime.now().isoformat()}Z\tboth_smtp_failed_or_slow\n")
                    except Exception:
                        pass
            threading.Thread(target=watchdog, daemon=True).start()

        threading.Thread(target=_bg_send_race, args=(msg,), daemon=True).start()
        # ==== סוף מרוץ ====

        if is_ajax:
            return jsonify({"ok": True, "message": "ההודעה נקלטה – נשלח ברקע."}), 200

        flash('ההודעה התקבלה, נטפל בה מיד. תודה!', 'success')
        return redirect(url_for('contact', lang=lang))

    except Exception as e:
        print('MAIL SETUP ERROR:', repr(e))
        if is_ajax:
            return jsonify({"ok": False, "error": "server"}), 500
        flash('הייתה בעיה בשליחת ההודעה.', 'error')
        return redirect(url_for('contact', lang=lang))


@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    flash('התנתקת בהצלחה', 'success')
    return redirect(url_for('admin_login'))



@csrf.exempt
@app.post('/admin/logout-beacon')
def admin_logout_beacon():
    # לוגאאוט שקט כאשר נסגרת הלשונית האחרונה (נשלח מהדפדפן ב-sendBeacon)
    session.pop('is_admin', None)
    return ('', 204)



# ------------------------------
# בקשת בעל מקצוע
# ------------------------------
@app.route('/<lang>/request', methods=['GET', 'POST'])
def request_professional(lang):
    # --- דרישת קישור הזמנה ---
    invite_key = os.environ.get('INVITE_KEY', 'dev-invite')  # שים ערך אמיתי ב-.env
    supplied_key = (request.args.get('key') or request.form.get('key') or '').strip()
    if supplied_key != invite_key:
        flash('כדי למלא את הטופס יש צורך בקישור הזמנה.', 'error')
        return redirect(url_for('contact', lang=lang))

    if request.method == 'POST':
        # --- איסוף נתונים מהטופס ---
        name = request.form.get('name')
        company_name = request.form.get('company_name')
        field = request.form.get('field')
        area = request.form.get('area')
        base_city = request.form.get('base_city')
        work_radius = request.form.get('work_radius')
        phone = request.form.get('phone')
        experience = request.form.get('experience')
        description = request.form.get('description')
        reviews = request.form.get('reviews')
        image = request.files.get('image')
        image_filename = ''

        # NEW: שדות חדשים מהטופס
        # 1) תת-תחומים – אם בטופס יש כמה צ'קבוקסים עם אותו name="sub_services"
        #    זה יחזיר רשימה של מה שסומן. אם אין – נקבל רשימה ריקה.
        sub_services = request.form.getlist('sub_services')

        # 2) שירות חירום – צ'קבוקס בודד name="offers_emergency"
        #    כל ערך שאינו ריק ייחשב True.
        offers_emergency = bool(request.form.get('offers_emergency'))

        # --- וידאו: לינק/קובץ ---
        video_file_cam = request.files.get('video_file_cam')
        video_file_gallery = request.files.get('video_file_gallery')
        video_file = video_file_cam or video_file_gallery
        saved_video_relpath = None  # נתיב יחסי ל-static אם נשמר קובץ

        if image and image.filename != '':
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_filename = 'upload_pending/' + filename

        # אם אין קישור אבל הועלה קובץ – נשמור אותו
        if video_file and video_file.filename:
            if allowed_video_file(video_file.filename):
                safe_name = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{video_file.filename}")
                save_path = os.path.join(VIDEO_UPLOAD_SUBDIR, safe_name)
                try:
                    # בדיקת גודל (אופציונלי)
                    video_file.stream.seek(0, os.SEEK_END)
                    size_mb = video_file.stream.tell() / (1024 * 1024)
                    video_file.stream.seek(0)
                    if size_mb > MAX_VIDEO_MB:
                        flash(f"וידאו גדול מדי (>{MAX_VIDEO_MB}MB). נסה/י קובץ קטן יותר.", "error")
                    else:
                        video_file.save(save_path)
                        saved_video_relpath = f"upload_pending/videos/{safe_name}"
                except Exception:
                    flash("אירעה שגיאה בשמירת הווידאו. נסה/י שוב.", "error")
            else:
                flash("סוג הקובץ אינו נתמך. מותר: mp4, webm, ogg", "error")

        he_field   = _canon_he_field(field)
        i18n_field = FIELD_I18N.get(he_field, {"he": he_field, "en": he_field, "ru": he_field})

        # שעות עבודה – בלוק ראשון (כפי שהיה)
        work_blocks = []
        start_hour_0 = request.form.get('start_hour_0')
        end_hour_0 = request.form.get('end_hour_0')
        days_0 = request.form.getlist('days_0')
        if start_hour_0 and end_hour_0 and days_0:
            work_blocks.append({"start_hour": int(start_hour_0), "end_hour": int(end_hour_0), "days": days_0})

        # ערים בטווח רדיוס
        cities_in_radius = get_cities_in_radius(base_city, int(work_radius) if work_radius else 0)

        # בניית הרשומה החדשה לפנדינג
        new_request = {
            "company_name": company_name,
            "name": name,
            "field":    i18n_field["he"],
            "field_en": i18n_field["en"],
            "field_ru": i18n_field["ru"],
            "base_city": base_city,
            "work_radius": int(work_radius) if work_radius else 0,
            "active_cities": cities_in_radius,
            "phone": phone,
            "experience": int(experience) if experience and experience.isdigit() else 0,
            "description": description,
            "reviews": reviews,
            "image_filename": image_filename,
            "video_url": None,
            "video_local": saved_video_relpath,
            "work_blocks": work_blocks,

            # NEW: שמירה ב-JSON
            "sub_services": sub_services,            # רשימת המחרוזות שסומנו בטופס (בעברית כרגע)
            "offers_emergency": offers_emergency     # True/False
        }

        # שמירה לפנדינג
        pending_list = read_json_file(PENDING_FILE)
        pending_list.append(new_request)
        write_json_file(PENDING_FILE, pending_list)

        flash("הבקשה נשלחה בהצלחה! תודה רבה.")
        # שומרים את ה-key גם בחזרה, כדי שהעמוד יישאר נגיש ברענון
        return redirect(url_for('request_professional', lang=lang, key=invite_key))

    # GET — מעבירים invite_key לטמפלט (שדה חבוי + ב-action)
    return render_template('request.html', lang=lang, invite_key=invite_key)
# ------------------------------
# Workers list
# ------------------------------
@app.route('/<lang>/workers/<field>/', defaults={'area': None})
@app.route('/<lang>/workers/<field>/<area>')
def show_workers(lang, field, area):
    session['last_workers_field'] = field
    session['last_workers_area'] = area

    # URL נקי לרשימה הנוכחית (שומר query string רק אם קיים)
    qs = request.query_string.decode('utf-8') if request.query_string else ''
    current_list_url = request.path + (f'?{qs}' if qs else '')
    # 👇 שמירה ל"בחזרה מהרשימות"
    session['last_workers_path'] = current_list_url

    # נרמל מפתחות מה-URL
    field_key = normalize_slug(field)
    area_key  = normalize_slug(area) if area else None

    # ===== Canonicalization + aliases =====
    # 1) פתרון נרדפים → שם קנוני בעברית (אם לא נמצא – ניפול לערך המנורמל)
    resolved_field_he = resolve_field_alias(field, lang) or field_key
    resolved_area_he  = (resolve_city_alias(area, lang) if area else None) or (area_key if area_key else None)

    # 2) בניית סלג קנוני בשפת ה־UI
    canon_field_slug = localize_field_slug(resolved_field_he, lang)
    canon_area_slug  = localize_city_slug(resolved_area_he, lang) if resolved_area_he else None

    incoming_field_slug = to_kebab_slug(field)
    incoming_area_slug  = to_kebab_slug(area) if area else None

    # 3) אם ה-URL אינו קנוני → הפניה 301 עם שמירת ה-query string
    if incoming_field_slug != canon_field_slug or incoming_area_slug != canon_area_slug:
        target = url_for('show_workers', lang=lang, field=canon_field_slug, area=canon_area_slug)
        qs = request.query_string.decode('utf-8') if request.query_string else ''
        if qs:
            target = f"{target}?{qs}"
        return redirect(target, code=301)

    # 4) מכאן נעבוד תמיד עם שמות עברית קנוניים לסינון
    search_field = resolved_field_he
    search_area  = resolved_area_he

    # טעינת עובדים וסינון
    all_workers = read_json_file(APPROVED_FILE)
    if search_area:
        workers = [
            w for w in all_workers
            if w.get('field') == search_field and (
                w.get('base_city') == search_area or
                search_area in w.get('active_cities', []) or        # רשימה שנשמרה
                _in_radius(w, search_area)                           # 👈 בדיקה דינמית
            )
        ]
    else:
        workers = [w for w in all_workers if w.get('field') == search_field]

    # הכנה לזמינות
    now = datetime.now()
    current_day = now.weekday()
    current_hour = now.hour
    days_map_he = {'שני': 0, 'שלישי': 1, 'רביעי': 2, 'חמישי': 3, 'שישי': 4, 'שבת': 5, 'ראשון': 6}

    # 🔹 טוענים קובץ תרגום פעם אחת (לא לכל עובד)
    translations = {}
    translation_file = os.path.join(TRANSLATIONS_FOLDER, lang, 'show_workers.json')
    if os.path.exists(translation_file):
        with open(translation_file, 'r', encoding='utf-8') as f:
            translations = json.load(f)
    default_template = translations.get('default_tagline', 'Professional in the field of {field}')

    # עיבוד נתונים לתצוגה
    for w in workers:
        # זמינות עכשיו
        is_available = False
        for block in w.get('work_blocks', []):
            start = int(block.get('start_hour', 0))
            end = int(block.get('end_hour', 0))
            days_as_numbers = [days_map_he.get(day, day) for day in block.get('days', [])]
            if current_day in days_as_numbers and start <= current_hour < end:
                is_available = True
                break
        w['is_available_now'] = is_available

        # טלפון בפורמט
        w['phone_formatted'] = format_phone(w.get('phone'))

        # התחום המתורגם לתצוגה
        field_lang_key = f'field_{lang}' if lang in ['en', 'ru'] else 'field'
        w['field_translated'] = w.get(field_lang_key, w.get('field', 'Unknown'))

        # טאגליין לפי קובץ תרגום (משתמשת בתבנית שטענו פעם אחת)
        w['tagline'] = default_template.format(
            field_en=w.get('field_en', w.get('field', 'Unknown')),
            field_ru=w.get('field_ru', w.get('field', 'Unknown')),
            field=w.get('field', 'Unknown')
        )

        # ניסיון (טקסט מקוצר)
        if lang == 'he':
            w['experience_text'] = f"{w.get('experience')} שנות ניסיון" if w.get('experience') else "ניסיון לא צוין"
        elif lang == 'en':
            w['experience_text'] = f"{w.get('experience')} years of experience" if w.get('experience') else "Experience not specified"
        elif lang == 'ru':
            w['experience_text'] = f"{w.get('experience')} лет опыта" if w.get('experience') else "Опыт не указан"

        # דירוג ממוצע + מספר ביקורות
        reviews = get_all_reviews(w.get('worker_id'), lang)
        w['reviews_count'] = 0
        if reviews:
            ratings = [r['rating'] for r in reviews if r.get('rating') is not None]
            w['reviews_count'] = len([r for r in reviews if r.get('rating') is not None])
            w['rating'] = round(sum(ratings) / len(ratings), 1) if ratings else None
        else:
            w['rating'] = None

        latest_review = get_latest_review(w.get('worker_id'), lang) or {}
        w['latest_review'] = (latest_review.get('text') or '').strip()
        w['latest_review_author'] = (latest_review.get('author') or '').strip()

    # --- Labels לתצוגה בשפת ה-UI ---
    def _label_field(he_value, lang_code):
        if not he_value:
            return ''
        if lang_code == 'en':
            return field_map_he_to_en.get(he_value, he_value).title()
        if lang_code == 'ru':
            return field_map_he_to_ru.get(he_value, he_value)
        return he_value  # he

    def _label_city(he_value, lang_code):
        if not he_value:
            return ''
        if lang_code == 'en':
            return city_map_he_to_en.get(he_value, he_value).title()
        if lang_code == 'ru':
            return city_map_he_to_ru.get(he_value, he_value)
        return he_value  # he

    field_label = _label_field(search_field, lang)
    area_label  = _label_city(search_area, lang) if search_area else ''

    # 👇👇 שמירת הקשר חיפוש לסשן – כדי שדף הפרופיל ידע לבנות breadcrumb נכון
    session['last_search_category_label'] = field_label
    session['last_search_city_label']     = (area_label or None)
    session['last_search_category_slug']  = canon_field_slug
    session['last_search_city_slug']      = (canon_area_slug or None)
    session.modified = True
    # ☝️☝️

    # --- hreflang + canonical (absolute) ---
    hreflang_urls = {}
    for L in ['he', 'en', 'ru']:
        f_slug = localize_field_slug(search_field, L)
        c_slug = localize_city_slug(search_area, L) if search_area else None
        if c_slug:
            hreflang_urls[L] = url_for('show_workers', lang=L, field=f_slug, area=c_slug, _external=True)
        else:
            hreflang_urls[L] = url_for('show_workers', lang=L, field=f_slug, _external=True)
    canonical_url = hreflang_urls.get(lang)

    # --- META דינמי לפי שפה + ספירת תוצאות ---
    n = len(workers)

    titles = {
        'he': f"{field_label}{(' ב' + area_label) if area_label else ''} – {n} מומלצים וזמינים | בעלי מקצוע בקליק",
        'en': f"{field_label}{(' in ' + area_label) if area_label else ''} – {n} vetted pros | Baley-Mikzoa",
        'ru': f"{field_label}{(' в ' + area_label) if area_label else ''} – {n} проверенных мастеров | Baley-Mikzoa",
    }
    descs = {
        'he': f"מחפשים {field_label}{(' ב' + area_label) if area_label else ''}? {n} בעלי מקצוע אמינים עם ביקורות אמיתיות. זמינות עכשיו, טלפון/וואטסאפ בלחיצה.",
        'en': f"Looking for {field_label}{(' in ' + area_label) if area_label else ''}? {n} trusted pros with real reviews. Contact in one tap.",
        'ru': f"Ищете {field_label}{(' в ' + area_label) if area_label else ''}? {n} надёжных мастеров с отзывами. Связь в один клик.",
    }
    meta_title = titles.get(lang) or titles['he']
    meta_description = descs.get(lang) or descs['he']
    meta_image = url_for('static', filename=f'og/home-{lang}.jpg', _external=True)  # כבר דואגים לקובץ 1200x630

    # --- JSON-LD: CollectionPage + ItemList של LocalBusiness ---
    items = []
    for i, w in enumerate(workers, 1):
        li = {
            "@type": "ListItem",
            "position": i,
            "url": url_for('worker_reviews', lang=lang, worker_id=w.get('worker_id'), _external=True),
            "item": {
                "@type": "LocalBusiness",
                "name": (w.get('company_name') or w.get('name') or f"#{w.get('worker_id')}"),
                "areaServed": area_label or (w.get('base_city') or ""),
                "telephone": w.get('phone_formatted') or "",
                "serviceType": w.get('field_translated') or w.get('field') or ""
            }
        }
        # aggregateRating רק אם יש נתונים
        if w.get('reviews_count'):
            li["item"]["aggregateRating"] = {
                "@type": "AggregateRating",
                "ratingValue": w.get('rating'),
                "reviewCount": w.get('reviews_count')
            }
        items.append(li)

    structured_data = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": meta_title,
        "description": meta_description,
        "inLanguage": lang,
        "mainEntity": {
            "@type": "ItemList",
            "numberOfItems": n,
            "itemListElement": items
        }
    }
    structured_data_json = json.dumps(structured_data, ensure_ascii=False)

    # רינדור (שומר את כל הפרמטרים שהיו + SEO חדשים)
    return render_template(
        'workers_list.html',
        workers=workers,
        field=field_key,
        area=area_key,
        current_list_url=current_list_url,
        field_label=field_label,
        area_label=area_label,
        hreflang_urls=hreflang_urls,
        canonical_url=canonical_url,
        # SEO:
        meta_title=meta_title,
        meta_description=meta_description,
        meta_image=meta_image,
        structured_data_json=structured_data_json
    )



@app.route('/<lang>/services/<service>/', defaults={'area': None})
@app.route('/<lang>/services/<service>/<area>')
def service_landing(lang, service, area):
    # מזהה שירות -> מפה לתחום קנוני בעברית
    key = resolve_service_key(service) or service
    he_field = SERVICE_REGISTRY.get(key, {}).get("field_he")

    # אם לא זוהה שירות אבל זה נראה כמו תחום/נרדף – ננסה לפתור כתחום
    if not he_field:
        he_field = resolve_field_alias(service, lang)

    # אם עדיין לא זוהה כלום – 404
    if not he_field:
        return not_found(404)

    # עיר (אם נמסרה) לנוסח קנוני בעברית
    he_area = resolve_city_alias(area, lang) if area else None

    # המרה ל-slug בשפת ה-UI (he/en/ru)
    f_slug = localize_field_slug(he_field, lang)
    c_slug = localize_city_slug(he_area,  lang) if he_area else None

    # במקום redirect: מרנדרים את **אותו** דף רשימה,
    # כך המשתמש כבר רואה את הליסט, וה־canonical נשאר של /workers/ (מעולה ל-SEO).
    return show_workers(lang, f_slug, c_slug)




def _in_radius(worker: dict, area_he: str) -> bool:
    if not worker or not area_he:
        return False
    base = worker.get('base_city')
    r = int(worker.get('work_radius') or 0)
    if not base or r <= 0:
        return False
    if base in cities_coords and area_he in cities_coords:
        (lat1, lon1) = cities_coords[base]
        (lat2, lon2) = cities_coords[area_he]
        return haversine(lat1, lon1, lat2, lon2) <= r
    return False





@app.route('/<lang>/worker/<worker_id>/reviews')
def worker_reviews(lang, worker_id):
    # --- איתור העובד ---
    all_workers = read_json_file(APPROVED_FILE)
    worker = next((w for w in all_workers if str(w.get('worker_id')) == str(worker_id)), None)
    if not worker:
        return "Worker not found", 404

    # --- back_url קאנוני (עם שימור ה־QS האחרון מהרשימה אם קיים) ---
    he_field = worker.get('field') or 'all'
    he_city = worker.get('base_city')
    field_slug = localize_field_slug(he_field, lang)
    city_slug  = localize_city_slug(he_city, lang)
    if city_slug:
        canonical_path = url_for('show_workers', lang=lang, field=field_slug, area=city_slug)
    else:
        canonical_path = url_for('show_workers', lang=lang, field=field_slug)

    last_path = session.get('last_workers_path') or ''
    qs = last_path.split('?', 1)[1] if '?' in last_path else ''
    back_url = canonical_path + (f'?{qs}' if qs else '')

    # --- HERO meta בסיסי ---
    worker['phone_formatted'] = format_phone(worker.get('phone'))
    if lang == 'en':
        worker['field_display'] = worker.get('field_en', worker.get('field'))
    elif lang == 'ru':
        worker['field_display'] = worker.get('field_ru', worker.get('field'))
    else:
        worker['field_display'] = worker.get('field')

    image_rel = worker.get('image_filename')
    worker['image_url'] = url_for('static', filename=image_rel) if image_rel else None

    video_local = worker.get('video_local')
    video_url   = worker.get('video_url')
    if video_local:
        worker['hero_video_src']  = url_for('static', filename=video_local)
        worker['hero_video_kind'] = 'mp4'
    elif video_url:
        worker['hero_video_src']  = to_embed_url(video_url)
        worker['hero_video_kind'] = video_kind(video_url)
    else:
        worker['hero_video_src']  = None
        worker['hero_video_kind'] = 'unknown'

    # --- תוכן מסודר ללא כפילויות ---
    def _clean_about(txt: str) -> str:
        if not txt:
            return ''
        pat = re.compile(r'(השירותים\s*כוללים|השרותים\s*כוללים|שירותים\s*כוללים|services?\s+include|услуги\s+включают)', re.I)
        out = []
        for ln in (txt or '').splitlines():
            ln = (ln or '').strip()
            if not ln:
                out.append('')
                continue
            if pat.search(ln):
                continue
            out.append(ln)
        cleaned = '\n'.join(out)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()
        return cleaned

    about_src = (worker.get('bio_full') or worker.get('description') or '').strip()
    worker['about']       = about_src
    worker['about_clean'] = _clean_about(about_src)

    # רשימת שירותים
    specs = (worker.get('services_list')
             or worker.get('specializations')
             or worker.get('sub_services')
             or [])
    worker['specializations'] = [s for s in specs if isinstance(s, str) and s.strip()]

    # ניסיון (טקסט קצר לפי שפה)
    exp = worker.get('experience')
    if isinstance(exp, (int, float)) and exp:
        years = int(exp)
        worker['experience_text'] = (
            f"{years} שנות ניסיון" if lang == 'he'
            else f"{years} years of experience" if lang == 'en'
            else f"{years} лет опыта"
        )
    else:
        worker['experience_text'] = ''

    # איזורי שירות (מאוחדים בלי כפילויות)
    areas_raw = []
    if worker.get('service_areas'):
        areas_raw.extend([c for c in worker['service_areas'] if c])
    else:
        if worker.get('base_city'):
            areas_raw.append(worker['base_city'])
        areas_raw.extend([c for c in (worker.get('active_cities') or []) if c])
    seen = set(); areas = []
    for c in areas_raw:
        if c not in seen:
            seen.add(c); areas.append(c)
    worker['service_areas'] = areas

    # --- ביקורות + חישוב ממוצע (הקריטי ל-HERO) ---
    reviews_file = os.path.join(DATA_FOLDER, 'worker_reviews.json')
    all_reviews  = read_json_file(reviews_file)
    reviews      = [r for r in all_reviews if str(r.get('worker_id')) == str(worker_id)]

    ratings = []
    for r in reviews:
        # טקסט לפי שפה
        r['display_text'] = (r.get('translations', {}) or {}).get(lang) or r.get('text', '')
        # דירוג מספרי (תמיכה גם בפסיק)
        raw = r.get('rating')
        if raw is None:
            continue
        try:
            val = float(str(raw).replace(',', '.'))
        except (TypeError, ValueError):
            continue
        if 0 <= val <= 5:
            ratings.append(val)

    if ratings:
        worker['rating'] = round(sum(ratings) / len(ratings), 2)
        worker['reviews_count'] = len(ratings)
    else:
        worker['rating'] = None
        worker['reviews_count'] = 0

    # === פירורי־לחם: Home → "קטגוריה / עיר" → שם בעל המקצוע ===
    cat_label = session.get('last_search_category_label')
    city_label = session.get('last_search_city_label')
    cat_slug_sess = session.get('last_search_category_slug')
    city_slug_sess = session.get('last_search_city_slug')

    def _label_field(he_value: str, L: str) -> str:
        if not he_value: return ''
        if L == 'en': return field_map_he_to_en.get(he_value, he_value).title()
        if L == 'ru': return field_map_he_to_ru.get(he_value, he_value)
        return he_value

    def _label_city(he_value: str, L: str) -> str:
        if not he_value: return ''
        if L == 'en': return city_map_he_to_en.get(he_value, he_value).title()
        if L == 'ru': return city_map_he_to_ru.get(he_value, he_value)
        return he_value

    if not cat_label:
        cat_label = _label_field(he_field, lang)
        cat_slug_sess = field_slug
    if not city_label and he_city:
        city_label = _label_city(he_city, lang)
        city_slug_sess = localize_city_slug(he_city, lang)

    home_href = url_for('home', lang=lang)
    list_href = None
    try:
        if cat_slug_sess and city_slug_sess:
            list_href = url_for('show_workers', lang=lang, field=cat_slug_sess, area=city_slug_sess)
        elif cat_slug_sess:
            list_href = url_for('show_workers', lang=lang, field=cat_slug_sess)
    except Exception:
        list_href = None

    breadcrumb_ctx = {
        "home":   {"label": _("home_label") if "home_label" in g.translations else "דף הבית", "href": home_href},
        "cat_city": None,
        "worker": {"label": (worker.get('company_name') or worker.get('name') or f"#{worker_id}")},
    }
    if cat_label:
        label = f"{cat_label}" + (f" / {city_label}" if city_label else "")
        breadcrumb_ctx["cat_city"] = {"label": label, "href": list_href}

    # --- טווחי מחירים/מחשבון: price_prest ---
    price_items = build_price_items_for_worker(worker, lang=lang)

    # רינדור
    return render_template(
        'worker_reviews.html',
        worker=worker,
        reviews=reviews,
        lang=lang,
        back_url=back_url,
        breadcrumb_ctx=breadcrumb_ctx,
        price_items=price_items,  # ← חדש
    )






@app.route('/<lang>/add-review', methods=['GET', 'POST'])
def add_review(lang):
    all_workers = read_json_file(APPROVED_FILE)
    success_message = None

    if request.method == 'POST':
        worker_id = request.form.get('worker_id')
        author    = request.form.get('author')
        text      = request.form.get('text')
        rating    = request.form.get('rating')

        if not (worker_id and text and author):
            flash("אנא מלאו את כל השדות", "error")
            return redirect(url_for('add_review', lang=lang))

        # מזהה ייחודי לביקורת כדי לעדכן אותה אח"כ ברקע
        review_id    = secrets.token_hex(8)
        reviews_file = os.path.join(DATA_FOLDER, 'worker_reviews.json')

        # כותבים מיידית את הרשומה (מהיר) — תרגומים נבצע ברקע
        new_review = {
            "review_id": review_id,
            "worker_id": str(worker_id),
            "author":    author,
            "text":      text,                       # מקור
            "translations": {"he": text},            # נוסיף en/ru ברקע
            "rating":    float(rating) if rating else None,
            "date":      datetime.now().isoformat()
        }

        # כתיבה מוגנת מנעילה כדי למנוע דריסות בקבצים
        # כתיבה מוגנת מנעילה כדי למנוע דריסות בקבצים
        with REVIEWS_JSON_LOCK:
            reviews_list = read_json_file(reviews_file)
            reviews_list.append(new_review)
            write_json_file(reviews_file, reviews_list)

        # סנכרון לשיטס (Webhook) - לא חוסם את הזרימה
        sync_review_to_sheets(new_review, lang=lang)



        # ---- תרגום ברקע + עדכון הרשומה בקובץ ----
        def _patch_translations_async(_rid: str, _text: str, _path: str):
            try:
                # משתמש בפונקציה הגלובלית translate_review שכבר קיימת למעלה בקובץ
                trans = translate_review(_text)  # {'he':..., 'en':..., 'ru':...}
            except Exception:
                trans = {"he": _text}
            try:
                with REVIEWS_JSON_LOCK:
                    cur = read_json_file(_path)
                    for r in cur:
                        if r.get("review_id") == _rid:
                            r["translations"] = trans
                            break
                    write_json_file(_path, cur)
            except Exception as e:
                # לוג “best effort” אם תרצה לעקוב אחרי תקלות
                try:
                    with open(os.path.join(DATA_FOLDER, 'reviews_errors.log'), 'a', encoding='utf-8') as f:
                        f.write(f"{datetime.now().isoformat()}Z\ttranslate_patch\t{repr(e)}\n")
                except Exception:
                    pass

        threading.Thread(
            target=_patch_translations_async,
            args=(review_id, text, reviews_file),
            daemon=True
        ).start()

        # הודעת הצלחה מהירה (בלי להמתין לתרגומים)
        success_message = "הביקורת נוספה! נתרגם ונסנכרן ברקע."

    return render_template('add_review.html', lang=lang, workers=all_workers, success_message=success_message)



@app.route('/<lang>/<term>/', defaults={'area': None})
@app.route('/<lang>/<term>/<area>')
def smart_alias(lang, term, area):
    if lang not in SUPPORTED_LANGS:
        return not_found(404)

    reserved_endpoint = SMART_ALIAS_RESERVED.get((term or '').strip().lower())
    if reserved_endpoint:
        if area:
            return not_found(404)
        target_lang = normalize_lang(lang)
        target = url_for(reserved_endpoint, lang=target_lang)
        if request.query_string:
            qs = request.query_string.decode('utf-8', 'ignore')
            target = f"{target}?{qs}"
        return redirect(target, code=302)

    # מפרק למילים, מנרמל HE/EN/RU
    def _tokens(s: str):
        s = normalize_slug(s or "") or ""
        return [t for t in re.split(r'[-_\s]+', s) if t]

    toks = _tokens(term)

    # 1) ניסיון לזהות עיר: קודם מה-segment של <area>, ואם אין – מתוך המילים
    he_area = resolve_city_alias(area, lang) if area else None
    if not he_area:
        for win in range(min(3, len(toks)), 0, -1):
            for i in range(0, len(toks) - win + 1):
                phrase = "-".join(toks[i:i+win])
                he_found = resolve_city_alias(phrase, lang)
                if he_found:
                    he_area = he_found
                    break
            if he_area:
                break

    # 2) ניסיון לזהות שירות…
    svc_key = None
    for win in range(min(3, len(toks)), 0, -1):
        for i in range(0, len(toks) - win + 1):
            phrase = "-".join(toks[i:i+win])
            key = resolve_service_key(phrase)
            if key:
                svc_key = key
                break
        if svc_key:
            break

    # 3) …ואם זוהה שירות – ממפים אותו ל"תחום" (שזה מה שנרצה להציג)
    he_field = None
    if svc_key:
        he_field = SERVICE_REGISTRY.get(svc_key, {}).get("field_he")

    # 4) אם לא זוהה שירות, ננסה לזהות תחום ישירות (שיפוצים/אינסטלטורים/חשמלאים/מנעולנים)
    if not he_field:
        for win in range(min(3, len(toks)), 0, -1):
            for i in range(0, len(toks) - win + 1):
                phrase = "-".join(toks[i:i+win])
                he = resolve_field_alias(phrase, lang)
                if he in CANON_FIELDS_HE:
                    he_field = he
                    break
            if he_field:
                break

    # 5) יעד: תמיד רשימת תחום (workers list). שירות משמש רק כגשר -> תחום.
    qs = request.query_string.decode('utf-8') if request.query_string else ''
    if he_field:
        canon_field_slug = localize_field_slug(he_field, lang)
        canon_area_slug  = localize_city_slug(he_area, lang) if he_area else None
        target = url_for('show_workers', lang=lang, field=canon_field_slug, area=canon_area_slug)
        if qs: target = f"{target}?{qs}"
        return redirect(target, code=301)

    # לא זיהינו כלום → 404
    return not_found(404)






# ------------------------------
# Admin
# ------------------------------
@app.route('/admin')
def admin():
    pending_list = read_json_file(PENDING_FILE)
    return render_template('admin.html', pending_list=pending_list)

@app.route('/approve/<int:index>', methods=['POST'])
def approve_professional(index):
    pending_list = read_json_file(PENDING_FILE)
    approved_list = read_json_file(APPROVED_FILE)

    # עוזרי טקסט מקומיים (לא תלויים ב-ai_writer)
    def _sanitize_he(text: str) -> str:
        if not text: return text
        fixes = {
            "נקייהיה": "נקייה",
            "מסתפק במתח": "עבודות חשמל",
            "מסתפקים במתח": "עבודות חשמל",
            " ,": ",", "  ": " ",
        }
        for src, dst in fixes.items():
            text = text.replace(src, dst)
        return re.sub(r"\s{2,}", " ", text).strip()

    def _strip_emergency(text: str) -> str:
        if not text: return text
        t = re.sub(r"\s?זמין(?:ה)?\s+ל(?:קריאות|חירום).{0,30}?24\s*/?\s*7", "", text)
        t = re.sub(r"\s?חירום\s*24\s*/?\s*7", "", t)
        return re.sub(r"\s{2,}", " ", t).strip()

    def _field_key_for_variants(s: str) -> str:
        s = (s or "").strip()
        if s in ("חשמלאים", "חשמלאי"):
            return "חשמלאי"
        if s in ("אינסטלטורים", "אינסטלטור"):
            return "אינסטלטור"
        return s

    if 0 <= index < len(pending_list):
        # שולפים את הפריט המאושר מתוך הפנדינג
        item = pending_list.pop(index)

        # מזהה חדש
        existing_ids = [int(w.get('worker_id', 0)) for w in approved_list]
        max_id = max(existing_ids) if existing_ids else 0
        item['worker_id'] = str(max_id + 1)

        # קנוניזציה + מילוי שדות
        normalize_worker_fields(item)

        # נשמור תמיד את תתי-התחומים כפי שהוזנו בטופס (ולא של המודל)
        sub_services = [s for s in (item.get('sub_services') or []) if isinstance(s, str) and s.strip()]
        if sub_services:
            item['specializations'] = sub_services[:]   # לשימוש בטמפלט "מה אני עושה"
        else:
            item['specializations'] = []

        # --- שימוש בטיוטת AI אם ביקשו בטופס ---
        use_ai = request.form.get('use_ai') in ('1', 'on', 'true', 'True')
        if use_ai and (item.get('ai_status') == 'ready'):
            # שליפה בטוחה של שדות מהטיוטה
            ai_bio_short = (item.get('ai_draft_bio_short') or item.get('ai_draft_bio') or '').strip()
            ai_bio_full  = (item.get('ai_draft_bio_full')  or item.get('ai_draft_bio') or '').strip()

            # מחיקת כפילות "חירום 24/7" אם מציגים באדג'
            if item.get('offers_emergency'):
                ai_bio_short = _strip_emergency(ai_bio_short)
                ai_bio_full  = _strip_emergency(ai_bio_full)

            # ניקוי עברית בסיסי
            ai_bio_short = _sanitize_he(ai_bio_short)
            ai_bio_full  = _sanitize_he(ai_bio_full)

            # services_sentence: מהמודל אם קיים, אחרת מהרשימה שסומנה
            if item.get('ai_draft_services_sentence'):
                services_sentence = _sanitize_he(item['ai_draft_services_sentence'].lstrip("שירותים:").strip())
            else:
                services_sentence = _sanitize_he(", ".join(sub_services)) if sub_services else ""

            # seo_title: מהמודל או ברירת מחדל ללא עיר
            if item.get('ai_draft_seo_title'):
                seo_title = _sanitize_he(item['ai_draft_seo_title'].strip())
            else:
                name  = (item.get('name') or item.get('company_name') or '').strip()
                field = (item.get('field') or '').strip()
                field_singular = field.rstrip("ים").rstrip("ות") if field else field
                seo_title = _sanitize_he(f"{field_singular or field} – {name}".strip(" – "))

            # שמירה בשדות חדשים
            item['bio_short'] = ai_bio_short
            item['bio_full']  = ai_bio_full
            item['services_sentence'] = services_sentence
            item['services_list'] = sub_services[:]
            item['seo_title'] = seo_title

            # תאימות—description = התיאור המלא
            if ai_bio_full:
                item['description'] = ai_bio_full

        # --- נעילת וריאנט לעובד המאושר (כדי לא לשכפל וריאנטים) ---
        try:
            used_variant_id = (item.get("ai_variant_used") or "").strip()
            if used_variant_id:
                fk = _field_key_for_variants(item.get("field") or item.get("field_he") or "")
                if fk:
                    assign_variant(fk, used_variant_id, item['worker_id'])
        except Exception as e:
            try:
                app.logger.warning(f"assign_variant failed: {e}")
            except Exception:
                pass

        # מוסיפים לרשימת המאושרים ושומרים קבצים
        approved_list.append(item)
        write_json_file(PENDING_FILE, pending_list)
        write_json_file(APPROVED_FILE, approved_list)

        flash(f"בעל המקצוע {item.get('company_name') or item.get('name')} אושר בהצלחה!")

    return redirect(url_for('admin'))




@app.route('/delete_pending/<int:index>', methods=['POST'])
def delete_pending(index):
    pending_list = read_json_file(PENDING_FILE)
    if 0 <= index < len(pending_list):
        pending_list.pop(index)
        write_json_file(PENDING_FILE, pending_list)
    return redirect(url_for('admin'))


# ====== Analytics: API + helpers + admin pages (monthly + all-time with search) ======

# --- api_track: מקבל גם path מתוך ה-payload/Referer ---
@csrf.exempt
@app.post('/api/track')
def api_track():
    data = request.get_json(silent=True) or {}
    event = (data.get('event') or '').strip()
    worker_id = str(data.get('worker_id') or '').strip()
    if event not in ('view', 'click_call', 'click_whatsapp') or not worker_id:
        return jsonify({"ok": False, "error": "bad_request"}), 400

    page_path = (data.get('path') or '').strip()
    if not page_path:
        page_path = _extract_path_from_referer(request.headers.get('Referer', '')) or '/'

    logged = log_analytics_event(event, worker_id, page_path=page_path)
    return jsonify({"ok": True, "logged": bool(logged)})

# --- נתיב מתוך Referer (למקרה שאין path ב-payload) ---
def _extract_path_from_referer(ref: str) -> str:
    try:
        if not ref:
            return ''
        p = urlparse(ref)
        path = p.path or ''
        if p.query:
            path += '?' + p.query
        return path
    except Exception:
        return ''

# --- איטרציה על אירועים (יום/חודש/כלל הקבצים) ---
def _iter_day_events(day_str):
    """כל האירועים של יום מסוים (YYYY-MM-DD)."""
    if not day_str or not os.path.isdir(ANALYTICS_DIR):
        return
    file_name = f"{day_str}.jsonl"
    path = os.path.join(ANALYTICS_DIR, file_name)
    if not os.path.isfile(path):
        return
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except Exception:
                    continue
    except Exception:
        return


def _iter_month_events(month_str):
    """כל האירועים של חודש מסוים (YYYY-MM)."""
    if not month_str or not os.path.isdir(ANALYTICS_DIR):
        return
    prefix = month_str + '-'
    for name in os.listdir(ANALYTICS_DIR):
        if name.startswith(prefix) and name.endswith('.jsonl'):
            path = os.path.join(ANALYTICS_DIR, name)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            yield json.loads(line)
                        except Exception:
                            continue
            except Exception:
                continue


def _iter_all_events():
    """כל האירועים מכל הקבצים בתיקיית האנליטיקס."""
    if not os.path.isdir(ANALYTICS_DIR):
        return
    for name in os.listdir(ANALYTICS_DIR):
        if not name.endswith('.jsonl'):
            continue
        path = os.path.join(ANALYTICS_DIR, name)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        yield json.loads(line)
                    except Exception:
                        continue
        except Exception:
            continue

# --- אגרגציה בסיסית לאירועים לפי עובד ---
def _aggregate_events(events_iterable):
    """מקבץ לפי worker_id: views / calls / wa."""
    per_worker = defaultdict(lambda: {'views': 0, 'calls': 0, 'wa': 0})
    for e in events_iterable or []:
        wid = str(e.get('worker_id') or '').strip()
        ev = str(e.get('event') or '').strip().lower()
        if not wid:
            continue
        if ev == 'view':
            per_worker[wid]['views'] += 1
        elif ev in ('click_call', 'call'):
            per_worker[wid]['calls'] += 1
        elif ev in ('click_whatsapp', 'wa'):
            per_worker[wid]['wa'] += 1
    return per_worker


def _analytics_available_months():
    """רשימת חודשים (YYYY-MM) שקיימים להם קבצי אנליטיקס."""
    months = set()
    if not os.path.isdir(ANALYTICS_DIR):
        return []
    for name in os.listdir(ANALYTICS_DIR):
        # קבצים בפורמט YYYY-MM-DD.jsonl
        if len(name) >= 17 and name.endswith('.jsonl'):
            m = name[:7]
            if re.match(r'^\d{4}-\d{2}$', m):
                months.add(m)
    return sorted(months, reverse=True)


# --- ניקוד חיפוש: שם/מקצוע/עיר (HE/EN/RU שכבר שמורים באובייקט העובד) ---
def _search_score(worker, q: str) -> int:
    if not q:
        return 0
    q = q.strip().lower()
    tokens = [t for t in q.split() if t]
    text_name = ((worker.get('company_name') or '') + ' ' + (worker.get('name') or '')).lower()
    text_field = ((worker.get('field') or '') + ' ' + (worker.get('field_en') or '') + ' ' + (worker.get('field_ru') or '')).lower()
    text_city = (worker.get('base_city') or '').lower()

    score = 0
    for t in tokens:
        if t in text_name:
            score += 30
        if t in text_field:
            score += 20
        if t in text_city:
            score += 10
    combo = f"{text_name} {text_field} {text_city}"
    if q and q in combo:
        score += 5
    return score


def _rows_for_all_workers(per_stats: dict, q: str):
    """ יוצר רשומות טבלה לכל העובדים המאושרים (גם בלי אירועים).
        per_stats = dict של {worker_id: {views, calls, wa}} """
    approved = read_json_file(APPROVED_FILE)
    rows = []
    for w in approved:
        wid = str(w.get('worker_id') or '')
        stats = per_stats.get(wid, {'views': 0, 'calls': 0, 'wa': 0})
        v = int(stats.get('views', 0))
        c = int(stats.get('calls', 0))
        wa = int(stats.get('wa', 0))
        total_clicks = c + wa
        ctr_call = round((c / v * 100), 1) if v else 0.0
        ctr_wa = round((wa / v * 100), 1) if v else 0.0
        rows.append({
            'worker_id': wid,
            'name': (w.get('company_name') or w.get('name') or f'#{wid}'),
            'field': w.get('field') or '',
            'city': w.get('base_city') or '',
            'views': v,
            'calls': c,
            'wa': wa,
            'ctr_call': ctr_call,
            'ctr_wa': ctr_wa,
            'total_clicks': total_clicks,
            'score': _search_score(w, q),
        })
    # אם יש חיפוש – מיין לפי רלוונטיות ואז קליקים/צפיות; אחרת לפי קליקים/צפיות
    if q:
        rows.sort(key=lambda r: (r['score'], r['total_clicks'], r['views']), reverse=True)
    else:
        rows.sort(key=lambda r: (r['total_clicks'], r['views']), reverse=True)
    return rows


def _monthly_totals(month_str):
    agg = _aggregate_events(_iter_month_events(month_str))
    total_views = sum(v['views'] for v in agg.values())
    total_calls = sum(v['calls'] for v in agg.values())
    total_wa = sum(v['wa'] for v in agg.values())
    return {'views': total_views, 'calls': total_calls, 'wa': total_wa}


# --- ניהול אנליטיקס: אינדקס / חודשי / כל הזמנים ---
@app.route('/admin/analysis/')
def analysis_index():
    months = _analytics_available_months()

    # סכומים לכל חודש
    month_cards = []
    for m in months:
        t = _monthly_totals(m)
        month_cards.append({'month': m, **t})

    # סכום all-time
    agg_all = _aggregate_events(_iter_all_events())
    all_totals = {
        'views': sum(v['views'] for v in agg_all.values()),
        'calls': sum(v['calls'] for v in agg_all.values()),
        'wa': sum(v['wa'] for v in agg_all.values()),
    }
    return render_template('analysis/index.html', months=months, month_cards=month_cards, all_totals=all_totals)


@app.route('/admin/analysis/monthly')
def analysis_monthly():
    # בחירת חודש + חיפוש
    month = request.args.get('month')
    q = (request.args.get('q') or '').strip()

    months = _analytics_available_months()
    if not month:
        month = months[0] if months else datetime.utcnow().strftime('%Y-%m')

    per_worker = _aggregate_events(_iter_month_events(month))
    rows = _rows_for_all_workers(per_worker, q)
    totals = _monthly_totals(month)

    return render_template('analysis/monthly.html', month=month, months=months, rows=rows, totals=totals, q=q)


# נשמר את ה-route הישן 'all' כדי שלא ישברו קישורים קיימים
@app.route('/admin/analysis/all')
def admin_analysis_all():
    q = (request.args.get('q') or '').strip()
    per_worker = _aggregate_events(_iter_all_events())
    rows = _rows_for_all_workers(per_worker, q)
    totals = {
        'views': sum(r['views'] for r in rows),
        'calls': sum(r['calls'] for r in rows),
        'wa': sum(r['wa'] for r in rows),
    }
    return render_template('analysis/all_time.html', rows=rows, totals=totals, q=q)


@app.route('/admin/analysis/all-time')
def analysis_all_time():
    return admin_analysis_all()  # קורא את הפונקציה השנייה ומחזיר את אותו הדף ללא redirect


@app.route('/admin/analysis/login', methods=['GET', 'POST'], endpoint='admin_login')
def admin_login():
    next_url = request.args.get('next') or url_for('analysis_index')
    if request.method == 'POST':
        pwd = (request.form.get('password') or '').strip()

        ok = False
        if ADMIN_PASSWORD_HASH:
            ok = check_password_hash(ADMIN_PASSWORD_HASH, pwd)
        elif os.environ.get('ADMIN_PASSWORD_PLAIN'):
            ok = (pwd == os.environ['ADMIN_PASSWORD_PLAIN'])

        if ok:
            session.permanent = True          # ← הוסף שורה זו
            session['is_admin'] = True
            if not is_safe_url(next_url):
                next_url = url_for('analysis_index')
            return redirect(next_url)


        flash('סיסמה שגויה', 'error')

    return render_template('analysis/login.html', next=next_url)






@app.route('/admin/pending/<int:index>/ai-generate', methods=['POST'])
def admin_ai_generate(index):
    """
    כל לחיצה מדפדפת לוריאנט הבא ושומרת את הטיוטה בפנדינג.
    ניתן לאפס קורסור עם פרמטר ?reset=1 אם צריך.
    """
    pending_list = read_json_file(PENDING_FILE)
    if not (0 <= index < len(pending_list)):
        flash("פריט לא קיים", "error")
        return redirect(url_for('admin'))

    item = pending_list[index]

    # מזהה יציב לפנדינג (כי עדיין אין worker_id)
    pre_id = _pre_worker_id(item)

    # איפוס קורסור (אופציונלי): /admin/pending/<i>/ai-generate?reset=1
    if request.args.get("reset") in ("1", "true", "yes"):
        cur = session.get("ai_vcur", {})
        if pre_id in cur:
            cur.pop(pre_id, None)
            session["ai_vcur"] = cur
            session.modified = True

    # --- בחירת גודל המאגר לפי תחום בפועל (עם פולבאק ל-ENV/7) ---
    def _field_key_for_variants(s: str) -> str:
        s = (s or "").strip()
        if s in ("חשמלאים", "חשמלאי"):
            return "חשמלאי"
        if s in ("אינסטלטורים", "אינסטלטור"):
            return "אינסטלטור"
        return s

    field_for_variants = _field_key_for_variants(item.get("field") or "")
    try:
        variants_meta = list_variants(field_for_variants)  # [{'id','label',...}, ...]
        total_variants = len(variants_meta)
    except Exception:
        variants_meta, total_variants = [], 0

    if total_variants <= 0:
        total_variants = int(os.environ.get("AI_VARIANTS_TOTAL", "7"))

    # דפדוף: כל לחיצה מקדמת
    v_idx = _bump_variant_cursor(pre_id, total=total_variants)

    # מכינים payload למנוע הכתיבה:
    # - original_bio: התיאור שבעל המקצוע כתב על עצמו
    # - variant_refresh: האינדקס (קורסור) לשינוי הניסוח/הסדר
    worker = dict(item)
    worker["original_bio"] = item.get("description") or item.get("about") or ""
    worker["variant_refresh"] = v_idx

    try:
        draft = generate_draft(worker, lang='he')  # services.ai_writer תומך ב-variant_refresh
        # נשמור גם את מצב הדפדוף ומטא:
        draft["ai_variant_cursor"] = v_idx
        item.update(draft)

        # נשמור חזרה
        pending_list[index] = item
        write_json_file(PENDING_FILE, pending_list)

        # דגל הצלחה: מציגים גם מזהה וריאנט, ואם ניתן – label
        used_id = (draft.get("ai_variant_used") or "").strip()
        label = ""
        if used_id and variants_meta:
            for v in variants_meta:
                if v.get("id") == used_id:
                    label = v.get("label") or ""
                    break
        suffix = f" • {used_id}" + (f" – {label}" if label else "")
        flash(f"טיוטת AI #{v_idx + 1} נוצרה{suffix}.", "success")

    except Exception as e:
        # לא מפילים—נרשום שגיאה ונמשיך
        item["ai_status"] = "error"
        pending_list[index] = item
        write_json_file(PENDING_FILE, pending_list)
        flash("אירעה שגיאה ביצירת הטיוטה.", "error")

    return redirect(url_for('admin'))







@app.route('/favicon.ico')
def favicon_route():
    # אם השארת את הקובץ בתיקייה static/icons
    return send_from_directory(
        os.path.join(app.root_path, 'static', 'icons'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon'
    )

# ------------------------------
# Error handlers
# ------------------------------
@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404  # ✅ מחזיר סטטוס נכון


@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    # הודעה ידידותית למשתמש + חזרה לעמוד הקודם
    flash('פג תוקף הטופס או חסר אימות אבטחה (CSRF). רענן/י את העמוד ונסה/י שוב.', 'error')
    return redirect(request.referrer or url_for('home', lang=getattr(g, 'current_lang', 'he')))


# ========= REPLACE robots_txt + sitemap_xml WITH THIS =========

from xml.sax.saxutils import escape as _xesc


def _abs_path(path: str) -> str:
    """לבנות URL מוחלט עם BASE_DOMAIN (כדי למנוע דומיין dev בסריקה)."""
    return f"{BASE_DOMAIN.rstrip('/')}{path}"

def _iso(d: datetime | date | None) -> str:
    if not d:
        return date.today().isoformat()
    return (d.date() if isinstance(d, datetime) else d).isoformat()

@app.route('/robots.txt')
def robots_txt():
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /api/",
        "Disallow: /static/upload_pending/",
        "Allow: /",
        f"Sitemap: {BASE_DOMAIN.rstrip('/')}/sitemap.xml",
    ]
    resp = Response("\n".join(lines), mimetype="text/plain; charset=utf-8")
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp



@app.route('/sitemap.xml')
def sitemap_xml():
    """
    Sitemap דינמי מלא: דפי ליבה (עם hreflang), רשימות תחום/עיר שיש להן עובדים,
    ועמודי פרופיל/ביקורות — בכל השפות.
    """
    # --- נתונים מהדיסק ---
    try:
        approved = read_json_file(APPROVED_FILE)  # רשימת עובדים מאושרים
    except Exception:
        approved = []

    reviews_path = os.path.join(DATA_FOLDER, 'worker_reviews.json')
    try:
        all_reviews = read_json_file(reviews_path)
    except Exception:
        all_reviews = []

    # worker_id -> תאריך ביקורת אחרון (ל-lastmod)
    latest_review_by_worker: dict[str, datetime] = {}
    for r in all_reviews:
        wid = str(r.get("worker_id") or "")
        if not wid:
            continue
        try:
            dt = datetime.fromisoformat((r.get("date") or "").replace("Z", ""))
        except Exception:
            dt = None
        if dt and (wid not in latest_review_by_worker or dt > latest_review_by_worker[wid]):
            latest_review_by_worker[wid] = dt

    # mtime של קבצים מרכזיים
    def _file_mtime(path):
        try:
            return datetime.fromtimestamp(os.path.getmtime(path))
        except Exception:
            return None

    site_last_any = max(
        filter(None, (_file_mtime(APPROVED_FILE), _file_mtime(reviews_path))),
        default=None
    )
    today = date.today()

    # ---- מחולל <url> עם hreflang ----
    def url_entry_with_alternates(paths_by_lang: dict[str, str],
                                  lastmod: datetime | date | None,
                                  changefreq: str = "weekly",
                                  priority: str = "0.7") -> str:
        # בחר שורת הבסיס (he אם יש)
        base_lang = "he" if "he" in paths_by_lang else next(iter(paths_by_lang.keys()))
        loc = _abs_path(paths_by_lang[base_lang])
        lines = ["  <url>"]
        lines.append(f"    <loc>{_xesc(loc)}</loc>")
        lines.append(f"    <lastmod>{_iso(lastmod)}</lastmod>")
        lines.append(f"    <changefreq>{changefreq}</changefreq>")
        lines.append(f"    <priority>{priority}</priority>")
        # hreflang לכל השפות הקיימות בקבוצה
        for L, p in paths_by_lang.items():
            lines.append(f'    <xhtml:link rel="alternate" hreflang="{L}" href="{_xesc(_abs_path(p))}" />')
        # x-default → he כברירת מחדל
        lines.append(
            f'    <xhtml:link rel="alternate" hreflang="x-default" href="{_xesc(_abs_path(paths_by_lang.get("he", paths_by_lang[base_lang])))}" />'
        )
        lines.append("  </url>")
        return "\n".join(lines)

    url_items: list[str] = []

    # ---- 1) דפי ליבה בכל השפות (עם hreflang) ----
    static_endpoints = [
        ("home", {}),
        ("works", {}),
        ("niches", {}),
        ("contact", {}),
        ("terms", {}),
        ("privacy", {}),
        ("accessibility", {}),
        ("cookies", {}),
    ]
    for ep, params in static_endpoints:
        if ep not in app.view_functions:
            continue
        group = {}
        for L in SUPPORTED_LANGS:
            try:
                group[L] = url_for(ep, lang=L, **params)
            except Exception:
                # ייתכן שלחלק מהראוטים אין פרמטר lang
                group = {}
                break
        if group:
            url_items.append(
                url_entry_with_alternates(
                    group,
                    site_last_any or today,
                    changefreq="weekly",
                    priority="0.8" if ep == "home" else "0.6"
                )
            )

    # ---- 2) רשימות תחום/עיר — רק קומבינציות שיש להן עובדים בפועל ----
    # נבנה סטים של תחומים קיימים ושל זוגות (תחום, עיר) קיימים לפי approved.json
    existing_fields_he: set[str] = set()
    existing_pairs_he: set[tuple[str, str]] = set()

    for w in approved:
        he_field = _canon_he_field(w.get("field") or w.get("field_he") or "")
        if not he_field:
            continue
        existing_fields_he.add(he_field)

        city_candidates = set()
        base_city = (w.get("base_city") or "").strip()
        if base_city:
            city_candidates.add(base_city)

        for c in (w.get("active_cities") or []):
            if c:
                city_candidates.add(c)

        # אם הוגדר רדיוס — הוסף את כל הערים בטווח
        try:
            r = int(w.get("work_radius") or 0)
        except Exception:
            r = 0
        if r > 0 and base_city in cities_coords:
            for c in get_cities_in_radius(base_city, r):
                city_candidates.add(c)

        for c in city_candidates:
            existing_pairs_he.add((he_field, c))

    # lastmod לרשימות = שינוי ב־approved/reviews
    lists_lastmod = site_last_any or today

    # עמודי "תחום בלבד"
    for he_field in sorted(existing_fields_he):
        group = {}
        for L in SUPPORTED_LANGS:
            f_slug = localize_field_slug(he_field, L)
            group[L] = url_for('show_workers', lang=L, field=f_slug)
        url_items.append(
            url_entry_with_alternates(group, lists_lastmod, changefreq="daily", priority="0.85")
        )

    # עמודי "תחום + עיר"
    for he_field, city_he in sorted(existing_pairs_he):
        group = {}
        for L in SUPPORTED_LANGS:
            f_slug = localize_field_slug(he_field, L)
            c_slug = localize_city_slug(city_he, L)
            group[L] = url_for('show_workers', lang=L, field=f_slug, area=c_slug)
        url_items.append(
            url_entry_with_alternates(group, lists_lastmod, changefreq="daily", priority="0.90")
        )

    # ---- 3) פרופילי עובדים (עמודי הביקורות) בכל השפות ----
    for w in approved:
        wid = str(w.get("worker_id") or "").strip()
        if not wid:
            continue
        w_last = latest_review_by_worker.get(wid, site_last_any or today)
        group = {}
        for L in SUPPORTED_LANGS:
            try:
                group[L] = url_for('worker_reviews', lang=L, worker_id=wid)
            except Exception:
                continue
        if group:
            url_items.append(
                url_entry_with_alternates(group, w_last, changefreq="weekly", priority="0.7")
            )

    # ---- בניית XML ----
    xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
        '        xmlns:xhtml="http://www.w3.org/1999/xhtml">'
    ]
    xml.append("\n".join(url_items))
    xml.append("</urlset>")

    # === השינוי: Cache-Control בכותרות התגובה ===
    resp = Response("\n".join(xml), mimetype="application/xml; charset=utf-8")
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


# ========= END REPLACEMENT =========




# ===== Autocomplete: API בסיסי לבדיקה =====
# ===== Autocomplete: API בסיסי לבדיקה =====
@app.route('/api/suggest', methods=['GET'])
def api_suggest():
    q = (request.args.get('q') or '').strip().lower()
    typ = (request.args.get('type') or '').strip().lower()  # 'area' | 'field'
    lang = (request.args.get('lang') or getattr(g, 'current_lang', 'he') or 'he').strip().lower()

    # --- רשימות קנוניות בעברית (HE) ---
    cities_he = ["תל אביב", "ירושלים", "חיפה", "באר שבע", "פתח תקווה", "נתניה", "אשדוד", "ראשון לציון", "רמת גן", "בת ים"]
    fields_he = ["שיפוצים", "אינסטלטורים", "חשמלאים", "מנעולנים"]  # שמות תואמים לאתר

    # --- פונקציות תצוגה לפי שפה ---
    def label_field(he_value):
        if lang == 'en':
            return (field_map_he_to_en.get(he_value, he_value) or he_value).title()
        if lang == 'ru':
            return field_map_he_to_ru.get(he_value, he_value)
        return he_value  # he

    def label_city(he_value):
        if lang == 'en':
            return (city_map_he_to_en.get(he_value, he_value) or he_value).title()
        if lang == 'ru':
            return city_map_he_to_ru.get(he_value, he_value)
        return he_value  # he

    def norm(s: str) -> str:
        # נרמול פשוט להשוואה: לואוקייס + החלפת מפרידים לרווח
        s = (s or '').strip().lower()
        s = re.sub(r'[_\-]+', ' ', s)
        s = re.sub(r'\s+', ' ', s)
        return s

    results = []
    if typ == 'field':
        base = fields_he
        for he in base:
            lbl = label_field(he)
            # מילות חיפוש אפשריות לכל שפה (כדי שתפוס גם אם מקלידים באנגלית/רוסית)
            synonyms = {
                norm(he),
                norm(lbl),
                norm(field_map_he_to_en.get(he, '')),
                norm(field_map_he_to_ru.get(he, '')),
            }
            if not q or any(q in s for s in synonyms if s):
                results.append({"label": lbl, "value": lbl})
    elif typ == 'area':
        base = cities_he
        for he in base:
            lbl = label_city(he)
            synonyms = {
                norm(he),
                norm(lbl),
                norm(city_map_he_to_en.get(he, '')),
                norm(city_map_he_to_ru.get(he, '')),
            }
            if not q or any(q in s for s in synonyms if s):
                results.append({"label": lbl, "value": lbl})
    else:
        results = []

    # עד 8 תוצאות
    return jsonify({"ok": True, "results": results[:8]})


# ===== iOS inline-CSS fallback (only for Safari on iPhone/iPad) =====
IOS_INLINE_CSS_FILES = ['css/style.css', 'css/navbar.css']  # תוסיף/תגרע לפי מה שיש לך

def _is_ios_safari(ua: str) -> bool:
    if not ua:
        return False
    u = ua.lower()
    isiOS = ('iphone' in u) or ('ipad' in u) or ('ipod' in u)
    if not isiOS:
        return False
    # חריג: כרום/פיירפוקס/אדג' על iOS
    if 'crios' in u or 'fxios' in u or 'edgios' in u or 'opios' in u:
        return False
    # Safari קלאסי או WebView
    return 'safari' in u or 'applewebkit' in u

def _read_static_text(rel_path: str) -> str:
    try:
        fullpath = os.path.join(STATIC_DIR, rel_path)

        with open(fullpath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return ''

@app.after_request
def inline_css_for_ios(resp):
    """
    מזריק CSS אינליין כפתרון ל־Safari ב־iOS — רק בעמודי HTML.
    לעולם לא נוגע בתמונות/קבצי סטטי/ראוטים מיוחדים, ולא אם יש X-Bypass-Inline.
    """
    try:
        # הוסף שתי בדיקות הגנה כלליות ממש בתחילת הפונקציה:
        if "." in (request.path or ""):  # כל נתיב עם סיומת קובץ = אל תיגע
            return resp
        if not _is_ios_safari(request.headers.get("User-Agent", "")):  # תפעל רק בספארי על iOS
            return resp

        path = (request.path or "")
        # 1) דלג תמיד על קבצים/אזורי אתר שלא רוצים לגעת בהם
        if (path.startswith("/static/") or
            path.startswith("/admin")  or
            path.startswith("/api/")   or
            path.startswith("/img/")   or
            resp.headers.get("X-Bypass-Inline") == "1"):
            return resp

        # 2) אם זו תגובה שהיא תמונה — לא לגעת בכלל
        ct = (resp.headers.get("Content-Type") or "").lower()
        if ct.startswith("image/"):
            return resp

        # 3) מטפלים רק ב־GET 200 וב־HTML
        if request.method != "GET" or resp.status_code != 200:
            return resp
        if "text/html" not in ct:
            return resp

        # 4) אל תזריק פעמיים
        marker = "<!--__ios_inline_css__-->"
        resp.direct_passthrough = False
        html = resp.get_data(as_text=True)
        if marker in html:
            return resp

        # 5) קריאת קבצי ה־CSS והזרקה ל־<head>
        css_parts = []
        for rel in IOS_INLINE_CSS_FILES:
            txt = _read_static_text(rel)  # פונקציית עזר שקוראת קובץ מתוך static
            if txt:
                css_parts.append(f"/* inline: {rel} */\n{txt}\n")
        if not css_parts:
            return resp

        style_tag = marker + "\n<style>\n" + "\n".join(css_parts) + "\n</style>\n"
        head_close = "</head>"
        idx = html.lower().find(head_close)
        if idx != -1:
            actual_close = html[idx:idx+len(head_close)]
            html = html[:idx] + style_tag + actual_close + html[idx+len(head_close):]
        else:
            html = style_tag + html

        resp.set_data(html)
        return resp

    except Exception:
        # במקרה של תקלה — לא מפילים את הבקשה, פשוט מחזירים כמות־שהיא
        return resp










@app.after_request
def add_noindex_header(resp):
    if (request.path or '').startswith('/admin/'):
        resp.headers['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
    return resp



@app.route("/_debug/img/<path:name>")
def _debug_img(name):
    p = os.path.join(STATIC_DIR, name)

    if not os.path.isfile(p):
        return Response(f"NOT FOUND: {p}", status=404, mimetype="text/plain; charset=utf-8")
    with open(p, "rb") as f:
        data = f.read()
    mt, _ = mimetypes.guess_type(p)
    return Response(data, mimetype=mt or "application/octet-stream")


@app.route("/test_static")
def test_static():
    return render_template("test_static.html")



    


@app.route("/warmup")
def warmup():
    v = request.args.get("v", "0")
    flag = url_for("static", filename="flags/israel-flag-png-large.png", v=v)
    hero = url_for("static", filename="photo1.jpg", v=v)
    html = f"""<!doctype html><meta charset="utf-8">
<title>warm</title>
<style>body{{margin:0;padding:0}}</style>
<img src="{flag}" alt="" loading="eager" decoding="async">
<img src="{hero}" alt="" loading="eager" decoding="async">
<script>
  // נסיון חוזר אחרי 3 ו-10 שניות (ngrok לפעמים מציק)
  const u1 = "{flag}", u2 = "{hero}";
  function kick(u) {{
    const i = new Image(); i.decoding="async"; i.loading="eager";
    i.src = u + (u.includes('?')?'&':'?') + '_w=' + Date.now();
  }}
  setTimeout(()=>{{ kick(u1); kick(u2); }}, 3000);
  setTimeout(()=>{{ kick(u1); kick(u2); }}, 10000);
</script>"""
    return Response(html, mimetype="text/html; charset=utf-8",
                    headers={"Cache-Control":"no-store, no-cache, must-revalidate, max-age=0"})





# =====================================================
# 🧮 Estimate AI Calculator (מחשבון הצעת מחיר)
# =====================================================

# --- עמוד המחשבון ---


def normalize_lang(lang: str) -> str:
    lang = (lang or "he").lower()
    return lang if lang in SUPPORTED_LANGS else "he"

def load_estimate_i18n(lang: str):
    """טוען translations/<lang>/estimate.json; מחזיר {} אם אין."""
    lang = normalize_lang(lang)
    path = os.path.join(app.root_path, "translations", lang, "estimate.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _swap_lang_in_path(path: str, new_lang: str) -> str:
    """מחליף/מזריק את מקטע השפה בנתיב הנוכחי, ושומר את ה־/ הסופי אם היה."""
    want_trailing = path.endswith("/")
    parts = [p for p in path.split("/") if p]
    if parts and parts[0] in SUPPORTED_LANGS:
        parts[0] = new_lang
    else:
        parts.insert(0, new_lang)
    new_path = "/" + "/".join(parts)
    if want_trailing and not new_path.endswith("/"):
        new_path += "/"
    return new_path



@app.route('/<lang>/works/<field>/', defaults={'area': None})
@app.route('/<lang>/works/<field>/<area>')
def works_to_workers(lang, field, area):
    # הפניה קאנונית לעמוד הרשימה האמיתי
    return redirect(url_for('show_workers', lang=lang, field=field, area=area), code=301)



@app.template_global()
def url_for_lang(endpoint=None, lang=None, **kwargs):
    """
    שימושים נתמכים:
      - url_for_lang('home')                => url_for('home', lang=current)
      - url_for_lang('home', lang='en')     => url_for('home', lang='en')
      - url_for_lang(lang='ru')             => אותו דף בשפה אחרת (ללא שינוי endpoint)
    """
    new_lang = normalize_lang(lang or getattr(g, "current_lang", "he"))

    # --- אליאסים לשמות endpoint ישנים/בטמפלייטים ---
    ENDPOINT_ALIASES = {
        "workers": "show_workers",   # שם ישן/בטמפלייט → ה־endpoint האמיתי
        # תוכל להוסיף כאן אליאסים נוספים בעתיד אם צריך
    }

    if endpoint:
        endpoint = ENDPOINT_ALIASES.get(endpoint, endpoint)
        kwargs["lang"] = new_lang
        return url_for(endpoint, **kwargs)

    # אין endpoint => מחליפים שפה באותו הנתיב (כולל שמירת ה־query string)
    new_path = _swap_lang_in_path(request.path, new_lang)
    qs = request.query_string.decode("utf-8", "ignore")
    return new_path + (("?" + qs) if qs else "")


# ראוט עם שפה + תמיכה גם בלי הסלאש (strict_slashes=False)
@app.route("/<lang>/estimate/", strict_slashes=False)
def estimate(lang):
    lang = normalize_lang(lang)
    g.current_lang = lang
    i18n_est = load_estimate_i18n(lang)
    return render_template("estimate.html", i18n_est=i18n_est)

# ראוט בלי שפה שמפנה לברירת מחדל (או לשפה שכבר נשמרה ב-g)
@app.route("/estimate/", strict_slashes=False)
def estimate_no_lang():
    lang = normalize_lang(getattr(g, "current_lang", None) or "he")
    return redirect(url_for("estimate", lang=lang), code=302)



@csrf.exempt
@app.route("/api/estimate", methods=["POST"])
def api_estimate():
    try:
        data = request.get_json(silent=True) or {}
        category = (data.get("category") or "").strip().lower()
        job_id   = (data.get("job") or "").strip().lower()
        subtype  = (data.get("subtype") or "").strip().lower()
        answers  = data.get("answers")
        lang     = (data.get("lang") or getattr(g, "current_lang", "he") or "he").strip().lower()

        if not category:
            return jsonify({"error": "Missing category"}), 400

        base_root = os.path.join(app.root_path, "data", "estimate_ai")

        def get_path(cat: str, lng: str):
            return os.path.join(base_root, lng, f"{cat}.json")

        # קודם ננסה בשפה המבוקשת, ואם לא קיים – ניפול לעברית
        file_path = get_path(category, lang)
        if not os.path.exists(file_path):
            fallback_path = get_path(category, "he")
            if os.path.exists(fallback_path):
                file_path = fallback_path
                lang = "he"  # כדי שהתרגומים ילקחו נכון
            else:
                return jsonify({"error": f"Unknown category: {category} (lang={lang})"}), 400

        with open(file_path, "r", encoding="utf-8") as f:
            catalog = json.load(f)

        def t(val, lng=lang):
            """בחר טקסט לפי שפה; נופל לעברית ואז לכל ערך קיים."""
            if isinstance(val, dict):
                return val.get(lng) or val.get("he") or next(iter(val.values()), "")
            return val

        jobs = catalog.get("jobs", [])

        # ── שלב 1: רק קטגוריה → מחזירים jobs
        if category and not job_id:
            return jsonify({
                "category": category,
                "jobs": [{"id": (j.get("id") or ""), "label": t(j.get("label"))} for j in jobs]
            })

        # מאתרים job
        job = next((j for j in jobs if (j.get("id") or "").lower() == job_id), None)
        if not job:
            return jsonify({"error": "Unknown job"}), 400

        # ── שלב 2: יש job אבל אין subtype → מחזירים subtypes
        subtypes = job.get("subtypes") or []
        if job_id and not subtype:
            return jsonify({
                "category": category,
                "job": job_id,
                "subtypes": [{"id": (s.get("id") or ""), "label": t(s.get("label"))} for s in subtypes]
            })

        # מאתרים subtype
        sub = next((s for s in subtypes if (s.get("id") or "").lower() == subtype), None)
        if not sub:
            return jsonify({"error": "Unknown subtype"}), 400

        questions = sub.get("questions", [])

        # ── שלב 3: אם אין answers → מחזירים שאלות
        if not isinstance(answers, dict):
            return jsonify({
                "category": category,
                "job": job_id,
                "subtype": subtype,
                "questions": [
                    {
                        "id": q.get("id"),
                        "text": t(q.get("text")),
                        "options": [{"value": o.get("value"), "label": t(o.get("label"))}
                                    for o in (q.get("options") or [])]
                    }
                    for q in questions
                ],
                "result_note": t(sub.get("result_note")) or t(job.get("result_note")) or t(catalog.get("result_note"))
            })

        # ── שלב 4: חישוב מחיר
        def get_base(bp):
            if isinstance(bp, list) and len(bp) == 2 and all(isinstance(x, (int, float)) for x in bp):
                return float(bp[0]), float(bp[1])
            return 0.0, 0.0

        base_min, base_max = (get_base(sub.get("base_price")) if sub.get("base_price") else
                              get_base(job.get("base_price")) if job.get("base_price") else
                              get_base(catalog.get("base_price")))
        total_min, total_max = base_min, base_max
        multiplier_total = 1.0
        applied = []

        def find_opt(qid, val):
            for q in questions:
                if q.get("id") == qid:
                    for o in (q.get("options") or []):
                        if o.get("value") == val:
                            return q, o
            return None, None

        for qid, val in answers.items():
            q, o = find_opt(qid, val)
            if not o:
                continue
            label = t(o.get("label")) or str(val)

            delta = o.get("delta")
            if isinstance(delta, list) and len(delta) == 2 and all(isinstance(x, (int, float)) for x in delta):
                total_min += float(delta[0])
                total_max += float(delta[1])
                applied.append(f"{t(q.get('text'))}: {label}")

            mult = o.get("multiplier")
            if isinstance(mult, (int, float)) and mult > 0:
                multiplier_total *= float(mult)
                applied.append(f"{t(q.get('text'))}: {label} (x{mult})")

        total_min = int(round(total_min * multiplier_total))
        total_max = int(round(total_max * multiplier_total))

        return jsonify({
            "category": category,
            "job": job_id,
            "subtype": subtype,
            "price": f"₪{total_min}–₪{total_max}",
            "price_min": total_min,
            "price_max": total_max,
            "description": " · ".join(applied) if applied else "",
            "result_note": t(sub.get("result_note")) or t(job.get("result_note")) or t(catalog.get("result_note"))
        })

    except Exception as e:
        app.logger.exception("api_estimate error: %s", e)
        return jsonify({"error": "Server error"}), 500



# ------------------------------ #
# הפעלת האפליקציה
# ------------------------------ #
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)






