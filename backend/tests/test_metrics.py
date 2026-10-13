from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_metrics_expose_requests_latency_and_db_pool() -> None:
    client = TestClient(app)
    assert client.get("/health").status_code == 200

    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert (
        'buy_modern_http_requests_total{method="GET",route="/health",status="200"}' in response.text
    )
    assert "buy_modern_http_request_duration_seconds_bucket" in response.text
    assert 'buy_modern_db_pool_connections{state="checked_out"}' in response.text


def test_metrics_are_not_published_in_openapi_or_frontend_proxy() -> None:
    client = TestClient(app)
    assert "/metrics" not in client.get("/openapi.json").json()["paths"]

    nginx_config = Path(__file__).resolve().parents[2] / "frontend" / "nginx.conf"
    config_text = nginx_config.read_text(encoding="utf-8")
    assert "location /metrics" not in config_text
