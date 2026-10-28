"""Use cases for Documentation and Knowledge Base (EP-09)."""

from typing import Protocol

from app.modules.documentation.application.dtos import (
    CreateDocumentationCommand,
    DocumentationEntryDTO,
    DocumentationListResponse,
    DocumentationOperationResponse,
    UpdateDocumentationCommand,
    is_valid_url,
)
from app.modules.documentation.domain import messages
from app.modules.documentation.domain.entities import (
    DocumentationApprovalStatus,
    DocumentationCategory,
    DocumentationEntry,
)
from app.modules.documentation.domain.ports import DocumentationRepository
from app.shared.application.identity import CurrentUser
from app.shared.application.ports import Clock, IdGenerator, UnitOfWork
from app.shared.domain.authorization import AccessDeniedError
from app.shared.domain.errors import AppError, ErrorKind


class ProjectLookupPort(Protocol):
    def get_project(self, project_id: str) -> object | None: ...
    def is_member(self, project_id: str, user_id: str) -> bool: ...


class UserLookupPort(Protocol):
    def get_user_display(self, user_id: str) -> tuple[str, str | None] | None: ...


def _check_project_access(
    project_id: str, actor: CurrentUser, projects: ProjectLookupPort
) -> object:
    project = projects.get_project(project_id)
    if project is None or (hasattr(project, "is_deleted") and project.is_deleted()):
        raise AppError("PROJECT_NOT_FOUND", messages.PROJECT_NOT_FOUND, ErrorKind.NOT_FOUND)

    if actor.role == "admin":
        return project

    is_proj_manager = hasattr(project, "manager_id") and project.manager_id == actor.id
    is_owner = hasattr(project, "owner_id") and project.owner_id == actor.id
    if is_proj_manager or is_owner:
        return project

    if not projects.is_member(project_id, actor.id):
        raise AccessDeniedError()

    return project


def _validate_documentation_input(
    cmd: CreateDocumentationCommand | UpdateDocumentationCommand,
) -> None:
    if not cmd.title or not cmd.title.strip():
        raise AppError("TITLE_REQUIRED", messages.TITLE_REQUIRED, ErrorKind.VALIDATION)
    if len(cmd.title.strip()) > 100:
        raise AppError("TITLE_TOO_LONG", messages.TITLE_TOO_LONG, ErrorKind.VALIDATION)

    valid_cats = {c.value for c in DocumentationCategory}
    if not cmd.category or cmd.category.strip() not in valid_cats:
        raise AppError("CATEGORY_REQUIRED", messages.CATEGORY_REQUIRED, ErrorKind.VALIDATION)

    if cmd.external_url and cmd.external_url.strip() and not is_valid_url(cmd.external_url):
        raise AppError("INVALID_URL", messages.INVALID_URL, ErrorKind.VALIDATION)

    has_content = bool(cmd.content and cmd.content.strip())
    has_url = bool(cmd.external_url and cmd.external_url.strip())
    if not has_content and not has_url:
        raise AppError(
            "CONTENT_OR_URL_REQUIRED", messages.CONTENT_OR_URL_REQUIRED, ErrorKind.VALIDATION
        )


def _entry_to_dto(
    entry: DocumentationEntry, actor: CurrentUser, users: UserLookupPort
) -> DocumentationEntryDTO:
    user_info = users.get_user_display(entry.author_id)
    author_name = user_info[0] if user_info else None

    return DocumentationEntryDTO(
        id=entry.id,
        project_id=entry.project_id,
        author_id=entry.author_id,
        author_name=author_name,
        title=entry.title,
        category=entry.category.value if hasattr(entry.category, "value") else str(entry.category),
        objective=entry.objective,
        tags=entry.tags,
        content=entry.content,
        external_url=entry.external_url,
        approval_status=entry.approval_status.value
        if hasattr(entry.approval_status, "value")
        else str(entry.approval_status),
        is_pinned=entry.is_pinned,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        can_edit=entry.can_edit(actor.id, actor.role),
        can_delete=entry.can_delete(actor.role),
    )


