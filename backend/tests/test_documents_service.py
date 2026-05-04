from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import *  # noqa: F401,F403
from app.db.session import Base
from app.db.session import get_db
from app.main import app
from app.core.security import create_access_token
from app.models.documents import Document
from app.models.identity import Role, User
from app.models.partners import Partner
from app.models.products import Product
from app.models.stock import StockBalance, StockMovement
from app.models.stock import Warehouse
from app.schemas.documents import DocumentCreate, DocumentLineCreate, DocumentLineUpdate, DocumentUpdate
from app.services.documents_service import (
    add_document_line,
    cancel_document,
    create_document,
    delete_document_line,
    delete_draft_document,
    post_document,
    update_document_header,
    update_document_line,
)
from app.core.security import hash_password
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
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def seed_catalog(db: Session) -> tuple[Product, Warehouse, Partner]:
    product = Product(name="Bolt", sku="BOLT")
    warehouse = Warehouse(name="Main", code="MAIN")
    partner = Partner(name="Supplier", code="SUP")
    db.add_all([product, warehouse, partner])
    db.commit()
    return product, warehouse, partner


def make_document(db: Session, document_type: str, warehouse_id: int, partner_id: int | None = None) -> Document:
    return create_document(
        db,
        DocumentCreate(
            document_type=document_type,
            document_date=date(2026, 5, 1),
            warehouse_id=warehouse_id,
            partner_id=partner_id,
        ),
    )


def add_line(db: Session, document_id: int, product_id: int, quantity: str) -> None:
    add_document_line(
        db,
        document_id,
        DocumentLineCreate(product_id=product_id, quantity=Decimal(quantity), price=Decimal("10.00")),
    )


def balance_quantity(db: Session, product_id: int, warehouse_id: int) -> Decimal:
    balance = db.scalar(
        select(StockBalance).where(
            StockBalance.product_id == product_id,
            StockBalance.warehouse_id == warehouse_id,
        )
    )
    return balance.quantity if balance else Decimal("0")


def test_incoming_increases_stock(db: Session) -> None:
    product, warehouse, partner = seed_catalog(db)
    document = make_document(db, Document.TYPE_INCOMING, warehouse.id, partner.id)
    add_line(db, document.id, product.id, "5")

    post_document(db, document.id)

    assert balance_quantity(db, product.id, warehouse.id) == Decimal("5.000")


def test_outgoing_decreases_stock(db: Session) -> None:
    product, warehouse, partner = seed_catalog(db)
    incoming = make_document(db, Document.TYPE_INCOMING, warehouse.id, partner.id)
    add_line(db, incoming.id, product.id, "5")
    post_document(db, incoming.id)

    outgoing = make_document(db, Document.TYPE_OUTGOING, warehouse.id, partner.id)
    add_line(db, outgoing.id, product.id, "2")
    post_document(db, outgoing.id)

    assert balance_quantity(db, product.id, warehouse.id) == Decimal("3.000")


def test_outgoing_without_stock_is_rejected(db: Session) -> None:
    product, warehouse, partner = seed_catalog(db)
    outgoing = make_document(db, Document.TYPE_OUTGOING, warehouse.id, partner.id)
    add_line(db, outgoing.id, product.id, "2")

    with pytest.raises(HTTPException) as exc:
        post_document(db, outgoing.id)

    assert exc.value.status_code == 409
    assert balance_quantity(db, product.id, warehouse.id) == Decimal("0")


def test_cancel_document_reverses_stock(db: Session) -> None:
    product, warehouse, partner = seed_catalog(db)
    incoming = make_document(db, Document.TYPE_INCOMING, warehouse.id, partner.id)
    add_line(db, incoming.id, product.id, "5")
    post_document(db, incoming.id)

    cancel_document(db, incoming.id)

    assert balance_quantity(db, product.id, warehouse.id) == Decimal("0.000")


