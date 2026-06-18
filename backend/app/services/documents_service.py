from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.accounting import AuditLog
from app.models.documents import Document, DocumentLine
from app.models.partners import Partner
from app.models.stock import StockBalance, StockMovement
from app.schemas.documents import DocumentCreate, DocumentLineCreate, DocumentLineUpdate, DocumentUpdate
from app.services.currency_service import BASE_CURRENCY_CODE, get_currency


class DocumentRulesError(ValueError):
    pass


def _line_total(quantity: Decimal, price: Decimal) -> Decimal:
    return (quantity * price).quantize(Decimal("0.01"))


def _normalize_rate(value: Decimal | None) -> Decimal:
    rate = value or Decimal("1")
    if rate <= 0:
        raise HTTPException(status_code=422, detail="Exchange rate must be greater than zero")
    return rate


def _base_price(document: Document, price: Decimal, foreign_price: Decimal | None) -> Decimal:
    if document.document_type == Document.TYPE_INCOMING:
        return ((foreign_price if foreign_price is not None else price) * document.exchange_rate).quantize(Decimal("0.01"))
    return price.quantize(Decimal("0.01"))


def _document_prefix(document_type: str) -> str:
    prefixes = {
        Document.TYPE_INCOMING: "IN",
        Document.TYPE_OUTGOING: "OUT",
        Document.TYPE_ADJUSTMENT: "ADJ",
        Document.TYPE_TRANSFER: "TR",
    }
    try:
        return prefixes[document_type]
    except KeyError as exc:
        raise HTTPException(status_code=422, detail="Invalid document type") from exc


def _generate_document_number(db: Session, document_type: str) -> str:
    # TODO LEGACY_RULE_REQUIRED: replace with confirmed legacy numbering rules,
    # including period resets, document subtype rules, and concurrency guarantees.
    prefix = _document_prefix(document_type)
    existing_numbers = db.scalars(
        select(Document.number).where(
            Document.document_type == document_type,
            Document.number.like(f"{prefix}-%"),
        )
    ).all()
    max_value = 0
    for number in existing_numbers:
        if not number:
            continue
        try:
            max_value = max(max_value, int(number.rsplit("-", 1)[1]))
        except (IndexError, ValueError):
            continue
    return f"{prefix}-{max_value + 1:06d}"


def _load_document(db: Session, document_id: int) -> Document:
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
    return document


def _get_balance(db: Session, product_id: int, warehouse_id: int) -> StockBalance:
    balance = db.scalar(
        select(StockBalance).where(
            StockBalance.product_id == product_id,
            StockBalance.warehouse_id == warehouse_id,
        )
    )
    if balance is None:
        balance = StockBalance(product_id=product_id, warehouse_id=warehouse_id, quantity=Decimal("0"))
        db.add(balance)
        db.flush()
    return balance


def _audit(db: Session, entity_type: str, entity_id: int, action: str, details: str | None = None) -> None:
    db.add(AuditLog(entity_type=entity_type, entity_id=str(entity_id), action=action, details=details))


def _recalculate_total(document: Document) -> None:
    document.total_amount = sum((line.line_total for line in document.lines), Decimal("0"))
    document.foreign_total_amount = sum((line.foreign_line_total or line.line_total for line in document.lines), Decimal("0"))


def recalculate_document_total(document: Document) -> None:
    _recalculate_total(document)


def _ensure_draft(document: Document) -> None:
    if document.status != Document.STATUS_DRAFT:
        raise HTTPException(status_code=409, detail="Only draft documents can be edited")


def _valid_document_types() -> set[str]:
    return {Document.TYPE_INCOMING, Document.TYPE_OUTGOING, Document.TYPE_ADJUSTMENT, Document.TYPE_TRANSFER}


def _validate_document_partner(db: Session, document_type: str, partner_id: int | None) -> None:
    if document_type == Document.TYPE_TRANSFER:
        if partner_id is not None:
            raise HTTPException(status_code=422, detail="Transfer document must not have partner")
        return
    if document_type == Document.TYPE_ADJUSTMENT:
        return
    if partner_id is None:
        if document_type == Document.TYPE_INCOMING:
            raise HTTPException(status_code=422, detail="Incoming document requires supplier partner")
        if document_type == Document.TYPE_OUTGOING:
            raise HTTPException(status_code=422, detail="Outgoing document requires customer partner")
    partner = db.get(Partner, partner_id)
    if partner is None:
        raise HTTPException(status_code=404, detail="Partner not found")
    if document_type == Document.TYPE_INCOMING and partner.partner_type not in {Partner.TYPE_SUPPLIER, Partner.TYPE_BOTH}:
        raise HTTPException(status_code=409, detail="Incoming document requires supplier partner")
    if document_type == Document.TYPE_OUTGOING and partner.partner_type not in {Partner.TYPE_CUSTOMER, Partner.TYPE_BOTH}:
        raise HTTPException(status_code=409, detail="Outgoing document requires customer partner")


