from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import *  # noqa: F401,F403
from app.db.session import Base, get_db
from app.main import app
from app.models.documents import Document, DocumentLine
from app.models.logistics import WarehouseTask
from app.models.partners import Partner
from app.models.products import Product
from app.models.stock import StockBalance, StockMovement, Warehouse
from app.services.auth_seed import seed_auth_defaults
from app.schemas.documents import DocumentCreate, DocumentLineCreate, DocumentRepost
from app.services.documents_service import add_document_line, cancel_document, create_document, post_document, repost_document


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    session = TestingSession()
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


def login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def seed_logistics_data(db: Session) -> tuple[Warehouse, Document, Document]:
    assigned = Warehouse(code="LOG-A", name="Assigned Warehouse")
    other = Warehouse(code="LOG-B", name="Other Warehouse")
    supplier = Partner(code="LOG-SUP", name="Logistics Supplier", partner_type=Partner.TYPE_SUPPLIER)
    customer = Partner(code="LOG-CUST", name="Logistics Customer", partner_type=Partner.TYPE_CUSTOMER)
    product = Product(sku="LOG-P", name="Logistics Product", base_price=Decimal("150.00"), is_active=True)
    db.add_all([assigned, other, supplier, customer, product])
    db.flush()

    incoming = Document(
        document_type=Document.TYPE_INCOMING,
        number="IN-LOG-1",
        document_date=date(2026, 7, 24),
        status=Document.STATUS_POSTED,
        partner_id=supplier.id,
        warehouse_id=assigned.id,
        total_amount=Decimal("800.00"),
        currency_code="USD",
        exchange_rate=Decimal("16.20"),
        foreign_total_amount=Decimal("50.00"),
    )
    other_outgoing = Document(
        document_type=Document.TYPE_OUTGOING,
        number="OUT-LOG-2",
        document_date=date(2026, 7, 24),
        status=Document.STATUS_POSTED,
        partner_id=customer.id,
        warehouse_id=other.id,
        total_amount=Decimal("175.00"),
    )
    db.add_all([incoming, other_outgoing])
    db.flush()
    db.add_all(
        [
            DocumentLine(
                document_id=incoming.id,
                product_id=product.id,
                quantity=Decimal("2"),
                price=Decimal("400.00"),
                line_total=Decimal("800.00"),
                foreign_price=Decimal("25.00"),
                foreign_line_total=Decimal("50.00"),
            ),
            DocumentLine(
                document_id=other_outgoing.id,
                product_id=product.id,
                quantity=Decimal("1"),
                price=Decimal("175.00"),
                line_total=Decimal("175.00"),
            ),
        ]
    )
    db.commit()
    return assigned, incoming, other_outgoing


def create_logistics_user(client: TestClient, warehouse_id: int) -> dict[str, str]:
    admin_headers = login(client, "admin@example.com", "admin123")
    response = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "email": "logist@example.com",
            "password": "logist123",
            "full_name": "Logistics Operator",
            "role_names": ["logist"],
            "warehouse_ids": [warehouse_id],
        },
    )
    assert response.status_code == 201
    return login(client, "logist@example.com", "logist123")


def create_logistics_user_with_email(
    client: TestClient,
    warehouse_id: int,
    email: str,
) -> dict[str, str]:
    admin_headers = login(client, "admin@example.com", "admin123")
    response = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "email": email,
            "password": "logist123",
            "full_name": email,
            "role_names": ["logist"],
            "warehouse_ids": [warehouse_id],
        },
    )
    assert response.status_code == 201
    return login(client, email, "logist123")


def post_incoming_task(db: Session, *, quantity: str = "5") -> tuple[Document, Product, Warehouse, Partner]:
    warehouse = Warehouse(code="TASK-W", name="Task Warehouse")
    supplier = Partner(code="TASK-S", name="Task Supplier", partner_type=Partner.TYPE_SUPPLIER)
    product = Product(sku="TASK-P", name="Task Product", base_price=Decimal("150.00"), is_active=True)
    db.add_all([warehouse, supplier, product])
    db.commit()
    document = create_document(
        db,
        DocumentCreate(
            document_type=Document.TYPE_INCOMING,
            document_date=date(2026, 9, 2),
            partner_id=supplier.id,
            warehouse_id=warehouse.id,
        ),
    )
    add_document_line(
        db,
        document.id,
        DocumentLineCreate(product_id=product.id, quantity=Decimal(quantity), price=Decimal("70.00")),
    )
    return post_document(db, document.id), product, warehouse, supplier


