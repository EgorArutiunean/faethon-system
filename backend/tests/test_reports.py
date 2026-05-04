from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.base import *  # noqa: F401,F403
from app.db.session import Base, get_db
from app.main import app
from app.models.accounting import Payment
from app.models.documents import Document
from app.models.identity import Role, User
from app.models.partners import Partner
from app.models.products import Product
from app.models.stock import Warehouse
from app.schemas.cash import CashOperationCreate
from app.schemas.documents import DocumentCreate, DocumentLineCreate
from app.schemas.payments import PaymentCreate
from app.services.auth_seed import seed_auth_defaults
from app.services.cash_service import create_cash_operation
from app.services.documents_service import add_document_line, cancel_document, create_document, post_document
from app.services.payments_service import create_payment, post_payment


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


def auth_header(client: TestClient, email: str = "admin@example.com", password: str = "admin123") -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_user_without_reports(db: Session) -> None:
    role = Role(name="no_reports", description="No reports")
    user = User(
        username="no-reports@example.com",
        full_name="No Reports",
        hashed_password=hash_password("password"),
        is_active=True,
        roles=[role],
    )
    db.add(user)
    db.commit()


def seed_report_data(db: Session) -> dict[str, int]:
    product = Product(name="Report Bolt", sku="R-BOLT")
    warehouse = Warehouse(name="Report Main", code="R-MAIN")
    partner = Partner(name="Report Customer", code="R-CUST")
    supplier = Partner(name="Report Supplier", code="R-SUP")
    db.add_all([product, warehouse, partner, supplier])
    db.commit()

    incoming = create_document(
        db,
        DocumentCreate(
            document_type=Document.TYPE_INCOMING,
            document_date=date(2026, 5, 1),
            partner_id=supplier.id,
            warehouse_id=warehouse.id,
        ),
    )
    add_document_line(db, incoming.id, DocumentLineCreate(product_id=product.id, quantity=Decimal("10"), price=Decimal("5.00")))
    post_document(db, incoming.id)

    outgoing = create_document(
        db,
        DocumentCreate(
            document_type=Document.TYPE_OUTGOING,
            document_date=date(2026, 5, 2),
            partner_id=partner.id,
            warehouse_id=warehouse.id,
        ),
    )
    add_document_line(db, outgoing.id, DocumentLineCreate(product_id=product.id, quantity=Decimal("3"), price=Decimal("7.00")))
    post_document(db, outgoing.id)

    draft = create_document(
        db,
        DocumentCreate(
            document_type=Document.TYPE_ADJUSTMENT,
            document_date=date(2026, 5, 3),
            partner_id=partner.id,
            warehouse_id=warehouse.id,
        ),
    )
    cancelled = create_document(
        db,
        DocumentCreate(
            document_type=Document.TYPE_INCOMING,
            document_date=date(2026, 5, 4),
            partner_id=supplier.id,
            warehouse_id=warehouse.id,
        ),
    )
    add_document_line(db, cancelled.id, DocumentLineCreate(product_id=product.id, quantity=Decimal("1"), price=Decimal("1.00")))
    post_document(db, cancelled.id)
    cancel_document(db, cancelled.id)

    payment = create_payment(
        db,
        PaymentCreate(
            partner_id=partner.id,
            payment_date=date(2026, 5, 5),
            payment_type=Payment.TYPE_CUSTOMER_PAYMENT,
            amount=Decimal("5.00"),
        ),
    )
    post_payment(db, payment.id)
    create_cash_operation(
        db,
        CashOperationCreate(operation_date=date(2026, 5, 6), operation_type="cash_out", amount=Decimal("2.00")),
    )

    return {"product_id": product.id, "warehouse_id": warehouse.id, "partner_id": partner.id, "draft_id": draft.id}


def test_reports_require_auth(client: TestClient) -> None:
    response = client.get("/api/v1/reports/stock-balances")

    assert response.status_code == 401


def test_reports_require_reports_read(client: TestClient, db: Session) -> None:
    create_user_without_reports(db)

    response = client.get("/api/v1/reports/stock-balances", headers=auth_header(client, "no-reports@example.com", "password"))

    assert response.status_code == 403


