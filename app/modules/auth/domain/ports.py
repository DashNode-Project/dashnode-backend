"""
Repository and service ports for the Auth module domain.
@sad AD-09, 4.1.1
@origin [SAD-Propuesto]
"""

from typing import Protocol

from app.modules.auth.domain.entities import User


class UserRepository(Protocol):
    """Port for persisting and querying User domain entities."""

    def get_by_id(self, user_id: str) -> User | None: ...

    def get_by_email(self, email: str) -> User | None: ...

    def save(self, user: User) -> None: ...

    def update(self, user: User) -> None: ...


class TokenService(Protocol):
    """Port for signing and verifying security tokens."""

    def create_access_token(self, user_id: str, role: str, email: str, name: str = "") -> str: ...

    def decode_token(self, token: str) -> dict[str, object] | None: ...
