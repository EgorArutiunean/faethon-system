from datetime import date
from decimal import Decimal
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import base  # noqa: F401
from app.db.session import Base, SessionLocal, engine
from app.models.accounting import CashOperation, Payment
from app.models.documents import Document
from app.models.partners import Partner
from app.models.products import Product
from app.models.stock import Warehouse
from app.schemas.documents import DocumentCreate, DocumentLineCreate
from app.schemas.cash import CashOperationCreate
from app.schemas.payments import PaymentCreate
from app.services.cash_service import create_cash_operation, get_cash_balance
from app.services.auth_seed import seed_auth_defaults
from app.services.documents_service import add_document_line, create_document, post_document
from app.services.payments_service import create_payment, get_partner_statement, post_payment


def _get_or_create_product(db: Session, sku: str, name: str, price: str) -> Product:
    product = db.scalar(select(Product).where(Product.sku == sku))
    if product:
        return product
    product = Product(sku=sku, name=name, base_price=Decimal(price), is_active=True)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def _get_or_create_warehouse(db: Session, code: str, name: str) -> Warehouse:
    warehouse = db.scalar(select(Warehouse).where(Warehouse.code == code))
    if warehouse:
        return warehouse
    warehouse = Warehouse(code=code, name=name, address=f"Demo address {code}")
    db.add(warehouse)
    db.commit()
    db.refresh(warehouse)
    return warehouse


def _get_or_create_partner(db: Session, code: str, name: str, partner_type: str) -> Partner:
    partner = db.scalar(select(Partner).where(Partner.code == code))
    if partner:
        partner.partner_type = partner_type
        db.commit()
        db.refresh(partner)
        return partner
    partner = Partner(code=code, name=name, partner_type=partner_type, phone="+000 demo", is_active=True)
    db.add(partner)
    db.commit()
    db.refresh(partner)
    return partner


def _document_exists(db: Session, note: str) -> bool:
    return db.scalar(select(Document.id).where(Document.note == note)) is not None


def _payment_exists(db: Session, note: str) -> bool:
    return db.scalar(select(Payment.id).where(Payment.note == note)) is not None


