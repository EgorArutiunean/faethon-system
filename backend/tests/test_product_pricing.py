from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.base import *  # noqa: F401,F403
from app.db.session import Base, get_db
from app.main import app
from app.models.documents import Document
from app.models.partners import Partner
from app.models.products import Product
from app.models.stock import Warehouse
from app.schemas.documents import DocumentCreate, DocumentLineCreate, DocumentRepost
from app.services.auth_seed import seed_auth_defaults
from app.services.documents_service import add_document_line, cancel_document, create_document, post_document, repost_document
from app.services.product_pricing_service import attach_single_product_pricing


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
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def seed_catalog(db: Session, sale_price: str = "120.00") -> tuple[Product, Warehouse, Partner]:
    product = Product(name="Pricing product", sku="PRICE-1", base_price=Decimal(sale_price))
    warehouse = Warehouse(name="Pricing warehouse", code="PRICE-WH")
    supplier = Partner(name="Pricing supplier", code="PRICE-SUP", partner_type=Partner.TYPE_SUPPLIER)
    db.add_all([product, warehouse, supplier])
    db.commit()
    return product, warehouse, supplier


def post_incoming(
    db: Session,
    product: Product,
    warehouse: Warehouse,
    supplier: Partner,
    document_date: date,
    cost: str,
) -> Document:
    document = create_document(
        db,
        DocumentCreate(
            document_type=Document.TYPE_INCOMING,
            document_date=document_date,
            warehouse_id=warehouse.id,
            partner_id=supplier.id,
        ),
    )
    add_document_line(
        db,
        document.id,
        DocumentLineCreate(product_id=product.id, quantity=Decimal("1"), price=Decimal(cost)),
    )
    return post_document(db, document.id)


def test_latest_purchase_uses_document_date_and_calculates_markup(db: Session) -> None:
    product, warehouse, supplier = seed_catalog(db)
    latest = post_incoming(db, product, warehouse, supplier, date(2026, 8, 2), "100.00")
    post_incoming(db, product, warehouse, supplier, date(2026, 8, 1), "80.00")

    priced = attach_single_product_pricing(db, product)

    assert priced.latest_purchase_cost == Decimal("100.00")
    assert priced.latest_purchase_document_id == latest.id
    assert priced.latest_purchase_document_number == latest.number
    assert priced.latest_purchase_date == date(2026, 8, 2)
    assert priced.markup_percent == Decimal("20.00")
    assert priced.minimum_sale_price == Decimal("110.00")
    assert priced.price_review_required is False


def test_markup_below_ten_percent_requires_price_review(db: Session) -> None:
    product, warehouse, supplier = seed_catalog(db, "109.00")
    post_incoming(db, product, warehouse, supplier, date(2026, 8, 2), "100.00")

    priced = attach_single_product_pricing(db, product)

    assert priced.markup_percent == Decimal("9.00")
    assert priced.minimum_sale_price == Decimal("110.00")
    assert priced.price_review_required is True


def test_exact_ten_percent_markup_does_not_require_review(db: Session) -> None:
    product, warehouse, supplier = seed_catalog(db, "110.00")
    post_incoming(db, product, warehouse, supplier, date(2026, 8, 2), "100.00")

    assert attach_single_product_pricing(db, product).price_review_required is False


def test_cancelling_latest_purchase_falls_back_to_previous_cost(db: Session) -> None:
    product, warehouse, supplier = seed_catalog(db)
    previous = post_incoming(db, product, warehouse, supplier, date(2026, 8, 1), "80.00")
    latest = post_incoming(db, product, warehouse, supplier, date(2026, 8, 2), "100.00")

    cancel_document(db, latest.id)
    priced = attach_single_product_pricing(db, product)

    assert priced.latest_purchase_cost == Decimal("80.00")
    assert priced.latest_purchase_document_id == previous.id


def test_reposting_latest_purchase_recalculates_cost(db: Session) -> None:
    product, warehouse, supplier = seed_catalog(db, "109.00")
    incoming = post_incoming(db, product, warehouse, supplier, date(2026, 8, 2), "80.00")

    repost_document(
        db,
        incoming.id,
        DocumentRepost(
            document_type=Document.TYPE_INCOMING,
            number=incoming.number,
            document_date=incoming.document_date,
            partner_id=supplier.id,
            warehouse_id=warehouse.id,
            reason="Purchase cost correction",
            lines=[
                DocumentLineCreate(product_id=product.id, quantity=Decimal("1"), price=Decimal("100.00"))
            ],
        ),
    )

    priced = attach_single_product_pricing(db, product)
    assert priced.latest_purchase_cost == Decimal("100.00")
    assert priced.markup_percent == Decimal("9.00")
    assert priced.price_review_required is True


def test_products_api_exposes_server_pricing_fields(db: Session) -> None:
    admin = seed_auth_defaults(db)
    product, warehouse, supplier = seed_catalog(db, "109.00")
    incoming = post_incoming(db, product, warehouse, supplier, date(2026, 8, 2), "100.00")

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).get(
            "/api/v1/products",
            headers={"Authorization": f"Bearer {create_access_token(str(admin.id))}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = next(row for row in response.json() if row["id"] == product.id)
    assert payload["latest_purchase_cost"] == "100.00"
    assert payload["latest_purchase_document_id"] == incoming.id
    assert payload["markup_percent"] == "9.00"
    assert payload["minimum_sale_price"] == "110.00"
    assert payload["price_review_required"] is True
