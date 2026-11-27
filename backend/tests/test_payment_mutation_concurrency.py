import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Event
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.base import *  # noqa: F401,F403
from app.db.session import Base
from app.models.accounting import CashOperation, Payment
from app.models.partners import Partner
from app.schemas.payments import PaymentCreate, PaymentUpdate
from app.services import payments_service

POSTGRES_URL = os.getenv("PAYMENTS_CONCURRENCY_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_URL, reason="PAYMENTS_CONCURRENCY_DATABASE_URL is not configured"
)


@pytest.fixture()
def isolated_payment_sessions():
    """Create and remove only a unique test schema; never modify public tables."""
    assert POSTGRES_URL is not None
    schema = f"payment_race_{uuid4().hex}"
    administration = create_engine(POSTGRES_URL, pool_pre_ping=True)
    with administration.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = create_engine(
        POSTGRES_URL,
        connect_args={"options": f"-csearch_path={schema},public -clock_timeout=5000"},
        pool_pre_ping=True,
    ).execution_options(schema_translate_map={None: schema})
    try:
        Base.metadata.create_all(engine)
        expected_tables = {table.name for table in Base.metadata.sorted_tables}
        assert expected_tables <= set(inspect(engine).get_table_names(schema=schema)), (
            "All fixture tables must exist in the isolated schema before any rows are written"
        )
        assert engine.get_execution_options()["schema_translate_map"][None] == schema
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as db:
            partner = Partner(name="Concurrent payment customer", partner_type="customer")
            db.add(partner)
            db.commit()
            payment = payments_service.create_payment(
                db,
                PaymentCreate(
                    partner_id=partner.id,
                    payment_date=date(2026, 10, 23),
                    payment_type="customer_payment",
                    amount=Decimal("100"),
                    method="cash",
                ),
            )
            payment_id = payment.id
        yield factory, payment_id
    finally:
        engine.dispose()
        with administration.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        administration.dispose()


def run_operation(factory, payment_id, operation):
    with factory() as db:
        db.info["race_operation"] = operation
        try:
            if operation == "post":
                payments_service.post_payment(db, payment_id)
            elif operation == "update":
                payments_service.update_payment(
                    db, payment_id, PaymentUpdate(amount=Decimal("200"))
                )
            else:
                payments_service.delete_draft_payment(db, payment_id)
            return 200
        except HTTPException as exc:
            db.rollback()
            return exc.status_code


def assert_matching_cash(factory, payment_id, expected_amount):
    with factory() as db:
        payment = db.get(Payment, payment_id)
        cash = db.scalar(select(CashOperation).where(CashOperation.payment_id == payment_id))
        assert payment.status == Payment.STATUS_POSTED
        assert payment.amount == Decimal(expected_amount)
        assert cash.status == CashOperation.STATUS_POSTED
        assert cash.amount == payment.amount


@pytest.mark.parametrize("mutation", ["update", "delete"])
def test_posting_first_blocks_draft_mutation_until_it_is_rejected(
    isolated_payment_sessions, monkeypatch, mutation
):
    factory, payment_id = isolated_payment_sessions
    posting_loaded = Event()
    release_posting = Event()
    mutation_attempted = Event()
    mutation_loaded = Event()
    original_load = payments_service._load_payment

    def observe_load(db, item_id, *, for_update=False):
        operation = db.info.get("race_operation")
        if operation == mutation:
            mutation_attempted.set()
        payment = original_load(db, item_id, for_update=for_update)
        if operation == "post":
            posting_loaded.set()
            assert release_posting.wait(10), "Timed out waiting to release posting"
        elif operation == mutation:
            mutation_loaded.set()
        return payment

    monkeypatch.setattr(payments_service, "_load_payment", observe_load)
    with ThreadPoolExecutor(max_workers=2) as executor:
        posting = executor.submit(run_operation, factory, payment_id, "post")
        assert posting_loaded.wait(5)
        changing = executor.submit(run_operation, factory, payment_id, mutation)
        try:
            assert mutation_attempted.wait(5)
            assert not mutation_loaded.wait(0.3), "Draft mutation read an unlocked stale payment"
        finally:
            release_posting.set()
        assert posting.result(timeout=10) == 200
        assert changing.result(timeout=10) == 409
    assert_matching_cash(factory, payment_id, "100")


def test_updating_first_holds_payment_until_posting_uses_the_new_amount(
    isolated_payment_sessions, monkeypatch
):
    factory, payment_id = isolated_payment_sessions
    update_loaded = Event()
    release_update = Event()
    posting_attempted = Event()
    posting_loaded = Event()
    original_load = payments_service._load_payment

    def observe_load(db, item_id, *, for_update=False):
        operation = db.info.get("race_operation")
        if operation == "post":
            posting_attempted.set()
        payment = original_load(db, item_id, for_update=for_update)
        if operation == "update":
            update_loaded.set()
            assert release_update.wait(10), "Timed out waiting to release update"
        elif operation == "post":
            posting_loaded.set()
        return payment

    monkeypatch.setattr(payments_service, "_load_payment", observe_load)
    with ThreadPoolExecutor(max_workers=2) as executor:
        updating = executor.submit(run_operation, factory, payment_id, "update")
        assert update_loaded.wait(5)
        posting = executor.submit(run_operation, factory, payment_id, "post")
        try:
            assert posting_attempted.wait(5)
            assert not posting_loaded.wait(0.3), "Posting read an unlocked stale amount"
        finally:
            release_update.set()
        assert updating.result(timeout=10) == 200
        assert posting.result(timeout=10) == 200
    assert_matching_cash(factory, payment_id, "200")
