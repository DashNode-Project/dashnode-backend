"""Application use cases for EP-11 Issues and Evidences.

@sad AD-09, AD-10
@origin [User Stories HU_DN_07_97 .. HU_DN_07_105]
"""

from datetime import datetime

from app.modules.fixes.application.dtos import (
    AssignIssueCommand,
    CloseIssueCommand,
    CreateIssueCommand,
    EvidenceDTO,
    EvidenceOperationResponse,
    IssueDetailDTO,
    IssueDTO,
    IssueListResponse,
    IssueOperationResponse,
    ReportTaskFixCommand,
    ResolveIssueCommand,
)
from app.modules.fixes.application.file_validation import (
    validate_and_sanitize_evidence_file,
)
from app.modules.fixes.domain.entities import (
    ConflictError,
    Evidence,
    Issue,
    IssueSeverity,
    IssueStatus,
    IssueType,
    TaskSnapshot,
    resolve_restorable_task_status,
)
from app.modules.fixes.domain.messages import (
    ASSIGN_DEVELOPER_ONLY,
    ASSIGN_FORBIDDEN,
    CLOSE_FORBIDDEN,
    DUPLICATE_EVIDENCE,
    EVIDENCE_ATTACHED,
    EVIDENCE_NOT_FOUND,
    EVIDENCE_TITLE_TOO_LONG,
    FIX_REPORT_OWN_TASKS_ONLY,
    ISSUE_ASSIGNED,
    ISSUE_CLOSED,
    ISSUE_CREATED,
    ISSUE_NOT_FOUND,
    ISSUE_NOT_OPEN,
    ISSUE_NOT_RESOLVED,
    ISSUE_RESOLVED,
    NOT_MEMBER_ERROR,
    OPTIMISTIC_LOCK_CONFLICT,
    SIGNATURE_INVALID_OR_EXPIRED,
    TASK_FIX_REPORTED,
    TASK_NOT_FOUND,
    TASK_UNLINKED_AND_UPDATED,
)
from app.modules.fixes.domain.ports import (
    EvidenceFileStorage,
    EvidenceRepository,
    FixTaskCoordinatorPort,
    IssueNotificationPort,
    IssueRepository,
    OutboxPort,
    ProjectLookupPort,
    SignedUrlGenerator,
    UserDisplayLookupPort,
)
from app.shared.application.identity import CurrentUser
from app.shared.application.ports import Clock, IdGenerator, UnitOfWork


def _resolve_user_name(
    users: UserDisplayLookupPort, user_id: str | None, fallback: str | None = None
) -> str | None:
    if not user_id:
        return None
    disp = users.get_user_display(user_id)
    return disp[0] if disp else fallback


def _build_issue_dto(
    issue: Issue,
    users: UserDisplayLookupPort,
    *,
    evidences_count: int = 0,
    task_snapshot: TaskSnapshot | None = None,
) -> IssueDTO:
    reporter_name = _resolve_user_name(users, issue.reporter_id, "Usuario") or "Usuario"
    assignee_name = _resolve_user_name(users, issue.assignee_id)
    resolved_by_name = _resolve_user_name(users, issue.resolved_by)
    return IssueDTO(
        id=issue.id,
        project_id=issue.project_id,
        title=issue.title,
        description=issue.description,
        severity=issue.severity.value,
        type=issue.type.value,
        status=issue.status.value,
        reporter_id=issue.reporter_id,
        reporter_name=reporter_name,
        assignee_id=issue.assignee_id,
        assignee_name=assignee_name,
        task_id=issue.task_id,
        task_name=task_snapshot.name if task_snapshot else None,
        task_status=task_snapshot.status if task_snapshot else None,
        task_previous_status=task_snapshot.status_before_correction if task_snapshot else None,
        resolution_note=issue.resolution_note,
        resolved_by=issue.resolved_by,
        resolved_by_name=resolved_by_name,
        resolved_at=issue.resolved_at.isoformat() if issue.resolved_at else None,
        version=issue.version,
        created_at=issue.created_at.isoformat(),
        updated_at=issue.updated_at.isoformat(),
        evidences_count=evidences_count,
    )


