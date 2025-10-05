# services/ai_variants.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
import hashlib, time, threading

# =========================
# מודל נתונים לוריאנט
# =========================
@dataclass(frozen=True)
class Variant:
    id: str                  # מזהה ייחודי (למשל "elc_v1")
    label: str               # שם אנושי קצר (להצגה ברשימות)
    field_key: str           # תחום קנוני: "חשמלאי", "אינסטלטור" וכו'
    card_style: int          # מזהה סגנון פתיח לכרטיס (0..N-1)
    full_style: int          # מזהה סגנון פסקה מלאה (0..M-1)
    cta_group: int           # בנק CTA (לגיוון קטן)
    notes: str = ""          # הערת הסבר/כוונה (למנהלי מערכת)

@dataclass
class VariantUsage:
    field_key: str
    variant_id: str
    worker_id: str
    assigned_at: float
    status: str = "assigned"   # assigned | released

# =========================
# קנוניזציה של תחומים (יחיד/רבים/כינויים)
# =========================
_GENERIC_KEY = "__generic__"

_FIELD_ALIASES = {
    # חשמל
    "חשמלאי": "חשמלאי",
    "חשמלאים": "חשמלאי",
    "חשמל": "חשמלאי",

    # אינסטלציה
    "אינסטלטור": "אינסטלטור",
    "אינסטלטורים": "אינסטלטור",
    "אינסטלציה": "אינסטלטור",

    # דוגמאות להרחבה (תוכל להוסיף בהמשך לפי צורך):
    "מנעולן": "מנעולן",
    "מנעולנים": "מנעולן",
    "שיפוצניק": "שיפוצניק",
    "שיפוצים": "שיפוצניק",
    "צבאי": "צבעי",
    "צבע": "צבעי",
    "צבעים": "צבעי",
    "נגר": "נגר",
    "נגרים": "נגר",
    "מדביר": "מדביר",
    "הדברה": "מדביר",
    "גנן": "גנן",
    "גינון": "גנן",
    "מיזוג אוויר": "טכנאי מזגנים",
    "טכנאי מזגנים": "טכנאי מזגנים",
}

def _canon_field_key(s: str) -> str:
    s = (s or "").strip()
    return _FIELD_ALIASES.get(s, s)

