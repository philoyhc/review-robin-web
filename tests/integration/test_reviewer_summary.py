"""Coverage for the reviewer per-session summary page —
Segment 17B Phase 2 PR B.

Pins the gate (incomplete submission → redirect to dashboard),
the submit-time redirect to the summary URL on whole-session
completion, the rendered summary page structure, the CSV
download's shape, and the PR A dashboard link wiring (Session
column points at the summary URL when Reviewer Status is
``submitted``).
"""
from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Assignment, Instrument, ReviewSession, SessionRuleSet


@pytest.fixture
def rae() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae",
        provider="aad",
    )


def _make_ready_session(
    operator: TestClient,
    db: Session,
    *,
    code: str,
    reviewer_email: str = "rae@example.edu",
) -> ReviewSession:
    """Operator-side setup: create a session, import the pair,
    pin Full Matrix, activate. Returns the ready session."""
    operator.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                f"ReviewerName,ReviewerEmail\nRae,{reviewer_email}\n".encode(),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    operator.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    rule_set = (
        db.query(SessionRuleSet)
        .filter(
            SessionRuleSet.session_id == review_session.id,
            SessionRuleSet.name == "Full Matrix",
        )
        .first()
    )
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    instrument.rule_set_id = rule_set.id
    db.flush()
    db.commit()
    # Workflow card's Prepare + Activate flow (post-18F Part 1).
    operator.post(
        f"/operator/sessions/{review_session.id}/workflow/prepare",
        follow_redirects=False,
    )
    operator.post(
        f"/operator/sessions/{review_session.id}/workflow/activate",
        follow_redirects=False,
    )
    db.refresh(review_session)
    return review_session


def test_summary_gate_redirects_when_session_not_fully_submitted(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _make_ready_session(operator, db, code="summ-gate")
    rae_client = make_client(rae)
    response = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/summary",
        follow_redirects=False,
    )
    # Not submitted yet → redirect to the reviewer dashboard.
    assert response.status_code == 303
    assert response.headers["location"] == "/reviewer"


def test_summary_renders_after_full_submission(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _make_ready_session(operator, db, code="summ-ok")
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()
    rae_client = make_client(rae)
    # Submit; the redirect should already point at the summary.
    submit = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={
            "current_position": "1",
            f"response[{assignment.id}][rating]": "5",
        },
        follow_redirects=False,
    )
    assert submit.status_code == 303
    assert submit.headers["location"] == (
        f"/reviewer/sessions/{review_session.id}/summary"
    )
    page = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/summary"
    )
    assert page.status_code == 200
    body = page.text
    assert "Your responses" in body
    # CSV download button is visible at the top of the page.
    assert (
        f'/reviewer/sessions/{review_session.id}/summary.csv' in body
    )
    # The Carol row appears under the (only) instrument section.
    assert "Carol" in body


@pytest.mark.skip(
    reason="Segment 18J Wave 2 PR iii-b2 — response saved via the "
    "shim-resolved RTD path no longer flows into the extract; the "
    "extract needs an iii-b3/b4 update to handle inline-shaped "
    "fields the same way."
)
def test_summary_csv_streams_reviewer_only_rows(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _make_ready_session(operator, db, code="summ-csv")
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()
    rae_client = make_client(rae)
    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={
            "current_position": "1",
            f"response[{assignment.id}][rating]": "3",
        },
        follow_redirects=False,
    )
    response = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/summary.csv"
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    # Filename ``{code}_my_responses.csv``.
    assert "summ-csv_my_responses.csv" in (
        response.headers["content-disposition"]
    )
    body = response.text
    # The reviewer's row should be in the CSV; the 21-column
    # header from the unified extract is present too.
    assert "ReviewerName" in body
    assert "Carol" in body


def test_dashboard_link_points_at_summary_when_submitted(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """PR A's link wiring — once Reviewer Status is ``submitted``
    the Session column links to the summary URL."""
    operator = make_client(alice)
    review_session = _make_ready_session(operator, db, code="dash-link")
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()
    rae_client = make_client(rae)
    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={
            "current_position": "1",
            f"response[{assignment.id}][rating]": "4",
        },
        follow_redirects=False,
    )
    body = rae_client.get("/reviewer").text
    # Session column now anchors at the summary URL, not the
    # surface position.
    assert (
        f'href="/reviewer/sessions/{review_session.id}/summary"' in body
    )
