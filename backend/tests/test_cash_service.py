from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import pytest
from fastapi import HTTPException

from app.db.base import *  # noqa: F401,F403
from app.db.session import Base
from app.models.accounting import CashOperation, Payment
from app.models.partners import Partner
from app.schemas.cash import CashOperationCreate
from app.schemas.payments import PaymentCreate
from app.services.cash_service import cancel_cash_operation, create_cash_operation, get_cash_balance, get_cash_book
from app.services.payments_service import cancel_payment, create_payment, post_payment


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


def partner(db: Session) -> Partner:
    obj = Partner(name="Cash Partner", code="CASH")
    db.add(obj)
    db.commit()
    return obj


def make_payment(db: Session, partner_id: int, payment_type: str) -> Payment:
    return create_payment(
        db,
        PaymentCreate(
            partner_id=partner_id,
            payment_date=date(2026, 5, 2),
            payment_type=payment_type,
            amount=Decimal("25.00"),
            method="cash",
        ),
    )


def test_customer_payment_creates_cash_in(db: Session) -> None:
    obj = partner(db)
    payment = make_payment(db, obj.id, Payment.TYPE_CUSTOMER_PAYMENT)

    post_payment(db, payment.id)

    operation = db.scalar(select(CashOperation).where(CashOperation.payment_id == payment.id))
    assert operation is not None
    assert operation.operation_type == CashOperation.TYPE_CASH_IN
    assert get_cash_balance(db).balance == Decimal("25.00")


def test_supplier_payment_creates_cash_out(db: Session) -> None:
    obj = partner(db)
    payment = make_payment(db, obj.id, Payment.TYPE_SUPPLIER_PAYMENT)

    post_payment(db, payment.id)

    operation = db.scalar(select(CashOperation).where(CashOperation.payment_id == payment.id))
    assert operation is not None
    assert operation.operation_type == CashOperation.TYPE_CASH_OUT
    assert get_cash_balance(db).balance == Decimal("-25.00")


def test_cancel_payment_cancels_linked_cash_operation(db: Session) -> None:
    obj = partner(db)
    payment = make_payment(db, obj.id, Payment.TYPE_CUSTOMER_PAYMENT)
    post_payment(db, payment.id)

    cancel_payment(db, payment.id)

    operation = db.scalar(select(CashOperation).where(CashOperation.payment_id == payment.id))
    assert operation is not None
    assert operation.status == CashOperation.STATUS_CANCELLED
    assert get_cash_balance(db).balance == Decimal("0")


def test_manual_cash_in_increases_balance(db: Session) -> None:
    create_cash_operation(
        db,
        CashOperationCreate(operation_date=date(2026, 5, 1), operation_type=CashOperation.TYPE_CASH_IN, amount=Decimal("10.00")),
    )

    assert get_cash_balance(db).balance == Decimal("10.00")


def test_manual_cash_out_decreases_balance(db: Session) -> None:
    create_cash_operation(
        db,
        CashOperationCreate(operation_date=date(2026, 5, 1), operation_type=CashOperation.TYPE_CASH_OUT, amount=Decimal("4.00")),
    )

    assert get_cash_balance(db).balance == Decimal("-4.00")


def test_cancelled_cash_operation_does_not_affect_balance(db: Session) -> None:
    operation = create_cash_operation(
        db,
        CashOperationCreate(operation_date=date(2026, 5, 1), operation_type=CashOperation.TYPE_CASH_IN, amount=Decimal("10.00")),
    )

    cancel_cash_operation(db, operation.id)

    assert get_cash_balance(db).balance == Decimal("0")
    with pytest.raises(HTTPException):
        cancel_cash_operation(db, operation.id)


def test_cash_book_returns_operations_by_date(db: Session) -> None:
    create_cash_operation(
        db,
        CashOperationCreate(operation_date=date(2026, 5, 3), operation_type=CashOperation.TYPE_CASH_IN, amount=Decimal("3.00")),
    )
    create_cash_operation(
        db,
        CashOperationCreate(operation_date=date(2026, 5, 1), operation_type=CashOperation.TYPE_CASH_OUT, amount=Decimal("1.00")),
    )

    rows = get_cash_book(db)

    assert [row.operation_date for row in rows] == [date(2026, 5, 1), date(2026, 5, 3)]
    assert [row.balance for row in rows] == [Decimal("-1.00"), Decimal("2.00")]
