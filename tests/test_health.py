from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_root_returns_service_metadata() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "Review Robin Web",
        "status": "ok",
        "health": "/health",
        "docs": "/docs",
    }


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
