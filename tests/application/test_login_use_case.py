"""
HU_DN_01_03 - Iniciar sesion (application layer).
Traceability: TK_DN_01_03_3 .. TK_DN_01_03_6.
"""

from datetime import timedelta

import pytest

from app.modules.auth.application.dtos import LoginCommand, SecurityPolicy
from app.modules.auth.application.session_use_cases import (
    AuthenticateSessionUseCase,
    LoginUseCase,
)
from app.modules.auth.domain.entities import UserRole
from app.modules.auth.domain.errors import (
    AccountDisabledError,
    InvalidCredentialsError,
    LoginAttemptsExceededError,
    LoginValidationError,
    NotAuthenticatedError,
    SessionExpiredError,
)
from tests.fakes import (
    FakeClock,
    FakeIdGenerator,
    FakeLoginAttemptRepository,
    FakePasswordHasher,
    FakeSessionRepository,
    FakeSessionTokenService,
    FakeUnitOfWork,
    FakeUserRepository,
    make_user,
)

POLICY = SecurityPolicy(
    session_ttl=timedelta(hours=8),
    session_retention=timedelta(hours=24),
    max_failed_attempts=5,
    attempt_window=timedelta(minutes=15),
)
PASSWORD = "Segura123"


class Harness:
    def __init__(self) -> None:
        self.users = FakeUserRepository()
        self.sessions = FakeSessionRepository()
        self.attempts = FakeLoginAttemptRepository()
        self.hasher = FakePasswordHasher()
        self.tokens = FakeSessionTokenService()
        self.clock = FakeClock()
        self.uow = FakeUnitOfWork()
        self.login = LoginUseCase(
            user_repo=self.users,
            session_repo=self.sessions,
            attempt_repo=self.attempts,
            hasher=self.hasher,
            tokens=self.tokens,
            id_gen=FakeIdGenerator(),
            clock=self.clock,
            uow=self.uow,
            policy=POLICY,
        )
        self.authenticate = AuthenticateSessionUseCase(
            user_repo=self.users, session_repo=self.sessions, tokens=self.tokens, clock=self.clock
        )

    def add_user(self, **kwargs: object) -> None:
        kwargs.setdefault("email", "ana@empresa.com")
        kwargs.setdefault("password", PASSWORD)
        self.users.save(make_user(hasher=self.hasher, **kwargs))  # type: ignore[arg-type]

    def attempt(self, password: str = PASSWORD, email: str = "ana@empresa.com") -> None:
        self.login.execute(LoginCommand(email=email, password=password))


@pytest.fixture
def h() -> Harness:
    return Harness()


def test_successful_login_opens_session_for_exactly_8_hours(h: Harness) -> None:
    h.add_user(role=UserRole.MANAGER)

    result = h.login.execute(LoginCommand(email="ana@empresa.com", password=PASSWORD))

    assert result.token == "token-1"
    assert result.session.user.role is UserRole.MANAGER
    assert result.session.expires_at == h.clock.now() + timedelta(hours=8)
    stored = next(iter(h.sessions.sessions.values()))
    assert stored.token_hash == "digest::token-1"  # only the digest is stored
    assert h.uow.committed is True


def test_token_is_not_part_of_the_repr_of_the_result(h: Harness) -> None:
    h.add_user()
    result = h.login.execute(LoginCommand(email="ana@empresa.com", password=PASSWORD))
    assert "token-1" not in repr(result)


def test_email_is_normalized_before_lookup(h: Harness) -> None:
    h.add_user()
    assert h.login.execute(LoginCommand(email="  ANA@Empresa.COM ", password=PASSWORD))


@pytest.mark.parametrize(
    ("email", "password", "code"),
    [
        ("", PASSWORD, "REQUIRED_FIELDS"),
        ("ana@empresa.com", "", "REQUIRED_FIELDS"),
        ("ana@empresa.com", "   ", "REQUIRED_FIELDS"),
        ("", "", "REQUIRED_FIELDS"),
        ("no-es-correo", PASSWORD, "EMAIL_INVALID"),
        ("a@b", PASSWORD, "EMAIL_INVALID"),
    ],
)
def test_blank_or_malformed_input_is_rejected_and_not_counted(
    h: Harness, email: str, password: str, code: str
) -> None:
    h.add_user()
    with pytest.raises(LoginValidationError) as caught:
        h.login.execute(LoginCommand(email=email, password=password))
    assert caught.value.code == code
    assert h.attempts.attempts == {}


