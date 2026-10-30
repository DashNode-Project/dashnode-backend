"""Shared assistant data shapes (no cross-module imports)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectRow:
    id: str
    name: str
