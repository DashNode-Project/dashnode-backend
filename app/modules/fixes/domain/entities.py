"""Domain entities and value objects for EP-11 Issues and Evidences.

@sad AD-10, BR-2
@origin [User Stories HU_DN_07_97 .. HU_DN_07_101]
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.modules.fixes.domain.messages import (
    DESCRIPTION_TOO_LONG,
    SEVERITY_REQUIRED,
    TITLE_REQUIRED,
    TITLE_TOO_LONG,
    TYPE_REQUIRED,
)


class IssueSeverity(str, Enum):
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


class IssueType(str, Enum):
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


class IssueStatus(str, Enum):
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


class EvidenceType(str, Enum):
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
