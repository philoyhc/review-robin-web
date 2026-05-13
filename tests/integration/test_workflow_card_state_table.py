"""Segment 15E PR 3 coverage for the Operations Workflow Card —
per-state next-action copy + button-enabled matrix.

Tests pin the contract for the three lifecycle states the card
renders against on the Assignments page (the PR 3 beachhead):

- ``draft`` with various readiness reports — Generate is the
  Primary; Activate / Send invitations / Send reminders / Pause
  are greyed.
- ``validated`` — Activate is the Primary; Generate stays
  available as Secondary; warnings → inline acknowledge checkbox.
- ``ready`` — Send invitations is the Primary; Send reminders +
  Pause are available; Generate is locked.

Plus a separate file (``test_assignments_generate_wraps_validation.py``)
covers the Generate-wraps-validation route logic.
"""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionRuleSet,
)
from app.schemas.assignments import AssignmentMode
from app.services import assignments as assignments_service
from app.services import session_lifecycle as lifecycle
from app.services import validation
from app.web.views import build_workflow_card_context


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": f"WF-{code}", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed_pair_plus_pinned_instrument(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    """Bare session → import 1 reviewer + 1 reviewee → pin the
    default instrument's rule_set_id to the seeded Full Matrix
    SessionRuleSet. Setup gate is clean at this point; operator's
    next click is Generate."""
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
    rule_set = db.query(SessionRuleSet).filter(
        SessionRuleSet.session_id == review_session.id
    ).first()
    instrument = db.query(Instrument).filter(
        Instrument.session_id == review_session.id
    ).first()
    instrument.rule_set_id = rule_set.id
    db.flush()
    db.commit()
    db.refresh(review_session)
    return review_session


# --------------------------------------------------------------------------- #
# View-shape state matrix
# --------------------------------------------------------------------------- #


def test_workflow_card_draft_bare_session_offers_generate(
    client: TestClient, db: Session
) -> None:
    """Bare draft → Generate is the Primary; Activate / Send /
    Pause are all greyed. Next-action line points at fixing setup
    errors (reviewers/reviewees empty)."""
    review_session = _make_session(client, db, code="wf-bare")
    ctx = build_workflow_card_context(db, review_session)
    assert ctx.generate_enabled is True
    assert ctx.generate_is_primary is True
    assert ctx.activate_enabled is False
    assert ctx.send_invitations_enabled is False
    assert ctx.send_reminders_enabled is False
    assert ctx.pause_enabled is False
    assert "setup errors" in ctx.next_action_line.lower()


def test_workflow_card_draft_setup_clean_offers_generate(
    client: TestClient, db: Session
) -> None:
    """Rosters + pinned rule but no Generate yet → Generate Primary,
    Activate stays disabled (the Generate wrap auto-promotes to
    validated, surfacing Activate on the next render)."""
    review_session = _seed_pair_plus_pinned_instrument(
        client, db, code="wf-clean-draft"
    )
    ctx = build_workflow_card_context(db, review_session)
    assert ctx.generate_enabled is True
    assert ctx.generate_is_primary is True
    assert ctx.activate_enabled is False
    assert "Generate assignments" in ctx.next_action_line


def test_workflow_card_validated_offers_activate(
    client: TestClient, db: Session
) -> None:
    """Validated session → Activate Primary; Generate stays
    available as Secondary; Pause greyed (revert-to-draft works
    only from ready)."""
    review_session = _seed_pair_plus_pinned_instrument(
        client, db, code="wf-validated"
    )
    # Generate writes rows (state stays draft — Generate calls
    # invalidate_if_validated, and PR 3 doesn't auto-promote).
    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/generate",
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.refresh(review_session)
    # Use ?validated=1 (the existing Session Home "Validate Setup"
    # button) to transition draft → validated.
    client.get(
        f"/operator/sessions/{review_session.id}?validated=1",
        follow_redirects=False,
    )
    db.refresh(review_session)
    assert review_session.status == "validated"

    ctx = build_workflow_card_context(db, review_session)
    assert ctx.activate_enabled is True
    assert ctx.activate_is_primary is True
    assert ctx.generate_enabled is True
    assert ctx.generate_is_primary is False
    assert ctx.send_invitations_enabled is False
    assert ctx.pause_enabled is False
    assert "Activate" in ctx.next_action_line


def test_workflow_card_ready_offers_send_invitations(
    client: TestClient, db: Session
) -> None:
    """Ready (activated) → Send invitations Primary; Pause +
    Send reminders Secondary; Generate locked."""
    review_session = _seed_pair_plus_pinned_instrument(
        client, db, code="wf-ready"
    )
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/generate",
        follow_redirects=False,
    )
    client.get(
        f"/operator/sessions/{review_session.id}?validated=1",
        follow_redirects=False,
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}/activate",
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.refresh(review_session)
    assert lifecycle.is_ready(review_session)

    ctx = build_workflow_card_context(db, review_session)
    assert ctx.send_invitations_enabled is True
    assert ctx.send_invitations_is_primary is True
    assert ctx.send_reminders_enabled is True
    assert ctx.pause_enabled is True
    assert ctx.generate_enabled is False
    assert ctx.activate_enabled is False
    assert "Send invitations" in ctx.next_action_line


def test_workflow_card_validated_with_warnings_carries_acknowledge_count(
    db: Session,
) -> None:
    """Build a validated session that still has at least one
    warning, then check the workflow card's acknowledge-warnings
    count flows through. Skips the HTTP path — we patch the state
    + warnings via direct DB writes for control."""
    from app.db.models import User

    user = User(email="op-wf-ack@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="WF-ack",
        code="wf-ack",
        created_by_user_id=user.id,
        status="validated",
    )
    db.add(review_session)
    db.flush()
    # Seed enough to produce at least one warning (no rosters →
    # reviewers.empty error, no_included_pairs warning, etc. The
    # state=validated alone is enough.)
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="A",
            email="a@example.edu",
        )
    )
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="C",
            email_or_identifier="c@example.edu",
        )
    )
    db.flush()
    from app.services.instruments import ensure_default_instrument

    ensure_default_instrument(db, review_session)
    rule_set = SessionRuleSet(
        session_id=review_session.id,
        name="Full Matrix",
        description="",
        combinator="ALL_OF",
        exclude_self_reviews=False,
        seed=None,
        rules_json=[],
        is_seeded=True,
    )
    db.add(rule_set)
    db.flush()
    instrument = db.query(Instrument).filter(
        Instrument.session_id == review_session.id
    ).first()
    instrument.rule_set_id = rule_set.id
    db.flush()
    db.commit()

    issues = validation.validate_session_setup(db, review_session)
    warnings = [i for i in issues if i.severity.value == "warning"]
    assert warnings, "test setup must produce at least one warning"

    ctx = build_workflow_card_context(db, review_session)
    assert ctx.activate_enabled is True
    assert ctx.acknowledge_warnings_count == len(warnings)
    assert "acknowledge" in ctx.next_action_line.lower()


def test_workflow_card_banner_query_param_drives_render(
    db: Session,
) -> None:
    """``banner_kind`` is the bridge between the Generate route's
    ``?wf=`` redirect and the partial. Pin each value's mapping."""
    from app.db.models import User

    user = User(email="op-wf-banner@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="WF-banner", code="wf-banner", created_by_user_id=user.id
    )
    db.add(review_session)
    db.commit()

    for kind, expected_class in [
        ("clean", "verdict-clean"),
        ("warnings", "verdict-warn"),
        ("errors", "verdict-error"),
        ("setup_errors", "verdict-error"),
    ]:
        ctx = build_workflow_card_context(
            db, review_session, banner_kind=kind
        )
        assert ctx.banner_kind == expected_class
        assert ctx.banner_text is not None
    # Unrecognised values surface no banner.
    ctx = build_workflow_card_context(db, review_session, banner_kind="bogus")
    assert ctx.banner_kind is None
    assert ctx.banner_text is None


