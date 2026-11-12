"""
Repository and service ports for the Auth module domain.
@sad AD-09, 4.1.1
@origin [SAD-Propuesto]
"""

from datetime import datetime
from typing import Protocol

from app.modules.auth.domain.entities import (
    CredentialTokenPurpose,
    LoginAttempt,
    PasswordCredentialToken,
    User,
    UserSession,
)


class UserRepository(Protocol):
    """Port for persisting and querying User domain entities."""

    def get_by_id(self, user_id: str) -> User | None: ...

    def get_by_email(self, email: str) -> User | None: ...

    def save(self, user: User) -> None: ...

    def update(self, user: User) -> None: ...

    def list_all(self) -> list[User]: ...

    def list_filtered(
        self, *, name_contains: str | None = None, role: str | None = None
    ) -> list[User]: ...

    def list_active_managers(self) -> list[User]: ...

    def list_active_users(self, *, name_contains: str | None = None) -> list[User]: ...

    def list_developers_invited_by(self, manager_id: str) -> list[User]: ...

    def delete(self, user_id: str) -> None: ...

    def list_invitation_housekeeping(self) -> list[User]: ...


class SessionRepository(Protocol):
    """Port for server-side sessions (looked up by the hash of the opaque token)."""

    def add(self, session: UserSession) -> None: ...

    def get_by_token_hash(self, token_hash: str) -> UserSession | None: ...

    def update(self, session: UserSession) -> None: ...

    def purge_expired_before(self, moment: datetime) -> None: ...

    def revoke_all_active_for_user(self, user_id: str, when: datetime) -> None: ...


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


class PasswordCredentialTokenRepository(Protocol):
    def add(self, token: PasswordCredentialToken) -> None: ...

    def get_by_token_hash(self, token_hash: str) -> PasswordCredentialToken | None: ...

    def update(self, token: PasswordCredentialToken) -> None: ...

    def invalidate_active_for_user(self, user_id: str, purpose: CredentialTokenPurpose) -> None: ...


class PendingAssignmentsQuery(Protocol):
    """Count of non-completed tasks assigned to a user (orchestration adapter)."""

    def count_pending_for_user(self, user_id: str) -> int: ...


class ProjectOwnershipQuery(Protocol):
    """Cross-module check: whether a user owns at least one project (orchestration adapter)."""

    def user_owns_projects(self, user_id: str) -> bool: ...

    def count_active_projects(self) -> int: ...


class TransactionalEmailSender(Protocol):
    """Sends password/activation links. Must not log message bodies with secrets."""

    def send_password_reset(self, *, to_email: str, reset_url: str) -> None: ...

    def send_account_activation(self, *, to_email: str, activation_url: str) -> None: ...

    def send_developer_invitation(
        self, *, to_email: str, invitation_url: str, verification_code: str
    ) -> None: ...