# =========================
# מאגר וריאנטים: הגדרה סטטית (קל להרחיב)
# =========================
_VARIANTS: List[Variant] = [
    # ---------- חשמלאי ----------
    Variant("elc_v1",  "פתיח קלאסי, חיבורים 'בנוסף/כמו כן'", "חשמלאי", 0, 0, 0),
    Variant("elc_v2",  "פתיח 'מספק מענה', חיבורים 'נוסף על כך/וכן'", "חשמלאי", 1, 1, 1),
    Variant("elc_v3",  "פתיח 'מטפל ב', חיבורים 'ועוד/ובנוסף'",       "חשמלאי", 2, 2, 2),
    Variant("elc_v4",  "פתיח 'נותן שירות', חיבורים 'בין היתר/ניתן'", "חשמלאי", 3, 3, 3),
    Variant("elc_v5",  "פתיח 'אצל {שם} תקבלו', קצב זריז",             "חשמלאי", 4, 0, 4),
    Variant("elc_v6",  "פתיח קלאסי, ניסוח יותר ענייני",               "חשמלאי", 0, 1, 5),
    Variant("elc_v7",  "פתיח 'מספק מענה', טון חם",                    "חשמלאי", 1, 2, 6),
    Variant("elc_v8",  "פתיח 'מטפל ב', טון טכני נקי",                 "חשמלאי", 2, 3, 7),

    # ---------- אינסטלטור ----------
    Variant("plm_v1",  "פתיח קלאסי, 'בנוסף/כמו כן'", "אינסטלטור", 0, 0, 0),
    Variant("plm_v2",  "'מספק מענה', 'נוסף על כך/וכן'", "אינסטלטור", 1, 1, 1),
    Variant("plm_v3",  "'מטפל ב', 'ועוד/ובנוסף'",        "אינסטלטור", 2, 2, 2),
    Variant("plm_v4",  "'נותן שירות', 'בין היתר/ניתן'",  "אינסטלטור", 3, 3, 3),
    Variant("plm_v5",  "'אצל {שם} תקבלו', קצב זריז",     "אינסטלטור", 4, 0, 4),
    Variant("plm_v6",  "קלאסי ענייני",                   "אינסטלטור", 0, 1, 5),

    # ---------- מנעולן ----------
    Variant("lck_v1",  "פתיח מדגיש זמינות",               "מנעולן", 2, 2, 2),
    Variant("lck_v2",  "קלאסי עם דגש על אבטחה",           "מנעולן", 0, 1, 5),
    Variant("lck_v3",  "'אצל {שם} תקבלו', טון אישי",      "מנעולן", 4, 0, 6),

    # ---------- מדביר ----------
    Variant("pst_v1",  "פתיח מקיף לכל סוגי ההדברה",      "מדביר", 1, 1, 1),
    Variant("pst_v2",  "טון טכני ונקי",                   "מדביר", 2, 3, 7),
    Variant("pst_v3",  "מסר חם עם הדגשת שקיפות",          "מדביר", 0, 0, 0),

    # ---------- נגר ----------
    Variant("crp_v1",  "דגש על עבודות בהתאמה אישית",      "נגר", 3, 3, 3),
    Variant("crp_v2",  "פתיח חם ומזמין",                  "נגר", 1, 2, 6),
    Variant("crp_v3",  "טון טכני-מדויק",                  "נגר", 2, 1, 4),

    # ---------- שיפוצניק ----------
    Variant("rnv_v1",  "תכל'ס עם רשימת שירותים",         "שיפוצניק", 0, 0, 5),
    Variant("rnv_v2",  "'מטפל ב', טון חם",                "שיפוצניק", 2, 2, 6),
    Variant("rnv_v3",  "'אצל {שם} תקבלו', טון זמין",      "שיפוצניק", 4, 1, 7),

    # ---------- טכנאי מזגנים ----------
    Variant("ac_v1",   "פתיח טכני נקי",                   "טכנאי מזגנים", 2, 3, 7),
    Variant("ac_v2",   "טון חם ושירותי",                   "טכנאי מזגנים", 1, 2, 6),
    Variant("ac_v3",   "קלאסי עם הדגשת זמינות",          "טכנאי מזגנים", 0, 1, 4),

    # ---------- כלליים (GENERIC) ----------
    # בנויים כך שיתאימו *לכל* תחום – בלי רמיזות ספציפיות.
    Variant("gen_v1", "כללי: פתיח קלאסי",                  _GENERIC_KEY, 0, 0, 0, "פתיח ניטרלי, חיבורים 'בנוסף/כמו כן'"),
    Variant("gen_v2", "כללי: מספק מענה",                   _GENERIC_KEY, 1, 1, 1, "מספק מענה / נוסף על כך"),
    Variant("gen_v3", "כללי: מטפל ב",                      _GENERIC_KEY, 2, 2, 2, "מטפל ב / ועוד / ובנוסף"),
    Variant("gen_v4", "כללי: נותן שירות",                  _GENERIC_KEY, 3, 3, 3, "נותן שירות / בין היתר / ניתן"),
    Variant("gen_v5", "כללי: אצל {שם} תקבלו",              _GENERIC_KEY, 4, 0, 4, "זריז ואישי"),
    Variant("gen_v6", "כללי: קלאסי ענייני",                _GENERIC_KEY, 0, 1, 5, "נוסח תמציתי ומדויק"),
    Variant("gen_v7", "כללי: מספק מענה, טון חם",           _GENERIC_KEY, 1, 2, 6, "טון חם ושירותי"),
    Variant("gen_v8", "כללי: מטפל ב, טון טכני נקי",        _GENERIC_KEY, 2, 3, 7, "טון טכני-נקי, ברור"),
]

# אינדקס לפי תחום (בקנוניזציה)
_VARIANTS_BY_FIELD: Dict[str, List[Variant]] = {}
for v in _VARIANTS:
    key = _canon_field_key(v.field_key)
    _VARIANTS_BY_FIELD.setdefault(key, []).append(v)

# =========================
# שכבת אחסון – InMemory (עם נעילה קטנה)
# =========================
class VariantStore:
    def list_assigned(self, field_key: str) -> List[VariantUsage]:
        raise NotImplementedError
    def assign(self, field_key: str, variant_id: str, worker_id: str) -> bool:
        raise NotImplementedError
    def release(self, field_key: str, worker_id: str) -> None:
        raise NotImplementedError
    def in_use_by(self, field_key: str, variant_id: str) -> Optional[str]:
        raise NotImplementedError

