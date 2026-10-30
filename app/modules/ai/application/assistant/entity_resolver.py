"""Fuzzy resolution of project and sprint names within authorized scope."""

from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from app.config import settings
from app.modules.ai.application.assistant.text_normalize import normalize_text


@dataclass(frozen=True)
class ProjectCandidate:
    id: str
    name: str


@dataclass(frozen=True)
class SprintCandidate:
    id: str
    name: str
    project_id: str


@dataclass
class ResolveResult[T]:
    value: T | None
    ambiguous: list[T]
    score: int


def resolve_project(
    ref: str | None,
    candidates: list[ProjectCandidate],
    *,
    threshold: int | None = None,
) -> ResolveResult[ProjectCandidate]:
    limit = threshold or settings.AI_FUZZY_MATCH_THRESHOLD
    if not candidates:
        return ResolveResult(None, [], 0)
    if not ref or not ref.strip():
        return ResolveResult(None, [], 0)
    needle = normalize_text(ref)
    scored = [
        (
            item,
            max(
                fuzz.token_set_ratio(needle, normalize_text(item.name)),
                fuzz.partial_ratio(needle, normalize_text(item.name)),
            ),
        )
        for item in candidates
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    best_item, best_score = scored[0]
    if best_score < limit:
        return ResolveResult(None, [], best_score)
    close = [item for item, score in scored if score >= limit and score >= best_score - 3]
    if len(close) > 1:
        return ResolveResult(None, close, best_score)
    return ResolveResult(best_item, [], best_score)


def find_project_name_in_utterance(
    text: str,
    candidates: list[ProjectCandidate],
    *,
    threshold: int | None = None,
) -> ResolveResult[ProjectCandidate]:
    """Locate an authorized project name embedded in free-form user text."""
    limit = threshold or settings.AI_FUZZY_MATCH_THRESHOLD
    if not text.strip() or not candidates:
        return ResolveResult(None, [], 0)
    haystack = normalize_text(text)
    scored: list[tuple[ProjectCandidate, int]] = []
    for item in sorted(candidates, key=lambda c: len(c.name), reverse=True):
        needle = normalize_text(item.name)
        if not needle:
            continue
        score = 0
        if needle == haystack or re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", haystack):
            score = 100
        else:
            score = max(
                fuzz.partial_ratio(needle, haystack),
                fuzz.token_set_ratio(needle, haystack),
            )
        scored.append((item, score))
    if not scored:
        return ResolveResult(None, [], 0)
    scored.sort(key=lambda pair: pair[1], reverse=True)
    best_item, best_score = scored[0]
    if best_score < limit:
        return ResolveResult(None, [], best_score)
    close = [item for item, score in scored if score >= limit and score >= best_score - 3]
    if len(close) > 1:
        return ResolveResult(None, close, best_score)
    return ResolveResult(best_item, [], best_score)


def resolve_sprint_by_ref(
    ref: str | None,
    candidates: list[SprintCandidate],
) -> ResolveResult[SprintCandidate]:
    if not ref or not candidates:
        return ResolveResult(None, [], 0)
    ref_norm = normalize_text(ref)
    if ref_norm.isdigit():
        matches = [
            sprint
            for sprint in candidates
            if ref_norm in normalize_text(sprint.name)
            or normalize_text(sprint.name).endswith(ref_norm)
        ]
        if len(matches) == 1:
            return ResolveResult(matches[0], [], 100)
        if len(matches) > 1:
            return ResolveResult(None, matches, 100)
    scored = [
        (sprint, fuzz.token_set_ratio(ref_norm, normalize_text(sprint.name)))
        for sprint in candidates
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    best, score = scored[0]
    if score < settings.AI_FUZZY_MATCH_THRESHOLD:
        return ResolveResult(None, [], score)
    close = [
        sprint
        for sprint, sprint_score in scored
        if sprint_score >= score - 3 and sprint_score >= settings.AI_FUZZY_MATCH_THRESHOLD
    ]
    if len(close) > 1:
        return ResolveResult(None, close, score)
    return ResolveResult(best, [], score)
