import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.mark.parametrize(
    "text,lang,expected",
    [
        ("hello", "he", "שלום"),
    ],
)
def test_translate_smoke(monkeypatch, text, lang, expected):
    class FakeTranslator:
        def __init__(self, source="auto", target="he"):
            self.target = target

        def translate(self, value):
            if value == "hello" and self.target == "he":
                return "שלום"
            return value

    import services.translation as module

    monkeypatch.setattr(module, "GoogleTranslator", FakeTranslator)

    out = module.translate(text, lang)
    assert out == expected