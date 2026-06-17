from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import *  # noqa: F401,F403
from app.db.session import Base
from app.models.accounting import Payment
from app.models.documents import Document
from app.models.partners import Partner
from app.models.products import Product
from app.models.stock import Warehouse
from app.schemas.documents import DocumentCreate, DocumentLineCreate
from app.schemas.payments import PaymentCreate, PaymentUpdate
from app.services.documents_service import add_document_line, cancel_document, create_document, post_document
from app.services.payments_service import cancel_payment, create_payment, delete_draft_payment, get_partner_balance, post_payment, update_payment


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


def seed(db: Session) -> tuple[Product, Warehouse, Partner]:
    product = Product(name="Bolt", sku="BOLT")
    warehouse = Warehouse(name="Main", code="MAIN")
    partner = Partner(name="Customer", code="CUST")
    db.add_all([product, warehouse, partner])
    db.commit()
    return product, warehouse, partner


def posted_document(db: Session, document_type: str, total_qty: str = "2") -> tuple[Document, Partner]:
    product, warehouse, partner = seed(db)
    if document_type == Document.TYPE_OUTGOING:
        supplier = Partner(name="Supplier", code="SUP")
        db.add(supplier)
        db.commit()
        incoming = create_document(
            db,
            DocumentCreate(document_type=Document.TYPE_INCOMING, document_date=date(2026, 5, 1), warehouse_id=warehouse.id, partner_id=supplier.id),
        )
        add_document_line(db, incoming.id, DocumentLineCreate(product_id=product.id, quantity=Decimal("10"), price=Decimal("1")))
        post_document(db, incoming.id)
    document = create_document(
        db,
        DocumentCreate(document_type=document_type, document_date=date(2026, 5, 2), warehouse_id=warehouse.id, partner_id=partner.id),
    )
    add_document_line(db, document.id, DocumentLineCreate(product_id=product.id, quantity=Decimal(total_qty), price=Decimal("10")))
    post_document(db, document.id)
    return document, partner


def make_payment(db: Session, partner_id: int, amount: str, payment_type: str = Payment.TYPE_CUSTOMER_PAYMENT) -> Payment:
    return create_payment(
        db,
        PaymentCreate(
            partner_id=partner_id,
            payment_date=date(2026, 5, 3),
            payment_type=payment_type,
            amount=Decimal(amount),
            method="cash",
        ),
    )


def test_outgoing_document_creates_partner_debt(db: Session) -> None:
    _document, partner = posted_document(db, Document.TYPE_OUTGOING)

    balance = get_partner_balance(db, partner.id)

    assert balance.balance == Decimal("20.00")


def test_customer_payment_reduces_debt(db: Session) -> None:
    _document, partner = posted_document(db, Document.TYPE_OUTGOING)
    payment = make_payment(db, partner.id, "7.50")

    post_payment(db, payment.id)

    assert get_partner_balance(db, partner.id).balance == Decimal("12.50")


def test_overpayment_is_credit_balance(db: Session) -> None:
    _document, partner = posted_document(db, Document.TYPE_OUTGOING)
    payment = make_payment(db, partner.id, "30.00")

    post_payment(db, payment.id)

    assert get_partner_balance(db, partner.id).balance == Decimal("-10.00")


def test_cancel_payment_restores_debt(db: Session) -> None:
    _document, partner = posted_document(db, Document.TYPE_OUTGOING)
    payment = make_payment(db, partner.id, "5.00")
    post_payment(db, payment.id)

    cancel_payment(db, payment.id)

    assert get_partner_balance(db, partner.id).balance == Decimal("20.00")


def test_cancel_document_changes_partner_balance(db: Session) -> None:
    document, partner = posted_document(db, Document.TYPE_OUTGOING)

    cancel_document(db, document.id)

    assert get_partner_balance(db, partner.id).balance == Decimal("0")


def test_reposting_payment_is_rejected(db: Session) -> None:
    _document, partner = posted_document(db, Document.TYPE_OUTGOING)
    payment = make_payment(db, partner.id, "5.00")
    post_payment(db, payment.id)

    with pytest.raises(HTTPException) as exc:
        post_payment(db, payment.id)

    assert exc.value.status_code == 409


def test_cancel_draft_payment_is_rejected(db: Session) -> None:
    _document, partner = posted_document(db, Document.TYPE_OUTGOING)
    payment = make_payment(db, partner.id, "5.00")

    with pytest.raises(HTTPException) as exc:
        cancel_payment(db, payment.id)

    assert exc.value.status_code == 409


def test_update_draft_payment_changes_editable_fields(db: Session) -> None:
    _document, partner = posted_document(db, Document.TYPE_OUTGOING)
    payment = make_payment(db, partner.id, "5.00")

    updated = update_payment(
        db,
        payment.id,
        PaymentUpdate(
            payment_date=date(2026, 5, 4),
            amount=Decimal("6.25"),
            method="bank",
            note="corrected before posting",
        ),
    )

    assert updated.payment_date == date(2026, 5, 4)
    assert updated.amount == Decimal("6.25")
    assert updated.method == "bank"
    assert updated.note == "corrected before posting"


def test_update_posted_payment_is_rejected(db: Session) -> None:
    _document, partner = posted_document(db, Document.TYPE_OUTGOING)
    payment = make_payment(db, partner.id, "5.00")
    post_payment(db, payment.id)

    with pytest.raises(HTTPException) as exc:
        update_payment(db, payment.id, PaymentUpdate(amount=Decimal("6.25")))

    assert exc.value.status_code == 409


def test_delete_draft_payment_removes_payment(db: Session) -> None:
    _document, partner = posted_document(db, Document.TYPE_OUTGOING)
    payment = make_payment(db, partner.id, "5.00")

    delete_draft_payment(db, payment.id)

    assert db.get(Payment, payment.id) is None


def test_delete_posted_payment_is_rejected(db: Session) -> None:
    _document, partner = posted_document(db, Document.TYPE_OUTGOING)
    payment = make_payment(db, partner.id, "5.00")
    post_payment(db, payment.id)

    with pytest.raises(HTTPException) as exc:
        delete_draft_payment(db, payment.id)

    assert exc.value.status_code == 409
    assert db.get(Payment, payment.id) is not None


def test_update_payment_validates_partner_type(db: Session) -> None:
    _document, partner = posted_document(db, Document.TYPE_OUTGOING)
    supplier = Partner(name="Only Supplier", code="ONLY-SUP", partner_type=Partner.TYPE_SUPPLIER)
    db.add(supplier)
    db.commit()
    payment = make_payment(db, partner.id, "5.00")

    with pytest.raises(HTTPException) as exc:
        update_payment(db, payment.id, PaymentUpdate(partner_id=supplier.id, payment_type=Payment.TYPE_CUSTOMER_PAYMENT))

    assert exc.value.status_code == 409
