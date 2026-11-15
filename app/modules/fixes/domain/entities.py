"""Domain entities and value objects for EP-11 Issues and Evidences.

@sad AD-10, BR-2
@origin [User Stories HU_DN_07_97 .. HU_DN_07_101]
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.modules.fixes.domain.messages import (
    DESCRIPTION_TOO_LONG,
    RESOLUTION_NOTE_REQUIRED,
    RESOLUTION_NOTE_TOO_LONG,
    SEVERITY_REQUIRED,
    TASK_TARGET_STATUS_INVALID,
    TITLE_REQUIRED,
    TITLE_TOO_LONG,
    TYPE_REQUIRED,
)

VALID_RESTORABLE_TASK_STATUSES = frozenset(
    {"TODO", "IN_PROGRESS", "CODE_REVIEW", "TESTING", "DONE"}
)


class ConflictError(Exception):
    """Raised when an optimistic concurrency lock check fails."""


def resolve_restorable_task_status(
    requested_status: str | None,
    previous_status: str | None,
) -> str:
    """Resolve valid post-correction task status or default to IN_PROGRESS."""
    if requested_status is not None and requested_status.strip():
        candidate = requested_status.strip().upper()
        if candidate not in VALID_RESTORABLE_TASK_STATUSES:
            raise ValueError(TASK_TARGET_STATUS_INVALID)
        return candidate

    if previous_status is not None and previous_status.strip():
        prev_candidate = previous_status.strip().upper()
        if prev_candidate in VALID_RESTORABLE_TASK_STATUSES:
            return prev_candidate
    return "IN_PROGRESS"


@dataclass
class TaskSnapshot:
    id: str
    project_id: str
    name: str
    status: str
    assignee_id: str | None
    status_before_correction: str | None
    version: int = 1


class IssueSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @classmethod
    def from_string(cls, val: str | None) -> "IssueSeverity":
        if not val or not str(val).strip():
            raise ValueError(SEVERITY_REQUIRED)
        normalized = str(val).strip().lower()
        mapping = {
            "low": cls.LOW,
            "baja": cls.LOW,
            "medium": cls.MEDIUM,
            "media": cls.MEDIUM,
            "high": cls.HIGH,
            "alta": cls.HIGH,
            "critical": cls.CRITICAL,
            "crítica": cls.CRITICAL,
            "critica": cls.CRITICAL,
        }
        if normalized not in mapping:
            raise ValueError(SEVERITY_REQUIRED)
        return mapping[normalized]


class IssueType(StrEnum):
    BUG = "bug"
    REGRESSION = "regression"
    PERFORMANCE = "performance"
    SECURITY = "security"
    UX = "ux"

    @classmethod
    def from_string(cls, val: str | None) -> "IssueType":
        if not val or not str(val).strip():
            raise ValueError(TYPE_REQUIRED)
        normalized = str(val).strip().lower()
        mapping = {
            "bug": cls.BUG,
            "regression": cls.REGRESSION,
            "regresión": cls.REGRESSION,
            "regresion": cls.REGRESSION,
            "performance": cls.PERFORMANCE,
            "rendimiento": cls.PERFORMANCE,
            "security": cls.SECURITY,
            "seguridad": cls.SECURITY,
            "ux": cls.UX,
        }
        if normalized not in mapping:
            raise ValueError(TYPE_REQUIRED)
        return mapping[normalized]


class IssueStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in-progress"
    RESOLVED = "resolved"
    CLOSED = "closed"

    @classmethod
    def from_string(cls, val: str | None) -> "IssueStatus":
        if not val or not str(val).strip():
            return cls.OPEN
        normalized = str(val).strip().lower()
        mapping = {
            "open": cls.OPEN,
            "abierto": cls.OPEN,
            "in-progress": cls.IN_PROGRESS,
            "in_progress": cls.IN_PROGRESS,
            "en progreso": cls.IN_PROGRESS,
            "en corrección": cls.IN_PROGRESS,
            "en correccion": cls.IN_PROGRESS,
            "resolved": cls.RESOLVED,
            "resuelto": cls.RESOLVED,
            "closed": cls.CLOSED,
            "cerrado": cls.CLOSED,
        }
        if normalized in mapping:
            return mapping[normalized]
        return cls.OPEN


class EvidenceType(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    LOG = "log"


@dataclass
class Issue:
    id: str
    project_id: str
    title: str
    description: str | None
    severity: IssueSeverity
    type: IssueType
    status: IssueStatus
    reporter_id: str
    assignee_id: str | None
    resolution_note: str | None
    resolved_at: datetime | None
    idempotency_key: str | None
    created_at: datetime
    updated_at: datetime
    task_id: str | None = None
    resolved_by: str | None = None
    version: int = 1

    @classmethod
    def validate_title(cls, title: str | None) -> str:
        if not title or not title.strip():
            raise ValueError(TITLE_REQUIRED)
        cleaned = title.strip()
        if len(cleaned) > 100:
            raise ValueError(TITLE_TOO_LONG)
        return cleaned

    @classmethod
    def validate_description(cls, description: str | None) -> str | None:
        if description is None:
            return None
        cleaned = description.strip()
        if len(cleaned) > 5000:
            raise ValueError(DESCRIPTION_TOO_LONG)
        return cleaned if cleaned else None

    @classmethod
    def validate_resolution_note(cls, resolution_note: str | None) -> str:
        if not resolution_note or not resolution_note.strip():
            raise ValueError(RESOLUTION_NOTE_REQUIRED)
        cleaned = resolution_note.strip()
        if len(cleaned) > 2000:
            raise ValueError(RESOLUTION_NOTE_TOO_LONG)
        return cleaned


@dataclass
class Evidence:
    id: str
    fix_id: str
    project_id: str
    title: str | None
    file_name: str
    file_type: EvidenceType
    mime_type: str
    file_size: int
    storage_path: str
    sha256_hash: str
    duration_seconds: float | None
    uploaded_by: str
    created_at: datetime
