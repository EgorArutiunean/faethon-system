from datetime import date, datetime, timedelta, timezone
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
from app.models.accounting import CashOperation, Payment
from app.models.documents import Document
from app.models.identity import Role, User
from app.models.partners import Partner
from app.models.products import Product
from app.models.stock import StockBalance, Warehouse
from app.schemas.documents import DocumentCreate, DocumentLineCreate
from app.schemas.payments import PaymentCreate
from app.services.auth_seed import seed_auth_defaults
from app.services.documents_service import add_document_line, create_document
from app.services.payments_service import create_payment


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
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


def auth_header(
    client: TestClient, email: str = "admin@example.com", password: str = "admin123"
) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_user(db: Session, email: str, role_name: str) -> None:
    role = db.scalar(select(Role).where(Role.name == role_name))
    user = db.scalar(select(User).where(User.username == email))
    if user is None:
        user = User(
            username=email,
            full_name=email,
            hashed_password=hash_password("password"),
            is_active=True,
        )
        db.add(user)
    else:
        user.hashed_password = hash_password("password")
    user.roles = [role]
    db.commit()


def make_draft_document(db: Session) -> int:
    product = Product(name="Auth Product", sku="AUTH-P")
    warehouse = Warehouse(name="Auth Warehouse", code="AUTH-W")
    partner = Partner(name="Auth Partner", code="AUTH-C")
    db.add_all([product, warehouse, partner])
    db.commit()
    document = create_document(
        db,
        DocumentCreate(
            document_type="incoming",
            document_date=date(2026, 5, 2),
            warehouse_id=warehouse.id,
            partner_id=partner.id,
        ),
    )
    add_document_line(
        db,
        document.id,
        DocumentLineCreate(product_id=product.id, quantity=Decimal("1"), price=Decimal("1")),
    )
    return document.id


def make_draft_payment(db: Session) -> int:
    partner = Partner(name="Pay Partner", code="PAY-AUTH")
    db.add(partner)
    db.commit()
    payment = create_payment(
        db,
        PaymentCreate(
            partner_id=partner.id,
            payment_date=date(2026, 5, 2),
            payment_type="customer_payment",
            amount=Decimal("3"),
        ),
    )
    return payment.id


def test_login_returns_token(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "admin123"}
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_repeated_failed_logins_lock_account_until_cooldown(
    client: TestClient, db: Session
) -> None:
    for _ in range(5):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "wrong-password"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"

    admin = db.scalar(select(User).where(User.username == "admin@example.com"))
    assert admin is not None
    db.refresh(admin)
    assert admin.failed_login_attempts == 5
    assert admin.locked_until is not None

    locked_response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "admin123"},
    )
    assert locked_response.status_code == 401
    assert locked_response.json()["detail"] == "Invalid credentials"

    admin.locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    recovered = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "admin123"},
    )
    assert recovered.status_code == 200
    db.refresh(admin)
    assert admin.failed_login_attempts == 0
    assert admin.locked_until is None


def test_current_user_works(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me", headers=auth_header(client))

    assert response.status_code == 200
    assert response.json()["email"] == "admin@example.com"
    assert response.json()["must_change_password"] is False
    assert "users.manage" in response.json()["permissions"]


def test_temporary_password_blocks_work_until_changed(client: TestClient, db: Session) -> None:
    admin_role = db.scalar(select(Role).where(Role.name == "admin"))
    user = User(
        username="temporary@example.com",
        full_name="Temporary Admin",
        hashed_password=hash_password("temporary-password"),
        is_active=True,
        must_change_password=True,
        roles=[admin_role],
    )
    db.add(user)
    db.commit()

    headers = auth_header(client, "temporary@example.com", "temporary-password")
    current = client.get("/api/v1/auth/me", headers=headers)
    blocked = client.get("/api/v1/products", headers=headers)
    wrong_current = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "wrong-password", "new_password": "new-secure-password"},
    )
    changed = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "temporary-password", "new_password": "new-secure-password"},
    )

    assert current.status_code == 200
    assert current.json()["must_change_password"] is True
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "PASSWORD_CHANGE_REQUIRED"
    assert wrong_current.status_code == 400
    assert changed.status_code == 200
    assert changed.json()["must_change_password"] is False
    assert client.get("/api/v1/products", headers=headers).status_code == 401
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "temporary@example.com", "password": "temporary-password"},
        ).status_code
        == 401
    )
    new_login = client.post(
        "/api/v1/auth/login",
        json={"email": "temporary@example.com", "password": "new-secure-password"},
    )
    assert new_login.status_code == 200
    new_headers = {"Authorization": f"Bearer {new_login.json()['access_token']}"}
    assert client.get("/api/v1/products", headers=new_headers).status_code == 200


