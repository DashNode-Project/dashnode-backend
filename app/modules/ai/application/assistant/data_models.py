"""Shared assistant data shapes (no cross-module imports)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectRow:
    id: str
    name: str


@dataclass(frozen=True)
class ProjectSummaryData:
    name: str
    description: str
    status: str
    hu_count: int
    task_count: int
    member_count: int
    sprint_count: int
