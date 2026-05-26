"""Coverage for the Workflow card's Prepare + Activate buttons —
Segment 18F Part 1 split. Pins the failure paths, audit events,
right-column failure banner, and reconcile-detour mechanics for
both buttons.

Filename kept from the pre-18F super-button era for git history;
the super-button itself is gone — every test below exercises one
or both of the new ``POST /workflow/prepare`` and
``POST /workflow/activate`` routes.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    AuditEvent,
    InstrumentResponseField,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from app.services import session_lifecycle as lifecycle
from ._full_matrix import pin_full_matrix_on_all_instruments


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
    # Wave 5 PR 5.2 — the auto-seeded "Full Matrix" SessionRuleSet
    # retired; lazily materialise one via the shared helper.
    pin_full_matrix_on_all_instruments(db, review_session.id)
    db.refresh(review_session)
    return review_session


def _full_activation(
    client: TestClient,
    session_id: int,
    *,
    return_to: str | None = None,
    acknowledge_response_loss: bool = False,
) -> tuple:
    """End-to-end Prepare + Activate convenience for tests that just
    want the session ``ready``. Returns the two responses."""
    data: dict[str, str] = {}
    if return_to is not None:
        data["return_to"] = return_to
    if acknowledge_response_loss:
        data["acknowledge_response_loss"] = "true"
    prepare = client.post(
        f"/operator/sessions/{session_id}/workflow/prepare",
        data=data,
        follow_redirects=False,
    )
    # Activate carries no acknowledge_response_loss form field.
    activate_data = (
        {"return_to": return_to} if return_to is not None else {}
    )
    activate = client.post(
        f"/operator/sessions/{session_id}/workflow/activate",
        data=activate_data,
        follow_redirects=False,
    )
    return prepare, activate


def _attach_response(db: Session, *, assignment: Assignment, key: str) -> int:
    """Attach one ``Response`` to ``assignment`` and return its id.

    Builds the response-type definition + instrument field the
    ``Response`` row needs; ``key`` makes both unique per session /
    instrument."""
    field = InstrumentResponseField(
        instrument_id=assignment.instrument_id,
        field_key=key,
        label="Score",
        _inline_data_type="Integer",
        _inline_response_type=f"RT-{key}",
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
    to draft. The roster is unchanged, so re-preparing reconciles
    with no response loss."""
    review_session = _seed_pair_plus_pinned(client, db, code=code)
    _full_activation(client, review_session.id)
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
    _attach_response(db, assignment=assignment, key="prepbtn")

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
    """Seed a draft session where re-preparing will drop a pair that
    holds a response — same setup as the pre-18F variant, restated
    here for clarity.

    Reviewer ``Sam`` and reviewee ``Sam`` share an email; Full
    Matrix pairs them as a self-review. After activating, recording
    a response on that self-pair, and reverting to draft, ``Sam``-
    as-a-reviewee is marked ``inactive`` — so the next reconcile
    drops the (Sam, Sam) pair and would delete its response.

    Pre-2026-05-26 this seed flipped
    ``session_rule_sets.exclude_self_reviews`` to ``True`` to
    achieve the same drop; that path is gone now that the project-
    wide policy keeps ``excludeSelfReviews=False`` everywhere
    (``spec/assignments.md`` "Self-review policy").

    Reviewee ``Dan`` is along for the ride so every reviewer /
    reviewee keeps ≥1 assignment after the drop — validation stays
    clean either side of the reconcile."""
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
    pin_full_matrix_on_all_instruments(db, review_session.id)

    _full_activation(client, review_session.id)
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

    # Add a Link 1 / 2 filter rule that excludes self-pairs
    # (``reviewee.email IS DIFFERENT FROM reviewer.email``). The
    # next reconcile drops the (Sam, Sam) pair and orphans its
    # response — exercising the response-loss detour without
    # depending on the retired ``exclude_self_reviews`` desugar
    # (project-wide policy: ``excludeSelfReviews`` is always
    # False at the engine layer — see ``spec/assignments.md``
    # "Self-review policy"). This is the recommended operator
    # path for suppressing self-reviews.
    from app.db.models import SessionRuleSet
    rule_set = db.execute(
        select(SessionRuleSet).where(
            SessionRuleSet.session_id == review_session.id
        )
    ).scalar_one()
    rule_set.rules_json = [
        {
            "id": "no-self",
            "kind": "COMPOSITE",
            "enabled": True,
            "op": "AND",
            "rules": [
                {
                    "id": "no-self-r0",
                    "kind": "MATCH",
                    "enabled": True,
                    "predicate": {
                        "field": "reviewee.email",
                        "operator": "different_from",
                        "operand": "reviewer.email",
                        "case_sensitive": False,
                    },
                }
            ],
        }
    ]
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
# Happy path: Prepare → Activate lands the session in ``ready``.
# --------------------------------------------------------------------------- #


