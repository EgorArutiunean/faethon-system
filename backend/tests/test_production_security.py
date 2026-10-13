from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db.base import *  # noqa: F401,F403
from app.db.session import Base
from app.models.identity import User
from app.services import auth_seed
from scripts import bootstrap_admin, seed_demo


def test_production_rejects_placeholder_secret() -> None:
    with pytest.raises(ValidationError, match="AUTH_SECRET_KEY"):
        Settings(
            app_env="production",
            auth_secret_key="change-me-dev-only",
            cors_origins="https://buy.example.test",
            access_token_minutes=60,
        )


def test_production_rejects_insecure_cors_origin() -> None:
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        Settings(
            app_env="production",
            auth_secret_key="a-secure-random-secret-with-32-chars",
            cors_origins="http://buy.example.test",
            access_token_minutes=60,
        )


def test_production_accepts_secure_settings() -> None:
    settings = Settings(
        app_env="production",
        auth_secret_key="a-secure-random-secret-with-32-chars",
        cors_origins="https://buy.example.test",
        access_token_minutes=60,
    )
    assert settings.app_env == "production"


def test_production_rejects_long_access_token_ttl() -> None:
    with pytest.raises(ValidationError, match="ACCESS_TOKEN_MINUTES"):
        Settings(
            app_env="production",
            auth_secret_key="a-secure-random-secret-with-32-chars",
            cors_origins="https://buy.example.test",
            access_token_minutes=480,
        )


def test_demo_seeds_are_disabled_in_production(monkeypatch) -> None:
    production = SimpleNamespace(app_env="production")
    monkeypatch.setattr(auth_seed, "get_settings", lambda: production)
    monkeypatch.setattr(seed_demo, "get_settings", lambda: production)

    with pytest.raises(RuntimeError, match="disabled in production"):
        auth_seed.seed_auth_defaults(None)  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="disabled in production"):
        seed_demo.seed()


def test_admin_bootstrap_is_one_time_and_does_not_reset_password(monkeypatch) -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    monkeypatch.setattr(bootstrap_admin, "SessionLocal", TestingSession)
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "owner@example.test")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "first-strong-password")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_FULL_NAME", "Initial Owner")

    bootstrap_admin.bootstrap_admin()

    with TestingSession() as db:
        admin = db.scalar(select(User).where(User.username == "owner@example.test"))
        assert admin is not None
        original_hash = admin.hashed_password
        assert admin.role_names == ["admin"]
        assert admin.must_change_password is True

    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "different-strong-password")
    with pytest.raises(RuntimeError, match="does not reset"):
        bootstrap_admin.bootstrap_admin()

    with TestingSession() as db:
        admin = db.scalar(select(User).where(User.username == "owner@example.test"))
        assert admin is not None
        assert admin.hashed_password == original_hash