def test_logistics_sees_only_assigned_documents_and_sale_price(client: TestClient, db: Session) -> None:
    assigned, incoming, other_outgoing = seed_logistics_data(db)
    headers = create_logistics_user(client, assigned.id)

    response = client.get("/api/v1/logistics/documents", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert [document["id"] for document in payload] == [incoming.id]
    assert other_outgoing.id not in [document["id"] for document in payload]
    assert payload[0]["lines"][0]["sale_price"] == "150.00"
    assert payload[0]["lines"][0]["sale_total"] == "300.00"
    assert "price" not in payload[0]["lines"][0]
    assert "foreign_price" not in payload[0]["lines"][0]
    assert "total_amount" not in payload[0]
    assert "currency_code" not in payload[0]
    assert "exchange_rate" not in payload[0]
    assert "foreign_total_amount" not in payload[0]


def test_logistics_cannot_bypass_scoped_document_endpoint(client: TestClient, db: Session) -> None:
    assigned, incoming, other_outgoing = seed_logistics_data(db)
    headers = create_logistics_user(client, assigned.id)

    regular_documents = client.get("/api/v1/documents", headers=headers)
    own_document = client.get(f"/api/v1/logistics/documents/{incoming.id}", headers=headers)
    other_document = client.get(f"/api/v1/logistics/documents/{other_outgoing.id}", headers=headers)
    post_document = client.post(f"/api/v1/documents/{incoming.id}/post", headers=headers)

    assert regular_documents.status_code == 403
    assert own_document.status_code == 200
    assert other_document.status_code == 404
    assert post_document.status_code == 403


def test_posting_creates_scoped_task_without_purchase_data(client: TestClient, db: Session) -> None:
    document, _product, warehouse, _supplier = post_incoming_task(db)
    headers = create_logistics_user(client, warehouse.id)

    response = client.get("/api/v1/logistics/tasks", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["document_id"] == document.id
    assert payload[0]["posting_version"] == 1
    assert payload[0]["task_type"] == "incoming_receive"
    assert payload[0]["status"] == "pending"
    assert payload[0]["lines"][0]["sale_price"] == "150.00"
    assert payload[0]["lines"][0]["sale_total"] == "750.00"
    forbidden_fields = {"price", "foreign_price", "currency_code", "exchange_rate", "purchase_cost"}
    assert forbidden_fields.isdisjoint(payload[0])
    assert forbidden_fields.isdisjoint(payload[0]["lines"][0])


def test_task_is_taken_exclusively_and_confirmation_does_not_move_stock(client: TestClient, db: Session) -> None:
    _document, product, warehouse, _supplier = post_incoming_task(db)
    first_headers = create_logistics_user_with_email(client, warehouse.id, "first-logist@example.com")
    second_headers = create_logistics_user_with_email(client, warehouse.id, "second-logist@example.com")
    task = client.get("/api/v1/logistics/tasks", headers=first_headers).json()[0]

    started = client.post(f"/api/v1/logistics/tasks/{task['id']}/start", headers=first_headers)
    second_start = client.post(f"/api/v1/logistics/tasks/{task['id']}/start", headers=second_headers)
    movement_count = db.query(StockMovement).count()
    balance_before = db.query(StockBalance).filter_by(product_id=product.id, warehouse_id=warehouse.id).one().quantity
    confirmed = client.put(
        f"/api/v1/logistics/tasks/{task['id']}/confirm",
        headers=first_headers,
        json={"lines": [{"line_id": task["lines"][0]["id"], "actual_quantity": "5"}]},
    )

    assert started.status_code == 200
    assert started.json()["assigned_to_name"] == "first-logist@example.com"
    assert second_start.status_code == 409
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "completed"
    assert db.query(StockMovement).count() == movement_count
    assert db.query(StockBalance).filter_by(product_id=product.id, warehouse_id=warehouse.id).one().quantity == balance_before


def test_discrepancy_requires_comment_and_goes_to_manager(client: TestClient, db: Session) -> None:
    _document, _product, warehouse, _supplier = post_incoming_task(db)
    headers = create_logistics_user(client, warehouse.id)
    task = client.get("/api/v1/logistics/tasks", headers=headers).json()[0]
    client.post(f"/api/v1/logistics/tasks/{task['id']}/start", headers=headers)

    rejected = client.put(
        f"/api/v1/logistics/tasks/{task['id']}/confirm",
        headers=headers,
        json={"lines": [{"line_id": task["lines"][0]["id"], "actual_quantity": "4"}]},
    )
    accepted = client.put(
        f"/api/v1/logistics/tasks/{task['id']}/confirm",
        headers=headers,
        json={
            "lines": [
                {"line_id": task["lines"][0]["id"], "actual_quantity": "4", "comment": "Недостача 1 шт."}
            ]
        },
    )
    manager_headers = login(client, "manager@example.com", "manager123")
    manager_tasks = client.get("/api/v1/logistics/tasks?status=needs_review", headers=manager_headers)

    assert rejected.status_code == 422
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "needs_review"
    assert accepted.json()["lines"][0]["status"] == "discrepancy"
    assert manager_tasks.status_code == 200
    assert [item["id"] for item in manager_tasks.json()] == [task["id"]]


def test_transfer_receive_is_unblocked_after_dispatch(client: TestClient, db: Session) -> None:
    incoming, product, source, _supplier = post_incoming_task(db)
    destination = Warehouse(code="TASK-D", name="Destination Warehouse")
    db.add(destination)
    db.commit()
    transfer = create_document(
        db,
        DocumentCreate(
            document_type=Document.TYPE_TRANSFER,
            document_date=date(2026, 9, 2),
            warehouse_id=source.id,
            destination_warehouse_id=destination.id,
        ),
    )
    add_document_line(
        db,
        transfer.id,
        DocumentLineCreate(product_id=product.id, quantity=Decimal("2"), price=Decimal("0")),
    )
    post_document(db, transfer.id)
    source_headers = create_logistics_user_with_email(client, source.id, "source-logist@example.com")
    destination_headers = create_logistics_user_with_email(client, destination.id, "destination-logist@example.com")
    dispatch = next(
        item for item in client.get("/api/v1/logistics/tasks", headers=source_headers).json()
        if item["document_id"] == transfer.id
    )
    receive = client.get("/api/v1/logistics/tasks", headers=destination_headers).json()[0]

    assert receive["status"] == "blocked"
    client.post(f"/api/v1/logistics/tasks/{dispatch['id']}/start", headers=source_headers)
    completed = client.put(
        f"/api/v1/logistics/tasks/{dispatch['id']}/confirm",
        headers=source_headers,
        json={"lines": [{"line_id": dispatch["lines"][0]["id"], "actual_quantity": "2"}]},
    )
    refreshed_receive = client.get(f"/api/v1/logistics/tasks/{receive['id']}", headers=destination_headers)

    assert incoming.status == Document.STATUS_POSTED
    assert completed.status_code == 200
    assert refreshed_receive.json()["status"] == "in_transit"


def test_repost_versions_tasks_and_cancel_closes_active_task(db: Session) -> None:
    document, product, warehouse, supplier = post_incoming_task(db)
    old_task = db.scalar(select(WarehouseTask).where(WarehouseTask.document_id == document.id))
    assert old_task is not None

    repost_document(
        db,
        document.id,
        DocumentRepost(
            document_type=Document.TYPE_INCOMING,
            number=document.number,
            document_date=document.document_date,
            partner_id=supplier.id,
            warehouse_id=warehouse.id,
            currency_code="RUB_PMR",
            exchange_rate=Decimal("1"),
            reason="Исправлено количество",
            lines=[DocumentLineCreate(product_id=product.id, quantity=Decimal("6"), price=Decimal("70"))],
        ),
    )
    tasks = list(db.scalars(select(WarehouseTask).where(WarehouseTask.document_id == document.id).order_by(WarehouseTask.posting_version)))

    assert [(task.posting_version, task.status) for task in tasks] == [(1, "cancelled"), (2, "pending")]
    cancel_document(db, document.id)
    db.refresh(tasks[1])
    assert tasks[1].status == "cancelled"
