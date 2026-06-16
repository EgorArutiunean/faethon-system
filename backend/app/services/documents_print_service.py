from html import escape
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.documents import Document, DocumentLine


TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "templates" / "invoice.html"


def _text(value: object) -> str:
    return escape("" if value is None else str(value))


def _line_rows(document: Document) -> str:
    rows: list[str] = []
    for index, line in enumerate(document.lines, start=1):
        rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td>{_text(line.product_name or line.product_id)}</td>"
            f"<td class=\"num\">{_text(line.quantity)}</td>"
            f"<td class=\"num\">{_text(line.price)}</td>"
            f"<td class=\"num\">{_text(line.line_total)}</td>"
            "</tr>"
        )
    if not rows:
        rows.append("<tr><td colspan=\"5\">Нет строк</td></tr>")
    return "\n".join(rows)


def _document_type_label(value: str) -> str:
    return {
        Document.TYPE_INCOMING: "Приход",
        Document.TYPE_OUTGOING: "Расход",
        Document.TYPE_ADJUSTMENT: "Коррекция",
        Document.TYPE_TRANSFER: "Перемещение",
    }.get(value, value)


def _status_label(value: str) -> str:
    return {
        Document.STATUS_DRAFT: "Черновик",
        Document.STATUS_POSTED: "Проведён",
        Document.STATUS_CANCELLED: "Отменён",
    }.get(value, value)


def get_invoice_html(db: Session, document_id: int) -> str:
    document = db.scalar(
        select(Document)
        .where(Document.id == document_id)
        .options(
            selectinload(Document.partner),
            selectinload(Document.warehouse),
            selectinload(Document.destination_warehouse),
            selectinload(Document.lines).selectinload(DocumentLine.product),
        )
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    values = {
        "document_number": _text(document.number or f"#{document.id}"),
        "document_date": _text(document.document_date),
        "document_type": _text(_document_type_label(document.document_type)),
        "status": _text(_status_label(document.status)),
        "warehouse_name": _text(document.warehouse_name or ""),
        "destination_warehouse_name": _text(document.destination_warehouse_name or ""),
        "partner_name": _text(document.partner_name or ""),
        "total_amount": _text(document.total_amount),
        "line_rows": _line_rows(document),
    }
    for key, value in values.items():
        template = template.replace(f"{{{{{key}}}}}", value)
    return template
