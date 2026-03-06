import importlib.util
import os
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


def test_contact_page_renders_submit_and_not_raw_translation_key():
    module = _load_app_module()
    client = module.app.test_client()

    response = client.get("/he/contact")
    assert response.status_code == 200

    body = response.get_data(as_text=True)
    assert '<button type="submit">' in body
    assert 'page_contact_heading' not in body