class CreateDocumentationEntryUseCase:
    def __init__(
        self,
        repo: DocumentationRepository,
        uow: UnitOfWork,
        id_gen: IdGenerator,
        clock: Clock,
        projects: ProjectLookupPort,
        users: UserLookupPort,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._id_gen = id_gen
        self._clock = clock
        self._projects = projects
        self._users = users

    def execute(
        self, project_id: str, cmd: CreateDocumentationCommand, actor: CurrentUser
    ) -> DocumentationOperationResponse:
        _check_project_access(project_id, actor, self._projects)
        _validate_documentation_input(cmd)

        now = self._clock.now()
        entry_id = self._id_gen.generate()
        category = DocumentationCategory(cmd.category)

        is_pinned = bool(
            cmd.is_pinned
            and str(actor.role).lower() in ("admin", "manager", "administrador", "gerente")
        )
        entry = DocumentationEntry(
            id=entry_id,
            project_id=project_id,
            author_id=actor.id,
            title=cmd.title.strip(),
            category=category,
            objective=cmd.objective.strip() if cmd.objective else None,
            tags=cmd.tags.strip() if cmd.tags else None,
            content=cmd.content.strip() if cmd.content else None,
            external_url=cmd.external_url.strip() if cmd.external_url else None,
            approval_status=DocumentationApprovalStatus.PENDING,
            is_pinned=is_pinned,
            is_deleted=False,
            created_at=now,
            updated_at=now,
        )

        with self._uow:
            self._repo.save(entry)
            self._uow.commit()

        return DocumentationOperationResponse(
            message=messages.ENTRY_CREATED,
            entry=_entry_to_dto(entry, actor, self._users),
        )


class UpdateDocumentationEntryUseCase:
    def __init__(
        self,
        repo: DocumentationRepository,
        uow: UnitOfWork,
        clock: Clock,
        projects: ProjectLookupPort,
        users: UserLookupPort,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._clock = clock
        self._projects = projects
        self._users = users

    def execute(
        self,
        project_id: str,
        entry_id: str,
        cmd: UpdateDocumentationCommand,
        actor: CurrentUser,
    ) -> DocumentationOperationResponse:
        _check_project_access(project_id, actor, self._projects)
        entry = self._repo.get_by_id(entry_id)
        if entry is None or entry.is_deleted or entry.project_id != project_id:
            raise AppError("ENTRY_NOT_FOUND", messages.ENTRY_NOT_FOUND, ErrorKind.NOT_FOUND)

        if not entry.can_edit(actor.id, actor.role):
            raise AccessDeniedError()

        _validate_documentation_input(cmd)

        now = self._clock.now()
        content_changed = (
            entry.title != cmd.title.strip()
            or entry.category != DocumentationCategory(cmd.category)
            or entry.objective != (cmd.objective.strip() if cmd.objective else None)
            or entry.tags != (cmd.tags.strip() if cmd.tags else None)
            or entry.content != (cmd.content.strip() if cmd.content else None)
            or entry.external_url != (cmd.external_url.strip() if cmd.external_url else None)
        )

        entry.title = cmd.title.strip()
        entry.category = DocumentationCategory(cmd.category)
        entry.objective = cmd.objective.strip() if cmd.objective else None
        entry.tags = cmd.tags.strip() if cmd.tags else None
        entry.content = cmd.content.strip() if cmd.content else None
        entry.external_url = cmd.external_url.strip() if cmd.external_url else None
        entry.updated_at = now

        if str(actor.role).lower() in ("admin", "manager", "administrador", "gerente"):
            if cmd.is_pinned is not None:
                entry.is_pinned = cmd.is_pinned

            if cmd.approval_status:
                status_str = cmd.approval_status.upper()
                if status_str in ("APPROVED", "REJECTED", "PENDING"):
                    entry.approval_status = DocumentationApprovalStatus(status_str)
            elif content_changed and entry.approval_status == DocumentationApprovalStatus.APPROVED:
                # RN-DOC-05: If already approved, editing resets status to PENDING
                entry.approval_status = DocumentationApprovalStatus.PENDING
        else:
            # RN-DOC-05: For Developer, editing always resets an approved entry to PENDING
            if entry.approval_status == DocumentationApprovalStatus.APPROVED:
                entry.approval_status = DocumentationApprovalStatus.PENDING

        with self._uow:
            self._repo.save(entry)
            self._uow.commit()

        return DocumentationOperationResponse(
            message=messages.ENTRY_UPDATED,
            entry=_entry_to_dto(entry, actor, self._users),
        )


class DeleteDocumentationEntryUseCase:
    def __init__(
        self,
        repo: DocumentationRepository,
        uow: UnitOfWork,
        clock: Clock,
        projects: ProjectLookupPort,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._clock = clock
        self._projects = projects

    def execute(
        self, project_id: str, entry_id: str, actor: CurrentUser
    ) -> DocumentationOperationResponse:
        _check_project_access(project_id, actor, self._projects)
        entry = self._repo.get_by_id(entry_id)
        if entry is None or entry.is_deleted or entry.project_id != project_id:
            raise AppError("ENTRY_NOT_FOUND", messages.ENTRY_NOT_FOUND, ErrorKind.NOT_FOUND)

        if not entry.can_delete(actor.role):
            raise AccessDeniedError()

        now = self._clock.now()
        entry.is_deleted = True
        entry.updated_at = now

        with self._uow:
            self._repo.save(entry)
            self._uow.commit()

        return DocumentationOperationResponse(
            message=messages.ENTRY_DELETED,
            entry=None,
        )


class ListDocumentationEntriesUseCase:
    def __init__(
        self,
        repo: DocumentationRepository,
        projects: ProjectLookupPort,
        users: UserLookupPort,
    ) -> None:
        self._repo = repo
        self._projects = projects
        self._users = users

    def execute(
        self,
        project_id: str,
        actor: CurrentUser,
        category: str | None = None,
        approval_status: str | None = None,
        search: str | None = None,
    ) -> DocumentationListResponse:
        _check_project_access(project_id, actor, self._projects)
        entries = self._repo.list_by_project(project_id)

        visible = [e for e in entries if e.can_view(actor.id, actor.role)]

        if category:
            cat_clean = category.strip().lower()
            visible = [
                e
                for e in visible
                if (e.category.value if hasattr(e.category, "value") else str(e.category)).lower()
                == cat_clean
            ]

        if approval_status:
            status_clean = approval_status.strip().upper()
            visible = [
                e
                for e in visible
                if (
                    e.approval_status.value
                    if hasattr(e.approval_status, "value")
                    else str(e.approval_status)
                ).upper()
                == status_clean
            ]

        if search:
            q = search.strip().lower()
            visible = [
                e
                for e in visible
                if q in e.title.lower()
                or (e.content and q in e.content.lower())
                or (e.objective and q in e.objective.lower())
                or (e.tags and q in e.tags.lower())
            ]

        # Sort: pinned first (0), then newest created_at first
        visible.sort(key=lambda e: (0 if e.is_pinned else 1, -e.created_at.timestamp()))

        dtos = [_entry_to_dto(e, actor, self._users) for e in visible]
        msg = messages.NO_ENTRIES if not dtos else None

        return DocumentationListResponse(entries=dtos, message=msg)


class GetDocumentationEntryUseCase:
    def __init__(
        self,
        repo: DocumentationRepository,
        projects: ProjectLookupPort,
        users: UserLookupPort,
    ) -> None:
        self._repo = repo
        self._projects = projects
        self._users = users

    def execute(self, project_id: str, entry_id: str, actor: CurrentUser) -> DocumentationEntryDTO:
        _check_project_access(project_id, actor, self._projects)
        entry = self._repo.get_by_id(entry_id)
        if entry is None or entry.is_deleted or entry.project_id != project_id:
            raise AppError("ENTRY_NOT_FOUND", messages.ENTRY_NOT_FOUND, ErrorKind.NOT_FOUND)

        # HU_DN_06_81: Direct access control
        if not entry.can_view(actor.id, actor.role):
            raise AppError("ACCESS_DENIED", messages.ENTRY_ACCESS_DENIED, ErrorKind.FORBIDDEN)

        return _entry_to_dto(entry, actor, self._users)
