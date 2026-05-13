"""Slice 4 coverage for ``compute_next_action_generate_state`` —
the pre-Validate Generate signal that Segment 15E will surface on
the Next Action card.

The resolver decides between three states:

- ``"hidden"`` — no nudge (post-Generate steady state, or session
  is past pre-Validate).
- ``"pin_rules"`` — operator hasn't pinned any rule yet; Segment
  15E will render a supporting link to the Instruments page.
- ``"generate"`` — at least one pinned instrument's materialised
  state diverges from its current eligible pairs; Segment 15E
  will render a Primary Generate button.

Internal-wiring slice: the button render itself ships in Segment
15E. These tests pin the data shape + state-machine logic so
nothing about the render layer can drift it.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionRuleSet,
    User,
)
from app.services import assignments as assignments_service
from app.services import session_lifecycle as lifecycle
from app.services.instruments import ensure_default_instrument
from app.web.views import compute_next_action_generate_state


def _seed(
    db: Session, *, code: str = "next-act", self_reviews_active: bool = True
) -> tuple[User, ReviewSession, Instrument, SessionRuleSet]:
    """Bare session: one reviewer, one reviewee, one default
    instrument, one ``Full Matrix`` SessionRuleSet. No rule pinned
    yet; no Assignment rows yet. Each test pulls the pieces it
    needs from this fixture and pins / generates as needed.
    """
    user = User(email="op@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="NA",
        code=code,
        created_by_user_id=user.id,
        self_reviews_active=self_reviews_active,
    )
    db.add(review_session)
    db.flush()
    db.add_all(
        [
            Reviewer(
                session_id=review_session.id,
                name="Alice",
                email="alice@example.edu",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Carol",
                email_or_identifier="carol@example.edu",
            ),
        ]
    )
    db.flush()
    instrument = ensure_default_instrument(db, review_session)
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
    db.commit()
    return user, review_session, instrument, rule_set


def test_pin_rules_state_when_no_instrument_has_rule(
    db: Session,
) -> None:
    """Zero pinned instruments → ``state="pin_rules"``. The
    ``instruments_url`` deep-link is populated so Segment 15E can
    render the supporting link without a second resolver call."""

    _user, review_session, *_ = _seed(db, code="na-pin")

    result = compute_next_action_generate_state(db, review_session)

    assert result.state == "pin_rules"
    assert result.pinned_instrument_count == 0
    assert result.instruments_url == (
        f"/operator/sessions/{review_session.id}/instruments"
    )
    assert result.generate_url == (
        f"/operator/sessions/{review_session.id}/assignments/generate"
    )


def test_generate_state_when_pinned_but_never_materialised(
    db: Session,
) -> None:
    """Pinned but ``generated_count == 0`` → ``state="generate"``.
    Catches the first-time generation case (operator just pinned
    rules and hasn't materialised yet)."""

    user, review_session, instrument, rule_set = _seed(
        db, code="na-pinned-empty"
    )
    instrument.rule_set_id = rule_set.id
    db.flush()
    db.commit()

    result = compute_next_action_generate_state(db, review_session)

    assert result.state == "generate"
    assert result.pinned_instrument_count == 1


def test_hidden_state_when_fresh_after_generation(
    db: Session,
) -> None:
    """Pinned + materialised + nothing changed since → ``hidden``.
    The Next Action card moves on to the next lifecycle step
    (Validate / Activate) without nudging Generate."""

    user, review_session, instrument, rule_set = _seed(db, code="na-fresh")
    instrument.rule_set_id = rule_set.id
    db.flush()
    db.commit()
    assignments_service.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        correlation_id="na-fresh",
    )

    result = compute_next_action_generate_state(db, review_session)

    assert result.state == "hidden"
    assert result.pinned_instrument_count == 1


def test_generate_state_when_roster_added_post_generate(
    db: Session,
) -> None:
    """Materialised pairs go stale when a new reviewer joins —
    eligible_count (engine run now) diverges from generated_count
    (last materialise). The resolver returns to ``"generate"``."""

    user, review_session, instrument, rule_set = _seed(db, code="na-stale")
    instrument.rule_set_id = rule_set.id
    db.flush()
    db.commit()
    assignments_service.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        correlation_id="na-stale-1",
    )
    # A new reviewer post-Generate bumps the eligible count for
    # Full Matrix; generated_count stays at 1.
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Bob",
            email="bob@example.edu",
        )
    )
    db.flush()
    db.commit()

    result = compute_next_action_generate_state(db, review_session)

    assert result.state == "generate"


def test_hidden_state_when_session_is_ready(db: Session) -> None:
    """Ready sessions don't surface the pre-Validate Generate
    signal — Slice 4's resolver returns ``hidden`` regardless of
    pinning / staleness state."""

    user, review_session, instrument, rule_set = _seed(db, code="na-ready")
    instrument.rule_set_id = rule_set.id
    db.flush()
    db.commit()
    assignments_service.replace_assignments(
        db, review_session=review_session, user=user, correlation_id="r1"
    )
    review_session.status = lifecycle.SessionStatus.ready.value
    db.flush()
    db.commit()

    result = compute_next_action_generate_state(db, review_session)

    assert result.state == "hidden"


def test_hidden_state_when_validated_and_fresh(db: Session) -> None:
    """Validated lifecycle is still pre-active; the resolver gates
    only on ``is_ready``. So a validated session with fresh
    materialisation reads ``hidden`` (operator has moved past
    Generate; the next-action card now offers Activate)."""

    user, review_session, instrument, rule_set = _seed(db, code="na-val")
    instrument.rule_set_id = rule_set.id
    db.flush()
    db.commit()
    assignments_service.replace_assignments(
        db, review_session=review_session, user=user, correlation_id="v1"
    )
    review_session.status = lifecycle.SessionStatus.validated.value
    db.flush()
    db.commit()

    result = compute_next_action_generate_state(db, review_session)

    assert result.state == "hidden"


def test_partial_pinning_still_nudges_generate(db: Session) -> None:
    """If at least one instrument is pinned + the per-instrument
    status block reports staleness, the resolver returns
    ``"generate"`` even when some instruments are unpinned
    alongside (the resolver doesn't gate on "every instrument is
    pinned")."""

    user, review_session, instrument, rule_set = _seed(db, code="na-mixed")
    # Pin the default instrument; add a second unpinned one.
    instrument.rule_set_id = rule_set.id
    db.add(
        Instrument(
            session_id=review_session.id, name="Peer", order=2
        )
    )
    db.flush()
    db.commit()

    result = compute_next_action_generate_state(db, review_session)

    # 1 pinned (stale, never generated) + 1 unpinned (skipped) →
    # signal is "generate". The unpinned instrument doesn't gate
    # this — operators can pin rules independently per instrument.
    assert result.state == "generate"
    assert result.pinned_instrument_count == 1
