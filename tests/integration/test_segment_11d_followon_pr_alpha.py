"""PR α — Reviewer-surface URL routing + dashboard rewiring.

Per `guide/archive/segment_11D_v2_sweep_non_session.md` "Follow-on: Reviewer
surface — multi-instrument rewrite" → PR α. The new URL pattern
(`/reviewer/sessions/{id}/{N}`) lands without visible layout change.

Post-Segment-18L the URL slot is the operator-defined page number
rather than the instrument position; bare URL still 303s to /1.
Submit and Clear are session-wide and redirect to the bare session
URL (no per-page round-trip).
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Assignment, Reviewer, ReviewSession
from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


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
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator_client, review_session.id)
    operator_client.get(f"/operator/sessions/{review_session.id}/assignments?validated=1")
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


# ── Position route ─────────────────────────────────────────────────────


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


# ── Submit redirect ────────────────────────────────────────────────────


def test_submit_redirect_lands_on_summary_when_session_complete(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """A successful Submit that completes the session 303s to the
    per-session summary page (17B Phase 2 PR B)."""
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

    # Single-assignment session: a successful Submit completes the
    # session, so 17B Phase 2 PR B redirects to the per-session summary
    # page. Post-Segment-18L the submit handler no longer reads a
    # ``current_position`` hint — the redirect target is the bare
    # session URL (which 303s on to /1) or /summary when complete.
    response = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={
            f"response[{assignment.id}][rating]": "4",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert (
        response.headers["location"]
        == f"/reviewer/sessions/{review_session.id}/summary"
    )


# ── Clear redirect → bare URL ──────────────────────────────────────────


def test_clear_redirect_goes_to_bare_url(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Post-Segment-18L-PR-1c: Clear no longer reads any position
    hint; it 303s to the bare session URL, which itself redirects
    to page 1."""
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
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert (
        response.headers["location"]
        == f"/reviewer/sessions/{review_session.id}"
    )
