"""Application settings loaded from environment variables.

All configuration goes through ``Settings`` so the rest of the codebase never
reads ``os.environ`` directly. This is also what makes the app trivial to test:
fixtures can construct a fresh ``Settings`` and inject it where needed.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings.

    Values are populated from (in order of precedence):
    1. process environment variables
    2. a ``.env`` file in the working directory (development only)
    3. defaults declared on the model

    Production deployments should rely entirely on env vars.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------------------------------------------------------------- App
    APP_NAME: str = "gift-finder"
    APP_ENV: Literal["development", "staging", "production", "test"] = "development"
    DEBUG: bool = False
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # ------------------------------------------------------------ Database
    # Async DSN, e.g. ``postgresql+asyncpg://user:pass@host:5432/giftfinder``.
    DATABASE_URL: PostgresDsn
    # Sync DSN used by Alembic when running migrations.
    DATABASE_SYNC_URL: PostgresDsn | None = None

    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_ECHO: bool = False

    # ------------------------------------------------------------- Redis
    REDIS_URL: RedisDsn = Field(default="redis://localhost:6379/0")  # type: ignore[assignment]

    # --------------------------------------------------------------- Auth
    JWT_SECRET: SecretStr
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # --------------------------------------------------------- 3rd-party
    OPENAI_API_KEY: SecretStr | None = None
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_EMBEDDING_DIMENSIONS: int = 1536

    # ----------------------------------------------------------- Storage
    S3_BUCKET: str = "gift-finder-assets"
    S3_REGION: str = "us-east-1"
    S3_ENDPOINT_URL: str | None = None  # for LocalStack / MinIO in tests
    AWS_ACCESS_KEY_ID: SecretStr | None = None
    AWS_SECRET_ACCESS_KEY: SecretStr | None = None
    CDN_BASE_URL: str | None = None

    # ----------------------------------------------------------- Scraping
    SCRAPER_DEFAULT_RATE_LIMIT_RPS: float = 1.0
    SCRAPER_USER_AGENT: str = "GiftFinderBot/1.0 (+https://giftfinder.example/bot)"
    SCRAPER_MAX_RETRIES: int = 3

    # --------------------------------------------------------- Validators
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors(cls, v: str | list[str]) -> list[str]:
        """Allow CORS_ORIGINS to be supplied as a comma-separated string."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> "Settings":
        """Refuse to boot with weak / well-known JWT secrets in production."""
        if self.is_production:
            weak_secrets = {
                "change-me-in-production-this-is-not-secret",
                "secret",
                "changeme",
                "",
            }
            secret_val = (
                self.JWT_SECRET.get_secret_value() if self.JWT_SECRET else ""
            )
            if secret_val in weak_secrets or len(secret_val) < 32:
                raise ValueError(
                    "JWT_SECRET must be at least 32 characters and not a "
                    "known-weak value in production"
                )
        return self

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_test(self) -> bool:
        return self.APP_ENV == "test"

    @property
    def database_sync_url(self) -> str:
        """Return a sync DSN for tools like Alembic that don't speak asyncpg."""
        if self.DATABASE_SYNC_URL is not None:
            return str(self.DATABASE_SYNC_URL)
        # Derive psycopg sync URL from the async one.
        return str(self.DATABASE_URL).replace("+asyncpg", "+psycopg")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached singleton settings instance.

    Cached so we don't re-parse env vars on every request. Tests that need a
    different config should call ``get_settings.cache_clear()``.
    """
    return Settings()  # type: ignore[call-arg]


# Convenience alias for code that needs the settings at import time.
settings: Settings = get_settings()
