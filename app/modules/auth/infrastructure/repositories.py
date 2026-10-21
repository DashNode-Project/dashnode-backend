"""
SQLAlchemy repository implementation for Users.
@sad AD-09, 5.6
@origin [SAD-Propuesto]
"""

from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.domain.entities import (
    CredentialTokenPurpose,
    LoginAttempt,
    PasswordCredentialToken,
    User,
    UserRole,
    UserSession,
)
from app.modules.auth.domain.errors import EmailAlreadyRegisteredError
from app.modules.auth.domain.ports import (
    LoginAttemptRepository,
    PasswordCredentialTokenRepository,
    SessionRepository,
    UserRepository,
)
from app.modules.auth.infrastructure.models import (
    LoginAttemptModel,
    PasswordCredentialTokenModel,
    SessionModel,
    UserModel,
)


class SqlAlchemyUserRepository(UserRepository):
    """SQLAlchemy implementation of the UserRepository port."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _to_domain(self, model: UserModel) -> User:
        return User(
            id=model.id,
            email=model.email,
            hashed_password=model.hashed_password,
            name=model.name,
            role=UserRole(model.role),
            is_active=model.is_active,
            avatar_key=model.avatar_key,
            invited_by_user_id=model.invited_by_user_id,
            invitation_accepted_at=model.invitation_accepted_at,
            profile_details=dict(model.profile_details or {}),
            invitation_status=model.invitation_status or "accepted",
            invitation_expires_at=model.invitation_expires_at,
            invitation_rejected_at=model.invitation_rejected_at,
            invitation_renewal_count=model.invitation_renewal_count or 0,
            invitation_code_hash=model.invitation_code_hash,
            invitation_code_attempts=model.invitation_code_attempts or 0,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def get_by_id(self, user_id: str) -> User | None:
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = self._session.execute(stmt).scalar_one_or_none()
        if result is None:
            return None
        return self._to_domain(result)

    def get_by_email(self, email: str) -> User | None:
        stmt = select(UserModel).where(UserModel.email == email)
        result = self._session.execute(stmt).scalar_one_or_none()
        if result is None:
            return None
        return self._to_domain(result)

    def save(self, user: User) -> None:
        model = UserModel(
            id=user.id,
            email=user.email,
            hashed_password=user.hashed_password,
            name=user.name,
            role=user.role.value,
            is_active=user.is_active,
            avatar_key=user.avatar_key,
            invited_by_user_id=user.invited_by_user_id,
            invitation_accepted_at=user.invitation_accepted_at,
            profile_details=user.profile_details or {},
            invitation_status=user.invitation_status,
            invitation_expires_at=user.invitation_expires_at,
            invitation_rejected_at=user.invitation_rejected_at,
            invitation_renewal_count=user.invitation_renewal_count,
            invitation_code_hash=user.invitation_code_hash,
            invitation_code_attempts=user.invitation_code_attempts,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
        self._session.add(model)
        try:
            self._session.flush()
        except IntegrityError as error:
            # Unique index on email: a concurrent registration won the race.
            raise EmailAlreadyRegisteredError from error

    def update(self, user: User) -> None:
        stmt = select(UserModel).where(UserModel.id == user.id)
        model = self._session.execute(stmt).scalar_one_or_none()
        if model is not None:
            model.email = user.email
            model.hashed_password = user.hashed_password
            model.name = user.name
            model.role = user.role.value
            model.is_active = user.is_active
            model.avatar_key = user.avatar_key
            model.invited_by_user_id = user.invited_by_user_id
            model.invitation_accepted_at = user.invitation_accepted_at
            model.invitation_status = user.invitation_status
            model.invitation_expires_at = user.invitation_expires_at
            model.invitation_rejected_at = user.invitation_rejected_at
            model.invitation_renewal_count = user.invitation_renewal_count
            model.invitation_code_hash = user.invitation_code_hash
            model.invitation_code_attempts = user.invitation_code_attempts
            model.profile_details = user.profile_details or {}
            model.updated_at = user.updated_at

    def list_developers_invited_by(self, manager_id: str) -> list[User]:
        stmt = (
            select(UserModel)
            .where(
                UserModel.invited_by_user_id == manager_id,
                UserModel.role == UserRole.DEVELOPER.value,
            )
            .order_by(UserModel.name, UserModel.email)
        )
        return [self._to_domain(model) for model in self._session.execute(stmt).scalars()]

    def delete(self, user_id: str) -> None:
        self._session.execute(
            delete(PasswordCredentialTokenModel).where(
                PasswordCredentialTokenModel.user_id == user_id
            )
        )
        self._session.execute(delete(SessionModel).where(SessionModel.user_id == user_id))
        self._session.execute(delete(UserModel).where(UserModel.id == user_id))

    def list_invitation_housekeeping(self) -> list[User]:
        stmt = select(UserModel).where(UserModel.invitation_status.in_(("pending", "rejected")))
        return [self._to_domain(model) for model in self._session.execute(stmt).scalars()]

    def list_all(self) -> list[User]:
        return self.list_filtered()

    def list_filtered(
        self, *, name_contains: str | None = None, role: str | None = None
    ) -> list[User]:
        stmt = select(UserModel)
        if name_contains:
            pattern = f"%{name_contains.strip()}%"
            stmt = stmt.where(UserModel.name.ilike(pattern))
        if role:
            stmt = stmt.where(UserModel.role == role)
        stmt = stmt.order_by(UserModel.name, UserModel.email)
        return [self._to_domain(model) for model in self._session.execute(stmt).scalars()]

    def list_active_managers(self) -> list[User]:
        stmt = (
            select(UserModel)
            .where(UserModel.role == UserRole.MANAGER.value, UserModel.is_active.is_(True))
            .order_by(UserModel.name, UserModel.email)
        )
        return [self._to_domain(model) for model in self._session.execute(stmt).scalars()]

    def list_active_users(self, *, name_contains: str | None = None) -> list[User]:
        stmt = select(UserModel).where(UserModel.is_active.is_(True))
        if name_contains:
            pattern = f"%{name_contains.strip()}%"
            stmt = stmt.where(UserModel.name.ilike(pattern) | UserModel.email.ilike(pattern))
        stmt = stmt.order_by(UserModel.name, UserModel.email)
        return [self._to_domain(model) for model in self._session.execute(stmt).scalars()]


class SqlAlchemySessionRepository(SessionRepository):
    """SQLAlchemy implementation of the SessionRepository port."""

    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _to_domain(model: SessionModel) -> UserSession:
        return UserSession(
            id=model.id,
            user_id=model.user_id,
            token_hash=model.token_hash,
            created_at=model.created_at,
            expires_at=model.expires_at,
            revoked_at=model.revoked_at,
        )

    def add(self, session: UserSession) -> None:
        self._session.add(
            SessionModel(
                id=session.id,
                user_id=session.user_id,
                token_hash=session.token_hash,
                created_at=session.created_at,
                expires_at=session.expires_at,
                revoked_at=session.revoked_at,
            )
        )
        self._session.flush()

    def get_by_token_hash(self, token_hash: str) -> UserSession | None:
        stmt = select(SessionModel).where(SessionModel.token_hash == token_hash)
        model = self._session.execute(stmt).scalar_one_or_none()
        return None if model is None else self._to_domain(model)

    def update(self, session: UserSession) -> None:
        model = self._session.get(SessionModel, session.id)
        if model is not None:
            model.revoked_at = session.revoked_at
            model.expires_at = session.expires_at

    def purge_expired_before(self, moment: datetime) -> None:
        self._session.execute(delete(SessionModel).where(SessionModel.expires_at < moment))

    def revoke_all_active_for_user(self, user_id: str, when: datetime) -> None:
        stmt = select(SessionModel).where(
            SessionModel.user_id == user_id,
            SessionModel.revoked_at.is_(None),
        )
        for model in self._session.execute(stmt).scalars():
            model.revoked_at = when


class SqlAlchemyLoginAttemptRepository(LoginAttemptRepository):
    """SQLAlchemy implementation of the LoginAttemptRepository port."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, attempt: LoginAttempt) -> None:
        self._session.add(
            LoginAttemptModel(id=attempt.id, email=attempt.email, attempted_at=attempt.attempted_at)
        )
        self._session.flush()

    def count_since(self, email: str, since: datetime) -> int:
        stmt = (
            select(func.count())
            .select_from(LoginAttemptModel)
            .where(LoginAttemptModel.email == email, LoginAttemptModel.attempted_at >= since)
        )
        return int(self._session.execute(stmt).scalar_one())

    def delete(self, attempt_id: str) -> None:
        self._session.execute(delete(LoginAttemptModel).where(LoginAttemptModel.id == attempt_id))

    def clear_for(self, email: str) -> None:
        self._session.execute(delete(LoginAttemptModel).where(LoginAttemptModel.email == email))

    def purge_before(self, moment: datetime) -> None:
        self._session.execute(
            delete(LoginAttemptModel).where(LoginAttemptModel.attempted_at < moment)
        )


