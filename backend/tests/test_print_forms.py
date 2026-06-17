from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.base import *  # noqa: F401,F403
from app.db.session import Base, get_db
from app.main import app
from app.models.identity import Role, User
from app.models.partners import Partner
from app.models.products import Product
from app.models.stock import Warehouse
from app.schemas.documents import DocumentCreate, DocumentLineCreate
from app.services.auth_seed import seed_auth_defaults
from app.services.documents_service import add_document_line, create_document


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


def create_user_without_documents_read(db: Session) -> None:
    role = Role(name="no_documents_read", description="No documents read")
    user = User(
        username="no-docs@example.com",
        full_name="No Docs",
        hashed_password=hash_password("password"),
        is_active=True,
        roles=[role],
    )
    db.add(user)
    db.commit()


def make_document(db: Session) -> int:
    product = Product(name="Printable Bolt", sku="PRINT-BOLT")
    warehouse = Warehouse(name="Print Warehouse", code="PRINT-WH", address="Warehouse address")
    partner = Partner(name="Print Partner", code="PRINT-P", tax_id="TAX-777", phone="+373000000", address="Partner address")
    db.add_all([product, warehouse, partner])
    db.commit()
    document = create_document(
        db,
        DocumentCreate(
            document_type="incoming",
            document_date=date(2026, 5, 2),
            partner_id=partner.id,
            warehouse_id=warehouse.id,
            note="Printed for QA",
        ),
    )
    add_document_line(db, document.id, DocumentLineCreate(product_id=product.id, quantity=Decimal("2"), price=Decimal("11.50")))
    return document.id


def test_print_requires_auth(client: TestClient, db: Session) -> None:
    document_id = make_document(db)

    response = client.get(f"/api/v1/documents/{document_id}/print")

    assert response.status_code == 401


def test_print_requires_documents_read(client: TestClient, db: Session) -> None:
    create_user_without_documents_read(db)
    document_id = make_document(db)

    response = client.get(
        f"/api/v1/documents/{document_id}/print",
        headers=auth_header(client, "no-docs@example.com", "password"),
    )

    assert response.status_code == 403


def test_print_existing_document_returns_200(client: TestClient, db: Session) -> None:
    document_id = make_document(db)

    response = client.get(f"/api/v1/documents/{document_id}/print", headers=auth_header(client))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


def test_print_missing_document_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/documents/9999/print", headers=auth_header(client))

    assert response.status_code == 404


def test_print_contains_document_number_and_total_amount(client: TestClient, db: Session) -> None:
    document_id = make_document(db)

    response = client.get(f"/api/v1/documents/{document_id}/print.html", headers=auth_header(client))

    assert response.status_code == 200
    assert "IN-000001" in response.text
    assert "23.00" in response.text
    assert "Printable Bolt" in response.text


def test_print_form_has_business_ready_russian_layout(client: TestClient, db: Session) -> None:
    document_id = make_document(db)

    response = client.get(f"/api/v1/documents/{document_id}/print.html", headers=auth_header(client))

    assert response.status_code == 200
    assert "Приходная накладная" in response.text
    assert "Черновик" in response.text
    assert "Print Warehouse" in response.text
    assert "PRINT-WH" in response.text
    assert "Warehouse address" in response.text
    assert "Print Partner" in response.text
    assert "TAX-777" in response.text
    assert "+373000000" in response.text
    assert "Printed for QA" in response.text
    assert "ЧЕРНОВИК" in response.text
    assert "TODO" not in response.text
    assert "Рџ" not in response.text
    assert "Рќ" not in response.text
    assert "СЃ" not in response.text
