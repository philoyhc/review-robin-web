"""Coverage for the Activate session super-button (PR 3 of
spec/workflow_card.md). The route fuses Generate + Validate +
Activate into a single click; this file pins the four failure
paths from appendix A.6 + the audit-event story per case + the
right-column failure banner that surfaces the diagnostic.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEvent,
    Instrument,
    ReviewSession,
    SessionRuleSet,
)
from app.services import session_lifecycle as lifecycle


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": f"WSB-{code}", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed_pair_plus_pinned(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    review_session = _make_session(client, db, code=code)
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
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
    instrument = (
        db.query(Instrument)
        .filter(Instrument.session_id == review_session.id)
        .first()
    )
    instrument.rule_set_id = rule_set.id
    db.flush()
    db.commit()
    db.refresh(review_session)
    return review_session


def _audit_event_types(db: Session, session_id: int) -> list[str]:
    rows = list(
        db.execute(
            select(AuditEvent.event_type)
            .where(AuditEvent.session_id == session_id)
            .order_by(AuditEvent.id)
        ).scalars()
    )
    return rows


# --------------------------------------------------------------------------- #
# Happy path: end-to-end Generate + Validate + Activate from State 1A.
# --------------------------------------------------------------------------- #


def test_super_button_end_to_end_from_state_1a_lands_session_in_ready(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair_plus_pinned(client, db, code="happy-1a")

    response = client.post(
        f"/operator/sessions/{review_session.id}/workflow/activate",
        data={"return_to": "assignments"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    # Lands on Assignments per return_to=assignments.
    assert response.headers["location"] == (
        f"/operator/sessions/{review_session.id}/assignments"
    )

    db.refresh(review_session)
    assert lifecycle.is_ready(review_session)

    # Audit log carries the four expected events for a clean run.
    types = _audit_event_types(db, review_session.id)
    assert "session.workflow_run_started" in types
    assert "assignments.generated" in types
    assert "session.validated" in types
    assert "session.activated" in types
    assert "session.workflow_run_failed" not in types


def test_super_button_redirects_to_session_home_without_return_to(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair_plus_pinned(client, db, code="happy-home")

    response = client.post(
        f"/operator/sessions/{review_session.id}/workflow/activate",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/operator/sessions/{review_session.id}"
    )


# --------------------------------------------------------------------------- #
# Failure-mode A.2: Validate finds errors → State 3.
# --------------------------------------------------------------------------- #


def test_super_button_validate_failure_lands_in_state_3_and_audits(
    client: TestClient, db: Session
) -> None:
    """Empty rosters → Generate produces zero pairs → Validate
    surfaces errors → super-button stays in draft and 303s with
    super_status=failed&super_step=validate. Card resolves to State 3
    (with the freshly-generated rows still in place; here zero rows
    since rosters are empty)."""
    # Seed a session with a pinned rule but NO rosters — Generate
    # produces zero pairs which Validate reports as an error.
    review_session = _make_session(client, db, code="fail-validate")
    rule_set = (
        db.query(SessionRuleSet)
        .filter(
            SessionRuleSet.session_id == review_session.id,
            SessionRuleSet.name == "Full Matrix",
        )
        .first()
    )
    instrument = (
        db.query(Instrument)
        .filter(Instrument.session_id == review_session.id)
        .first()
    )
    instrument.rule_set_id = rule_set.id
    db.flush()
    db.commit()
    db.refresh(review_session)

    response = client.post(
        f"/operator/sessions/{review_session.id}/workflow/activate",
        data={"return_to": "assignments"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith(
        f"/operator/sessions/{review_session.id}/assignments?"
    )
    assert "super_status=failed" in location
    assert "super_step=validate" in location

    db.refresh(review_session)
    assert lifecycle.is_draft(review_session)

    types = _audit_event_types(db, review_session.id)
    assert "session.workflow_run_started" in types
    assert "session.workflow_run_failed" in types
    assert "session.validated" not in types
    assert "session.activated" not in types


# --------------------------------------------------------------------------- #
# Pre-flight gates.
# --------------------------------------------------------------------------- #


def test_super_button_redirects_with_failure_when_session_already_ready(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair_plus_pinned(client, db, code="precondition-ready")
    # First click: lands ready.
    client.post(
        f"/operator/sessions/{review_session.id}/workflow/activate",
        follow_redirects=False,
    )
    db.refresh(review_session)
    assert lifecycle.is_ready(review_session)

    # Second click: route refuses with super_status=failed +
    # super_step=precondition.
    response = client.post(
        f"/operator/sessions/{review_session.id}/workflow/activate",
        data={"return_to": "assignments"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert "super_status=failed" in location
    assert "super_step=precondition" in location


# --------------------------------------------------------------------------- #
# Right-column failure banner.
# --------------------------------------------------------------------------- #


def test_super_failure_banner_renders_in_right_column(
    client: TestClient, db: Session
) -> None:
    """When the Assignments page is hit with the super_status=failed
    query params, the Workflow card's right-column aside renders a
    .banner.banner-error block above whatever per-state content
    would otherwise appear."""
    review_session = _seed_pair_plus_pinned(client, db, code="banner")
    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
        f"?super_status=failed&super_step=validate"
        f"&super_error=Validation+reported+1+error."
    ).text
    assert 'id="next-action-super-failure-banner"' in body
    assert "Activate session failed" in body
    assert "Validate setup" in body
    assert "Validation reported 1 error." in body
