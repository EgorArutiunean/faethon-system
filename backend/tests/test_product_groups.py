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


def test_product_group_crud_and_product_assignment(client: TestClient, db: Session) -> None:
    headers = auth_header(client)

    create_response = client.post(
        "/api/v1/product-groups", json={"name": "Напитки"}, headers=headers
    )
    assert create_response.status_code == 201
    group_id = create_response.json()["id"]

    product_response = client.post(
        "/api/v1/products",
        json={
            "sku": "DRINK-1",
            "name": "Напит. НОН СТОП энергит. 0.5л 1*24шт",
            "group_id": group_id,
            "base_price": "14.00",
        },
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


def test_product_page_supports_search_sort_pagination_and_group_counts(
    client: TestClient, db: Session
) -> None:
    headers = auth_header(client)
    drinks = ProductGroup(name="Напитки")
    snacks = ProductGroup(name="Снеки")
    db.add_all([drinks, snacks])
    db.flush()
    db.add_all(
        [
            Product(sku="COLA-2", name="Кола большая", group_id=drinks.id, base_price=20),
            Product(sku="COLA-1", name="Кола маленькая", group_id=drinks.id, base_price=10),
            Product(sku="SNACK-1", name="Сухарики", group_id=snacks.id, base_price=5),
        ]
    )
    db.commit()

    response = client.get(
        "/api/v1/products/page",
        params=[
            ("search", "cola"),
            ("sort_by", "base_price"),
            ("sort_order", "desc"),
            ("limit", "1"),
            ("group_ids", str(drinks.id)),
        ],
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["offset"] == 0
    assert payload["limit"] == 1
    assert [row["sku"] for row in payload["items"]] == ["COLA-2"]

    counts_response = client.get("/api/v1/products/group-counts", headers=headers)
    assert counts_response.status_code == 200
    counts = counts_response.json()
    assert counts["total"] == 3
    assert {row["group_id"]: row["count"] for row in counts["items"]} == {
        drinks.id: 2,
        snacks.id: 1,
    }


def test_product_options_are_bounded_and_search_name_or_sku(
    client: TestClient, db: Session
) -> None:
    headers = auth_header(client)
    db.add_all(
        [
            Product(sku="MATCH-SKU", name="Обычное имя", is_active=True),
            Product(sku="OTHER", name="Искомый товар", is_active=True),
            Product(sku="MATCH-INACTIVE", name="Скрытый", is_active=False),
        ]
    )
    db.commit()

    by_sku = client.get("/api/v1/products/options", params={"search": "match"}, headers=headers)
    by_name = client.get("/api/v1/products/options", params={"search": "товар"}, headers=headers)

    assert by_sku.status_code == 200
    assert [row["sku"] for row in by_sku.json()] == ["MATCH-SKU"]
    assert by_name.status_code == 200
    assert [row["sku"] for row in by_name.json()] == ["OTHER"]


def test_duplicate_product_group_name_is_rejected(client: TestClient) -> None:
    headers = auth_header(client)

    assert (
        client.post("/api/v1/product-groups", json={"name": "Бакалея"}, headers=headers).status_code
        == 201
    )
    response = client.post("/api/v1/product-groups", json={"name": "Бакалея"}, headers=headers)

    assert response.status_code == 409


def test_nested_product_groups_are_supported(client: TestClient) -> None:
    headers = auth_header(client)

    root_response = client.post(
        "/api/v1/product-groups", json={"name": "Продукты"}, headers=headers
    )
    assert root_response.status_code == 201
    root_id = root_response.json()["id"]

    child_response = client.post(
        "/api/v1/product-groups",
        json={"name": "Напитки", "parent_id": root_id},
        headers=headers,
    )
    assert child_response.status_code == 201
    child_id = child_response.json()["id"]
    assert child_response.json()["parent_id"] == root_id
    assert child_response.json()["parent_name"] == "Продукты"

    grandchild_response = client.post(
        "/api/v1/product-groups",
        json={"name": "Газированные напитки", "parent_id": child_id},
        headers=headers,
    )
    assert grandchild_response.status_code == 201
    assert grandchild_response.json()["parent_id"] == child_id
    assert grandchild_response.json()["parent_name"] == "Напитки"


def test_product_group_indirect_cycle_is_rejected(client: TestClient, db: Session) -> None:
    headers = auth_header(client)
    root = ProductGroup(name="Продукты")
    child = ProductGroup(name="Напитки", parent=root)
    grandchild = ProductGroup(name="Газированные напитки", parent=child)
    db.add_all([root, child, grandchild])
    db.commit()

    response = client.patch(
        f"/api/v1/product-groups/{root.id}",
        json={"parent_id": grandchild.id},
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Product group hierarchy cannot contain cycles"
    db.refresh(root)
    assert root.parent_id is None


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
