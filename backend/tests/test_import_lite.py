from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import *  # noqa: F401,F403
from app.db.session import Base, get_db
from app.main import app
from app.models.partners import Partner
from app.models.products import Product
from app.models.stock import StockBalance, Warehouse
from app.services.auth_seed import seed_auth_defaults
from app.services.payments_service import get_partner_balance


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


def upload(client: TestClient, path: str, content: str, filename: str = "data.csv"):
    return client.post(
        path,
        content=content.encode("utf-8-sig"),
        headers={**auth_header(client), "Content-Type": "application/octet-stream", "X-Filename": filename},
    )


def test_template_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/import/templates/products.xlsx")

    assert response.status_code == 401


def test_template_requires_permission(client: TestClient) -> None:
    response = client.get("/api/v1/import/templates/products.xlsx", headers=auth_header(client, "viewer@example.com", "viewer123"))

    assert response.status_code == 403


def test_dry_run_detects_missing_fields(client: TestClient) -> None:
    response = upload(client, "/api/v1/import/products/dry-run", "sku,base_price\nSKU-1,10\n")

    assert response.status_code == 200
    payload = response.json()
    assert payload["rows_invalid"] == 1
    assert payload["errors"][0]["field"] == "name"


def test_dry_run_detects_invalid_numbers(client: TestClient) -> None:
    response = upload(client, "/api/v1/import/products/dry-run", "sku,name,base_price\nSKU-1,Test,abc\n")

    assert response.status_code == 200
    payload = response.json()
    assert payload["rows_invalid"] == 1
    assert payload["errors"][0]["field"] == "base_price"


def test_apply_refuses_invalid_file(client: TestClient, db: Session) -> None:
    response = upload(client, "/api/v1/import/products/apply", "sku,base_price\nSKU-1,10\n")

    assert response.status_code == 200
    assert response.json()["applied"] is False
    assert db.scalar(select(Product).where(Product.sku == "SKU-1")) is None


def test_products_import_creates_products(client: TestClient, db: Session) -> None:
    response = upload(client, "/api/v1/import/products/apply", "sku,name,base_price\nSKU-1,Imported Product,12.50\n")

    assert response.status_code == 200
    assert response.json()["created"] == 1
    product = db.scalar(select(Product).where(Product.sku == "SKU-1"))
    assert product is not None
    assert product.name == "Imported Product"


def test_warehouses_import_creates_warehouses(client: TestClient, db: Session) -> None:
    response = upload(client, "/api/v1/import/warehouses/apply", "name,code,address\nImported Warehouse,WH-1,Address\n")

    assert response.status_code == 200
    assert response.json()["created"] == 1
    assert db.scalar(select(Warehouse).where(Warehouse.name == "Imported Warehouse")) is not None


def test_opening_stock_updates_balances(client: TestClient, db: Session) -> None:
    db.add_all([Product(sku="SKU-STOCK", name="Stock Product"), Warehouse(name="Stock Warehouse", code="STOCK")])
    db.commit()

    response = upload(
        client,
        "/api/v1/import/opening-stock/apply",
        "product_sku,product_name,warehouse_name,quantity\nSKU-STOCK,,Stock Warehouse,7\n",
    )

    assert response.status_code == 200
    balance = db.scalar(select(StockBalance))
    assert balance is not None
    assert balance.quantity == Decimal("7")


def test_opening_partner_balances_updates_partner_balance(client: TestClient, db: Session) -> None:
    partner = Partner(name="Opening Partner", code="OPEN-P")
    db.add(partner)
    db.commit()

    response = upload(client, "/api/v1/import/opening-partner-balances/apply", "partner_name,balance\nOpening Partner,15.25\n")

    assert response.status_code == 200
    assert get_partner_balance(db, partner.id).balance == Decimal("15.25")


def test_viewer_cannot_import(client: TestClient) -> None:
    response = client.post(
        "/api/v1/import/products/dry-run",
        content=b"sku,name\nSKU-1,Nope\n",
        headers={**auth_header(client, "viewer@example.com", "viewer123"), "Content-Type": "application/octet-stream", "X-Filename": "data.csv"},
    )

    assert response.status_code == 403
