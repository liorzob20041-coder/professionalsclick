"""Thin wrapper around deep_translator for easier testing."""

from __future__ import annotations

from deep_translator import GoogleTranslator


def translate(text: str, target_lang: str, source_lang: str = "auto") -> str:
    """Translate *text* to *target_lang* using deep_translator."""

    translator = GoogleTranslator(source=source_lang, target=target_lang)
    return translator.translate(text)


__all__ = ["GoogleTranslator", "translate"]