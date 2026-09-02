from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.base import *  # noqa: F401,F403
from app.db.session import Base, get_db
from app.main import app
from app.models.accounting import CashOperation, Payment
from app.models.documents import Document
from app.models.identity import User
from app.models.partners import Partner
from app.models.products import Product
from app.models.stock import Warehouse
from app.schemas.documents import DocumentCreate, DocumentLineCreate, DocumentRepost
from app.schemas.payments import PaymentAllocationInput, PaymentCreate
from app.services.auth_seed import seed_auth_defaults
from app.services.documents_service import add_document_line, cancel_document, create_document, post_document, repost_document
from app.services.payments_service import (
    cancel_payment,
    create_payment,
    get_partner_balance,
    get_payment_allocation_options,
    post_payment,
    replace_posted_payment_allocations,
)


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


def setup_two_sales(db: Session) -> tuple[Product, Warehouse, Partner, Document, Document]:
    product = Product(name="Allocated product", sku="ALLOC-P", base_price=Decimal("15"))
    warehouse = Warehouse(name="Allocation warehouse", code="ALLOC-W")
    supplier = Partner(name="Allocation supplier", code="ALLOC-S", partner_type=Partner.TYPE_SUPPLIER)
    customer = Partner(name="Allocation customer", code="ALLOC-C", partner_type=Partner.TYPE_CUSTOMER)
    db.add_all([product, warehouse, supplier, customer])
    db.commit()
    incoming = create_document(
        db,
        DocumentCreate(
            document_type=Document.TYPE_INCOMING,
            document_date=date(2026, 9, 1),
            warehouse_id=warehouse.id,
            partner_id=supplier.id,
        ),
    )
    add_document_line(
        db,
        incoming.id,
        DocumentLineCreate(product_id=product.id, quantity=Decimal("10"), price=Decimal("5")),
    )
    post_document(db, incoming.id)

    sales: list[Document] = []
    for day, quantity in [(1, "2"), (2, "3")]:
        sale = create_document(
            db,
            DocumentCreate(
                document_type=Document.TYPE_OUTGOING,
                document_date=date(2026, 9, day),
                warehouse_id=warehouse.id,
                partner_id=customer.id,
            ),
        )
        add_document_line(
            db,
            sale.id,
            DocumentLineCreate(product_id=product.id, quantity=Decimal(quantity), price=Decimal("10")),
        )
        sales.append(post_document(db, sale.id))
    return product, warehouse, customer, sales[0], sales[1]


def make_allocated_payment(
    db: Session,
    partner_id: int,
    amount: str,
    allocations: list[tuple[int, str]],
) -> Payment:
    return create_payment(
        db,
        PaymentCreate(
            partner_id=partner_id,
            payment_date=date(2026, 9, 3),
            payment_type=Payment.TYPE_CUSTOMER_PAYMENT,
            amount=Decimal(amount),
            method="cash",
            allocations=[
                PaymentAllocationInput(document_id=document_id, amount=Decimal(allocation_amount))
                for document_id, allocation_amount in allocations
            ],
        ),
    )


def test_payment_can_be_split_and_remainder_stays_advance(db: Session) -> None:
    _product, _warehouse, customer, first, second = setup_two_sales(db)
    payment = make_allocated_payment(db, customer.id, "40", [(first.id, "15"), (second.id, "20")])

    posted = post_payment(db, payment.id)
    options = get_payment_allocation_options(db, customer.id, Payment.TYPE_CUSTOMER_PAYMENT)

    assert posted.allocated_amount == Decimal("35.00")
    assert posted.unallocated_amount == Decimal("5.00")
    assert posted.document_id is None
    assert get_partner_balance(db, customer.id).balance == Decimal("10.00")
    assert [(option.document_id, option.outstanding_amount) for option in options] == [
        (first.id, Decimal("5.00")),
        (second.id, Decimal("10.00")),
    ]


def test_allocation_cannot_exceed_payment_or_document_outstanding(db: Session) -> None:
    _product, _warehouse, customer, first, _second = setup_two_sales(db)

    with pytest.raises(HTTPException) as payment_error:
        make_allocated_payment(db, customer.id, "10", [(first.id, "11")])
    with pytest.raises(HTTPException) as document_error:
        make_allocated_payment(db, customer.id, "25", [(first.id, "21")])

    assert payment_error.value.status_code == 409
    assert document_error.value.status_code == 409


def test_second_payment_cannot_overallocate_posted_document(db: Session) -> None:
    _product, _warehouse, customer, first, _second = setup_two_sales(db)
    first_payment = make_allocated_payment(db, customer.id, "15", [(first.id, "15")])
    post_payment(db, first_payment.id)

    with pytest.raises(HTTPException) as exc:
        make_allocated_payment(db, customer.id, "10", [(first.id, "10")])

    assert exc.value.status_code == 409


