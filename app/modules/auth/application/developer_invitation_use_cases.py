"""Manager developer invitations: consent, one-time code, and expiry (no shared password)."""

import secrets
from datetime import timedelta

from app.modules.auth.application.dtos import (
    ActivateInvitationCommand,
    InvitationDecisionCommand,
    MessageResponse,
)
from app.modules.auth.application.password_reset_use_cases import CredentialTokenPolicy
from app.modules.auth.domain import messages
from app.modules.auth.domain.entities import (
    CredentialTokenPurpose,
    PasswordCredentialToken,
    UserRole,
)
from app.modules.auth.domain.errors import (
    EmailSendFailedError,
    InvalidCredentialTokenError,
    PasswordResetValidationError,
)
from app.modules.auth.domain.ports import (
    PasswordCredentialTokenRepository,
    SessionTokenService,
    TransactionalEmailSender,
    UserRepository,
)
from app.modules.auth.domain.rules import is_valid_password
from app.shared.application.ports import Clock, IdGenerator, PasswordHasher, UnitOfWork
from app.shared.domain.authorization import AccessDeniedError
from app.shared.domain.errors import AppError, ErrorKind

INVITE_TTL = timedelta(hours=24)
REJECT_GRACE = timedelta(days=3)
MAX_RENEWALS = 3
MAX_CODE_ATTEMPTS = 5


def purge_stale_invitations(users: UserRepository, clock: Clock, uow: UnitOfWork) -> None:
    now = clock.now()
    doomed: list[str] = []
    for user in users.list_invitation_housekeeping():
        rejected_due = (
            user.invitation_status == "rejected"
            and user.invitation_rejected_at is not None
            and now >= user.invitation_rejected_at + REJECT_GRACE
        )
        pending_due = (
            user.invitation_status == "pending"
            and user.invitation_expires_at is not None
            and now >= user.invitation_expires_at
            and user.invitation_renewal_count >= MAX_RENEWALS
        )
        if rejected_due or pending_due:
            doomed.append(user.id)
    if not doomed:
        return
    with uow:
        for user_id in doomed:
            users.delete(user_id)
        uow.commit()


def _load_invite_token(
    tokens: SessionTokenService,
    token_repo: PasswordCredentialTokenRepository,
    raw: str,
    clock: Clock,
) -> PasswordCredentialToken:
    stored = token_repo.get_by_token_hash(tokens.digest(raw.strip()))
    now = clock.now()
    if (
        stored is None
        or stored.purpose != CredentialTokenPurpose.DEVELOPER_INVITE
        or stored.is_used()
        or stored.is_expired(now)
    ):
        raise InvalidCredentialTokenError()
    return stored


class DecideDeveloperInvitationUseCase:
    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: PasswordCredentialTokenRepository,
        tokens: SessionTokenService,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._users = user_repo
        self._tokens_repo = token_repo
        self._tokens = tokens
        self._clock = clock
        self._uow = uow

    def execute(self, cmd: InvitationDecisionCommand) -> MessageResponse:
        decision = cmd.decision.strip().lower()
        if decision not in ("accept", "reject"):
            raise AppError("INVITATION_DECISION", messages.REQUIRED_FIELDS, ErrorKind.VALIDATION)
        stored = _load_invite_token(self._tokens, self._tokens_repo, cmd.token, self._clock)
        user = self._users.get_by_id(stored.user_id)
        now = self._clock.now()
        if user is None or user.invitation_status != "pending":
            raise InvalidCredentialTokenError()
        if user.invitation_expires_at is not None and now >= user.invitation_expires_at:
            raise AppError("INVITATION_EXPIRED", messages.INVITATION_EXPIRED, ErrorKind.VALIDATION)
        if decision == "accept":
            return MessageResponse(message=messages.INVITATION_CONTINUE)
        user.invitation_status = "rejected"
        user.invitation_rejected_at = now
        user.is_active = False
        user.updated_at = now
        stored.mark_used(now)
        with self._uow:
            self._users.update(user)
            self._tokens_repo.update(stored)
            self._uow.commit()
        return MessageResponse(message=messages.INVITATION_REJECTED)


