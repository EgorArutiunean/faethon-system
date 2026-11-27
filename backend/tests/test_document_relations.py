from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.base import *  # noqa: F401,F403
from app.db.session import Base, get_db
from app.main import app
from app.models.accounting import Payment, PaymentAllocation
from app.models.documents import Document
from app.models.identity import Permission, Role, User
from app.models.logistics import WarehouseTask
from app.models.partners import Partner
from app.models.stock import Warehouse
from app.services.auth_seed import seed_auth_defaults


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    seed_auth_defaults(session)
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def client(db: Session) -> TestClient:
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def headers(db: Session, username: str = "manager@example.com") -> dict[str, str]:
    user = db.scalar(select(User).where(User.username == username))
    assert user is not None
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def related_records(db: Session):
    warehouse = Warehouse(name="Relations warehouse", code="REL-W")
    customer = Partner(name="Relations customer", code="REL-C", partner_type=Partner.TYPE_BOTH)
    db.add_all([warehouse, customer])
    db.flush()
    documents = [
        Document(
            number=f"REL-{index}",
            document_type=kind,
            document_date=date(2026, 10, 20),
            status=status,
            partner_id=customer.id,
            warehouse_id=warehouse.id,
            total_amount=Decimal("100.00"),
            posting_version=1,
        )
        for index, (kind, status) in enumerate(
            [
                (Document.TYPE_OUTGOING, Document.STATUS_POSTED),
                (Document.TYPE_OUTGOING, Document.STATUS_POSTED),
                (Document.TYPE_INCOMING, Document.STATUS_DRAFT),
            ],
            1,
        )
    ]
    db.add_all(documents)
    db.flush()
    first, second, draft = documents
    payments = []
    for status, amount, allocations in [
        (Payment.STATUS_POSTED, "90", [(first.id, "30"), (second.id, "50")]),
        (Payment.STATUS_DRAFT, "20", [(first.id, "20")]),
        (Payment.STATUS_CANCELLED, "10", [(first.id, "10")]),
        (Payment.STATUS_POSTED, "40", []),
        (Payment.STATUS_POSTED, "5", [(second.id, "5")]),
    ]:
        payment = Payment(
            partner_id=customer.id,
            payment_date=date(2026, 10, 21),
            payment_type=Payment.TYPE_CUSTOMER_PAYMENT,
            amount=Decimal(amount),
            status=status,
            method="cash",
        )
        payment.allocations = [
            PaymentAllocation(document_id=document_id, amount=Decimal(value))
            for document_id, value in allocations
        ]
        db.add(payment)
        payments.append(payment)
    db.commit()
    return warehouse, first, second, draft, payments


def test_document_summary_counts_only_posted_allocations_not_full_split_payment(
    client: TestClient, db: Session
) -> None:
    _warehouse, first, _second, _draft, payments = related_records(db)

    response = client.get(f"/api/v1/payments/document-summary/{first.id}", headers=headers(db))

    assert response.status_code == 200
    payload = response.json()
    assert payload["paid_amount"] == "30.00"
    assert payload["outstanding_amount"] == "70.00"
    assert payload["payment_type"] == "customer_payment"
    assert payload["payments_count"] == 3
    assert {row["id"] for row in payload["payments"]} == {payment.id for payment in payments[:3]}
    posted = next(row for row in payload["payments"] if row["id"] == payments[0].id)
    assert posted["amount"] == "90.00"
    assert posted["allocated_amount_for_document"] == "30.00"
    assert {row["status"] for row in payload["payments"]} == {"draft", "posted", "cancelled"}


def test_document_summary_releases_cancelled_amount_and_draft_is_not_payable(
    client: TestClient, db: Session
) -> None:
    _warehouse, first, _second, draft, payments = related_records(db)
    payments[0].status = Payment.STATUS_CANCELLED
    db.commit()

    cancelled = client.get(
        f"/api/v1/payments/document-summary/{first.id}", headers=headers(db)
    ).json()
    pending = client.get(
        f"/api/v1/payments/document-summary/{draft.id}", headers=headers(db)
    ).json()

    assert cancelled["paid_amount"] == "0.00"
    assert cancelled["outstanding_amount"] == "100.00"
    assert cancelled["payments_count"] == 3
    assert pending["document_status"] == "draft"
    assert Decimal(pending["outstanding_amount"]) == 0
    assert pending["payment_type"] == "supplier_payment"