def test_email_format_message_is_literal(h: Harness) -> None:
    with pytest.raises(LoginValidationError) as caught:
        h.attempt(email="malo")
    assert caught.value.message == "El correo electrónico ingresado no tiene un formato válido."


def test_wrong_password_and_unknown_email_are_indistinguishable(h: Harness) -> None:
    h.add_user()
    with pytest.raises(InvalidCredentialsError) as wrong_password:
        h.attempt(password="Equivocada1")
    with pytest.raises(InvalidCredentialsError) as unknown_email:
        h.attempt(email="nadie@empresa.com")
    assert wrong_password.value.message == unknown_email.value.message
    assert wrong_password.value.code == unknown_email.value.code == "INVALID_CREDENTIALS"
    assert (
        wrong_password.value.message == "Credenciales no válidas. Verifique su correo y contraseña."
    )
    assert wrong_password.value.fields == unknown_email.value.fields == {}
    assert h.sessions.sessions == {}


def test_unknown_email_still_spends_hashing_time(h: Harness) -> None:
    with pytest.raises(InvalidCredentialsError):
        h.attempt(email="nadie@empresa.com")
    assert h.hasher.dummy_calls == 1


def test_disabled_account_with_correct_password_gets_disabled_message(h: Harness) -> None:
    h.add_user(is_active=False)
    with pytest.raises(AccountDisabledError) as caught:
        h.attempt()
    assert caught.value.message == "Su cuenta está desactivada. Contacte al Administrador."
    assert h.sessions.sessions == {}


def test_disabled_account_with_wrong_password_does_not_reveal_status(h: Harness) -> None:
    h.add_user(is_active=False)
    with pytest.raises(InvalidCredentialsError):
        h.attempt(password="Equivocada1")


def test_sixth_failed_attempt_is_rejected_with_literal_message(h: Harness) -> None:
    h.add_user()
    for _ in range(5):
        with pytest.raises(InvalidCredentialsError):
            h.attempt(password="Equivocada1")

    with pytest.raises(LoginAttemptsExceededError) as caught:
        h.attempt(password="Equivocada1")
    assert (
        caught.value.message
        == "Ha superado el número de intentos permitidos. Intente nuevamente más tarde."
    )


def test_correct_password_is_refused_while_locked_and_lock_is_not_extended(h: Harness) -> None:
    h.add_user()
    for _ in range(5):
        with pytest.raises(InvalidCredentialsError):
            h.attempt(password="Equivocada1")
    for _ in range(3):  # hammering during the lock must neither succeed nor extend it
        with pytest.raises(LoginAttemptsExceededError):
            h.attempt()
    assert len(h.attempts.attempts) == 5

    h.clock.advance(minutes=15, seconds=1)
    assert h.login.execute(LoginCommand(email="ana@empresa.com", password=PASSWORD))


def test_fifth_attempt_may_still_succeed(h: Harness) -> None:
    h.add_user()
    for _ in range(4):
        with pytest.raises(InvalidCredentialsError):
            h.attempt(password="Equivocada1")
    assert h.login.execute(LoginCommand(email="ana@empresa.com", password=PASSWORD))


def test_success_resets_the_failure_counter(h: Harness) -> None:
    h.add_user()
    for _ in range(4):
        with pytest.raises(InvalidCredentialsError):
            h.attempt(password="Equivocada1")
    h.attempt()
    for _ in range(5):
        with pytest.raises(InvalidCredentialsError):
            h.attempt(password="Equivocada1")
    with pytest.raises(LoginAttemptsExceededError):
        h.attempt(password="Equivocada1")