def seed() -> None:
    # Helpful for local SQLite demo databases. PostgreSQL environments should still run Alembic first.
    Base.metadata.create_all(engine)

    db = SessionLocal()
    try:
        seed_auth_defaults(db)
        bolt = _get_or_create_product(db, "DEMO-BOLT", "Demo Bolt M8", "10.00")
        cable = _get_or_create_product(db, "DEMO-CABLE", "Demo Cable 2m", "15.50")
        lamp = _get_or_create_product(db, "DEMO-LAMP", "Demo Lamp", "22.00")

        main = _get_or_create_warehouse(db, "DEMO-MAIN", "Demo Main Warehouse")
        retail = _get_or_create_warehouse(db, "DEMO-RETAIL", "Demo Retail Warehouse")

        supplier = _get_or_create_partner(db, "DEMO-SUP", "Demo Supplier", Partner.TYPE_SUPPLIER)
        customer = _get_or_create_partner(db, "DEMO-CUST", "Demo Customer", Partner.TYPE_CUSTOMER)
        cash_customer = _get_or_create_partner(db, "DEMO-CASH", "Demo Cash Customer", Partner.TYPE_CUSTOMER)
        _get_or_create_partner(db, "DEMO-BOTH", "Demo Universal Partner", Partner.TYPE_BOTH)

        if not _document_exists(db, "demo-seed:incoming"):
            incoming = create_document(
                db,
                DocumentCreate(
                    document_type=Document.TYPE_INCOMING,
                    document_date=date(2026, 5, 2),
                    partner_id=supplier.id,
                    warehouse_id=main.id,
                    note="demo-seed:incoming",
                ),
            )
            add_document_line(db, incoming.id, DocumentLineCreate(product_id=bolt.id, quantity=Decimal("20"), price=Decimal("8.00")))
            add_document_line(db, incoming.id, DocumentLineCreate(product_id=cable.id, quantity=Decimal("12"), price=Decimal("12.00")))
            add_document_line(db, incoming.id, DocumentLineCreate(product_id=lamp.id, quantity=Decimal("6"), price=Decimal("18.00")))
            post_document(db, incoming.id)

        if not _document_exists(db, "demo-seed:outgoing"):
            outgoing = create_document(
                db,
                DocumentCreate(
                    document_type=Document.TYPE_OUTGOING,
                    document_date=date(2026, 5, 3),
                    partner_id=customer.id,
                    warehouse_id=main.id,
                    note="demo-seed:outgoing",
                ),
            )
            add_document_line(db, outgoing.id, DocumentLineCreate(product_id=bolt.id, quantity=Decimal("5"), price=Decimal("10.00")))
            add_document_line(db, outgoing.id, DocumentLineCreate(product_id=cable.id, quantity=Decimal("2"), price=Decimal("15.50")))
            post_document(db, outgoing.id)

        if not _document_exists(db, "demo-seed:retail-outgoing"):
            retail_doc = create_document(
                db,
                DocumentCreate(
                    document_type=Document.TYPE_INCOMING,
                    document_date=date(2026, 5, 3),
                    partner_id=supplier.id,
                    warehouse_id=retail.id,
                    note="demo-seed:retail-outgoing",
                ),
            )
            add_document_line(db, retail_doc.id, DocumentLineCreate(product_id=lamp.id, quantity=Decimal("3"), price=Decimal("18.00")))
            post_document(db, retail_doc.id)

        if not _payment_exists(db, "demo-seed:customer-payment"):
            payment = create_payment(
                db,
                PaymentCreate(
                    partner_id=customer.id,
                    payment_date=date(2026, 5, 4),
                    payment_type=Payment.TYPE_CUSTOMER_PAYMENT,
                    amount=Decimal("40.00"),
                    method="cash",
                    note="demo-seed:customer-payment",
                ),
            )
            post_payment(db, payment.id)

        if not db.scalar(select(Payment.id).where(Payment.note == "demo-seed:supplier-payment")):
            supplier_payment = create_payment(
                db,
                PaymentCreate(
                    partner_id=supplier.id,
                    payment_date=date(2026, 5, 4),
                    payment_type=Payment.TYPE_SUPPLIER_PAYMENT,
                    amount=Decimal("25.00"),
                    method="cash",
                    note="demo-seed:supplier-payment",
                ),
            )
            post_payment(db, supplier_payment.id)

        if not db.scalar(select(Payment.id).where(Payment.note == "demo-seed:cash-customer-payment")):
            cash_customer_payment = create_payment(
                db,
                PaymentCreate(
                    partner_id=cash_customer.id,
                    payment_date=date(2026, 5, 5),
                    payment_type=Payment.TYPE_CUSTOMER_PAYMENT,
                    amount=Decimal("15.00"),
                    method="cash",
                    note="demo-seed:cash-customer-payment",
                ),
            )
            post_payment(db, cash_customer_payment.id)

        if not db.scalar(select(CashOperation.id).where(CashOperation.note == "demo-seed:manual-correction")):
            create_cash_operation(
                db,
                CashOperationCreate(
                    operation_date=date(2026, 5, 5),
                    operation_type="correction",
                    amount=Decimal("5.00"),
                    note="demo-seed:manual-correction",
                ),
            )

        # Touch statements so seed output confirms that document/payment entries are available.
        customer_statement = get_partner_statement(db, customer.id)
        supplier_statement = get_partner_statement(db, supplier.id)
        print("Demo seed complete")
        print("Demo admin: admin@example.com / admin123")
        print("Demo manager: manager@example.com / manager123")
        print("Demo cashier: cashier@example.com / cashier123")
        print("Demo viewer: viewer@example.com / viewer123")
        print(f"Products: {bolt.sku}, {cable.sku}, {lamp.sku}")
        print(f"Warehouses: {main.code}, {retail.code}")
        print(f"Partners: {supplier.code}, {customer.code}, {cash_customer.code}")
        print(f"Customer statement entries: {len(customer_statement)}")
        print(f"Supplier statement entries: {len(supplier_statement)}")
        print(f"Cash balance: {get_cash_balance(db).balance}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
