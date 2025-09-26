# -*- coding: utf-8 -*-
# scripts/build_all_translations.py
import os, csv, json, urllib.request, urllib.error, re
from urllib.parse import urlparse, parse_qs, quote

# === נתיבים מקומיים ===
BASE_DIR = r"C:\Users\liorz\OneDrive\שולחן העבודה\balei-miktzoa-site"
SOURCES_JSON = os.path.join(BASE_DIR, "scripts", "translations_sources.json")
OUT_ROOT = os.path.join(BASE_DIR, "translations")

# שפות בטורים
LANGS = ["he", "en", "ru"]

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def http_get(url: str) -> str:
    """GET עם User-Agent תקין + החזרת טקסט"""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        }
    )
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode("utf-8-sig")

def detect_delimiter_from_url(url: str) -> str:
    """מזהה מפריד (CSV/TSV). תומך גם ב-gviz tqx=out:csv/tsv."""
    q = parse_qs(urlparse(url).query)
    output = (q.get("output", [""])[0] or "").lower()
    fmt    = (q.get("format", [""])[0] or "").lower()
    tqx    = (q.get("tqx", [""])[0] or "").lower()
    if "out:tsv" in tqx or output == "tsv" or fmt == "tsv":
        return "\t"
    return ","

def parse_table(text: str, delimiter: str):
    return list(csv.DictReader(text.splitlines(), delimiter=delimiter))

def build_lang_maps(rows):
    """
    בונה מפות תרגום לכל שפה.
    - key -> <label בשפה>
    - key.price -> <price בשפה>  (אם קיימת price_<lang> בשורה)
    """
    maps = {lang: {} for lang in LANGS}
    if not rows:
        return maps

    # בדיקת כותרות נדרשות
    headers = {h.strip().lower() for h in rows[0].keys()}
    required = {"key"} | set(LANGS)
    missing = required - headers
    if missing:
        raise SystemExit(f"שדות חסרים בגליון: {', '.join(sorted(missing))}")

    # יש גם עמודות מחירים אופציונליות: price_he, price_en, price_ru
    for r in rows:
        key = (r.get("key") or r.get("Key") or "").strip()
        if not key:
            continue
        for lang in LANGS:
            label = (r.get(lang) or r.get(lang.upper()) or "").strip()
            if label:
                maps[lang][key] = label

            price_col = f"price_{lang}"
            price_val = (r.get(price_col) or r.get(price_col.upper()) or "").strip()
            if price_val:
                maps[lang][f"{key}.price"] = price_val

    return maps


_SPREADSHEET_ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")

def extract_spreadsheet_id(s: str) -> str | None:
    if not s:
        return None
    if re.fullmatch(r"[a-zA-Z0-9-_]{20,}", s):
        return s
    m = _SPREADSHEET_ID_RE.search(s)
    return m.group(1) if m else None

# ---- URL builders (gviz יציב לפי שם לשונית) ----
def build_gviz_url_by_sheet(base_doc: str, sheet_name: str) -> str:
    spreadsheet_id = extract_spreadsheet_id(base_doc)
    if not spreadsheet_id:
        raise SystemExit("לא הצלחנו לחלץ spreadsheetId מ-_doc_id.")
    return (
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
        f"/gviz/tq?tqx=out:csv&sheet={quote(sheet_name)}"
    )

def build_gviz_url_by_gid(base_doc: str, gid: str | int) -> str:
    spreadsheet_id = extract_spreadsheet_id(base_doc)
    if not spreadsheet_id:
        raise SystemExit("לא הצלחנו לחלץ spreadsheetId מ-_doc_id.")
    return (
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
        f"/gviz/tq?tqx=out:csv&gid={gid}"
    )

def build_export_url(base_doc: str, gid: str | int, fmt: str = "csv") -> str:
    spreadsheet_id = extract_spreadsheet_id(base_doc)
    if not spreadsheet_id:
        raise SystemExit("לא הצלחנו לחלץ spreadsheetId מ-_doc_id.")
    gid_str = str(gid)
    fmt = (fmt or "csv").lower()
    if fmt not in ("csv", "tsv"):
        fmt = "csv"
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format={fmt}&gid={gid_str}"

def build_pub_url(base_doc: str, gid: str | int, fmt: str = "csv") -> str:
    spreadsheet_id = extract_spreadsheet_id(base_doc)
    gid_str = str(gid)
    fmt = (fmt or "csv").lower()
    if fmt not in ("csv", "tsv"):
        fmt = "csv"
    # pub?output=csv דורש File > Share: Anyone with the link (Viewer)
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/pub?gid={gid_str}&single=true&output={fmt}"