def test_logout_revokes_existing_token(client: TestClient) -> None:
    headers = auth_header(client)

    logged_out = client.post("/api/v1/auth/logout", headers=headers)

    assert logged_out.status_code == 204
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_unauthenticated_request_gets_401(client: TestClient) -> None:
    response = client.get("/api/v1/products")

    assert response.status_code == 401


def test_user_without_permission_gets_403(client: TestClient, db: Session) -> None:
    create_user(db, "viewer@example.com", "viewer")

    response = client.post(
        "/api/v1/products",
        json={"name": "Forbidden Product", "sku": "FORBID", "base_price": "1", "is_active": True},
        headers=auth_header(client, "viewer@example.com", "password"),
    )

    assert response.status_code == 403


def test_admin_can_post_document(client: TestClient, db: Session) -> None:
    document_id = make_draft_document(db)

    response = client.post(f"/api/v1/documents/{document_id}/post", headers=auth_header(client))

    assert response.status_code == 200
    assert response.json()["status"] == "posted"


def test_viewer_cannot_post_document(client: TestClient, db: Session) -> None:
    create_user(db, "viewer2@example.com", "viewer")
    document_id = make_draft_document(db)

    response = client.post(
        f"/api/v1/documents/{document_id}/post",
        headers=auth_header(client, "viewer2@example.com", "password"),
    )

    assert response.status_code == 403


