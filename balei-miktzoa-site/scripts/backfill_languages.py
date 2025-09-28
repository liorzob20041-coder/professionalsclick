#!/usr/bin/env python3
"""Backfill worker language lists in approved.json and pending.json."""

import argparse
import json
from pathlib import Path
from typing import Iterable, List, Sequence

WORKER_LANGUAGE_CHOICES: Sequence[str] = (
    "עברית",
    "אנגלית",
    "רוסית",
    "ערבית",
    "אמהרית",
    "צרפתית",
    "ספרדית",
)
DEFAULT_LANGUAGES: Sequence[str] = ()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
TARGET_FILES = ("approved.json", "pending.json")


def _collect_languages(values: Iterable[str]) -> List[str]:
    allowed = set(WORKER_LANGUAGE_CHOICES)
    cleaned: List[str] = []
    seen = set()
    for value in values:
        if not isinstance(value, str):
            continue
        label = value.strip()
        if not label or label not in allowed or label in seen:
            continue
        seen.add(label)
        cleaned.append(label)
    return cleaned


def sanitize_languages(raw) -> List[str]:
    if isinstance(raw, str):
        candidates = [raw]
    elif isinstance(raw, (list, tuple, set)):
        candidates = list(raw)
    else:
        candidates = []

    cleaned = _collect_languages(candidates)
    if cleaned:
        return cleaned
    return _collect_languages(DEFAULT_LANGUAGES)


def process_file(path: Path, apply: bool) -> None:
    if not path.exists():
        print(f"- skip {path.name} (missing)")
        return

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"- skip {path.name} (invalid JSON: {exc})")
        return

    if not isinstance(data, list):
        print(f"- skip {path.name} (expected list root)")
        return

    updated = 0
    for item in data:
        if not isinstance(item, dict):
            continue
        sanitized = sanitize_languages(item.get("languages"))
        if item.get("languages") != sanitized:
            item["languages"] = sanitized
            updated += 1

    if updated == 0:
        print(f"• {path.name}: already up to date")
        return

    if apply:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✔ {path.name}: updated {updated} records")
    else:
        print(f"• {path.name}: would update {updated} records (run with --apply to write changes)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill worker language lists in JSON data files."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write updates to disk (default is a dry-run).",
    )
    args = parser.parse_args()

    for filename in TARGET_FILES:
        process_file(DATA_DIR / filename, apply=args.apply)


if __name__ == "__main__":
    main()