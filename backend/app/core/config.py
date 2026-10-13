from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Buy Modern"
    app_env: Literal["development", "test", "production"] = "development"
    api_prefix: str = "/api/v1"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "text"] = "json"
    sentry_dsn: str | None = None
    sentry_environment: str | None = None
    sentry_traces_sample_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    release_version: str | None = None
    database_url: str = "postgresql+psycopg://buy:buy@localhost:5432/buy_modern"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    auth_secret_key: str = Field(
        default="change-me-demo-secret",
        validation_alias=AliasChoices("AUTH_SECRET_KEY", "JWT_SECRET_KEY"),
    )
    access_token_minutes: int = Field(default=60, ge=5, le=1440)
    login_max_attempts: int = Field(default=5, ge=2, le=20)
    login_lock_minutes: int = Field(default=15, ge=1, le=1440)
    import_max_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=100 * 1024 * 1024)
    import_max_rows: int = Field(default=20_000, ge=1, le=200_000)
    import_xlsx_max_uncompressed_bytes: int = Field(
        default=50 * 1024 * 1024, ge=1024, le=500 * 1024 * 1024
    )
    import_xlsx_max_entries: int = Field(default=1000, ge=10, le=10_000)
    import_xlsx_max_compression_ratio: int = Field(default=100, ge=2, le=1000)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.app_env != "production":
            return self

        unsafe_secrets = {"change-me-demo-secret", "change-me-dev-only", "ci-only-secret"}
        if self.auth_secret_key in unsafe_secrets or len(self.auth_secret_key) < 32:
            raise ValueError(
                "AUTH_SECRET_KEY must be a non-placeholder value of at least 32 characters in production"
            )
        if self.access_token_minutes > 60:
            raise ValueError("ACCESS_TOKEN_MINUTES must not exceed 60 in production")
        if self.log_format != "json":
            raise ValueError("LOG_FORMAT must be json in production")

        origins = self.cors_origin_list
        if not origins or any(not origin.startswith("https://") for origin in origins):
            raise ValueError("CORS_ORIGINS must contain only explicit HTTPS origins in production")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