def test_limit_is_per_account_and_also_applies_to_unknown_emails(h: Harness) -> None:
    h.add_user()
    h.add_user(user_id="usr-2", email="otro@empresa.com")
    for _ in range(5):
        with pytest.raises(InvalidCredentialsError):
            h.attempt(password="Equivocada1")
    assert h.login.execute(LoginCommand(email="otro@empresa.com", password=PASSWORD))

    for _ in range(5):
        with pytest.raises(InvalidCredentialsError):
            h.attempt(email="fantasma@empresa.com")
    with pytest.raises(LoginAttemptsExceededError):  # same behaviour: no enumeration
        h.attempt(email="fantasma@empresa.com")


def test_old_failures_leave_the_window(h: Harness) -> None:
    h.add_user()
    for _ in range(5):
        with pytest.raises(InvalidCredentialsError):
            h.attempt(password="Equivocada1")
    h.clock.advance(minutes=15, seconds=1)
    with pytest.raises(InvalidCredentialsError):  # counted again from zero
        h.attempt(password="Equivocada1")


def test_login_purges_sessions_older_than_cookie_retention(h: Harness) -> None:
    h.add_user()
    h.login.execute(LoginCommand(email="ana@empresa.com", password=PASSWORD))
    h.clock.advance(hours=8 + 24, minutes=1)
    h.login.execute(LoginCommand(email="ana@empresa.com", password=PASSWORD))
    assert len(h.sessions.sessions) == 1


# --- session validation -----------------------------------------------------------


def test_authenticate_returns_user_and_expiry(h: Harness) -> None:
    h.add_user(role=UserRole.MANAGER)
    result = h.login.execute(LoginCommand(email="ana@empresa.com", password=PASSWORD))
    info = h.authenticate.execute(result.token)
    assert info.user.email == "ana@empresa.com"
    assert info.expires_at == result.session.expires_at


@pytest.mark.parametrize("token", [None, "", "desconocido"])
def test_authenticate_rejects_missing_or_unknown_token(h: Harness, token: str | None) -> None:
    with pytest.raises(NotAuthenticatedError):
        h.authenticate.execute(token)


def test_session_is_valid_until_the_exact_expiry_instant(h: Harness) -> None:
    h.add_user()
    token = h.login.execute(LoginCommand(email="ana@empresa.com", password=PASSWORD)).token
    h.clock.advance(hours=7, minutes=59, seconds=59)
    assert h.authenticate.execute(token)
    h.clock.advance(seconds=1)
    with pytest.raises(SessionExpiredError) as caught:
        h.authenticate.execute(token)
    assert caught.value.message == "Su sesión ha expirado. Inicie sesión nuevamente."


def test_session_does_not_slide_with_activity(h: Harness) -> None:
    h.add_user()
    token = h.login.execute(LoginCommand(email="ana@empresa.com", password=PASSWORD)).token
    for _ in range(7):
        h.clock.advance(hours=1)
        h.authenticate.execute(token)
    h.clock.advance(hours=1)
    with pytest.raises(SessionExpiredError):
        h.authenticate.execute(token)


def test_revoked_session_is_rejected(h: Harness) -> None:
    h.add_user()
    token = h.login.execute(LoginCommand(email="ana@empresa.com", password=PASSWORD)).token
    session = next(iter(h.sessions.sessions.values()))
    session.revoke(h.clock.now())
    with pytest.raises(NotAuthenticatedError):
        h.authenticate.execute(token)


def test_session_of_user_disabled_after_login_is_rejected(h: Harness) -> None:
    h.add_user()
    token = h.login.execute(LoginCommand(email="ana@empresa.com", password=PASSWORD)).token
    user = h.users.get_by_email("ana@empresa.com")
    assert user is not None
    user.deactivate(h.clock.now())
    with pytest.raises(AccountDisabledError):
        h.authenticate.execute(token)


def test_session_of_deleted_user_is_rejected(h: Harness) -> None:
    h.add_user()
    token = h.login.execute(LoginCommand(email="ana@empresa.com", password=PASSWORD)).token
    h.users.users_by_id.clear()
    with pytest.raises(NotAuthenticatedError):
        h.authenticate.execute(token)
