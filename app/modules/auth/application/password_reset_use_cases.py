"""Password reset and one-time credential link flows (HU_DN_01_06, HU_DN_01_07, HU_DN_01_10)."""

from dataclasses import dataclass
from datetime import timedelta

from app.modules.auth.application.dtos import (
    AdminUserSummaryDTO,
    CompletePasswordResetCommand,
    MessageResponse,
    RequestPasswordResetCommand,
)
from app.modules.auth.domain import messages
from app.modules.auth.domain.entities import CredentialTokenPurpose, PasswordCredentialToken
from app.modules.auth.domain.errors import (
    AdminOnlyError,
    AdminResetDisabledTargetError,
    InvalidCredentialTokenError,
    PasswordResetValidationError,
)
from app.modules.auth.domain.ports import (
    PasswordCredentialTokenRepository,
    SessionTokenService,
    TransactionalEmailSender,
    UserRepository,
)
from app.modules.auth.domain.rules import is_valid_email, is_valid_password, normalize_email
from app.shared.application.ports import Clock, IdGenerator, PasswordHasher, UnitOfWork


@dataclass(frozen=True)
class CredentialTokenPolicy:
    reset_ttl: timedelta
    activation_ttl: timedelta
    frontend_base_url: str


class RequestPasswordResetUseCase:
    """HU_DN_01_06: agnostic success; e-mail only when the account exists."""

    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: PasswordCredentialTokenRepository,
        tokens: SessionTokenService,
        mailer: TransactionalEmailSender,
        id_gen: IdGenerator,
        clock: Clock,
        uow: UnitOfWork,
        policy: CredentialTokenPolicy,
    ) -> None:
        self._users = user_repo
        self._tokens_repo = token_repo
        self._tokens = tokens
        self._mailer = mailer
        self._id_gen = id_gen
        self._clock = clock
        self._uow = uow
        self._policy = policy

    def execute(self, cmd: RequestPasswordResetCommand) -> MessageResponse:
        email = normalize_email(cmd.email.strip())
        if not email:
            raise PasswordResetValidationError(
                "REQUIRED_FIELDS",
                messages.REQUIRED_FIELDS,
                {"email": messages.REQUIRED_FIELDS},
            )
        if not is_valid_email(email):
            raise PasswordResetValidationError(
                "EMAIL_INVALID",
                messages.EMAIL_INVALID,
                {"email": messages.EMAIL_INVALID},
            )

        user = self._users.get_by_email(email)
        if user is not None and user.is_active:
            raw = self._tokens.new_token()
            now = self._clock.now()
            token = PasswordCredentialToken(
                id=self._id_gen.generate(),
                user_id=user.id,
                token_hash=self._tokens.digest(raw),
                purpose=CredentialTokenPurpose.PASSWORD_RESET,
                created_at=now,
                expires_at=now + self._policy.reset_ttl,
            )
            with self._uow:
                self._tokens_repo.invalidate_active_for_user(
                    user.id, CredentialTokenPurpose.PASSWORD_RESET
                )
                self._tokens_repo.add(token)
                self._uow.commit()
            reset_url = (
                f"{self._policy.frontend_base_url.rstrip('/')}/establecer-contrasena"
                f"?token={raw}&purpose=reset"
            )
            self._mailer.send_password_reset(to_email=user.email, reset_url=reset_url)

        return MessageResponse(message=messages.PASSWORD_RESET_REQUEST_SUCCESS)


