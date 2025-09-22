# scripts/build_all_translations.py
import os, csv, json, urllib.request
from urllib.parse import urlparse, parse_qs

# נתיבי בסיס
BASE_DIR = r"C:\Users\liorz\OneDrive\שולחן העבודה\balei-miktzoa-site"
SOURCES_JSON = os.path.join(BASE_DIR, "scripts", "translations_sources.json")
OUT_ROOT = os.path.join(BASE_DIR, "translations")

# אילו שפות מייצרים
LANGS = ["he", "en", "ru"]

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def fetch_text(url: str) -> str:
    with urllib.request.urlopen(url) as resp:
        # utf-8-sig מסיר BOM אם יש
        return resp.read().decode("utf-8-sig")

def detect_delimiter_from_url(url: str) -> str:
    # אם output=tsv => טאבים, אחרת נברור פסיקים
    q = parse_qs(urlparse(url).query)
    out = (q.get("output", [""])[0] or "").lower()
    return "\t" if out == "tsv" else ","

def parse_table(text: str, delimiter: str):
    # קורא את הטבלה למבנה של DictReader
    return list(csv.DictReader(text.splitlines(), delimiter=delimiter))

def build_lang_maps(rows):
    """
    rows: רשומות עם עמודות key, he, en, ru
    החזרה: { 'he': {...}, 'en': {...}, 'ru': {...} }
    """
    maps = {lang: {} for lang in LANGS}
    if not rows:
        return maps

    # ולידציה מינימלית של כותרות
    headers = {h.strip().lower() for h in rows[0].keys()}
    required = {"key"} | set(LANGS)
    missing = required - headers
    if missing:
        raise SystemExit(f"שדות חסרים בגליון: {', '.join(sorted(missing))}")

    for r in rows:
        key = (r.get("key") or r.get("Key") or "").strip()
        if not key:
            continue
        for lang in LANGS:
            val = (r.get(lang) or r.get(lang.upper()) or "").strip()
            # אפשר לשים fallback = key אם ריק. כרגע נשאיר ריק כדי לזהות חסרים ב־UI אם יש.
            maps[lang][key] = val
    return maps

def main():
    # טען את מפת המקורות (page -> url)
    if not os.path.exists(SOURCES_JSON):
        raise FileNotFoundError(f"לא נמצא הקובץ: {SOURCES_JSON}")
    with open(SOURCES_JSON, "r", encoding="utf-8") as f:
        sources = json.load(f)
    if not isinstance(sources, dict) or not sources:
        raise SystemExit("translations_sources.json חייב להכיל mapping של page->url")

    ensure_dir(OUT_ROOT)

    total = 0
    for page, url in sources.items():
        if not url:
            print(f"מדלג: '{page}' ללא URL")
            continue

        print(f"\n==> מושך תרגומים עבור page='{page}'")
        text = fetch_text(url)
        delimiter = detect_delimiter_from_url(url)
        rows = parse_table(text, delimiter)
        lang_maps = build_lang_maps(rows)

        # כתיבה ל-translations/<lang>/<page>.json
        for lang in LANGS:
            out_dir = os.path.join(OUT_ROOT, lang)
            ensure_dir(out_dir)
            out_path = os.path.join(out_dir, f"{page}.json")
            with open(out_path, "w", encoding="utf-8") as out:
                json.dump(lang_maps[lang], out, ensure_ascii=False, indent=2)
            total += 1
            print(f"✔ נכתב: {os.path.abspath(out_path)}  (keys: {len(lang_maps[lang])})")

    print(f"\nOK • נוצרו {total} קבצים • מקור: {SOURCES_JSON}")

if __name__ == "__main__":
    main()
