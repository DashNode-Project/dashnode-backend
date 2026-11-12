"""Normalize text for fuzzy entity matching."""

from __future__ import annotations

import re
import unicodedata


def normalize_text(value: str) -> str:
    lowered = value.casefold().strip()
    decomposed = unicodedata.normalize("NFKD", lowered)
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    collapsed = re.sub(r"[^a-z0-9]+", " ", without_marks)
    return re.sub(r"\s+", " ", collapsed).strip()
