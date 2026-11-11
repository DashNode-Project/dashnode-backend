"""Application use cases for EP-11 Issues and Evidences.

@sad AD-09, AD-10
@origin [User Stories HU_DN_07_97 .. HU_DN_07_101]
"""

from app.modules.fixes.application.dtos import (
    CreateIssueCommand,
    EvidenceDTO,
    EvidenceOperationResponse,
    IssueDetailDTO,
    IssueDTO,
    IssueListResponse,
    IssueOperationResponse,
)
from app.modules.fixes.application.file_validation import (
    validate_and_sanitize_evidence_file,
)
from app.modules.fixes.domain.entities import (
    Evidence,
    Issue,
    IssueSeverity,
    IssueStatus,
    IssueType,
)
from app.modules.fixes.domain.messages import (
    DUPLICATE_EVIDENCE,
    EVIDENCE_ATTACHED,
    EVIDENCE_NOT_FOUND,
    EVIDENCE_TITLE_TOO_LONG,
    ISSUE_CREATED,
    ISSUE_NOT_FOUND,
    NOT_MEMBER_ERROR,
    SIGNATURE_INVALID_OR_EXPIRED,
)
from app.modules.fixes.domain.ports import (
    EvidenceFileStorage,
    EvidenceRepository,
    IssueNotificationPort,
    IssueRepository,
    ProjectLookupPort,
    SignedUrlGenerator,
    UserDisplayLookupPort,
)
from app.shared.application.identity import CurrentUser
from app.shared.application.ports import Clock, IdGenerator, UnitOfWork


