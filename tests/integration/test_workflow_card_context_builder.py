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

from app.db.models import ReviewSession
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
    # Wave 5 PR 5.2 — lazily materialise the Full Matrix
    # ``session_rule_sets`` row (auto-seed retired).
    from ._full_matrix import pin_full_matrix_on_all_instruments
    pin_full_matrix_on_all_instruments(db, review_session.id)
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
    "prepare_confirm",
    "scheduled_activation_caption",
    "manual_activate_cancellation",
    "auto_send_invites_caption",
    "auto_send_reminders_caption",
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
        "instruments_configured_ok": False,
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
        "instruments_configured_ok": True,
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


def test_parse_super_failure_decodes_query_params() -> None:
    """The decoder reads the four ``super_*`` query params from a
    failure-bound redirect and resolves the active button. Absent
    ``super_button``, the step name implies it (generate / validate
    → prepare; activate → activate); precondition falls back to
    prepare."""
    assert views.parse_super_failure(None, None, None) is None
    assert (
        views.parse_super_failure(
            "anything-else", "step", "err", "prepare"
        )
        is None
    )
    # No button param + unknown step → prepare fallback.
    assert views.parse_super_failure("failed", None, None) == {
        "button": "prepare",
        "step": "unknown",
        "error": "",
    }
    # Step name implies the button when ``super_button`` is absent
    # (legacy URL).
    assert views.parse_super_failure(
        "failed", "validate", "Validation failed."
    ) == {
        "button": "prepare",
        "step": "validate",
        "error": "Validation failed.",
    }
    assert views.parse_super_failure(
        "failed", "activate", "Activate raised."
    ) == {
        "button": "activate",
        "step": "activate",
        "error": "Activate raised.",
    }
    # Explicit ``super_button`` wins (e.g. precondition on Activate).
    assert views.parse_super_failure(
        "failed",
        "precondition",
        "Session is already activated.",
        "activate",
    ) == {
        "button": "activate",
        "step": "precondition",
        "error": "Session is already activated.",
    }
