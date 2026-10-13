from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import asc, desc, func, select, union
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.documents import Document
from app.models.partners import Partner
from app.schemas.documents import (
    DocumentCreate,
    DocumentDetailRead,
    DocumentLineCreate,
    DocumentLineRead,
    DocumentLineUpdate,
    DocumentPage,
    DocumentRead,
    DocumentRepost,
    DocumentRevisionRead,
    DocumentUpdate,
)
from app.services import documents_print_service, documents_service

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get(
    "",
    response_model=list[DocumentRead],
    dependencies=[Depends(require_permission("documents.read"))],
)
def list_documents(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    search: str | None = None,
    partner_id: int | None = None,
    document_type: str | None = None,
    status: str | None = None,
):
    stmt = select(Document).options(
        selectinload(Document.partner),
        selectinload(Document.warehouse),
        selectinload(Document.destination_warehouse),
    )
    if search:
        stmt = stmt.where(Document.number.ilike(f"%{search}%"))
    if partner_id is not None:
        stmt = stmt.where(Document.partner_id == partner_id)
    if document_type:
        stmt = stmt.where(Document.document_type == document_type)
    if status:
        stmt = stmt.where(Document.status == status)
    stmt = (
        stmt.order_by(Document.document_date.desc(), Document.id.desc()).offset(skip).limit(limit)
    )
    return list(db.scalars(stmt).all())


@router.get(
    "/page",
    response_model=DocumentPage,
    dependencies=[Depends(require_permission("documents.read"))],
)
def page_documents(
    db: Session = Depends(get_db),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None, max_length=200),
    document_type: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    sort_by: Literal[
        "id", "number", "document_date", "status", "document_type", "total_amount", "created_at"
    ] = "document_date",
    sort_order: Literal["asc", "desc"] = "desc",
):
    filters: list[ColumnElement[bool]] = []
    normalized_search = search.strip() if search else ""
    if normalized_search:
        pattern = f"%{normalized_search}%"
        matching_documents = union(
            select(Document.id).where(Document.number.ilike(pattern)),
            select(Document.id)
            .join(Partner, Partner.id == Document.partner_id)
            .where(Partner.name.ilike(pattern)),
        ).subquery()
        filters.append(Document.id.in_(select(matching_documents.c.id)))
    if document_type:
        filters.append(Document.document_type == document_type)
    if status_filter:
        filters.append(Document.status == status_filter)

    base = select(Document).where(*filters)
    total = db.scalar(select(func.count(Document.id)).where(*filters)) or 0
    sort_column = getattr(Document, sort_by)
    order = desc(sort_column) if sort_order == "desc" else asc(sort_column)
    stmt = (
        base.options(
            selectinload(Document.partner),
            selectinload(Document.warehouse),
            selectinload(Document.destination_warehouse),
        )
        .order_by(order, Document.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return DocumentPage(items=list(db.scalars(stmt).all()), total=total, offset=offset, limit=limit)


@router.post(
    "",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("documents.create"))],
)
def create_document(payload: DocumentCreate, db: Session = Depends(get_db)):
    return documents_service.create_document(db, payload)


@router.get(
    "/{item_id}",
    response_model=DocumentDetailRead,
    dependencies=[Depends(require_permission("documents.read"))],
)
def get_document(item_id: int, db: Session = Depends(get_db)):
    return documents_service._load_document(db, item_id)


@router.get("/{item_id}/print", dependencies=[Depends(require_permission("documents.read"))])
@router.get("/{item_id}/print.html", dependencies=[Depends(require_permission("documents.read"))])
def print_document(item_id: int, db: Session = Depends(get_db)):
    html = documents_print_service.get_invoice_html(db, item_id)
    return Response(content=html, media_type="text/html; charset=utf-8")


@router.get("/{item_id}/print.pdf", dependencies=[Depends(require_permission("documents.read"))])
def print_document_pdf(item_id: int, db: Session = Depends(get_db)):
    content = documents_print_service.get_invoice_pdf(db, item_id)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="document-{item_id}.pdf"'},
    )


@router.patch(
    "/{item_id}",
    response_model=DocumentRead,
    dependencies=[Depends(require_permission("documents.update"))],
)
def update_document(item_id: int, payload: DocumentUpdate, db: Session = Depends(get_db)):
    return documents_service.update_document_header(db, item_id, payload)


@router.post(
    "/{item_id}/post",
    response_model=DocumentRead,
    dependencies=[Depends(require_permission("documents.post"))],
)
def post_document_endpoint(item_id: int, db: Session = Depends(get_db)):
    return documents_service.post_document(db, item_id)


@router.post(
    "/{item_id}/repost",
    response_model=DocumentDetailRead,
    dependencies=[
        Depends(require_permission("documents.update")),
        Depends(require_permission("documents.post")),
    ],
)
def repost_document_endpoint(item_id: int, payload: DocumentRepost, db: Session = Depends(get_db)):
    return documents_service.repost_document(db, item_id, payload)


@router.get(
    "/{item_id}/revisions",
    response_model=list[DocumentRevisionRead],
    dependencies=[Depends(require_permission("documents.read"))],
)
def list_document_revisions(item_id: int, db: Session = Depends(get_db)):
    return documents_service.list_document_revisions(db, item_id)


@router.post(
    "/{item_id}/cancel",
    response_model=DocumentRead,
    dependencies=[Depends(require_permission("documents.cancel"))],
)
def cancel_document_endpoint(item_id: int, db: Session = Depends(get_db)):
    return documents_service.cancel_document(db, item_id)


@router.post(
    "/{item_id}/lines",
    response_model=DocumentLineRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("documents.update"))],
)
def add_document_line(item_id: int, payload: DocumentLineCreate, db: Session = Depends(get_db)):
    return documents_service.add_document_line(db, item_id, payload)


@router.patch(
    "/{item_id}/lines/{line_id}",
    response_model=DocumentLineRead,
    dependencies=[Depends(require_permission("documents.update"))],
)
def update_document_line(
    item_id: int,
    line_id: int,
    payload: DocumentLineUpdate,
    db: Session = Depends(get_db),
):
    return documents_service.update_document_line(db, item_id, line_id, payload)


@router.delete(
    "/{item_id}/lines/{line_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("documents.update"))],
)
def delete_document_line(item_id: int, line_id: int, db: Session = Depends(get_db)):
    documents_service.delete_document_line(db, item_id, line_id)


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("documents.delete"))],
)
def delete_document(item_id: int, db: Session = Depends(get_db)):
    documents_service.delete_draft_document(db, item_id)
