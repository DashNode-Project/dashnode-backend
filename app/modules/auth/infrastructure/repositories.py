"""
SQLAlchemy repository implementation for Users.
@sad AD-09, 5.6
@origin [SAD-Propuesto]
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.domain.entities import User, UserRole
from app.modules.auth.domain.ports import UserRepository
from app.modules.auth.infrastructure.models import UserModel


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
