from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import *  # noqa: F401,F403
from app.db.session import Base, get_db
from app.main import app
from app.models.documents import Document, DocumentLine
from app.models.partners import Partner
from app.models.products import Product
from app.models.stock import Warehouse
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


def login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def seed_logistics_data(db: Session) -> tuple[Warehouse, Document, Document]:
    assigned = Warehouse(code="LOG-A", name="Assigned Warehouse")
    other = Warehouse(code="LOG-B", name="Other Warehouse")
    supplier = Partner(code="LOG-SUP", name="Logistics Supplier", partner_type=Partner.TYPE_SUPPLIER)
    customer = Partner(code="LOG-CUST", name="Logistics Customer", partner_type=Partner.TYPE_CUSTOMER)
    product = Product(sku="LOG-P", name="Logistics Product", base_price=Decimal("150.00"), is_active=True)
    db.add_all([assigned, other, supplier, customer, product])
    db.flush()

    incoming = Document(
        document_type=Document.TYPE_INCOMING,
        number="IN-LOG-1",
        document_date=date(2026, 7, 24),
        status=Document.STATUS_POSTED,
        partner_id=supplier.id,
        warehouse_id=assigned.id,
        total_amount=Decimal("800.00"),
        currency_code="USD",
        exchange_rate=Decimal("16.20"),
        foreign_total_amount=Decimal("50.00"),
    )
    other_outgoing = Document(
        document_type=Document.TYPE_OUTGOING,
        number="OUT-LOG-2",
        document_date=date(2026, 7, 24),
        status=Document.STATUS_POSTED,
        partner_id=customer.id,
        warehouse_id=other.id,
        total_amount=Decimal("175.00"),
    )
    db.add_all([incoming, other_outgoing])
    db.flush()
    db.add_all(
        [
            DocumentLine(
                document_id=incoming.id,
                product_id=product.id,
                quantity=Decimal("2"),
                price=Decimal("400.00"),
                line_total=Decimal("800.00"),
                foreign_price=Decimal("25.00"),
                foreign_line_total=Decimal("50.00"),
            ),
            DocumentLine(
                document_id=other_outgoing.id,
                product_id=product.id,
                quantity=Decimal("1"),
                price=Decimal("175.00"),
                line_total=Decimal("175.00"),
            ),
        ]
    )
    db.commit()
    return assigned, incoming, other_outgoing


def create_logistics_user(client: TestClient, warehouse_id: int) -> dict[str, str]:
    admin_headers = login(client, "admin@example.com", "admin123")
    response = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "email": "logist@example.com",
            "password": "logist123",
            "full_name": "Logistics Operator",
            "role_names": ["logist"],
            "warehouse_ids": [warehouse_id],
        },
    )
    assert response.status_code == 201
    return login(client, "logist@example.com", "logist123")


def test_logistics_sees_only_assigned_documents_and_sale_price(client: TestClient, db: Session) -> None:
    assigned, incoming, other_outgoing = seed_logistics_data(db)
    headers = create_logistics_user(client, assigned.id)

    response = client.get("/api/v1/logistics/documents", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert [document["id"] for document in payload] == [incoming.id]
    assert other_outgoing.id not in [document["id"] for document in payload]
    assert payload[0]["lines"][0]["sale_price"] == "150.00"
    assert payload[0]["lines"][0]["sale_total"] == "300.00"
    assert "price" not in payload[0]["lines"][0]
    assert "foreign_price" not in payload[0]["lines"][0]
    assert "total_amount" not in payload[0]
    assert "currency_code" not in payload[0]
    assert "exchange_rate" not in payload[0]
    assert "foreign_total_amount" not in payload[0]


def test_logistics_cannot_bypass_scoped_document_endpoint(client: TestClient, db: Session) -> None:
    assigned, incoming, other_outgoing = seed_logistics_data(db)
    headers = create_logistics_user(client, assigned.id)

    regular_documents = client.get("/api/v1/documents", headers=headers)
    own_document = client.get(f"/api/v1/logistics/documents/{incoming.id}", headers=headers)
    other_document = client.get(f"/api/v1/logistics/documents/{other_outgoing.id}", headers=headers)
    post_document = client.post(f"/api/v1/documents/{incoming.id}/post", headers=headers)

    assert regular_documents.status_code == 403
    assert own_document.status_code == 200
    assert other_document.status_code == 404
    assert post_document.status_code == 403
