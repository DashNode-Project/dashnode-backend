"""SQLAlchemy repositories and storage adapters for EP-11 Issues and Evidences.

@sad AD-09, 5.6
@origin [User Stories HU_DN_07_97 .. HU_DN_07_101]
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

from sqlalchemy import case, func, select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.modules.fixes.domain.entities import (
    AiAnalysis,
    AiAnalysisResult,
    AiAnalysisStatus,
    AiProgressStage,
    AiValidationStatus,
    Evidence,
    EvidenceType,
    Issue,
    IssueSeverity,
    IssueStatus,
    IssueType,
)
from app.modules.fixes.domain.ports import (
    AiAnalysisRepository,
    EvidenceFileStorage,
    EvidenceRepository,
    IssueRepository,
    SignedUrlGenerator,
)
from app.modules.fixes.infrastructure.models import AiAnalysisModel, EvidenceModel, FixModel

logger = logging.getLogger(__name__)


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
        task_id=m.task_id,
        resolved_by=m.resolved_by,
        version=int(m.version) if m.version is not None else 1,
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
                task_id=issue.task_id,
                resolution_note=issue.resolution_note,
                resolved_by=issue.resolved_by,
                resolved_at=issue.resolved_at,
                idempotency_key=issue.idempotency_key,
                version=issue.version,
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
            model.task_id = issue.task_id
            model.resolution_note = issue.resolution_note
            model.resolved_by = issue.resolved_by
            model.resolved_at = issue.resolved_at
            model.version = issue.version
            model.updated_at = issue.updated_at
        self._session.flush()

    def update_with_optimistic_lock(self, issue: Issue, expected_version: int) -> bool:
        stmt = (
            update(FixModel)
            .where(FixModel.id == issue.id, FixModel.version == expected_version)
            .values(
                title=issue.title,
                description=issue.description,
                severity=issue.severity.value,
                type=issue.type.value,
                status=issue.status.value,
                assignee_id=issue.assignee_id,
                task_id=issue.task_id,
                resolution_note=issue.resolution_note,
                resolved_by=issue.resolved_by,
                resolved_at=issue.resolved_at,
                updated_at=issue.updated_at,
                version=expected_version + 1,
            )
            .execution_options(synchronize_session="fetch")
        )
        result = self._session.execute(stmt)
        self._session.flush()
        row_count = getattr(result, "rowcount", 0) or 0
        return int(row_count) == 1

    def count_other_open_issues_for_task(
        self, task_id: str, exclude_issue_id: str | None = None
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(FixModel)
            .where(
                FixModel.task_id == task_id,
                FixModel.status.in_(["open", "in-progress"]),
            )
        )
        if exclude_issue_id is not None:
            stmt = stmt.where(FixModel.id != exclude_issue_id)
        return int(self._session.scalar(stmt) or 0)

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


def _model_to_ai_analysis(m: AiAnalysisModel) -> AiAnalysis:
    res: AiAnalysisResult | None = None
    if m.response:
        try:
            data = json.loads(m.response)
            res = AiAnalysisResult(
                problem_description=data.get("problem_description", ""),
                probable_cause=data.get("probable_cause", ""),
                suggested_solution=data.get("suggested_solution"),
                context_sufficient=bool(data.get("context_sufficient", True)),
            )
        except Exception:
            res = None

    return AiAnalysis(
        id=m.id,
        issue_id=m.issue_id,
        evidence_id=m.evidence_id,
        requested_by=m.requested_by,
        status=AiAnalysisStatus(m.status),
        progress_stage=AiProgressStage(m.progress_stage) if m.progress_stage else None,
        reuse_key=m.reuse_key,
        prompt_version=m.prompt_version,
        model_id=m.model_id,
        response=res,
        validation_status=AiValidationStatus(m.validation_status),
        validated_by=m.validated_by,
        validated_at=m.validated_at,
        rejected_by=m.rejected_by,
        rejected_at=m.rejected_at,
        error_code=m.error_code,
        input_tokens=m.input_tokens,
        output_tokens=m.output_tokens,
        latency_ms=m.latency_ms,
        created_at=m.created_at,
        deleted_at=m.deleted_at,
        deleted_by=m.deleted_by,
    )


class SqlAlchemyAiAnalysisRepository(AiAnalysisRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, analysis: AiAnalysis) -> None:
        m = self._session.get(AiAnalysisModel, analysis.id)
        raw_response = json.dumps(analysis.response.to_dict()) if analysis.response else None
        if m is None:
            m = AiAnalysisModel(
                id=analysis.id,
                issue_id=analysis.issue_id,
                evidence_id=analysis.evidence_id,
                requested_by=analysis.requested_by,
                status=analysis.status.value,
                progress_stage=analysis.progress_stage.value if analysis.progress_stage else None,
                reuse_key=analysis.reuse_key,
                prompt_version=analysis.prompt_version,
                model_id=analysis.model_id,
                response=raw_response,
                validation_status=analysis.validation_status.value,
                validated_by=analysis.validated_by,
                validated_at=analysis.validated_at,
                rejected_by=analysis.rejected_by,
                rejected_at=analysis.rejected_at,
                error_code=analysis.error_code,
                input_tokens=analysis.input_tokens,
                output_tokens=analysis.output_tokens,
                latency_ms=analysis.latency_ms,
                created_at=analysis.created_at,
                deleted_at=analysis.deleted_at,
                deleted_by=analysis.deleted_by,
            )
            self._session.add(m)
        else:
            m.status = analysis.status.value
            m.progress_stage = analysis.progress_stage.value if analysis.progress_stage else None
            m.response = raw_response
            m.model_id = analysis.model_id
            m.error_code = analysis.error_code
            m.input_tokens = analysis.input_tokens
            m.output_tokens = analysis.output_tokens
            m.latency_ms = analysis.latency_ms
            m.validation_status = analysis.validation_status.value
            m.validated_by = analysis.validated_by
            m.validated_at = analysis.validated_at
            m.rejected_by = analysis.rejected_by
            m.rejected_at = analysis.rejected_at
            m.deleted_at = analysis.deleted_at
            m.deleted_by = analysis.deleted_by

    def get_by_id(self, analysis_id: str) -> AiAnalysis | None:
        m = self._session.get(AiAnalysisModel, analysis_id)
        if m is None or m.deleted_at is not None:
            return None
        return _model_to_ai_analysis(m)

    def find_active_by_reuse_key(self, reuse_key: str) -> AiAnalysis | None:
        stmt = (
            select(AiAnalysisModel)
            .where(
                AiAnalysisModel.reuse_key == reuse_key,
                AiAnalysisModel.status == AiAnalysisStatus.DONE.value,
                AiAnalysisModel.deleted_at.is_(None),
            )
            .order_by(AiAnalysisModel.created_at.desc())
            .limit(1)
        )
        m = self._session.execute(stmt).scalar_one_or_none()
        return _model_to_ai_analysis(m) if m else None

    def list_by_issue(
        self, issue_id: str, limit: int = 20, cursor: str | None = None
    ) -> tuple[list[AiAnalysis], str | None]:
        stmt = select(AiAnalysisModel).where(
            AiAnalysisModel.issue_id == issue_id,
            AiAnalysisModel.deleted_at.is_(None),
        )
        if cursor:
            try:
                dt_cursor = datetime.fromisoformat(cursor)
                stmt = stmt.where(AiAnalysisModel.created_at < dt_cursor)
            except (ValueError, TypeError):
                logger.warning("Invalid cursor format for ai analysis list: %s", cursor)
        stmt = stmt.order_by(AiAnalysisModel.created_at.desc()).limit(limit + 1)
        rows = list(self._session.execute(stmt).scalars().all())
        has_next = len(rows) > limit
        items = rows[:limit]
        next_cursor = items[-1].created_at.isoformat() if has_next and items else None
        return [_model_to_ai_analysis(r) for r in items], next_cursor

    def soft_delete(self, analysis_id: str, actor_id: str, deleted_at: datetime) -> bool:
        m = self._session.get(AiAnalysisModel, analysis_id)
        if m is None or m.deleted_at is not None:
            return False
        m.deleted_at = deleted_at
        m.deleted_by = actor_id
        return True
