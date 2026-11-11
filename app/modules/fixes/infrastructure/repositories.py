"""SQLAlchemy repositories and storage adapters for EP-11 Issues and Evidences.

@sad AD-09, 5.6
@origin [User Stories HU_DN_07_97 .. HU_DN_07_101]
"""

import base64
import hashlib
import hmac
import os
import time
from pathlib import Path

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.modules.fixes.domain.entities import (
    Evidence,
    EvidenceType,
    Issue,
    IssueSeverity,
    IssueStatus,
    IssueType,
)
from app.modules.fixes.domain.ports import (
    EvidenceFileStorage,
    EvidenceRepository,
    IssueRepository,
    SignedUrlGenerator,
)
from app.modules.fixes.infrastructure.models import EvidenceModel, FixModel


def _model_to_issue(m: FixModel) -> Issue:
    return Issue(
        id=m.id,
        project_id=m.project_id,
        title=m.title,
        description=m.description,
        severity=IssueSeverity(m.severity),
        type=IssueType(m.type),
        status=IssueStatus(m.status),
        reporter_id=m.reporter_id,
        assignee_id=m.assignee_id,
        resolution_note=m.resolution_note,
        resolved_at=m.resolved_at,
        idempotency_key=m.idempotency_key,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _model_to_evidence(m: EvidenceModel) -> Evidence:
    return Evidence(
        id=m.id,
        fix_id=m.fix_id,
        project_id=m.project_id,
        title=m.title,
        file_name=m.file_name,
        file_type=EvidenceType(m.file_type),
        mime_type=m.mime_type,
        file_size=m.file_size,
        storage_path=m.storage_path,
        sha256_hash=m.sha256_hash,
        duration_seconds=m.duration_seconds,
        uploaded_by=m.uploaded_by,
        created_at=m.created_at,
    )


class SqlAlchemyFixRepository(IssueRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, issue: Issue) -> None:
        model = self._session.get(FixModel, issue.id)
        if model is None:
            model = FixModel(
                id=issue.id,
                project_id=issue.project_id,
                title=issue.title,
                description=issue.description,
                severity=issue.severity.value,
                type=issue.type.value,
                status=issue.status.value,
                reporter_id=issue.reporter_id,
                assignee_id=issue.assignee_id,
                resolution_note=issue.resolution_note,
                resolved_at=issue.resolved_at,
                idempotency_key=issue.idempotency_key,
                created_at=issue.created_at,
                updated_at=issue.updated_at,
            )
            self._session.add(model)
        else:
            model.title = issue.title
            model.description = issue.description
            model.severity = issue.severity.value
            model.type = issue.type.value
            model.status = issue.status.value
            model.assignee_id = issue.assignee_id
            model.resolution_note = issue.resolution_note
            model.resolved_at = issue.resolved_at
            model.updated_at = issue.updated_at

    def get_by_id(self, issue_id: str) -> Issue | None:
        m = self._session.get(FixModel, issue_id)
        return _model_to_issue(m) if m else None

    def get_by_idempotency_key(self, project_id: str, key: str) -> Issue | None:
        stmt = select(FixModel).where(
            FixModel.project_id == project_id,
            FixModel.idempotency_key == key,
        )
        m = self._session.scalars(stmt).first()
        return _model_to_issue(m) if m else None

    def list_by_project(
        self,
        project_id: str,
        status: IssueStatus | None = None,
        severity: IssueSeverity | None = None,
        issue_type: IssueType | None = None,
        cursor: str | None = None,
        limit: int = 25,
    ) -> tuple[list[Issue], str | None, int]:
        stmt = select(FixModel).where(FixModel.project_id == project_id)

        if status is not None:
            stmt = stmt.where(FixModel.status == status.value)
        if severity is not None:
            stmt = stmt.where(FixModel.severity == severity.value)
        if issue_type is not None:
            stmt = stmt.where(FixModel.type == issue_type.value)

        # Count total matches
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self._session.scalar(count_stmt) or 0

        # Default ordering:
        # 1. Open first: 'open', 'in-progress' -> 0, other -> 1
        # 2. Severity: critical -> 0, high -> 1, medium -> 2, low -> 3
        # 3. Created date: newest first
        # 4. ID desc
        status_rank = case(
            (FixModel.status.in_(["open", "in-progress"]), 0),
            else_=1,
        )
        severity_rank = case(
            (FixModel.severity == "critical", 0),
            (FixModel.severity == "high", 1),
            (FixModel.severity == "medium", 2),
            else_=3,
        )

        stmt = stmt.order_by(
            status_rank.asc(),
            severity_rank.asc(),
            FixModel.created_at.desc(),
            FixModel.id.desc(),
        )

        # Decode cursor (offset-based)
        offset = 0
        if cursor:
            try:
                decoded = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
                offset = max(0, int(decoded))
            except Exception:
                offset = 0

        stmt = stmt.offset(offset).limit(limit)
        models = self._session.scalars(stmt).all()
        issues = [_model_to_issue(m) for m in models]

        next_cursor = None
        if offset + len(issues) < total:
            next_cursor = base64.urlsafe_b64encode(str(offset + limit).encode("utf-8")).decode(
                "ascii"
            )

        return issues, next_cursor, total

    def count_evidences_for_issues(self, issue_ids: list[str]) -> dict[str, int]:
        if not issue_ids:
            return {}
        stmt = (
            select(EvidenceModel.fix_id, func.count(EvidenceModel.id))
            .where(EvidenceModel.fix_id.in_(issue_ids))
            .group_by(EvidenceModel.fix_id)
        )
        rows = self._session.execute(stmt).all()
        return {fix_id: count for fix_id, count in rows}


class SqlAlchemyEvidenceRepository(EvidenceRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, evidence: Evidence) -> None:
        m = self._session.get(EvidenceModel, evidence.id)
        if m is None:
            m = EvidenceModel(
                id=evidence.id,
                fix_id=evidence.fix_id,
                project_id=evidence.project_id,
                title=evidence.title,
                file_name=evidence.file_name,
                file_type=evidence.file_type.value,
                mime_type=evidence.mime_type,
                file_size=evidence.file_size,
                storage_path=evidence.storage_path,
                sha256_hash=evidence.sha256_hash,
                duration_seconds=evidence.duration_seconds,
                uploaded_by=evidence.uploaded_by,
                created_at=evidence.created_at,
            )
            self._session.add(m)
        else:
            m.title = evidence.title
            m.file_name = evidence.file_name
            m.file_size = evidence.file_size
            m.sha256_hash = evidence.sha256_hash

    def get_by_id(self, evidence_id: str) -> Evidence | None:
        m = self._session.get(EvidenceModel, evidence_id)
        return _model_to_evidence(m) if m else None

    def list_by_issue(self, issue_id: str) -> list[Evidence]:
        stmt = (
            select(EvidenceModel)
            .where(EvidenceModel.fix_id == issue_id)
            .order_by(EvidenceModel.created_at.asc())
        )
        return [_model_to_evidence(m) for m in self._session.scalars(stmt).all()]

    def find_by_fix_and_hash(
        self,
        fix_id: str | None = None,
        sha256_hash: str = "",
        *,
        issue_id: str | None = None,
    ) -> Evidence | None:
        target_id = fix_id or issue_id or ""
        stmt = select(EvidenceModel).where(
            EvidenceModel.fix_id == target_id,
            EvidenceModel.sha256_hash == sha256_hash,
        )
        m = self._session.scalars(stmt).first()
        return _model_to_evidence(m) if m else None

    def delete(self, evidence_id: str) -> None:
        m = self._session.get(EvidenceModel, evidence_id)
        if m is not None:
            self._session.delete(m)


class LocalEvidenceFileStorage(EvidenceFileStorage):
    """Secure private file storage storing files with UUID filenames."""

    def __init__(self, base_dir: Path | None = None) -> None:
        if base_dir is None:
            self._base_dir = (
                Path(__file__).resolve().parent.parent.parent.parent.parent
                / "uploads"
                / "evidences"
            )
        else:
            self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def save_file(self, file_id: str, data: bytes, extension: str) -> str:
        safe_ext = extension if extension.startswith(".") else f".{extension}"
        target_path = self._base_dir / f"{file_id}{safe_ext}"
        target_path.write_bytes(data)
        return str(target_path)

    def read_file(self, storage_path: str) -> bytes:
        p = Path(storage_path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {storage_path}")
        return p.read_bytes()

    def delete_file(self, storage_path: str) -> None:
        p = Path(storage_path)
        if p.exists():
            p.unlink()


class HmacSignedUrlGenerator(SignedUrlGenerator):
    """Generates and validates HMAC-SHA256 signed URLs with 5-minute expiry."""

    def __init__(self, secret_key: str | None = None) -> None:
        if secret_key:
            raw = secret_key
        elif hasattr(settings, "SECRET_KEY"):
            val = settings.SECRET_KEY
            raw = val.get_secret_value() if hasattr(val, "get_secret_value") else str(val)
        else:
            raw = os.environ.get("SECRET_KEY", "insecure-dev-secret-key-ep11")
        self._secret = raw.encode("utf-8")

    def generate(
        self,
        project_id: str,
        issue_id: str,
        evidence_id: str,
        expires_in_seconds: int = 300,
    ) -> str:
        expires = int(time.time()) + expires_in_seconds
        msg = f"{evidence_id}:{expires}".encode()
        sig = hmac.new(self._secret, msg, hashlib.sha256).hexdigest()
        return (
            f"/api/v1/projects/{project_id}/issues/{issue_id}/evidences/{evidence_id}/content"
            f"?signature={sig}&expires={expires}"
        )

    def verify(
        self,
        evidence_id: str,
        expires_timestamp: int,
        signature: str,
    ) -> bool:
        msg = f"{evidence_id}:{expires_timestamp}".encode()
        expected = hmac.new(self._secret, msg, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)
