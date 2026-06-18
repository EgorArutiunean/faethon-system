from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.documents import Document
from app.schemas.documents import (
    DocumentCreate,
    DocumentDetailRead,
    DocumentLineCreate,
    DocumentLineRead,
    DocumentLineUpdate,
    DocumentRead,
    DocumentUpdate,
)
from app.services import documents_print_service, documents_service

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentRead], dependencies=[Depends(require_permission("documents.read"))])
def list_documents(db: Session = Depends(get_db), skip: int = 0, limit: int = Query(default=100, le=500), search: str | None = None):
    stmt = (
        select(Document)
        .options(selectinload(Document.partner), selectinload(Document.warehouse), selectinload(Document.destination_warehouse))
        .offset(skip)
        .limit(limit)
    )
    if search:
        stmt = stmt.where(Document.number.ilike(f"%{search}%"))
    return list(db.scalars(stmt).all())


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("documents.create"))])
def create_document(payload: DocumentCreate, db: Session = Depends(get_db)):
    return documents_service.create_document(db, payload)


@router.get("/{item_id}", response_model=DocumentDetailRead, dependencies=[Depends(require_permission("documents.read"))])
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


@router.patch("/{item_id}", response_model=DocumentRead, dependencies=[Depends(require_permission("documents.update"))])
def update_document(item_id: int, payload: DocumentUpdate, db: Session = Depends(get_db)):
    return documents_service.update_document_header(db, item_id, payload)


@router.post("/{item_id}/post", response_model=DocumentRead, dependencies=[Depends(require_permission("documents.post"))])
def post_document_endpoint(item_id: int, db: Session = Depends(get_db)):
    return documents_service.post_document(db, item_id)


@router.post("/{item_id}/cancel", response_model=DocumentRead, dependencies=[Depends(require_permission("documents.cancel"))])
def cancel_document_endpoint(item_id: int, db: Session = Depends(get_db)):
    return documents_service.cancel_document(db, item_id)


@router.post("/{item_id}/lines", response_model=DocumentLineRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("documents.update"))])
def add_document_line(item_id: int, payload: DocumentLineCreate, db: Session = Depends(get_db)):
    return documents_service.add_document_line(db, item_id, payload)


@router.patch("/{item_id}/lines/{line_id}", response_model=DocumentLineRead, dependencies=[Depends(require_permission("documents.update"))])
def update_document_line(
    item_id: int,
    line_id: int,
    payload: DocumentLineUpdate,
    db: Session = Depends(get_db),
):
    return documents_service.update_document_line(db, item_id, line_id, payload)


@router.delete("/{item_id}/lines/{line_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("documents.update"))])
def delete_document_line(item_id: int, line_id: int, db: Session = Depends(get_db)):
    documents_service.delete_document_line(db, item_id, line_id)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("documents.delete"))])
def delete_document(item_id: int, db: Session = Depends(get_db)):
    documents_service.delete_draft_document(db, item_id)
