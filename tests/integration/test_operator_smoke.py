"""Smoke tests for refactor package conversions.

PR 0 of the routes_operator ladder moves the ``Jinja2Templates``
directory anchor from ``Path(__file__).parent / "templates"`` (in
the old ``routes_operator.py``) to
``Path(__file__).parent.parent / "templates"`` (in
``routes_operator/_shared.py``). Without the extra ``.parent`` hop,
every operator template render 500s. ``test_operator_sessions_renders``
catches that regression by asserting one operator GET returns a 200
with a known string from ``operator/sessions_list.html``.

PR 0 of the §12.B (``app/web/views.py`` split) ladder converts
``views.py`` into a package backed by a re-export wall. If the
wall is missing a name, every Session Home render 500s because
``build_setup_rows`` / ``session_status_pills`` /
``build_quick_setup_context`` / ``build_extract_data_context`` —
the most-imported view-shape adapters — would resolve to nothing.
``test_operator_session_home_renders`` covers that regression.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_operator_sessions_renders(client: TestClient) -> None:
    response = client.get("/operator/sessions")

    assert response.status_code == 200
    assert "You don't have any sessions yet." in response.text


def test_operator_session_home_renders(client: TestClient) -> None:
    """Smoke test for §12.B PR 0 — Session Home is the most view-
    builder-dense operator page."""
    create = client.post(
        "/operator/sessions",
        data={"name": "Smoke Test", "code": "smoke-views-pr0"},
        follow_redirects=False,
    )
    assert create.status_code == 303
    home_url = create.headers["location"]

    response = client.get(home_url)
    assert response.status_code == 200
    # Session Home renders the four-card layout and the canonical
    # status pills via ``views.build_setup_rows`` /
    # ``session_status_pills``; both must resolve through the
    # re-export wall for the page to render at all.
    assert "Smoke Test" in response.text
