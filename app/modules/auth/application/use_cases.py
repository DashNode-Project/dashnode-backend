"""
Use cases for authentication and user management.
@sad AD-09, 4.1.1
@origin [SAD-Propuesto]
"""

from app.modules.auth.application.dtos import (
    RegisterManagerCommand,
    RegisterManagerResponse,
)
from app.modules.auth.application.mappers import to_user_dto
from app.modules.auth.domain import messages
from app.modules.auth.domain.entities import User, UserRole
from app.modules.auth.domain.errors import (
    EmailAlreadyRegisteredError,
    RegistrationRoleNotAllowedError,
    RegistrationValidationError,
)
from app.modules.auth.domain.ports import UserRepository
from app.modules.auth.domain.rules import (
    NAME_MAX_LENGTH,
    is_valid_email,
    is_valid_password,
    normalize_email,
)
from app.shared.application.ports import Clock, IdGenerator, PasswordHasher, UnitOfWork

_FIELD_ORDER = ("name", "email", "password", "confirm_password")


class RegisterManagerUseCase:
    """Public registration of a Manager account (HU_DN_01_02)."""

    def __init__(
        self,
        user_repo: UserRepository,
        hasher: PasswordHasher,
        id_gen: IdGenerator,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._user_repo = user_repo
        self._hasher = hasher
        self._id_gen = id_gen
        self._clock = clock
        self._uow = uow

    @staticmethod
    def _validate(cmd: RegisterManagerCommand, name: str, email: str) -> None:
        """Raise RegistrationValidationError describing every problem found."""
        raw = {
            "name": name,
            "email": email,
            "password": cmd.password,
            "confirm_password": cmd.confirm_password,
        }
        blank = [field for field in _FIELD_ORDER if not raw[field].strip()]
        if blank:
            if blank == ["name"]:
                raise RegistrationValidationError(
                    "NAME_REQUIRED", messages.NAME_REQUIRED, {"name": messages.NAME_REQUIRED}
                )
            fields = {
                field: messages.NAME_REQUIRED if field == "name" else messages.REQUIRED_FIELDS
                for field in blank
            }
            raise RegistrationValidationError("REQUIRED_FIELDS", messages.REQUIRED_FIELDS, fields)

        errors: dict[str, tuple[str, str]] = {}
        if len(name) > NAME_MAX_LENGTH:
            errors["name"] = ("NAME_TOO_LONG", messages.NAME_TOO_LONG)
        if not is_valid_email(email):
            errors["email"] = ("EMAIL_INVALID", messages.EMAIL_INVALID)
        if not is_valid_password(cmd.password):
            errors["password"] = ("PASSWORD_WEAK", messages.PASSWORD_WEAK)
        elif cmd.password != cmd.confirm_password:
            errors["confirm_password"] = ("PASSWORD_MISMATCH", messages.PASSWORD_MISMATCH)
        if errors:
            first = next(field for field in _FIELD_ORDER if field in errors)
            code, message = errors[first]
            raise RegistrationValidationError(
                code, message, {field: text for field, (_, text) in errors.items()}
            )

    def execute(self, cmd: RegisterManagerCommand) -> RegisterManagerResponse:
        # Public registration is only for the Manager role: reject anything else
        # before touching credentials (prevents privilege escalation).
        if cmd.role is not None and cmd.role.strip().lower() != UserRole.MANAGER.value:
            raise RegistrationRoleNotAllowedError

        name = cmd.name.strip()
        email = normalize_email(cmd.email)
        self._validate(cmd, name, email)

        if self._user_repo.get_by_email(email) is not None:
            raise EmailAlreadyRegisteredError

        now = self._clock.now()
        user = User(
            id=self._id_gen.generate(),
            email=email,
            hashed_password=self._hasher.hash(cmd.password),
            name=name,
            role=UserRole.MANAGER,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        with self._uow:
            self._user_repo.save(user)  # raises EmailAlreadyRegisteredError on a race
            self._uow.commit()

        return RegisterManagerResponse(message=messages.REGISTER_SUCCESS, user=to_user_dto(user))
