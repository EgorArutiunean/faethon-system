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
from app.models.identity import Role, User
from app.models.partners import Partner
from app.models.products import Product
from app.models.stock import Warehouse
from app.schemas.documents import DocumentCreate, DocumentLineCreate
from app.schemas.payments import PaymentCreate
from app.services.auth_seed import seed_auth_defaults
from app.core.security import hash_password
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


def create_user(db: Session, email: str, role_name: str) -> None:
    role = db.scalar(select(Role).where(Role.name == role_name))
    user = db.scalar(select(User).where(User.username == email))
    if user is None:
        user = User(username=email, full_name=email, hashed_password=hash_password("password"), is_active=True)
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
        DocumentCreate(document_type="incoming", document_date=date(2026, 5, 2), warehouse_id=warehouse.id, partner_id=partner.id),
    )
    add_document_line(db, document.id, DocumentLineCreate(product_id=product.id, quantity=Decimal("1"), price=Decimal("1")))
    return document.id


def make_draft_payment(db: Session) -> int:
    partner = Partner(name="Pay Partner", code="PAY-AUTH")
    db.add(partner)
    db.commit()
    payment = create_payment(
        db,
        PaymentCreate(partner_id=partner.id, payment_date=date(2026, 5, 2), payment_type="customer_payment", amount=Decimal("3")),
    )
    return payment.id


def test_login_returns_token(client: TestClient) -> None:
    response = client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "admin123"})

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_current_user_works(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me", headers=auth_header(client))

    assert response.status_code == 200
    assert response.json()["email"] == "admin@example.com"
    assert "users.manage" in response.json()["permissions"]


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

    response = client.post(f"/api/v1/documents/{document_id}/post", headers=auth_header(client, "viewer2@example.com", "password"))

    assert response.status_code == 403


def test_cashier_can_post_payment(client: TestClient, db: Session) -> None:
    create_user(db, "cashier@example.com", "cashier")
    payment_id = make_draft_payment(db)

    response = client.post(f"/api/v1/payments/{payment_id}/post", headers=auth_header(client, "cashier@example.com", "password"))

    assert response.status_code == 200
    assert response.json()["status"] == "posted"


def test_viewer_cannot_access_cash_create_or_cancel(client: TestClient, db: Session) -> None:
    create_user(db, "viewer3@example.com", "viewer")
    headers = auth_header(client, "viewer3@example.com", "password")

    response = client.post(
        "/api/v1/cash/operations",
        json={"operation_date": "2026-05-02", "operation_type": "cash_in", "amount": "1.00"},
        headers=headers,
    )

    assert response.status_code == 403
