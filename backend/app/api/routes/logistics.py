from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.documents import Document, DocumentLine
from app.models.identity import User
from app.schemas.logistics import LogisticsDocumentLineRead, LogisticsDocumentRead

router = APIRouter(prefix="/logistics", tags=["logistics"])


def _document_query(warehouse_ids: list[int]):
    return (
        select(Document)
        .where(
            or_(
                Document.warehouse_id.in_(warehouse_ids),
                Document.destination_warehouse_id.in_(warehouse_ids),
            )
        )
        .options(
            selectinload(Document.partner),
            selectinload(Document.warehouse),
            selectinload(Document.destination_warehouse),
            selectinload(Document.lines).selectinload(DocumentLine.product),
        )
    )


def _to_logistics_document(document: Document) -> LogisticsDocumentRead:
    lines: list[LogisticsDocumentLineRead] = []
    for line in document.lines:
        sale_price = line.price if document.document_type == Document.TYPE_OUTGOING else (line.product.base_price or Decimal("0"))
        lines.append(
            LogisticsDocumentLineRead(
                id=line.id,
                product_id=line.product_id,
                product_name=line.product_name,
                quantity=line.quantity,
                sale_price=sale_price,
                sale_total=(line.quantity * sale_price).quantize(Decimal("0.01")),
            )
        )
    return LogisticsDocumentRead(
        id=document.id,
        document_type=document.document_type,
        number=document.number,
        document_date=document.document_date,
        status=document.status,
        partner_name=document.partner_name,
        warehouse_id=document.warehouse_id,
        warehouse_name=document.warehouse_name,
        destination_warehouse_id=document.destination_warehouse_id,
        destination_warehouse_name=document.destination_warehouse_name,
        lines=lines,
    )


@router.get("/documents", response_model=list[LogisticsDocumentRead])
def list_logistics_documents(
    status: str | None = None,
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("logistics.read")),
):
    warehouse_ids = user.warehouse_ids
    if not warehouse_ids:
        return []
    stmt = _document_query(warehouse_ids)
    if status:
        stmt = stmt.where(Document.status == status)
    stmt = stmt.order_by(Document.document_date.desc(), Document.id.desc()).offset(skip).limit(limit)
    return [_to_logistics_document(document) for document in db.scalars(stmt).all()]


@router.get("/documents/{document_id}", response_model=LogisticsDocumentRead)
def get_logistics_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("logistics.read")),
):
    if not user.warehouse_ids:
        raise HTTPException(status_code=404, detail="Logistics document not found")
    document = db.scalar(_document_query(user.warehouse_ids).where(Document.id == document_id))
    if document is None:
        raise HTTPException(status_code=404, detail="Logistics document not found")
    return _to_logistics_document(document)
