"""Self-service profile updates (HU_DN_01_21)."""

from app.modules.auth.application.dtos import (
    ChangePasswordCommand,
    ProfileResponse,
    UpdateProfileCommand,
)
from app.modules.auth.application.mappers import to_profile_dto
from app.modules.auth.domain import messages
from app.modules.auth.domain.errors import ProfileValidationError
from app.modules.auth.domain.ports import UserRepository
from app.modules.auth.domain.rules import NAME_MAX_LENGTH, is_valid_password
from app.modules.auth.infrastructure.avatar_storage import LocalAvatarStorage
from app.shared.application.ports import Clock, PasswordHasher, UnitOfWork


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
        if cmd.details is not None:
            skills = [s.strip() for s in cmd.details.skills if s and str(s).strip()]
            nickname = (cmd.details.nickname or "").strip().lstrip("@") or None
            user.profile_details = {
                "last_name": (cmd.details.last_name or "").strip() or None,
                "nickname": nickname,
                "description": (cmd.details.description or "").strip() or None,
                "experience": (cmd.details.experience or "").strip() or None,
                "skills": skills[:50],
                "github": (cmd.details.github or "").strip() or None,
                "linkedin": (cmd.details.linkedin or "").strip() or None,
                "availability_text": (cmd.details.availability_text or "").strip() or None,
            }
        if avatar_bytes is not None:
            user.avatar_key = self._storage.save(user_id=user.id, content=avatar_bytes)

        with self._uow:
            self._users.update(user)
            self._uow.commit()

        return ProfileResponse(message=messages.PROFILE_UPDATED, profile=to_profile_dto(user))


class ChangePasswordUseCase:
    def __init__(
        self,
        user_repo: UserRepository,
        hasher: PasswordHasher,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._users = user_repo
        self._hasher = hasher
        self._clock = clock
        self._uow = uow

    def execute(self, *, user_id: str, cmd: ChangePasswordCommand) -> ProfileResponse:
        user = self._users.get_by_id(user_id)
        if user is None:
            from app.shared.domain.errors import AppError, ErrorKind

            raise AppError("USER_NOT_FOUND", messages.USER_NOT_FOUND, ErrorKind.NOT_FOUND)

        current = cmd.current_password.strip()
        new_pwd = cmd.new_password
        confirm = cmd.confirm_password
        fields: dict[str, str] = {}
        if not current:
            fields["current_password"] = messages.CURRENT_PASSWORD_REQUIRED
        if not new_pwd.strip() or not confirm.strip():
            fields.setdefault("new_password", messages.REQUIRED_FIELDS)
        if not is_valid_password(new_pwd):
            fields["new_password"] = messages.PASSWORD_WEAK
        elif new_pwd != confirm:
            fields["confirm_password"] = messages.PASSWORD_MISMATCH
        if fields:
            first = next(iter(fields))
            code = (
                "PASSWORD_MISMATCH"
                if first == "confirm_password"
                else "PASSWORD_WEAK"
                if first == "new_password"
                else "CURRENT_PASSWORD_REQUIRED"
            )
            raise ProfileValidationError(code, fields[first], fields)

        if not self._hasher.verify(current, user.hashed_password):
            raise ProfileValidationError(
                "CURRENT_PASSWORD_INVALID",
                messages.CURRENT_PASSWORD_INVALID,
                {"current_password": messages.CURRENT_PASSWORD_INVALID},
            )

        user.hashed_password = self._hasher.hash(new_pwd)
        user.updated_at = self._clock.now()
        with self._uow:
            self._users.update(user)
            self._uow.commit()

        return ProfileResponse(message=messages.PASSWORD_CHANGED, profile=to_profile_dto(user))
