"""Unit tests for the return-to-origin helper (Segment 11D, PR A)."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.web.return_to import DEFAULT_TARGET, ReturnTarget, resolve_return_to


def _seed_session(db: Session, *, name: str = "Spring 2026") -> ReviewSession:
    user = User(email="op@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    session = ReviewSession(name=name, code="rrw-test", created_by_user_id=user.id)
    db.add(session)
    db.flush()
    return session


def test_none_falls_back_to_default(db: Session) -> None:
    assert resolve_return_to(None, db) == DEFAULT_TARGET


def test_empty_string_falls_back_to_default(db: Session) -> None:
    assert resolve_return_to("", db) == DEFAULT_TARGET


def test_operator_sessions_root_resolves_to_sessions_label(db: Session) -> None:
    target = resolve_return_to("/operator/sessions", db)
    assert target.url == "/operator/sessions"
    assert target.label == "Sessions"


def test_operator_session_detail_resolves_to_session_name(db: Session) -> None:
    session = _seed_session(db, name="My Review")
    target = resolve_return_to(f"/operator/sessions/{session.id}", db)
    assert target.url == f"/operator/sessions/{session.id}"
    assert target.label == "My Review"


def test_operator_session_tab_resolves_to_session_name(db: Session) -> None:
    session = _seed_session(db, name="Tabbed Session")
    target = resolve_return_to(f"/operator/sessions/{session.id}/instruments", db)
    assert target.url == f"/operator/sessions/{session.id}/instruments"
    assert target.label == "Tabbed Session"


def test_operator_session_with_unknown_id_falls_back(db: Session) -> None:
    assert resolve_return_to("/operator/sessions/999999", db) == DEFAULT_TARGET


def test_reviewer_root_resolves_to_your_reviews(db: Session) -> None:
    target = resolve_return_to("/me", db)
    assert target.url == "/me"
    assert target.label == "your reviews"


def test_reviewer_session_resolves_to_session_name(db: Session) -> None:
    session = _seed_session(db, name="Reviewer Session")
    target = resolve_return_to(f"/me/sessions/{session.id}", db)
    assert target.url == f"/me/sessions/{session.id}"
    assert target.label == "Reviewer Session"


def test_query_string_and_fragment_are_stripped(db: Session) -> None:
    target = resolve_return_to("/operator/sessions?validated=1#x", db)
    assert target.url == "/operator/sessions"
    assert target.label == "Sessions"


@pytest.mark.parametrize(
    "raw",
    [
        "https://evil.example.com/",
        "//evil.example.com/path",
        "/operator/../etc/passwd",
        "/operator/sessions/abc",  # non-numeric session id
        "/operator/instruments",  # not in the allowlist
        "javascript:alert(1)",
        # ``$`` matched before a trailing newline, which a cookie then
        # refused with a 500.
        "/operator/sessions\n",
        "/operator/sessions%0A",
        "/me\n",
        "/operator/settings\n",
    ],
)
def test_paths_outside_allowlist_fall_back_to_default(
    db: Session, raw: str
) -> None:
    assert resolve_return_to(raw, db) == DEFAULT_TARGET


def test_operator_session_page_at_any_depth_resolves_to_session_name(
    db: Session,
) -> None:
    session = _seed_session(db, name="Deep Session")
    path = f"/operator/sessions/{session.id}/instruments/7"
    target = resolve_return_to(path, db)
    assert target.url == path
    assert target.label == "Deep Session"


@pytest.mark.parametrize(
    ("path", "label"),
    [
        ("/operator/sessions/archived", "Archived sessions"),
        ("/operator/sessions/new", "New session"),
        ("/operator/settings", "Settings"),
        ("/operator/settings/", "Settings"),
    ],
)
def test_operator_pages_outside_a_session_resolve_to_their_title(
    db: Session, path: str, label: str
) -> None:
    assert resolve_return_to(path, db) == ReturnTarget(url=path, label=label)


def _fullwidth(digits: str) -> str:
    return "".join(chr(0xFF10 + int(d)) for d in digits)


@pytest.mark.parametrize(
    "shape",
    [
        "/operator/sessions/{id}/a.b",  # outside the segment alphabet
        "/operator/sessions/{id}\n",  # ``$`` matched before a newline
        "/operator/sessions/{id}/instruments\n",
        "/operator/sessions/{fw}",  # ``\d`` matched any Unicode digit
        "/operator/sessions/{fw}/assignments",
        "/me/sessions/{fw}",
        # A page a POST rendered: the chrome passes the POST's path, and
        # a GET there would 405.
        "/operator/sessions/{id}/reviewers/import",
        "/operator/sessions/{id}/no/such/page",
    ],
)
def test_an_existing_session_still_falls_back_on_a_bad_path(
    db: Session, shape: str
) -> None:
    session = _seed_session(db)
    raw = shape.format(id=session.id, fw=_fullwidth(str(session.id)))
    assert resolve_return_to(raw, db) == DEFAULT_TARGET