class InMemoryVariantStore(VariantStore):
    def __init__(self):
        self._assigned: Dict[Tuple[str,str], VariantUsage] = {}
        self._by_worker: Dict[str, Tuple[str,str]] = {}
        self._lock = threading.Lock()

    def list_assigned(self, field_key: str) -> List[VariantUsage]:
        fk = _canon_field_key(field_key)
        with self._lock:
            return [
                u for (k_field, k_var), u in self._assigned.items()
                if k_field == fk and u.status == "assigned"
            ]

    def assign(self, field_key: str, variant_id: str, worker_id: str) -> bool:
        fk = _canon_field_key(field_key)
        with self._lock:
            # שחרור קודם אם לעובד הזה כבר שמור משהו
            prev = self._by_worker.get(worker_id)
            if prev:
                key_prev = (prev[0], prev[1])
                if key_prev in self._assigned:
                    self._assigned[key_prev].status = "released"
                    del self._assigned[key_prev]
                del self._by_worker[worker_id]

            key = (fk, variant_id)
            if key in self._assigned:
                return False  # כבר תפוס
            usage = VariantUsage(field_key=fk, variant_id=variant_id, worker_id=worker_id, assigned_at=time.time())
            self._assigned[key] = usage
            self._by_worker[worker_id] = (fk, variant_id)
            return True

    def release(self, field_key: str, worker_id: str) -> None:
        fk = _canon_field_key(field_key)
        with self._lock:
            prev = self._by_worker.get(worker_id)
            if not prev:
                return
            if prev[0] == fk:
                key = (prev[0], prev[1])
                if key in self._assigned:
                    self._assigned[key].status = "released"
                    del self._assigned[key]
                del self._by_worker[worker_id]

    def in_use_by(self, field_key: str, variant_id: str) -> Optional[str]:
        fk = _canon_field_key(field_key)
        with self._lock:
            u = self._assigned.get((fk, variant_id))
            return u.worker_id if u and u.status == "assigned" else None

# מופע ברירת מחדל (אם אין DB עדיין)
_DEFAULT_STORE = InMemoryVariantStore()

# =========================
# API חיצוני לשימוש מהשירות/בקר
# =========================
def list_fields() -> List[str]:
    """רשימת תחומים שיש להם וריאנטים רשומים (כולל הכללי)."""
    return sorted(_VARIANTS_BY_FIELD.keys())

def variants_count(field_key: str) -> int:
    fk = _canon_field_key(field_key)
    v = _VARIANTS_BY_FIELD.get(fk)
    if not v:
        v = _VARIANTS_BY_FIELD.get(_GENERIC_KEY, [])
    return len(v)

def list_variants(field_key: str, store: VariantStore = _DEFAULT_STORE) -> List[dict]:
    fk = _canon_field_key(field_key)
    variants = _VARIANTS_BY_FIELD.get(fk)
    if not variants:
        variants = _VARIANTS_BY_FIELD.get(_GENERIC_KEY, [])
    out = []
    for v in variants:
        used_by = store.in_use_by(fk, v.id)
        out.append({
            "id": v.id,
            "label": v.label,
            "card_style": v.card_style,
            "full_style": v.full_style,
            "cta_group": v.cta_group,
            "in_use_by": used_by,  # None או worker_id
        })
    return out

def pick_next_variant(field_key: str, seed: str, cursor: int = 0, skip_in_use: bool = True, store: VariantStore = _DEFAULT_STORE) -> dict:
    """
    בוחר וריאנט דטרמיניסטית (seed+cursor) מתוך התחום המבוקש.
    אם אין לתחום וריאנטים – נופל אוטומטית למשפחת __generic__.
    """
    fk = _canon_field_key(field_key)
    variants = _VARIANTS_BY_FIELD.get(fk)
    if not variants:
        fk = _GENERIC_KEY
        variants = _VARIANTS_BY_FIELD.get(_GENERIC_KEY, [])
    if not variants:
        return {"error": "No variants available at all"}

    # אינדקס התחלתי דטרמיניסטי: seed → 0..N-1
    h = hashlib.sha1(str(seed).encode("utf-8", errors="ignore")).hexdigest()
    start = (int(h, 16) + int(cursor or 0)) % len(variants)

    tried = 0
    idx = start
    skipped = 0
    while tried < len(variants):
        v = variants[idx]
        used_by = store.in_use_by(fk, v.id)
        if not (skip_in_use and used_by):
            return {"variant": asdict(v), "exhausted": False, "skipped_count": skipped, "in_use_by": used_by}
        skipped += 1
        tried += 1
        idx = (idx + 1) % len(variants)

    # כולם בשימוש – נחזיר את הראשון (עם דגל exhausted)
    v = variants[start]
    return {"variant": asdict(v), "exhausted": True, "skipped_count": skipped, "in_use_by": store.in_use_by(fk, v.id)}

def assign_variant(field_key: str, variant_id: str, worker_id: str, store: VariantStore = _DEFAULT_STORE) -> dict:
    fk = _canon_field_key(field_key)
    ok = store.assign(fk, variant_id, worker_id)
    return {"ok": ok, "in_use_by": None if ok else store.in_use_by(fk, variant_id)}

def release_variant(field_key: str, worker_id: str, store: VariantStore = _DEFAULT_STORE) -> None:
    fk = _canon_field_key(field_key)
    store.release(fk, worker_id)
