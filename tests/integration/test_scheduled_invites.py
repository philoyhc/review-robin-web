"""Coverage for the Segment 18G Part 2 (PR 2A) auto-send invite trigger.

Tests run the observer end-to-end with a stub ``build_invite_url``
closure so the dispatch path runs without a live FastAPI Request.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    AuditEvent,
    Instrument,
    Invitation,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionRuleSet,
    User,
)
from app.schemas.sessions import SessionCreate
from app.services import (
    invitations as invitations_service,
    scheduled_events,
    session_lifecycle as lifecycle,
    sessions as sessions_service,
)


# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #


def _stub_build_url(token: str) -> str:
    return f"https://example.test/reviewer/invite/{token}"


def _seed_session_with_reviewers(
    db: Session,
    code: str,
    *,
    reviewer_count: int = 2,
) -> ReviewSession:
    """Create a session with N reviewers + one reviewee + a pinned
    rule. Returns the session in ``draft`` (status flip is the test's
    responsibility)."""
    op = User(email=f"op-{code}@example.edu", display_name="Op")
    db.add(op)
    db.flush()

    rs = sessions_service.create_session(
        db,
        user=op,
        payload=SessionCreate(name=code.title(), code=code, description="d"),
    )

    for i in range(reviewer_count):
        db.add(
            Reviewer(
                session_id=rs.id,
                name=f"R{i}",
                email=f"r{i}-{code}@example.edu",
            )
        )
    db.add(
        Reviewee(
            session_id=rs.id,
            name="Carol",
            email_or_identifier=f"carol-{code}@example.edu",
        )
    )
    db.flush()

    rule_set = db.execute(
        select(SessionRuleSet).where(
            SessionRuleSet.session_id == rs.id,
            SessionRuleSet.name == "Full Matrix",
        )
    ).scalar_one()
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == rs.id)
    ).scalar_one()
    instrument.rule_set_id = rule_set.id
    db.flush()
    db.commit()
    db.refresh(rs)
    return rs


def _audit_rows(
    db: Session, rs: ReviewSession, event_type: str
) -> list[AuditEvent]:
    return list(
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.session_id == rs.id)
            .where(AuditEvent.event_type == event_type)
            .order_by(AuditEvent.id)
        ).scalars()
    )


def _seed_assignments(db: Session, rs: ReviewSession) -> None:
    """Create one ``include=True`` Assignment per (reviewer, reviewee)
    + instrument so ``generate_invitations`` has candidates to enrol.
    Bypasses the rule engine — the test fixtures pre-pin Full Matrix,
    but materialise_session_rule_eligibility isn't worth running for
    this layer of tests."""
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == rs.id)
    ).scalar_one()
    reviewers = db.execute(
        select(Reviewer).where(Reviewer.session_id == rs.id)
    ).scalars().all()
    reviewees = db.execute(
        select(Reviewee).where(Reviewee.session_id == rs.id)
    ).scalars().all()
    for reviewer in reviewers:
        for reviewee in reviewees:
            db.add(
                Assignment(
                    session_id=rs.id,
                    instrument_id=instrument.id,
                    reviewer_id=reviewer.id,
                    reviewee_id=reviewee.id,
                    include=True,
                )
            )
    db.flush()
    db.commit()


def _generate_invitations(
    db: Session, rs: ReviewSession, op: User
) -> None:
    """Call the existing operator path that materialises Invitation
    rows for every assigned reviewer."""
    _seed_assignments(db, rs)
    invitations_service.generate_invitations(
        db, review_session=rs, user=op, correlation_id=None
    )


def _operator(db: Session, rs: ReviewSession) -> User:
    return db.get(User, rs.created_by_user_id)


# --------------------------------------------------------------------------- #
# No-op paths                                                                 #
# --------------------------------------------------------------------------- #


def test_no_op_when_invite_offsets_unset(db: Session) -> None:
    rs = _seed_session_with_reviewers(db, "noop-empty")
    rs.scheduled_activate_at = datetime.now(timezone.utc) + timedelta(days=1)
    db.flush()
    db.commit()

    scheduled_events.observe_scheduled_events(
        db, rs, build_invite_url=_stub_build_url
    )
    assert _audit_rows(db, rs, "session.scheduled_invites_fired") == []
    assert _audit_rows(db, rs, "session.scheduled_invites_skipped") == []


def test_no_op_when_anchor_unset(db: Session) -> None:
    """invite_offsets set but scheduled_activate_at None → inert."""
    rs = _seed_session_with_reviewers(db, "noop-anchor-null")
    rs.invite_offsets = ["-P1D"]
    db.flush()
    db.commit()

    scheduled_events.observe_scheduled_events(
        db, rs, build_invite_url=_stub_build_url
    )
    assert _audit_rows(db, rs, "session.scheduled_invites_fired") == []


def test_no_op_when_build_invite_url_missing(db: Session) -> None:
    """Without a URL builder we can't dispatch → silent no-op."""
    rs = _seed_session_with_reviewers(db, "noop-no-url")
    rs.scheduled_activate_at = datetime.now(timezone.utc) + timedelta(days=1)
    rs.invite_offsets = ["-P30D"]
    db.flush()
    db.commit()

    scheduled_events.observe_scheduled_events(db, rs)
    assert _audit_rows(db, rs, "session.scheduled_invites_fired") == []


