import json
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.document_history import DocumentHistory

router = APIRouter(
    prefix="/document-history",
    tags=["documents"],
    dependencies=[Depends(require_permission("documents.read"))],
)


@router.get("")
def list_history(
    db: Session = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    search: str = Query("", max_length=200),
    document_type: Literal["incoming", "outgoing"] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "Начальная дата позже конечной")
    filters = []
    if search.strip():
        pattern = "%" + search.strip() + "%"
        filters.append(
            or_(
                DocumentHistory.number.ilike(pattern),
                DocumentHistory.partner_name.ilike(pattern),
                DocumentHistory.partner_code.ilike(pattern),
            )
        )
    if document_type:
        filters.append(DocumentHistory.document_type == document_type)
    if date_from:
        filters.append(DocumentHistory.document_date >= date_from)
    if date_to:
        filters.append(DocumentHistory.document_date <= date_to)
    total = db.scalar(select(func.count()).select_from(DocumentHistory).where(*filters))
    records = db.scalars(
        select(DocumentHistory)
        .where(*filters)
        .order_by(DocumentHistory.document_date.desc(), DocumentHistory.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "items": [{"id": r.id, "header": json.loads(r.payload)["header"]} for r in records],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/{history_id}")
def detail(history_id: int, db: Session = Depends(get_db)):
    row = db.get(DocumentHistory, history_id)
    if row is None:
        raise HTTPException(404, "Историческая накладная не найдена")
    return {
        "id": row.id,
        **json.loads(row.payload),
        "source_database_sha256": row.source_database_sha256,
        "imported_at": row.imported_at,
        "read_only": True,
    }
