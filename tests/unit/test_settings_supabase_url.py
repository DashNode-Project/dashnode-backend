from pydantic import SecretStr

from app.config import Settings


def test_supabase_url_built_from_ref_and_password() -> None:
    s = Settings.model_construct(
        DATABASE_URL="postgresql+psycopg://local/db",
        SUPABASE_PROJECT_REF="abc123",
        SUPABASE_DB_PASSWORD=SecretStr("p@ss/word"),
        APP_ENV="development",
    )
    url = s.supabase_database_url()
    assert url is not None
    assert "db.abc123.supabase.co" in url
    assert "sslmode=require" in url
    assert s.database_primary_url == url
    assert s.database_fallback_url == "postgresql+psycopg://local/db"


def test_primary_is_database_url_when_supabase_missing() -> None:
    s = Settings.model_construct(
        DATABASE_URL="postgresql+psycopg://local/db",
        APP_ENV="development",
    )
    assert s.supabase_database_url() is None
    assert s.database_primary_url.endswith("/db")