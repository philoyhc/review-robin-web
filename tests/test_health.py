from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


# The root ``/`` is a role-aware redirect (18R Item 6), not a JSON
# metadata endpoint — it needs an authenticated identity + DB, so its
# behaviour is covered by ``tests/integration/test_landing_pages.py``
# against the authed client. Liveness / metadata lives at ``/health``.


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