class ActivateDeveloperInvitationUseCase:
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

    def execute(self, cmd: ActivateInvitationCommand) -> MessageResponse:
        stored = _load_invite_token(self._tokens, self._tokens_repo, cmd.token, self._clock)
        user = self._users.get_by_id(stored.user_id)
        now = self._clock.now()
        if user is None or user.invitation_status != "pending" or user.invitation_code_hash is None:
            raise InvalidCredentialTokenError()
        if user.invitation_expires_at is not None and now >= user.invitation_expires_at:
            raise AppError("INVITATION_EXPIRED", messages.INVITATION_EXPIRED, ErrorKind.VALIDATION)
        if not is_valid_password(cmd.password):
            raise PasswordResetValidationError(
                "PASSWORD_WEAK",
                messages.PASSWORD_WEAK,
                {"password": messages.PASSWORD_WEAK},
            )
        if cmd.password != cmd.confirm_password:
            raise PasswordResetValidationError(
                "PASSWORD_MISMATCH",
                messages.PASSWORD_MISMATCH,
                {"confirm_password": messages.PASSWORD_MISMATCH},
            )
        code = cmd.code.strip()
        if not self._hasher.verify(code, user.invitation_code_hash):
            user.invitation_code_attempts += 1
            user.updated_at = now
            with self._uow:
                self._users.update(user)
                if user.invitation_code_attempts >= MAX_CODE_ATTEMPTS:
                    stored.mark_used(now)
                    self._tokens_repo.update(stored)
                self._uow.commit()
            raise AppError(
                "INVITATION_CODE_INVALID",
                messages.INVITATION_CODE_INVALID,
                ErrorKind.VALIDATION,
            )
        user.hashed_password = self._hasher.hash(cmd.password)
        user.is_active = True
        user.invitation_status = "accepted"
        user.invitation_accepted_at = now
        user.invitation_code_hash = None
        user.invitation_code_attempts = 0
        user.updated_at = now
        stored.mark_used(now)
        with self._uow:
            self._users.update(user)
            self._tokens_repo.update(stored)
            self._uow.commit()
        return MessageResponse(message=messages.INVITATION_ACTIVATED)


class RenewDeveloperInvitationUseCase:
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

    def execute(self, *, actor_id: str, target_user_id: str) -> MessageResponse:
        purge_stale_invitations(self._users, self._clock, self._uow)
        actor = self._users.get_by_id(actor_id)
        if actor is None or actor.role != UserRole.MANAGER:
            raise AccessDeniedError()
        user = self._users.get_by_id(target_user_id)
        if user is None or user.invited_by_user_id != actor_id:
            raise AccessDeniedError()
        now = self._clock.now()
        if user.invitation_status != "pending":
            raise AppError("INVITATION_EXPIRED", messages.INVITATION_EXPIRED, ErrorKind.VALIDATION)
        if user.invitation_expires_at is not None and now < user.invitation_expires_at:
            raise AppError(
                "INVITATION_STILL_VALID", messages.INVITATION_STILL_VALID, ErrorKind.VALIDATION
            )
        if user.invitation_renewal_count >= MAX_RENEWALS:
            with self._uow:
                self._users.delete(user.id)
                self._uow.commit()
            return MessageResponse(message=messages.INVITATION_REMOVED)

        code = f"{secrets.randbelow(1_000_000):06d}"
        raw = self._tokens.new_token()
        user.invitation_renewal_count += 1
        user.invitation_expires_at = now + INVITE_TTL
        user.invitation_code_hash = self._hasher.hash(code)
        user.invitation_code_attempts = 0
        user.updated_at = now
        token = PasswordCredentialToken(
            id=self._id_gen.generate(),
            user_id=user.id,
            token_hash=self._tokens.digest(raw),
            purpose=CredentialTokenPurpose.DEVELOPER_INVITE,
            created_at=now,
            expires_at=now + INVITE_TTL,
        )
        with self._uow:
            self._tokens_repo.invalidate_active_for_user(
                user.id, CredentialTokenPurpose.DEVELOPER_INVITE
            )
            self._users.update(user)
            self._tokens_repo.add(token)
            self._uow.commit()
        url = f"{self._policy.frontend_base_url.rstrip('/')}/invitacion?token={raw}"
        try:
            self._mailer.send_developer_invitation(
                to_email=user.email, invitation_url=url, verification_code=code
            )
        except EmailSendFailedError:
            raise
        return MessageResponse(message=messages.INVITATION_RENEWED)


class DeleteInvitedDeveloperByAdminUseCase:
    def __init__(self, user_repo: UserRepository, clock: Clock, uow: UnitOfWork) -> None:
        self._users = user_repo
        self._clock = clock
        self._uow = uow

    def execute(self, *, actor_id: str, target_user_id: str) -> MessageResponse:
        purge_stale_invitations(self._users, self._clock, self._uow)
        actor = self._users.get_by_id(actor_id)
        if actor is None or actor.role != UserRole.ADMIN:
            raise AccessDeniedError()
        user = self._users.get_by_id(target_user_id)
        if user is None:
            raise AppError("USER_NOT_FOUND", messages.USER_NOT_FOUND, ErrorKind.NOT_FOUND)
        if user.invitation_status not in ("pending", "rejected"):
            raise AccessDeniedError()
        with self._uow:
            self._users.delete(user.id)
            self._uow.commit()
        return MessageResponse(message=messages.INVITATION_REMOVED)
