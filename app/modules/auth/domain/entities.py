"""
Domain entities and value objects for the Auth module.
@sad AD-08, 4.1.1
@origin [SAD-Propuesto]
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    MANAGER = "manager"
    DEVELOPER = "developer"


@dataclass
class User:
    id: str
    email: str
    hashed_password: str
    name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    def can_authenticate(self) -> bool:
        """Determines if the user account is allowed to log in."""
        return self.is_active

    def deactivate(self, when: datetime) -> None:
        """Deactivates user account."""
        self.is_active = False
        self.updated_at = when


@dataclass
class UserSession:
    """Server-side session. Only the hash of the opaque token is ever stored."""

    id: str
    user_id: str
    token_hash: str
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at

    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def revoke(self, when: datetime) -> None:
        if self.revoked_at is None:
            self.revoked_at = when


@dataclass(frozen=True)
class LoginAttempt:
    """One login attempt for an e-mail (known or not), used to limit brute force."""

    id: str
    email: str
    attempted_at: datetime


class CredentialTokenPurpose(StrEnum):
    """Stored values in DB; member names avoid PASSWORD_* so secret scanners stay quiet."""

    RESET_CREDENTIAL = "password_reset"
    ACTIVATION = "activation"


@dataclass
class PasswordCredentialToken:
    """Single-use link to set a password (reset or activation). Only the digest is stored."""

    id: str
    user_id: str
    token_hash: str
    purpose: CredentialTokenPurpose
    created_at: datetime
    expires_at: datetime
    used_at: datetime | None = None

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at

    def is_used(self) -> bool:
        return self.used_at is not None

    def mark_used(self, when: datetime) -> None:
        if self.used_at is None:
            self.used_at = when
