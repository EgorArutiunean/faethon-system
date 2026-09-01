import hashlib
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.documents import Document, DocumentLine, DocumentNumberSequence
from app.models.partners import Partner
from app.models.products import Product
from app.models.stock import StockBalance, StockMovement
from app.models.stock import Warehouse
from app.schemas.documents import DocumentCreate, DocumentLineCreate, DocumentLineUpdate, DocumentUpdate
from app.services.audit_writer import change_details, write_audit
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
    prefix = _document_prefix(document_type)
    initial_value = 1
    if db.get(DocumentNumberSequence, document_type) is None:
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
        initial_value = max_value + 1
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        statement = (
            postgresql_insert(DocumentNumberSequence)
            .values(document_type=document_type, last_value=initial_value)
            .on_conflict_do_update(
                index_elements=[DocumentNumberSequence.document_type],
                set_={"last_value": DocumentNumberSequence.last_value + 1},
            )
            .returning(DocumentNumberSequence.last_value)
        )
        next_value = db.scalar(statement)
    elif dialect == "sqlite":
        statement = (
            sqlite_insert(DocumentNumberSequence)
            .values(document_type=document_type, last_value=initial_value)
            .on_conflict_do_update(
                index_elements=[DocumentNumberSequence.document_type],
                set_={"last_value": DocumentNumberSequence.last_value + 1},
            )
            .returning(DocumentNumberSequence.last_value)
        )
        next_value = db.scalar(statement)
    else:
        sequence = db.get(DocumentNumberSequence, document_type, with_for_update=True)
        if sequence is None:
            sequence = DocumentNumberSequence(document_type=document_type, last_value=initial_value)
            db.add(sequence)
        else:
            sequence.last_value += 1
        db.flush()
        next_value = sequence.last_value
    return f"{prefix}-{next_value:06d}"


def _reserve_document_number(db: Session, document_type: str, number: str) -> None:
    prefix = _document_prefix(document_type)
    if not number.startswith(f"{prefix}-"):
        return
    suffix = number.rsplit("-", 1)[1]
    if not suffix.isdigit():
        return
    value = int(suffix)
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        statement = postgresql_insert(DocumentNumberSequence).values(
            document_type=document_type,
            last_value=value,
        ).on_conflict_do_update(
            index_elements=[DocumentNumberSequence.document_type],
            set_={"last_value": func.greatest(DocumentNumberSequence.last_value, value)},
        )
        db.execute(statement)
    elif dialect == "sqlite":
        statement = sqlite_insert(DocumentNumberSequence).values(
            document_type=document_type,
            last_value=value,
        ).on_conflict_do_update(
            index_elements=[DocumentNumberSequence.document_type],
            set_={"last_value": func.max(DocumentNumberSequence.last_value, value)},
        )
        db.execute(statement)
    else:
        sequence = db.get(DocumentNumberSequence, document_type, with_for_update=True)
        if sequence is None:
            db.add(DocumentNumberSequence(document_type=document_type, last_value=value))
        elif sequence.last_value < value:
            sequence.last_value = value


def _normalize_document_number(db: Session, document_type: str, number: str | None) -> str:
    normalized = (number or "").strip()
    if not normalized:
        return _generate_document_number(db, document_type)
    _reserve_document_number(db, document_type, normalized)
    return normalized


def _load_document(db: Session, document_id: int, *, for_update: bool = False) -> Document:
    statement = (
        select(Document)
        .where(Document.id == document_id)
        .options(
            selectinload(Document.partner),
            selectinload(Document.warehouse),
            selectinload(Document.destination_warehouse),
            selectinload(Document.lines).selectinload(DocumentLine.product),
        )
    )
    if for_update:
        statement = statement.with_for_update()
    document = db.scalar(statement)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


def _get_balance(db: Session, product_id: int, warehouse_id: int) -> StockBalance:
    balance = db.scalar(
        select(StockBalance).where(
            StockBalance.product_id == product_id,
            StockBalance.warehouse_id == warehouse_id,
        ).with_for_update()
    )
    if balance is None:
        balance = StockBalance(product_id=product_id, warehouse_id=warehouse_id, quantity=Decimal("0"))
        db.add(balance)
        db.flush()
    return balance


