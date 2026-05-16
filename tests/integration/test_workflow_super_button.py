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
    Assignment,
    AuditEvent,
    Instrument,
    InstrumentResponseField,
    Response,
    ResponseTypeDefinition,
    Reviewee,
    Reviewer,
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


def _attach_response(db: Session, *, assignment: Assignment, key: str) -> int:
    """Attach one ``Response`` to ``assignment`` and return its id.

    Builds the response-type definition + instrument field the
    ``Response`` row needs; ``key`` makes both unique per session /
    instrument."""
    rtd = ResponseTypeDefinition(
        session_id=assignment.session_id,
        response_type=f"RT-{key}",
        data_type="number",
    )
    db.add(rtd)
    db.flush()
    field = InstrumentResponseField(
        instrument_id=assignment.instrument_id,
        field_key=key,
        label="Score",
        response_type_id=rtd.id,
    )
    db.add(field)
    db.flush()
    response = Response(
        assignment_id=assignment.id,
        response_field_id=field.id,
        value="5",
    )
    db.add(response)
    db.flush()
    db.commit()
    return response.id


def _seed_reverted_session_with_response(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    """Activate a seeded session, record one response, then revert it
    to draft. The roster is unchanged, so re-activating reconciles
    with no response loss."""
    review_session = _seed_pair_plus_pinned(client, db, code=code)
    client.post(
        f"/operator/sessions/{review_session.id}/workflow/activate",
        follow_redirects=False,
    )
    db.refresh(review_session)
    assert lifecycle.is_ready(review_session)

    assignment = (
        db.execute(
            select(Assignment).where(
                Assignment.session_id == review_session.id
            )
        )
        .scalars()
        .first()
    )
    _attach_response(db, assignment=assignment, key="superbtn")

    # Revert ready → draft; responses are preserved across the flip.
    client.post(
        f"/operator/sessions/{review_session.id}/revert",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    db.refresh(review_session)
    assert lifecycle.is_draft(review_session)
    return review_session


def _seed_session_with_droppable_response(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    """Seed a draft session where re-activation will drop a pair that
    holds a response.

    Reviewer ``Sam`` and reviewee ``Sam`` share an email, so Full
    Matrix pairs them (a self-review). After activating, recording a
    response on that self-pair, and reverting to draft, the rule set
    is flipped to exclude self-reviews — so the next reconcile drops
    the self-pair and deletes its response.

    Reviewee ``Dan`` is along for the ride so that, once the
    self-pair is gone, every reviewer and reviewee still has at least
    one assignment — keeping validation clean either side of the
    reconcile."""
    review_session = _make_session(client, db, code=code)
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\n"
                b"Sam,sam@example.edu\nTom,tom@example.edu\n",
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
                b"RevieweeName,RevieweeEmail\n"
                b"Sam,sam@example.edu\nDan,dan@example.edu\n",
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

    client.post(
        f"/operator/sessions/{review_session.id}/workflow/activate",
        follow_redirects=False,
    )
    db.refresh(review_session)
    assert lifecycle.is_ready(review_session)

    self_pair = (
        db.execute(
            select(Assignment)
            .join(Reviewer, Reviewer.id == Assignment.reviewer_id)
            .join(Reviewee, Reviewee.id == Assignment.reviewee_id)
            .where(
                Assignment.session_id == review_session.id,
                Reviewer.email == "sam@example.edu",
                Reviewee.email_or_identifier == "sam@example.edu",
            )
        )
        .scalars()
        .one()
    )
    _attach_response(db, assignment=self_pair, key="selfpair")

    client.post(
        f"/operator/sessions/{review_session.id}/revert",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    db.refresh(review_session)
    assert lifecycle.is_draft(review_session)

    # Flip the rule to exclude self-reviews — the next reconcile drops
    # Sam's self-pair (and its response).
    db.refresh(rule_set)
    rule_set.exclude_self_reviews = True
    db.flush()
    db.commit()
    return review_session


def _response_count(db: Session, session_id: int) -> int:
    return len(
        list(
            db.execute(
                select(Response.id)
                .join(Assignment, Assignment.id == Response.assignment_id)
                .where(Assignment.session_id == session_id)
            ).scalars()
        )
    )


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


# --------------------------------------------------------------------------- #
# Saved-response confirmation detour.
# --------------------------------------------------------------------------- #


def test_super_button_runs_through_when_reconcile_deletes_no_responses(
    client: TestClient, db: Session
) -> None:
    """A reverted session whose roster is unchanged reconciles with no
    response loss — the super-button runs straight through with no
    confirmation detour, and the saved response survives."""
    review_session = _seed_reverted_session_with_response(
        client, db, code="no-loss"
    )
    assert _response_count(db, review_session.id) == 1

    response = client.post(
        f"/operator/sessions/{review_session.id}/workflow/activate",
        data={"return_to": "assignments"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/operator/sessions/{review_session.id}/assignments"
    )

    db.refresh(review_session)
    assert lifecycle.is_ready(review_session)
    assert _response_count(db, review_session.id) == 1


def test_super_button_detours_when_reconcile_would_delete_responses(
    client: TestClient, db: Session
) -> None:
    """When the reconcile would drop a pair that holds a response, the
    super-button 303s to ``?activate_confirm=responses`` instead of
    running."""
    review_session = _seed_session_with_droppable_response(
        client, db, code="loss-detour"
    )
    assert _response_count(db, review_session.id) == 1

    response = client.post(
        f"/operator/sessions/{review_session.id}/workflow/activate",
        data={"return_to": "assignments"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/operator/sessions/{review_session.id}"
        f"/assignments?activate_confirm=responses"
    )

    db.refresh(review_session)
    # Nothing ran — still draft, response untouched.
    assert lifecycle.is_draft(review_session)
    assert _response_count(db, review_session.id) == 1


def test_super_button_acknowledged_loss_regenerates_and_activates(
    client: TestClient, db: Session
) -> None:
    """``acknowledge_response_loss=true`` runs past the detour: the
    orphaned self-pair and its response are deleted and the session
    activates."""
    review_session = _seed_session_with_droppable_response(
        client, db, code="loss-ack"
    )
    assert _response_count(db, review_session.id) == 1

    response = client.post(
        f"/operator/sessions/{review_session.id}/workflow/activate",
        data={
            "return_to": "assignments",
            "acknowledge_response_loss": "true",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/operator/sessions/{review_session.id}/assignments"
    )

    db.refresh(review_session)
    assert lifecycle.is_ready(review_session)
    # Sam's self-pair was dropped — its response went with it.
    assert _response_count(db, review_session.id) == 0


def test_activate_confirm_banner_renders_on_host_page(
    client: TestClient, db: Session
) -> None:
    """The Workflow card renders the saved-response confirmation
    banner with the reconcile impact counts when a run would delete
    responses."""
    review_session = _seed_session_with_droppable_response(
        client, db, code="loss-banner"
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/assignments?activate_confirm=responses"
    ).text
    assert 'id="next-action-activate-confirm-banner"' in body
    # Collapse template whitespace so the multi-line banner copy can
    # be matched as a single phrase.
    normalized = " ".join(body.split())
    assert "Activating will delete 1 saved response." in normalized
    assert "drops 1 assignment pair" in normalized
    assert "Regenerate &amp; activate" in body
    assert "Cancel" in body


def test_activate_confirm_param_ignored_when_no_responses_lost(
    client: TestClient, db: Session
) -> None:
    """A stale ``?activate_confirm=responses`` renders no banner when a
    run would delete no responses — the builder dry-runs the reconcile
    and guards on its impact, not on whether responses merely exist."""
    review_session = _seed_reverted_session_with_response(
        client, db, code="no-banner"
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/assignments?activate_confirm=responses"
    ).text
    assert 'id="next-action-activate-confirm-banner"' not in body
