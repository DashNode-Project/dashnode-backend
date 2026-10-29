"""Heuristics for low-quality Whisper output (silence / hallucinations)."""

from __future__ import annotations

import re

_HALLUCINATION_PATTERNS = (
    re.compile(r"amara\.org", re.IGNORECASE),
    re.compile(r"subt[ií]tulos\s+realizados", re.IGNORECASE),
    re.compile(r"thank\s+you\s+for\s+watching", re.IGNORECASE),
    re.compile(r"^\s*(\.|\u2026|…|\-)\s*$"),
    re.compile(r"^[\W\d\s]{0,12}$"),
)


def is_low_quality_transcription(text: str) -> bool:
    cleaned = text.strip()
    if len(cleaned) < 2:
        return True
    for pattern in _HALLUCINATION_PATTERNS:
        if pattern.search(cleaned):
            return True
    return False
