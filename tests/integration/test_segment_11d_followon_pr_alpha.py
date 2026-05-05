"""PR α — Reviewer-surface URL routing + dashboard rewiring.

Per `guide/archive/segment_11D_v2_sweep_non_session.md` "Follow-on: Reviewer
surface — multi-instrument rewrite" → PR α. The new URL pattern
(`/reviewer/sessions/{id}/{instrument_position}`) lands without
visible layout change. Save, Submit, and Clear get the
`current_position` hidden form field plumbing for downstream PRs.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Assignment, Reviewer, ReviewSession


def _operator_creates_session_with_pair(
    operator_client: TestClient,
    db: Session,
    *,
    code: str,
    reviewer_email: str,
    reviewee_ident: str,
) -> ReviewSession:
    operator_client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    operator_client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                f"ReviewerName,ReviewerEmail\nR,{reviewer_email}\n".encode(),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    operator_client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                f"RevieweeName,RevieweeEmail\nCarol,{reviewee_ident}\n".encode(),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    operator_client.post(
        f"/operator/sessions/{review_session.id}/assignments/full-matrix",
        data={"exclude_self_review": ""},
        follow_redirects=False,
    )
    operator_client.get(f"/operator/sessions/{review_session.id}?validated=1")
    operator_client.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    db.refresh(review_session)
    assert review_session.status == "ready"
    return review_session


@pytest.fixture
def rae() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae Reviewer",
        provider="aad",
    )


# ── Bare URL → /1 redirect ─────────────────────────────────────────────


def test_bare_session_url_303s_to_position_1(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """`GET /reviewer/sessions/{id}` (no position) → 303 to
    `/reviewer/sessions/{id}/1`. Existing invitation links and
    bookmarks travel through this redirect."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-bare",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    response = rae_client.get(
        f"/reviewer/sessions/{review_session.id}",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert (
        response.headers["location"]
        == f"/reviewer/sessions/{review_session.id}/1"
    )


def test_bare_session_url_redirect_lands_on_surface(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The redirect chain bare → /1 → surface lands the reviewer on
    the same content they'd have seen on the bare URL pre-PR-α."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-bare-follow",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    response = rae_client.get(
        f"/reviewer/sessions/{review_session.id}",
        follow_redirects=True,
    )
    assert response.status_code == 200
    # The hidden current_position lands at 1 after the redirect.
    assert (
        '<input type="hidden" name="current_position" value="1">'
        in response.text
    )


# ── Position route + 404 on out-of-range ───────────────────────────────


def test_positioned_url_renders_surface(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-pos",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    response = rae_client.get(f"/reviewer/sessions/{review_session.id}/1")
    assert response.status_code == 200
    body = response.text
    assert (
        '<input type="hidden" name="current_position" value="1">' in body
    )
    # The form action carries the position too.
    assert (
        f'action="/reviewer/sessions/{review_session.id}/1/save"' in body
    )


def test_out_of_range_position_returns_404(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Position > instrument count, or 0 / negative, returns 404."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-oob",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    # 1-instrument session: position 1 is valid; 2 is out of range.
    assert (
        rae_client.get(f"/reviewer/sessions/{review_session.id}/2").status_code
        == 404
    )
    assert (
        rae_client.get(f"/reviewer/sessions/{review_session.id}/0").status_code
        == 404
    )
    # Negative numbers fail FastAPI's int parsing → 422.
    assert (
        rae_client.get(f"/reviewer/sessions/{review_session.id}/-1").status_code
        == 404
    )


def test_non_integer_position_returns_422(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """A non-integer path segment fails FastAPI's int validation."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-nonint",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    response = rae_client.get(f"/reviewer/sessions/{review_session.id}/abc")
    assert response.status_code == 422


# ── Dashboard rows link to /1 ──────────────────────────────────────────


def test_dashboard_rows_link_to_position_1(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-dash",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    body = rae_client.get("/reviewer").text
    assert (
        f'<a href="/reviewer/sessions/{review_session.id}/1">' in body
    )
    # The bare URL no longer appears in the dashboard.
    assert (
        f'href="/reviewer/sessions/{review_session.id}">' not in body
    )


# ── Save URL shape ─────────────────────────────────────────────────────


def test_save_post_url_carries_position(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The Save POST endpoint accepts the new positioned URL shape."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-savepos",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()
    rae_client = make_client(rae)
    response = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/1/save",
        data={f"response[{assignment.id}][rating]": "4"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert (
        response.headers["location"]
        == f"/reviewer/sessions/{review_session.id}/1"
    )


# ── Submit redirect honours `current_position` ─────────────────────────


def test_submit_redirect_honours_current_position_field(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """A successful Submit 303s to the position the reviewer was on,
    read from the form's hidden `current_position` field. Falls back
    to position 1 when the field is missing or malformed."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-submit-pos",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == review_session.id)
    ).scalar_one()
    assignment = db.execute(
        select(Assignment).where(
            Assignment.session_id == review_session.id,
            Assignment.reviewer_id == reviewer.id,
        )
    ).scalar_one()
    rae_client = make_client(rae)

    # Submit with current_position=1 (the only valid position for a
    # single-instrument session). On success, redirect uses position 1.
    response = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={
            "current_position": "1",
            f"response[{assignment.id}][rating]": "4",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert (
        response.headers["location"]
        == f"/reviewer/sessions/{review_session.id}/1"
    )


def test_submit_redirect_falls_back_when_current_position_missing(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """A Submit POST without `current_position` (e.g. a malformed form)
    redirects to position 1 rather than 500ing."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-submit-fallback",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == review_session.id)
    ).scalar_one()
    assignment = db.execute(
        select(Assignment).where(
            Assignment.session_id == review_session.id,
            Assignment.reviewer_id == reviewer.id,
        )
    ).scalar_one()
    rae_client = make_client(rae)
    response = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={f"response[{assignment.id}][rating]": "4"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert (
        response.headers["location"]
        == f"/reviewer/sessions/{review_session.id}/1"
    )


# ── Clear redirect honours `current_position` ──────────────────────────


def test_clear_redirect_honours_current_position(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Clear lands the reviewer back on the page they were on (read
    from the hidden `current_position`); falls back to /1 otherwise."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-clear-pos",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    response = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/clear",
        data={"confirm": "true", "current_position": "1"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert (
        response.headers["location"]
        == f"/reviewer/sessions/{review_session.id}/1"
    )
