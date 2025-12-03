from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
def _ensure_he_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Return the Hebrew meta dictionary, ensuring it is a mapping."""
    he_meta = meta.get("he")
    if not isinstance(he_meta, dict):
        he_meta = {}
        meta["he"] = he_meta
    return he_meta
BASE_DIR = Path(__file__).resolve().parent
CONTENT_ROOT = BASE_DIR / "content"
def _iter_article_directories() -> Iterable[tuple[str, Path]]:
    """Yield (category, article_dir) pairs for all article directories."""
    if not CONTENT_ROOT.exists():
        return
    for category_dir in sorted(CONTENT_ROOT.iterdir()):
        if not category_dir.is_dir():
            continue
        for article_dir in sorted(category_dir.iterdir()):
            if not article_dir.is_dir():
                continue
            yield category_dir.name, article_dir
def _resolve_meta_path(article_dir: Path, slug_hint: Optional[str] = None) -> Optional[Path]:
    """Return the most specific meta file path available for an article."""
    candidates = []
    if slug_hint:
        candidates.append(article_dir / f"meta.{slug_hint}.json")
    dir_name = article_dir.name
    if slug_hint != dir_name:
        candidates.append(article_dir / f"meta.{dir_name}.json")
    candidates.append(article_dir / "meta.json")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None
def _resolve_body_path(article_dir: Path, slug: str, lang: str) -> Optional[Path]:
    """Return the body HTML path, supporting slug-aware fallbacks."""
    candidates = [article_dir / f"body.{lang}.{slug}.html", article_dir / f"body.{lang}.html"]
    if lang != "he":
        candidates.append(article_dir / f"body.he.{slug}.html")
        candidates.append(article_dir / "body.he.html")
    else:
        candidates.append(article_dir / "body.he.html")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None
def _extract_lang_data(meta: Dict[str, Any], lang: str) -> Dict[str, Any]:
    """Return language-specific metadata with graceful fallbacks."""
    lang_data = meta.get(lang)
    if isinstance(lang_data, dict):
        return lang_data
    if lang != "he":
        he_data = meta.get("he")
        if isinstance(he_data, dict):
            return he_data
    fallback: Dict[str, Any] = {}
    for key in ("title", "description", "excerpt"):
        value = meta.get(key)
        if isinstance(value, str) and value:
            fallback[key] = value
    return fallback
def load_article(slug: str, lang: str) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    """Load a single article's metadata, language-specific data, and HTML body."""
    for category, article_dir in _iter_article_directories():
        meta_path = _resolve_meta_path(article_dir, slug_hint=slug)
        if meta_path is None:
            continue
        with meta_path.open(encoding="utf-8") as f:
            meta = json.load(f)
        meta_slug = meta.get("slug") or article_dir.name
        if meta_slug != slug:
            continue
        if not meta.get("category"):
            derived_category = category if category != "articles" else None
            if derived_category:
                meta["category"] = derived_category
        _ensure_he_meta(meta)
        lang_data = _extract_lang_data(meta, lang)
        body_path = _resolve_body_path(article_dir, slug, lang)
        body_html = ""
        if body_path is not None and body_path.exists():
            body_html = body_path.read_text(encoding="utf-8")
        return meta, lang_data, body_html
    raise FileNotFoundError(f"Article meta not found for slug: {slug}")
def load_articles_list(lang: str) -> List[Dict[str, Any]]:
    """Return a list of article summaries for the index page."""
    articles: List[Dict[str, Any]] = []
    if not CONTENT_ROOT.exists():
        return articles
    for category, article_dir in _iter_article_directories():
        meta_path = _resolve_meta_path(article_dir, slug_hint=article_dir.name)
        if meta_path is None:
            continue
        with meta_path.open(encoding="utf-8") as f:
            meta = json.load(f)
        status = str(meta.get("status", "published")).lower()
        if status not in {"published", "public", "live"}:
            continue
        slug = meta.get("slug") or article_dir.name
        lang_data = _extract_lang_data(meta, lang)
        derived_category = meta.get("category") or (category if category != "articles" else None)
        _ensure_he_meta(meta)

        hero_image = meta.get("hero_image") or meta.get("hero_image_source")
        if not hero_image:
            hero_file = meta.get("hero_image_file")
            if hero_file:
                hero_image = f"/static/{str(hero_file).lstrip('/')}"

        article_data: Dict[str, Any] = {
            "slug": slug,
            "date": meta.get("date"),
            "category": derived_category,
            "featured": bool(meta.get("featured", False)),
            "popular": bool(meta.get("popular", False)),
            "hero_image": hero_image,
            "hero_image_file": meta.get("hero_image_file") or meta.get("hero_image_source"),
            "hero_image_width": meta.get("hero_image_width"),
            "hero_image_height": meta.get("hero_image_height"),
            "hero_alt": meta.get("hero_alt"),
            "img_file": meta.get("img_file"),
            "img_width": meta.get("img_width"),
            "img_height": meta.get("img_height"),
            "reading_minutes": meta.get("reading_minutes"),
            "placeholder": meta.get("placeholder"),
            "content_type": meta.get("content_type"),
            "type": meta.get("type"),
            "title": lang_data.get("title"),
            "description": lang_data.get("description"),
            "excerpt": lang_data.get("excerpt") or lang_data.get("description"),
            "tags": meta.get("tags", []),
        }
        articles.append(article_data)
    articles.sort(key=lambda a: a.get("date") or "", reverse=True)
    return articles
def get_related_articles(
    current_slug: str,
    category: Optional[str],
    lang: str = "he",
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """Return a list of related articles that share the same category."""
    related: List[Dict[str, Any]] = []
    articles = load_articles_list(lang)
    for article in articles:
        slug = article.get("slug")
        if not slug or slug == current_slug:
            continue
        if category and article.get("category") != category:
            continue
        try:
            meta, lang_data, _ = load_article(slug, lang)
        except FileNotFoundError:
            continue
        related.append({
            "slug": meta.get("slug") or slug,
            "meta": meta,
            "lang_data": lang_data,
        })
        if len(related) >= limit:
            break
    return related
