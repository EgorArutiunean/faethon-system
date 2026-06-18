import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import *  # noqa: F401,F403
from app.db.session import Base, get_db
from app.main import app
from app.models.products import Product, ProductGroup
from app.services.auth_seed import seed_auth_defaults


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


def test_product_group_crud_and_product_assignment(client: TestClient, db: Session) -> None:
    headers = auth_header(client)

    create_response = client.post("/api/v1/product-groups", json={"name": "Напитки"}, headers=headers)
    assert create_response.status_code == 201
    group_id = create_response.json()["id"]

    product_response = client.post(
        "/api/v1/products",
        json={"sku": "DRINK-1", "name": "Напит. НОН СТОП энергит. 0.5л 1*24шт", "group_id": group_id, "base_price": "14.00"},
        headers=headers,
    )
    assert product_response.status_code == 201
    assert product_response.json()["group_name"] == "Напитки"

    list_response = client.get("/api/v1/products", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()[0]["group_id"] == group_id
    assert list_response.json()[0]["group_name"] == "Напитки"

    product = db.scalar(select(Product).where(Product.sku == "DRINK-1"))
    assert product is not None
    assert product.group_id == group_id


def test_duplicate_product_group_name_is_rejected(client: TestClient) -> None:
    headers = auth_header(client)

    assert client.post("/api/v1/product-groups", json={"name": "Бакалея"}, headers=headers).status_code == 201
    response = client.post("/api/v1/product-groups", json={"name": "Бакалея"}, headers=headers)

    assert response.status_code == 409


def test_used_product_group_cannot_be_deleted(client: TestClient, db: Session) -> None:
    group = ProductGroup(name="Снеки")
    db.add(group)
    db.flush()
    db.add(Product(sku="SNACK-1", name="Сухарики", group_id=group.id))
    db.commit()

    response = client.delete(f"/api/v1/product-groups/{group.id}", headers=auth_header(client))

    assert response.status_code == 409


def test_viewer_cannot_create_product_group(client: TestClient) -> None:
    response = client.post(
        "/api/v1/product-groups",
        json={"name": "Forbidden"},
        headers=auth_header(client, "viewer@example.com", "viewer123"),
    )

    assert response.status_code == 403
