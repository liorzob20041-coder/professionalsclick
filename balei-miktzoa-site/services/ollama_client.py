# services/ollama_client.py
import os
import json
import time
import urllib.request
import urllib.error

# ===== תצורה =====
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.environ.get("AI_MODEL", "gemma2:9b-instruct-q4_K_S")
DEFAULT_TIMEOUT = int(os.getenv("AI_TIMEOUT", "60"))
RETRIES = int(os.getenv("AI_RETRIES", "2"))  # ניסיונות חוזרים על שגיאות רשת
BACKOFF = float(os.getenv("AI_BACKOFF", "0.6"))

def _default_options():
    def _f(env, default):
        try:
            return float(os.getenv(env, default))
        except Exception:
            return float(default)
    return {
        "temperature":    _f("AI_T", "0.65"),
        "top_p":          _f("AI_TOP_P", "0.95"),
        "repeat_penalty": _f("AI_RP", "1.05"),
        # אפשר להוסיף פרמטרים אם המודל תומך:
        # "num_ctx": int(os.getenv("AI_CTX", "4096")),
        # "max_tokens": int(os.getenv("AI_MAX_TOKENS", "512")),
    }

# ===== כלי רשת =====
def _request(path: str, payload: dict = None, method: str = "POST", timeout: int = None) -> dict:
    """
    בקשת JSON ל-Ollama עם ניסיונות חוזרים בסיסיים.
    """
    assert path.startswith("/"), "path must start with /"
    url = OLLAMA_URL.rstrip("/") + path
    body = None
    headers = {"Content-Type": "application/json"}

    if payload is not None:
        # ensure_ascii=False לשמירת עברית
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    last_err = None
    to = timeout or DEFAULT_TIMEOUT

    for attempt in range(RETRIES + 1):
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=to) as resp:
                raw = resp.read()
            return json.loads(raw.decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as e:
            # ננסה לחלץ פרטים
            try:
                detail = e.read().decode("utf-8", errors="replace")
            except Exception:
                detail = str(e)
            last_err = RuntimeError(f"Ollama HTTP error {e.code}: {detail}")
        except urllib.error.URLError as e:
            last_err = RuntimeError(f"Ollama URL error: {e.reason}")
        except Exception as e:
            last_err = e

        # אם נכשל – ננסה שוב עם backoff קטן
        if attempt < RETRIES:
            time.sleep(BACKOFF * (attempt + 1))

    # אם כל הנסיונות נכשלו
    raise last_err if last_err else RuntimeError("Unknown network error")

# ===== API עיקריים =====
def chat(messages, model: str = None, options: dict = None, timeout: int = None) -> str:
    """
    /api/chat – שיחת צ'אט. מחזיר את הטקסט של ה-assistant.
    """
    use_model = model or DEFAULT_MODEL
    opts = _default_options()
    if options:
        opts.update(options)

    payload = {
        "model": use_model,
        "messages": messages,
        "stream": False,
        "options": opts,
    }
    data = _request("/api/chat", payload=payload, method="POST", timeout=timeout)
    return (data.get("message") or {}).get("content", "") or ""

def generate(prompt: str, model: str = None, options: dict = None, timeout: int = None) -> str:
    """
    /api/generate – מצב השלמה ישירה (לא צ'אט). שימושי אם תרצה פרומפט בודד.
    """
    use_model = model or DEFAULT_MODEL
    opts = _default_options()
    if options:
        opts.update(options)

    payload = {
        "model": use_model,
        "prompt": prompt,
        "stream": False,
        "options": opts,
    }
    data = _request("/api/generate", payload=payload, method="POST", timeout=timeout)
    return data.get("response", "") or ""

# ===== עזרי דיבוג/ניהול קלים =====
def list_models(timeout: int = 10):
    """
    /api/tags – רשימת מודלים מקומית.
    """
    try:
        data = _request("/api/tags", payload=None, method="GET", timeout=timeout)
        return [m.get("name") for m in (data.get("models") or [])]
    except Exception:
        return []

def has_model(name: str) -> bool:
    try:
        return name in (list_models() or [])
    except Exception:
        return False

def info() -> dict:
    """
    מידע בסיסי על ברירות־מחדל – לעזור בדיבוג.
    """
    return {
        "OLLAMA_URL": OLLAMA_URL,
        "DEFAULT_MODEL": DEFAULT_MODEL,
        "DEFAULT_TIMEOUT": DEFAULT_TIMEOUT,
        "RETRIES": RETRIES,
        "BACKOFF": BACKOFF,
        "DEFAULT_OPTIONS": _default_options(),
    }
