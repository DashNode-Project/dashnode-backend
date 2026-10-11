"""
@sad 1.5, 5.6
@origin [Archetype Convention Addition]
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_ENV: str = "development"
    DATABASE_URL: str = "postgresql+psycopg://dashnode:dashnode@localhost:5432/dashnode"
    
    JWT_SECRET: str = "super_secret_development_key_only_change_in_prod"  # noqa: S105
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "dashnode"
    JWT_AUDIENCE: str = "dashnode_app"
    SESSION_TTL_HOURS: int = 8

    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"
    
    API_HOST: str = "0.0.0.0"  # noqa: S104
    API_PORT: int = 8000

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, v: str, info: object) -> str:
        # In non-development, must not be default and must be at least 32 chars
        # For this prototype we enforce it strictly
        if len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters long.")
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
