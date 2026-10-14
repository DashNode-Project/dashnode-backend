"""
In-memory test doubles for the application ports (shared by application tests).
"""

from datetime import UTC, datetime, timedelta

from app.modules.auth.domain.entities import (
    CredentialTokenPurpose,
    LoginAttempt,
    PasswordCredentialToken,
    User,
    UserRole,
    UserSession,
)
from app.modules.auth.domain.errors import EmailAlreadyRegisteredError
from app.shared.application.ports import UnitOfWork

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


class FakeUserRepository:
    def __init__(self) -> None:
        self.users_by_id: dict[str, User] = {}
        self.users_by_email: dict[str, User] = {}

    def get_by_id(self, user_id: str) -> User | None:
        return self.users_by_id.get(user_id)

    def get_by_email(self, email: str) -> User | None:
        return self.users_by_email.get(email)

    def save(self, user: User) -> None:
        if user.email in self.users_by_email and self.users_by_email[user.email].id != user.id:
            raise EmailAlreadyRegisteredError
        self.users_by_id[user.id] = user
        self.users_by_email[user.email] = user

    def update(self, user: User) -> None:
        self.users_by_id[user.id] = user
        self.users_by_email[user.email] = user

    def list_all(self) -> list[User]:
        return self.list_filtered()

    def list_filtered(
        self, *, name_contains: str | None = None, role: str | None = None
    ) -> list[User]:
        users = list(self.users_by_id.values())
        if name_contains:
            needle = name_contains.lower()
            users = [u for u in users if needle in u.name.lower()]
        if role:
            users = [u for u in users if u.role.value == role]
        return sorted(users, key=lambda u: (u.name, u.email))

    def list_active_managers(self) -> list[User]:
        return [u for u in self.users_by_id.values() if u.role.value == "manager" and u.is_active]

    def list_active_users(self, *, name_contains: str | None = None) -> list[User]:
        users = [u for u in self.users_by_id.values() if u.is_active]
        if name_contains:
            needle = name_contains.lower()
            users = [u for u in users if needle in u.name.lower() or needle in u.email.lower()]
        return sorted(users, key=lambda u: (u.name, u.email))

    def list_developers_invited_by(self, manager_id: str) -> list[User]:
        users = [
            u
            for u in self.users_by_id.values()
            if u.invited_by_user_id == manager_id and u.role == UserRole.DEVELOPER
        ]
        return sorted(users, key=lambda u: (u.name, u.email))


class FakeClock:
    def __init__(self, fixed_now: datetime = T0) -> None:
        self.fixed_now = fixed_now

    def now(self) -> datetime:
        return self.fixed_now

    def advance(self, **delta: float) -> None:
        self.fixed_now += timedelta(**delta)


class FakeIdGenerator:
    """Deterministic ids: id-1, id-2, ... (or a fixed one when provided)."""

    def __init__(self, fixed_id: str | None = None) -> None:
        self._fixed = fixed_id
        self._counter = 0

    def generate(self) -> str:
        if self._fixed is not None:
            return self._fixed
        self._counter += 1
        return f"id-{self._counter}"


class FakePasswordHasher:
    def __init__(self) -> None:
        self.dummy_calls = 0

    def hash(self, password: str) -> str:
        return f"hashed_{password}"

    def verify(self, password: str, hashed: str) -> bool:
        return hashed == f"hashed_{password}"

    def verify_dummy(self, password: str) -> None:
        self.dummy_calls += 1


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


def make_user(
    *,
    user_id: str = "usr-1",
    email: str = "user@example.com",
    password: str = "Password1",  # noqa: S107 - test literal
    role: UserRole = UserRole.MANAGER,
    is_active: bool = True,
    name: str = "Test User",
    hasher: FakePasswordHasher | None = None,
) -> User:
    return User(
        id=user_id,
        email=email,
        hashed_password=(hasher or FakePasswordHasher()).hash(password),
        name=name,
        role=role,
        is_active=is_active,
        created_at=T0,
        updated_at=T0,
    )


class FakeSessionRepository:
    def __init__(self) -> None:
        self.sessions: dict[str, UserSession] = {}

    def add(self, session: UserSession) -> None:
        self.sessions[session.id] = session

    def get_by_token_hash(self, token_hash: str) -> UserSession | None:
        return next((s for s in self.sessions.values() if s.token_hash == token_hash), None)

    def update(self, session: UserSession) -> None:
        self.sessions[session.id] = session

    def purge_expired_before(self, moment: datetime) -> None:
        self.sessions = {k: s for k, s in self.sessions.items() if s.expires_at >= moment}

    def revoke_all_active_for_user(self, user_id: str, when: datetime) -> None:
        for session in self.sessions.values():
            if session.user_id == user_id and session.revoked_at is None:
                session.revoke(when)


class FakeLoginAttemptRepository:
    def __init__(self) -> None:
        self.attempts: dict[str, LoginAttempt] = {}

    def add(self, attempt: LoginAttempt) -> None:
        self.attempts[attempt.id] = attempt

    def count_since(self, email: str, since: datetime) -> int:
        return sum(
            1 for a in self.attempts.values() if a.email == email and a.attempted_at >= since
        )

    def delete(self, attempt_id: str) -> None:
        self.attempts.pop(attempt_id, None)

    def clear_for(self, email: str) -> None:
        self.attempts = {k: a for k, a in self.attempts.items() if a.email != email}

    def purge_before(self, moment: datetime) -> None:
        self.attempts = {k: a for k, a in self.attempts.items() if a.attempted_at >= moment}


class FakeSessionTokenService:
    """Deterministic tokens: token-1, token-2, ...; digest is a visible transformation."""

    def __init__(self) -> None:
        self._counter = 0

    def new_token(self) -> str:
        self._counter += 1
        return f"token-{self._counter}"

    def digest(self, token: str) -> str:
        return f"digest::{token}"


class FakePasswordCredentialTokenRepository:
    def __init__(self) -> None:
        self.tokens: dict[str, PasswordCredentialToken] = {}

    def add(self, token: PasswordCredentialToken) -> None:
        self.tokens[token.id] = token

    def get_by_token_hash(self, token_hash: str) -> PasswordCredentialToken | None:
        return next((t for t in self.tokens.values() if t.token_hash == token_hash), None)

    def update(self, token: PasswordCredentialToken) -> None:
        self.tokens[token.id] = token

    def invalidate_active_for_user(self, user_id: str, purpose: CredentialTokenPurpose) -> None:
        for token in self.tokens.values():
            if token.user_id == user_id and token.purpose == purpose and token.used_at is None:
                token.used_at = T0


class FakeTransactionalEmailSender:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[tuple[str, str]] = []

    def send_password_reset(self, *, to_email: str, reset_url: str) -> None:
        if self.fail:
            from app.modules.auth.domain.errors import EmailSendFailedError

            raise EmailSendFailedError()
        self.sent.append((to_email, reset_url))

    def send_account_activation(self, *, to_email: str, activation_url: str) -> None:
        if self.fail:
            from app.modules.auth.domain.errors import EmailSendFailedError

            raise EmailSendFailedError()
        self.sent.append((to_email, activation_url))


class FakeProjectOwnershipQuery:
    def __init__(self, owns: bool = False) -> None:
        self.owns = owns
        self.checked: list[str] = []

    def user_owns_projects(self, user_id: str) -> bool:
        self.checked.append(user_id)
        return self.owns
