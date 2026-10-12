"""
SQLAlchemy repository implementation for Users.
@sad AD-09, 5.6
@origin [SAD-Propuesto]
"""

from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.domain.entities import LoginAttempt, User, UserRole, UserSession
from app.modules.auth.domain.errors import EmailAlreadyRegisteredError
from app.modules.auth.domain.ports import LoginAttemptRepository, SessionRepository, UserRepository
from app.modules.auth.infrastructure.models import LoginAttemptModel, SessionModel, UserModel


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
            model.updated_at = user.updated_at


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
