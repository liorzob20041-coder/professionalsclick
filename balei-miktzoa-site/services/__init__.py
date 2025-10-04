# -*- coding: utf-8 -*-
"""
services package – public API surface.

מטרות:
- לחשוף את generate_draft (הפרומפטים הישנים) לשימוש נקודתי.
- לחשוף את generate_worker_descriptions/describe_worker (המתאם לשלושה טונים)
  כך שכל שאר הקוד/הראוטים יייבאו מכאן ולא ישירות מהקבצים הפנימיים.
- לא להשתמש ב-ai_writer_advanced / ollama_client כברירת מחדל.
"""

from __future__ import annotations
from typing import Any, Dict, Mapping

# פרומפטים ישנים (טיוטה בסיסית אחת)
from .ai_writer import generate_draft

# המתאם החדש שמחזיר שלושה טונים (ולא תלוי ב-ollama)
from .worker_descriptions import (
    generate_worker_descriptions,
    describe_worker,
)

__all__ = [
    "generate_draft",
    "generate_worker_descriptions",
    "describe_worker",
    "get_descriptions",
    "__version__",
]

__version__ = "2025.03.0-adapter"

def get_descriptions(worker: Mapping[str, Any]) -> Dict[str, Any]:
    """
    נקודת כניסה אחת נוחה מהראוטים/שכבת השירותים:
    - מקבלת worker (dict-like)
    - מחזירה שלושה טונים + used_fields (עם cache פנימי)
    """
    return describe_worker(worker)
