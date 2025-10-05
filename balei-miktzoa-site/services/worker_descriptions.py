# -*- coding: utf-8 -*-
"""
Worker descriptions (adapter) – Hebrew, prompt-based.

מטרה:
- להשתמש ב- ai_writer.generate_draft (הגרסה הישנה המבוססת פרומפטים)
- להחזיר אובייקט במבנה "שלושה טונים" כדי לא לשנות את ה-UI/תבניות:
  {
    "neutral_professional": {"teaser": "...", "body": "...", "source": "prompt"},
    "service_human":        {"teaser": "...", "body": "...", "source": "prompt"},
    "urgent_trust":         {"teaser": "...", "body": "...", "source": "prompt"},
    "used_fields": {...}
  }

אין תלות ב-ollama / ai_writer_advanced.
"""

from __future__ import annotations
import hashlib
import json
import logging
import re
import time
from typing import Any, Dict, Mapping, MutableMapping, Tuple

from .ai_writer import generate_draft  # ← הפרומפטים הישנים

LOGGER = logging.getLogger(__name__)

# -------------------------
# Cache
# -------------------------
_CACHE: MutableMapping[str, Tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL_SECONDS = 15 * 60
_CACHE_MAX = 128


def _fingerprint(worker: Mapping[str, Any]) -> str:
    relevant_keys = [
        "worker_id", "id", "updated_at", "ai_updated_at",
        "name", "company_name", "field", "field_display",
        "city", "base_city", "sub_services", "services_list",
        "about_clean", "about", "description", "bio", "bio_short",
    ]
    payload = {k: worker.get(k) for k in relevant_keys if k in worker}
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha1(serialized.encode("utf-8")).hexdigest()


def _used_fields(worker: Mapping[str, Any], draft: Mapping[str, Any]) -> Dict[str, Any]:
    # תצוגת מטא נוחה למודאל/דבאג
    return {
        "display_name": worker.get("company_name") or worker.get("business_name") or worker.get("name") or "בעל מקצוע",
        "person_name": worker.get("name") or "",
        "field_label": worker.get("field_display") or worker.get("title") or worker.get("field") or "",
        "city": worker.get("city") or worker.get("base_city") or worker.get("area") or "",
        "sub_services": worker.get("sub_services") or worker.get("services_list") or [],
        "highlights": draft.get("ai_draft_highlights") or [],
        "policy_flags": {
            "licensed": bool(worker.get("is_licensed") or worker.get("certified")),
            "insured": bool(worker.get("insured")),
            "invoice": bool(worker.get("invoice_vat") or worker.get("issue_invoice")),
            "emergency": bool(worker.get("offers_emergency")),
        },
        "source_bio": worker.get("original_bio") or worker.get("about_clean") or worker.get("about") or worker.get("description") or worker.get("bio") or "",
    }

_TEASER_TARGET_MAX = 220

_TONE_LAYERS = {
    "neutral_professional": {
        "teaser_extra": "תכנון מוקפד וביצוע מקצועי.",
        "open": "התמונה המלאה:",
        "mid": "מתאמים הכל בשקיפות מלאה לאורך הפרויקט.",
        "cta": "צרו קשר ונגבש פתרון מדויק."},
    "service_human": {
        "teaser_extra": "יחס אישי וחיוך בכל פנייה.",
        "open": "איך אנחנו מלווים אתכם:",
        "mid": "שומרים על עדכונים רציפים וקשב מלא לצרכים שלכם.",
        "cta": "בואו נדבר ונבנה יחד מענה שמתאים לכם."},
    "urgent_trust": {
        "teaser_extra": "זמינות גבוהה לקריאות דחופות.",
        "open": "כדי לפתור את התקלה במהירות:",
        "mid": "זמינים לשאלות ולעדכונים בזמן אמת עד לסיום.",
        "cta": "הרימו טלפון ונגיע במהירות."},
}


def _trim_teaser(text: str, limit: int = _TEASER_TARGET_MAX) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    if len(text) <= limit:
        return text
    trimmed = text[: limit - 1].rstrip()
    trimmed = re.sub(r"[\s,;:.]+$", "", trimmed)
    return f"{trimmed}…"


def _compose_body(base_body: str, layer: Dict[str, str]) -> str:
    base_body = (base_body or "").strip()
    segments = []
    open_phrase = layer.get("open")
    if open_phrase:
        segments.append(open_phrase.rstrip())
    if base_body:
        segments.append(base_body)
    mid_phrase = layer.get("mid")
    if mid_phrase:
        mid_phrase = mid_phrase.rstrip(" ")
        if not mid_phrase.endswith(('.', '!', '?')):
            mid_phrase += "."
        segments.append(mid_phrase)
    cta = layer.get("cta")
    if cta:
        cta = cta.rstrip(" ")
        if not cta.endswith(('.', '!', '?')):
            cta += "."
        segments.append(cta)
    text = " ".join(seg for seg in segments if seg).strip()
    return text


def _tone_teaser(base_teaser: str, layer: Dict[str, str]) -> str:
    base_teaser = (base_teaser or "").strip()
    extra = layer.get("teaser_extra")
    text = f"{base_teaser} {extra}".strip() if extra else base_teaser
    return _trim_teaser(text)



def _adapt_to_three_styles(draft: Mapping[str, Any]) -> Dict[str, Any]:
    """
    ממפה את הפלט של ai_writer (bio_short/full) לשלושת הטונים עם התאמות ניסוח עדינות.

    """
    teaser = (draft.get("ai_draft_bio_short") or "").strip()
    body = (draft.get("ai_draft_bio_full") or teaser).strip()
    out: Dict[str, Any] = {}
    for tone, layer in _TONE_LAYERS.items():
        tone_teaser = _tone_teaser(teaser, layer)
        tone_body = _compose_body(body, layer)
        out[tone] = {"teaser": tone_teaser, "body": tone_body, "source": "prompt"}
    return out


def generate_worker_descriptions(worker: Mapping[str, Any]) -> Dict[str, Any]:
    """
    ה-API הציבורי: מחזיר שלושה סגנונות (אותו טקסט בכל אחד בשלב זה) + used_fields.
    """
    try:
        draft = generate_draft(dict(worker))  # מהפרומפטים הישנים
        if draft.get("ai_status") != "ready":
            raise RuntimeError(draft.get("ai_error") or "ai_writer returned error")

        styles = _adapt_to_three_styles(draft)
        styles["used_fields"] = _used_fields(worker, draft)
        # למי שצריך מטא (לא חובה): אפשר לצרף גם כזו, רק לא לשבור מבנים קיימים
        styles["_meta"] = {
            "ai_model": draft.get("ai_model"),
            "ai_variant_used": draft.get("ai_variant_used"),
            "ai_variant_card_style": draft.get("ai_variant_card_style"),
            "ai_variant_full_style": draft.get("ai_variant_full_style"),
            "ai_variant_cta_group": draft.get("ai_variant_cta_group"),
            "ai_variant_cursor_next": draft.get("ai_variant_cursor_next"),
            "ai_updated_at": draft.get("ai_updated_at"),
        }
        return styles

    except Exception as exc:
        LOGGER.error("generate_worker_descriptions adapter failed: %s", exc)
        # פולבאק מינימלי שלא מפיל את הפרונט
        display = worker.get("company_name") or worker.get("business_name") or worker.get("name") or "בעל מקצוע"
        teaser = f"{display} — שירות מקצועי ואדיב."
        body = f"{display} מעניק/ה שירות מוקפד ואמין. מוזמנים ליצור קשר."
        return {
            "neutral_professional": {"teaser": teaser, "body": body, "source": "fallback"},
            "service_human":        {"teaser": teaser, "body": body, "source": "fallback"},
            "urgent_trust":         {"teaser": teaser, "body": body, "source": "fallback"},
            "used_fields": _used_fields(worker, {}),
            "_meta": {"error": str(exc)},
        }


def describe_worker(worker: Mapping[str, Any]) -> Dict[str, Any]:
    """
    עטיפת cache דקה סביב generate_worker_descriptions, כמו קודם.
    """
    key = _fingerprint(worker)
    now = time.time()
    cached = _CACHE.get(key)
    if cached and (now - cached[0]) < _CACHE_TTL_SECONDS:
        return cached[1]
    data = generate_worker_descriptions(worker)
    _CACHE[key] = (now, data)
    # ניקוי LRU פשוט
    if len(_CACHE) > _CACHE_MAX:
        oldest_key = min(_CACHE.items(), key=lambda item: item[1][0])[0]
        _CACHE.pop(oldest_key, None)
    return data


__all__ = ["generate_worker_descriptions", "describe_worker"]
