"""Heuristics for low-quality Whisper output (silence / hallucinations)."""

from __future__ import annotations

import re

_HALLUCINATION_PATTERNS = (
    re.compile(r"amara\.org", re.IGNORECASE),
    re.compile(r"subt[ií]tulos\s+realizados", re.IGNORECASE),
    re.compile(r"thank\s+you\s+for\s+watching", re.IGNORECASE),
    re.compile(r"^\s*(\.|\u2026|…|\-)\s*$"),
    re.compile(r"^[\W\d\s]{0,12}$"),
    re.compile(r"paz.*justicia|justicia.*paz", re.IGNORECASE),
    re.compile(r"gracias,?\s*para\s*ti", re.IGNORECASE),
    re.compile(r"^s[ií]\.?\s*gracias", re.IGNORECASE),
)

_REPEATED_PHRASE = re.compile(r"(.+?)(?:\s+\1){2,}", re.IGNORECASE)


def is_low_quality_transcription(text: str) -> bool:
    cleaned = text.strip()
    if len(cleaned) < 2:
        return True
    for pattern in _HALLUCINATION_PATTERNS:
        if pattern.search(cleaned):
            return True
    if _REPEATED_PHRASE.search(cleaned):
        return True
    tokens = re.findall(r"[a-záéíóúñ]+", cleaned.lower())
    return bool(len(tokens) >= 6 and len(set(tokens)) <= 3)
