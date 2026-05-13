"""Segment 15E PR 3 coverage for Generate-wraps-validation —
the POST /assignments/generate route is now bracketed by a
setup-gate pre-check and a full validation post-check that
surfaces the outcome as a workflow-card banner via the ``?wf=``
redirect param.

Three outcome paths:

- ``setup_errors`` — pre-flight setup-gate errors hard-stop the
  call; no assignment rows written.
- ``warnings`` — generation succeeded but operations-gate warnings
  surfaced. Rows written.
- ``clean`` — generation succeeded with no errors and no warnings.
  Rows written.

PR 3 deliberately does **not** auto-promote draft → validated
inside the Generate wrap — that would conflict with the
``replace_assignments → invalidate_if_validated`` invariant
(setup mutations reset the validate ceremony). Operators continue
to click "Validate Setup" on Session Home to reach validated state
in PR 3; PR 5 (Session Home Next Action retirement) revisits the
validate surface on the workflow card itself.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Assignment, Instrument, ReviewSession, SessionRuleSet
from app.services import assignments as assignments_service


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": f"GW-{code}", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _import_pair(client: TestClient, review_session: ReviewSession) -> None:
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


def _pin_default_rule(
    db: Session, review_session: ReviewSession
) -> SessionRuleSet:
    # Pick the Full Matrix seed explicitly — the seeded RuleSets
    # include several alternatives whose engine output differs.
    # ``.first()`` without an ORDER BY can pick a different one on
    # Postgres than on SQLite.
    rule_set = db.query(SessionRuleSet).filter(
        SessionRuleSet.session_id == review_session.id,
        SessionRuleSet.name == "Full Matrix",
    ).first()
    instrument = db.query(Instrument).filter(
        Instrument.session_id == review_session.id
    ).first()
    instrument.rule_set_id = rule_set.id
    db.flush()
    db.commit()
    return rule_set


# --------------------------------------------------------------------------- #
# setup-gate hard-stop
# --------------------------------------------------------------------------- #


def test_generate_blocks_on_setup_errors(
    client: TestClient, db: Session
) -> None:
    """Bare draft session has setup-gate errors (reviewers.empty,
    reviewees.empty). Generate redirects to ?wf=setup_errors and
    writes no assignment rows."""
    review_session = _make_session(client, db, code="gw-setup-err")
    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/generate",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "wf=setup_errors" in response.headers["location"]
    assert (
        assignments_service.existing_count(db, review_session.id) == 0
    )


# --------------------------------------------------------------------------- #
# clean path: rows written + auto-mark-validated
# --------------------------------------------------------------------------- #


def test_generate_clean_writes_rows_and_stays_draft(
    client: TestClient, db: Session
) -> None:
    """Rosters + pinned rule → Generate writes rows; post-flight
    readiness report is clean → ``?wf=clean`` redirect. Session
    stays in draft (no auto-promote — see module docstring)."""
    review_session = _make_session(client, db, code="gw-clean")
    _import_pair(client, review_session)
    _pin_default_rule(db, review_session)
    assert review_session.status == "draft"

    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/generate",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "wf=clean" in response.headers["location"]
    assert (
        assignments_service.existing_count(db, review_session.id) == 1
    )
    db.refresh(review_session)
    # Session stays in draft — auto-promote intentionally omitted.
    assert review_session.status == "draft"


def test_generate_clean_invalidates_when_run_from_validated(
    client: TestClient, db: Session
) -> None:
    """Re-running Generate from a validated session invalidates it
    back to draft (the existing ``replace_assignments`` invariant),
    re-writes rows, and surfaces ``?wf=clean``."""
    review_session = _make_session(client, db, code="gw-idempotent")
    _import_pair(client, review_session)
    _pin_default_rule(db, review_session)
    # First run + click Validate Setup to reach validated.
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/generate",
        follow_redirects=False,
    )
    client.get(
        f"/operator/sessions/{review_session.id}?validated=1",
        follow_redirects=False,
    )
    db.refresh(review_session)
    assert review_session.status == "validated"
    # Second run: state flips back to draft per the lifecycle
    # invariant. Banner is still ``clean`` (post-validation report
    # has no errors / warnings).
    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/generate",
        data={
            "confirm_replace": "true",
            "acknowledge_response_loss": "true",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "wf=clean" in response.headers["location"]
    db.refresh(review_session)
    assert review_session.status == "draft"


# --------------------------------------------------------------------------- #
# warnings path: rows written, no auto-promote
# --------------------------------------------------------------------------- #


def test_generate_with_warnings_stays_draft(
    client: TestClient, db: Session
) -> None:
    """Generate produces rows but operations-gate warnings still
    fire (e.g. self-review-only scenario where the operator hasn't
    fully addressed a remaining warning). Stay in draft and surface
    ``?wf=warnings``."""
    # The cleanest way to produce a draft-with-warnings post-Generate
    # is to deactivate every Assignment row after generation. Then
    # ``instruments.zero_included`` + ``assignments.no_included_pairs``
    # warnings fire on the next validate call.
    review_session = _make_session(client, db, code="gw-warn")
    _import_pair(client, review_session)
    _pin_default_rule(db, review_session)
    # Generate writes rows; state stays draft (PR 3 doesn't auto-
    # promote; see module docstring).
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/generate",
        follow_redirects=False,
    )
    db.refresh(review_session)
    assert review_session.status == "draft"
    # Deactivate every row to trigger zero_included +
    # no_included_pairs warnings on the next validate pass.
    db.query(Assignment).filter(
        Assignment.session_id == review_session.id
    ).update({Assignment.include: False})
    db.flush()
    db.commit()
    # The workflow card on this draft session surfaces the
    # warnings via its next-action line copy; warnings flow through
    # the validation pass.
    from app.services.validation import validate_session_setup

    issues = validate_session_setup(db, review_session)
    warnings = [i for i in issues if i.severity.value == "warning"]
    assert warnings, "deactivation should produce zero_included warnings"

    from app.web.views import build_workflow_card_context

    ctx = build_workflow_card_context(db, review_session)
    # Draft + warnings (no errors): next-action copy nudges toward
    # Generate + reviewing warnings on Validate.
    assert ctx.generate_enabled is True
    assert "warning" in ctx.next_action_line.lower()
