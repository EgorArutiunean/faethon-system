import os
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import *  # noqa: F401,F403
from app.db.session import Base
from app.models.accounting import CashOperation, PaymentAllocation
from app.models.documents import Document
from app.models.partners import Partner
from app.models.products import Product
from app.models.stock import StockBalance, StockMovement, Warehouse
from app.schemas.documents import DocumentCreate, DocumentLineCreate
from app.schemas.payments import PaymentAllocationInput, PaymentCreate
from app.services.cash_service import get_cash_balance
from app.services.currency_service import seed_default_currencies
from app.services.documents_service import add_document_line, create_document, post_document
from app.services.payments_service import create_payment, get_partner_balance, post_payment

POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not POSTGRES_URL, reason="TEST_POSTGRES_URL is not configured")


@pytest.fixture()
def postgres_db() -> Session:
    assert POSTGRES_URL is not None
    engine = create_engine(POSTGRES_URL, pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    session = factory()
    seed_default_currencies(session)
    session.commit()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def seed_parties_and_stock(
    postgres_db: Session,
) -> tuple[Product, Warehouse, Partner, Partner, Document]:
    product = Product(name="PostgreSQL core product", sku="PG-CORE-PRODUCT")
    warehouse = Warehouse(name="PostgreSQL core warehouse", code="PG-CORE-WH")
    supplier = Partner(
        name="PostgreSQL core supplier",
        code="PG-CORE-SUP",
        partner_type=Partner.TYPE_SUPPLIER,
    )
    customer = Partner(
        name="PostgreSQL core customer",
        code="PG-CORE-CUS",
        partner_type=Partner.TYPE_CUSTOMER,
    )
    postgres_db.add_all([product, warehouse, supplier, customer])
    postgres_db.commit()

    incoming = create_document(
        postgres_db,
        DocumentCreate(
            document_type=Document.TYPE_INCOMING,
            document_date=date(2026, 10, 11),
            warehouse_id=warehouse.id,
            partner_id=supplier.id,
        ),
    )
    add_document_line(
        postgres_db,
        incoming.id,
        DocumentLineCreate(product_id=product.id, quantity=Decimal("5"), price=Decimal("80")),
    )
    post_document(postgres_db, incoming.id)
    return product, warehouse, supplier, customer, incoming


def create_sale(
    postgres_db: Session,
    *,
    product_id: int,
    warehouse_id: int,
    customer_id: int,
    quantity: str,
) -> Document:
    sale = create_document(
        postgres_db,
        DocumentCreate(
            document_type=Document.TYPE_OUTGOING,
            document_date=date(2026, 10, 11),
            warehouse_id=warehouse_id,
            partner_id=customer_id,
        ),
    )
    add_document_line(
        postgres_db,
        sale.id,
        DocumentLineCreate(
            product_id=product_id,
            quantity=Decimal(quantity),
            price=Decimal("150"),
        ),
    )
    return sale


def test_postgresql_stock_ledger_and_failed_sale_are_atomic(postgres_db: Session) -> None:
    product, warehouse, _supplier, customer, _incoming = seed_parties_and_stock(postgres_db)
    sale = create_sale(
        postgres_db,
        product_id=product.id,
        warehouse_id=warehouse.id,
        customer_id=customer.id,
        quantity="2",
    )
    post_document(postgres_db, sale.id)

    rejected_sale = create_sale(
        postgres_db,
        product_id=product.id,
        warehouse_id=warehouse.id,
        customer_id=customer.id,
        quantity="4",
    )
    with pytest.raises(HTTPException) as exc:
        post_document(postgres_db, rejected_sale.id)

    assert exc.value.status_code == 409
    balance = postgres_db.scalar(
        select(StockBalance).where(
            StockBalance.product_id == product.id,
            StockBalance.warehouse_id == warehouse.id,
        )
    )
    movements = list(
        postgres_db.scalars(
            select(StockMovement)
            .where(StockMovement.product_id == product.id)
            .order_by(StockMovement.id)
        )
    )
    postgres_db.refresh(rejected_sale)

    assert balance is not None
    assert balance.quantity == Decimal("3.000")
    assert [movement.quantity_delta for movement in movements] == [
        Decimal("5.000"),
        Decimal("-2.000"),
    ]
    assert rejected_sale.status == Document.STATUS_DRAFT


def test_postgresql_partial_payment_updates_debt_allocation_and_cash(postgres_db: Session) -> None:
    product, warehouse, _supplier, customer, _incoming = seed_parties_and_stock(postgres_db)
    sale = create_sale(
        postgres_db,
        product_id=product.id,
        warehouse_id=warehouse.id,
        customer_id=customer.id,
        quantity="2",
    )
    post_document(postgres_db, sale.id)

    payment = create_payment(
        postgres_db,
        PaymentCreate(
            partner_id=customer.id,
            payment_date=date(2026, 10, 11),
            payment_type="customer_payment",
            amount=Decimal("120"),
            method="cash",
            allocations=[PaymentAllocationInput(document_id=sale.id, amount=Decimal("120"))],
        ),
    )
    posted = post_payment(postgres_db, payment.id)
    allocation = postgres_db.scalar(
        select(PaymentAllocation).where(PaymentAllocation.payment_id == payment.id)
    )
    cash_operation = postgres_db.scalar(
        select(CashOperation).where(CashOperation.payment_id == payment.id)
    )

    assert posted.status == "posted"
    assert allocation is not None
    assert allocation.document_id == sale.id
    assert allocation.amount == Decimal("120.00")
    assert get_partner_balance(postgres_db, customer.id).balance == Decimal("180.00")
    assert get_cash_balance(postgres_db).balance == Decimal("120.00")
    assert cash_operation is not None
    assert cash_operation.operation_type == CashOperation.TYPE_CASH_IN
    assert cash_operation.status == CashOperation.STATUS_POSTED
