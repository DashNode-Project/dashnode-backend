"""
Application settings loaded exclusively from environment variables (12-factor).

Fail-fast policy: required values must be provided and insecure combinations are
rejected at start-up. No secret has a default value in code.

@sad 1.5, 5.6
@origin [Archetype Convention Addition]
"""

from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Runtime profile -------------------------------------------------
    APP_ENV: Literal["development", "testing", "production"] = "development"

    # --- Persistence (required, no default: credentials never live in code) ---
    DATABASE_URL: str = Field(min_length=1)

    # Server where the integration tests may create/drop temporary databases.
    TEST_POSTGRES_URL: str | None = None

    # --- Server session (HU_DN_01_03, HU_DN_01_05; RNF-SEG-06, RNF-SEG-09) -------
    SESSION_COOKIE_NAME: str = "dashnode_session"
    SESSION_TTL_HOURS: int = Field(default=8, ge=1, le=24 * 30)
    # The browser keeps the cookie a little longer than the server session so an
    # expired session can be answered with the expiry message instead of a bare 401.
    SESSION_COOKIE_RETENTION_HOURS: int = Field(default=24, ge=0, le=24 * 30)
    SESSION_COOKIE_SECURE: bool = False
    SESSION_COOKIE_SAMESITE: Literal["lax", "strict"] = "lax"
    LOGIN_MAX_FAILED_ATTEMPTS: int = Field(default=5, ge=1, le=50)
    LOGIN_ATTEMPT_WINDOW_MINUTES: int = Field(default=15, ge=1, le=24 * 60)

    # --- Password hashing (Argon2id). OWASP minimum: m=19 MiB, t=2, p=1 ----------
    ARGON2_TIME_COST: int = Field(default=3, ge=1)
    ARGON2_MEMORY_COST_KIB: int = Field(default=65536, ge=8)
    ARGON2_PARALLELISM: int = Field(default=4, ge=1)

    # --- CORS / CSRF (explicit allow-list, never a wildcard with credentials) ----
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:8080"

    # --- Server ------------------------------------------------------------------
    API_HOST: str = "0.0.0.0"  # noqa: S104 - bound inside the container only
    API_PORT: int = 8000

    # --- Mail (prepared for the password-recovery story; unused in this epic) ----
    FRONTEND_BASE_URL: str = "http://localhost:8080"
    PASSWORD_RESET_TTL_MINUTES: int = Field(default=60, ge=5, le=1440)
    PASSWORD_ACTIVATION_TTL_HOURS: int = Field(default=24, ge=1, le=168)
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: SecretStr | None = None
    SMTP_FROM_EMAIL: str | None = None
    SMTP_USE_TLS: bool = True

    # --- Local development seed (read from environment, blocked in production) ---
    SEED_ADMIN_EMAIL: str | None = None
    SEED_ADMIN_PASSWORD: SecretStr | None = None
    SEED_MANAGER_EMAIL: str | None = None
    SEED_MANAGER_PASSWORD: SecretStr | None = None
    SEED_DEVELOPER_EMAIL: str | None = None
    SEED_DEVELOPER_PASSWORD: SecretStr | None = None
    SEED_DISABLED_EMAIL: str | None = None
    SEED_DISABLED_PASSWORD: SecretStr | None = None

    @model_validator(mode="after")
    def _validate_security_profile(self) -> Self:
        if "*" in self.cors_origins_list:
            raise ValueError("CORS_ORIGINS must list explicit origins (no wildcard).")
        if self.APP_ENV == "production":
            if not self.SESSION_COOKIE_SECURE:
                raise ValueError("SESSION_COOKIE_SECURE must be true in production.")
            if self.DATABASE_URL.startswith("sqlite"):
                raise ValueError("SQLite is not allowed in production.")
            if self.ARGON2_TIME_COST < 2 or self.ARGON2_MEMORY_COST_KIB < 19456:
                raise ValueError("Argon2 parameters are below the OWASP minimum for production.")
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def session_ttl_seconds(self) -> int:
        return self.SESSION_TTL_HOURS * 3600

    @property
    def session_cookie_max_age_seconds(self) -> int:
        return (self.SESSION_TTL_HOURS + self.SESSION_COOKIE_RETENTION_HOURS) * 3600


settings = Settings()
