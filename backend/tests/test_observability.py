import json
import logging
import re

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.core.observability import JsonFormatter
from app.main import app


def test_request_id_is_preserved_and_returned() -> None:
    response = TestClient(app).get("/health", headers={"X-Request-ID": "release-smoke-001"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "release-smoke-001"


def test_invalid_request_id_is_replaced() -> None:
    response = TestClient(app).get("/health", headers={"X-Request-ID": "short"})

    request_id = response.headers["X-Request-ID"]
    assert request_id != "short"
    assert re.fullmatch(r"[0-9a-f]{32}", request_id)


def test_json_formatter_emits_allowlisted_request_fields() -> None:
    record = logging.LogRecord(
        name="buy_modern.request",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request_completed",
        args=(),
        exc_info=None,
    )
    record.request_id = "release-smoke-001"
    record.method = "GET"
    record.path = "/api/v1/products"
    record.status_code = 200
    record.duration_ms = 12.34

    payload = json.loads(JsonFormatter().format(record))

    assert payload["event"] == "request_completed"
    assert payload["request_id"] == "release-smoke-001"
    assert payload["path"] == "/api/v1/products"
    assert "query" not in payload
    assert "authorization" not in payload


def test_production_requires_json_log_format() -> None:
    with pytest.raises(ValidationError, match="LOG_FORMAT"):
        Settings(
            app_env="production",
            auth_secret_key="a-secure-random-secret-with-32-chars",
            cors_origins="https://buy.example.test",
            access_token_minutes=60,
            log_format="text",
        )
