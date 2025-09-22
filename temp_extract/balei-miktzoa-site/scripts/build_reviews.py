# scripts/build_reviews.py
import os, csv, json, urllib.request
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from pathlib import Path
import secrets
from deep_translator import GoogleTranslator


# נתיב בסיס של הפרויקט (תעדכן אם צריך)
BASE_DIR = r"C:\Users\liorz\OneDrive\שולחן העבודה\balei-miktzoa-site"
DATA_DIR = os.path.join(BASE_DIR, "data")
OUT_PATH = os.path.join(DATA_DIR, "worker_reviews.json")

# כתובת השיטס עם הביקורות (CSV export)
REVIEWS_URL = "https://docs.google.com/spreadsheets/d/1ORUqM51tJTqPo8d4b9kS8MO9n_sywYgDstXaH4Ookgo/export?format=csv&gid=1432374502"

def translate_review(text: str) -> dict:
    """
    מתרגם he->en/ru עם deep_translator.
    אם יש כשל/rate limit – נשאיר את הטקסט המקורי כדי לא לשבור את הבילד.
    """
    translations = {"he": text}
    for lang in ("en", "ru"):
        try:
            translations[lang] = GoogleTranslator(source="iw", target=lang).translate(text)
        except Exception:
            translations[lang] = text
    return translations


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def fetch_text(url: str) -> str:
    with urllib.request.urlopen(url) as resp:
        return resp.read().decode("utf-8-sig")

def detect_delimiter_from_url(url: str) -> str:
    q = parse_qs(urlparse(url).query)
    out = (q.get("output", [""])[0] or "").lower()
    return "\t" if out == "tsv" else ","

def parse_table(text: str, delimiter: str):
    return list(csv.DictReader(text.splitlines(), delimiter=delimiter))

def main():
    print("==> מושך ביקורות מהשיטס")
    text = fetch_text(REVIEWS_URL)
    delimiter = detect_delimiter_from_url(REVIEWS_URL)
    rows = parse_table(text, delimiter)

    reviews = []
    for r in rows:
        worker_id = (r.get("worker_id") or "").strip()
        author    = (r.get("author") or "").strip()
        text      = (r.get("text") or "").strip()
        rating    = r.get("rating")
        date      = r.get("date") or datetime.now().isoformat()

        if not (worker_id and text and author):
            continue

        review = {
            "review_id": r.get("review_id") or secrets.token_hex(8),
            "worker_id": worker_id,
            "author":    author,
            "text":      text,
            "translations": translate_review(text),
            "rating":    float(rating) if rating else None,
            "date":      date,
        }
        reviews.append(review)

    ensure_dir(DATA_DIR)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(reviews, f, ensure_ascii=False, indent=2)

    print(f"✔ נכתב: {os.path.abspath(OUT_PATH)}  (סה״כ {len(reviews)} ביקורות)")

if __name__ == "__main__":
    main()
