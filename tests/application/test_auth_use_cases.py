"""
Application layer use-case tests for Auth module.
Uses in-memory test doubles for pure port isolation.
@sad AD-09, 4.1.1
"""

from datetime import UTC, datetime

import pytest

from app.modules.auth.application.dtos import LoginCommand, RegisterUserCommand
from app.modules.auth.application.use_cases import (
    GetCurrentUserUseCase,
    LoginUseCase,
    RegisterUserUseCase,
)
from app.modules.auth.domain.entities import User, UserRole
from app.shared.application.ports import UnitOfWork


class FakeUserRepository:
    def __init__(self) -> None:
        self.users_by_id: dict[str, User] = {}
        self.users_by_email: dict[str, User] = {}

    def get_by_id(self, user_id: str) -> User | None:
        return self.users_by_id.get(user_id)

    def get_by_email(self, email: str) -> User | None:
        return self.users_by_email.get(email)

    def save(self, user: User) -> None:
        self.users_by_id[user.id] = user
        self.users_by_email[user.email] = user

    def update(self, user: User) -> None:
        self.save(user)


class FakeClock:
    def __init__(self, fixed_now: datetime) -> None:
        self.fixed_now = fixed_now

    def now(self) -> datetime:
        return self.fixed_now


class FakeIdGenerator:
    def __init__(self, fixed_id: str = "fixed-uuid-1") -> None:
        self.fixed_id = fixed_id

    def generate(self) -> str:
        return self.fixed_id


class FakePasswordHasher:
    def hash(self, password: str) -> str:
        return f"hashed_{password}"

    def verify(self, password: str, hashed: str) -> bool:
        return hashed == f"hashed_{password}"


class FakeUnitOfWork(UnitOfWork):
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    def __enter__(self) -> "FakeUnitOfWork":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        if exc_type is not None:
            self.rollback()

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class FakeTokenService:
    def create_access_token(self, user_id: str, role: str, email: str, name: str = "") -> str:
        return f"token_for_{user_id}_{role}_{email}"

    def decode_token(self, token: str) -> dict[str, object] | None:
        if token.startswith("token_for_"):
            parts = token.split("_")
            return {"sub": parts[2], "role": parts[3], "email": parts[4]}
        return None


def test_register_user_success() -> None:
    repo = FakeUserRepository()
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    id_gen = FakeIdGenerator("user-123")
    hasher = FakePasswordHasher()
    uow = FakeUnitOfWork()

    use_case = RegisterUserUseCase(
        user_repo=repo,
        hasher=hasher,
        id_gen=id_gen,
        clock=clock,
        uow=uow,
    )

    cmd = RegisterUserCommand(
        email="dev@example.com",
        password="secretpassword",
        name="Developer One",
        role=UserRole.DEVELOPER,
    )

    result = use_case.execute(cmd)

    assert result.id == "user-123"
    assert result.email == "dev@example.com"
    assert result.name == "Developer One"
    assert result.role == UserRole.DEVELOPER
    assert result.is_active is True
    assert uow.committed is True

    # User persisted
    persisted = repo.get_by_id("user-123")
    assert persisted is not None
    assert persisted.hashed_password == "hashed_secretpassword"


def test_register_user_duplicate_email() -> None:
    repo = FakeUserRepository()
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    id_gen = FakeIdGenerator("user-123")
    hasher = FakePasswordHasher()
    uow = FakeUnitOfWork()

    use_case = RegisterUserUseCase(
        user_repo=repo,
        hasher=hasher,
        id_gen=id_gen,
        clock=clock,
        uow=uow,
    )

    cmd = RegisterUserCommand(
        email="dev@example.com",
        password="secretpassword",
        name="Developer One",
    )
    use_case.execute(cmd)

    with pytest.raises(ValueError, match="ya se encuentra registrado"):
        use_case.execute(cmd)


def test_login_success() -> None:
    repo = FakeUserRepository()
    hasher = FakePasswordHasher()
    token_svc = FakeTokenService()

    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    user = User(
        id="usr-1",
        email="admin@example.com",
        hashed_password=hasher.hash("adminpass123"),
        name="Admin",
        role=UserRole.ADMIN,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    repo.save(user)

    login_uc = LoginUseCase(user_repo=repo, hasher=hasher, token_service=token_svc)
    cmd = LoginCommand(email="admin@example.com", password="adminpass123")
    resp = login_uc.execute(cmd)

    assert resp.access_token == "token_for_usr-1_admin_admin@example.com"
    assert resp.token_type == "bearer"


def test_login_invalid_password() -> None:
    repo = FakeUserRepository()
    hasher = FakePasswordHasher()
    token_svc = FakeTokenService()

    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    user = User(
        id="usr-1",
        email="admin@example.com",
        hashed_password=hasher.hash("adminpass123"),
        name="Admin",
        role=UserRole.ADMIN,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    repo.save(user)

    login_uc = LoginUseCase(user_repo=repo, hasher=hasher, token_service=token_svc)
    cmd = LoginCommand(email="admin@example.com", password="wrongpassword")
    with pytest.raises(ValueError, match="Credenciales inválidas"):
        login_uc.execute(cmd)


def test_login_user_not_found() -> None:
    repo = FakeUserRepository()
    hasher = FakePasswordHasher()
    token_svc = FakeTokenService()

    login_uc = LoginUseCase(user_repo=repo, hasher=hasher, token_service=token_svc)
    cmd = LoginCommand(email="unknown@example.com", password="anypassword")
    with pytest.raises(ValueError, match="Credenciales inválidas"):
        login_uc.execute(cmd)


def test_login_inactive_user() -> None:
    repo = FakeUserRepository()
    hasher = FakePasswordHasher()
    token_svc = FakeTokenService()

    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    user = User(
        id="usr-1",
        email="inactive@example.com",
        hashed_password=hasher.hash("pass12345"),
        name="Inactive",
        role=UserRole.DEVELOPER,
        is_active=False,
        created_at=now,
        updated_at=now,
    )
    repo.save(user)

    login_uc = LoginUseCase(user_repo=repo, hasher=hasher, token_service=token_svc)
    cmd = LoginCommand(email="inactive@example.com", password="pass12345")
    with pytest.raises(ValueError, match="desactivada"):
        login_uc.execute(cmd)


def test_get_current_user_use_case() -> None:
    repo = FakeUserRepository()
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    user = User(
        id="usr-10",
        email="dev10@example.com",
        hashed_password="hash",
        name="User Ten",
        role=UserRole.DEVELOPER,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    repo.save(user)

    uc = GetCurrentUserUseCase(user_repo=repo)
    result = uc.execute("usr-10")
    assert result.id == "usr-10"
    assert result.email == "dev10@example.com"

    with pytest.raises(ValueError, match="no encontrado"):
        uc.execute("non-existent-id")
