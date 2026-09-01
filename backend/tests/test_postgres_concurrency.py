from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
import os
from threading import Barrier

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import *  # noqa: F401,F403
from app.db.session import Base
from app.models.documents import Document
from app.models.partners import Partner
from app.models.products import Product
from app.models.stock import StockBalance, Warehouse
from app.schemas.documents import DocumentCreate, DocumentLineCreate
from app.services.currency_service import seed_default_currencies
from app.services.documents_service import add_document_line, create_document, post_document


POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not POSTGRES_URL, reason="TEST_POSTGRES_URL is not configured")


@pytest.fixture()
def postgres_session_factory():
    assert POSTGRES_URL is not None
    engine = create_engine(POSTGRES_URL, pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    with factory() as db:
        seed_default_currencies(db)
        db.commit()
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_concurrent_document_numbers_are_unique(postgres_session_factory) -> None:
    with postgres_session_factory() as db:
        warehouse = Warehouse(name="Concurrent warehouse", code="CON-NUM")
        supplier = Partner(name="Concurrent supplier", code="CON-SUP", partner_type=Partner.TYPE_SUPPLIER)
        db.add_all([warehouse, supplier])
        db.commit()
        warehouse_id = warehouse.id
        supplier_id = supplier.id

    barrier = Barrier(12)

    def create_number(_index: int) -> str:
        with postgres_session_factory() as db:
            barrier.wait()
            document = create_document(
                db,
                DocumentCreate(
                    document_type=Document.TYPE_INCOMING,
                    document_date=date(2026, 9, 1),
                    warehouse_id=warehouse_id,
                    partner_id=supplier_id,
                ),
            )
            assert document.number is not None
            return document.number

    with ThreadPoolExecutor(max_workers=12) as executor:
        numbers = list(executor.map(create_number, range(12)))

    assert len(set(numbers)) == 12
    assert sorted(numbers) == [f"IN-{index:06d}" for index in range(1, 13)]


def test_concurrent_sales_cannot_consume_same_stock_twice(postgres_session_factory) -> None:
    with postgres_session_factory() as db:
        product = Product(name="Concurrent product", sku="CON-STOCK")
        warehouse = Warehouse(name="Concurrent stock", code="CON-STOCK")
        supplier = Partner(name="Stock supplier", code="STOCK-SUP", partner_type=Partner.TYPE_SUPPLIER)
        customer = Partner(name="Stock customer", code="STOCK-CUS", partner_type=Partner.TYPE_CUSTOMER)
        db.add_all([product, warehouse, supplier, customer])
        db.commit()

        incoming = create_document(
            db,
            DocumentCreate(
                document_type=Document.TYPE_INCOMING,
                document_date=date(2026, 9, 1),
                warehouse_id=warehouse.id,
                partner_id=supplier.id,
            ),
        )
        add_document_line(
            db,
            incoming.id,
            DocumentLineCreate(product_id=product.id, quantity=Decimal("5"), price=Decimal("1")),
        )
        post_document(db, incoming.id)

        outgoing_ids = []
        for _index in range(2):
            outgoing = create_document(
                db,
                DocumentCreate(
                    document_type=Document.TYPE_OUTGOING,
                    document_date=date(2026, 9, 1),
                    warehouse_id=warehouse.id,
                    partner_id=customer.id,
                ),
            )
            add_document_line(
                db,
                outgoing.id,
                DocumentLineCreate(product_id=product.id, quantity=Decimal("4"), price=Decimal("2")),
            )
            outgoing_ids.append(outgoing.id)
        product_id = product.id
        warehouse_id = warehouse.id

    barrier = Barrier(2)

    def try_post(document_id: int) -> int:
        with postgres_session_factory() as db:
            barrier.wait()
            try:
                post_document(db, document_id)
                return 200
            except HTTPException as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(try_post, outgoing_ids))

    assert sorted(statuses) == [200, 409]
    with postgres_session_factory() as db:
        balance = db.scalar(
            select(StockBalance).where(
                StockBalance.product_id == product_id,
                StockBalance.warehouse_id == warehouse_id,
            )
        )
        documents = list(db.scalars(select(Document).where(Document.id.in_(outgoing_ids))))
        assert balance is not None
        assert balance.quantity == Decimal("1.000")
        assert sorted(document.status for document in documents) == [Document.STATUS_DRAFT, Document.STATUS_POSTED]
