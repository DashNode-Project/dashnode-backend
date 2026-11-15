"""
HU_DN_01_04 - Cerrar sesion (application layer).
Traceability: TK_DN_01_04_2, TK_DN_01_04_4.
"""

from datetime import timedelta

import pytest

from app.modules.auth.application.dtos import LoginCommand
from app.modules.auth.application.session_use_cases import LogoutUseCase
from app.modules.auth.domain.errors import NotAuthenticatedError
from tests.application.test_login_use_case import PASSWORD, POLICY, Harness


@pytest.fixture
def h() -> Harness:
    harness = Harness()
    harness.add_user()
    return harness


def _logout(h: Harness) -> LogoutUseCase:
    return LogoutUseCase(session_repo=h.sessions, tokens=h.tokens, clock=h.clock, uow=h.uow)


def _login(h: Harness) -> str:
    return h.login.execute(LoginCommand(email="ana@empresa.com", password=PASSWORD)).token


def test_logout_revokes_session_and_returns_literal_message(h: Harness) -> None:
    token = _login(h)

    result = _logout(h).execute(token)

    assert result.message == "Sesión cerrada correctamente."
    session = next(iter(h.sessions.sessions.values()))
    assert session.revoked_at == h.clock.now()


def test_revoked_session_cannot_be_reused(h: Harness) -> None:
    token = _login(h)
    _logout(h).execute(token)
    with pytest.raises(NotAuthenticatedError):
        h.authenticate.execute(token)


def test_logout_is_idempotent_and_keeps_first_revocation_time(h: Harness) -> None:
    token = _login(h)
    _logout(h).execute(token)
    first = next(iter(h.sessions.sessions.values())).revoked_at
    h.clock.advance(minutes=5)
    assert _logout(h).execute(token).message == "Sesión cerrada correctamente."
    assert next(iter(h.sessions.sessions.values())).revoked_at == first


@pytest.mark.parametrize("token", [None, "", "token-desconocido"])
def test_logout_without_valid_session_still_succeeds(h: Harness, token: str | None) -> None:
    assert _logout(h).execute(token).message == "Sesión cerrada correctamente."


def test_logout_of_expired_session_succeeds(h: Harness) -> None:
    token = _login(h)
    h.clock.advance(hours=9)
    assert _logout(h).execute(token).message == "Sesión cerrada correctamente."


def test_logout_only_affects_the_given_session(h: Harness) -> None:
    first, second = _login(h), _login(h)
    _logout(h).execute(first)
    assert h.authenticate.execute(second)
    with pytest.raises(NotAuthenticatedError):
        h.authenticate.execute(first)


def test_policy_ttl_is_not_extended_by_logout_flow(h: Harness) -> None:
    token = _login(h)
    _logout(h).execute(token)
    session = next(iter(h.sessions.sessions.values()))
    assert session.expires_at - session.created_at == POLICY.session_ttl == timedelta(hours=8)
