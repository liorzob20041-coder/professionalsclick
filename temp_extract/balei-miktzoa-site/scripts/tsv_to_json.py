# scripts/tsv_to_json.py
import csv, json, os

# === הקובץ המדויק שלך (CSV או TSV) ===
DATA_PATH = r"C:\Users\liorz\OneDrive\שולחן העבודה\balei-miktzoa-site\scripts\site-data - translations.csv"

# === שם הדף לקובץ היעד: translations/<lang>/<PAGE>.json ===
PAGE = "home"

# === תיקיית היעד (ליד scripts\..\translations) ===
OUT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "translations"))

LANGS = ["he", "en", "ru"]

# --- בדיקה שהקובץ קיים ---
if not os.path.exists(DATA_PATH):
    raise FileNotFoundError(f"לא נמצא הקובץ: {DATA_PATH}")

# --- קובע מפריד לפי סיומת: .tsv => טאבים, אחרת פסיקים ---
ext = os.path.splitext(DATA_PATH)[1].lower()
delimiter = "\t" if ext == ".tsv" else ","

# --- קריאה מה-CSV/TSV ---
with open(DATA_PATH, "r", encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f, delimiter=delimiter)
    fieldnames = [h.strip() for h in (reader.fieldnames or [])]
    required = {"key", "he", "en", "ru"}
    missing = required - set(fieldnames)
    if missing:
        raise SystemExit(f"שדות חסרים בקובץ: {', '.join(sorted(missing))}")
    rows = list(reader)

# --- בניית מילונים לכל שפה ---
data = {lang: {} for lang in LANGS}
for r in rows:
    key = (r.get("key") or "").strip()
    if not key:
        continue
    for lang in LANGS:
        data[lang][key] = (r.get(lang) or "").strip()

# --- כתיבה ל-translations/<lang>/<PAGE>.json ---
for lang in LANGS:
    out_dir = os.path.join(OUT_ROOT, lang)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{PAGE}.json")
    with open(out_path, "w", encoding="utf-8") as out:
        json.dump(data[lang], out, ensure_ascii=False, indent=2)
    print("wrote", os.path.abspath(out_path))

print("OK • source:", DATA_PATH)
