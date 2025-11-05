from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
BASE_DIR = Path(__file__).resolve().parent
ARTICLES_ROOT = BASE_DIR / "content" / "articles"
def load_article(slug: str, lang: str) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    """Load a single article's metadata, language-specific data, and HTML body."""
    article_dir = ARTICLES_ROOT / slug
    meta_path = article_dir / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Article meta.json not found for slug: {slug}")
    with meta_path.open(encoding="utf-8") as f:
        meta = json.load(f)
    lang_data = meta.get(lang) or meta.get("he") or {}
    body_path = article_dir / f"body.{lang}.html"
    if not body_path.exists():
        body_path = article_dir / "body.he.html"
    body_html = ""
    if body_path.exists():
        body_html = body_path.read_text(encoding="utf-8")
    return meta, lang_data, body_html
def load_articles_list(lang: str) -> List[Dict[str, Any]]:
    """Return a list of article summaries for the index page."""
    articles: List[Dict[str, Any]] = []
    if not ARTICLES_ROOT.exists():
        return articles
    for article_dir in sorted(ARTICLES_ROOT.iterdir()):
        if not article_dir.is_dir():
            continue
        meta_path = article_dir / "meta.json"
        if not meta_path.exists():
            continue
        with meta_path.open(encoding="utf-8") as f:
            meta = json.load(f)
        if meta.get("status") != "published":
            continue
        slug = meta.get("slug") or article_dir.name
        lang_data = meta.get(lang) or meta.get("he") or {}
        articles.append(
            {
                "slug": slug,
                "date": meta.get("date"),
                "category": meta.get("category"),
                "hero_image": meta.get("hero_image"),
                "reading_minutes": meta.get("reading_minutes"),
                "title": lang_data.get("title"),
                "description": lang_data.get("description"),
                "tags": meta.get("tags", []),
            }
        )
    articles.sort(key=lambda a: a.get("date") or "", reverse=True)
    return articles