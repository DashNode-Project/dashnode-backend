"""
SQLAlchemy database setup and UnitOfWork implementation.
@sad AD-09, 5.6
@origin [SAD-Propuesto]
"""

from collections.abc import Generator

from sqlalchemy import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.shared.application.ports import UnitOfWork
from app.shared.infrastructure.database_provider import (
    DatabaseProviderStatus,
    build_engine,
    select_database_url,
)

_engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None
_provider_status: DatabaseProviderStatus | None = None


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy ORM models."""

    pass


def initialize_database() -> DatabaseProviderStatus:
    """Resolve primary vs fallback once and bind the process-wide engine."""
    global _engine, SessionLocal, _provider_status
    if _engine is not None and _provider_status is not None:
        return _provider_status

    url, status = select_database_url()
    _engine = build_engine(url)
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=_engine,
        expire_on_commit=False,
    )
    _provider_status = status
    return status


def get_engine() -> Engine:
    if _engine is None:
        initialize_database()
    assert _engine is not None
    return _engine


def get_database_provider_status() -> DatabaseProviderStatus | None:
    return _provider_status


def _require_session_factory() -> sessionmaker[Session]:
    if SessionLocal is None:
        initialize_database()
    assert SessionLocal is not None
    return SessionLocal


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
    factory = _require_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()


def __getattr__(name: str) -> Engine:
    if name == "engine":
        return get_engine()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
