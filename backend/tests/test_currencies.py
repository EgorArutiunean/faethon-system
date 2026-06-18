import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import *  # noqa: F401,F403
from app.db.session import Base, get_db
from app.main import app
from app.services.auth_seed import seed_auth_defaults


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    session = TestingSession()
    seed_auth_defaults(session)
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def client(db: Session) -> TestClient:
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def auth_header(client: TestClient, email: str = "admin@example.com", password: str = "admin123") -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_default_currencies_are_available(client: TestClient) -> None:
    response = client.get("/api/v1/currencies", headers=auth_header(client))

    assert response.status_code == 200
    codes = [row["code"] for row in response.json()]
    assert codes[:1] == ["RUB_PMR"]
    assert {"MDL", "USD", "EUR"}.issubset(set(codes))


def test_admin_can_create_and_read_exchange_rate(client: TestClient) -> None:
    response = client.post(
        "/api/v1/currencies/rates",
        json={"currency_code": "USD", "rate_date": "2026-06-19", "rate_to_base": "16.200000", "note": "manual"},
        headers=auth_header(client),
    )

    assert response.status_code == 200
    assert response.json()["currency_code"] == "USD"
    latest = client.get("/api/v1/currencies/rates/latest?currency_code=USD&on_date=2026-06-19", headers=auth_header(client))
    assert latest.status_code == 200
    assert latest.json()["rate_to_base"] == 16.2
