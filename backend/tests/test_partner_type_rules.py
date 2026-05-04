from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import *  # noqa: F401,F403
from app.db.session import Base, get_db
from app.main import app
from app.models.accounting import Payment
from app.models.documents import Document
from app.models.partners import Partner
from app.models.products import Product
from app.models.stock import Warehouse
from app.schemas.documents import DocumentCreate
from app.schemas.payments import PaymentCreate
from app.services.auth_seed import seed_auth_defaults
from app.services.documents_service import create_document
from app.services.payments_service import create_payment


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


def auth_header(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "admin123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def seed_catalog(db: Session) -> tuple[Warehouse, Partner, Partner, Partner]:
    db.add(Product(name="Bolt", sku="BOLT", base_price=Decimal("1")))
    warehouse = Warehouse(name="Main", code="MAIN")
    customer = Partner(name="Customer", code="CUST", partner_type=Partner.TYPE_CUSTOMER)
    supplier = Partner(name="Supplier", code="SUP", partner_type=Partner.TYPE_SUPPLIER)
    both = Partner(name="Both", code="BOTH", partner_type=Partner.TYPE_BOTH)
    db.add_all([warehouse, customer, supplier, both])
    db.commit()
    return warehouse, customer, supplier, both


def test_partner_create_requires_partner_type(client: TestClient) -> None:
    response = client.post("/api/v1/partners", json={"name": "No Type"}, headers=auth_header(client))

    assert response.status_code == 422


def test_incoming_accepts_supplier_or_both_only(db: Session) -> None:
    warehouse, customer, supplier, both = seed_catalog(db)

    supplier_doc = create_document(db, DocumentCreate(document_type=Document.TYPE_INCOMING, document_date=date(2026, 5, 4), warehouse_id=warehouse.id, partner_id=supplier.id))
    both_doc = create_document(db, DocumentCreate(document_type=Document.TYPE_INCOMING, document_date=date(2026, 5, 4), warehouse_id=warehouse.id, partner_id=both.id))

    with pytest.raises(HTTPException) as exc:
        create_document(db, DocumentCreate(document_type=Document.TYPE_INCOMING, document_date=date(2026, 5, 4), warehouse_id=warehouse.id, partner_id=customer.id))

    assert supplier_doc.id
    assert both_doc.id
    assert exc.value.status_code == 409


def test_outgoing_accepts_customer_or_both_only(db: Session) -> None:
    warehouse, customer, supplier, both = seed_catalog(db)

    customer_doc = create_document(db, DocumentCreate(document_type=Document.TYPE_OUTGOING, document_date=date(2026, 5, 4), warehouse_id=warehouse.id, partner_id=customer.id))
    both_doc = create_document(db, DocumentCreate(document_type=Document.TYPE_OUTGOING, document_date=date(2026, 5, 4), warehouse_id=warehouse.id, partner_id=both.id))

    with pytest.raises(HTTPException) as exc:
        create_document(db, DocumentCreate(document_type=Document.TYPE_OUTGOING, document_date=date(2026, 5, 4), warehouse_id=warehouse.id, partner_id=supplier.id))

    assert customer_doc.id
    assert both_doc.id
    assert exc.value.status_code == 409


def test_customer_payment_accepts_customer_or_both_only(db: Session) -> None:
    _warehouse, customer, supplier, both = seed_catalog(db)

    customer_payment = create_payment(db, PaymentCreate(partner_id=customer.id, payment_date=date(2026, 5, 4), payment_type=Payment.TYPE_CUSTOMER_PAYMENT, amount=Decimal("1")))
    both_payment = create_payment(db, PaymentCreate(partner_id=both.id, payment_date=date(2026, 5, 4), payment_type=Payment.TYPE_CUSTOMER_PAYMENT, amount=Decimal("1")))

    with pytest.raises(HTTPException) as exc:
        create_payment(db, PaymentCreate(partner_id=supplier.id, payment_date=date(2026, 5, 4), payment_type=Payment.TYPE_CUSTOMER_PAYMENT, amount=Decimal("1")))

    assert customer_payment.id
    assert both_payment.id
    assert exc.value.status_code == 409


def test_supplier_payment_accepts_supplier_or_both_only(db: Session) -> None:
    _warehouse, customer, supplier, both = seed_catalog(db)

    supplier_payment = create_payment(db, PaymentCreate(partner_id=supplier.id, payment_date=date(2026, 5, 4), payment_type=Payment.TYPE_SUPPLIER_PAYMENT, amount=Decimal("1")))
    both_payment = create_payment(db, PaymentCreate(partner_id=both.id, payment_date=date(2026, 5, 4), payment_type=Payment.TYPE_SUPPLIER_PAYMENT, amount=Decimal("1")))

    with pytest.raises(HTTPException) as exc:
        create_payment(db, PaymentCreate(partner_id=customer.id, payment_date=date(2026, 5, 4), payment_type=Payment.TYPE_SUPPLIER_PAYMENT, amount=Decimal("1")))

    assert supplier_payment.id
    assert both_payment.id
    assert exc.value.status_code == 409


def test_import_partners_validates_partner_type(client: TestClient) -> None:
    response = client.post(
        "/api/v1/import/partners/dry-run",
        content=b"name,partner_type,code\nBad,invalid,BAD\n",
        headers={**auth_header(client), "Content-Type": "application/octet-stream", "X-Filename": "data.csv"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["rows_invalid"] == 1
    assert payload["errors"][0]["field"] == "partner_type"


def test_partner_debts_report_includes_and_filters_partner_type(client: TestClient, db: Session) -> None:
    _warehouse, customer, supplier, _both = seed_catalog(db)

    response = client.get("/api/v1/reports/partner-debts?partner_type=customer", headers=auth_header(client))

    assert response.status_code == 200
    payload = response.json()
    assert {row["partner_name"] for row in payload["rows"]} == {customer.name}
    assert payload["rows"][0]["partner_type"] == Partner.TYPE_CUSTOMER
    assert supplier.name not in {row["partner_name"] for row in payload["rows"]}


def test_used_partner_delete_is_rejected(client: TestClient, db: Session) -> None:
    warehouse, customer, _supplier, _both = seed_catalog(db)
    create_document(db, DocumentCreate(document_type=Document.TYPE_OUTGOING, document_date=date(2026, 5, 4), warehouse_id=warehouse.id, partner_id=customer.id))

    response = client.delete(f"/api/v1/partners/{customer.id}", headers=auth_header(client))

    assert response.status_code == 409
    assert db.scalar(select(Partner).where(Partner.id == customer.id)) is not None
