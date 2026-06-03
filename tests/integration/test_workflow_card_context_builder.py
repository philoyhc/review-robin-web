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
    # ``session_rule_sets`` row (auto-seed retired). The helper
    # also marks every instrument's Band 1 link pills as touched
    # so the Wave 5 "Not set" pill safety gate sees the bypass
    # as fully configured.
    from ._full_matrix import pin_full_matrix_on_all_instruments
    pin_full_matrix_on_all_instruments(db, review_session.id)
    db.refresh(review_session)
    return review_session


_EXPECTED_KEYS = {
    "is_draft",
    "is_validated",
    "is_ready",
    "is_expired",
    "is_archived",
    "revert_visible",
    "prepare_visible",
    "create_invites_visible",
    "send_invites_visible",
    "activate_visible",
    "send_reminders_visible",
    "close_visible",
    "release_responses_visible",
    "stop_release_visible",
    "archive_visible",
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
    # Wave 5 follow-up — the "Not set" pill safety gate forces
    # every Band 1 link to be deliberately clicked before
    # ``instruments_configured_ok`` flips True. A bare session's
    # default instrument has Rating + Comments visible response
    # fields out of the box but no Band 1 link pills touched yet,
    # so it surfaces as not configured.
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


def test_archive_visible_gates_on_expired_only(
    client: TestClient, db: Session
) -> None:
    """Archive button surfaces only when the session is
    ``expired`` — i.e. the operator has run Close session. The
    underlying ``lifecycle.archive_session`` service stays
    permissive, but the Workflow card chrome doesn't surface
    Archive from earlier states (avoids piling buttons on
    pre-close states + matches the close-then-file-away
    sequence)."""
    sess = _make_session(client, db, code="archive-gate")
    ctx = views.build_workflow_card_context(
        db, sess, return_to="home"
    )
    # draft: archive button hidden.
    assert ctx["archive_visible"] is False

    for state in ("validated", "ready"):
        sess.status = state
        db.commit()
        ctx = views.build_workflow_card_context(
            db, sess, return_to="home"
        )
        assert ctx["archive_visible"] is False, (
            f"archive button should not surface in {state!r}"
        )

    sess.status = "expired"
    db.commit()
    ctx = views.build_workflow_card_context(
        db, sess, return_to="home"
    )
    assert ctx["archive_visible"] is True

    sess.status = "archived"
    db.commit()
    ctx = views.build_workflow_card_context(
        db, sess, return_to="home"
    )
    assert ctx["archive_visible"] is False


# ── Single-row visible-button gating per state ──────────────────────────


_VISIBLE_KEYS = (
    "revert_visible",
    "prepare_visible",
    "create_invites_visible",
    "send_invites_visible",
    "activate_visible",
    "send_reminders_visible",
    "close_visible",
    "release_responses_visible",
    "stop_release_visible",
    "archive_visible",
)


def _visible_set(ctx: dict) -> set[str]:
    return {key for key in _VISIBLE_KEYS if ctx.get(key)}


def test_draft_empty_state_surfaces_nothing(
    client: TestClient, db: Session
) -> None:
    sess = _make_session(client, db, code="vis-state-1")
    ctx = views.build_workflow_card_context(
        db, sess, return_to="home"
    )
    assert _visible_set(ctx) == set()


def test_validated_no_invites_surfaces_revert_prepare_create_activate(
    client: TestClient, db: Session
) -> None:
    sess = _seed_pair_plus_pinned(client, db, code="vis-state-4")
    sess.status = "validated"
    db.commit()
    ctx = views.build_workflow_card_context(
        db, sess, return_to="home"
    )
    visible = _visible_set(ctx)
    assert visible == {
        "revert_visible",
        "prepare_visible",
        "create_invites_visible",
        "activate_visible",
    }
    assert len(visible) <= 4


def test_ready_no_invites_surfaces_revert_create_close_release(
    client: TestClient, db: Session
) -> None:
    sess = _seed_pair_plus_pinned(client, db, code="vis-state-7")
    sess.status = "ready"
    db.commit()
    ctx = views.build_workflow_card_context(
        db, sess, return_to="home"
    )
    visible = _visible_set(ctx)
    assert visible == {
        "revert_visible",
        "create_invites_visible",
        "close_visible",
        "release_responses_visible",
    }
    assert len(visible) <= 4


def test_expired_surfaces_revert_release_archive(
    client: TestClient, db: Session
) -> None:
    sess = _seed_pair_plus_pinned(client, db, code="vis-state-10")
    sess.status = "expired"
    db.commit()
    ctx = views.build_workflow_card_context(
        db, sess, return_to="home"
    )
    visible = _visible_set(ctx)
    assert visible == {
        "revert_visible",
        "release_responses_visible",
        "archive_visible",
    }


def test_archived_surfaces_nothing(
    client: TestClient, db: Session
) -> None:
    sess = _seed_pair_plus_pinned(client, db, code="vis-state-archived")
    sess.status = "archived"
    db.commit()
    ctx = views.build_workflow_card_context(
        db, sess, return_to="home"
    )
    assert _visible_set(ctx) == set()


def test_every_state_keeps_visible_count_within_four(
    client: TestClient, db: Session
) -> None:
    """Sanity check for the 25%-per-button single-row layout — every
    lifecycle state caps the visible-button count at 4."""
    sess = _seed_pair_plus_pinned(client, db, code="vis-cap")
    for state in ("draft", "validated", "ready", "expired", "archived"):
        sess.status = state
        db.commit()
        ctx = views.build_workflow_card_context(
            db, sess, return_to="home"
        )
        visible = _visible_set(ctx)
        assert len(visible) <= 4, (
            f"state {state!r} surfaces {len(visible)} buttons: {visible}"
        )


def test_stop_release_visible_gates_on_post_activation(
    client: TestClient, db: Session
) -> None:
    """A backdated ``responses_release_at`` on a draft / validated
    session opens the release window per
    ``is_response_release_window_open``, but Stop must stay hidden
    in pre-activation states. Otherwise validated + no invites
    would surface five visible buttons (Revert · Prepare ·
    Create invites · Activate · Stop) and blow the ≤4 grid
    contract."""
    from datetime import datetime, timedelta, timezone

    sess = _seed_pair_plus_pinned(client, db, code="stop-pre-activation")
    sess.responses_release_at = datetime.now(timezone.utc) - timedelta(
        hours=1
    )

    for state in ("draft", "validated"):
        sess.status = state
        db.commit()
        ctx = views.build_workflow_card_context(
            db, sess, return_to="home"
        )
        assert ctx["stop_release_visible"] is False, (
            f"Stop should stay hidden in pre-activation state "
            f"{state!r} even with a backdated release_at"
        )
        assert len(_visible_set(ctx)) <= 4

    # Once activated, Stop surfaces because the window is open.
    sess.status = "ready"
    db.commit()
    ctx = views.build_workflow_card_context(
        db, sess, return_to="home"
    )
    assert ctx["stop_release_visible"] is True
    assert ctx["release_responses_visible"] is False