# --------------------------------------------------------------------------- #
# Render assertions on the Assignments page
# --------------------------------------------------------------------------- #


def test_assignments_page_renders_workflow_card(
    client: TestClient, db: Session
) -> None:
    """Workflow card partial renders directly under the chrome on
    the Assignments page; carries the expected ``operations-workflow-card``
    id + title."""
    review_session = _make_session(client, db, code="wf-render")
    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    assert 'id="operations-workflow-card"' in body
    assert "Operations workflow" in body
    # Default no-banner render — no banner attribute.
    assert "workflow-card-banner" not in body


def test_assignments_page_renders_banner_on_wf_query(
    client: TestClient, db: Session
) -> None:
    """``?wf=warnings`` surfaces the verdict-warn banner with the
    Generate-with-warnings copy."""
    review_session = _seed_pair_plus_pinned_instrument(
        client, db, code="wf-banner-render"
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments?wf=warnings"
    ).text
    assert 'data-banner-kind="verdict-warn"' in body
    assert "warnings" in body.lower()


def test_assignments_page_renders_buttons_with_disabled_state(
    client: TestClient, db: Session
) -> None:
    """Bare draft → Activate / Send buttons render with the
    ``disabled`` attribute; Generate renders enabled."""
    review_session = _make_session(client, db, code="wf-disabled")
    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    assert (
        'data-wf-action="generate"' in body
        and 'data-wf-action="activate"' in body
    )
    # Activate button is disabled in bare draft.
    import re
    activate_match = re.search(
        r'(<[^>]*data-wf-action="activate"[^>]*>)', body
    )
    assert activate_match is not None
    assert "disabled" in activate_match.group(1)
    # Generate button is not disabled.
    generate_match = re.search(
        r'(<button[^>]*data-wf-action="generate"[^>]*>)', body
    )
    assert generate_match is not None
    assert "disabled" not in generate_match.group(1)


# --------------------------------------------------------------------------- #
# Forms wired correctly
# --------------------------------------------------------------------------- #


def test_workflow_card_generate_form_posts_to_assignments_generate(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="wf-form")
    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    assert (
        f'action="/operator/sessions/{review_session.id}/assignments/generate"'
        in body
    )
    assert 'id="workflow-card-generate-form"' in body


def test_workflow_card_pause_form_includes_confirm_token(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="wf-pause")
    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    # Pause form carries the confirm=true hidden input — the existing
    # /revert route requires it.
    assert 'id="workflow-card-pause-form"' in body
    assert 'name="confirm" value="true"' in body


# Suppress the unused-import lint that would otherwise flag
# ``Assignment`` and ``AssignmentMode`` / ``assignments_service`` /
# ``uuid`` — they're available for future state-table tests that
# need direct DB manipulation.
_ = Assignment, AssignmentMode, assignments_service, uuid
