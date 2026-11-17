"""Primary / fallback database selection (Supabase first, local contingency).

A single engine is chosen once per process. Providers are never switched mid-session.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings

logger = logging.getLogger(__name__)


class DatabaseProviderRole(StrEnum):
    PRIMARY = "primary"
    FALLBACK = "fallback"
    TESTING = "testing"


@dataclass(frozen=True)
class DatabaseProviderStatus:
    """Active connection origin and operational limits of the fallback."""

    role: DatabaseProviderRole
    url_label: str
    fallback_available: bool
    fallback_active: bool
    limitations: str | None = None


def _url_label(url: str) -> str:
    if url.startswith("sqlite"):
        return "sqlite"
    if "supabase" in url.lower():
        return "supabase"
    if url.startswith("postgresql"):
        return "postgresql"
    return "other"


def _engine_kwargs(url: str) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "echo": False,
        "pool_pre_ping": True,
    }
    if url.startswith("sqlite"):
        return kwargs
    if url.startswith("postgresql"):
        kwargs["connect_args"] = {"connect_timeout": settings.DATABASE_CONNECT_TIMEOUT_SECONDS}
        kwargs["pool_size"] = settings.DATABASE_POOL_SIZE
        kwargs["max_overflow"] = settings.DATABASE_POOL_MAX_OVERFLOW
        kwargs["pool_recycle"] = settings.DATABASE_POOL_RECYCLE_SECONDS
        kwargs["pool_timeout"] = settings.DATABASE_POOL_TIMEOUT_SECONDS
    return kwargs


def _probe(engine: Engine) -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False


def select_database_url() -> tuple[str, DatabaseProviderStatus]:
    """Pick the active URL and describe the provider (no side effects on existing engines)."""
    primary = settings.DATABASE_URL.strip()
    fallback = (settings.DATABASE_FALLBACK_URL or "").strip() or None

    if settings.APP_ENV == "testing" or primary.startswith("sqlite"):
        status = DatabaseProviderStatus(
            role=DatabaseProviderRole.TESTING,
            url_label=_url_label(primary),
            fallback_available=bool(fallback),
            fallback_active=False,
            limitations=None,
        )
        return primary, status

    primary_engine = create_engine(primary, **_engine_kwargs(primary))
    try:
        if _probe(primary_engine):
            logger.info("Database provider: primary (%s)", _url_label(primary))
            return primary, DatabaseProviderStatus(
                role=DatabaseProviderRole.PRIMARY,
                url_label=_url_label(primary),
                fallback_available=bool(fallback),
                fallback_active=False,
                limitations=None,
            )
    finally:
        primary_engine.dispose()

    if not fallback:
        raise SQLAlchemyError(
            "Primary database unreachable and DATABASE_FALLBACK_URL is not configured."
        )

    fallback_engine = create_engine(fallback, **_engine_kwargs(fallback))
    try:
        if not _probe(fallback_engine):
            raise SQLAlchemyError("Both primary and fallback database connections failed.")
    finally:
        fallback_engine.dispose()

    logger.warning(
        "Primary database unreachable; using fallback (%s). "
        "Data is not synchronized with the remote provider.",
        _url_label(fallback),
    )
    return fallback, DatabaseProviderStatus(
        role=DatabaseProviderRole.FALLBACK,
        url_label=_url_label(fallback),
        fallback_available=True,
        fallback_active=True,
        limitations=(
            "Fallback database is active. Remote and local data are not assumed to be "
            "synchronized; writes apply only to the local provider until primary is restored."
        ),
    )


def build_engine(url: str) -> Engine:
    return create_engine(url, **_engine_kwargs(url))