def test_reposting_is_rejected(db: Session) -> None:
    product, warehouse, partner = seed_catalog(db)
    incoming = make_document(db, Document.TYPE_INCOMING, warehouse.id, partner.id)
    add_line(db, incoming.id, product.id, "5")
    post_document(db, incoming.id)

    with pytest.raises(HTTPException) as exc:
        post_document(db, incoming.id)

    assert exc.value.status_code == 409


def test_cancel_draft_is_rejected(db: Session) -> None:
    _product, warehouse, partner = seed_catalog(db)
    incoming = make_document(db, Document.TYPE_INCOMING, warehouse.id, partner.id)

    with pytest.raises(HTTPException) as exc:
        cancel_document(db, incoming.id)

    assert exc.value.status_code == 409


def test_document_number_is_generated_by_type(db: Session) -> None:
    _product, warehouse, partner = seed_catalog(db)

    incoming = make_document(db, Document.TYPE_INCOMING, warehouse.id, partner.id)
    outgoing = make_document(db, Document.TYPE_OUTGOING, warehouse.id, partner.id)
    adjustment = make_document(db, Document.TYPE_ADJUSTMENT, warehouse.id, partner.id)
    second_incoming = make_document(db, Document.TYPE_INCOMING, warehouse.id, partner.id)

    assert incoming.number == "IN-000001"
    assert outgoing.number == "OUT-000001"
    assert adjustment.number == "ADJ-000001"
    assert second_incoming.number == "IN-000002"


def test_line_total_is_calculated(db: Session) -> None:
    product, warehouse, partner = seed_catalog(db)
    document = make_document(db, Document.TYPE_INCOMING, warehouse.id, partner.id)

    line = add_document_line(
        db,
        document.id,
        DocumentLineCreate(product_id=product.id, quantity=Decimal("2.5"), price=Decimal("4.00")),
    )

    assert line.line_total == Decimal("10.000")


def test_document_total_recalculates_after_adding_line(db: Session) -> None:
    product, warehouse, partner = seed_catalog(db)
    document = make_document(db, Document.TYPE_INCOMING, warehouse.id, partner.id)

    add_document_line(
        db,
        document.id,
        DocumentLineCreate(product_id=product.id, quantity=Decimal("2"), price=Decimal("4.00")),
    )

    db.refresh(document)
    assert document.total_amount == Decimal("8.00")


def test_document_total_recalculates_after_updating_line(db: Session) -> None:
    product, warehouse, partner = seed_catalog(db)
    document = make_document(db, Document.TYPE_INCOMING, warehouse.id, partner.id)
    line = add_document_line(
        db,
        document.id,
        DocumentLineCreate(product_id=product.id, quantity=Decimal("2"), price=Decimal("4.00")),
    )

    update_document_line(
        db,
        document.id,
        line.id,
        DocumentLineUpdate(quantity=Decimal("3"), price=Decimal("5.00")),
    )

    db.refresh(document)
    assert document.total_amount == Decimal("15.00")


def test_movements_are_linked_to_document(db: Session) -> None:
    product, warehouse, partner = seed_catalog(db)
    document = make_document(db, Document.TYPE_INCOMING, warehouse.id, partner.id)
    add_line(db, document.id, product.id, "4")

    post_document(db, document.id)

    movement = db.execute(select(StockMovement)).scalar_one()
    assert movement.document_id == document.id
    assert movement.document_number == "IN-000001"


