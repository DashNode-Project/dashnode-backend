"""HU_DN_01_06, HU_DN_01_07, HU_DN_01_10 — password reset application tests."""

from datetime import timedelta

import pytest

from app.modules.auth.application.dtos import CompletePasswordResetCommand, RequestPasswordResetCommand
from app.modules.auth.application.password_reset_use_cases import (
    AdminRequestPasswordResetUseCase,
    CompletePasswordResetUseCase,
    CredentialTokenPolicy,
    RequestPasswordResetUseCase,
)
from app.modules.auth.domain import messages
from app.modules.auth.domain.entities import CredentialTokenPurpose, PasswordCredentialToken, UserRole
from app.modules.auth.domain.errors import (
    AdminResetDisabledTargetError,
    EmailSendFailedError,
    InvalidCredentialTokenError,
    PasswordResetValidationError,
)
from tests.fakes import (
    FakeClock,
    FakeIdGenerator,
    FakePasswordCredentialTokenRepository,
    FakePasswordHasher,
    FakeSessionTokenService,
    FakeTransactionalEmailSender,
    FakeUnitOfWork,
    FakeUserRepository,
    T0,
    make_user,
)

POLICY = CredentialTokenPolicy(
    reset_ttl=timedelta(hours=1),
    activation_ttl=timedelta(hours=24),
    frontend_base_url="http://localhost:5173",
)
PASSWORD = "Segura123"


def _request_uc(
    users: FakeUserRepository,
    tokens: FakePasswordCredentialTokenRepository,
    mailer: FakeTransactionalEmailSender,
) -> RequestPasswordResetUseCase:
    return RequestPasswordResetUseCase(
        user_repo=users,
        token_repo=tokens,
        tokens=FakeSessionTokenService(),
        mailer=mailer,
        id_gen=FakeIdGenerator(),
        clock=FakeClock(),
        uow=FakeUnitOfWork(),
        policy=POLICY,
    )


def test_request_password_reset_agnostic_success_when_email_unknown() -> None:
    mailer = FakeTransactionalEmailSender()
    result = _request_uc(FakeUserRepository(), FakePasswordCredentialTokenRepository(), mailer).execute(
        RequestPasswordResetCommand(email="unknown@example.com")
    )
    assert result.message == messages.PASSWORD_RESET_REQUEST_SUCCESS
    assert mailer.sent == []


def test_request_password_reset_sends_mail_for_active_user() -> None:
    users = FakeUserRepository()
    users.save(make_user(email="ana@empresa.com"))
    mailer = FakeTransactionalEmailSender()
    _request_uc(users, FakePasswordCredentialTokenRepository(), mailer).execute(
        RequestPasswordResetCommand(email="ana@empresa.com")
    )
    assert len(mailer.sent) == 1
    assert mailer.sent[0][0] == "ana@empresa.com"
    assert "token-1" in mailer.sent[0][1]


def test_request_password_reset_invalid_email_format() -> None:
    with pytest.raises(PasswordResetValidationError) as exc:
        _request_uc(
            FakeUserRepository(), FakePasswordCredentialTokenRepository(), FakeTransactionalEmailSender()
        ).execute(RequestPasswordResetCommand(email="not-an-email"))
    assert exc.value.fields["email"] == messages.EMAIL_INVALID


def test_request_password_reset_email_failure() -> None:
    users = FakeUserRepository()
    users.save(make_user(email="ana@empresa.com"))
    with pytest.raises(EmailSendFailedError):
        _request_uc(
            users, FakePasswordCredentialTokenRepository(), FakeTransactionalEmailSender(fail=True)
        ).execute(RequestPasswordResetCommand(email="ana@empresa.com"))


def test_complete_password_reset_success() -> None:
    users = FakeUserRepository()
    user = make_user(email="ana@empresa.com", password="OldPass1")
    users.save(user)
    token_svc = FakeSessionTokenService()
    raw = token_svc.new_token()
    tokens = FakePasswordCredentialTokenRepository()
    tokens.add(
        PasswordCredentialToken(
            id="tok-1",
            user_id=user.id,
            token_hash=token_svc.digest(raw),
            purpose=CredentialTokenPurpose.PASSWORD_RESET,
            created_at=T0,
            expires_at=T0 + timedelta(hours=1),
        )
    )
    hasher = FakePasswordHasher()
    uc = CompletePasswordResetUseCase(
        user_repo=users,
        token_repo=tokens,
        tokens=token_svc,
        hasher=hasher,
        clock=FakeClock(),
        uow=FakeUnitOfWork(),
    )
    result = uc.execute(
        CompletePasswordResetCommand(
            token=raw, password=PASSWORD, confirm_password=PASSWORD
        )
    )
    assert result.message == messages.PASSWORD_SET_SUCCESS
    assert users.get_by_id(user.id).hashed_password == hasher.hash(PASSWORD)
    assert tokens.get_by_token_hash(token_svc.digest(raw)).is_used()


def test_complete_password_reset_rejects_reuse() -> None:
    users = FakeUserRepository()
    user = make_user(email="ana@empresa.com")
    users.save(user)
    token_svc = FakeSessionTokenService()
    raw = token_svc.new_token()
    stored = PasswordCredentialToken(
        id="tok-1",
        user_id=user.id,
        token_hash=token_svc.digest(raw),
        purpose=CredentialTokenPurpose.PASSWORD_RESET,
        created_at=T0,
        expires_at=T0 + timedelta(hours=1),
        used_at=T0,
    )
    tokens = FakePasswordCredentialTokenRepository()
    tokens.add(stored)
    uc = CompletePasswordResetUseCase(
        user_repo=users,
        token_repo=tokens,
        tokens=token_svc,
        hasher=FakePasswordHasher(),
        clock=FakeClock(),
        uow=FakeUnitOfWork(),
    )
    with pytest.raises(InvalidCredentialTokenError):
        uc.execute(
            CompletePasswordResetCommand(
                token=raw, password=PASSWORD, confirm_password=PASSWORD
            )
        )


def test_admin_reset_rejects_disabled_user() -> None:
    users = FakeUserRepository()
    admin = make_user(user_id="admin-1", email="admin@x.com", role=UserRole.ADMIN)
    target = make_user(user_id="u-2", email="u@x.com", is_active=False)
    users.save(admin)
    users.save(target)
    uc = AdminRequestPasswordResetUseCase(
        actor_repo=users,
        user_repo=users,
        token_repo=FakePasswordCredentialTokenRepository(),
        tokens=FakeSessionTokenService(),
        mailer=FakeTransactionalEmailSender(),
        id_gen=FakeIdGenerator(),
        clock=FakeClock(),
        uow=FakeUnitOfWork(),
        policy=POLICY,
    )
    with pytest.raises(AdminResetDisabledTargetError):
        uc.execute(actor_id=admin.id, target_user_id=target.id)
