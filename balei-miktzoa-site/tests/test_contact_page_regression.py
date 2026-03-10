import importlib.util
import os
import re
import sys
from pathlib import Path


def _load_app_module():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    os.environ.setdefault("INVITE_KEY", "test-invite")
    spec = importlib.util.spec_from_file_location("balei_app", root / "app.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _extract_csrf_token(html: str) -> str:
    match = re.search(r'name=["\']csrf_token["\'][^>]*value=["\']([^"\']+)', html)
    assert match, "csrf_token not found in login page"
    return match.group(1)


def test_contact_page_renders_submit_and_not_raw_translation_key():
    module = _load_app_module()
    client = module.app.test_client()

    response = client.get("/he/contact")
    assert response.status_code == 200

    body = response.get_data(as_text=True)
    assert '<button type="submit">' in body
    assert 'page_contact_heading' not in body
    assert 'homepage.whatsapp_help' not in body


def test_admin_login_rate_limit_returns_429_with_login_page_message():
    module = _load_app_module()
    module.app.config["TESTING"] = True
    module.app.config["WTF_CSRF_ENABLED"] = False
    client = module.app.test_client()

    environ = {"REMOTE_ADDR": "10.10.10.10"}
    login_page = client.get("/admin/analysis/login", environ_overrides=environ)
    assert login_page.status_code == 200
    csrf_token = _extract_csrf_token(login_page.get_data(as_text=True))

    form_data = {"password": "wrong-password", "csrf_token": csrf_token}

    for _ in range(5):
        response = client.post(
            "/admin/analysis/login",
            data=form_data,
            environ_overrides=environ,
        )
        assert response.status_code == 200

    blocked = client.post(
        "/admin/analysis/login",
        data=form_data,
        environ_overrides=environ,
    )
    assert blocked.status_code == 429
    body = blocked.get_data(as_text=True)
    assert "בוצעו יותר מדי ניסיונות בזמן קצר. נסו שוב בעוד כמה דקות." in body


def test_admin_login_rate_limit_returns_json_for_ajax_requests():
    module = _load_app_module()
    module.app.config["TESTING"] = True
    module.app.config["WTF_CSRF_ENABLED"] = False
    client = module.app.test_client()

    environ = {"REMOTE_ADDR": "20.20.20.20"}
    login_page = client.get("/admin/analysis/login", environ_overrides=environ)
    assert login_page.status_code == 200
    csrf_token = _extract_csrf_token(login_page.get_data(as_text=True))

    form_data = {"password": "wrong-password", "csrf_token": csrf_token}
    headers = {
        "Accept": "application/json",
        "X-Requested-With": "fetch",
    }

    for _ in range(5):
        response = client.post(
            "/admin/analysis/login",
            data=form_data,
            headers=headers,
            environ_overrides=environ,
        )
        assert response.status_code == 200

    blocked = client.post(
        "/admin/analysis/login",
        data=form_data,
        headers=headers,
        environ_overrides=environ,
    )
    assert blocked.status_code == 429
    assert blocked.is_json
    payload = blocked.get_json()
    assert payload == {
        "ok": False,
        "error": "rate_limit",
        "message": "בוצעו יותר מדי ניסיונות בזמן קצר. נסו שוב בעוד כמה דקות.",
    }