def test_stock_balances_api_returns_display_names(db: Session) -> None:
    product, warehouse, partner = seed_catalog(db)
    document = make_document(db, Document.TYPE_INCOMING, warehouse.id, partner.id)
    add_line(db, document.id, product.id, "6")
    post_document(db, document.id)

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        admin = seed_auth_defaults(db)
        response = TestClient(app).get(
            "/api/v1/stock/balances",
            headers={"Authorization": f"Bearer {create_access_token(str(admin.id))}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["product_name"] == "Bolt"
    assert payload[0]["warehouse_name"] == "Main"


def test_can_edit_draft_header(db: Session) -> None:
    _product, warehouse, partner = seed_catalog(db)
    document = make_document(db, Document.TYPE_INCOMING, warehouse.id, partner.id)

    updated = update_document_header(db, document.id, DocumentUpdate(note="changed", document_date=date(2026, 5, 2)))

    assert updated.note == "changed"
    assert updated.document_date == date(2026, 5, 2)


def test_cannot_edit_posted_header(db: Session) -> None:
    product, warehouse, partner = seed_catalog(db)
    document = make_document(db, Document.TYPE_INCOMING, warehouse.id, partner.id)
    add_line(db, document.id, product.id, "1")
    post_document(db, document.id)

    with pytest.raises(HTTPException) as exc:
        update_document_header(db, document.id, DocumentUpdate(note="blocked"))

    assert exc.value.status_code == 409


def test_can_delete_draft_line_and_total_recalculates(db: Session) -> None:
    product, warehouse, partner = seed_catalog(db)
    document = make_document(db, Document.TYPE_INCOMING, warehouse.id, partner.id)
    first = add_document_line(db, document.id, DocumentLineCreate(product_id=product.id, quantity=Decimal("2"), price=Decimal("5.00")))
    first_id = first.id
    add_document_line(db, document.id, DocumentLineCreate(product_id=product.id, quantity=Decimal("3"), price=Decimal("4.00")))

    delete_document_line(db, document.id, first_id)

    db.refresh(document)
    assert document.total_amount == Decimal("12.00")
    assert db.get(type(first), first_id) is None


def test_cannot_delete_posted_line(db: Session) -> None:
    product, warehouse, partner = seed_catalog(db)
    document = make_document(db, Document.TYPE_INCOMING, warehouse.id, partner.id)
    line = add_document_line(db, document.id, DocumentLineCreate(product_id=product.id, quantity=Decimal("1"), price=Decimal("5.00")))
    post_document(db, document.id)

    with pytest.raises(HTTPException) as exc:
        delete_document_line(db, document.id, line.id)

    assert exc.value.status_code == 409


def test_can_delete_draft_document(db: Session) -> None:
    _product, warehouse, partner = seed_catalog(db)
    document = make_document(db, Document.TYPE_INCOMING, warehouse.id, partner.id)

    delete_draft_document(db, document.id)

    assert db.get(Document, document.id) is None


def test_cannot_delete_posted_document(db: Session) -> None:
    product, warehouse, partner = seed_catalog(db)
    document = make_document(db, Document.TYPE_INCOMING, warehouse.id, partner.id)
    add_line(db, document.id, product.id, "1")
    post_document(db, document.id)

    with pytest.raises(HTTPException) as exc:
        delete_draft_document(db, document.id)

    assert exc.value.status_code == 409


def test_cancelled_document_cannot_be_edited(db: Session) -> None:
    product, warehouse, partner = seed_catalog(db)
    document = make_document(db, Document.TYPE_INCOMING, warehouse.id, partner.id)
    add_line(db, document.id, product.id, "1")
    post_document(db, document.id)
    cancel_document(db, document.id)

    with pytest.raises(HTTPException) as exc:
        update_document_header(db, document.id, DocumentUpdate(note="blocked"))

    assert exc.value.status_code == 409


def test_viewer_cannot_delete_or_edit_document(db: Session) -> None:
    seed_auth_defaults(db)
    role = db.scalar(select(Role).where(Role.name == "viewer"))
    user = User(username="viewer-doc@example.com", hashed_password=hash_password("password"), is_active=True, roles=[role])
    db.add(user)
    db.commit()
    _product, warehouse, partner = seed_catalog(db)
    document = make_document(db, Document.TYPE_INCOMING, warehouse.id, partner.id)

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        headers = {"Authorization": f"Bearer {create_access_token(str(user.id))}"}
        patch_response = TestClient(app).patch(f"/api/v1/documents/{document.id}", json={"note": "blocked"}, headers=headers)
        delete_response = TestClient(app).delete(f"/api/v1/documents/{document.id}", headers=headers)
    finally:
        app.dependency_overrides.clear()

    assert patch_response.status_code == 403
    assert delete_response.status_code == 403
