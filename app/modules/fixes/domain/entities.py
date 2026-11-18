"""Domain entities and value objects for EP-11 Issues and Evidences.

@sad AD-10, BR-2
@origin [User Stories HU_DN_07_97 .. HU_DN_07_101]
"""

import re
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


class AiAnalysisStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    DONE = "DONE"
    FAILED = "FAILED"


class AiProgressStage(StrEnum):
    PREPROCESSING = "PREPROCESSING"
    UPLOADING = "UPLOADING"
    ANALYZING = "ANALYZING"


class AiValidationStatus(StrEnum):
    PENDING_VALIDATION = "PENDING_VALIDATION"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"


@dataclass
class AiAnalysisResult:
    problem_description: str
    probable_cause: str
    suggested_solution: str | None
    context_sufficient: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "problem_description": self.problem_description,
            "probable_cause": self.probable_cause,
            "suggested_solution": self.suggested_solution if self.context_sufficient else None,
            "context_sufficient": self.context_sufficient,
        }


@dataclass
class AiAnalysis:
    id: str
    issue_id: str
    evidence_id: str
    requested_by: str
    status: AiAnalysisStatus
    progress_stage: AiProgressStage | None
    reuse_key: str
    prompt_version: str
    model_id: str | None
    response: AiAnalysisResult | None
    validation_status: AiValidationStatus
    created_at: datetime
    validated_by: str | None = None
    validated_at: datetime | None = None
    rejected_by: str | None = None
    rejected_at: datetime | None = None
    error_code: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None
    deleted_at: datetime | None = None
    deleted_by: str | None = None


# Guardrails & sanitization helpers for EP-12

FORBIDDEN_FIX_PATTERNS = re.compile(
    r"\b(se aplic[oó]|se corrigi[oó]|fue desplegad[oa]|he aplicado|hemos aplicado|"
    r"hemos desplegado|se solucion[oó]|queda resuelto|ha sido corregid[oa]|el fix fue aplicado|"
    r"cambio desplegado|c[oó]digo corregido y aplicado)\b",
    re.IGNORECASE,
)

SENSITIVE_PATTERNS = [
    ("token", re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]+", re.IGNORECASE)),
    ("apikey", re.compile(r"\b(AIza[0-9A-Za-z-_]{25,45}|sk-[a-zA-Z0-9]{20,})\b")),
    ("api_key_field", re.compile(r"(?i)\b(api_key|apikey)\s*[:=]\s*(\S+)")),
    ("github_token", re.compile(r"\b(ghp_[0-9A-Za-z]{30,}|github_pat_[0-9A-Za-z_]{40,})\b")),
    ("generic_token", re.compile(r"(?i)\b(token|auth_token)\s*[:=]\s*(\S+)")),
    ("password", re.compile(r"(?i)(password|passwd|pwd|secret)\s*[:=]\s*(\S+)")),
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")),
    ("card", re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
]


def count_words(text: str | None) -> int:
    if not text:
        return 0
    return len(text.strip().split())


def total_result_words(result: AiAnalysisResult) -> int:
    total = count_words(result.problem_description) + count_words(result.probable_cause)
    if result.context_sufficient and result.suggested_solution:
        total += count_words(result.suggested_solution)
    return total


def has_forbidden_fix_claims(text: str | None) -> bool:
    if not text:
        return False
    return bool(FORBIDDEN_FIX_PATTERNS.search(text))


def result_has_forbidden_fix_claims(result: AiAnalysisResult) -> bool:
    return (
        has_forbidden_fix_claims(result.problem_description)
        or has_forbidden_fix_claims(result.probable_cause)
        or has_forbidden_fix_claims(result.suggested_solution)
    )


def redact_sensitive_text(text: str) -> tuple[str, dict[str, int]]:
    redaction_counts: dict[str, int] = {}
    sanitized = text
    for name, pattern in SENSITIVE_PATTERNS:
        matches = len(pattern.findall(sanitized))
        if matches > 0:
            redaction_counts[name] = matches
            sanitized = pattern.sub(f"[REDACTED:{name.upper()}]", sanitized)
    return sanitized, redaction_counts