def _normalize_document_currency(db: Session, document_type: str, currency_code: str | None, exchange_rate: Decimal | None) -> tuple[str, Decimal]:
    if document_type != Document.TYPE_INCOMING:
        return BASE_CURRENCY_CODE, Decimal("1")
    code = currency_code or BASE_CURRENCY_CODE
    currency = get_currency(db, code)
    rate = Decimal("1") if currency.is_base else _normalize_rate(exchange_rate)
    if currency.is_base and exchange_rate not in {None, Decimal("1")}:
        raise HTTPException(status_code=422, detail="Base currency rate must be 1")
    return currency.code, rate


def create_document(db: Session, payload: DocumentCreate) -> Document:
    if payload.document_type not in _valid_document_types():
        raise HTTPException(status_code=422, detail="Invalid document type")
    _validate_document_partner(db, payload.document_type, payload.partner_id)
    values = payload.model_dump(exclude={"status"})
    values["currency_code"], values["exchange_rate"] = _normalize_document_currency(db, payload.document_type, payload.currency_code, payload.exchange_rate)
    values["foreign_total_amount"] = Decimal("0")
    if not values.get("number"):
        values["number"] = _generate_document_number(db, payload.document_type)
    document = Document(**values, status=Document.STATUS_DRAFT)
    db.add(document)
    db.flush()
    _audit(db, "document", document.id, "create")
    db.commit()
    db.refresh(document)
    return document


def add_document_line(db: Session, document_id: int, payload: DocumentLineCreate) -> DocumentLine:
    document = _load_document(db, document_id)
    _ensure_draft(document)
    price = _base_price(document, payload.price, payload.foreign_price)
    foreign_price = payload.foreign_price if document.document_type == Document.TYPE_INCOMING else None
    line = DocumentLine(
        document=document,
        product_id=payload.product_id,
        quantity=payload.quantity,
        price=price,
        line_total=_line_total(payload.quantity, price),
        foreign_price=foreign_price,
        foreign_line_total=_line_total(payload.quantity, foreign_price) if foreign_price is not None else None,
    )
    db.add(line)
    db.flush()
    _recalculate_total(document)
    _audit(db, "document", document.id, "add_line", f"line_id={line.id}")
    db.commit()
    db.refresh(line)
    return line


def update_document_line(db: Session, document_id: int, line_id: int, payload: DocumentLineUpdate) -> DocumentLine:
    document = _load_document(db, document_id)
    _ensure_draft(document)
    line = db.get(DocumentLine, line_id)
    if line is None or line.document_id != document.id:
        raise HTTPException(status_code=404, detail="Document line not found")
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(line, key, value)
    if document.document_type == Document.TYPE_INCOMING:
        line.foreign_price = line.foreign_price if line.foreign_price is not None else line.price
        line.price = _base_price(document, line.price, line.foreign_price)
        line.foreign_line_total = _line_total(line.quantity, line.foreign_price)
    else:
        line.foreign_price = None
        line.foreign_line_total = None
        line.price = line.price.quantize(Decimal("0.01"))
    line.line_total = _line_total(line.quantity, line.price)
    _recalculate_total(document)
    _audit(db, "document", document.id, "update_line", f"line_id={line.id}")
    db.commit()
    db.refresh(line)
    return line


def update_document_header(db: Session, document_id: int, payload: DocumentUpdate) -> Document:
    document = _load_document(db, document_id)
    _ensure_draft(document)
    values = payload.model_dump(exclude_unset=True, exclude={"status", "total_amount"})
    if "document_type" in values and values["document_type"] not in _valid_document_types():
        raise HTTPException(status_code=422, detail="Invalid document type")
    next_type = values.get("document_type", document.document_type)
    next_partner_id = values.get("partner_id", document.partner_id)
    _validate_document_partner(db, next_type, next_partner_id)
    if "document_type" in values or "currency_code" in values or "exchange_rate" in values:
        values["currency_code"], values["exchange_rate"] = _normalize_document_currency(
            db,
            next_type,
            values.get("currency_code", document.currency_code),
            values.get("exchange_rate", document.exchange_rate),
        )
    for key, value in values.items():
        setattr(document, key, value)
    for line in document.lines:
        if document.document_type == Document.TYPE_INCOMING:
            line.foreign_price = line.foreign_price if line.foreign_price is not None else line.price
            line.price = _base_price(document, line.price, line.foreign_price)
            line.foreign_line_total = _line_total(line.quantity, line.foreign_price)
        else:
            line.foreign_price = None
            line.foreign_line_total = None
            line.price = line.price.quantize(Decimal("0.01"))
        line.line_total = _line_total(line.quantity, line.price)
    _recalculate_total(document)
    _audit(db, "document", document.id, "update_header", ",".join(sorted(values.keys())))
    db.commit()
    db.refresh(document)
    return document


