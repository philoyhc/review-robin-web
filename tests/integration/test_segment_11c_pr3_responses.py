"""Integration tests for Segment 11C Part 1 PR 3.

Covers the new Responses page (`/sessions/{id}/responses`), its
reviewee-detail drill-in, and the chrome / nav changes that
accompany the Monitoring retirement.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Reviewee, ReviewSession


# --------------------------------------------------------------------------- #
# Setup helpers — mirror the shape used by test_invitations.py /
# test_reminders.py so the fixtures stay readable.
# --------------------------------------------------------------------------- #


def _create_session(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _populate(
    client: TestClient,
    session_id: int,
    *,
    reviewer_emails: list[str],
    reviewee_emails: list[str],
) -> None:
    rev_csv = b"ReviewerName,ReviewerEmail\n" + b"".join(
        f"R{i},{e}\n".encode() for i, e in enumerate(reviewer_emails)
    )
    client.post(
        f"/operator/sessions/{session_id}/reviewers/import",
        files={"file": ("r.csv", rev_csv, "text/csv")},
        follow_redirects=False,
    )
    revw_csv = b"RevieweeName,RevieweeEmail\n" + b"".join(
        f"E{i},{e}\n".encode() for i, e in enumerate(reviewee_emails)
    )
    client.post(
        f"/operator/sessions/{session_id}/reviewees/import",
        files={"file": ("e.csv", revw_csv, "text/csv")},
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{session_id}/assignments/full-matrix",
        data={"exclude_self_review": ""},
        follow_redirects=False,
    )


def _activate(client: TestClient, session_id: int) -> None:
    client.get(f"/operator/sessions/{session_id}?validated=1")
    response = client.post(
        f"/operator/sessions/{session_id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text


def _ready_session(
    client: TestClient,
    db: Session,
    code: str,
    *,
    reviewer_emails: list[str],
    reviewee_emails: list[str],
) -> ReviewSession:
    session = _create_session(client, db, code)
    _populate(
        client,
        session.id,
        reviewer_emails=reviewer_emails,
        reviewee_emails=reviewee_emails,
    )
    _activate(client, session.id)
    db.refresh(session)
    return session


# --------------------------------------------------------------------------- #
# Responses page — chrome + table
# --------------------------------------------------------------------------- #


def test_responses_page_renders_table_for_assigned_reviewees(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(
        client,
        db,
        "resp-table",
        reviewer_emails=["rae@example.edu"],
        reviewee_emails=["carol@example.edu", "dave@example.edu"],
    )
    response = client.get(f"/operator/sessions/{session.id}/responses")
    assert response.status_code == 200
    body = response.text
    # Headers per the PR spec.
    for header in (
        "<th>Reviewee</th>",
        "<th>Coverage</th>",
        "<th>Reviewers</th>",
        "<th>Last response</th>",
    ):
        assert header in body
    # Both reviewees render.
    assert "carol@example.edu" in body
    assert "dave@example.edu" in body
    # Each reviewee starts with no responses.
    assert ">no responses</span>" in body
    assert "0/1" in body


def test_responses_tab_shows_in_top_nav_and_active_on_page(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(
        client,
        db,
        "resp-tab",
        reviewer_emails=["rae@example.edu"],
        reviewee_emails=["carol@example.edu"],
    )
    body = client.get(
        f"/operator/sessions/{session.id}/responses"
    ).text
    # Tab renders pointing at /responses, and is active.
    assert (
        f'href="/operator/sessions/{session.id}/responses">Responses</a>'
        in body
    )
    assert "nav-tab active" in body
    # Monitoring tab is gone.
    assert ">Monitoring</a>" not in body


def test_responses_page_reviewee_name_links_to_drill_in(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(
        client,
        db,
        "resp-link",
        reviewer_emails=["rae@example.edu"],
        reviewee_emails=["carol@example.edu"],
    )
    reviewee = db.execute(
        select(Reviewee).where(
            Reviewee.session_id == session.id,
            Reviewee.email_or_identifier == "carol@example.edu",
        )
    ).scalar_one()
    body = client.get(f"/operator/sessions/{session.id}/responses").text
    assert (
        f'href="/operator/sessions/{session.id}/responses/'
        f'{reviewee.id}/detail"' in body
    )


def test_responses_reviewee_detail_renders(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(
        client,
        db,
        "resp-detail",
        reviewer_emails=["rae@example.edu"],
        reviewee_emails=["carol@example.edu"],
    )
    reviewee = db.execute(
        select(Reviewee).where(
            Reviewee.session_id == session.id,
            Reviewee.email_or_identifier == "carol@example.edu",
        )
    ).scalar_one()
    response = client.get(
        f"/operator/sessions/{session.id}/responses/{reviewee.id}/detail"
    )
    assert response.status_code == 200
    body = response.text
    assert "carol@example.edu" in body
    assert "Coverage" in body
    # The drill-in shows the per-reviewee coverage row data.
    assert "Reviewers responded:" in body


def test_responses_reviewee_detail_404_for_other_session(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(
        client,
        db,
        "resp-404",
        reviewer_emails=["rae@example.edu"],
        reviewee_emails=["carol@example.edu"],
    )
    other_session = _ready_session(
        client,
        db,
        "resp-404-other",
        reviewer_emails=["rae@example.edu"],
        reviewee_emails=["zed@example.edu"],
    )
    other_reviewee = db.execute(
        select(Reviewee).where(
            Reviewee.session_id == other_session.id,
            Reviewee.email_or_identifier == "zed@example.edu",
        )
    ).scalar_one()
    response = client.get(
        f"/operator/sessions/{session.id}/responses/"
        f"{other_reviewee.id}/detail"
    )
    assert response.status_code == 404


def test_responses_page_bulk_remind_form_targets_invitations_endpoint(
    client: TestClient, db: Session
) -> None:
    """The Responses page's bulk reminder funnels through the same
    ``/invitations/remind-incomplete`` endpoint Manage Invitations
    uses (single-source per the segment plan)."""
    session = _ready_session(
        client,
        db,
        "resp-bulk-form",
        reviewer_emails=["rae@example.edu"],
        reviewee_emails=["carol@example.edu"],
    )
    body = client.get(f"/operator/sessions/{session.id}/responses").text
    assert (
        f'action="/operator/sessions/{session.id}/invitations/remind-incomplete"'
        in body
    )


# --------------------------------------------------------------------------- #
# Coverage classification — Complete / Adequate / At risk / No responses
# --------------------------------------------------------------------------- #


def test_per_reviewee_coverage_no_responses_with_assignments(
    client: TestClient, db: Session
) -> None:
    """A reviewee with assigned reviewers but zero submitted responses
    classifies as ``no responses``."""
    from app.services import monitoring

    session = _ready_session(
        client,
        db,
        "cov-empty",
        reviewer_emails=["rae@example.edu", "ren@example.edu"],
        reviewee_emails=["carol@example.edu"],
    )
    coverage = monitoring.per_reviewee_coverage(db, session)
    assert len(coverage) == 1
    assert coverage[0].reviewer_count == 2
    assert coverage[0].completed_count == 0
    assert coverage[0].pill_state == "no responses"