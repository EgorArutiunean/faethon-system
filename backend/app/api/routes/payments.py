from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.accounting import Payment, PaymentAllocation
from app.models.identity import User
from app.schemas.payments import (
    PaymentAllocationOption,
    PaymentAllocationReplace,
    PaymentCreate,
    PaymentRead,
    PaymentUpdate,
)
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
        .options(
            selectinload(Payment.partner),
            selectinload(Payment.document),
            selectinload(Payment.cash_operations),
            selectinload(Payment.allocations).selectinload(PaymentAllocation.document),
        )
        .offset(skip)
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


@router.post("", response_model=PaymentRead, status_code=201)
def create_payment(
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("payments.create")),
):
    if (payload.allocations or payload.document_id is not None) and "payments.allocate" not in user.permissions:
        raise HTTPException(status_code=403, detail="Payment allocation requires manager permission")
    return payments_service.create_payment(db, payload)


@router.get(
    "/allocation-options",
    response_model=list[PaymentAllocationOption],
    dependencies=[Depends(require_permission("payments.allocate"))],
)
def payment_allocation_options(
    partner_id: int,
    payment_type: str,
    exclude_payment_id: int | None = None,
    db: Session = Depends(get_db),
):
    return payments_service.get_payment_allocation_options(
        db,
        partner_id,
        payment_type,
        exclude_payment_id=exclude_payment_id,
    )


@router.get("/{payment_id}", response_model=PaymentRead, dependencies=[Depends(require_permission("payments.read"))])
def get_payment(payment_id: int, db: Session = Depends(get_db)):
    return payments_service._load_payment(db, payment_id)


@router.patch("/{payment_id}", response_model=PaymentRead)
def update_payment(
    payment_id: int,
    payload: PaymentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("payments.update")),
):
    if (payload.allocations is not None or "document_id" in payload.model_fields_set) and "payments.allocate" not in user.permissions:
        raise HTTPException(status_code=403, detail="Payment allocation requires manager permission")
    return payments_service.update_payment(db, payment_id, payload)


@router.delete("/{payment_id}", status_code=204, dependencies=[Depends(require_permission("payments.delete"))])
def delete_payment(payment_id: int, db: Session = Depends(get_db)):
    payments_service.delete_draft_payment(db, payment_id)


@router.post("/{payment_id}/post", response_model=PaymentRead, dependencies=[Depends(require_permission("payments.post"))])
def post_payment(payment_id: int, db: Session = Depends(get_db)):
    return payments_service.post_payment(db, payment_id)


@router.put(
    "/{payment_id}/allocations",
    response_model=PaymentRead,
    dependencies=[Depends(require_permission("payments.allocate"))],
)
def replace_payment_allocations(
    payment_id: int,
    payload: PaymentAllocationReplace,
    db: Session = Depends(get_db),
):
    return payments_service.replace_posted_payment_allocations(db, payment_id, payload.allocations)


@router.post("/{payment_id}/cancel", response_model=PaymentRead, dependencies=[Depends(require_permission("payments.cancel"))])
def cancel_payment(payment_id: int, db: Session = Depends(get_db)):
    return payments_service.cancel_payment(db, payment_id)
