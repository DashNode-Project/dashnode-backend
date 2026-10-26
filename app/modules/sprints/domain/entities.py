"""Sprint domain entities (EP-07)."""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum


class SprintStatus(StrEnum):
    PLANNING = "PLANNING"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


@dataclass
class Sprint:
    id: str
    project_id: str
    name: str
    goal: str | None
    start_date: date
    end_date: date
    status: SprintStatus
    created_at: datetime
    closed_at: datetime | None = None