class SqlAlchemyPasswordCredentialTokenRepository(PasswordCredentialTokenRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _to_domain(model: PasswordCredentialTokenModel) -> PasswordCredentialToken:
        return PasswordCredentialToken(
            id=model.id,
            user_id=model.user_id,
            token_hash=model.token_hash,
            purpose=CredentialTokenPurpose(model.purpose),
            created_at=model.created_at,
            expires_at=model.expires_at,
            used_at=model.used_at,
        )

    def add(self, token: PasswordCredentialToken) -> None:
        self._session.add(
            PasswordCredentialTokenModel(
                id=token.id,
                user_id=token.user_id,
                token_hash=token.token_hash,
                purpose=token.purpose.value,
                created_at=token.created_at,
                expires_at=token.expires_at,
                used_at=token.used_at,
            )
        )
        self._session.flush()

    def get_by_token_hash(self, token_hash: str) -> PasswordCredentialToken | None:
        stmt = select(PasswordCredentialTokenModel).where(
            PasswordCredentialTokenModel.token_hash == token_hash
        )
        model = self._session.execute(stmt).scalar_one_or_none()
        return None if model is None else self._to_domain(model)

    def update(self, token: PasswordCredentialToken) -> None:
        model = self._session.get(PasswordCredentialTokenModel, token.id)
        if model is not None:
            model.used_at = token.used_at

    def invalidate_active_for_user(self, user_id: str, purpose: CredentialTokenPurpose) -> None:
        stmt = select(PasswordCredentialTokenModel).where(
            PasswordCredentialTokenModel.user_id == user_id,
            PasswordCredentialTokenModel.purpose == purpose.value,
            PasswordCredentialTokenModel.used_at.is_(None),
        )
        for model in self._session.execute(stmt).scalars():
            model.used_at = model.expires_at
