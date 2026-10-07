"""Segment 14A PR 2 — global error handling.

Exercises the four handlers registered by
``app.web.error_handlers.register_error_handlers``: friendly HTML
pages for ``HTTPException`` (404 / 403), a service's
``SessionStateConflict`` (409, findings Bc4), unhandled exceptions
(500, traceback logged not shown), and request-validation errors
(400). Plus the invitation-specific 404 copy.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from collections.abc import Iterator

import pytest
from fastapi import APIRouter, HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser, get_current_user
from app.db.session import get_db
from app.main import app
from app.services.session_guard import SessionStateConflict

_test_router = APIRouter()


@_test_router.get("/__test/err/forbidden")
def _forbidden() -> dict[str, str]:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have access to this session",
    )


@_test_router.get("/__test/err/not-found-bare")
def _not_found_bare() -> dict[str, str]:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@_test_router.get("/__test/err/state-conflict")
def _state_conflict() -> dict[str, str]:
    raise SessionStateConflict(
        "Session is ready; revert to draft to edit", code="not_editable"
    )


@_test_router.get("/__test/err/boom")
def _boom() -> dict[str, str]:
    raise ValueError("kaboom")


@_test_router.get("/__test/err/typed")
def _typed(n: int) -> dict[str, int]:
    return {"n": n}


@pytest.fixture(autouse=True)
def _mount_test_routes() -> Iterator[None]:
    app.include_router(_test_router)
    try:
        yield
    finally:
        app.router.routes = [
            r
            for r in app.router.routes
            if not getattr(r, "path", "").startswith("/__test/err/")
        ]


def test_unknown_path_renders_html_404() -> None:
    resp = TestClient(app).get("/no/such/page")

    assert resp.status_code == 404
    assert "text/html" in resp.headers["content-type"]
    assert "Page not found" in resp.text
    assert "Error 404" in resp.text


def test_the_error_page_draws_no_drop_shadow() -> None:
    """``error.html`` carries its own stylesheet, outside ``base.html``,
    so the "no drop shadows" rule (``spec/visual_style_general.md``) is
    checked here too (findings Ec10): the card stands out by its
    border. Read from the ``.error-card`` rule in the page's own
    ``<style>`` block, and only an elevation shadow fails: an inset
    marker or focus ring stays allowed (``spec/ui_elements.md``)."""
    resp = TestClient(app).get("/no/such/page")

    assert resp.status_code == 404
    assert "Error 404" in resp.text
    style = resp.text.split("<style>", 1)[1].split("</style>", 1)[0]
    card = re.search(r"\.error-card\s*\{([^}]*)\}", style)
    assert card, "premise: the card rule is there to read"
    shadows = re.findall(r"box-shadow\s*:\s*([^;]+);", card.group(1))
    assert all(
        value.strip() == "none" or "inset" in value for value in shadows
    ), shadows


def test_the_error_card_takes_the_card_shape() -> None:
    """The card shape ``spec/visual_style_general.md`` sets for every card
    — a 2px ``border-default`` edge and an 8px radius — holds on the
    standalone error page too (findings Ec11), with ``border-default``'s
    one value in both themes."""
    resp = TestClient(app).get("/no/such/page")

    style = resp.text.split("<style>", 1)[1].split("</style>", 1)[0]
    card = re.search(r"\.error-card\s*\{([^}]*)\}", style).group(1)
    assert re.search(r"border:\s*2px solid var\(--e-border\)", card)
    assert re.search(r"border-radius:\s*8px", card)
    padding = re.search(r"padding:\s*(\d+)px\s*;", card)
    assert padding and 16 <= int(padding.group(1)) <= 24, card
    # The edge is base.html's --border-default, which points at
    # --slate-dim in both themes: read it there rather than copy the hex,
    # so a repointed token fails here instead of drifting.
    base = (
        Path(__file__).resolve().parents[2] / "app/web/templates/base.html"
    ).read_text()
    assert re.findall(r"--border-default:\s*([^;]+);", base) == [
        "var(--slate-dim)",
        "var(--slate-dim)",
    ]
    (slate_dim,) = re.findall(r"--slate-dim:\s*([^;]+);", base)
    assert re.findall(r"--e-border:\s*([^;]+);", style) == [slate_dim, slate_dim]


def test_http_exception_shows_route_detail() -> None:
    resp = TestClient(app).get("/__test/err/forbidden")

    assert resp.status_code == 403
    assert "Access denied" in resp.text
    assert "You do not have access to this session" in resp.text


def test_a_service_state_conflict_renders_the_409_page() -> None:
    """A service's state gate, decided under the session lock, answers
    as a route's own gate does: the 409 page, carrying its message."""
    resp = TestClient(app).get("/__test/err/state-conflict")

    assert resp.status_code == 409
    assert "text/html" in resp.headers["content-type"]
    assert "Session is ready; revert to draft to edit" in resp.text


def test_bare_http_exception_falls_back_to_default_copy() -> None:
    resp = TestClient(app).get("/__test/err/not-found-bare")

    assert resp.status_code == 404
    # Starlette defaults a detail-less 404 to the phrase "Not Found";
    # the page must show friendly copy, not that phrase.
    assert "Page not found" in resp.text
    assert "Not Found" not in resp.text


def test_unhandled_exception_renders_friendly_500(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = TestClient(app, raise_server_exceptions=False)

    with caplog.at_level(logging.ERROR):
        resp = client.get("/__test/err/boom")

    assert resp.status_code == 500
    assert "Something went wrong" in resp.text
    assert "kaboom" not in resp.text  # traceback never leaks to the user

    logged = [r for r in caplog.records if r.getMessage() == "unhandled exception"]
    assert len(logged) == 1
    assert logged[0].path == "/__test/err/boom"
    assert "ValueError: kaboom" in caplog.text  # but it IS logged


def test_request_validation_error_renders_html_page() -> None:
    resp = TestClient(app).get("/__test/err/typed", params={"n": "not-an-int"})

    assert resp.status_code == 422
    assert "text/html" in resp.headers["content-type"]
    assert "Bad request" in resp.text


def test_invalid_invitation_token_renders_friendly_404(db: Session) -> None:
    def override_get_db() -> Iterator[Session]:
        yield db

    def override_get_current_user() -> AuthenticatedUser:
        return AuthenticatedUser(
            principal_id="rae-oid",
            email="rae@example.edu",
            name="Rae",
            provider="aad",
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        resp = TestClient(app).get("/me/invite/bogus-token")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404
    assert "This invitation link is invalid or has expired." in resp.text