def delete_document_line(db: Session, document_id: int, line_id: int) -> None:
    document = _load_document(db, document_id)
    _ensure_draft(document)
    line = db.get(DocumentLine, line_id)
    if line is None or line.document_id != document.id:
        raise HTTPException(status_code=404, detail="Document line not found")
    db.delete(line)
    db.flush()
    db.refresh(document)
    _recalculate_total(document)
    _audit(db, "document", document.id, "delete_line", f"line_id={line_id}")
    db.commit()


def delete_draft_document(db: Session, document_id: int) -> None:
    document = _load_document(db, document_id)
    if document.status != Document.STATUS_DRAFT:
        raise HTTPException(status_code=409, detail="Only draft documents can be deleted")
    _audit(db, "document", document.id, "delete_draft")
    db.delete(document)
    db.commit()


def _movement_delta(document: Document, line: DocumentLine, current_quantity: Decimal) -> Decimal:
    # TODO LEGACY_RULE_REQUIRED: confirm whether adjustment lines represent target stock,
    # absolute correction delta, inventory fact quantity, or a separate document type.
    if document.document_type == Document.TYPE_INCOMING:
        return line.quantity
    if document.document_type == Document.TYPE_OUTGOING:
        if current_quantity < line.quantity:
            raise DocumentRulesError("Not enough stock for outgoing document")
        return -line.quantity
    if document.document_type == Document.TYPE_ADJUSTMENT:
        return line.quantity - current_quantity
    if document.document_type == Document.TYPE_TRANSFER:
        if current_quantity < line.quantity:
            raise DocumentRulesError("Not enough stock for transfer document")
        return -line.quantity
    raise DocumentRulesError("Unsupported document type")


def _validate_document_warehouses(document: Document) -> None:
    if document.warehouse_id is None:
        raise HTTPException(status_code=422, detail="Document warehouse is required")
    if document.document_type == Document.TYPE_TRANSFER:
        if document.destination_warehouse_id is None:
            raise HTTPException(status_code=422, detail="Transfer document destination warehouse is required")
        if document.destination_warehouse_id == document.warehouse_id:
            raise HTTPException(status_code=422, detail="Transfer warehouses must be different")
    elif document.destination_warehouse_id is not None:
        raise HTTPException(status_code=422, detail="Destination warehouse is only valid for transfer documents")


def post_document(db: Session, document_id: int) -> Document:
    document = _load_document(db, document_id)
    if document.status != Document.STATUS_DRAFT:
        raise HTTPException(status_code=409, detail="Only draft documents can be posted")
    _validate_document_warehouses(document)
    if not document.lines:
        raise HTTPException(status_code=422, detail="Document has no lines")
    _validate_document_partner(db, document.document_type, document.partner_id)

    try:
        for line in document.lines:
            balance = _get_balance(db, line.product_id, document.warehouse_id)
            delta = _movement_delta(document, line, balance.quantity)
            balance.quantity += delta
            db.add(
                StockMovement(
                    product_id=line.product_id,
                    warehouse_id=document.warehouse_id,
                    document_id=document.id,
                    quantity_delta=delta,
                    reason=f"post:{document.document_type}",
                )
            )
            if document.document_type == Document.TYPE_TRANSFER:
                destination_balance = _get_balance(db, line.product_id, document.destination_warehouse_id)
                destination_balance.quantity += line.quantity
                db.add(
                    StockMovement(
                        product_id=line.product_id,
                        warehouse_id=document.destination_warehouse_id,
                        document_id=document.id,
                        quantity_delta=line.quantity,
                        reason=f"post:{document.document_type}",
                    )
                )
        document.status = Document.STATUS_POSTED
        _audit(db, "document", document.id, "post", "draft posting rules applied")
        db.commit()
    except DocumentRulesError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.refresh(document)
    return document


def cancel_document(db: Session, document_id: int) -> Document:
    document = _load_document(db, document_id)
    if document.status != Document.STATUS_POSTED:
        raise HTTPException(status_code=409, detail="Only posted documents can be cancelled")
    _validate_document_warehouses(document)

    movements = list(
        db.scalars(
            select(StockMovement).where(
                StockMovement.document_id == document.id,
                StockMovement.reason.like("post:%"),
            )
        )
    )
    try:
        for movement in movements:
            balance = _get_balance(db, movement.product_id, movement.warehouse_id)
            reverse_delta = -movement.quantity_delta
            if balance.quantity + reverse_delta < 0:
                # TODO LEGACY_RULE_REQUIRED: confirm cancellation behavior when later documents consumed stock.
                raise DocumentRulesError("Cancellation would make stock negative")
            balance.quantity += reverse_delta
            db.add(
                StockMovement(
                    product_id=movement.product_id,
                    warehouse_id=movement.warehouse_id,
                    document_id=document.id,
                    quantity_delta=reverse_delta,
                    reason=f"cancel:{document.document_type}",
                )
            )
        document.status = Document.STATUS_CANCELLED
        _audit(db, "document", document.id, "cancel")
        db.commit()
    except DocumentRulesError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.refresh(document)
    return document
