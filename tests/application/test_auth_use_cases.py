"""
Application layer use-case tests for Auth module (legacy login, replaced in HU_DN_01_03).
Uses in-memory test doubles for pure port isolation.
@sad AD-09, 4.1.1
"""

import pytest

from app.modules.auth.application.dtos import LoginCommand
from app.modules.auth.application.use_cases import GetCurrentUserUseCase, LoginUseCase
from app.modules.auth.domain.entities import UserRole
from tests.fakes import FakePasswordHasher, FakeUserRepository, make_user


class FakeTokenService:
    def create_access_token(self, user_id: str, role: str, email: str, name: str = "") -> str:
        return f"token_for_{user_id}_{role}_{email}"

    def decode_token(self, token: str) -> dict[str, object] | None:
        return None


def _login_use_case(repo: FakeUserRepository) -> LoginUseCase:
    return LoginUseCase(
        user_repo=repo, hasher=FakePasswordHasher(), token_service=FakeTokenService()
    )


def test_login_success() -> None:
    repo = FakeUserRepository()
    repo.save(make_user(email="admin@example.com", password="adminpass123", role=UserRole.ADMIN))
    resp = _login_use_case(repo).execute(
        LoginCommand(email="admin@example.com", password="adminpass123")
    )
    assert resp.access_token == "token_for_usr-1_admin_admin@example.com"
    assert resp.token_type == "bearer"


def test_login_invalid_password() -> None:
    repo = FakeUserRepository()
    repo.save(make_user(email="admin@example.com", password="adminpass123"))
    with pytest.raises(ValueError, match="Credenciales inválidas"):
        _login_use_case(repo).execute(
            LoginCommand(email="admin@example.com", password="wrongpassword")
        )


def test_login_user_not_found() -> None:
    with pytest.raises(ValueError, match="Credenciales inválidas"):
        _login_use_case(FakeUserRepository()).execute(
            LoginCommand(email="unknown@example.com", password="anypassword")
        )


def test_login_inactive_user() -> None:
    repo = FakeUserRepository()
    repo.save(make_user(email="inactive@example.com", password="pass12345", is_active=False))
    with pytest.raises(ValueError, match="desactivada"):
        _login_use_case(repo).execute(
            LoginCommand(email="inactive@example.com", password="pass12345")
        )


def test_get_current_user_use_case() -> None:
    repo = FakeUserRepository()
    repo.save(
        make_user(
            user_id="usr-10", email="dev10@example.com", role=UserRole.DEVELOPER, name="User Ten"
        )
    )
    uc = GetCurrentUserUseCase(user_repo=repo)
    result = uc.execute("usr-10")
    assert result.id == "usr-10"
    assert result.email == "dev10@example.com"
    with pytest.raises(ValueError, match="no encontrado"):
        uc.execute("non-existent-id")
