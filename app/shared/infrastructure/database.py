"""
SQLAlchemy database setup and UnitOfWork implementation.
@sad AD-09, 5.6
@origin [SAD-Propuesto]
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings
from app.shared.application.ports import UnitOfWork

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.APP_ENV == "development",
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy ORM models."""
    pass


class SqlAlchemyUnitOfWork(UnitOfWork):
    """SQLAlchemy implementation of the UnitOfWork pattern."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
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
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()


def get_db_session() -> Generator[Session, None, None]:
    """Provides a transactional database session for dependencies."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
