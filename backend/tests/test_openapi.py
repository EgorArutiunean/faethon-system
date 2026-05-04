from fastapi.testclient import TestClient

from app.main import app


def test_openapi_contains_core_tags() -> None:
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    tags = {tag["name"] for tag in response.json()["tags"]}
    assert {"health", "products", "partners", "warehouses", "documents"}.issubset(tags)
