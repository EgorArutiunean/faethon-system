from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.db.base import *  # noqa: F401,F403
from app.db.session import Base, get_db
from app.main import app
from app.models.accounting import AuditLog, Payment, PaymentAllocation
from app.models.documents import Document, DocumentLine, DocumentNumberSequence, DocumentRevision
from app.models.identity import Permission, Role, User
from app.models.logistics import WarehouseTask
from app.models.partners import Partner
from app.models.products import Product
from app.models.stock import StockBalance, StockMovement, Warehouse
from app.schemas.document_copy import DocumentCopy
from app.schemas.documents import DocumentCreate, DocumentLineCreate
from app.services import document_copy_service, documents_service
from app.services.auth_seed import seed_auth_defaults


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def client(db: Session):
    seed_auth_defaults(db)

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def count(db: Session, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


def make_source(db: Session, status: str = "draft", document_type: str = "incoming") -> Document:
    product = Product(name="Copy original product", sku="COPY-1", is_active=True)
    other = Product(name="Copy second product", sku="COPY-2", is_active=True)
    warehouse = Warehouse(name="Copy source warehouse", code="COPY-SOURCE")
    destination = Warehouse(name="Copy destination warehouse", code="COPY-DEST")
    partner = Partner(name="Copy supplier", code="COPY-SUP", partner_type="both")
    db.add_all([product, other, warehouse, destination, partner])
    db.commit()
    source = documents_service.create_document(
        db,
        DocumentCreate(
            document_type=document_type,
            document_date=date(2025, 1, 2),
            warehouse_id=warehouse.id,
            destination_warehouse_id=destination.id if document_type == "transfer" else None,
            partner_id=None if document_type == "transfer" else partner.id,
            currency_code="USD" if document_type == "incoming" else "RUB_PMR",
            exchange_rate=Decimal("2") if document_type == "incoming" else Decimal("1"),
            note="Copied note",
        ),
    )
    for item, quantity, price in [(product, "2", "10"), (other, "1.5", "1.23")]:
        documents_service.add_document_line(
            db,
            source.id,
            DocumentLineCreate(
                product_id=item.id,
                quantity=Decimal(quantity),
                price=Decimal(price),
                foreign_price=Decimal(price) if document_type == "incoming" else None,
            ),
        )
    if status != "draft":
        documents_service.post_document(db, source.id)
        if status == "cancelled":
            documents_service.cancel_document(db, source.id)
    return documents_service._load_document(db, source.id)


@pytest.mark.parametrize("source_status", ["draft", "posted", "cancelled"])
def test_copy_is_independent_draft_without_accounting_effects(db: Session, source_status: str):
    source = make_source(db, source_status)
    source_snapshot = documents_service._document_snapshot(source)
    db.add(
        Payment(
            partner_id=source.partner_id,
            document_id=source.id,
            payment_date=date(2025, 1, 2),
            payment_type="supplier_payment",
            amount=Decimal("1"),
            status="draft",
        )
    )
    db.commit()
    effects = {
        model: count(db, model)
        for model in [
            StockBalance,
            StockMovement,
            WarehouseTask,
            DocumentRevision,
            Payment,
            PaymentAllocation,
        ]
    }
    copy = document_copy_service.copy_document(
        db, source.id, DocumentCopy(document_date=date(2026, 10, 23))
    )

    assert copy.id != source.id
    assert copy.number != source.number
    assert copy.document_date == date(2026, 10, 23)
    assert copy.status == "draft"
    assert copy.posting_version == 0
    assert copy.partner_id == source.partner_id
    assert copy.warehouse_id == source.warehouse_id
    assert copy.note == source.note
    assert copy.currency_code == "USD"
    assert copy.exchange_rate == Decimal("2")
    assert copy.total_amount == Decimal("43.69")
    assert copy.foreign_total_amount == Decimal("21.84")
    assert len(copy.lines) == 2
    assert {line.id for line in copy.lines}.isdisjoint({line.id for line in source.lines})
    assert [line.product_id for line in copy.lines] == [line.product_id for line in source.lines]
    assert [line.quantity for line in copy.lines] == [line.quantity for line in source.lines]
    assert [line.price for line in copy.lines] == [line.price for line in source.lines]
    assert [line.foreign_price for line in copy.lines] == [
        line.foreign_price for line in source.lines
    ]
    assert not copy.revisions
    assert {model: count(db, model) for model in effects} == effects
    assert documents_service._document_snapshot(source) == source_snapshot
    audit = db.scalar(
        select(AuditLog).where(AuditLog.entity_id == str(copy.id), AuditLog.action == "copy")
    )
    assert audit.details == f"source_document_id={source.id}"


def test_transfer_copy_keeps_both_warehouses_and_defaults_to_today(db: Session):
    source = make_source(db, document_type="transfer")
    copied = document_copy_service.copy_document(db, source.id, DocumentCopy())
    assert copied.document_date == date.today()
    assert copied.destination_warehouse_id == source.destination_warehouse_id
    assert copied.partner_id is None
    assert copied.currency_code == "RUB_PMR"
    assert copied.exchange_rate == Decimal("1")
    assert copied.total_amount == source.total_amount
    assert all(line.foreign_price is None for line in copied.lines)


def test_copy_recalculates_totals_instead_of_trusting_saved_aggregates(db: Session):
    source = make_source(db)
    source.total_amount = Decimal("999")
    source.foreign_total_amount = Decimal("999")
    db.commit()
    copied = document_copy_service.copy_document(db, source.id, DocumentCopy())
    assert copied.total_amount == Decimal("43.69")
    assert copied.foreign_total_amount == Decimal("21.84")
    assert source.total_amount == Decimal("999")


def test_inactive_product_rejects_entire_copy_without_consuming_number(db: Session):
    source = make_source(db)
    source.lines[-1].product.is_active = False
    db.commit()
    before = {model: count(db, model) for model in [Document, DocumentLine, AuditLog]}
    sequence = db.get(DocumentNumberSequence, source.document_type).last_value
    with pytest.raises(HTTPException) as exc:
        document_copy_service.copy_document(db, source.id, DocumentCopy())
    assert exc.value.status_code == 409
    assert {model: count(db, model) for model in before} == before
    assert db.get(DocumentNumberSequence, source.document_type).last_value == sequence


def test_failure_after_inserting_all_lines_rolls_back_document_lines_and_number(
    db: Session, monkeypatch
):
    source = make_source(db)
    before = {model: count(db, model) for model in [Document, DocumentLine, AuditLog]}
    sequence = db.get(DocumentNumberSequence, source.document_type).last_value

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit failed")

    monkeypatch.setattr(document_copy_service, "write_audit", fail_audit)
    with pytest.raises(RuntimeError, match="audit failed"):
        document_copy_service.copy_document(db, source.id, DocumentCopy())
    assert {model: count(db, model) for model in before} == before
    assert db.get(DocumentNumberSequence, source.document_type).last_value == sequence


@pytest.mark.parametrize("missing", ["documents.read", "documents.create", "documents.update"])
def test_api_requires_each_copy_permission(db: Session, client: TestClient, missing: str):
    source = make_source(db)
    required = {"documents.read", "documents.create", "documents.update"}
    permissions = list(
        db.scalars(select(Permission).where(Permission.code.in_(required - {missing})))
    )
    role = Role(name=f"copy-without-{missing}", permissions=permissions)
    user = User(
        username=f"copy-{missing}@example.com",
        hashed_password=hash_password("test-password"),
        is_active=True,
        roles=[role],
    )
    db.add(user)
    db.commit()
    token = create_access_token(str(user.id))
    response = client.post(
        f"/api/v1/documents/{source.id}/copy", headers={"Authorization": f"Bearer {token}"}, json={}
    )
    assert response.status_code == 403
    assert count(db, Document) == 1


def test_api_returns_complete_copy_and_rejects_injected_accounting_fields(
    db: Session, client: TestClient
):
    source = make_source(db, "posted")
    manager = db.scalar(select(User).where(User.username == "manager@example.com"))
    headers = {"Authorization": f"Bearer {create_access_token(str(manager.id))}"}
    rejected = client.post(
        f"/api/v1/documents/{source.id}/copy", headers=headers, json={"status": "posted"}
    )
    assert rejected.status_code == 422
    response = client.post(
        f"/api/v1/documents/{source.id}/copy", headers=headers, json={"document_date": "2026-10-23"}
    )
    assert response.status_code == 201
    copied = response.json()
    assert copied["status"] == "draft"
    assert copied["posting_version"] == 0
    assert len(copied["lines"]) == 2
    assert copied["lines"][0]["product_name"] == "Copy original product"
    assert copied["document_date"] == "2026-10-23"


def test_copy_missing_source_does_not_create_document(db: Session):
    with pytest.raises(HTTPException) as exc:
        document_copy_service.copy_document(db, 999, DocumentCopy())
    assert exc.value.status_code == 404
    assert count(db, Document) == 0
