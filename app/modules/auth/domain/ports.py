"""
Repository and service ports for the Auth module domain.
@sad AD-09, 4.1.1
@origin [SAD-Propuesto]
"""

from datetime import datetime
from typing import Protocol

from app.modules.auth.domain.entities import LoginAttempt, User, UserSession


class UserRepository(Protocol):
    """Port for persisting and querying User domain entities."""

    def get_by_id(self, user_id: str) -> User | None: ...

    def get_by_email(self, email: str) -> User | None: ...

    def save(self, user: User) -> None: ...

    def update(self, user: User) -> None: ...


class SessionRepository(Protocol):
    """Port for server-side sessions (looked up by the hash of the opaque token)."""

    def add(self, session: UserSession) -> None: ...

    def get_by_token_hash(self, token_hash: str) -> UserSession | None: ...

    def update(self, session: UserSession) -> None: ...

    def purge_expired_before(self, moment: datetime) -> None: ...


class LoginAttemptRepository(Protocol):
    """Port for the brute-force protection ledger."""

    def add(self, attempt: LoginAttempt) -> None: ...

    def count_since(self, email: str, since: datetime) -> int: ...

    def delete(self, attempt_id: str) -> None: ...

    def clear_for(self, email: str) -> None: ...

    def purge_before(self, moment: datetime) -> None: ...


class SessionTokenService(Protocol):
    """Port that creates unguessable session tokens and their storable digest."""

    def new_token(self) -> str: ...

    def digest(self, token: str) -> str: ...
