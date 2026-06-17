import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import *  # noqa: F401,F403
from app.db.session import Base, get_db
from app.main import app
from app.schemas.products import ProductCreate
from app.services.auth_seed import seed_auth_defaults
from app.services.directory_service import create_product, create_warehouse
from app.schemas.warehouses import WarehouseCreate


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


def test_audit_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/audit")

    assert response.status_code == 401


def test_audit_requires_audit_read_permission(client: TestClient) -> None:
    response = client.get("/api/v1/audit", headers=auth_header(client, "viewer@example.com", "viewer123"))

    assert response.status_code == 403


def test_admin_can_read_audit_log(client: TestClient, db: Session) -> None:
    create_product(db, ProductCreate(name="Audit Product", sku="AUD-1"))

    response = client.get("/api/v1/audit", headers=auth_header(client))

    assert response.status_code == 200
    rows = response.json()
    assert rows[0]["entity_type"] == "product"
    assert rows[0]["entity_id"] == "1"
    assert rows[0]["action"] == "create"
    assert rows[0]["created_at"]


def test_audit_can_filter_by_entity_type(client: TestClient, db: Session) -> None:
    create_product(db, ProductCreate(name="Audit Product", sku="AUD-1"))
    create_warehouse(db, WarehouseCreate(name="Audit Warehouse", code="AUD-WH"))

    response = client.get("/api/v1/audit?entity_type=warehouse", headers=auth_header(client))

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["entity_type"] == "warehouse"