def _maybe_restore_linked_task(
    *,
    project_id: str,
    issue: Issue,
    requested_task_status: str | None,
    actor_id: str,
    now: datetime,
    issue_repo: IssueRepository,
    task_coordinator: FixTaskCoordinatorPort | None,
    outbox: OutboxPort | None,
    id_gen: IdGenerator,
) -> tuple[TaskSnapshot | None, bool]:
    if issue.task_id is None or task_coordinator is None:
        return None, False
    locked_task = task_coordinator.lock_task_for_update(project_id, issue.task_id)
    if locked_task is None or locked_task.status != "CORRECTION":
        return locked_task, False
    remaining = issue_repo.count_other_open_issues_for_task(
        issue.task_id, exclude_issue_id=issue.id
    )
    if remaining > 0:
        return locked_task, False
    target_status = resolve_restorable_task_status(
        requested_task_status, locked_task.status_before_correction
    )
    restored = task_coordinator.restore_task_from_correction(
        task=locked_task,
        target_status=target_status,
        actor_id=actor_id,
        history_id=id_gen.generate(),
        when=now,
    )
    if outbox is not None:
        outbox.enqueue_event(
            event_id=id_gen.generate(),
            aggregate_type="story_task",
            aggregate_id=restored.id,
            event_type="task.status_restored",
            payload={
                "project_id": project_id,
                "task_id": restored.id,
                "issue_id": issue.id,
                "previous_status": "CORRECTION",
                "new_status": restored.status,
                "actor_id": actor_id,
            },
            created_at=now,
        )
    return restored, True


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

        if cmd.idempotency_key:
            existing = self._repo.get_by_idempotency_key(project_id, cmd.idempotency_key)
            if existing is not None:
                return IssueOperationResponse(
                    message=ISSUE_CREATED,
                    issue=_build_issue_dto(existing, self._users),
                )

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
            task_id=None,
            resolved_by=None,
            version=1,
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

        return IssueOperationResponse(
            message=ISSUE_CREATED,
            issue=_build_issue_dto(issue, self._users),
        )


class ListIssuesUseCase:
    def __init__(
        self,
        repo: IssueRepository,
        projects: ProjectLookupPort,
        users: UserDisplayLookupPort,
        tasks: FixTaskCoordinatorPort | None = None,
    ) -> None:
        self._repo = repo
        self._projects = projects
        self._users = users
        self._tasks = tasks

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
        task_ids = [i.task_id for i in issues if i.task_id]
        task_map = (
            self._tasks.get_task_snapshots_map(task_ids)
            if self._tasks is not None and task_ids
            else {}
        )

        items = [
            _build_issue_dto(
                iss,
                self._users,
                evidences_count=ev_counts.get(iss.id, 0),
                task_snapshot=task_map.get(iss.task_id) if iss.task_id else None,
            )
            for iss in issues
        ]

        return IssueListResponse(items=items, next_cursor=next_cursor, total=total)


