# services/ai_writer.py
from datetime import datetime
import os, re, json, hashlib
from .ai_variants import pick_next_variant  # אם אין רישום – נופל לפולבאק פנימי

# =========================
#  Utilities
# =========================
def _get_str(d: dict, *keys, default=""):
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return default

def _truthy(x) -> bool:
    s = str(x).strip().lower()
    return s in ("1","true","yes","y","on")

def _first_name(full: str) -> str:
    return (full or "").strip().split()[0] if (full or "").strip() else ""

# =========================
#  Style pick (for variety)
# =========================
_STYLES = [
    {"name": "ישיר ומקצועי"},
    {"name": "חם ואמין"},
    {"name": "טכני נקי"},
    {"name": "תכל'ס"},
    {"name": "רגוע ושקוף"},
    {"name": "ענייני ומדויק"},
]
def _style_for_worker(worker: dict) -> dict:
    key = f"{worker.get('name','')}|{worker.get('company_name','')}|{worker.get('phone','')}|{worker.get('field','')}"
    h = hashlib.md5(key.encode('utf-8', errors='ignore')).hexdigest()
    return _STYLES[int(h, 16) % len(_STYLES)]

# =========================
#  Variant seeding
# =========================
def _approved_worker_id(worker: dict) -> str:
    wid = worker.get("worker_id") or worker.get("id") or worker.get("workerId")
    return str(wid).strip() if wid is not None else ""

def _compute_provisional_seed(worker: dict) -> str:
    base = f"{_get_str(worker,'name')}|{_get_str(worker,'phone')}|{_get_str(worker,'field')}|{_get_str(worker,'company_name')}"
    return hashlib.sha1(base.encode("utf-8", errors="ignore")).hexdigest()[:16]

def _variant_seed(worker: dict) -> str:
    saved = _get_str(worker, "ai_variant_seed")
    if saved:
        return saved
    wid = _approved_worker_id(worker)
    if wid:
        return f"id:{wid}"
    return f"pre:{_compute_provisional_seed(worker)}"

# =========================
#  Source bio + policy (no guessing!)
# =========================
def _extract_source_bio(worker: dict) -> str:
    return _get_str(worker, "original_bio","original_description","bio_original","bio_raw","bio","notes","description")

def _build_policy(worker: dict) -> dict:
    """
    טענות תלויות-מדיניות מותרות *רק* אם יש דגל מפורש.
    אין ניחוש ‘מוסמך/מורשה’/‘24-7’/‘חשבונית’/‘אחריות’ מהתיאור החופשי.
    """
    return {
        "licensed": _truthy(worker.get("is_licensed")) or _truthy(worker.get("certified")),
        "license_number": _get_str(worker, "license_number","license","license_no","license_num"),
        "insured": _truthy(worker.get("insured")),
        "emergency": _truthy(worker.get("offers_emergency")),
        "warranty_years": int(worker.get("warranty_years") or 0),
        "invoice_vat": _truthy(worker.get("invoice_vat")) or _truthy(worker.get("issue_invoice")),
    }

def _cert_suffix(policy: dict) -> str:
    """מוסיף ‘מוסמך’ רק אם policy['licensed'] True (לא לפי טקסט חופשי)."""
    return "מוסמך" if policy.get("licensed") else ""

# =========================
#  Voice & safe echoes from bio
# =========================
def _derive_voice_tags(source_bio: str):
    # שואבים מילים/ערכים שאפשר להזכיר בבטחה
    s = (source_bio or "").replace("־","-").replace("–","-").lower()
    tags = []
    if re.search(r"עמידה\s+ב(?:לווחות|לוחות)\s+זמנים|בזמנים", s): tags.append("עמידה בלוחות זמנים")
    if re.search(r"מחירים?\s+הוגנים?|שקיפות\s+בתמחור|שקיפות", s): tags.append("שקיפות בתמחור")
    if re.search(r"יחס\s+אישי|ליווי\s+צמוד", s): tags.append("יחס אישי וליווי צמוד")
    out, seen = [], set()
    for t in tags:
        if t not in seen:
            out.append(t); seen.add(t)
        if len(out) >= 2: break
    return out

def _voice_line(tags: list[str]) -> str:
    tags = [t for t in tags if isinstance(t, str) and t.strip()]
    if not tags: return ""
    if len(tags) == 1: return f"דגש על {tags[0]}."
    return f"דגש על {tags[0]} ו{tags[1]}."