def test_prepare_lands_session_in_validated_and_audits(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair_plus_pinned(client, db, code="happy-prep")

    response = client.post(
        f"/operator/sessions/{review_session.id}/workflow/prepare",
        data={"return_to": "assignments"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert response.headers["location"] == (
        f"/operator/sessions/{review_session.id}/assignments"
    )

    db.refresh(review_session)
    assert lifecycle.is_validated(review_session)

    types = _audit_event_types(db, review_session.id)
    assert "session.workflow_run_started" in types
    assert "assignments.generated" in types
    assert "session.validated" in types
    assert "session.workflow_run_failed" not in types


def test_activate_after_prepare_lands_session_in_ready_and_audits(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair_plus_pinned(client, db, code="happy-act")
    _full_activation(client, review_session.id, return_to="assignments")

    db.refresh(review_session)
    assert lifecycle.is_ready(review_session)

    types = _audit_event_types(db, review_session.id)
    # Two ``workflow_run_started`` events — one per button.
    assert types.count("session.workflow_run_started") == 2
    assert "assignments.generated" in types
    assert "session.validated" in types
    assert "session.activated" in types
    assert "session.workflow_run_failed" not in types


def test_prepare_redirects_to_session_home_without_return_to(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair_plus_pinned(client, db, code="happy-home-prep")
    response = client.post(
        f"/operator/sessions/{review_session.id}/workflow/prepare",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/operator/sessions/{review_session.id}"
    )


def test_activate_redirects_to_session_home_without_return_to(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair_plus_pinned(client, db, code="happy-home-act")
    client.post(
        f"/operator/sessions/{review_session.id}/workflow/prepare",
        follow_redirects=False,
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}/workflow/activate",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/operator/sessions/{review_session.id}"
    )


# --------------------------------------------------------------------------- #
# Failure: Prepare's Validate step finds errors.
# --------------------------------------------------------------------------- #


def test_prepare_validate_failure_lands_in_draft_and_audits(
    client: TestClient, db: Session
) -> None:
    """Empty rosters → Generate produces zero pairs → Validate
    surfaces errors → Prepare stays in draft and 303s with
    super_status=failed&super_button=prepare&super_step=validate."""
    review_session = _make_session(client, db, code="fail-validate")
    pin_full_matrix_on_all_instruments(db, review_session.id)
    db.refresh(review_session)

    response = client.post(
        f"/operator/sessions/{review_session.id}/workflow/prepare",
        data={"return_to": "assignments"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith(
        f"/operator/sessions/{review_session.id}/assignments?"
    )
    assert "super_status=failed" in location
    assert "super_button=prepare" in location
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


def test_activate_refuses_when_session_already_ready(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair_plus_pinned(
        client, db, code="precondition-ready"
    )
    _full_activation(client, review_session.id)
    db.refresh(review_session)
    assert lifecycle.is_ready(review_session)

    response = client.post(
        f"/operator/sessions/{review_session.id}/workflow/activate",
        data={"return_to": "assignments"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert "super_status=failed" in location
    assert "super_button=activate" in location
    assert "super_step=precondition" in location


def test_activate_refuses_when_session_not_prepared(
    client: TestClient, db: Session
) -> None:
    """Pre-flight gate — Activate runs only after Prepare has flipped
    the session to ``validated``. A draft session activates with
    super_button=activate&super_step=precondition."""
    review_session = _seed_pair_plus_pinned(
        client, db, code="precondition-draft"
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}/workflow/activate",
        data={"return_to": "assignments"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert "super_status=failed" in location
    assert "super_button=activate" in location
    assert "super_step=precondition" in location


# --------------------------------------------------------------------------- #
# Right-column failure banner.
# --------------------------------------------------------------------------- #


def test_prepare_failure_banner_renders_in_right_column(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair_plus_pinned(client, db, code="banner-prep")
    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
        f"?super_status=failed&super_button=prepare&super_step=validate"
        f"&super_error=Validation+reported+1+error."
    ).text
    assert 'id="next-action-super-failure-banner"' in body
    assert "Prepare session failed" in body
    assert "Validate setup" in body
    assert "Validation reported 1 error." in body


def test_activate_failure_banner_renders_in_right_column(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair_plus_pinned(client, db, code="banner-act")
    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
        f"?super_status=failed&super_button=activate&super_step=activate"
        f"&super_error=Activate+raised."
    ).text
    assert 'id="next-action-super-failure-banner"' in body
    assert "Activate session failed" in body
    assert "Activate raised." in body


# --------------------------------------------------------------------------- #
# Saved-response confirmation detour — now on Prepare (18F Part 1).
# --------------------------------------------------------------------------- #


def test_prepare_runs_through_when_reconcile_deletes_no_responses(
    client: TestClient, db: Session
) -> None:
    """A reverted session whose roster is unchanged reconciles with no
    response loss — Prepare runs straight through with no
    confirmation detour, and the saved response survives."""
    review_session = _seed_reverted_session_with_response(
        client, db, code="no-loss"
    )
    assert _response_count(db, review_session.id) == 1

    response = client.post(
        f"/operator/sessions/{review_session.id}/workflow/prepare",
        data={"return_to": "assignments"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/operator/sessions/{review_session.id}/assignments"
    )

    db.refresh(review_session)
    assert lifecycle.is_validated(review_session)
    assert _response_count(db, review_session.id) == 1


def test_prepare_detours_when_reconcile_would_delete_responses(
    client: TestClient, db: Session
) -> None:
    """When the reconcile would drop a pair that holds a response,
    Prepare 303s to ``?prepare_confirm=responses`` instead of running."""
    review_session = _seed_session_with_droppable_response(
        client, db, code="loss-detour"
    )
    assert _response_count(db, review_session.id) == 1

    response = client.post(
        f"/operator/sessions/{review_session.id}/workflow/prepare",
        data={"return_to": "assignments"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/operator/sessions/{review_session.id}"
        f"/assignments?prepare_confirm=responses"
    )

    db.refresh(review_session)
    assert lifecycle.is_draft(review_session)
    assert _response_count(db, review_session.id) == 1


def test_prepare_acknowledged_loss_regenerates_and_validates(
    client: TestClient, db: Session
) -> None:
    """``acknowledge_response_loss=true`` runs past the detour: the
    orphaned self-pair and its response are deleted and the session
    lands in ``validated``."""
    review_session = _seed_session_with_droppable_response(
        client, db, code="loss-ack"
    )
    assert _response_count(db, review_session.id) == 1

    response = client.post(
        f"/operator/sessions/{review_session.id}/workflow/prepare",
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
    assert lifecycle.is_validated(review_session)
    assert _response_count(db, review_session.id) == 0


def test_prepare_confirm_banner_renders_on_host_page(
    client: TestClient, db: Session
) -> None:
    """The Workflow card renders the saved-response confirmation
    banner with the reconcile impact counts when a Prepare run
    would delete responses."""
    review_session = _seed_session_with_droppable_response(
        client, db, code="loss-banner"
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/assignments?prepare_confirm=responses"
    ).text
    assert 'id="next-action-prepare-confirm-banner"' in body
    normalized = " ".join(body.split())
    assert "Preparing will delete 1 saved response." in normalized
    assert "drops 1 assignment pair" in normalized
    assert "Regenerate &amp; prepare" in body
    assert "Cancel" in body


def test_prepare_confirm_param_ignored_when_no_responses_lost(
    client: TestClient, db: Session
) -> None:
    """A stale ``?prepare_confirm=responses`` renders no banner when
    a run would delete no responses — the builder dry-runs the
    reconcile and guards on its impact, not on whether responses
    merely exist."""
    review_session = _seed_reverted_session_with_response(
        client, db, code="no-banner"
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/assignments?prepare_confirm=responses"
    ).text
    assert 'id="next-action-prepare-confirm-banner"' not in body
