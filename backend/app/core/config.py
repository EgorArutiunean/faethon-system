from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Buy Modern"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://buy:buy@localhost:5432/buy_modern"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    auth_secret_key: str = Field(default="change-me-demo-secret", validation_alias=AliasChoices("AUTH_SECRET_KEY", "JWT_SECRET_KEY"))
    access_token_minutes: int = 480

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
