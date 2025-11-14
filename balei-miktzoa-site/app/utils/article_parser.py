"""Utilities for turning shortcode-based article text into renderable blocks."""
from __future__ import annotations
import re
from typing import Any, Iterable
SHORTCODE_RE = re.compile(r"^\[(?P<name>[A-Za-z0-9_]+)(?::\s*\"(?P<title>[^\"]*)\")?\]\s*$")
KEY_VALUE_RE = re.compile(r"^\s*([^:]+):\s*(.+?)\s*$")
DIVIDER_RE = re.compile(r"^[-\s]+$")
HEADING_PREFIXES = {"###": 3, "##": 2, "#": 2}
def _slugify(text: str, existing: set[str]) -> str:
    base = re.sub(r"[\s\u200f\u200e]+", " ", (text or "").strip())
    cleaned = re.sub(r"[^\w\u0590-\u05FF- ]+", "", base).strip().lower()
    cleaned = re.sub(r"\s+", "-", cleaned).strip("-") or "section"
    slug = cleaned
    counter = 2
    while slug in existing:
        slug = f"{cleaned}-{counter}"
        counter += 1
    existing.add(slug)
    return slug
def _flush_text_buffer(buffer: list[str], blocks: list[dict[str, Any]], seen_slugs: set[str]) -> None:
    if not buffer:
        return
    raw = "\n".join(buffer)
    buffer.clear()
    if not raw.strip():
        return
    segments = re.split(r"\n{2,}", raw)
    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue
        for prefix, level in HEADING_PREFIXES.items():
            if segment.startswith(prefix + " "):
                text = segment[len(prefix) + 1 :].strip()
                slug = _slugify(text, seen_slugs)
                blocks.append({
                    "type": "heading",
                    "data": {"level": level, "text": text, "slug": slug},
                })
                break
        else:
            lines = [ln for ln in segment.splitlines() if ln.strip()]
            if lines and all(_is_bullet(line) for line in lines):
                items = [_clean_bullet(line) for line in lines if _clean_bullet(line)]
                if items:
                    blocks.append({"type": "list", "data": {"items": items}})
                continue
            blocks.append({"type": "paragraph", "data": {"text": segment}})
