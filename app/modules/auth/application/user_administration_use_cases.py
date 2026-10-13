"""User provisioning and administration (EP-02: HU_DN_01_11 .. HU_DN_01_16)."""

import secrets

from app.modules.auth.application.dtos import (
    AdminUserSummaryDTO,
    CreateUserByAdminCommand,
    InviteDeveloperCommand,
    MessageResponse,
    UpdateUserByAdminCommand,
    UpdateUserByAdminResponse,
)
from app.modules.auth.application.mappers import to_user_dto
from app.modules.auth.application.password_reset_use_cases import CredentialTokenPolicy
from app.modules.auth.domain import messages
from app.modules.auth.domain.entities import (
    CredentialTokenPurpose,
    PasswordCredentialToken,
    User,
    UserRole,
)
from app.modules.auth.domain.errors import (
    EmailAlreadyRegisteredError,
    ManagerRoleChangeBlockedError,
    UserAdministrationValidationError,
)
from app.modules.auth.domain.ports import (
    PasswordCredentialTokenRepository,
    ProjectOwnershipQuery,
    SessionTokenService,
    TransactionalEmailSender,
    UserRepository,
)
from app.modules.auth.domain.rules import NAME_MAX_LENGTH, is_valid_email, normalize_email
from app.shared.application.ports import Clock, IdGenerator, PasswordHasher, UnitOfWork
from app.shared.domain.authorization import AccessDeniedError
from app.shared.domain.errors import AppError, ErrorKind


def _reject_admin_role(role_raw: str) -> None:
    if role_raw.strip().lower() == UserRole.ADMIN.value:
        raise AccessDeniedError()


def _parse_staff_role(role_raw: str) -> UserRole:
    _reject_admin_role(role_raw)
    normalized = role_raw.strip().lower()
    if normalized == UserRole.MANAGER.value:
        return UserRole.MANAGER
    if normalized == UserRole.DEVELOPER.value:
        return UserRole.DEVELOPER
    raise UserAdministrationValidationError(
        "ROLE_INVALID",
        messages.REQUIRED_FIELDS,
        {"role": messages.REQUIRED_FIELDS},
    )


def _validate_name_email(*, name: str, email: str) -> tuple[str, str]:
    clean_name = name.strip()
    clean_email = normalize_email(email.strip())
    if not clean_name:
        raise UserAdministrationValidationError(
            "NAME_REQUIRED", messages.NAME_REQUIRED, {"name": messages.NAME_REQUIRED}
        )
    if len(clean_name) > NAME_MAX_LENGTH:
        raise UserAdministrationValidationError(
            "NAME_TOO_LONG", messages.NAME_TOO_LONG, {"name": messages.NAME_TOO_LONG}
        )
    if not clean_email:
        raise UserAdministrationValidationError(
            "REQUIRED_FIELDS", messages.REQUIRED_FIELDS, {"email": messages.REQUIRED_FIELDS}
        )
    if not is_valid_email(clean_email):
        raise UserAdministrationValidationError(
            "EMAIL_INVALID", messages.EMAIL_INVALID, {"email": messages.EMAIL_INVALID}
        )
    return clean_name, clean_email


class _ActivationMailMixin:
    _users: UserRepository
    _tokens_repo: PasswordCredentialTokenRepository
    _tokens: SessionTokenService
    _mailer: TransactionalEmailSender
    _id_gen: IdGenerator
    _clock: Clock
    _uow: UnitOfWork
    _policy: CredentialTokenPolicy

    def _issue_activation(self, user: User) -> None:
        raw = self._tokens.new_token()
        now = self._clock.now()
        token = PasswordCredentialToken(
            id=self._id_gen.generate(),
            user_id=user.id,
            token_hash=self._tokens.digest(raw),
            purpose=CredentialTokenPurpose.ACTIVATION,
            created_at=now,
            expires_at=now + self._policy.activation_ttl,
        )
        with self._uow:
            self._tokens_repo.invalidate_active_for_user(user.id, CredentialTokenPurpose.ACTIVATION)
            self._tokens_repo.add(token)
            self._uow.commit()
        activation_url = (
            f"{self._policy.frontend_base_url.rstrip('/')}/establecer-contrasena"
            f"?token={raw}&purpose=activation"
        )
        self._mailer.send_account_activation(to_email=user.email, activation_url=activation_url)


