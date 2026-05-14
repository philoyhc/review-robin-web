"""Unit-style coverage for ``views.build_workflow_card_context``,
the shared context builder introduced in PR 5 of
``spec/workflow_card.md`` A.8. The builder is the canonical entry
point every Operations-row page route will call once the Workflow
card spreads beyond Assignments. Pinning its output shape here
keeps the per-page wiring drop-in for PRs 6+.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, ReviewSession, SessionRuleSet
from app.web import views


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": f"WCB-{code}", "code": code, "description": "d"},
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


_EXPECTED_KEYS = {
    "is_draft",
    "is_validated",
    "is_ready",
    "is_setup_empty",
    "is_pre_generate",
    "invitations_generated",
    "invitations_sent",
    "validation_summary",
    "validation_issues_by_severity",
    "setup_checklist",
    "super_failure",
    "next_action_return_to",
}


def test_builder_returns_expected_key_set(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="builder-keys")
    ctx = views.build_workflow_card_context(
        db, review_session, return_to="assignments"
    )
    assert set(ctx.keys()) == _EXPECTED_KEYS


def test_builder_state_1_setup_empty_carries_checklist_falses(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="builder-state1")
    ctx = views.build_workflow_card_context(
        db, review_session, return_to="assignments"
    )
    assert ctx["is_draft"] is True
    assert ctx["is_setup_empty"] is True
    assert ctx["is_pre_generate"] is False
    assert ctx["setup_checklist"] == {
        "reviewers_ok": False,
        "reviewees_ok": False,
        "instruments_pinned_ok": False,
    }
    assert ctx["validation_summary"] is None
    assert ctx["super_failure"] is None
    assert ctx["next_action_return_to"] == "assignments"


def test_builder_state_1a_flips_when_rosters_and_rule_pinned(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair_plus_pinned(
        client, db, code="builder-state1a"
    )
    ctx = views.build_workflow_card_context(
        db, review_session, return_to="assignments"
    )
    assert ctx["is_setup_empty"] is False
    assert ctx["is_pre_generate"] is True  # no assignments rows yet
    assert ctx["setup_checklist"] == {
        "reviewers_ok": True,
        "reviewees_ok": True,
        "instruments_pinned_ok": True,
    }


def test_builder_validated_just_ran_promotes_draft_to_validated(
    client: TestClient, db: Session
) -> None:
    """When ``validated_just_ran=True`` and the readiness report is
    clean, the builder calls ``lifecycle.mark_validated`` inline —
    same behaviour the old ``?validated=1`` handler had."""
    from app.services import session_lifecycle as lifecycle
    from app.db.models import User

    review_session = _seed_pair_plus_pinned(
        client, db, code="builder-promote"
    )
    # Generate so validation reports zero errors.
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/generate",
        follow_redirects=False,
    )
    db.refresh(review_session)
    assert lifecycle.is_draft(review_session)

    operator = db.execute(select(User).limit(1)).scalar_one()
    ctx = views.build_workflow_card_context(
        db,
        review_session,
        return_to="assignments",
        validated_just_ran=True,
        user=operator,
    )
    db.refresh(review_session)
    assert lifecycle.is_validated(review_session)
    assert ctx["is_validated"] is True
    assert ctx["validation_summary"] is not None
    assert ctx["validation_summary"]["can_activate"] is True


def test_parse_super_failure_decodes_query_param_triple() -> None:
    assert views.parse_super_failure(None, None, None) is None
    assert (
        views.parse_super_failure("anything-else", "step", "err") is None
    )
    assert views.parse_super_failure("failed", None, None) == {
        "step": "unknown",
        "error": "",
    }
    assert views.parse_super_failure(
        "failed", "validate", "Validation failed."
    ) == {
        "step": "validate",
        "error": "Validation failed.",
    }
