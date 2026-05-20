from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_list_datasources_empty():
    response = client.get("/api/datasources")
    assert response.status_code == 200
    assert response.json() == {"datasources": []}


def test_internal_schema_empty():
    response = client.get("/internal/schema")
    assert response.status_code == 200
    body = response.json()
    assert "schema" in body
    assert "combined" in body
    assert "context" in body
    assert "context_by_view" in body


def test_internal_datasources_empty():
    response = client.get("/internal/datasources")
    assert response.status_code == 200
    assert response.json() == {"datasources": []}


def test_create_space():
    response = client.post("/create-space")
    assert response.status_code == 200
    assert "id" in response.json()


def test_start_analysis_validation_no_datasource():
    space = client.post("/create-space").json()["id"]
    response = client.post(
        "/start-analysis",
        json={
            "space_id": space,
            "query": "show me sales",
            "tables": [],
            "mode": "standard",
            "model": "",
            "index": -1,
        },
    )
    assert response.status_code == 200
    assert response.json()["error"] == "No database registered"
