"""Deactivate and reactivate users (HU_DN_01_17, HU_DN_01_18)."""

from app.modules.auth.application.dtos import MessageResponse
from app.modules.auth.domain import messages
from app.modules.auth.domain.entities import UserRole
from app.modules.auth.domain.errors import (
    ManagerDeactivateBlockedError,
    ReactivateNotInactiveError,
    SelfDeactivateBlockedError,
)
from app.modules.auth.domain.ports import (
    PendingAssignmentsQuery,
    ProjectOwnershipQuery,
    SessionRepository,
    UserRepository,
)
from app.shared.application.ports import Clock, UnitOfWork
from app.shared.domain.authorization import AccessDeniedError
from app.shared.domain.errors import AppError, ErrorKind


class DeactivateUserByAdminUseCase:
    def __init__(
        self,
        user_repo: UserRepository,
        session_repo: SessionRepository,
        project_ownership: ProjectOwnershipQuery,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._users = user_repo
        self._sessions = session_repo
        self._project_ownership = project_ownership
        self._clock = clock
        self._uow = uow

    def execute(self, *, actor_id: str, target_user_id: str) -> MessageResponse:
        actor = self._users.get_by_id(actor_id)
        if actor is None or actor.role != UserRole.ADMIN:
            raise AccessDeniedError()

        if actor_id == target_user_id:
            raise SelfDeactivateBlockedError()

        target = self._users.get_by_id(target_user_id)
        if target is None:
            raise AppError("USER_NOT_FOUND", messages.USER_NOT_FOUND, ErrorKind.NOT_FOUND)

        if target.role == UserRole.MANAGER and self._project_ownership.user_owns_projects(
            target.id
        ):
            raise ManagerDeactivateBlockedError()

        now = self._clock.now()
        target.deactivate(now)

        with self._uow:
            self._sessions.revoke_all_active_for_user(target.id, now)
            self._users.update(target)
            self._uow.commit()

        return MessageResponse(message=messages.USER_DEACTIVATED)


class ReactivateUserByAdminUseCase:
    def __init__(
        self,
        user_repo: UserRepository,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._users = user_repo
        self._clock = clock
        self._uow = uow

    def execute(self, *, actor_id: str, target_user_id: str) -> MessageResponse:
        actor = self._users.get_by_id(actor_id)
        if actor is None or actor.role != UserRole.ADMIN:
            raise AccessDeniedError()

        target = self._users.get_by_id(target_user_id)
        if target is None:
            raise AppError("USER_NOT_FOUND", messages.USER_NOT_FOUND, ErrorKind.NOT_FOUND)

        if target.is_active:
            raise ReactivateNotInactiveError()

        now = self._clock.now()
        target.reactivate(now)

        with self._uow:
            self._users.update(target)
            self._uow.commit()

        return MessageResponse(message=messages.USER_REACTIVATED)


class GetPendingAssignmentsUseCase:
    """HU_DN_01_19: count pending tasks/stories for deactivate dialog."""

    def __init__(
        self,
        user_repo: UserRepository,
        pending: PendingAssignmentsQuery,
    ) -> None:
        self._users = user_repo
        self._pending = pending

    def execute(self, *, actor_id: str, target_user_id: str) -> dict[str, int]:
        actor = self._users.get_by_id(actor_id)
        if actor is None or actor.role != UserRole.ADMIN:
            raise AccessDeniedError()

        if self._users.get_by_id(target_user_id) is None:
            raise AppError("USER_NOT_FOUND", messages.USER_NOT_FOUND, ErrorKind.NOT_FOUND)

        count = self._pending.count_pending_for_user(target_user_id)
        return {"pending_count": count}
