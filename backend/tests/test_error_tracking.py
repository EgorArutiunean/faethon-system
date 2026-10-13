from typing import Any

import sentry_sdk

from app.core.config import Settings
from app.core.error_tracking import configure_error_tracking, scrub_sensitive_event


def test_error_tracking_is_disabled_without_dsn(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: calls.append(kwargs))

    configure_error_tracking(Settings(sentry_dsn=None))

    assert calls == []


def test_error_tracking_uses_privacy_safe_defaults(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: calls.append(kwargs))
    settings = Settings(
        app_env="test",
        sentry_dsn="https://public@example.invalid/1",
        sentry_environment="staging",
        sentry_traces_sample_rate=0.25,
        release_version="2026.10.12",
    )

    configure_error_tracking(settings)

    assert len(calls) == 1
    options = calls[0]
    assert options["send_default_pii"] is False
    assert options["include_local_variables"] is False
    assert options["max_request_body_size"] == "never"
    assert options["environment"] == "staging"
    assert options["release"] == "2026.10.12"
    assert options["traces_sample_rate"] == 0.25
    assert options["before_send"] is scrub_sensitive_event
    assert options["before_send_transaction"] is scrub_sensitive_event


def test_sensitive_request_data_is_removed_before_sending() -> None:
    event: dict[str, Any] = {
        "user": {"email": "private@example.test"},
        "request": {
            "url": "https://buy.example.test/api/v1/products?token=secret#fragment",
            "method": "GET",
            "headers": {"Authorization": "Bearer secret"},
            "cookies": {"session": "secret"},
            "query_string": "token=secret",
            "data": {"password": "secret"},
            "env": {"REMOTE_ADDR": "192.0.2.1"},
        },
    }

    scrubbed = scrub_sensitive_event(event, {})

    assert "user" not in scrubbed
    assert scrubbed["request"] == {
        "url": "https://buy.example.test/api/v1/products",
        "method": "GET",
    }