# =========================
#  Fallback service hints (optional, per some common trades)
# =========================
_KNOWN_PATTERNS = {
    "חשמלאי": [
        "תיקון קצרי חשמל",
        "התקנת שקעים ומפסקים",
        "שדרוג לוח תלת פאזי",
        "התקנת תאורה",
        "תכנון נקודות חשמל",
        "הכנת תשתיות לדוד/מזגן",
        "איתור תקלות חשמל",
        "התקנת מאוורר תקרה",
    ],
    "אינסטלטור": [
        "פתיחת סתימות",
        "איתור נזילות",
        "איתור ותיקון פיצוצי צנרת",
        "החלפת קווי מים וביוב",
        "התקנת כלים סניטריים",
        "הגברת לחץ מים",
        "בדיקת לחץ",
        "ניאגרות סמויות",
        "שיפוץ חדר אמבטיה",
        "טוחן אשפה",
        "התקנת נקודת מים",
    ],
}

def _infer_services_from_bio(field: str, source_bio: str):
    base = []
    f = (field or "").strip()
    if "חשמל" in f or "חשמלא" in f:
        base = _KNOWN_PATTERNS["חשמלאי"]
    elif "אינסטל" in f:
        base = _KNOWN_PATTERNS["אינסטלטור"]
    if not base or not source_bio:
        return []
    s = (source_bio or "").replace("־","-").replace("–","-")
    # מיפוי אנגלי נפוץ → עברית, כדי שזיהוי יעבוד
    s = s.replace("Electrical work", "עבודות החשמל").replace("electrical work", "עבודות החשמל")
    found = []
    for item in base:
        key = item.split()[0]
        if key in s or item in s:
            found.append(item)
    if len(found) < 2:
        return base[:4]
    return [x for x in base if x in found]

# =========================
#  Hebrew normalization / safety scrubbing
# =========================
_CITY_PAT = re.compile(
    r"\s?ב(?:תל\s?אביב(?:-יפו)?|יפו|ירושלים|חיפה|באר\s?שבע|פתח\s?תקווה|נתניה|אשדוד|ראשון\s?לציון|רחובות|כפר\s?סבא|רעננה|מודיעין|בית\sשמש|חולון|בת\sים|הרצליה|אשקלון|נהריה|עפולה|רמת\sגן|גבעתיים|נוף\sהגליל|טבריה|צפת|כרמיאל|אילת)\b",
    flags=re.IGNORECASE
)
_LATIN = re.compile(r"[A-Za-z]+(?:[ -]*[A-Za-z]+)*")
_EXP_NUM_PAT = re.compile(
    r"(?:עם\s+)?(?:\d{1,2}\s*(?:שנה|שנות)\s*(?:ניסיון|נסיון)|וותק\s*(?:של)?\s*\d{1,2}\s*(?:שנים|שנה)|ניסיון\s*(?:של)?\s*\d{1,2}\s*(?:שנים|שנה))"
)
_EXP_GENERIC_PAT = re.compile(r"(?:בעל(?:ת)?\s+ניסיון|ניסיון\s+רב|רב\s+ניסיון)")

def _strip_areas(t: str) -> str:
    return _CITY_PAT.sub("", t or "")

def _strip_latin(t: str) -> str:
    if not t: return t
    # תיקונים קטנים לפני הסרה
    t = t.replace("Electrical work", "עבודות החשמל").replace("electrical work", "עבודות החשמל")
    t = _LATIN.sub("", t)
    return re.sub(r"\s{2,}", " ", t).strip()

def _strip_experience(t: str) -> str:
    t = _EXP_NUM_PAT.sub("", t or "")
    t = _EXP_GENERIC_PAT.sub("", t)
    t = re.sub(r"\s{2,}", " ", t)
    t = re.sub(r"\s+([,.;:])", r"\1", t)
    return t.strip()

_SERVICE_CANON_MAP = {
    "שדרוג ללוח תלת פאזי": "שדרוג לוח תלת פאזי",
    "שדרוג לוחות תלת פאזי": "שדרוג לוח תלת פאזי",
    "שדרוג לוחות חשמל לתלת פאזי": "שדרוג לוח תלת פאזי",
    "שדרוג לוחות חשמל": "שדרוג לוח תלת פאזי",
    "תשתיות לדוד או מזגן": "הכנת תשתיות לדוד/מזגן",
    "הכנת תשתיות לדוד או מזגן": "הכנת תשתיות לדוד/מזגן",
}
def _canon(s: str) -> str:
    s = (s or "").strip()
    return _SERVICE_CANON_MAP.get(s, s)