def urls_for_source(page: str, raw, base_doc: str | None) -> list[str]:
    """
    מחזיר רשימת מועמדים (מהכי יציב לחלופי):
    - dict עם sheet: שימוש בשם לשונית (gviz) – הכי יציב.
    - string לא-URL: שם לשונית (gviz).
    - gid: gviz-by-gid ואז export/pub.
    - URL מלא: כמו שהוא.
    """
    cand: list[str] = []

    # URL מלא
    if isinstance(raw, str) and raw.strip().lower().startswith(("http://", "https://")):
        cand.append(raw.strip())
        return cand

    if not base_doc:
        if isinstance(raw, (int, str)) and not str(raw).startswith(("http://", "https://")):
            raise SystemExit(f"page='{page}': נדרש _doc_id כדי לבנות URL מ-sheet/gid")
        return cand

    # dict
    if isinstance(raw, dict):
        sheet = raw.get("sheet")
        gid   = raw.get("gid")
        fmt   = (raw.get("format") or "csv").lower()
        if sheet:
            cand.append(build_gviz_url_by_sheet(base_doc, sheet))
        if gid is not None:
            cand.append(build_gviz_url_by_gid(base_doc, gid))
            cand.append(build_export_url(base_doc, gid, fmt))
            cand.append(build_pub_url(base_doc, gid, fmt))
        return cand

    # string לא-URL ⇒ sheet name
    if isinstance(raw, str):
        cand.append(build_gviz_url_by_sheet(base_doc, raw.strip()))
        return cand

    # מספר ⇒ gid
    if isinstance(raw, int) or (isinstance(raw, str) and raw.isdigit()):
        gid = int(raw)
        cand.append(build_gviz_url_by_gid(base_doc, gid))
        cand.append(build_export_url(base_doc, gid, "csv"))
        cand.append(build_pub_url(base_doc, gid, "csv"))
        return cand

    return cand

def main():
    if not os.path.exists(SOURCES_JSON):
        raise FileNotFoundError(f"לא נמצא הקובץ: {SOURCES_JSON}")
    with open(SOURCES_JSON, "r", encoding="utf-8") as f:
        sources = json.load(f)
    if not isinstance(sources, dict) or not sources:
        raise SystemExit("translations_sources.json חייב להכיל mapping של page -> (sheet|gid|url|obj)")

    base_doc = sources.get("_doc_id")
    ensure_dir(OUT_ROOT)

    total = 0
    for page, raw in sources.items():
        if str(page).startswith("_"):
            continue

        candidates = urls_for_source(page, raw, base_doc)
        if not candidates:
            print(f"מדלג: '{page}' ללא מקור תקף. ערך: {raw!r}")
            continue

        last_err = None
        tried = []

        for url in candidates:
            try:
                print(f"\n==> מושך תרגומים עבור page='{page}'")
                print(f"    URL: {url}")
                text = http_get(url)
                delimiter = detect_delimiter_from_url(url)
                rows = parse_table(text, delimiter)
                lang_maps = build_lang_maps(rows)

                for lang in LANGS:
                    out_dir = os.path.join(OUT_ROOT, lang)
                    ensure_dir(out_dir)
                    out_path = os.path.join(out_dir, f"{page}.json")
                    with open(out_path, "w", encoding="utf-8") as out:
                        json.dump(lang_maps[lang], out, ensure_ascii=False, indent=2)
                total += 1
                print(f"✔ נוצרו קבצים ל-{page} (keys: {len(lang_maps[LANGS[0]])})")
                break
            except urllib.error.HTTPError as e:
                tried.append((url, e.code))
                last_err = e
                print(f"   אזהרה: HTTP {e.code}. מנסה חלופי…")
                continue
            except Exception as e:
                tried.append((url, str(e)))
                last_err = e
                print(f"   שגיאה בקריאה: {e}. מנסה חלופי…")
                continue
        else:
            print(f"\n✖ נכשל לדף '{page}'. ניסיונות:")
            for u, c in tried:
                print(f"   - {u} -> {c}")
            if last_err:
                raise last_err

    print(f"\nOK • נוצרו {total} קבצים • מקור: {SOURCES_JSON}")

if __name__ == "__main__":
    main()