class CreateIssueUseCase:
    def __init__(
        self,
        repo: IssueRepository,
        uow: UnitOfWork,
        id_gen: IdGenerator,
        clock: Clock,
        projects: ProjectLookupPort,
        users: UserDisplayLookupPort,
        notification_sender: IssueNotificationPort | None = None,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._id_gen = id_gen
        self._clock = clock
        self._projects = projects
        self._users = users
        self._notifications = notification_sender

    def execute(
        self,
        project_id: str,
        cmd: CreateIssueCommand,
        actor: CurrentUser,
    ) -> IssueOperationResponse:
        if not self._projects.is_active_member(project_id, actor.id):
            raise PermissionError(NOT_MEMBER_ERROR)

        # Idempotency check
        if cmd.idempotency_key:
            existing = self._repo.get_by_idempotency_key(project_id, cmd.idempotency_key)
            if existing is not None:
                reporter_display = self._users.get_user_display(existing.reporter_id)
                reporter_name = reporter_display[0] if reporter_display else "Usuario"
                assignee_name = None
                if existing.assignee_id:
                    assignee_display = self._users.get_user_display(existing.assignee_id)
                    assignee_name = assignee_display[0] if assignee_display else None
                dto = IssueDTO(
                    id=existing.id,
                    project_id=existing.project_id,
                    title=existing.title,
                    description=existing.description,
                    severity=existing.severity.value,
                    type=existing.type.value,
                    status=existing.status.value,
                    reporter_id=existing.reporter_id,
                    reporter_name=reporter_name,
                    assignee_id=existing.assignee_id,
                    assignee_name=assignee_name,
                    resolution_note=existing.resolution_note,
                    resolved_at=existing.resolved_at.isoformat() if existing.resolved_at else None,
                    created_at=existing.created_at.isoformat(),
                    updated_at=existing.updated_at.isoformat(),
                    evidences_count=0,
                )
                return IssueOperationResponse(message=ISSUE_CREATED, issue=dto)

        # Domain validations
        clean_title = Issue.validate_title(cmd.title)
        clean_desc = Issue.validate_description(cmd.description)
        severity = IssueSeverity.from_string(cmd.severity)
        issue_type = IssueType.from_string(cmd.type)

        now = self._clock.now()
        issue = Issue(
            id=self._id_gen.generate(),
            project_id=project_id,
            title=clean_title,
            description=clean_desc,
            severity=severity,
            type=issue_type,
            status=IssueStatus.OPEN,
            reporter_id=actor.id,
            assignee_id=None,
            resolution_note=None,
            resolved_at=None,
            idempotency_key=cmd.idempotency_key,
            created_at=now,
            updated_at=now,
        )

        with self._uow:
            self._repo.save(issue)
            self._uow.commit()

        if self._notifications is not None:
            self._notifications.notify_issue_created(
                project_id=project_id,
                issue_id=issue.id,
                title=issue.title,
                reporter_id=actor.id,
            )

        reporter_display = self._users.get_user_display(actor.id)
        reporter_name = reporter_display[0] if reporter_display else actor.email

        dto = IssueDTO(
            id=issue.id,
            project_id=issue.project_id,
            title=issue.title,
            description=issue.description,
            severity=issue.severity.value,
            type=issue.type.value,
            status=issue.status.value,
            reporter_id=issue.reporter_id,
            reporter_name=reporter_name,
            assignee_id=None,
            assignee_name=None,
            resolution_note=None,
            resolved_at=None,
            created_at=issue.created_at.isoformat(),
            updated_at=issue.updated_at.isoformat(),
            evidences_count=0,
        )
        return IssueOperationResponse(message=ISSUE_CREATED, issue=dto)


class ListIssuesUseCase:
    def __init__(
        self,
        repo: IssueRepository,
        projects: ProjectLookupPort,
        users: UserDisplayLookupPort,
    ) -> None:
        self._repo = repo
        self._projects = projects
        self._users = users

    def execute(
        self,
        project_id: str,
        actor: CurrentUser,
        status: str | None = None,
        severity: str | None = None,
        issue_type: str | None = None,
        cursor: str | None = None,
        limit: int = 25,
    ) -> IssueListResponse:
        if not self._projects.is_active_member(project_id, actor.id):
            raise PermissionError(NOT_MEMBER_ERROR)

        status_enum = None
        if status and status.strip().lower() not in ("all", "todos"):
            status_enum = IssueStatus.from_string(status)

        severity_enum = None
        if severity and severity.strip().lower() not in ("all", "todas", "todos"):
            severity_enum = IssueSeverity.from_string(severity)

        type_enum = None
        if issue_type and issue_type.strip().lower() not in ("all", "todos", "todas"):
            type_enum = IssueType.from_string(issue_type)

        issues, next_cursor, total = self._repo.list_by_project(
            project_id=project_id,
            status=status_enum,
            severity=severity_enum,
            issue_type=type_enum,
            cursor=cursor,
            limit=limit,
        )

        issue_ids = [i.id for i in issues]
        ev_counts = self._repo.count_evidences_for_issues(issue_ids) if issue_ids else {}

        items: list[IssueDTO] = []
        for iss in issues:
            rep_disp = self._users.get_user_display(iss.reporter_id)
            rep_name = rep_disp[0] if rep_disp else "Usuario"
            asg_name = None
            if iss.assignee_id:
                asg_disp = self._users.get_user_display(iss.assignee_id)
                asg_name = asg_disp[0] if asg_disp else None

            items.append(
                IssueDTO(
                    id=iss.id,
                    project_id=iss.project_id,
                    title=iss.title,
                    description=iss.description,
                    severity=iss.severity.value,
                    type=iss.type.value,
                    status=iss.status.value,
                    reporter_id=iss.reporter_id,
                    reporter_name=rep_name,
                    assignee_id=iss.assignee_id,
                    assignee_name=asg_name,
                    resolution_note=iss.resolution_note,
                    resolved_at=iss.resolved_at.isoformat() if iss.resolved_at else None,
                    created_at=iss.created_at.isoformat(),
                    updated_at=iss.updated_at.isoformat(),
                    evidences_count=ev_counts.get(iss.id, 0),
                )
            )

        return IssueListResponse(items=items, next_cursor=next_cursor, total=total)


class GetIssueDetailUseCase:
    def __init__(
        self,
        issue_repo: IssueRepository,
        evidence_repo: EvidenceRepository,
        signed_url_gen: SignedUrlGenerator,
        projects: ProjectLookupPort,
        users: UserDisplayLookupPort,
    ) -> None:
        self._issue_repo = issue_repo
        self._evidence_repo = evidence_repo
        self._signed_url_gen = signed_url_gen
        self._projects = projects
        self._users = users

    def execute(
        self,
        project_id: str,
        issue_id: str,
        actor: CurrentUser,
    ) -> IssueDetailDTO:
        if not self._projects.is_active_member(project_id, actor.id):
            raise PermissionError(NOT_MEMBER_ERROR)

        issue = self._issue_repo.get_by_id(issue_id)
        if issue is None or issue.project_id != project_id:
            raise LookupError(ISSUE_NOT_FOUND)

        rep_disp = self._users.get_user_display(issue.reporter_id)
        rep_name = rep_disp[0] if rep_disp else "Usuario"
        asg_name = None
        if issue.assignee_id:
            asg_disp = self._users.get_user_display(issue.assignee_id)
            asg_name = asg_disp[0] if asg_disp else None

        evidences = self._evidence_repo.list_by_issue(issue.id)
        ev_dtos: list[EvidenceDTO] = []
        for ev in evidences:
            url = self._signed_url_gen.generate(
                project_id=project_id,
                issue_id=issue.id,
                evidence_id=ev.id,
                expires_in_seconds=300,
            )
            up_disp = self._users.get_user_display(ev.uploaded_by)
            up_name = up_disp[0] if up_disp else "Usuario"
            ev_dtos.append(
                EvidenceDTO(
                    id=ev.id,
                    fix_id=ev.fix_id,
                    title=ev.title,
                    file_name=ev.file_name,
                    file_type=ev.file_type.value,
                    mime_type=ev.mime_type,
                    file_size=ev.file_size,
                    download_url=url,
                    thumbnail_url=url if ev.file_type.value in ("image", "video") else None,
                    duration_seconds=ev.duration_seconds,
                    uploaded_by=ev.uploaded_by,
                    uploaded_by_name=up_name,
                    created_at=ev.created_at.isoformat(),
                )
            )

        return IssueDetailDTO(
            id=issue.id,
            project_id=issue.project_id,
            title=issue.title,
            description=issue.description,
            severity=issue.severity.value,
            type=issue.type.value,
            status=issue.status.value,
            reporter_id=issue.reporter_id,
            reporter_name=rep_name,
            assignee_id=issue.assignee_id,
            assignee_name=asg_name,
            resolution_note=issue.resolution_note,
            resolved_at=issue.resolved_at.isoformat() if issue.resolved_at else None,
            created_at=issue.created_at.isoformat(),
            updated_at=issue.updated_at.isoformat(),
            evidences_count=len(ev_dtos),
            evidences=ev_dtos,
            ai_analyses=[],
        )


class AttachEvidenceUseCase:
    def __init__(
        self,
        issue_repo: IssueRepository,
        evidence_repo: EvidenceRepository,
        storage: EvidenceFileStorage,
        signed_url_gen: SignedUrlGenerator,
        uow: UnitOfWork,
        id_gen: IdGenerator,
        clock: Clock,
        projects: ProjectLookupPort,
        users: UserDisplayLookupPort,
    ) -> None:
        self._issue_repo = issue_repo
        self._evidence_repo = evidence_repo
        self._storage = storage
        self._signed_url_gen = signed_url_gen
        self._uow = uow
        self._id_gen = id_gen
        self._clock = clock
        self._projects = projects
        self._users = users

    def execute(
        self,
        project_id: str,
        issue_id: str,
        file_name: str,
        raw_data: bytes,
        title: str | None,
        actor: CurrentUser,
    ) -> EvidenceOperationResponse:
        if not self._projects.is_active_member(project_id, actor.id):
            raise PermissionError(NOT_MEMBER_ERROR)

        issue = self._issue_repo.get_by_id(issue_id)
        if issue is None or issue.project_id != project_id:
            raise LookupError(ISSUE_NOT_FOUND)

        clean_title = None
        if title is not None and title.strip():
            if len(title.strip()) > 255:
                raise ValueError(EVIDENCE_TITLE_TOO_LONG)
            clean_title = title.strip()

        # Strict validation & EXIF stripping
        validated = validate_and_sanitize_evidence_file(file_name, raw_data)

        # Check duplicate hash
        existing_duplicate = self._evidence_repo.find_by_fix_and_hash(
            fix_id=issue_id,
            sha256_hash=validated.sha256_hash,
        )
        if existing_duplicate is not None:
            raise ValueError(DUPLICATE_EVIDENCE)

        evidence_id = self._id_gen.generate()
        now = self._clock.now()

        # Save to private storage with UUID filename
        storage_path = self._storage.save_file(
            file_id=evidence_id,
            data=validated.sanitized_bytes,
            extension=validated.extension,
        )

        evidence = Evidence(
            id=evidence_id,
            fix_id=issue_id,
            project_id=project_id,
            title=clean_title,
            file_name=file_name,
            file_type=validated.file_type,
            mime_type=validated.mime_type,
            file_size=len(validated.sanitized_bytes),
            storage_path=storage_path,
            sha256_hash=validated.sha256_hash,
            duration_seconds=validated.duration_seconds,
            uploaded_by=actor.id,
            created_at=now,
        )

        try:
            with self._uow:
                self._evidence_repo.save(evidence)
                self._uow.commit()
        except Exception:
            # Ensure no partial/orphaned files remain on disk if persistence fails
            self._storage.delete_file(storage_path)
            raise

        url = self._signed_url_gen.generate(
            project_id=project_id,
            issue_id=issue_id,
            evidence_id=evidence.id,
            expires_in_seconds=300,
        )
        up_disp = self._users.get_user_display(actor.id)
        up_name = up_disp[0] if up_disp else actor.email

        dto = EvidenceDTO(
            id=evidence.id,
            fix_id=evidence.fix_id,
            title=evidence.title,
            file_name=evidence.file_name,
            file_type=evidence.file_type.value,
            mime_type=evidence.mime_type,
            file_size=evidence.file_size,
            download_url=url,
            thumbnail_url=url if evidence.file_type.value in ("image", "video") else None,
            duration_seconds=evidence.duration_seconds,
            uploaded_by=evidence.uploaded_by,
            uploaded_by_name=up_name,
            created_at=evidence.created_at.isoformat(),
        )
        return EvidenceOperationResponse(message=EVIDENCE_ATTACHED, evidence=dto)


class DownloadEvidenceUseCase:
    def __init__(
        self,
        evidence_repo: EvidenceRepository,
        storage: EvidenceFileStorage,
        signed_url_gen: SignedUrlGenerator,
        clock: Clock,
    ) -> None:
        self._evidence_repo = evidence_repo
        self._storage = storage
        self._signed_url_gen = signed_url_gen
        self._clock = clock

    def execute(
        self,
        evidence_id: str,
        expires: int,
        signature: str,
    ) -> tuple[bytes, str, str]:
        current_ts = int(self._clock.now().timestamp())
        if current_ts > expires:
            raise PermissionError(SIGNATURE_INVALID_OR_EXPIRED)

        if not self._signed_url_gen.verify(evidence_id, expires, signature):
            raise PermissionError(SIGNATURE_INVALID_OR_EXPIRED)

        evidence = self._evidence_repo.get_by_id(evidence_id)
        if evidence is None:
            raise LookupError(EVIDENCE_NOT_FOUND)

        data = self._storage.read_file(evidence.storage_path)
        return data, evidence.mime_type, evidence.file_name