def _stock_lock_key(product_id: int, warehouse_id: int) -> int:
    digest = hashlib.blake2b(f"stock:{product_id}:{warehouse_id}".encode("ascii"), digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big", signed=True)


def _lock_stock_keys(db: Session, keys: set[tuple[int, int]]) -> None:
    if db.get_bind().dialect.name != "postgresql":
        return
    for product_id, warehouse_id in sorted(keys):
        db.execute(select(func.pg_advisory_xact_lock(_stock_lock_key(product_id, warehouse_id))))


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


def _validate_document_warehouse_references(
    db: Session,
    document_type: str,
    warehouse_id: int | None,
    destination_warehouse_id: int | None,
) -> None:
    if warehouse_id is not None and db.get(Warehouse, warehouse_id) is None:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    if destination_warehouse_id is not None and db.get(Warehouse, destination_warehouse_id) is None:
        raise HTTPException(status_code=404, detail="Destination warehouse not found")
    if document_type != Document.TYPE_TRANSFER and destination_warehouse_id is not None:
        raise HTTPException(status_code=422, detail="Destination warehouse is only valid for transfer documents")
    if warehouse_id is not None and destination_warehouse_id == warehouse_id:
        raise HTTPException(status_code=422, detail="Transfer warehouses must be different")


def _validate_document_line(db: Session, document_type: str, product_id: int, quantity: Decimal) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    if not product.is_active:
        raise HTTPException(status_code=409, detail="Inactive product cannot be used in a document")
    if document_type != Document.TYPE_ADJUSTMENT and quantity <= 0:
        raise HTTPException(status_code=422, detail="Document line quantity must be greater than zero")
    if quantity < 0:
        raise HTTPException(status_code=422, detail="Document line quantity cannot be negative")
    return product


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
    _validate_document_warehouse_references(
        db,
        payload.document_type,
        payload.warehouse_id,
        payload.destination_warehouse_id,
    )
    values = payload.model_dump(exclude={"status", "total_amount", "foreign_total_amount"})
    values["currency_code"], values["exchange_rate"] = _normalize_document_currency(db, payload.document_type, payload.currency_code, payload.exchange_rate)
    values["total_amount"] = Decimal("0")
    values["foreign_total_amount"] = Decimal("0")
    values["number"] = _normalize_document_number(db, payload.document_type, payload.number)
    document = Document(**values, status=Document.STATUS_DRAFT)
    db.add(document)
    try:
        db.flush()
        write_audit(db, "document", document.id, "create")
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Document number already exists") from exc
    db.refresh(document)
    return document


def add_document_line(db: Session, document_id: int, payload: DocumentLineCreate) -> DocumentLine:
    document = _load_document(db, document_id)
    _ensure_draft(document)
    _validate_document_line(db, document.document_type, payload.product_id, payload.quantity)
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
    write_audit(db, "document", document.id, "add_line", f"line_id={line.id}")
    db.commit()
    db.refresh(line)
    return line


def update_document_line(db: Session, document_id: int, line_id: int, payload: DocumentLineUpdate) -> DocumentLine:
    document = _load_document(db, document_id)
    _ensure_draft(document)
    line = db.get(DocumentLine, line_id)
    if line is None or line.document_id != document.id:
        raise HTTPException(status_code=404, detail="Document line not found")
    tracked_fields = ("product_id", "quantity", "price", "foreign_price")
    old_values = {field: getattr(line, field) for field in tracked_fields}
    values = payload.model_dump(exclude_unset=True)
    next_product_id = values.get("product_id", line.product_id)
    next_quantity = values.get("quantity", line.quantity)
    _validate_document_line(db, document.document_type, next_product_id, next_quantity)
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
    new_values = {field: getattr(line, field) for field in tracked_fields}
    write_audit(
        db,
        "document",
        document.id,
        "update_line",
        f"line_id={line.id};changes={change_details(old_values, new_values)}",
    )
    db.commit()
    db.refresh(line)
    return line


def update_document_header(db: Session, document_id: int, payload: DocumentUpdate) -> Document:
    document = _load_document(db, document_id)
    _ensure_draft(document)
    values = payload.model_dump(exclude_unset=True, exclude={"status", "total_amount", "foreign_total_amount"})
    if "document_type" in values and values["document_type"] not in _valid_document_types():
        raise HTTPException(status_code=422, detail="Invalid document type")
    next_type = values.get("document_type", document.document_type)
    next_partner_id = values.get("partner_id", document.partner_id)
    _validate_document_partner(db, next_type, next_partner_id)
    next_warehouse_id = values.get("warehouse_id", document.warehouse_id)
    next_destination_id = values.get("destination_warehouse_id", document.destination_warehouse_id)
    _validate_document_warehouse_references(db, next_type, next_warehouse_id, next_destination_id)
    if "number" in values:
        values["number"] = _normalize_document_number(db, next_type, values["number"])
    elif next_type != document.document_type:
        values["number"] = _generate_document_number(db, next_type)
    if "document_type" in values or "currency_code" in values or "exchange_rate" in values:
        values["currency_code"], values["exchange_rate"] = _normalize_document_currency(
            db,
            next_type,
            values.get("currency_code", document.currency_code),
            values.get("exchange_rate", document.exchange_rate),
        )
    old_values = {key: getattr(document, key) for key in values}
    for key, value in values.items():
        setattr(document, key, value)
    for line in document.lines:
        _validate_document_line(db, document.document_type, line.product_id, line.quantity)
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
    new_values = {key: getattr(document, key) for key in values}
    write_audit(db, "document", document.id, "update_header", change_details(old_values, new_values))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Document number already exists") from exc
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
    write_audit(db, "document", document.id, "delete_line", f"line_id={line_id}")
    db.commit()


def delete_draft_document(db: Session, document_id: int) -> None:
    document = _load_document(db, document_id)
    if document.status != Document.STATUS_DRAFT:
        raise HTTPException(status_code=409, detail="Only draft documents can be deleted")
    write_audit(db, "document", document.id, "delete_draft")
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


def _validate_document_warehouses(db: Session, document: Document) -> None:
    if document.warehouse_id is None:
        raise HTTPException(status_code=422, detail="Document warehouse is required")
    _validate_document_warehouse_references(
        db,
        document.document_type,
        document.warehouse_id,
        document.destination_warehouse_id,
    )
    if document.document_type == Document.TYPE_TRANSFER:
        if document.destination_warehouse_id is None:
            raise HTTPException(status_code=422, detail="Transfer document destination warehouse is required")
        if document.destination_warehouse_id == document.warehouse_id:
            raise HTTPException(status_code=422, detail="Transfer warehouses must be different")
    elif document.destination_warehouse_id is not None:
        raise HTTPException(status_code=422, detail="Destination warehouse is only valid for transfer documents")


def post_document(db: Session, document_id: int) -> Document:
    document = _load_document(db, document_id, for_update=True)
    if document.status != Document.STATUS_DRAFT:
        raise HTTPException(status_code=409, detail="Only draft documents can be posted")
    _validate_document_warehouses(db, document)
    if not document.lines:
        raise HTTPException(status_code=422, detail="Document has no lines")
    _validate_document_partner(db, document.document_type, document.partner_id)
    for line in document.lines:
        _validate_document_line(db, document.document_type, line.product_id, line.quantity)

    stock_keys = {(line.product_id, document.warehouse_id) for line in document.lines}
    if document.document_type == Document.TYPE_TRANSFER:
        stock_keys.update((line.product_id, document.destination_warehouse_id) for line in document.lines)
    _lock_stock_keys(db, stock_keys)

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
        write_audit(
            db,
            "document",
            document.id,
            "post",
            change_details({"status": Document.STATUS_DRAFT}, {"status": Document.STATUS_POSTED}),
        )
        db.commit()
    except (DocumentRulesError, IntegrityError) as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.refresh(document)
    return document


def cancel_document(db: Session, document_id: int) -> Document:
    document = _load_document(db, document_id, for_update=True)
    if document.status != Document.STATUS_POSTED:
        raise HTTPException(status_code=409, detail="Only posted documents can be cancelled")
    _validate_document_warehouses(db, document)

    movements = list(
        db.scalars(
            select(StockMovement).where(
                StockMovement.document_id == document.id,
                StockMovement.reason.like("post:%"),
            )
        )
    )
    _lock_stock_keys(db, {(movement.product_id, movement.warehouse_id) for movement in movements})
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
        write_audit(
            db,
            "document",
            document.id,
            "cancel",
            change_details({"status": Document.STATUS_POSTED}, {"status": Document.STATUS_CANCELLED}),
        )
        db.commit()
    except (DocumentRulesError, IntegrityError) as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.refresh(document)
    return document