def test_admin_manager_viewer_cashier_can_read_reports(client: TestClient) -> None:
    for email, password in [
        ("admin@example.com", "admin123"),
        ("manager@example.com", "manager123"),
        ("viewer@example.com", "viewer123"),
        ("cashier@example.com", "cashier123"),
    ]:
        response = client.get("/api/v1/reports/documents-register", headers=auth_header(client, email, password))
        assert response.status_code == 200


def test_stock_balances_report_returns_seeded_balances(client: TestClient, db: Session) -> None:
    ids = seed_report_data(db)

    response = client.get(
        f"/api/v1/reports/stock-balances?warehouse_id={ids['warehouse_id']}&product_id={ids['product_id']}",
        headers=auth_header(client),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["rows"][0]["product_name"] == "Report Bolt"
    assert Decimal(payload["total_quantity"]) == Decimal("7.000")


def test_partner_debts_report_returns_expected_debt(client: TestClient, db: Session) -> None:
    ids = seed_report_data(db)

    response = client.get(f"/api/v1/reports/partner-debts?partner_id={ids['partner_id']}", headers=auth_header(client))

    assert response.status_code == 200
    payload = response.json()
    assert payload["rows"][0]["partner_name"] == "Report Customer"
    assert Decimal(payload["rows"][0]["balance"]) == Decimal("16.00")
    assert Decimal(payload["total_partner_debt"]) == Decimal("16.00")


def test_cash_book_report_returns_cash_operations(client: TestClient, db: Session) -> None:
    seed_report_data(db)

    response = client.get("/api/v1/reports/cash-book", headers=auth_header(client))

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["rows"]) >= 2
    assert Decimal(payload["cash_in_total"]) == Decimal("5.00")
    assert Decimal(payload["cash_out_total"]) == Decimal("2.00")
    assert Decimal(payload["cash_balance"]) == Decimal("3.00")


def test_documents_register_returns_all_statuses(client: TestClient, db: Session) -> None:
    seed_report_data(db)

    response = client.get("/api/v1/reports/documents-register", headers=auth_header(client))

    assert response.status_code == 200
    payload = response.json()
    statuses = {row["status"] for row in payload["rows"]}
    assert {"posted", "draft", "cancelled"}.issubset(statuses)
    assert Decimal(payload["total_amount"]) == Decimal("72.00")


def test_export_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/reports/stock-balances/export?format=csv")

    assert response.status_code == 401


def test_export_requires_reports_read(client: TestClient, db: Session) -> None:
    create_user_without_reports(db)

    response = client.get(
        "/api/v1/reports/stock-balances/export?format=csv",
        headers=auth_header(client, "no-reports@example.com", "password"),
    )

    assert response.status_code == 403


def test_xlsx_export_returns_correct_content_type(client: TestClient, db: Session) -> None:
    seed_report_data(db)

    response = client.get("/api/v1/reports/documents-register/export?format=xlsx", headers=auth_header(client))

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert response.content.startswith(b"PK")


def test_csv_export_returns_correct_content_type(client: TestClient, db: Session) -> None:
    seed_report_data(db)

    response = client.get("/api/v1/reports/partner-debts/export?format=csv", headers=auth_header(client))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.content.startswith(b"\xef\xbb\xbf")
    assert "Report Customer" in response.content.decode("utf-8-sig")


def test_export_respects_filters(client: TestClient, db: Session) -> None:
    ids = seed_report_data(db)

    response = client.get(
        f"/api/v1/reports/stock-balances/export?format=csv&product_id={ids['product_id'] + 999}",
        headers=auth_header(client),
    )

    assert response.status_code == 200
    content = response.content.decode("utf-8-sig")
    assert "Report Bolt" not in content
    assert "Total quantity,0" in content


def test_unsupported_export_format_returns_400(client: TestClient) -> None:
    response = client.get("/api/v1/reports/stock-balances/export?format=pdf", headers=auth_header(client))

    assert response.status_code == 400