def test_no_op_when_offset_in_future(db: Session) -> None:
    """Resolved fire moment hasn't arrived yet → no-op for that entry."""
    rs = _seed_session_with_reviewers(db, "future-offset")
    rs.scheduled_activate_at = datetime.now(timezone.utc) + timedelta(days=10)
    rs.invite_offsets = ["-P1D"]
    db.flush()
    db.commit()

    scheduled_events.observe_scheduled_events(
        db, rs, build_invite_url=_stub_build_url
    )
    assert _audit_rows(db, rs, "session.scheduled_invites_fired") == []


# --------------------------------------------------------------------------- #
# Precondition skip                                                           #
# --------------------------------------------------------------------------- #


def test_skip_when_invitations_not_created(db: Session) -> None:
    """invite_offsets due but no Invitation rows → skip + dedup entry."""
    rs = _seed_session_with_reviewers(db, "skip-no-inv")
    start = datetime.now(timezone.utc) - timedelta(hours=1)
    rs.scheduled_activate_at = start  # in the past — entry resolves to past
    rs.invite_offsets = ["-PT2H"]  # 2h before start → now - 3h, due
    db.flush()
    db.commit()

    scheduled_events.observe_scheduled_events(
        db, rs, build_invite_url=_stub_build_url
    )
    skipped = _audit_rows(db, rs, "session.scheduled_invites_skipped")
    assert len(skipped) == 1
    assert skipped[0].detail["reason"] == "invitations_not_created"
    assert skipped[0].detail["context"]["offset_index"] == 0

    # Second observer pass should not re-emit (dedup keyed on entry).
    scheduled_events.observe_scheduled_events(
        db, rs, build_invite_url=_stub_build_url
    )
    assert len(_audit_rows(db, rs, "session.scheduled_invites_skipped")) == 1


# --------------------------------------------------------------------------- #
# Happy fire                                                                  #
# --------------------------------------------------------------------------- #


def test_fires_pending_invitations_at_due_time(db: Session) -> None:
    """invite_offsets due + invitations created + URL builder →
    invitations dispatched, audit emitted with counts.sent."""
    rs = _seed_session_with_reviewers(db, "fire-happy", reviewer_count=3)
    op = _operator(db, rs)
    # Session has to be at least validated for generate_invitations.
    rs.status = lifecycle.SessionStatus.validated.value
    db.flush()
    db.commit()

    _generate_invitations(db, rs, op)

    # Schedule for 1 day in the future, with an entry 2 days before
    # Start (resolves to 1 day in the past → due).
    rs.scheduled_activate_at = datetime.now(timezone.utc) + timedelta(days=1)
    rs.invite_offsets = ["-P2D"]
    db.flush()
    db.commit()

    scheduled_events.observe_scheduled_events(
        db, rs, build_invite_url=_stub_build_url
    )

    fired = _audit_rows(db, rs, "session.scheduled_invites_fired")
    assert len(fired) == 1
    assert fired[0].detail["counts"]["sent"] == 3
    assert fired[0].detail["context"]["offset_index"] == 0
    assert "actual_fired_at" in fired[0].detail["context"]
    assert "scheduled_at" in fired[0].detail["context"]

    # Every invitation should now be sent
    pending = db.execute(
        select(Invitation).where(
            Invitation.session_id == rs.id,
            Invitation.status == "pending",
        )
    ).scalars().all()
    assert pending == []

    # invitation.sent audit rows should carry context.trigger=scheduled
    invite_sents = _audit_rows(db, rs, "invitation.sent")
    assert len(invite_sents) == 3
    for row in invite_sents:
        assert row.detail["context"]["trigger"] == "scheduled"


def test_idempotent_on_repeated_observer_calls(db: Session) -> None:
    """A second observer pass after a successful fire does not re-fire
    the same entry (dedup via audit log)."""
    rs = _seed_session_with_reviewers(db, "idempotent")
    op = _operator(db, rs)
    rs.status = lifecycle.SessionStatus.validated.value
    db.flush()
    db.commit()
    _generate_invitations(db, rs, op)

    rs.scheduled_activate_at = datetime.now(timezone.utc) + timedelta(days=1)
    rs.invite_offsets = ["-P2D"]
    db.flush()
    db.commit()

    for _ in range(3):
        scheduled_events.observe_scheduled_events(
            db, rs, build_invite_url=_stub_build_url
        )

    fired = _audit_rows(db, rs, "session.scheduled_invites_fired")
    assert len(fired) == 1
    invite_sents = _audit_rows(db, rs, "invitation.sent")
    assert len(invite_sents) == 2  # two reviewers, one send each


