from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import base  # noqa: F401
from app.db.session import SessionLocal
from app.models.accounting import CashOperation, ExchangeRate, Payment
from app.models.documents import Document
from app.models.partners import Partner
from app.models.products import Product, ProductGroup
from app.models.stock import Warehouse
from app.schemas.cash import CashOperationCreate
from app.schemas.currencies import ExchangeRateCreate
from app.schemas.documents import DocumentCreate, DocumentLineCreate
from app.schemas.payments import PaymentCreate
from app.services.auth_seed import seed_auth_defaults
from app.services.cash_service import create_cash_operation
from app.services.currency_service import create_exchange_rate, get_currency, seed_default_currencies
from app.services.documents_service import add_document_line, create_document, post_document
from app.services.payments_service import create_payment, post_payment

PREFIX = "TEST"
START_DATE = date(2026, 6, 1)


def _commit_refresh(db: Session, item):
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _group(db: Session, index: int) -> ProductGroup:
    name = f"{PREFIX} Category {index:02d}"
    group = db.scalar(select(ProductGroup).where(ProductGroup.name == name))
    if group:
        return group
    return _commit_refresh(db, ProductGroup(name=name))


def _product(db: Session, index: int, group: ProductGroup) -> Product:
    sku = f"{PREFIX}-P{index:03d}"
    product = db.scalar(select(Product).where(Product.sku == sku))
    if product:
        product.name = f"{PREFIX} Product {index:02d}"
        product.group_id = group.id
        product.base_price = Decimal("100.00") + Decimal(index * 15)
        product.is_active = True
        db.commit()
        db.refresh(product)
        return product
    return _commit_refresh(
        db,
        Product(
            sku=sku,
            name=f"{PREFIX} Product {index:02d}",
            group_id=group.id,
            base_price=Decimal("100.00") + Decimal(index * 15),
            is_active=True,
        ),
    )


def _warehouse(db: Session, index: int) -> Warehouse:
    code = f"{PREFIX}-W{index:02d}"
    warehouse = db.scalar(select(Warehouse).where(Warehouse.code == code))
    if warehouse:
        return warehouse
    return _commit_refresh(db, Warehouse(code=code, name=f"{PREFIX} Warehouse {index:02d}", address=f"{PREFIX} address {index:02d}"))


def _partner(db: Session, index: int) -> Partner:
    code = f"{PREFIX}-C{index:02d}"
    partner_type = [Partner.TYPE_SUPPLIER, Partner.TYPE_CUSTOMER, Partner.TYPE_BOTH][(index - 1) % 3]
    partner = db.scalar(select(Partner).where(Partner.code == code))
    if partner:
        partner.name = f"{PREFIX} Partner {index:02d}"
        partner.partner_type = partner_type
        partner.is_active = True
        db.commit()
        db.refresh(partner)
        return partner
    return _commit_refresh(
        db,
        Partner(
            code=code,
            name=f"{PREFIX} Partner {index:02d}",
            partner_type=partner_type,
            phone=f"+373 000 10 {index:02d}",
            address=f"{PREFIX} partner address {index:02d}",
            is_active=True,
        ),
    )


def _rate_exists(db: Session, currency_code: str, rate_date: date) -> bool:
    currency = get_currency(db, currency_code)
    return db.scalar(select(ExchangeRate.id).where(ExchangeRate.currency_id == currency.id, ExchangeRate.rate_date == rate_date)) is not None


def _seed_rates(db: Session) -> None:
    rates = [
        ("USD", Decimal("16.10")),
        ("MDL", Decimal("0.90")),
        ("EUR", Decimal("17.40")),
        ("USD", Decimal("16.20")),
        ("MDL", Decimal("0.92")),
        ("EUR", Decimal("17.50")),
        ("USD", Decimal("16.35")),
        ("MDL", Decimal("0.93")),
        ("EUR", Decimal("17.65")),
        ("USD", Decimal("16.50")),
    ]
    for offset, (currency_code, value) in enumerate(rates):
        rate_date = START_DATE + timedelta(days=offset)
        if _rate_exists(db, currency_code, rate_date):
            continue
        create_exchange_rate(
            db,
            ExchangeRateCreate(
                currency_code=currency_code,
                rate_date=rate_date,
                rate_to_base=value,
                note=f"{PREFIX}:rate:{offset + 1:02d}",
            ),
        )


def _document_exists(db: Session, note: str) -> bool:
    return db.scalar(select(Document.id).where(Document.note == note)) is not None


def _payment_exists(db: Session, note: str) -> bool:
    return db.scalar(select(Payment.id).where(Payment.note == note)) is not None


def _cash_exists(db: Session, note: str) -> bool:
    return db.scalar(select(CashOperation.id).where(CashOperation.note == note)) is not None


