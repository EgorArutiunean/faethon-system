from fastapi.testclient import TestClient

from app.api.routes import health
from app.main import app


def test_healthcheck() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_liveness() -> None:
    client = TestClient(app)
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readiness_success(monkeypatch) -> None:
    monkeypatch.setattr(
        health,
        "_readiness_status",
        lambda _db: {
            "status": "ready",
            "database": "ok",
            "schema_revision": "0013_manager_cash_permissions",
        },
    )

    client = TestClient(app)
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database": "ok",
        "schema_revision": "0013_manager_cash_permissions",
    }


def test_readiness_returns_503_without_leaking_failure_details(monkeypatch) -> None:
    def fail(_db):
        raise RuntimeError("postgresql://secret-user:secret-password@database/private")

    monkeypatch.setattr(health, "_readiness_status", fail)

    client = TestClient(app)
    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Service is not ready"}
    assert "secret" not in response.text