def test_multi_entry_fires_in_chronological_order(db: Session) -> None:
    """Two past-due entries fire on a single observer pass, earliest first."""
    rs = _seed_session_with_reviewers(db, "multi-entry", reviewer_count=1)
    op = _operator(db, rs)
    rs.status = lifecycle.SessionStatus.validated.value
    db.flush()
    db.commit()
    _generate_invitations(db, rs, op)

    rs.scheduled_activate_at = datetime.now(timezone.utc) + timedelta(days=1)
    # Both offsets resolve to the past so both are due in one pass.
    # Order in the list is out of chronological order — observer fires
    # earliest-resolved (most negative offset) first.
    rs.invite_offsets = ["-P2D", "-P10D"]
    db.flush()
    db.commit()

    scheduled_events.observe_scheduled_events(
        db, rs, build_invite_url=_stub_build_url
    )

    fired = _audit_rows(db, rs, "session.scheduled_invites_fired")
    assert len(fired) == 2
    # Earlier fire moment → smaller audit id (it was emitted first)
    first_scheduled = fired[0].detail["context"]["scheduled_at"]
    second_scheduled = fired[1].detail["context"]["scheduled_at"]
    assert first_scheduled < second_scheduled
    # The second fire dispatches zero invitations — the first already
    # marked them all sent.
    assert fired[0].detail["counts"]["sent"] == 1
    assert fired[1].detail["counts"]["sent"] == 0


def test_reschedule_resets_per_entry_dedup(db: Session) -> None:
    """Changing scheduled_activate_at (different anchor_at) lets an
    already-fired entry fire again against the new anchor."""
    rs = _seed_session_with_reviewers(db, "reanchor", reviewer_count=1)
    op = _operator(db, rs)
    rs.status = lifecycle.SessionStatus.validated.value
    db.flush()
    db.commit()
    _generate_invitations(db, rs, op)

    first_anchor = datetime.now(timezone.utc) + timedelta(days=1)
    rs.scheduled_activate_at = first_anchor
    rs.invite_offsets = ["-P2D"]
    db.flush()
    db.commit()

    scheduled_events.observe_scheduled_events(
        db, rs, build_invite_url=_stub_build_url
    )
    assert len(_audit_rows(db, rs, "session.scheduled_invites_fired")) == 1

    # Operator reschedules; one invitation was sent already so we
    # manually create a fresh "pending" invitation for the test.
    new_reviewer = Reviewer(
        session_id=rs.id, name="Late", email="late-reanchor@example.edu"
    )
    db.add(new_reviewer)
    db.flush()
    invitations_service.generate_invitations(
        db, review_session=rs, user=op, correlation_id=None
    )

    new_anchor = datetime.now(timezone.utc) + timedelta(days=2)
    rs.scheduled_activate_at = new_anchor
    db.flush()
    db.commit()

    scheduled_events.observe_scheduled_events(
        db, rs, build_invite_url=_stub_build_url
    )
    fired = _audit_rows(db, rs, "session.scheduled_invites_fired")
    assert len(fired) == 2  # entry fires again against the new anchor
    # The second fire's anchor_at differs from the first
    assert (
        fired[0].detail["context"]["anchor_at"]
        != fired[1].detail["context"]["anchor_at"]
    )


def test_unparseable_offset_skipped_silently(db: Session) -> None:
    """A malformed entry in invite_offsets resolves to None and is
    skipped — no audit event, no exception, observer continues."""
    rs = _seed_session_with_reviewers(db, "bad-offset")
    op = _operator(db, rs)
    rs.status = lifecycle.SessionStatus.validated.value
    db.flush()
    db.commit()
    _generate_invitations(db, rs, op)

    rs.scheduled_activate_at = datetime.now(timezone.utc) + timedelta(days=1)
    rs.invite_offsets = ["NOT-AN-ISO-DURATION", "-P2D"]
    db.flush()
    db.commit()

    scheduled_events.observe_scheduled_events(
        db, rs, build_invite_url=_stub_build_url
    )
    # The good entry fired; the bad one was silently skipped (no fire,
    # no skip audit — the editor save-time validator is responsible
    # for catching these, not the runtime trigger).
    fired = _audit_rows(db, rs, "session.scheduled_invites_fired")
    assert len(fired) == 1
    assert fired[0].detail["context"]["offset"] == "-P2D"