def _is_bullet(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("- ") or stripped.startswith("• ") or stripped.startswith("•")
def _clean_bullet(line: str) -> str:
    stripped = line.strip()
    if stripped.startswith("- "):
        return stripped[2:].strip()
    if stripped.startswith("• "):
        return stripped[2:].strip()
    if stripped.startswith("•"):
        return stripped[1:].strip()
    return stripped
def _parse_key_values(lines: Iterable[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in lines:
        match = KEY_VALUE_RE.match(line)
        if match:
            key = match.group(1).strip().lower()
            value = match.group(2).strip()
            result[key] = value
    return result
def _parse_summary_cost(title: str | None, lines: list[str]) -> dict[str, Any] | None:
    data = _parse_key_values(lines)
    if not data:
        return None
    result: dict[str, Any] = {
        "title": data.get("title") or (title or ""),
        "avg": data.get("average") or data.get("avg"),
        "low": data.get("low"),
        "high": data.get("high"),
    }
    badges = data.get("badges") or data.get("labels")
    if badges:
        result["badges"] = [badge.strip() for badge in re.split(r",|\|", badges) if badge.strip()]
    return result
def _parse_table(title: str | None, lines: list[str]) -> dict[str, Any] | None:
    rows: list[list[str]] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or "|" not in stripped:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        rows.append(cells)
    if not rows:
        return None
    headers: list[str] | None = None
    if len(rows) >= 2 and all(DIVIDER_RE.match(cell or "") for cell in rows[1]):
        headers = rows[0]
        rows = rows[2:]
    elif rows:
        headers = rows[0]
        rows = rows[1:]
    clean_rows = [row for row in rows if any(cell for cell in row)]
    if not clean_rows:
        return None
    data: dict[str, Any] = {"rows": clean_rows}
    if headers and any(header for header in headers):
        data["headers"] = headers
    if title:
        data["title"] = title
    return data
def _parse_pros_cons(title: str | None, lines: list[str]) -> dict[str, Any] | None:
    items: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    active_field: str | None = None
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.endswith(":") and not stripped.startswith(("✅", "❌", "-", "•")):
            current = {"name": stripped[:-1].strip(), "pros": [], "cons": []}
            items.append(current)
            active_field = None
            continue
        if stripped.startswith("✅"):
            active_field = "pros"
            continue
        if stripped.startswith("❌"):
            active_field = "cons"
            continue
        content = stripped.lstrip("-• ")
        if current and active_field:
            current.setdefault(active_field, []).append(content)
    cleaned = [item for item in items if item.get("pros") or item.get("cons")]
    if not cleaned:
        return None
    result: dict[str, Any] = {"items": cleaned}
    if title:
        result["title"] = title
    return result
def _parse_note(title: str | None, lines: list[str]) -> dict[str, Any] | None:
    text_lines: list[str] = []
    bullet_items: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith(("- ", "• ", "•")):
            bullet_items.append(_clean_bullet(stripped))
        else:
            text_lines.append(stripped)
    data: dict[str, Any] = {}
    if title:
        data["title"] = title
    if text_lines:
        data["text"] = "\n".join(text_lines)
    if bullet_items:
        data["items"] = bullet_items
    return data or None
def _parse_checklist(title: str | None, lines: list[str]) -> dict[str, Any] | None:
    entries: list[dict[str, Any]] = []
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        checked = False
        text = stripped
        if text.startswith("-"):
            text = text[1:].strip()
        if text.lower().startswith("[x]"):
            checked = True
            text = text[3:].strip()
        elif text.lower().startswith("[ ]"):
            text = text[3:].strip()
        elif text.startswith("✓"):
            checked = True
            text = text[1:].strip()
        if text:
            entries.append({"text": text, "checked": checked})
    if not entries:
        return None
    data: dict[str, Any] = {"items": entries}
    if title:
        data["title"] = title
    return data
def _parse_steps(title: str | None, lines: list[str]) -> dict[str, Any] | None:
    steps: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        match = re.match(r"^(\d+)[).]\s*(.+)$", stripped)
        if match:
            if current:
                steps.append(current)
            current = {"title": match.group(2).strip(), "text": ""}
            continue
        if stripped.endswith(":") and not stripped.startswith("-"):
            if current:
                steps.append(current)
            current = {"title": stripped[:-1].strip(), "text": ""}
            continue
        if current is None:
            current = {"title": "", "text": stripped}
        else:
            if current.get("text"):
                current["text"] += "\n" + stripped
            else:
                current["text"] = stripped
    if current:
        steps.append(current)
    normalized = []
    for step in steps:
        title_text = step.get("title", "").strip()
        body = step.get("text", "").strip()
        if not (title_text or body):
            continue
        normalized.append({"title": title_text, "text": body})
    if not normalized:
        return None
    data: dict[str, Any] = {"items": normalized}
    if title:
        data["title"] = title
    return data
def _parse_questions(title: str | None, lines: list[str]) -> dict[str, Any] | None:
    items: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        if re.match(r"^(Q|שאלה)[:\s]", stripped, re.IGNORECASE):
            if current:
                items.append(current)
            question = re.sub(r"^(Q|שאלה)[:\s]+", "", stripped, flags=re.IGNORECASE).strip()
            current = {"question": question, "answer": ""}
            continue
        if re.match(r"^(A|תשובה)[:\s]", stripped, re.IGNORECASE):
            if current is None:
                current = {"question": "", "answer": ""}
            answer = re.sub(r"^(A|תשובה)[:\s]+", "", stripped, flags=re.IGNORECASE).strip()
            current["answer"] = answer
            continue
        if current is None:
            current = {"question": stripped, "answer": ""}
        else:
            key = "answer" if current.get("answer") else "question"
            if current[key]:
                current[key] += "\n" + stripped
            else:
                current[key] = stripped
    if current:
        items.append(current)
    cleaned = []
    for item in items:
        question = (item.get("question") or "").strip()
        answer = (item.get("answer") or "").strip()
        if question or answer:
            cleaned.append({"question": question, "answer": answer})
    if not cleaned:
        return None
    data: dict[str, Any] = {"items": cleaned}
    if title:
        data["title"] = title
    return data
_BLOCK_BUILDERS = {
    "summarycostcard": _parse_summary_cost,
    "datatable": _parse_table,
    "prosconsgrid": _parse_pros_cons,
    "warningblock": _parse_note,
    "tipblock": _parse_note,
    "checklistblock": _parse_checklist,
    "processsteps": _parse_steps,
    "questionsblock": _parse_questions,
    "comparisontable": _parse_table,
    "infobox": _parse_note,
}
_TYPE_NAMES = {
    "summarycostcard": "summary_cost",
    "datatable": "data_table",
    "prosconsgrid": "pros_cons_grid",
    "warningblock": "warning",
    "tipblock": "tip",
    "checklistblock": "checklist",
    "processsteps": "process_steps",
    "questionsblock": "questions",
    "comparisontable": "comparison_table",
    "infobox": "info_box",
}
def _build_block(name: str, title: str | None, lines: list[str]) -> dict[str, Any] | None:
    key = name.lower()
    builder = _BLOCK_BUILDERS.get(key)
    if not builder:
        return None
    data = builder(title, lines)
    if not data:
        return None
    return {"type": _TYPE_NAMES[key], "data": data}
def parse_shortcodes(text: str) -> list[dict[str, Any]]:
    """Parse shortcode-rich article text into block dictionaries."""
    if not text:
        return []
    lines = text.splitlines()
    blocks: list[dict[str, Any]] = []
    buffer: list[str] = []
    seen_slugs: set[str] = set()
    idx = 0
    total = len(lines)
    while idx < total:
        raw_line = lines[idx]
        match = SHORTCODE_RE.match(raw_line.strip())
        if match:
            _flush_text_buffer(buffer, blocks, seen_slugs)
            name = match.group("name")
            title = match.group("title")
            idx += 1
            payload: list[str] = []
            while idx < total:
                candidate = lines[idx]
                if SHORTCODE_RE.match(candidate.strip()):
                    break
                payload.append(candidate)
                idx += 1
            block = _build_block(name, title, payload)
            if block:
                blocks.append(block)
            else:
                fallback = "\n".join([raw_line] + payload)
                buffer.append(fallback)
            continue
        buffer.append(raw_line)
        idx += 1
    _flush_text_buffer(buffer, blocks, seen_slugs)
    return blocks