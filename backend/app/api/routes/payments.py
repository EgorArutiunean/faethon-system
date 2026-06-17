from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.accounting import Payment
from app.schemas.payments import PaymentCreate, PaymentRead, PaymentUpdate
from app.services import payments_service

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("", response_model=list[PaymentRead], dependencies=[Depends(require_permission("payments.read"))])
def list_payments(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = Query(default=100, le=500),
):
    stmt = (
        select(Payment)
        .options(selectinload(Payment.partner), selectinload(Payment.document), selectinload(Payment.cash_operations))
        .offset(skip)
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


@router.post("", response_model=PaymentRead, status_code=201, dependencies=[Depends(require_permission("payments.create"))])
def create_payment(payload: PaymentCreate, db: Session = Depends(get_db)):
    return payments_service.create_payment(db, payload)


@router.get("/{payment_id}", response_model=PaymentRead, dependencies=[Depends(require_permission("payments.read"))])
def get_payment(payment_id: int, db: Session = Depends(get_db)):
    return payments_service._load_payment(db, payment_id)


@router.patch("/{payment_id}", response_model=PaymentRead, dependencies=[Depends(require_permission("payments.update"))])
def update_payment(payment_id: int, payload: PaymentUpdate, db: Session = Depends(get_db)):
    return payments_service.update_payment(db, payment_id, payload)


@router.delete("/{payment_id}", status_code=204, dependencies=[Depends(require_permission("payments.delete"))])
def delete_payment(payment_id: int, db: Session = Depends(get_db)):
    payments_service.delete_draft_payment(db, payment_id)


@router.post("/{payment_id}/post", response_model=PaymentRead, dependencies=[Depends(require_permission("payments.post"))])
def post_payment(payment_id: int, db: Session = Depends(get_db)):
    return payments_service.post_payment(db, payment_id)


@router.post("/{payment_id}/cancel", response_model=PaymentRead, dependencies=[Depends(require_permission("payments.cancel"))])
def cancel_payment(payment_id: int, db: Session = Depends(get_db)):
    return payments_service.cancel_payment(db, payment_id)