class CompletePasswordResetUseCase:
    """HU_DN_01_07: validate token, hash password, invalidate link atomically."""

    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: PasswordCredentialTokenRepository,
        tokens: SessionTokenService,
        hasher: PasswordHasher,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._users = user_repo
        self._tokens_repo = token_repo
        self._tokens = tokens
        self._hasher = hasher
        self._clock = clock
        self._uow = uow

    def execute(self, cmd: CompletePasswordResetCommand) -> MessageResponse:
        raw_token = cmd.token.strip()
        if not raw_token:
            raise InvalidCredentialTokenError()

        password = cmd.password
        confirm = cmd.confirm_password
        if not password.strip() or not confirm.strip():
            raise PasswordResetValidationError(
                "REQUIRED_FIELDS",
                messages.REQUIRED_FIELDS,
                {"password": messages.REQUIRED_FIELDS},
            )
        errors: dict[str, str] = {}
        if not is_valid_password(password):
            errors["password"] = messages.PASSWORD_WEAK
        elif password != confirm:
            errors["confirm_password"] = messages.PASSWORD_MISMATCH
        if errors:
            first_field = next(iter(errors))
            code = "PASSWORD_MISMATCH" if first_field == "confirm_password" else "PASSWORD_WEAK"
            raise PasswordResetValidationError(code, errors[first_field], errors)

        digest = self._tokens.digest(raw_token)
        stored = self._tokens_repo.get_by_token_hash(digest)
        now = self._clock.now()
        if stored is None or stored.is_used() or stored.is_expired(now):
            raise InvalidCredentialTokenError()

        user = self._users.get_by_id(stored.user_id)
        if user is None or not user.is_active:
            raise InvalidCredentialTokenError()

        user.hashed_password = self._hasher.hash(password)
        user.updated_at = now
        stored.mark_used(now)

        with self._uow:
            self._users.update(user)
            self._tokens_repo.update(stored)
            self._uow.commit()

        return MessageResponse(message=messages.PASSWORD_SET_SUCCESS)


class AdminRequestPasswordResetUseCase:
    """HU_DN_01_10: admin triggers reset e-mail for an active user."""

    def __init__(
        self,
        actor_repo: UserRepository,
        user_repo: UserRepository,
        token_repo: PasswordCredentialTokenRepository,
        tokens: SessionTokenService,
        mailer: TransactionalEmailSender,
        id_gen: IdGenerator,
        clock: Clock,
        uow: UnitOfWork,
        policy: CredentialTokenPolicy,
    ) -> None:
        self._actors = actor_repo
        self._users = user_repo
        self._tokens_repo = token_repo
        self._tokens = tokens
        self._mailer = mailer
        self._id_gen = id_gen
        self._clock = clock
        self._uow = uow
        self._policy = policy

    def execute(self, *, actor_id: str, target_user_id: str) -> MessageResponse:
        actor = self._actors.get_by_id(actor_id)
        if actor is None or actor.role.value != "admin":
            raise AdminOnlyError()

        target = self._users.get_by_id(target_user_id)
        if target is None:
            # Do not reveal existence: same success as a sent mail would be misleading;
            # admin UI only lists real users, so 404 is acceptable for unknown ids.
            from app.shared.domain.errors import AppError, ErrorKind

            raise AppError("USER_NOT_FOUND", "Usuario no encontrado.", ErrorKind.NOT_FOUND)

        if not target.is_active:
            raise AdminResetDisabledTargetError()

        raw = self._tokens.new_token()
        now = self._clock.now()
        token = PasswordCredentialToken(
            id=self._id_gen.generate(),
            user_id=target.id,
            token_hash=self._tokens.digest(raw),
            purpose=CredentialTokenPurpose.PASSWORD_RESET,
            created_at=now,
            expires_at=now + self._policy.reset_ttl,
        )
        with self._uow:
            self._tokens_repo.invalidate_active_for_user(
                target.id, CredentialTokenPurpose.PASSWORD_RESET
            )
            self._tokens_repo.add(token)
            self._uow.commit()
        reset_url = (
            f"{self._policy.frontend_base_url.rstrip('/')}/establecer-contrasena"
            f"?token={raw}&purpose=reset"
        )
        self._mailer.send_password_reset(to_email=target.email, reset_url=reset_url)
        return MessageResponse(message=messages.ADMIN_RESET_SENT)


class ListAdminUsersUseCase:
    def __init__(self, user_repo: UserRepository) -> None:
        self._users = user_repo

    def execute(self, *, actor_id: str) -> list[AdminUserSummaryDTO]:
        actor = self._users.get_by_id(actor_id)
        if actor is None or actor.role.value != "admin":
            raise AdminOnlyError()
        return [
            AdminUserSummaryDTO(
                id=u.id,
                name=u.name,
                email=u.email,
                role=u.role,
                is_active=u.is_active,
            )
            for u in self._users.list_all()
        ]
