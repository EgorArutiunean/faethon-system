from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.documents import Document, DocumentLine
from app.schemas.document_copy import DocumentCopy
from app.services import documents_service
from app.services.audit_writer import write_audit


def copy_document(db: Session, source_id: int, payload: DocumentCopy) -> Document:
    """Copy saved business data into one independently numbered, unposted draft."""
    try:
        source = documents_service._load_document(db, source_id, for_update=True)
        documents_service._validate_document_partner(db, source.document_type, source.partner_id)
        documents_service._validate_document_warehouse_references(
            db, source.document_type, source.warehouse_id, source.destination_warehouse_id
        )
        currency_code, exchange_rate = documents_service._normalize_document_currency(
            db, source.document_type, source.currency_code, source.exchange_rate
        )
        copied = Document(
            document_type=source.document_type,
            document_date=payload.document_date or date.today(),
            status=Document.STATUS_DRAFT,
            posting_version=0,
            partner_id=source.partner_id,
            warehouse_id=source.warehouse_id,
            destination_warehouse_id=source.destination_warehouse_id,
            currency_code=currency_code,
            exchange_rate=exchange_rate,
            note=source.note,
        )
        for line in sorted(source.lines, key=lambda item: item.id):
            documents_service._validate_document_line(
                db, source.document_type, line.product_id, line.quantity
            )
            foreign_price = None
            if source.document_type == Document.TYPE_INCOMING:
                foreign_price = line.foreign_price
                if foreign_price is None:
                    foreign_price = (line.price / exchange_rate).quantize(Decimal("0.01"))
            price = documents_service._base_price(copied, line.price, foreign_price)
            copied.lines.append(
                DocumentLine(
                    product_id=line.product_id,
                    quantity=line.quantity,
                    price=price,
                    foreign_price=foreign_price,
                    line_total=documents_service._line_total(line.quantity, price),
                    foreign_line_total=(
                        documents_service._line_total(line.quantity, foreign_price)
                        if foreign_price is not None
                        else None
                    ),
                )
            )
        documents_service.recalculate_document_total(copied)
        copied.number = documents_service._normalize_document_number(db, source.document_type, None)
        db.add(copied)
        db.flush()
        write_audit(db, "document", copied.id, "copy", f"source_document_id={source.id}")
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Could not create a unique document copy"
        ) from exc
    except Exception:
        db.rollback()
        raise
    return documents_service._load_document(db, copied.id)