def test_cashier_can_post_payment(client: TestClient, db: Session) -> None:
    create_user(db, "cashier@example.com", "cashier")
    payment_id = make_draft_payment(db)

    response = client.post(
        f"/api/v1/payments/{payment_id}/post",
        headers=auth_header(client, "cashier@example.com", "password"),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "posted"


def test_cashier_can_read_documents_but_cannot_post_them(client: TestClient, db: Session) -> None:
    create_user(db, "cashier@example.com", "cashier")
    document_id = make_draft_document(db)
    headers = auth_header(client, "cashier@example.com", "password")

    list_response = client.get("/api/v1/documents", headers=headers)
    post_response = client.post(f"/api/v1/documents/{document_id}/post", headers=headers)

    assert list_response.status_code == 200
    assert post_response.status_code == 403


def test_viewer_cannot_access_cash_create_or_cancel(client: TestClient, db: Session) -> None:
    create_user(db, "viewer3@example.com", "viewer")
    headers = auth_header(client, "viewer3@example.com", "password")

    response = client.post(
        "/api/v1/cash/operations",
        json={"operation_date": "2026-05-02", "operation_type": "cash_in", "amount": "1.00"},
        headers=headers,
    )

    assert response.status_code == 403


def test_manager_can_run_the_cash_register(client: TestClient) -> None:
    headers = auth_header(client, "manager@example.com", "manager123")

    current_user = client.get("/api/v1/auth/me", headers=headers)
    created = client.post(
        "/api/v1/cash/operations",
        json={
            "operation_date": "2026-05-02",
            "operation_type": "cash_in",
            "amount": "10.00",
            "note": "Opening balance",
        },
        headers=headers,
    )

    assert current_user.status_code == 200
    assert {"cash.read", "cash.create", "cash.cancel"} <= set(current_user.json()["permissions"])
    assert created.status_code == 201

    listed = client.get("/api/v1/cash/book", headers=headers)
    cancelled = client.post(
        f"/api/v1/cash/operations/{created.json()['id']}/cancel",
        headers=headers,
    )

    assert listed.status_code == 200
    assert listed.json()[0]["balance"] == "10.00"
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_cash_operation_author_cannot_be_supplied_by_client(client: TestClient) -> None:
    response = client.post(
        "/api/v1/cash/operations",
        json={
            "operation_date": "2026-05-02",
            "operation_type": "cash_in",
            "amount": "1.00",
            "created_by_id": 999,
        },
        headers=auth_header(client),
    )

    assert response.status_code == 422


def test_document_page_supports_partner_search_filters_sort_and_total(
    client: TestClient, db: Session
) -> None:
    partner = Partner(name="Paged Customer", code="PAGE-C", partner_type=Partner.TYPE_CUSTOMER)
    db.add(partner)
    db.flush()
    db.add_all(
        [
            Document(
                document_type=Document.TYPE_OUTGOING,
                number="OUT-OLD",
                document_date=date(2026, 1, 1),
                status=Document.STATUS_POSTED,
                partner_id=partner.id,
                total_amount=Decimal("10"),
            ),
            Document(
                document_type=Document.TYPE_OUTGOING,
                number="OUT-NEW",
                document_date=date(2026, 2, 1),
                status=Document.STATUS_POSTED,
                partner_id=partner.id,
                total_amount=Decimal("20"),
            ),
            Document(
                document_type=Document.TYPE_INCOMING,
                number="IN-OTHER",
                document_date=date(2026, 3, 1),
                status=Document.STATUS_DRAFT,
                partner_id=partner.id,
                total_amount=Decimal("30"),
            ),
        ]
    )
    db.commit()

    response = client.get(
        "/api/v1/documents/page",
        params={
            "search": "Paged",
            "document_type": "outgoing",
            "status": "posted",
            "sort_by": "total_amount",
            "sort_order": "desc",
            "limit": 1,
        },
        headers=auth_header(client),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["limit"] == 1
    assert [item["number"] for item in payload["items"]] == ["OUT-NEW"]


def test_partner_page_and_scoped_balances_are_bounded(client: TestClient, db: Session) -> None:
    partners = [
        Partner(
            name="Alpha Customer", code="ALPHA", phone="111", partner_type=Partner.TYPE_CUSTOMER
        ),
        Partner(name="Beta Customer", code="BETA", phone="222", partner_type=Partner.TYPE_CUSTOMER),
        Partner(
            name="Gamma Supplier", code="GAMMA", phone="333", partner_type=Partner.TYPE_SUPPLIER
        ),
    ]
    db.add_all(partners)
    db.commit()
    headers = auth_header(client)

    response = client.get(
        "/api/v1/partners/page",
        params={
            "search": "customer",
            "partner_type": "customer",
            "sort_by": "name",
            "sort_order": "desc",
            "limit": 1,
        },
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert [item["code"] for item in payload["items"]] == ["BETA"]

    balances = client.get(
        "/api/v1/partners/balances",
        params=[("partner_ids", str(partners[0].id)), ("partner_ids", str(partners[2].id))],
        headers=headers,
    )
    assert balances.status_code == 200
    assert {item["partner_id"] for item in balances.json()} == {partners[0].id, partners[2].id}

    options = client.get(
        "/api/v1/partners/options",
        params={"search": "customer", "role": "customer", "limit": 1},
        headers=headers,
    )
    assert options.status_code == 200
    assert len(options.json()) == 1
    assert options.json()[0]["partner_type"] == "customer"


def test_dashboard_summary_aggregates_period_and_respects_permissions(
    client: TestClient, db: Session
) -> None:
    partner = Partner(name="Dashboard Customer", code="DASH-C", partner_type=Partner.TYPE_CUSTOMER)
    product = Product(name="Dashboard Product", sku="DASH-P")
    warehouse = Warehouse(name="Dashboard Warehouse", code="DASH-W")
    db.add_all([partner, product, warehouse])
    db.flush()
    db.add_all(
        [
            Document(
                document_type=Document.TYPE_OUTGOING,
                number="DASH-OUT",
                document_date=date(2026, 5, 2),
                status=Document.STATUS_POSTED,
                partner_id=partner.id,
                warehouse_id=warehouse.id,
                total_amount=Decimal("150"),
            ),
            Document(
                document_type=Document.TYPE_INCOMING,
                number="DASH-IN",
                document_date=date(2026, 5, 1),
                status=Document.STATUS_POSTED,
                partner_id=partner.id,
                warehouse_id=warehouse.id,
                total_amount=Decimal("100"),
            ),
            Document(
                document_type=Document.TYPE_OUTGOING,
                number="DASH-DRAFT",
                document_date=date(2026, 5, 3),
                status=Document.STATUS_DRAFT,
                partner_id=partner.id,
                warehouse_id=warehouse.id,
                total_amount=Decimal("999"),
            ),
            Document(
                document_type=Document.TYPE_OUTGOING,
                number="DASH-OLD",
                document_date=date(2026, 4, 30),
                status=Document.STATUS_POSTED,
                partner_id=partner.id,
                warehouse_id=warehouse.id,
                total_amount=Decimal("500"),
            ),
            Payment(
                partner_id=partner.id,
                payment_date=date(2026, 5, 2),
                payment_type=Payment.TYPE_CUSTOMER_PAYMENT,
                status=Payment.STATUS_POSTED,
                amount=Decimal("25"),
                method="cash",
            ),
            Payment(
                partner_id=partner.id,
                payment_date=date(2026, 5, 3),
                payment_type=Payment.TYPE_CUSTOMER_PAYMENT,
                status=Payment.STATUS_DRAFT,
                amount=Decimal("10"),
                method="cash",
            ),
            StockBalance(product_id=product.id, warehouse_id=warehouse.id, quantity=Decimal("7")),
            CashOperation(
                operation_date=date(2026, 5, 1),
                operation_type=CashOperation.TYPE_CASH_IN,
                direction="in",
                status=CashOperation.STATUS_POSTED,
                amount=Decimal("200"),
            ),
            CashOperation(
                operation_date=date(2026, 5, 2),
                operation_type=CashOperation.TYPE_CASH_OUT,
                direction="out",
                status=CashOperation.STATUS_POSTED,
                amount=Decimal("50"),
            ),
            CashOperation(
                operation_date=date(2026, 5, 3),
                operation_type=CashOperation.TYPE_CASH_IN,
                direction="in",
                status=CashOperation.STATUS_CANCELLED,
                amount=Decimal("999"),
            ),
        ]
    )
    db.commit()

    response = client.get(
        "/api/v1/dashboard/summary",
        params={"date_from": "2026-05-01", "recent_limit": 2},
        headers=auth_header(client),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["documents_count"] == 3
    assert payload["outgoing_total"] == "150.00"
    assert payload["incoming_total"] == "100.00"
    assert payload["document_statuses"] == {"draft": 1, "posted": 2}
    assert payload["payment_statuses"] == {"draft": 1, "posted": 1}
    assert payload["stock_positions_count"] == 1
    assert payload["stock_total_quantity"] == "7.000"
    assert payload["top_warehouses"] == [{"name": "Dashboard Warehouse", "quantity": "7.000"}]
    assert payload["cash_balance"] == "150.00"
    assert [item["number"] for item in payload["recent_documents"]] == ["DASH-DRAFT", "DASH-OUT"]

    cashier = client.get(
        "/api/v1/dashboard/summary",
        headers=auth_header(client, "cashier@example.com", "cashier123"),
    )
    assert cashier.status_code == 200
    assert cashier.json()["products_count"] is None
    assert cashier.json()["stock_positions_count"] is None
    assert cashier.json()["partners_count"] is not None
    assert cashier.json()["documents_count"] is not None
