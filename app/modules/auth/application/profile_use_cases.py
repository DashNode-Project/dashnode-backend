"""Self-service profile updates (HU_DN_01_21)."""

from app.modules.auth.application.dtos import ProfileResponse, UpdateProfileCommand
from app.modules.auth.application.mappers import to_profile_dto
from app.modules.auth.domain import messages
from app.modules.auth.domain.errors import ProfileValidationError
from app.modules.auth.domain.ports import UserRepository
from app.modules.auth.domain.rules import NAME_MAX_LENGTH
from app.modules.auth.infrastructure.avatar_storage import LocalAvatarStorage
from app.shared.application.ports import Clock, UnitOfWork


class GetProfileUseCase:
    def __init__(self, user_repo: UserRepository) -> None:
        self._users = user_repo

    def execute(self, *, user_id: str) -> ProfileResponse:
        user = self._users.get_by_id(user_id)
        if user is None:
            from app.shared.domain.errors import AppError, ErrorKind

            raise AppError("USER_NOT_FOUND", messages.USER_NOT_FOUND, ErrorKind.NOT_FOUND)
        return ProfileResponse(profile=to_profile_dto(user))


class UpdateProfileUseCase:
    def __init__(
        self,
        user_repo: UserRepository,
        storage: LocalAvatarStorage,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._users = user_repo
        self._storage = storage
        self._clock = clock
        self._uow = uow

    def execute(
        self,
        *,
        user_id: str,
        cmd: UpdateProfileCommand,
        avatar_bytes: bytes | None = None,
    ) -> ProfileResponse:
        user = self._users.get_by_id(user_id)
        if user is None:
            from app.shared.domain.errors import AppError, ErrorKind

            raise AppError("USER_NOT_FOUND", messages.USER_NOT_FOUND, ErrorKind.NOT_FOUND)

        name = cmd.name.strip()
        if not name:
            raise ProfileValidationError(
                "NAME_REQUIRED", messages.NAME_REQUIRED, {"name": messages.NAME_REQUIRED}
            )
        if len(name) > NAME_MAX_LENGTH:
            raise ProfileValidationError(
                "NAME_TOO_LONG", messages.NAME_TOO_LONG, {"name": messages.NAME_TOO_LONG}
            )

        now = self._clock.now()
        user.name = name
        user.updated_at = now
        if avatar_bytes is not None:
            user.avatar_key = self._storage.save(user_id=user.id, content=avatar_bytes)

        with self._uow:
            self._users.update(user)
            self._uow.commit()

        return ProfileResponse(message=messages.PROFILE_UPDATED, profile=to_profile_dto(user))
