"""Smoke test added in PR 0 of the major refactor.

The package conversion moves the ``Jinja2Templates`` directory anchor
from ``Path(__file__).parent / "templates"`` (in the old
``routes_operator.py``) to ``Path(__file__).parent.parent / "templates"``
(in ``routes_operator/_shared.py``). Without the extra ``.parent``
hop, every operator template render 500s. This test catches that
regression by asserting one operator GET returns a 200 with a known
string from ``operator/sessions_list.html``.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_operator_sessions_renders(client: TestClient) -> None:
    response = client.get("/operator/sessions")

    assert response.status_code == 200
    assert "<h1>Sessions</h1>" in response.text
