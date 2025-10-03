"""Helper utilities for generating multi-tone worker descriptions.

The module exposes two public helpers:

* :func:`generate_worker_descriptions` – builds a payload for the LLM (when
  available) and returns three tone variants plus metadata about the fields
  that were actually used.
* :func:`describe_worker` – lightweight caching wrapper that templates can
  call to obtain ready-to-render copy with safe fallbacks when the model is
  offline.

All Hebrew text is produced with explicit safeguards – no certifications or
service promises are invented unless the worker data contains explicit flags.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Tuple

try:  # מודול ה-LLM אופציונלי בסביבת הפיתוח
    from . import ollama_client
except Exception:  # pragma: no cover - בעת בדיקות ללא המודול
    ollama_client = None  # type: ignore


LOGGER = logging.getLogger(__name__)

# גבולות המילים לכל סגנון – מאפשרים שליטה גם בפרומפט וגם בפולבאק.
MAX_TEASER_WORDS = 28
MAX_BODY_WORDS = 85

# אורך מקסימלי שנשתמש בו להצגת תתי-שירותים בפרומפט (לאחר דחיסה).
MAX_SUB_SERVICE_CHARS = 260

# מזהה לטון → מפתח במילון שיוחזר ללקוח.
STYLE_KEYS = {
    "neutral_professional": "ניטרלי-מקצועי",
    "service_human": "שירותי-אנושי",
    "urgent_trust": "דחוף/אמינות",
}


@dataclass
class WorkerContext:
    """Normalized worker payload that feeds the prompt/fallback."""

    display_name: str
    person_name: str
    field_label: str
    city: str
    years: str
    experience_text: str
    rating: str
    reviews_count: str
    languages: List[str]
    sub_services: List[str]
    sub_services_compact: str
    highlights: List[str]
    availability: str
    policy_flags: Dict[str, Any]
    source_bio: str
    used_fields: Dict[str, Any]


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _first(items: Iterable[str]) -> str:
    for item in items:
        item = _safe_str(item)
        if item:
            return item
    return ""


def _canonical_list(values: Iterable[Any]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for raw in values:
        value = re.sub(r"\s+", " ", _safe_str(raw))
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _compress_sub_services(sub_services: List[str]) -> Tuple[List[str], str]:
    """Compresses the list of sub services so it fits into the prompt budget."""

    cleaned = _canonical_list(sub_services)
    if not cleaned:
        return [], ""

    joined = ", ".join(cleaned)
    if len(joined) <= MAX_SUB_SERVICE_CHARS:
        return cleaned, joined

    budget = MAX_SUB_SERVICE_CHARS
    accumulator: List[str] = []
    total = 0
    for item in cleaned:
        item_len = len(item)
        projected = total + (2 if accumulator else 0) + item_len
        if projected > budget:
            break
        accumulator.append(item)
        total = projected

    remainder = len(cleaned) - len(accumulator)
    if remainder > 0:
        plural = "שירותים" if remainder > 1 else "שירות"
        accumulator.append(f"ועוד {remainder} {plural}")

    return cleaned, ", ".join(accumulator)


def _word_trim(text: str, limit: int) -> str:
    words = re.findall(r"\S+", text)
    if len(words) <= limit:
        return text.strip()
    trimmed = " ".join(words[:limit]).rstrip(".,;: ")
    return trimmed + "…"


def _policy_flags(worker: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "licensed": bool(worker.get("is_licensed") or worker.get("certified")),
        "insured": bool(worker.get("insured")),
        "invoice": bool(worker.get("invoice_vat") or worker.get("issue_invoice")),
        "emergency": bool(worker.get("offers_emergency")),
    }


def _availability(worker: Mapping[str, Any]) -> str:
    cta = worker.get("call_to_action") or {}
    status = _safe_str(cta.get("status"))
    if status == "open":
        return "זמין כעת"
    if status == "closed":
        subline = _safe_str(cta.get("subline"))
        return subline or "לא זמין"
    return _safe_str(cta.get("subline"))


def _collect_context(worker: Mapping[str, Any]) -> WorkerContext:
    display_name = _first([
        worker.get("company_name"),
        worker.get("business_name"),
        worker.get("name"),
    ]) or "בעל מקצוע"

    person_name = _safe_str(worker.get("name"))
    field_label = _first([
        worker.get("field_display"),
        worker.get("title"),
        worker.get("field"),
    ])
    city = _first([worker.get("city"), worker.get("base_city"), worker.get("area")])

    years_raw = worker.get("years") or worker.get("experience_years")
    years = ""
    try:
        if years_raw is not None:
            yrs = int(str(years_raw).strip())
            if yrs > 0:
                years = f"{yrs} שנות ניסיון"
    except Exception:
        years = ""

    experience_text = _safe_str(worker.get("experience_text"))

    rating = ""
    if worker.get("rating"):
        try:
            rating = f"{float(worker['rating']):.1f}/5"
        except Exception:
            rating = _safe_str(worker.get("rating"))

    reviews_count = ""
    if worker.get("reviews_count"):
        reviews_count = str(worker.get("reviews_count"))

    languages = _canonical_list(worker.get("languages") or [])

    cleaned_sub_services, compact = _compress_sub_services(
        worker.get("services_list") or worker.get("sub_services") or []
    )

    highlights = _canonical_list(worker.get("highlights") or [])
    availability = _availability(worker)
    policy = _policy_flags(worker)
    source_bio = _first([
        worker.get("about_clean"),
        worker.get("about"),
        worker.get("description"),
        worker.get("bio"),
    ])

    used_fields = {
        "display_name": display_name,
        "person_name": person_name,
        "field_label": field_label,
        "city": city,
        "years": years,
        "experience_text": experience_text,
        "rating": rating,
        "reviews_count": reviews_count,
        "languages": languages,
        "sub_services": cleaned_sub_services,
        "sub_services_compact": compact,
        "highlights": highlights,
        "availability": availability,
        "policy_flags": policy,
        "source_bio": source_bio,
    }

    return WorkerContext(
        display_name=display_name,
        person_name=person_name,
        field_label=field_label,
        city=city,
        years=years,
        experience_text=experience_text,
        rating=rating,
        reviews_count=reviews_count,
        languages=languages,
        sub_services=cleaned_sub_services,
        sub_services_compact=compact,
        highlights=highlights,
        availability=availability,
        policy_flags=policy,
        source_bio=source_bio,
        used_fields=used_fields,
    )


def _build_prompt_payload(ctx: WorkerContext) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "display_name": ctx.display_name,
        "person_name": ctx.person_name,
        "field_label": ctx.field_label,
        "city": ctx.city,
        "years": ctx.years,
        "experience_text": ctx.experience_text,
        "rating": ctx.rating,
        "reviews_count": ctx.reviews_count,
        "languages": ctx.languages,
        "sub_services": ctx.sub_services_compact,
        "availability": ctx.availability,
        "highlights": ctx.highlights,
        "policy_flags": ctx.policy_flags,
        "source_bio": ctx.source_bio,
    }
    # הסרת ערכים ריקים משפרת את האות לרעש בפרומפט.
    return {k: v for k, v in payload.items() if v}


def _prompt_text(payload: Dict[str, Any]) -> str:
    json_payload = json.dumps(payload, ensure_ascii=False)
    return (
        "נא לפעול לפי ההנחיות הבאות:\n"
        "1. החזר JSON תקין עם שלושה שדות ברמה העליונה: "
        "'neutral_professional', 'service_human', 'urgent_trust'.\n"
        "2. לכל שדה יש להחזיר אובייקט עם 'teaser' ו-'body'.\n"
        "3. כל טקסט בעברית תקנית, בגוף שני רבים, ללא הבטחות שלא אושרו.\n"
        "4. אין לציין תעודות/זמינות חירום אלא אם 'policy_flags' מתאים.\n"
        f"5. הגבל את ה-teaser לעד {MAX_TEASER_WORDS} מילים ואת ה-body לעד {MAX_BODY_WORDS} מילים.\n"
        "6. שמור על טון בהתאם לשם המפתח:\n"
        "   - neutral_professional: ענייני ומדויק.\n"
        "   - service_human: חם, אמפתי, מדגיש שירות אישי.\n"
        "   - urgent_trust: מדגיש אמינות, זמינות ותגובה מהירה (אם יש סימוכין).\n"
        "7. אל תוסיף קוד גיבוי או טקסט מחוץ ל-JSON.\n"
        "\nנתוני העובד:\n"
        f"{json_payload}"
    )


def _call_llm(ctx: WorkerContext) -> Dict[str, Dict[str, str]]:
    if not ollama_client:
        raise RuntimeError("ollama client unavailable")

    payload = _build_prompt_payload(ctx)
    if not payload:
        raise ValueError("insufficient worker data for LLM prompt")

    prompt = _prompt_text(payload)
    messages = [
        {
            "role": "system",
            "content": (
                "אתה מסייע בעריכת טקסטים קצרים לבעלי מקצוע. "
                "הקפד על ניסוח טבעי, בעברית, ובהתאם להנחיות הפורמט."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    response = ollama_client.chat(messages)  # type: ignore[attr-defined]
    try:
        parsed = json.loads(response)
        if not isinstance(parsed, dict):
            raise ValueError("LLM response is not a JSON object")
        return parsed  # type: ignore[return-value]
    except Exception as exc:  # pragma: no cover - הגנות ריצה
        raise RuntimeError(f"failed to parse LLM response: {exc}")


def _fallback_styles(ctx: WorkerContext, source: str) -> Dict[str, Dict[str, str]]:
    """Deterministic Hebrew copy used when the model is unreachable."""

    field_hint = ctx.field_label or "מקצוען"
    area_hint = ctx.city
    services_hint = ctx.sub_services_compact or "פתרונות מלאים"
    years_hint = ctx.years
    rating_hint = ctx.rating
    availability = ctx.availability
    langs = ", ".join(ctx.languages[:3])

    def teaser_base() -> str:
        core = f"{ctx.display_name} – {services_hint}"
        if area_hint:
            core += f" ב{area_hint}"
        return core or f"{ctx.display_name} – {field_hint}"

    def body_base(tone: str) -> str:
        sentences: List[str] = []
        sentences.append(
            f"{ctx.display_name} עוסק ב{services_hint} {('ב' + area_hint) if area_hint else 'בכל האזור'}."
        )
        if years_hint:
            sentences.append(f"עם {years_hint} תקבלו עבודה אחראית ומסודרת.")
        elif ctx.experience_text:
            sentences.append(ctx.experience_text)
        if rating_hint and ctx.reviews_count:
            sentences.append(f"מדורג {rating_hint} על סמך {ctx.reviews_count} ביקורות אמיתיות.")
        elif rating_hint:
            sentences.append(f"מדורג {rating_hint} על ידי לקוחות האתר.")
        if availability:
            sentences.append(f"{availability} לשאלות ותיאומים.")
        if tone == "service":
            sentences.append("שמים דגש על יחס אישי, תיאום ציפיות ותקשורת זמינה.")
        elif tone == "urgent":
            sentences.append("מגיעים מהר לשטח, מתעדים הכל ומספקים פתרון אמין מהפנייה ועד הסגירה.")
        else:
            sentences.append("העבודה מתבצעת לפי התקנים ועם אחריות מלאה על הביצוע.")
        if langs:
            sentences.append(f"שפות שירות: {langs}.")
        return " ".join(sentences)

    fallback = {
        "neutral_professional": {
            "teaser": teaser_base(),
            "body": body_base("neutral"),
            "source": source,
        },
        "service_human": {
            "teaser": teaser_base(),
            "body": body_base("service"),
            "source": source,
        },
        "urgent_trust": {
            "teaser": teaser_base(),
            "body": body_base("urgent"),
            "source": source,
        },
    }

    for style in fallback.values():
        style["teaser"] = _word_trim(style["teaser"], MAX_TEASER_WORDS)
        style["body"] = _word_trim(style["body"], MAX_BODY_WORDS)
    return fallback


def _normalize_llm_output(raw: Mapping[str, Any], ctx: WorkerContext) -> Dict[str, Dict[str, str]]:
    normalized: Dict[str, Dict[str, str]] = {}
    for key in STYLE_KEYS.keys():
        data = raw.get(key) if isinstance(raw, Mapping) else None
        teaser = ""
        body = ""
        if isinstance(data, Mapping):
            teaser = _safe_str(data.get("teaser"))
            body = _safe_str(data.get("body"))
        if not teaser or not body:
            LOGGER.warning("worker description missing key '%s', using fallback", key)
            fallback = _fallback_styles(ctx, source="fallback")
            normalized[key] = fallback[key]
            continue
        normalized[key] = {
            "teaser": _word_trim(teaser, MAX_TEASER_WORDS),
            "body": _word_trim(body, MAX_BODY_WORDS),
            "source": "llm",
        }
    return normalized


def generate_worker_descriptions(worker: Mapping[str, Any]) -> Dict[str, Any]:
    """Return three tone variants plus the fields that were used."""

    ctx = _collect_context(worker)
    used_fields = ctx.used_fields.copy()

    try:
        llm_output = _call_llm(ctx)
        styles = _normalize_llm_output(llm_output, ctx)
    except Exception as exc:
        LOGGER.warning("LLM unavailable, using fallback copy: %s", exc)
        styles = _fallback_styles(ctx, source="fallback")

    result: Dict[str, Any] = {**styles, "used_fields": used_fields}
    return result


# ---------------------------------------------------------------------------
# Public helper with lightweight caching for Jinja
# ---------------------------------------------------------------------------
_CACHE: MutableMapping[str, Tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL_SECONDS = 15 * 60
_CACHE_MAX = 128


def _fingerprint(worker: Mapping[str, Any]) -> str:
    relevant_keys = [
        "worker_id",
        "id",
        "updated_at",
        "ai_updated_at",
        "name",
        "company_name",
        "field",
        "field_display",
        "city",
        "base_city",
        "sub_services",
        "services_list",
        "about_clean",
        "about",
        "description",
        "bio",
        "bio_short",
    ]
    payload = {k: worker.get(k) for k in relevant_keys if k in worker}
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha1(serialized.encode("utf-8")).hexdigest()


def describe_worker(worker: Mapping[str, Any]) -> Dict[str, Any]:
    """Return cached worker descriptions suitable for templates."""

    key = _fingerprint(worker)
    now = time.time()
    cached = _CACHE.get(key)
    if cached and (now - cached[0]) < _CACHE_TTL_SECONDS:
        return cached[1]

    try:
        data = generate_worker_descriptions(worker)
    except Exception as exc:
        LOGGER.error("failed to generate worker description: %s", exc)
        ctx = _collect_context(worker)
        data = {**_fallback_styles(ctx, source="error"), "used_fields": ctx.used_fields}

    _CACHE[key] = (now, data)
    if len(_CACHE) > _CACHE_MAX:
        # פינוי הרשומה הישנה ביותר
        oldest_key = min(_CACHE.items(), key=lambda item: item[1][0])[0]
        _CACHE.pop(oldest_key, None)

    return data


__all__ = [
    "generate_worker_descriptions",
    "describe_worker",
]