def test_posted_payment_can_be_reallocated_without_cash_change(db: Session) -> None:
    _product, _warehouse, customer, first, second = setup_two_sales(db)
    payment = make_allocated_payment(db, customer.id, "20", [(first.id, "20")])
    post_payment(db, payment.id)
    cash_before = list(db.scalars(select(CashOperation).where(CashOperation.payment_id == payment.id)))

    reallocated = replace_posted_payment_allocations(
        db,
        payment.id,
        [PaymentAllocationInput(document_id=second.id, amount=Decimal("20"))],
    )
    cash_after = list(db.scalars(select(CashOperation).where(CashOperation.payment_id == payment.id)))

    assert [(allocation.document_id, allocation.amount) for allocation in reallocated.allocations] == [
        (second.id, Decimal("20.00"))
    ]
    assert len(cash_before) == len(cash_after) == 1
    assert cash_after[0].amount == Decimal("20.00")
    assert cash_after[0].status == CashOperation.STATUS_POSTED
    assert cash_after[0].document_id == second.id
    assert get_partner_balance(db, customer.id).balance == Decimal("30.00")


def test_document_with_allocation_requires_reallocation_before_cancel(db: Session) -> None:
    _product, _warehouse, customer, first, second = setup_two_sales(db)
    payment = make_allocated_payment(db, customer.id, "20", [(first.id, "20")])
    post_payment(db, payment.id)

    with pytest.raises(HTTPException) as exc:
        cancel_document(db, first.id)

    assert exc.value.status_code == 409
    replace_posted_payment_allocations(
        db,
        payment.id,
        [PaymentAllocationInput(document_id=second.id, amount=Decimal("20"))],
    )
    cancel_document(db, first.id)
    assert get_partner_balance(db, customer.id).balance == Decimal("10.00")


def test_document_total_cannot_drop_below_posted_allocations(db: Session) -> None:
    product, warehouse, customer, first, _second = setup_two_sales(db)
    payment = make_allocated_payment(db, customer.id, "20", [(first.id, "20")])
    post_payment(db, payment.id)

    with pytest.raises(HTTPException) as exc:
        repost_document(
            db,
            first.id,
            DocumentRepost(
                document_type=Document.TYPE_OUTGOING,
                number=first.number,
                document_date=first.document_date,
                partner_id=customer.id,
                warehouse_id=warehouse.id,
                reason="Reduce sale",
                lines=[
                    DocumentLineCreate(product_id=product.id, quantity=Decimal("1"), price=Decimal("10"))
                ],
            ),
        )

    assert exc.value.status_code == 409


def test_cancelled_payment_releases_document_outstanding(db: Session) -> None:
    _product, _warehouse, customer, first, _second = setup_two_sales(db)
    payment = make_allocated_payment(db, customer.id, "20", [(first.id, "20")])
    post_payment(db, payment.id)
    assert all(option.document_id != first.id for option in get_payment_allocation_options(db, customer.id, Payment.TYPE_CUSTOMER_PAYMENT))

    cancel_payment(db, payment.id)

    option = next(
        option
        for option in get_payment_allocation_options(db, customer.id, Payment.TYPE_CUSTOMER_PAYMENT)
        if option.document_id == first.id
    )
    assert option.outstanding_amount == Decimal("20.00")


def test_only_manager_or_admin_can_submit_allocations(db: Session) -> None:
    seed_auth_defaults(db)
    _product, _warehouse, customer, first, _second = setup_two_sales(db)
    manager = db.scalar(select(User).where(User.username == "manager@example.com"))
    cashier = db.scalar(select(User).where(User.username == "cashier@example.com"))
    assert manager is not None and cashier is not None

    def override_get_db():
        yield db

    payload = {
        "partner_id": customer.id,
        "payment_date": "2026-09-03",
        "payment_type": "customer_payment",
        "amount": "10",
        "method": "cash",
        "allocations": [{"document_id": first.id, "amount": "10"}],
    }
    app.dependency_overrides[get_db] = override_get_db
    try:
        cashier_response = TestClient(app).post(
            "/api/v1/payments",
            json=payload,
            headers={"Authorization": f"Bearer {create_access_token(str(cashier.id))}"},
        )
        manager_response = TestClient(app).post(
            "/api/v1/payments",
            json=payload,
            headers={"Authorization": f"Bearer {create_access_token(str(manager.id))}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert cashier_response.status_code == 403
    assert manager_response.status_code == 201
    assert manager_response.json()["allocated_amount"] == "10.00"
    assert manager_response.json()["allocations"][0]["document_id"] == first.id
