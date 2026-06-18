from decimal import Decimal
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import *  # noqa: F401,F403
from app.db.session import Base, get_db
from app.main import app
from app.models.partners import Partner
from app.models.products import Product, ProductGroup
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


def upload_bytes(client: TestClient, path: str, content: bytes, filename: str):
    return client.post(
        path,
        content=content,
        headers={**auth_header(client), "Content-Type": "application/octet-stream", "X-Filename": filename},
    )


def workbook_bytes(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


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


def test_products_import_assigns_category_and_preserves_legacy_name(client: TestClient, db: Session) -> None:
    category_name = "\u041d\u0430\u043f\u0438\u0442\u043a\u0438"
    legacy_name = "Old Imported Product"
    response = upload(
        client,
        "/api/v1/import/products/apply",
        f"sku,name,category,base_price,legacy_name\nSKU-CAT,Imported Product,{category_name},12.50,{legacy_name}\n",
    )

    assert response.status_code == 200
    assert response.json()["created"] == 1
    group = db.scalar(select(ProductGroup).where(ProductGroup.name == category_name))
    assert group is not None
    product = db.scalar(select(Product).where(Product.sku == "SKU-CAT"))
    assert product is not None
    assert product.group_id == group.id
    assert product.description is not None
    assert f"legacy_name: {legacy_name}" in product.description


def test_products_import_reads_legacy_price_list_xlsx(client: TestClient, db: Session) -> None:
    category_name = "\u0421\u043f\u0438\u0441\u043e\u043a"
    legacy_name = "\u041a\u0440\u0443\u043f\u0430 \u041a\u0443\u0442\u044c\u044f 0,9\u043a\u0433*17\u0448\u0442"
    content = workbook_bytes(
        [
            ["\u041f\u0440\u0430\u0439\u0441 - \u043b\u0438\u0441\u0442", None, None, None, None, None, None, None],
            ["\u0421\u043a\u043b\u0430\u0434", "\u041a\u043e\u0434", "\u0422\u043e\u0432\u0430\u0440", "\u0415\u0434.", "\u041a\u043e\u043b-\u0432\u043e", "\u0426\u0435\u043d\u0430 \u0443.\u0435.", "\u0426\u0435\u043d\u0430 \u043e\u0441\u0442.", "\u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f"],
            ["Main", "93197", legacy_name, "\u0448\u0442", 17, "8.000", "136.00", category_name],
        ]
    )

    response = upload_bytes(client, "/api/v1/import/products/apply", content, "price.xlsx")

    assert response.status_code == 200
    assert response.json()["created"] == 1
    product = db.scalar(select(Product).where(Product.sku == "93197"))
    assert product is not None
    assert product.name == legacy_name
    assert product.base_price == Decimal("136.00")
    assert product.description is not None
    assert f"legacy_name: {legacy_name}" in product.description
    assert product.group is not None
    assert product.group.name == category_name


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
