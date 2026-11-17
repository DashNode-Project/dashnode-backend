"""Database provider selection (primary vs fallback)."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.shared.infrastructure.database_provider import (
    DatabaseProviderRole,
    select_database_url,
)


def test_sqlite_testing_skips_fallback_probe():
    with patch("app.shared.infrastructure.database_provider.settings") as mock_settings:
        mock_settings.APP_ENV = "testing"
        mock_settings.DATABASE_URL = "sqlite+pysqlite:///:memory:"
        mock_settings.DATABASE_FALLBACK_URL = "postgresql+psycopg://local/db"
        url, status = select_database_url()
    assert url == "sqlite+pysqlite:///:memory:"
    assert status.role == DatabaseProviderRole.TESTING
    assert status.fallback_active is False


def test_primary_used_when_probe_succeeds():
    engine = MagicMock()
    conn = MagicMock()
    engine.connect.return_value.__enter__ = lambda s: conn
    engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    with (
        patch("app.shared.infrastructure.database_provider.settings") as mock_settings,
        patch("app.shared.infrastructure.database_provider.create_engine", return_value=engine),
        patch("app.shared.infrastructure.database_provider._probe", return_value=True),
    ):
        mock_settings.APP_ENV = "development"
        mock_settings.DATABASE_URL = "postgresql+psycopg://primary/db"
        mock_settings.DATABASE_FALLBACK_URL = "postgresql+psycopg://fallback/db"
        url, status = select_database_url()

    assert url == "postgresql+psycopg://primary/db"
    assert status.role == DatabaseProviderRole.PRIMARY
    engine.dispose.assert_called_once()


def test_fallback_when_primary_fails():
    engines = [MagicMock(), MagicMock()]

    with (
        patch("app.shared.infrastructure.database_provider.settings") as mock_settings,
        patch(
            "app.shared.infrastructure.database_provider.create_engine",
            side_effect=engines,
        ),
        patch(
            "app.shared.infrastructure.database_provider._probe",
            side_effect=[False, True],
        ),
    ):
        mock_settings.APP_ENV = "development"
        mock_settings.DATABASE_URL = "postgresql+psycopg://primary/db"
        mock_settings.DATABASE_FALLBACK_URL = "postgresql+psycopg://fallback/db"
        url, status = select_database_url()

    assert url == "postgresql+psycopg://fallback/db"
    assert status.role == DatabaseProviderRole.FALLBACK
    assert status.fallback_active is True
    assert status.limitations


def test_raises_when_both_unreachable():
    with (
        patch("app.shared.infrastructure.database_provider.settings") as mock_settings,
        patch(
            "app.shared.infrastructure.database_provider.create_engine", return_value=MagicMock()
        ),
        patch("app.shared.infrastructure.database_provider._probe", return_value=False),
    ):
        mock_settings.APP_ENV = "development"
        mock_settings.DATABASE_URL = "postgresql+psycopg://primary/db"
        mock_settings.DATABASE_FALLBACK_URL = "postgresql+psycopg://fallback/db"
        with pytest.raises(SQLAlchemyError):
            select_database_url()
