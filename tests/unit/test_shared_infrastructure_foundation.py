"""
Unit tests for the foundation pieces: Argon2 hasher, UtcDateTime and Settings validation.
@sad AD-09, 5.6
"""

from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, select

from app.config import Settings
from app.shared.infrastructure.hasher import Argon2PasswordHasher
from app.shared.infrastructure.types import UtcDateTime

_PASSWORD = "Abcdef12"


def _hasher() -> Argon2PasswordHasher:
    return Argon2PasswordHasher(time_cost=1, memory_cost_kib=8, parallelism=1)


def test_hash_is_salted_and_verifiable() -> None:
    hasher = _hasher()
    first, second = hasher.hash(_PASSWORD), hasher.hash(_PASSWORD)
    assert first != second
    assert first.startswith("$argon2id$")
    assert _PASSWORD not in first
    assert hasher.verify(_PASSWORD, first)
    assert not hasher.verify("Otra1234", first)


def test_verify_returns_false_for_malformed_hash() -> None:
    assert _hasher().verify(_PASSWORD, "not-a-hash") is False


def test_verify_dummy_never_raises_and_caches_hash() -> None:
    hasher = _hasher()
    hasher.verify_dummy(_PASSWORD)
    cached = hasher._dummy_hash
    hasher.verify_dummy(_PASSWORD)
    assert cached is not None
    assert hasher._dummy_hash == cached


def test_utc_datetime_roundtrip_returns_aware_utc() -> None:
    metadata = MetaData()
    table = Table("events", metadata, Column("id", Integer), Column("at", UtcDateTime))
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata.create_all(engine)
    bogota = timezone(timedelta(hours=-5))
    with engine.begin() as conn:
        conn.execute(
            table.insert(),
            [
                {"id": 1, "at": datetime(2026, 1, 1, 12, 0, tzinfo=bogota)},
                # naive values are treated as UTC
                {"id": 2, "at": datetime(2026, 1, 1, 12, 0)},  # noqa: DTZ001
                {"id": 3, "at": None},
            ],
        )
        rows = {row.id: row.at for row in conn.execute(select(table))}
    assert rows[1] == datetime(2026, 1, 1, 17, 0, tzinfo=UTC)
    assert rows[1].tzinfo is not None
    assert rows[2] == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    assert rows[3] is None


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {"DATABASE_URL": "sqlite+pysqlite:///:memory:"}
    base.update(overrides)
    return Settings(_env_file=None, **base)


def test_settings_require_database_url() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, DATABASE_URL="")


def test_settings_reject_wildcard_cors() -> None:
    with pytest.raises(ValidationError):
        _settings(CORS_ORIGINS="*")


def test_settings_derived_values() -> None:
    cfg = _settings(CORS_ORIGINS="http://a.test, http://b.test", SESSION_TTL_HOURS=8)
    assert cfg.cors_origins_list == ["http://a.test", "http://b.test"]
    assert cfg.session_ttl_seconds == 8 * 3600
    assert cfg.session_cookie_max_age_seconds == (8 + cfg.SESSION_COOKIE_RETENTION_HOURS) * 3600


@pytest.mark.parametrize(
    "overrides",
    [
        {"SESSION_COOKIE_SECURE": False},
        {"SESSION_COOKIE_SECURE": True},  # still sqlite
        {
            "SESSION_COOKIE_SECURE": True,
            "DATABASE_URL": "postgresql+psycopg://u@h/db",
            "ARGON2_TIME_COST": 1,
        },
    ],
)
def test_production_profile_rejects_insecure_configuration(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _settings(APP_ENV="production", **overrides)


def test_production_profile_accepts_hardened_configuration() -> None:
    cfg = _settings(
        APP_ENV="production",
        SESSION_COOKIE_SECURE=True,
        DATABASE_URL="postgresql+psycopg://u@h/db",
        ARGON2_TIME_COST=3,
        ARGON2_MEMORY_COST_KIB=65536,
    )
    assert cfg.APP_ENV == "production"