class CreateUserByAdminUseCase(_ActivationMailMixin):
    """HU_DN_01_11 / HU_DN_01_13: admin creates Manager or Developer with activation link."""

    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: PasswordCredentialTokenRepository,
        tokens: SessionTokenService,
        mailer: TransactionalEmailSender,
        hasher: PasswordHasher,
        id_gen: IdGenerator,
        clock: Clock,
        uow: UnitOfWork,
        policy: CredentialTokenPolicy,
    ) -> None:
        self._users = user_repo
        self._tokens_repo = token_repo
        self._tokens = tokens
        self._mailer = mailer
        self._hasher = hasher
        self._id_gen = id_gen
        self._clock = clock
        self._uow = uow
        self._policy = policy

    def execute(self, *, actor_id: str, cmd: CreateUserByAdminCommand) -> MessageResponse:
        actor = self._users.get_by_id(actor_id)
        if actor is None or actor.role != UserRole.ADMIN:
            raise AccessDeniedError()

        if cmd.role is not None:
            _reject_admin_role(cmd.role)

        clean_name, clean_email = _validate_name_email(name=cmd.name, email=cmd.email)
        if not cmd.role or not cmd.role.strip():
            raise UserAdministrationValidationError(
                "REQUIRED_FIELDS", messages.REQUIRED_FIELDS, {"role": messages.REQUIRED_FIELDS}
            )
        role = _parse_staff_role(cmd.role)

        if self._users.get_by_email(clean_email) is not None:
            raise EmailAlreadyRegisteredError()

        now = self._clock.now()
        pending_secret = secrets.token_urlsafe(48)
        user = User(
            id=self._id_gen.generate(),
            email=clean_email,
            hashed_password=self._hasher.hash(pending_secret),
            name=clean_name,
            role=role,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        with self._uow:
            self._users.save(user)
            self._uow.commit()

        self._issue_activation(user)
        return MessageResponse(message=messages.USER_CREATED)


class InviteDeveloperByManagerUseCase(_ActivationMailMixin):
    """HU_DN_01_12: manager invites a Developer; role is forced server-side."""

    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: PasswordCredentialTokenRepository,
        tokens: SessionTokenService,
        mailer: TransactionalEmailSender,
        hasher: PasswordHasher,
        id_gen: IdGenerator,
        clock: Clock,
        uow: UnitOfWork,
        policy: CredentialTokenPolicy,
    ) -> None:
        self._users = user_repo
        self._tokens_repo = token_repo
        self._tokens = tokens
        self._mailer = mailer
        self._hasher = hasher
        self._id_gen = id_gen
        self._clock = clock
        self._uow = uow
        self._policy = policy

    def execute(self, *, actor_id: str, cmd: InviteDeveloperCommand) -> MessageResponse:
        actor = self._users.get_by_id(actor_id)
        if actor is None or actor.role != UserRole.MANAGER:
            raise AccessDeniedError()

        if cmd.role is not None:
            _reject_admin_role(cmd.role)
            if cmd.role.strip().lower() not in ("", UserRole.DEVELOPER.value):
                raise AccessDeniedError()

        clean_name, clean_email = _validate_name_email(name=cmd.name, email=cmd.email)
        if self._users.get_by_email(clean_email) is not None:
            raise EmailAlreadyRegisteredError()

        now = self._clock.now()
        pending_secret = secrets.token_urlsafe(48)
        user = User(
            id=self._id_gen.generate(),
            email=clean_email,
            hashed_password=self._hasher.hash(pending_secret),
            name=clean_name,
            role=UserRole.DEVELOPER,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        with self._uow:
            self._users.save(user)
            self._uow.commit()

        self._issue_activation(user)
        return MessageResponse(message=messages.INVITE_DEVELOPER_SUCCESS)


class ListAdminUsersUseCase:
    """HU_DN_01_14: admin lists users with optional filters; never exposes password hashes."""

    def __init__(self, user_repo: UserRepository) -> None:
        self._users = user_repo

    def execute(
        self,
        *,
        actor_id: str,
        name: str | None = None,
        role: str | None = None,
    ) -> list[AdminUserSummaryDTO]:
        actor = self._users.get_by_id(actor_id)
        if actor is None or actor.role != UserRole.ADMIN:
            raise AccessDeniedError()

        role_filter: str | None = None
        if role and role.strip().lower() not in ("", "all", "todos"):
            parsed = role.strip().lower()
            if parsed not in {
                UserRole.ADMIN.value,
                UserRole.MANAGER.value,
                UserRole.DEVELOPER.value,
            }:
                raise UserAdministrationValidationError(
                    "ROLE_INVALID",
                    messages.REQUIRED_FIELDS,
                    {"role": messages.REQUIRED_FIELDS},
                )
            role_filter = parsed

        name_filter = name.strip() if name and name.strip() else None
        users = self._users.list_filtered(name_contains=name_filter, role=role_filter)
        return [
            AdminUserSummaryDTO(
                id=u.id,
                name=u.name,
                email=u.email,
                role=u.role,
                is_active=u.is_active,
            )
            for u in users
        ]


class UpdateUserByAdminUseCase:
    """HU_DN_01_16: admin edits name, e-mail and role with business guards."""

    def __init__(
        self,
        user_repo: UserRepository,
        project_ownership: ProjectOwnershipQuery,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._users = user_repo
        self._project_ownership = project_ownership
        self._clock = clock
        self._uow = uow

    def execute(
        self, *, actor_id: str, user_id: str, cmd: UpdateUserByAdminCommand
    ) -> UpdateUserByAdminResponse:
        actor = self._users.get_by_id(actor_id)
        if actor is None or actor.role != UserRole.ADMIN:
            raise AccessDeniedError()

        target = self._users.get_by_id(user_id)
        if target is None:
            raise AppError("USER_NOT_FOUND", messages.USER_NOT_FOUND, ErrorKind.NOT_FOUND)

        clean_name, clean_email = _validate_name_email(name=cmd.name, email=cmd.email)
        if not cmd.role or not cmd.role.strip():
            raise UserAdministrationValidationError(
                "REQUIRED_FIELDS", messages.REQUIRED_FIELDS, {"role": messages.REQUIRED_FIELDS}
            )

        if target.role == UserRole.ADMIN:
            new_role = UserRole.ADMIN
        else:
            if cmd.role is not None:
                _reject_admin_role(cmd.role)
            new_role = _parse_staff_role(cmd.role)

        existing = self._users.get_by_email(clean_email)
        if existing is not None and existing.id != target.id:
            raise EmailAlreadyRegisteredError()

        if (
            target.role == UserRole.MANAGER
            and new_role != UserRole.MANAGER
            and self._project_ownership.user_owns_projects(target.id)
        ):
            raise ManagerRoleChangeBlockedError()

        now = self._clock.now()
        target.name = clean_name
        target.email = clean_email
        target.role = new_role
        target.updated_at = now

        with self._uow:
            self._users.update(target)
            self._uow.commit()

        return UpdateUserByAdminResponse(
            message=messages.USER_UPDATED,
            user=to_user_dto(target),
        )


class ListActiveManagersUseCase:
    """EP-03: active managers for project assignment dropdowns (admin/manager)."""

    def __init__(self, user_repo: UserRepository) -> None:
        self._users = user_repo

    def execute(self, *, actor_id: str) -> list[AdminUserSummaryDTO]:
        actor = self._users.get_by_id(actor_id)
        if actor is None or actor.role not in (UserRole.ADMIN, UserRole.MANAGER):
            raise AccessDeniedError()

        return [
            AdminUserSummaryDTO(
                id=user.id,
                name=user.name,
                email=user.email,
                role=user.role.value,
                is_active=user.is_active,
            )
            for user in self._users.list_active_managers()
        ]


class ListActiveUsersUseCase:
    """HU_DN_02_27: active users for adding project members (admin/manager)."""

    def __init__(self, user_repo: UserRepository) -> None:
        self._users = user_repo

    def execute(
        self, *, actor_id: str, query: str | None = None
    ) -> list[AdminUserSummaryDTO]:
        actor = self._users.get_by_id(actor_id)
        if actor is None or actor.role not in (UserRole.ADMIN, UserRole.MANAGER):
            raise AccessDeniedError()

        return [
            AdminUserSummaryDTO(
                id=user.id,
                name=user.name,
                email=user.email,
                role=user.role.value,
                is_active=user.is_active,
            )
            for user in self._users.list_active_users(name_contains=query)
        ]
