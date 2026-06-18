from datetime import date
from decimal import Decimal
from html import unescape

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
from app.models.products import Product, Unit
from app.models.stock import Warehouse
from app.schemas.documents import DocumentCreate, DocumentLineCreate
from app.services.auth_seed import seed_auth_defaults
from app.services.documents_service import add_document_line, create_document, post_document


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
    unit = Unit(name="Штука", short_name="шт")
    product = Product(name="Крупа Кутья 0,9к*17шт Рис", sku="93197", unit=unit)
    warehouse = Warehouse(name="МОБИЛЬНЫЙ СКЛАД", code="MOB-WH", address="Warehouse address")
    supplier = Partner(name="Поставщик остатков", partner_type=Partner.TYPE_SUPPLIER)
    customer = Partner(name="Рынок Комсомольский №4 Людмила", partner_type=Partner.TYPE_CUSTOMER)
    db.add_all([unit, product, warehouse, supplier, customer])
    db.commit()
    incoming = create_document(
        db,
        DocumentCreate(
            document_type="incoming",
            document_date=date(2026, 5, 2),
            partner_id=supplier.id,
            warehouse_id=warehouse.id,
        ),
    )
    add_document_line(
        db,
        incoming.id,
        DocumentLineCreate(product_id=product.id, quantity=Decimal("17"), price=Decimal("8.00")),
    )
    post_document(db, incoming.id)
    document = create_document(
        db,
        DocumentCreate(
            document_type="outgoing",
            document_date=date(2026, 5, 2),
            partner_id=customer.id,
            warehouse_id=warehouse.id,
        ),
    )
    add_document_line(
        db,
        document.id,
        DocumentLineCreate(product_id=product.id, quantity=Decimal("17"), price=Decimal("8.00")),
    )
    post_document(db, document.id)
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


def test_print_pdf_requires_auth(client: TestClient, db: Session) -> None:
    document_id = make_document(db)

    response = client.get(f"/api/v1/documents/{document_id}/print.pdf")

    assert response.status_code == 401


def test_print_pdf_requires_documents_read(client: TestClient, db: Session) -> None:
    create_user_without_documents_read(db)
    document_id = make_document(db)

    response = client.get(
        f"/api/v1/documents/{document_id}/print.pdf",
        headers=auth_header(client, "no-docs@example.com", "password"),
    )

    assert response.status_code == 403


def test_print_pdf_existing_document_returns_pdf(client: TestClient, db: Session) -> None:
    document_id = make_document(db)

    response = client.get(f"/api/v1/documents/{document_id}/print.pdf", headers=auth_header(client))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.headers["content-disposition"] == f'attachment; filename="document-{document_id}.pdf"'
    assert response.content.startswith(b"%PDF-")
    assert b"%%EOF" in response.content
    assert len(response.content) > 1000


def test_print_pdf_missing_document_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/documents/9999/print.pdf", headers=auth_header(client))

    assert response.status_code == 404


def test_print_missing_document_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/documents/9999/print", headers=auth_header(client))

    assert response.status_code == 404


def test_print_contains_document_number_and_total_amount(client: TestClient, db: Session) -> None:
    document_id = make_document(db)

    response = client.get(f"/api/v1/documents/{document_id}/print.html", headers=auth_header(client))

    assert response.status_code == 200
    assert "OUT-000001" in response.text
    assert "136.00" in response.text
    assert "Крупа Кутья 0,9к*17шт Рис" in response.text


def test_print_form_matches_legacy_outgoing_invoice_layout(client: TestClient, db: Session) -> None:
    document_id = make_document(db)

    response = client.get(f"/api/v1/documents/{document_id}/print.html", headers=auth_header(client))
    html = unescape(response.text)

    assert response.status_code == 200
    assert "РАСХОДНАЯ НАКЛАДНАЯ № OUT-000001" in html
    assert "Дата:" in html
    assert "2026.05.02" in html
    assert "Поставщик:" in html
    assert "МОБИЛЬНЫЙ СКЛАД" in html
    assert "Покупатель:" in html
    assert "Рынок Комсомольский №4 Людмила" in html
    assert "Доверенность №:" in html
    assert "Отпущено:" in html
    assert ">№<" in html
    assert ">Код<" in html
    assert ">Товар<" in html
    assert ">Ед.<" in html
    assert ">Кол.<" in html
    assert ">Цена<" in html
    assert ">Сумма<" in html
    assert "93197" in html
    assert "Крупа Кутья 0,9к*17шт Рис" in html
    assert ">шт<" in html
    assert ">17<" in html
    assert "8.000" in html
    assert "136.00" in html
    assert "( Сто тридцать шесть рублей 00 копеек )" in html
    assert "Отпустил" in html
    assert "Получил" in html
    assert "ЧЕРНОВИК" not in html
    assert "TODO" not in html
    assert "Рџ" not in html
    assert "Рќ" not in html
    assert "СЃ" not in html