class GetIssueDetailUseCase:
    def __init__(
        self,
        issue_repo: IssueRepository,
        evidence_repo: EvidenceRepository,
        signed_url_gen: SignedUrlGenerator,
        projects: ProjectLookupPort,
        users: UserDisplayLookupPort,
        tasks: FixTaskCoordinatorPort | None = None,
    ) -> None:
        self._issue_repo = issue_repo
        self._evidence_repo = evidence_repo
        self._signed_url_gen = signed_url_gen
        self._projects = projects
        self._users = users
        self._tasks = tasks

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

        rep_name = _resolve_user_name(self._users, issue.reporter_id, "Usuario") or "Usuario"
        asg_name = _resolve_user_name(self._users, issue.assignee_id)
        res_name = _resolve_user_name(self._users, issue.resolved_by)

        task_snapshot = (
            self._tasks.get_task_snapshot(project_id, issue.task_id)
            if issue.task_id and self._tasks is not None
            else None
        )
        other_open = (
            self._issue_repo.count_other_open_issues_for_task(
                issue.task_id, exclude_issue_id=issue.id
            )
            if issue.task_id
            else 0
        )

        evidences = self._evidence_repo.list_by_issue(issue.id)
        ev_dtos: list[EvidenceDTO] = []
        for ev in evidences:
            url = self._signed_url_gen.generate(
                project_id=project_id,
                issue_id=issue.id,
                evidence_id=ev.id,
                expires_in_seconds=300,
            )
            up_name = _resolve_user_name(self._users, ev.uploaded_by, "Usuario") or "Usuario"
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
            task_id=issue.task_id,
            task_name=task_snapshot.name if task_snapshot else None,
            task_status=task_snapshot.status if task_snapshot else None,
            task_previous_status=(
                task_snapshot.status_before_correction if task_snapshot else None
            ),
            other_open_issues_count=other_open,
            resolution_note=issue.resolution_note,
            resolved_by=issue.resolved_by,
            resolved_by_name=res_name,
            resolved_at=issue.resolved_at.isoformat() if issue.resolved_at else None,
            version=issue.version,
            created_at=issue.created_at.isoformat(),
            updated_at=issue.updated_at.isoformat(),
            evidences_count=len(ev_dtos),
            evidences=ev_dtos,
            ai_analyses=[],
        )