def test_document_payment_page_filter_matches_split_and_legacy_links_before_pagination(
    client: TestClient, db: Session
) -> None:
    _warehouse, first, second, _draft, payments = related_records(db)
    legacy = Payment(
        partner_id=first.partner_id,
        document_id=first.id,
        payment_date=date(2026, 10, 22),
        payment_type=Payment.TYPE_CUSTOMER_PAYMENT,
        amount=Decimal("1"),
        method="cash",
        status=Payment.STATUS_DRAFT,
    )
    db.add(legacy)
    db.commit()
    auth = headers(db)
    response = client.get(
        f"/api/v1/payments/page?document_id={first.id}&limit=2&offset=1&sort_by=id&sort_order=asc",
        headers=auth,
    )

    assert response.status_code == 200
    assert response.json()["total"] == 4
    assert [row["id"] for row in response.json()["items"]] == [payments[1].id, payments[2].id]
    other = client.get(
        f"/api/v1/payments/page?document_id={second.id}&status=posted", headers=auth
    ).json()
    assert other["total"] == 2
    assert {row["id"] for row in other["items"]} == {payments[0].id, payments[4].id}
    assert client.get("/api/v1/payments/page?document_id=0", headers=auth).status_code == 422


def test_document_summary_requires_both_financial_and_document_permission(
    client: TestClient, db: Session
) -> None:
    _warehouse, first, _second, _draft, _payments = related_records(db)
    document_only = Role(
        name="document-only",
        permissions=[db.scalar(select(Permission).where(Permission.code == "documents.read"))],
    )
    payment_only = Role(
        name="payment-only",
        permissions=[db.scalar(select(Permission).where(Permission.code == "payments.read"))],
    )
    db.add_all(
        [
            User(username="document-only", hashed_password="unused", roles=[document_only]),
            User(username="payment-only", hashed_password="unused", roles=[payment_only]),
        ]
    )
    db.commit()
    path = f"/api/v1/payments/document-summary/{first.id}"

    assert client.get(path, headers=headers(db, "document-only")).status_code == 403
    assert client.get(path, headers=headers(db, "payment-only")).status_code == 403
    assert client.get(path, headers=headers(db, "viewer@example.com")).status_code == 200
    assert client.get(path, headers=headers(db, "cashier@example.com")).status_code == 200
    assert (
        client.get("/api/v1/payments/document-summary/99999", headers=headers(db)).status_code
        == 404
    )


def test_document_task_filter_keeps_warehouse_scope_and_filters_before_limit(
    client: TestClient, db: Session
) -> None:
    warehouse, first, second, _draft, _payments = related_records(db)
    other = Warehouse(name="Other relations warehouse", code="REL-OTHER")
    role = db.scalar(select(Role).where(Role.name == "logist"))
    operator = User(
        username="relations-logist", hashed_password="unused", roles=[role], warehouses=[warehouse]
    )
    db.add_all([other, operator])
    db.flush()
    target = WarehouseTask(
        document_id=first.id,
        posting_version=1,
        warehouse_id=warehouse.id,
        task_type=WarehouseTask.TYPE_OUTGOING_DISPATCH,
    )
    unrelated = WarehouseTask(
        document_id=second.id,
        posting_version=1,
        warehouse_id=warehouse.id,
        task_type=WarehouseTask.TYPE_OUTGOING_DISPATCH,
    )
    hidden = WarehouseTask(
        document_id=first.id,
        posting_version=1,
        warehouse_id=other.id,
        task_type=WarehouseTask.TYPE_OUTGOING_DISPATCH,
    )
    db.add_all([target, unrelated, hidden])
    db.commit()

    scoped = client.get(
        f"/api/v1/logistics/tasks?document_id={first.id}&limit=1",
        headers=headers(db, operator.username),
    )
    manager = client.get(f"/api/v1/logistics/tasks?document_id={first.id}", headers=headers(db))

    assert scoped.status_code == 200
    assert [row["id"] for row in scoped.json()] == [target.id]
    assert {row["id"] for row in manager.json()} == {target.id, hidden.id}
    assert (
        client.get("/api/v1/logistics/tasks?document_id=0", headers=headers(db)).status_code == 422
    )
