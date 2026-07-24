import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import *  # noqa: F401,F403
from app.db.session import Base, get_db
from app.main import app
from app.models.identity import User
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


def test_users_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/users")

    assert response.status_code == 401


def test_users_requires_manage_permission(client: TestClient) -> None:
    response = client.get("/api/v1/users", headers=auth_header(client, "viewer@example.com", "viewer123"))

    assert response.status_code == 403


def test_admin_can_list_roles_and_users(client: TestClient) -> None:
    headers = auth_header(client)

    roles = client.get("/api/v1/users/roles", headers=headers)
    users = client.get("/api/v1/users", headers=headers)

    assert roles.status_code == 200
    assert {role["name"] for role in roles.json()} >= {"admin", "manager", "cashier", "logist", "viewer"}
    assert users.status_code == 200
    assert any(user["email"] == "admin@example.com" for user in users.json())


def test_admin_can_create_and_update_user(client: TestClient) -> None:
    headers = auth_header(client)

    created = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "operator@example.com",
            "password": "operator123",
            "full_name": "Operator",
            "is_active": True,
            "role_names": ["manager"],
        },
    )
    assert created.status_code == 201
    assert created.json()["role_names"] == ["manager"]

    updated = client.patch(
        f"/api/v1/users/{created.json()['id']}",
        headers=headers,
        json={"is_active": False, "role_names": ["viewer"], "full_name": "Read Only Operator"},
    )
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False
    assert updated.json()["role_names"] == ["viewer"]
    assert updated.json()["full_name"] == "Read Only Operator"


def test_admin_cannot_deactivate_self(client: TestClient, db: Session) -> None:
    headers = auth_header(client)
    admin = db.scalar(select(User).where(User.username == "admin@example.com"))
    assert admin is not None

    response = client.patch(f"/api/v1/users/{admin.id}", headers=headers, json={"is_active": False})

    assert response.status_code == 409


def test_logistics_user_requires_assigned_warehouse(client: TestClient) -> None:
    headers = auth_header(client)

    response = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "logist@example.com",
            "password": "logist123",
            "full_name": "Logistics Operator",
            "is_active": True,
            "role_names": ["logist"],
            "warehouse_ids": [],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Logistics user requires at least one warehouse"


def test_logistics_role_cannot_be_combined_with_other_roles(client: TestClient) -> None:
    headers = auth_header(client)
    warehouse = client.post(
        "/api/v1/warehouses",
        headers=headers,
        json={"code": "LOG-ONLY", "name": "Logistics Only Warehouse"},
    ).json()

    response = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "unsafe-logist@example.com",
            "password": "logist123",
            "role_names": ["logist", "manager"],
            "warehouse_ids": [warehouse["id"]],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Logistics role cannot be combined with other roles"


def test_admin_assigns_warehouses_to_logistics_user(client: TestClient) -> None:
    headers = auth_header(client)
    warehouse = client.post(
        "/api/v1/warehouses",
        headers=headers,
        json={"code": "LOG-USERS", "name": "Logistics Users Warehouse"},
    ).json()

    response = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "logist@example.com",
            "password": "logist123",
            "full_name": "Logistics Operator",
            "is_active": True,
            "role_names": ["logist"],
            "warehouse_ids": [warehouse["id"]],
        },
    )

    assert response.status_code == 201
    assert response.json()["role_names"] == ["logist"]
    assert response.json()["warehouse_ids"] == [warehouse["id"]]
    assert response.json()["warehouse_names"] == ["Logistics Users Warehouse"]
