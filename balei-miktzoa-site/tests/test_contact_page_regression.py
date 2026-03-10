import importlib.util
import os
import re
import sys
from pathlib import Path


_ENV_UNSET = object()


def _load_app_module(*, admin_password_hash=_ENV_UNSET, admin_password_plain=_ENV_UNSET):
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    os.environ.setdefault("INVITE_KEY", "test-invite")

    if admin_password_hash is not _ENV_UNSET:
        if admin_password_hash is None:
            os.environ.pop("ADMIN_PASSWORD_HASH", None)
        else:
            os.environ["ADMIN_PASSWORD_HASH"] = admin_password_hash

    if admin_password_plain is not _ENV_UNSET:
        if admin_password_plain is None:
            os.environ.pop("ADMIN_PASSWORD_PLAIN", None)
        else:
            os.environ["ADMIN_PASSWORD_PLAIN"] = admin_password_plain
    spec = importlib.util.spec_from_file_location("balei_app", root / "app.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _extract_csrf_token(html: str) -> str:
    match = re.search(r'name=["\']csrf_token["\'][^>]*value=["\']([^"\']+)', html)
    assert match, "csrf_token not found in login page"
    return match.group(1)


def _login_as_admin(client, password: str, next_url: str = "/admin/analysis/dashboard"):
    login_page = client.get(f"/admin/analysis/login?next={next_url}")
    assert login_page.status_code == 200
    csrf_token = _extract_csrf_token(login_page.get_data(as_text=True))
    return client.post(
        "/admin/analysis/login",
        data={"password": password, "csrf_token": csrf_token, "next": next_url},
        follow_redirects=False,
    )


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


def test_admin_login_page_renders_expected_ui():
    module = _load_app_module()
    module.app.config["TESTING"] = True
    client = module.app.test_client()

    response = client.get("/admin/analysis/login")
    assert response.status_code == 200

    body = response.get_data(as_text=True)
    assert "התחברות לאזור ניהול" in body
    assert 'name="password"' in body
    assert "type=\"hidden\" name=\"csrf_token\"" in body
    assert "התחברות" in body


def test_admin_login_success_redirects_and_establishes_session():
    module = _load_app_module(admin_password_hash=None, admin_password_plain="correct-password")
    module.ADMIN_PASSWORD_HASH = ""
    os.environ["ADMIN_PASSWORD_PLAIN"] = "correct-password"
    module.app.config["TESTING"] = True
    module.app.config["WTF_CSRF_ENABLED"] = False
    client = module.app.test_client()

    login = _login_as_admin(client, "correct-password")
    assert login.status_code == 302
    assert login.headers["Location"].endswith("/admin/analysis/dashboard")

    with client.session_transaction() as sess:
        assert sess.get("is_admin") is True

    protected = client.get("/admin/analysis/dashboard")
    assert protected.status_code == 200


def test_admin_login_wrong_password_stays_unauthenticated_with_error():
    module = _load_app_module(admin_password_hash=None, admin_password_plain="correct-password")
    module.ADMIN_PASSWORD_HASH = ""
    os.environ["ADMIN_PASSWORD_PLAIN"] = "correct-password"
    module.app.config["TESTING"] = True
    module.app.config["WTF_CSRF_ENABLED"] = False
    client = module.app.test_client()

    login = _login_as_admin(client, "wrong-password")
    assert login.status_code == 200
    body = login.get_data(as_text=True)
    assert "סיסמה שגויה" in body

    with client.session_transaction() as sess:
        assert not sess.get("is_admin")


def test_protected_admin_route_redirects_when_unauthenticated():
    module = _load_app_module()
    module.app.config["TESTING"] = True
    client = module.app.test_client()

    response = client.get("/admin/analysis/dashboard", follow_redirects=False)
    assert response.status_code == 302
    assert "/admin/analysis/login" in response.headers["Location"]
    assert "next=/admin/analysis/dashboard" in response.headers["Location"]
