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
    create_cash_operation(
        db,
        CashOperationCreate(operation_date=date(2026, 5, 1), operation_type=CashOperation.TYPE_CASH_IN, amount=Decimal("30.00")),
    )
    payment = make_payment(db, obj.id, Payment.TYPE_SUPPLIER_PAYMENT)

    post_payment(db, payment.id)

    operation = db.scalar(select(CashOperation).where(CashOperation.payment_id == payment.id))
    assert operation is not None
    assert operation.operation_type == CashOperation.TYPE_CASH_OUT
    assert get_cash_balance(db).balance == Decimal("5.00")


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
        CashOperationCreate(operation_date=date(2026, 5, 1), operation_type=CashOperation.TYPE_CASH_IN, amount=Decimal("10.00")),
    )
    create_cash_operation(
        db,
        CashOperationCreate(operation_date=date(2026, 5, 1), operation_type=CashOperation.TYPE_CASH_OUT, amount=Decimal("4.00")),
    )

    assert get_cash_balance(db).balance == Decimal("6.00")


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
        CashOperationCreate(operation_date=date(2026, 5, 1), operation_type=CashOperation.TYPE_CASH_IN, amount=Decimal("3.00")),
    )
    create_cash_operation(
        db,
        CashOperationCreate(operation_date=date(2026, 5, 3), operation_type=CashOperation.TYPE_CASH_OUT, amount=Decimal("1.00")),
    )

    rows = get_cash_book(db)

    assert [row.operation_date for row in rows] == [date(2026, 5, 1), date(2026, 5, 3)]
    assert [row.balance for row in rows] == [Decimal("3.00"), Decimal("2.00")]


def test_cash_out_cannot_make_balance_negative(db: Session) -> None:
    with pytest.raises(HTTPException) as exc:
        create_cash_operation(
            db,
            CashOperationCreate(operation_date=date(2026, 5, 1), operation_type=CashOperation.TYPE_CASH_OUT, amount=Decimal("0.01")),
        )

    assert exc.value.status_code == 409
    assert get_cash_balance(db).balance == Decimal("0")


def test_cash_correction_sets_final_balance_and_stores_difference(db: Session) -> None:
    create_cash_operation(
        db,
        CashOperationCreate(operation_date=date(2026, 5, 1), operation_type=CashOperation.TYPE_CASH_IN, amount=Decimal("1000.00")),
    )

    correction = create_cash_operation(
        db,
        CashOperationCreate(
            operation_date=date(2026, 5, 2),
            operation_type=CashOperation.TYPE_CORRECTION,
            amount=Decimal("950.00"),
            note="Cash count",
        ),
    )

    assert correction.amount == Decimal("50.00")
    assert correction.direction == "out"
    assert correction.target_balance == Decimal("950.00")
    assert get_cash_balance(db).balance == Decimal("950.00")


def test_cash_correction_requires_reason(db: Session) -> None:
    with pytest.raises(HTTPException) as exc:
        create_cash_operation(
            db,
            CashOperationCreate(
                operation_date=date(2026, 5, 1),
                operation_type=CashOperation.TYPE_CORRECTION,
                amount=Decimal("0"),
            ),
        )

    assert exc.value.status_code == 422


def test_cancelling_cash_in_cannot_make_historical_balance_negative(db: Session) -> None:
    cash_in = create_cash_operation(
        db,
        CashOperationCreate(operation_date=date(2026, 5, 1), operation_type=CashOperation.TYPE_CASH_IN, amount=Decimal("10.00")),
    )
    create_cash_operation(
        db,
        CashOperationCreate(operation_date=date(2026, 5, 2), operation_type=CashOperation.TYPE_CASH_OUT, amount=Decimal("4.00")),
    )

    with pytest.raises(HTTPException) as exc:
        cancel_cash_operation(db, cash_in.id)

    assert exc.value.status_code == 409
    assert get_cash_balance(db).balance == Decimal("6.00")