def _canon_list(lst):
    out = []
    for x in (lst or []):
        if isinstance(x, str) and x.strip():
            y = _canon(x)
            if y not in out:
                out.append(y)
    return out

def _canon_set(lst):
    return { _canon(x) for x in (lst or []) if isinstance(x, str) and x.strip() }

def _normalize_field(field: str) -> str:
    f = (field or "").strip()
    # חשמל – תמיד יחיד
    if f in ("חשמלאים", "חשמל", "חשמלא"):
        return "חשמלאי"
    # אינסטלציה – תמיד יחיד
    if f in ("אינסטלטורים", "אינסטלציה"):
        return "אינסטלטור"
    return f

def _fix_hebrew_common(t: str) -> str:
    if not t: return t
    t = t.replace(" ,", ",").replace("דוד או מזגן", "דוד/מזגן")
    t = t.replace("תכנן נקודות", "תכנון נקודות").replace("נבנה עבורכם", "הכנת")
    # פיסוק ומרווחים
    t = re.sub(r"\s+([,.;:])", r"\1", t)
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()

def _strip_field_parens(t: str, field_with_cert: str) -> str:
    if not t or not field_with_cert:
        return t or ""
    pat = re.compile(rf"\s*\((?:{re.escape(field_with_cert)}|{re.escape(field_with_cert.split()[0])})\)\s*")
    return pat.sub(" ", t).strip()

# --- sensitive claims filters ---
_CERT_TERMS = re.compile(r"\b(?:מוסמך(?:ים)?|מורשה(?:ים)?|רשוי(?:ים)?|תעודה\s*מקצועית)\b")
_WARRANTY_TERMS = re.compile(r"\b(?:אחריות(?:\s*מלאה)?|אחריות\s*(?:כתובה|מורחבת))\b")
_INVOICE_TERMS = re.compile(r"\b(?:חשבונית(?:\s*מס)?|קבלה|מע\"מ)\b", re.UNICODE)
_EMERGENCY_PATTERNS = [
    re.compile(r"\bחירום\s*24\s*/?\s*7\b"),
    re.compile(r"\b24\s*/?\s*7\b"),
    re.compile(r"\bזמין(?:ה)?\s+ל(?:קריאות\s+)?חירום\b"),
    re.compile(r"\bקריאות\s+חירום\b"),
]