def _supplier_for(partners: list[Partner], index: int) -> Partner:
    suppliers = [partner for partner in partners if partner.partner_type in {Partner.TYPE_SUPPLIER, Partner.TYPE_BOTH}]
    return suppliers[(index - 1) % len(suppliers)]


def _customer_for(partners: list[Partner], index: int) -> Partner:
    customers = [partner for partner in partners if partner.partner_type in {Partner.TYPE_CUSTOMER, Partner.TYPE_BOTH}]
    return customers[(index - 1) % len(customers)]


def _seed_documents(db: Session, products: list[Product], warehouses: list[Warehouse], partners: list[Partner]) -> None:
    currency_cycle = ["RUB_PMR", "USD", "MDL", "EUR", "USD"]
    rate_cycle = [Decimal("1"), Decimal("16.20"), Decimal("0.92"), Decimal("17.50"), Decimal("16.35")]
    for index in range(1, 11):
        note = f"{PREFIX}:document:{index:02d}"
        if _document_exists(db, note):
            continue
        is_incoming = index <= 5
        stock_source_index = index if is_incoming else index - 5
        document = create_document(
            db,
            DocumentCreate(
                document_type=Document.TYPE_INCOMING if is_incoming else Document.TYPE_OUTGOING,
                document_date=START_DATE + timedelta(days=index),
                partner_id=(_supplier_for(partners, index).id if is_incoming else _customer_for(partners, index).id),
                warehouse_id=warehouses[(stock_source_index - 1) % len(warehouses)].id,
                currency_code=currency_cycle[(index - 1) % len(currency_cycle)] if is_incoming else "RUB_PMR",
                exchange_rate=rate_cycle[(index - 1) % len(rate_cycle)] if is_incoming else Decimal("1"),
                note=note,
            ),
        )
        for line_offset in range(2):
            product = products[(stock_source_index + line_offset - 1) % len(products)]
            quantity = Decimal("12") if is_incoming else Decimal("2")
            if is_incoming:
                add_document_line(
                    db,
                    document.id,
                    DocumentLineCreate(product_id=product.id, quantity=quantity, foreign_price=Decimal("5.00") + Decimal(index + line_offset)),
                )
            else:
                add_document_line(
                    db,
                    document.id,
                    DocumentLineCreate(product_id=product.id, quantity=quantity, price=Decimal(product.base_price or Decimal("100.00"))),
                )
        post_document(db, document.id)


def _seed_payments(db: Session, partners: list[Partner]) -> None:
    for index in range(1, 11):
        note = f"{PREFIX}:payment:{index:02d}"
        if _payment_exists(db, note):
            continue
        is_customer = index % 2 == 0
        partner = _customer_for(partners, index) if is_customer else _supplier_for(partners, index)
        payment = create_payment(
            db,
            PaymentCreate(
                partner_id=partner.id,
                payment_date=START_DATE + timedelta(days=20 + index),
                payment_type=Payment.TYPE_CUSTOMER_PAYMENT if is_customer else Payment.TYPE_SUPPLIER_PAYMENT,
                amount=Decimal("50.00") + Decimal(index * 10),
                method="cash",
                note=note,
            ),
        )
        post_payment(db, payment.id)


def _seed_cash_operations(db: Session, partners: list[Partner]) -> None:
    for index in range(1, 11):
        note = f"{PREFIX}:cash:{index:02d}"
        if _cash_exists(db, note):
            continue
        create_cash_operation(
            db,
            CashOperationCreate(
                operation_date=START_DATE + timedelta(days=40 + index),
                operation_type=[CashOperation.TYPE_CASH_IN, CashOperation.TYPE_CASH_OUT, CashOperation.TYPE_CORRECTION][(index - 1) % 3],
                amount=Decimal("20.00") + Decimal(index * 5),
                partner_id=partners[(index - 1) % len(partners)].id,
                note=note,
            ),
        )


def seed() -> None:
    db = SessionLocal()
    try:
        seed_auth_defaults(db)
        seed_default_currencies(db)
        db.commit()

        groups = [_group(db, index) for index in range(1, 11)]
        products = [_product(db, index, groups[index - 1]) for index in range(1, 11)]
        warehouses = [_warehouse(db, index) for index in range(1, 11)]
        partners = [_partner(db, index) for index in range(1, 11)]
        _seed_rates(db)
        _seed_documents(db, products, warehouses, partners)
        _seed_payments(db, partners)
        _seed_cash_operations(db, partners)

        print("Test data seed complete")
        print("Created/updated 10 product categories")
        print("Created/updated 10 products")
        print("Created/updated 10 warehouses")
        print("Created/updated 10 partners")
        print("Created/updated 10 exchange rates")
        print("Created up to 10 posted documents")
        print("Created up to 10 posted payments")
        print("Created up to 10 manual cash operations")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
