from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, asc, cast, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.accounting import Payment, PaymentAllocation
from app.models.documents import Document
from app.models.identity import User
from app.models.partners import Partner
from app.schemas.payments import (
    DocumentPaymentSummary,
    DocumentRelatedPayment,
    PaymentAllocationOption,
    PaymentAllocationReplace,
    PaymentCreate,
    PaymentPage,
    PaymentRead,
    PaymentUpdate,
)
from app.services import payments_service

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get(
    "/page",
    response_model=PaymentPage,
    dependencies=[Depends(require_permission("payments.read"))],
)
def page_payments(
    db: Session = Depends(get_db),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None, max_length=200),
    date_from: date | None = None,
    status: Literal["draft", "posted", "cancelled"] | None = None,
    payment_type: Literal["customer_payment", "supplier_payment", "refund"] | None = None,
    document_id: int | None = Query(default=None, gt=0),
    sort_by: Literal["payment_date", "id", "amount", "status"] = "payment_date",
    sort_order: Literal["asc", "desc"] = "desc",
):
    filters = []
    normalized_search = search.strip() if search else ""
    if normalized_search:
        pattern = f"%{normalized_search}%"
        filters.append(
            or_(
                cast(Payment.id, String).ilike(pattern),
                Payment.partner.has(Partner.name.ilike(pattern)),
                Payment.document.has(Document.number.ilike(pattern)),
                Payment.allocations.any(
                    PaymentAllocation.document.has(Document.number.ilike(pattern))
                ),
            )
        )
    if status:
        filters.append(Payment.status == status)
    if date_from:
        filters.append(Payment.payment_date >= date_from)
    if payment_type:
        filters.append(Payment.payment_type == payment_type)
    if document_id is not None:
        filters.append(_document_payment_filter(document_id))

    total = db.scalar(select(func.count(Payment.id)).where(*filters)) or 0
    sort_column = getattr(Payment, sort_by)
    order = desc(sort_column) if sort_order == "desc" else asc(sort_column)
    stmt = (
        select(Payment)
        .options(
            selectinload(Payment.partner),
            selectinload(Payment.document),
            selectinload(Payment.cash_operations),
            selectinload(Payment.allocations).selectinload(PaymentAllocation.document),
        )
        .where(*filters)
        .order_by(order, Payment.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return PaymentPage(items=list(db.scalars(stmt).all()), total=total, offset=offset, limit=limit)


def _document_payment_filter(document_id: int):
    return or_(
        Payment.document_id == document_id,
        Payment.allocations.any(PaymentAllocation.document_id == document_id),
    )


@router.get(
    "/document-summary/{document_id}",
    response_model=DocumentPaymentSummary,
    dependencies=[
        Depends(require_permission("documents.read")),
        Depends(require_permission("payments.read")),
    ],
)
def document_payment_summary(document_id: int, db: Session = Depends(get_db)):
    document = db.scalar(
        select(Document).where(Document.id == document_id).options(selectinload(Document.partner))
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    payment_type = {
        Document.TYPE_OUTGOING: Payment.TYPE_CUSTOMER_PAYMENT,
        Document.TYPE_INCOMING: Payment.TYPE_SUPPLIER_PAYMENT,
    }.get(document.document_type)
    allocated = db.scalar(
        select(func.coalesce(func.sum(PaymentAllocation.amount), 0))
        .join(Payment, Payment.id == PaymentAllocation.payment_id)
        .where(
            PaymentAllocation.document_id == document_id,
            Payment.status == Payment.STATUS_POSTED,
        )
    )
    paid_amount = Decimal(allocated or 0).quantize(Decimal("0.01"))
    payable = document.status == Document.STATUS_POSTED and payment_type is not None
    outstanding = (
        max(document.total_amount - paid_amount, Decimal("0.00")) if payable else Decimal("0.00")
    )
    linked_filter = _document_payment_filter(document_id)
    count = db.scalar(select(func.count(Payment.id)).where(linked_filter)) or 0
    linked = db.scalars(
        select(Payment)
        .options(selectinload(Payment.allocations))
        .where(linked_filter)
        .order_by(Payment.payment_date.desc(), Payment.id.desc())
        .limit(10)
    ).all()
    return DocumentPaymentSummary(
        document_id=document.id,
        document_number=document.number,
        document_type=document.document_type,
        document_status=document.status,
        partner_id=document.partner_id,
        partner_name=document.partner_name,
        total_amount=document.total_amount.quantize(Decimal("0.01")),
        paid_amount=paid_amount,
        outstanding_amount=outstanding,
        payment_type=payment_type,
        payments_count=count,
        payments=[
            DocumentRelatedPayment(
                id=payment.id,
                payment_date=payment.payment_date,
                payment_type=payment.payment_type,
                status=payment.status,
                amount=payment.amount.quantize(Decimal("0.01")),
                allocated_amount_for_document=sum(
                    (
                        allocation.amount
                        for allocation in payment.allocations
                        if allocation.document_id == document_id
                    ),
                    Decimal("0.00"),
                ).quantize(Decimal("0.01")),
            )
            for payment in linked
        ],
    )


@router.get(
    "",
    response_model=list[PaymentRead],
    dependencies=[Depends(require_permission("payments.read"))],
)
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
    if (
        payload.allocations or payload.document_id is not None
    ) and "payments.allocate" not in user.permissions:
        raise HTTPException(
            status_code=403, detail="Payment allocation requires manager permission"
        )
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


@router.get(
    "/{payment_id}",
    response_model=PaymentRead,
    dependencies=[Depends(require_permission("payments.read"))],
)
def get_payment(payment_id: int, db: Session = Depends(get_db)):
    return payments_service._load_payment(db, payment_id)


@router.patch("/{payment_id}", response_model=PaymentRead)
def update_payment(
    payment_id: int,
    payload: PaymentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("payments.update")),
):
    if (
        payload.allocations is not None or "document_id" in payload.model_fields_set
    ) and "payments.allocate" not in user.permissions:
        raise HTTPException(
            status_code=403, detail="Payment allocation requires manager permission"
        )
    return payments_service.update_payment(db, payment_id, payload)


@router.delete(
    "/{payment_id}", status_code=204, dependencies=[Depends(require_permission("payments.delete"))]
)
def delete_payment(payment_id: int, db: Session = Depends(get_db)):
    payments_service.delete_draft_payment(db, payment_id)


@router.post(
    "/{payment_id}/post",
    response_model=PaymentRead,
    dependencies=[Depends(require_permission("payments.post"))],
)
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


@router.post(
    "/{payment_id}/cancel",
    response_model=PaymentRead,
    dependencies=[Depends(require_permission("payments.cancel"))],
)
def cancel_payment(payment_id: int, db: Session = Depends(get_db)):
    return payments_service.cancel_payment(db, payment_id)