def _filter_claims(text: str, policy: dict) -> str:
    if not text:
        return text
    t = text
    if not policy.get("licensed"):
        t = _CERT_TERMS.sub("", t)
    if (policy.get("warranty_years") or 0) <= 0:
        t = _WARRANTY_TERMS.sub("", t)
    if not policy.get("invoice_vat"):
        t = _INVOICE_TERMS.sub("", t)
    # 24/7 – לא בטקסט (ה־badge עושה את זה)
    for rx in _EMERGENCY_PATTERNS:
        t = rx.sub("", t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    t = re.sub(r"\s+([,.;:])", r"\1", t)
    return t

def _sanitize_he_with_field(t: str, field_with_cert: str, policy: dict) -> str:
    t = _strip_field_parens(t or "", field_with_cert)
    t = _strip_latin(_strip_areas(_strip_experience(t)))
    t = _fix_hebrew_common(t)
    t = _filter_claims(t, policy)
    return t

# =========================
#  Hebrew joins & helpers
# =========================
def _join_inline(items):
    items = [s for s in (items or []) if isinstance(s, str) and s.strip()]
    if not items: return ""
    if len(items) == 1: return items[0]
    if len(items) == 2: return f"{items[0]} ו{items[1]}"
    return f"{', '.join(items[:-1])} ו{items[-1]}"

def _join_commas_and_and(items):
    items = [s for s in (items or []) if isinstance(s, str) and s.strip()]
    if not items: return ""
    if len(items) == 1: return items[0]
    return ", ".join(items[:-1]) + " ו" + items[-1]

_FIELD_GENITIVE = {
    "חשמלאי": "עבודות החשמל",
    "אינסטלטור": "עבודות האינסטלציה",
}
def _field_genitive(field: str) -> str:
    f = (field or "").strip()
    return _FIELD_GENITIVE.get(f, f and f"עבודות ה{f}" or "עבודות")

def _quality_tail(seed: str, voice_tags: list) -> str:
    # אם יש תגיות קול מהתיאור – נעדיף אותן
    vl = _voice_line(voice_tags)
    if vl:
        return vl
    pool = [
        "שירות מקצועי, מהיר ואמין.",
        "עמידה בלוחות זמנים, יחס אישי וליווי צמוד.",
        "שקיפות בתמחור והתאמה לצורכי הלקוח.",
    ]
    h = hashlib.sha1(f"{seed}|quality".encode("utf-8", errors="ignore")).hexdigest()
    idx = int(h, 16) % len(pool)
    return pool[idx]

# =============== All-selection detection ===============
_ALL_RATIO = 0.98  # “כמעט הכול” נחשב כל הסעיפים

def _selected_all_services(worker: dict, field: str, selected: list) -> bool:
    sel = _canon_set(selected)
    if not sel:
        return False

    # אם הגיע קטלוג מהטופס – זה העדיף
    catalog = None
    for key in ("sub_services_catalog", "services_catalog", "all_sub_services", "services_options"):
        v = worker.get(key)
        if isinstance(v, list) and v:
            catalog = _canon_set(v)
            break

    if catalog:
        coverage = len(sel & catalog) / max(1, len(catalog))
        return coverage >= _ALL_RATIO

    # פולבאק לפי תבניות ידועות
    base = []
    if "חשמל" in field or "חשמלא" in field:
        base = _KNOWN_PATTERNS["חשמלאי"]
    elif "אינסטל" in field:
        base = _KNOWN_PATTERNS["אינסטלטור"]
    base = _canon_set(base)
    if not base:
        return False
    coverage = len(sel & base) / max(1, len(base))
    return coverage >= _ALL_RATIO

# =========================
#  CTA (ניתן לכבות ב־ENV)
# =========================
# ⚠️ הוסרו ניסוחים “סגורים” כמו “בואו נסגור את הפרטים”.
_CTA_GROUPS = [
    ["מחכים לפנייתכם.", "נשמח לסייע.", "כאן לכל שאלה.", "נשמח לדבר.", "מוזמנים ליצור קשר."],
    ["פנו אליי ונצא לדרך.", "בואו נתקדם.", "נתאם ונגיע.", "נשמח לקבוע מועד."],
    ["נשמח לתת מענה.", "נשמח להציע פתרון.", "נשמח לעזור.", "נשמח לשוחח.", "כאן בשבילכם."],
    ["כתבו לנו ונחזור.", "נחזור אליכם במהירות.", "נשמח לשמוע מכם.", "מחכים לשמוע מכם.", "נשמח ליצור קשר."],
    ["אשמח לשמוע מכם.", "נדבר ונכוון יחד.", "אשמח לסייע.", "מוזמנים לפנות אליי.", "כאן לכל דבר."],
    # פיזור
    ["מחכים לפנייתכם.", "נשמח לסייע.", "כאן לכל שאלה.", "נשמח לדבר.", "מוזמנים ליצור קשר."],
    ["פנו אליי ונצא לדרך.", "בואו נתקדם.", "נתאם ונגיע.", "נשמח לקבוע מועד."],
    ["נשמח לתת מענה.", "נשמח להציע פתרון.", "נשמח לעזור.", "נשמח לשוחח.", "כאן בשבילכם."],
]
def _cta_pick(cta_group: int, seed: str, offset: int = 0) -> str:
    if str(os.environ.get("AI_CARD_CTA","on")).lower() in ("off","0","no","false"):
        return ""  # אפשר לכבות CTA לגמרי דרך ENV
    group = _CTA_GROUPS[cta_group % len(_CTA_GROUPS)]
    h = hashlib.sha1(f"{seed}|cta".encode("utf-8", errors="ignore")).hexdigest()
    idx = (int(h, 16) + int(offset)) % len(group)
    return group[idx]

# =========================
#  Headings & styles (בלי מקצוע)
# =========================
def _display_heading(worker) -> tuple[str,bool]:
    """
    מחזיר (heading, has_company):
    - אם יש חברה: '{חברה} בהנהלת {שם}'
    - אם אין חברה: שם פרטי בלבד
    """
    name = _get_str(worker, "name")
    comp = _get_str(worker, "company_name")
    has_comp = bool(comp and comp != name)
    if has_comp:
        return f"{comp} בהנהלת {name}", True
    return _first_name(name), False

def _card_opening_style(worker, field: str, sub_services: list, style_idx: int, seed: str, voice_tags: list, is_all: bool) -> str:
    heading, has_comp = _display_heading(worker)
    sv_inline = _join_inline(sub_services) if sub_services else ""
    sv_commas = _join_commas_and_and(sub_services) if sub_services else ""
    give_service  = "נותנים שירות" if has_comp else "נותן שירות"
    handle_verb   = "מטפלים" if has_comp else "מטפל"
    gen = _field_genitive(field)

    # 0) קלאסי טבעי
    if style_idx % 5 == 0:
        if is_all and sv_commas:
            return f"{heading} מתמחה בכל {gen}: {sv_commas}."
        if sv_inline:
            return f"{heading} מתמחה ב{sv_inline}."
        return f"{heading} מתמחה ב{gen}."

    # 1) “כל סוגי …: …”
    if style_idx % 5 == 1:
        if is_all and sv_commas:
            return f"{heading} מתמחה בכל סוגי {gen}: {sv_commas}."
        if sv_commas:
            return f"{heading} מתמחה במגוון {gen}: {sv_commas}."
        return f"{heading} מתמחה במגוון {gen}."

    # 2) שירות תיקונים + זנב איכות מהתיאור
    if style_idx % 5 == 2:
        tail = _quality_tail(seed, voice_tags)
        if sv_commas:
            return f"{heading} {give_service} תיקונים מהיר, {sv_commas}. {tail}"
        return f"{heading} {give_service} תיקונים מהיר. {tail}"

    # 3) “מטפל/ים ב…”
    if style_idx % 5 == 3:
        if sv_inline:
            return f"{heading} {handle_verb} ב{sv_inline}."
        return f"{heading} {handle_verb} ב{gen}."

    # 4) “אצל … תקבלו מענה ל…”
    if sv_inline:
        return f"אצל {heading} תקבלו מענה ל{sv_inline}."
    return f"אצל {heading} תקבלו מענה ל{gen}."

def _full_intro(worker):
    # בפרופיל מלא נשאיר אותו סופר-נייטרלי – בלי מקצוע
    name  = _get_str(worker, "name")
    comp  = _get_str(worker, "company_name")
    if comp and comp != name:
        return f"{comp} בהנהלת {name}"
    return f"{name}".strip()

def _fix_kmo_khen_with_name(text: str, name: str) -> str:
    if not text or not name: return text
    first = name.strip().split()[0]
    text = re.sub(rf"{re.escape(name)}\s*,?\s*כמו כן", f"כמו כן, {first}", text)
    text = re.sub(rf"כמו כן\s+{re.escape(name)}", f"כמו כן, {first}", text)
    return re.sub(r"\s{2,}", " ", text).strip()

def _build_full_paragraph_style(worker, field: str, sub_services: list, voice_tags: list, seed: str, style_idx: int, is_all: bool) -> str:
    sv = _canon_list(sub_services)
    display = _full_intro(worker)

    def segs(parts_style=0):
        a, b, c = sv[:2], sv[2:5], sv[5:]
        lines = []
        gen = _field_genitive(field)

        if is_all and sv:
            lines.append(f"{display} מתמחה בכל {gen}: { _join_inline(sv) }.")
        else:
            if a: lines.append(f"{display} מתמחה ב{_join_inline(a)}.")
            if b: lines.append(f"בנוסף מטפל ב{_join_inline(b)}.")
            if c: lines.append(f"כמו כן זמין ל{_join_inline(c)}.")

        # זנב איכות שנשאב מהתיאור כשיש
        q = _quality_tail(seed, voice_tags)
        if q:
            lines.append(q)

        return " ".join([x for x in lines if x]).strip()

    core = segs(parts_style=style_idx % 4)
    core = _fix_kmo_khen_with_name(core, _get_str(worker, "name"))
    return core

# =========================
#  Main
# =========================
def generate_draft(worker: dict, lang: str = "he") -> dict:
    """
    מחזיר:
      ai_draft_bio_short, ai_draft_bio_full, ai_draft_services_sentence, ai_draft_services,
      ai_draft_seo_title, ai_draft_bio, ai_style, ai_status, ועוד מטא וריאנטים.

    קווים מנחים:
    - לעולם לא מוסיפים “חשמלאי/אינסטלטור/…” בטקסט (כרטיס/פרופיל).
    - אם כל תתי-התחומים מסומנים: “מתמחה בכל עבודות ה…: …”.
    - אין 24/7/מוסמך/חשבונית/אחריות בלי דגלים. תגיות קול (“עמידה בזמנים”, “שקיפות”) כן נשאבות מהתיאור.
    """
    try:
        # בסיס
        raw_field = _get_str(worker, "field")
        field = _normalize_field(raw_field)
        source_bio = _extract_source_bio(worker)
        policy = _build_policy(worker)
        cert = _cert_suffix(policy)  # לא מציגים בטקסט; רק לצורך סניטיזציה פנימית
        field_with_cert = (f"{field} {cert}".strip() if cert else field) or field

        # שירותים
        sub_services = _canon_list([s for s in (worker.get("sub_services") or []) if isinstance(s, str) and s.strip()])
        if not sub_services:
            sub_services = _infer_services_from_bio(field or "", source_bio)

        # האם נבחרו הכול
        is_all = _selected_all_services(worker, field or "", sub_services)

        # קול
        voice_tags = _derive_voice_tags(source_bio)
        style_name = _style_for_worker(worker)["name"]

        # וריאנט
        seed = _variant_seed(worker)
        cursor = worker.get("ai_variant_cursor", worker.get("variant_refresh", 0))
        try: cursor = int(cursor or 0)
        except Exception: cursor = 0

        field_key = field  # כל תחום
        pick = {}
        try:
            pick = pick_next_variant(field_key=field_key, seed=seed, cursor=cursor, skip_in_use=bool(worker.get("skip_in_use_variants", True)))
        except Exception:
            pick = {"error": "no-registry"}

        if pick.get("error"):
            variant = {"id": "default", "card_style": 0, "full_style": 0, "cta_group": 0}
            in_use_by = None
            exhausted = True
        else:
            v = pick["variant"]
            variant = {"id": v["id"], "card_style": int(v["card_style"]), "full_style": int(v["full_style"]), "cta_group": int(v["cta_group"]) }
            in_use_by = pick.get("in_use_by")
            exhausted = bool(pick.get("exhausted"))

        # כרטיס (תיאור קצר) – בלי מקצוע
        opening = _card_opening_style(worker, field, sub_services, variant["card_style"], seed, voice_tags, is_all)
        cta = _cta_pick(variant["cta_group"], seed, offset=cursor)
        parts = [opening]
        qtail = _quality_tail(seed, voice_tags)
        if qtail:
            parts.append(qtail)
        if cta:
            parts.append(cta)
        bio_short = " ".join([p for p in parts if p]).strip()
        if not bio_short.endswith("."):
            bio_short += "."
        bio_short = _sanitize_he_with_field(bio_short, field_with_cert, policy)

        # פרופיל מלא – בלי מקצוע
        bio_full = _build_full_paragraph_style(worker, field, sub_services, voice_tags, seed, variant["full_style"], is_all)
        bio_full = _sanitize_he_with_field(bio_full, field_with_cert, policy)

        # SEO – בלי מקצוע: שם חברה/שם פרטי + 1-2 שירותים מובילים
        name  = _get_str(worker, "name")
        comp  = _get_str(worker, "company_name")
        has_comp = bool(comp and comp != name)
        top2 = ", ".join(_canon_list(sub_services)[:2]) if sub_services else ""
        if has_comp:
            seo_raw = f"{comp} | {top2}" if top2 else comp
        else:
            first = _first_name(name)
            seo_raw = f"{first} | {top2}" if top2 and first else (first or top2 or "שירות מקצועי")
        seo_title = _sanitize_he_with_field((seo_raw or "").strip(" |"), field_with_cert, policy)

        services_sentence = ", ".join(_canon_list(sub_services))
        highlights = ["תיאום מהיר ושקוף", "התאמה לצורכי הלקוח", "עבודה מוקפדת"]

        if not bio_short:
            raise ValueError("empty bio_short")

        return {
            "ai_draft_bio_short": bio_short,
            "ai_draft_bio_full": bio_full or bio_short,
            "ai_draft_bio": bio_short,
            "ai_draft_highlights": highlights,
            "ai_draft_seo_title": seo_title,
            "ai_draft_services_sentence": services_sentence,
            "ai_draft_services": _canon_list(sub_services),
            "ai_style": style_name,

            "ai_variant_used": variant["id"],
            "ai_variant_card_style": variant["card_style"],
            "ai_variant_full_style": variant["full_style"],
            "ai_variant_cta_group": variant["cta_group"],
            "ai_variant_in_use_by": in_use_by,
            "ai_variants_exhausted": exhausted,
            "ai_variant_cursor_next": int(cursor) + 1,

            "ai_status": "ready",
            "ai_updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "ai_model": "deterministic-variants+policy+voiceecho",
        }

    except Exception as e:
        return {
            "ai_status": "error",
            "ai_error": str(e)[:200],
            "ai_updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }
