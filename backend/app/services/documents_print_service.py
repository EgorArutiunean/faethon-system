from datetime import datetime
from decimal import Decimal
from html import escape
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.documents import Document, DocumentLine


TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "templates" / "invoice.html"


def _text(value: object) -> str:
    return escape("" if value is None else str(value))


def _money(value: Decimal | None) -> str:
    return "" if value is None else f"{value:.2f}"


def _quantity(value: Decimal | None) -> str:
    return "" if value is None else f"{value:.3f}".rstrip("0").rstrip(".")


def _address_block(*parts: object) -> str:
    visible = [_text(part) for part in parts if part]
    return "<br>".join(visible) if visible else "&mdash;"


def _line_rows(document: Document) -> str:
    rows: list[str] = []
    for index, line in enumerate(document.lines, start=1):
        rows.append(
            "<tr>"
            f"<td class=\"center\">{index}</td>"
            f"<td>{_text(line.product_name or line.product_id)}</td>"
            f"<td class=\"num\">{_quantity(line.quantity)}</td>"
            f"<td class=\"num\">{_money(line.price)}</td>"
            f"<td class=\"num strong\">{_money(line.line_total)}</td>"
            "</tr>"
        )
    if not rows:
        rows.append("<tr><td colspan=\"5\" class=\"empty\">\u041d\u0435\u0442 \u0441\u0442\u0440\u043e\u043a</td></tr>")
    return "\n".join(rows)


def _document_type_label(value: str) -> str:
    return {
        Document.TYPE_INCOMING: "\u041f\u0440\u0438\u0445\u043e\u0434",
        Document.TYPE_OUTGOING: "\u0420\u0430\u0441\u0445\u043e\u0434",
        Document.TYPE_ADJUSTMENT: "\u041a\u043e\u0440\u0440\u0435\u043a\u0446\u0438\u044f",
        Document.TYPE_TRANSFER: "\u041f\u0435\u0440\u0435\u043c\u0435\u0449\u0435\u043d\u0438\u0435",
    }.get(value, value)


def _status_label(value: str) -> str:
    return {
        Document.STATUS_DRAFT: "\u0427\u0435\u0440\u043d\u043e\u0432\u0438\u043a",
        Document.STATUS_POSTED: "\u041f\u0440\u043e\u0432\u0435\u0434\u0451\u043d",
        Document.STATUS_CANCELLED: "\u041e\u0442\u043c\u0435\u043d\u0451\u043d",
    }.get(value, value)


def _document_title(document: Document) -> str:
    if document.document_type == Document.TYPE_INCOMING:
        return "\u041f\u0440\u0438\u0445\u043e\u0434\u043d\u0430\u044f \u043d\u0430\u043a\u043b\u0430\u0434\u043d\u0430\u044f"
    if document.document_type == Document.TYPE_OUTGOING:
        return "\u0420\u0430\u0441\u0445\u043e\u0434\u043d\u0430\u044f \u043d\u0430\u043a\u043b\u0430\u0434\u043d\u0430\u044f"
    if document.document_type == Document.TYPE_TRANSFER:
        return "\u041d\u0430\u043a\u043b\u0430\u0434\u043d\u0430\u044f \u043d\u0430 \u043f\u0435\u0440\u0435\u043c\u0435\u0449\u0435\u043d\u0438\u0435"
    if document.document_type == Document.TYPE_ADJUSTMENT:
        return "\u0410\u043a\u0442 \u043a\u043e\u0440\u0440\u0435\u043a\u0446\u0438\u0438 \u043e\u0441\u0442\u0430\u0442\u043a\u043e\u0432"
    return "\u0414\u043e\u043a\u0443\u043c\u0435\u043d\u0442"


def _watermark(document: Document) -> str:
    if document.status == Document.STATUS_DRAFT:
        return "<div class=\"watermark\">\u0427\u0415\u0420\u041d\u041e\u0412\u0418\u041a</div>"
    if document.status == Document.STATUS_CANCELLED:
        return "<div class=\"watermark danger\">\u041e\u0422\u041c\u0415\u041d\u0401\u041d</div>"
    return ""


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

    partner = document.partner
    warehouse = document.warehouse
    destination = document.destination_warehouse
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    values = {
        "document_title": _text(_document_title(document)),
        "document_number": _text(document.number or f"#{document.id}"),
        "document_date": _text(document.document_date),
        "document_type": _text(_document_type_label(document.document_type)),
        "status": _text(_status_label(document.status)),
        "warehouse_name": _text(document.warehouse_name or "\u2014"),
        "warehouse_details": _address_block(warehouse.code if warehouse else None, warehouse.address if warehouse else None),
        "destination_warehouse_name": _text(document.destination_warehouse_name or "\u2014"),
        "destination_warehouse_details": _address_block(destination.code if destination else None, destination.address if destination else None),
        "partner_name": _text(document.partner_name or "\u2014"),
        "partner_details": _address_block(
            partner.code if partner else None,
            partner.tax_id if partner else None,
            partner.phone if partner else None,
            partner.address if partner else None,
        ),
        "note": _text(document.note or "\u2014"),
        "total_amount": _money(document.total_amount),
        "line_rows": _line_rows(document),
        "watermark": _watermark(document),
        "generated_at": _text(datetime.now().strftime("%Y-%m-%d %H:%M")),
    }
    for key, value in values.items():
        template = template.replace(f"{{{{{key}}}}}", value)
    return template