class AssignIssueUseCase:
    """HU_DN_07_102: Assign issue to active developer member with lock & outbox."""

    def __init__(
        self,
        repo: IssueRepository,
        uow: UnitOfWork,
        id_gen: IdGenerator,
        clock: Clock,
        projects: ProjectLookupPort,
        users: UserDisplayLookupPort,
        outbox: OutboxPort,
        notification_sender: IssueNotificationPort | None = None,
        tasks: FixTaskCoordinatorPort | None = None,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._id_gen = id_gen
        self._clock = clock
        self._projects = projects
        self._users = users
        self._outbox = outbox
        self._notifications = notification_sender
        self._tasks = tasks

    def execute(
        self,
        project_id: str,
        issue_id: str,
        cmd: AssignIssueCommand,
        actor: CurrentUser,
    ) -> IssueOperationResponse:
        if actor.role not in ("admin", "manager"):
            raise PermissionError(ASSIGN_FORBIDDEN)
        if not self._projects.is_active_member(project_id, actor.id):
            raise PermissionError(NOT_MEMBER_ERROR)

        clean_assignee = (cmd.assignee_id or "").strip() or None
        if clean_assignee is not None and not self._projects.is_active_developer_member(
            project_id, clean_assignee
        ):
            raise ValueError(ASSIGN_DEVELOPER_ONLY)

        issue = self._repo.get_by_id(issue_id)
        if issue is None or issue.project_id != project_id:
            raise LookupError(ISSUE_NOT_FOUND)

        if cmd.version is not None and cmd.version != issue.version:
            raise ConflictError(OPTIMISTIC_LOCK_CONFLICT)

        expected_version = cmd.version if cmd.version is not None else issue.version
        now = self._clock.now()
        issue.assignee_id = clean_assignee
        issue.updated_at = now
        issue.version = expected_version + 1

        with self._uow:
            updated = self._repo.update_with_optimistic_lock(issue, expected_version)
            if not updated:
                raise ConflictError(OPTIMISTIC_LOCK_CONFLICT)
            self._outbox.enqueue_event(
                event_id=self._id_gen.generate(),
                aggregate_type="fix",
                aggregate_id=issue.id,
                event_type="issue.assigned",
                payload={
                    "project_id": project_id,
                    "issue_id": issue.id,
                    "title": issue.title,
                    "assignee_id": clean_assignee,
                    "actor_id": actor.id,
                    "version": issue.version,
                },
                created_at=now,
            )
            if self._notifications is not None:
                self._notifications.notify_issue_assigned_in_tx(
                    project_id=project_id,
                    issue_id=issue.id,
                    title=issue.title,
                    assignee_id=clean_assignee,
                    actor_id=actor.id,
                    when=now,
                )
            self._uow.commit()

        task_snapshot = (
            self._tasks.get_task_snapshot(project_id, issue.task_id)
            if issue.task_id and self._tasks is not None
            else None
        )
        ev_count = self._repo.count_evidences_for_issues([issue.id]).get(issue.id, 0)
        return IssueOperationResponse(
            message=ISSUE_ASSIGNED,
            issue=_build_issue_dto(
                issue,
                self._users,
                evidences_count=ev_count,
                task_snapshot=task_snapshot,
            ),
        )


class ResolveIssueUseCase:
    """HU_DN_07_103 & HU_DN_07_105: Resolve open issue and restore linked task if unblocked."""

    def __init__(
        self,
        repo: IssueRepository,
        uow: UnitOfWork,
        id_gen: IdGenerator,
        clock: Clock,
        projects: ProjectLookupPort,
        users: UserDisplayLookupPort,
        outbox: OutboxPort,
        tasks: FixTaskCoordinatorPort | None = None,
        notification_sender: IssueNotificationPort | None = None,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._id_gen = id_gen
        self._clock = clock
        self._projects = projects
        self._users = users
        self._outbox = outbox
        self._tasks = tasks
        self._notifications = notification_sender

    def execute(
        self,
        project_id: str,
        issue_id: str,
        cmd: ResolveIssueCommand,
        actor: CurrentUser,
    ) -> IssueOperationResponse:
        if not self._projects.is_active_member(project_id, actor.id):
            raise PermissionError(NOT_MEMBER_ERROR)

        clean_note = Issue.validate_resolution_note(cmd.resolution_note)
        if cmd.task_status is not None and cmd.task_status.strip():
            resolve_restorable_task_status(cmd.task_status, None)

        issue = self._repo.get_by_id(issue_id)
        if issue is None or issue.project_id != project_id:
            raise LookupError(ISSUE_NOT_FOUND)

        if cmd.version is not None and cmd.version != issue.version:
            raise ConflictError(OPTIMISTIC_LOCK_CONFLICT)
        if issue.status != IssueStatus.OPEN:
            raise ValueError(ISSUE_NOT_OPEN)

        expected_version = cmd.version if cmd.version is not None else issue.version
        now = self._clock.now()
        issue.status = IssueStatus.RESOLVED
        issue.resolution_note = clean_note
        issue.resolved_by = actor.id
        issue.resolved_at = now
        issue.updated_at = now
        issue.version = expected_version + 1

        task_unlinked = False
        task_snapshot: TaskSnapshot | None = None

        with self._uow:
            updated = self._repo.update_with_optimistic_lock(issue, expected_version)
            if not updated:
                raise ConflictError(OPTIMISTIC_LOCK_CONFLICT)

            task_snapshot, task_unlinked = _maybe_restore_linked_task(
                project_id=project_id,
                issue=issue,
                requested_task_status=cmd.task_status,
                actor_id=actor.id,
                now=now,
                issue_repo=self._repo,
                task_coordinator=self._tasks,
                outbox=self._outbox,
                id_gen=self._id_gen,
            )

            self._outbox.enqueue_event(
                event_id=self._id_gen.generate(),
                aggregate_type="fix",
                aggregate_id=issue.id,
                event_type="issue.resolved",
                payload={
                    "project_id": project_id,
                    "issue_id": issue.id,
                    "title": issue.title,
                    "resolved_by": actor.id,
                    "task_id": issue.task_id,
                    "task_unlinked": task_unlinked,
                    "version": issue.version,
                },
                created_at=now,
            )
            if self._notifications is not None:
                self._notifications.notify_issue_resolved_in_tx(
                    project_id=project_id,
                    issue_id=issue.id,
                    title=issue.title,
                    reporter_id=issue.reporter_id,
                    assignee_id=issue.assignee_id,
                    actor_id=actor.id,
                    when=now,
                )
            self._uow.commit()

        ev_count = self._repo.count_evidences_for_issues([issue.id]).get(issue.id, 0)
        message = (
            f"{ISSUE_RESOLVED} {TASK_UNLINKED_AND_UPDATED}" if task_unlinked else ISSUE_RESOLVED
        )
        return IssueOperationResponse(
            message=message,
            issue=_build_issue_dto(
                issue,
                self._users,
                evidences_count=ev_count,
                task_snapshot=task_snapshot,
            ),
            task_unlinked=task_unlinked,
            task_id=task_snapshot.id if task_snapshot else issue.task_id,
            task_status=task_snapshot.status if task_snapshot else None,
            task_message=TASK_UNLINKED_AND_UPDATED if task_unlinked else None,
        )


class CloseIssueUseCase:
    """HU_DN_07_103 & HU_DN_07_105: Admin/Manager closes issue and restores linked task."""

    def __init__(
        self,
        repo: IssueRepository,
        uow: UnitOfWork,
        id_gen: IdGenerator,
        clock: Clock,
        projects: ProjectLookupPort,
        users: UserDisplayLookupPort,
        outbox: OutboxPort,
        tasks: FixTaskCoordinatorPort | None = None,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._id_gen = id_gen
        self._clock = clock
        self._projects = projects
        self._users = users
        self._outbox = outbox
        self._tasks = tasks

    def execute(
        self,
        project_id: str,
        issue_id: str,
        cmd: CloseIssueCommand,
        actor: CurrentUser,
    ) -> IssueOperationResponse:
        if actor.role not in ("admin", "manager"):
            raise PermissionError(CLOSE_FORBIDDEN)
        if not self._projects.is_active_member(project_id, actor.id):
            raise PermissionError(NOT_MEMBER_ERROR)

        if cmd.task_status is not None and cmd.task_status.strip():
            resolve_restorable_task_status(cmd.task_status, None)

        issue = self._repo.get_by_id(issue_id)
        if issue is None or issue.project_id != project_id:
            raise LookupError(ISSUE_NOT_FOUND)

        if cmd.version is not None and cmd.version != issue.version:
            raise ConflictError(OPTIMISTIC_LOCK_CONFLICT)
        if issue.status != IssueStatus.RESOLVED:
            raise ValueError(ISSUE_NOT_RESOLVED)

        expected_version = cmd.version if cmd.version is not None else issue.version
        now = self._clock.now()
        issue.status = IssueStatus.CLOSED
        issue.updated_at = now
        issue.version = expected_version + 1

        task_unlinked = False
        task_snapshot: TaskSnapshot | None = None

        with self._uow:
            updated = self._repo.update_with_optimistic_lock(issue, expected_version)
            if not updated:
                raise ConflictError(OPTIMISTIC_LOCK_CONFLICT)

            task_snapshot, task_unlinked = _maybe_restore_linked_task(
                project_id=project_id,
                issue=issue,
                requested_task_status=cmd.task_status,
                actor_id=actor.id,
                now=now,
                issue_repo=self._repo,
                task_coordinator=self._tasks,
                outbox=self._outbox,
                id_gen=self._id_gen,
            )

            self._outbox.enqueue_event(
                event_id=self._id_gen.generate(),
                aggregate_type="fix",
                aggregate_id=issue.id,
                event_type="issue.closed",
                payload={
                    "project_id": project_id,
                    "issue_id": issue.id,
                    "title": issue.title,
                    "closed_by": actor.id,
                    "task_id": issue.task_id,
                    "task_unlinked": task_unlinked,
                    "version": issue.version,
                },
                created_at=now,
            )
            self._uow.commit()

        ev_count = self._repo.count_evidences_for_issues([issue.id]).get(issue.id, 0)
        message = f"{ISSUE_CLOSED} {TASK_UNLINKED_AND_UPDATED}" if task_unlinked else ISSUE_CLOSED
        return IssueOperationResponse(
            message=message,
            issue=_build_issue_dto(
                issue,
                self._users,
                evidences_count=ev_count,
                task_snapshot=task_snapshot,
            ),
            task_unlinked=task_unlinked,
            task_id=task_snapshot.id if task_snapshot else issue.task_id,
            task_status=task_snapshot.status if task_snapshot else None,
            task_message=TASK_UNLINKED_AND_UPDATED if task_unlinked else None,
        )


class ReportTaskFixUseCase:
    """HU_DN_07_104: Atomically lock task, move to CORRECTION, create linked fix and outbox."""

    def __init__(
        self,
        repo: IssueRepository,
        uow: UnitOfWork,
        id_gen: IdGenerator,
        clock: Clock,
        projects: ProjectLookupPort,
        users: UserDisplayLookupPort,
        tasks: FixTaskCoordinatorPort,
        outbox: OutboxPort,
        notification_sender: IssueNotificationPort | None = None,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._id_gen = id_gen
        self._clock = clock
        self._projects = projects
        self._users = users
        self._tasks = tasks
        self._outbox = outbox
        self._notifications = notification_sender

    def execute(
        self,
        project_id: str,
        task_id: str,
        cmd: ReportTaskFixCommand,
        actor: CurrentUser,
    ) -> IssueOperationResponse:
        if not self._projects.is_active_member(project_id, actor.id):
            raise PermissionError(NOT_MEMBER_ERROR)

        clean_title = Issue.validate_title(cmd.title)
        clean_desc = Issue.validate_description(cmd.description)
        severity = IssueSeverity.from_string(cmd.severity)
        issue_type = IssueType.from_string(cmd.type)

        with self._uow:
            if cmd.idempotency_key:
                existing = self._repo.get_by_idempotency_key(project_id, cmd.idempotency_key)
                if existing is not None:
                    snap = (
                        self._tasks.get_task_snapshot(project_id, existing.task_id)
                        if existing.task_id
                        else None
                    )
                    return IssueOperationResponse(
                        message=TASK_FIX_REPORTED,
                        issue=_build_issue_dto(existing, self._users, task_snapshot=snap),
                        task_id=snap.id if snap else existing.task_id,
                        task_status=snap.status if snap else None,
                    )

            locked_task = self._tasks.lock_task_for_update(project_id, task_id)
            if locked_task is None:
                raise LookupError(TASK_NOT_FOUND)

            if actor.role == "developer" and locked_task.assignee_id != actor.id:
                raise PermissionError(FIX_REPORT_OWN_TASKS_ONLY)

            now = self._clock.now()
            updated_task = self._tasks.transition_task_to_correction(
                task=locked_task,
                actor_id=actor.id,
                history_id=self._id_gen.generate(),
                when=now,
            )

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
                task_id=updated_task.id,
                resolved_by=None,
                version=1,
            )
            self._repo.save(issue)

            self._outbox.enqueue_event(
                event_id=self._id_gen.generate(),
                aggregate_type="fix",
                aggregate_id=issue.id,
                event_type="task.fix_reported",
                payload={
                    "project_id": project_id,
                    "task_id": updated_task.id,
                    "issue_id": issue.id,
                    "title": issue.title,
                    "previous_task_status": updated_task.status_before_correction,
                    "reporter_id": actor.id,
                },
                created_at=now,
            )

            if self._notifications is not None:
                self._notifications.notify_task_fix_reported_in_tx(
                    project_id=project_id,
                    issue_id=issue.id,
                    task_id=updated_task.id,
                    task_name=updated_task.name,
                    title=issue.title,
                    reporter_id=actor.id,
                    when=now,
                )

            self._uow.commit()

        return IssueOperationResponse(
            message=TASK_FIX_REPORTED,
            issue=_build_issue_dto(issue, self._users, task_snapshot=updated_task),
            task_id=updated_task.id,
            task_status=updated_task.status,
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

        validated = validate_and_sanitize_evidence_file(file_name, raw_data)

        existing_duplicate = self._evidence_repo.find_by_fix_and_hash(
            fix_id=issue_id,
            sha256_hash=validated.sha256_hash,
        )
        if existing_duplicate is not None:
            raise ValueError(DUPLICATE_EVIDENCE)

        evidence_id = self._id_gen.generate()
        now = self._clock.now()

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
            self._storage.delete_file(storage_path)
            raise

        url = self._signed_url_gen.generate(
            project_id=project_id,
            issue_id=issue_id,
            evidence_id=evidence.id,
            expires_in_seconds=300,
        )
        up_name = _resolve_user_name(self._users, actor.id, actor.email) or actor.email

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
