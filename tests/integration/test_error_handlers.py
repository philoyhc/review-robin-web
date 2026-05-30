"""Segment 14A PR 2 — global error handling.

Exercises the three handlers registered by
``app.web.error_handlers.register_error_handlers``: friendly HTML
pages for ``HTTPException`` (404 / 403), unhandled exceptions
(500, traceback logged not shown), and request-validation errors
(400). Plus the invitation-specific 404 copy.
"""
from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest
from fastapi import APIRouter, HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser, get_current_user
from app.db.session import get_db
from app.main import app

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


def test_http_exception_shows_route_detail() -> None:
    resp = TestClient(app).get("/__test/err/forbidden")

    assert resp.status_code == 403
    assert "Access denied" in resp.text
    assert "You do not have access to this session" in resp.text


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
