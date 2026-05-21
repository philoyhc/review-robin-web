"""Coverage for the Segment 18G Part 3 (PR 3A) auto-send reminder trigger.

Tests run the observer end-to-end with a stub ``build_invite_url``
closure so the dispatch path runs without a live FastAPI Request.
Mirrors the structure of ``test_scheduled_invites.py``.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    AuditEvent,
    EmailOutbox,
    Instrument,
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
    rule. Returns the session in ``draft``."""
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


def _operator(db: Session, rs: ReviewSession) -> User:
    return db.get(User, rs.created_by_user_id)


def _ready_session_with_invitations(
    db: Session,
    code: str,
    *,
    reviewer_count: int = 2,
) -> ReviewSession:
    """Standard fixture: session moved to ``ready`` with one
    invitation per reviewer already minted (no sends yet).

    Reminders' fallback path (no prior invitation outbox row) calls
    ``send_invitation`` to rotate the token + dispatch — that's the
    happy path the tests below exercise.
    """
    rs = _seed_session_with_reviewers(db, code, reviewer_count=reviewer_count)
    op = _operator(db, rs)
    rs.status = lifecycle.SessionStatus.validated.value
    db.flush()
    db.commit()
    _seed_assignments(db, rs)
    invitations_service.generate_invitations(
        db, review_session=rs, user=op, correlation_id=None
    )
    rs.status = lifecycle.SessionStatus.ready.value
    db.flush()
    db.commit()
    return rs


# --------------------------------------------------------------------------- #
# No-op paths                                                                 #
# --------------------------------------------------------------------------- #


def test_no_op_when_reminder_offsets_unset(db: Session) -> None:
    rs = _ready_session_with_invitations(db, "noop-empty-rem")
    rs.deadline = datetime.now(timezone.utc) + timedelta(days=1)
    db.flush()
    db.commit()

    scheduled_events.observe_scheduled_events(
        db, rs, build_invite_url=_stub_build_url
    )
    assert _audit_rows(db, rs, "session.scheduled_reminders_fired") == []
    assert _audit_rows(db, rs, "session.scheduled_reminders_skipped") == []


def test_no_op_when_deadline_unset(db: Session) -> None:
    """reminder_offsets set but deadline None → inert."""
    rs = _ready_session_with_invitations(db, "noop-no-deadline")
    rs.reminder_offsets = ["-P1D"]
    db.flush()
    db.commit()

    scheduled_events.observe_scheduled_events(
        db, rs, build_invite_url=_stub_build_url
    )
    assert _audit_rows(db, rs, "session.scheduled_reminders_fired") == []
    assert _audit_rows(db, rs, "session.scheduled_reminders_skipped") == []


def test_no_op_when_build_invite_url_missing(db: Session) -> None:
    """Without a URL builder the fallback path can't dispatch → no-op."""
    rs = _ready_session_with_invitations(db, "noop-no-url-rem")
    rs.deadline = datetime.now(timezone.utc) + timedelta(days=1)
    rs.reminder_offsets = ["-P30D"]
    db.flush()
    db.commit()

    scheduled_events.observe_scheduled_events(db, rs)
    assert _audit_rows(db, rs, "session.scheduled_reminders_fired") == []


def test_no_op_when_offset_in_future(db: Session) -> None:
    """Resolved fire moment hasn't arrived yet → no-op for that entry."""
    rs = _ready_session_with_invitations(db, "future-offset-rem")
    rs.deadline = datetime.now(timezone.utc) + timedelta(days=10)
    rs.reminder_offsets = ["-P1D"]
    db.flush()
    db.commit()

    scheduled_events.observe_scheduled_events(
        db, rs, build_invite_url=_stub_build_url
    )
    assert _audit_rows(db, rs, "session.scheduled_reminders_fired") == []


# --------------------------------------------------------------------------- #
# Precondition skips                                                          #
# --------------------------------------------------------------------------- #


def test_skip_when_not_ready(db: Session) -> None:
    """reminder_offsets due but session is draft (not yet activated) →
    skip with reason=not_ready, one-shot consume."""
    rs = _seed_session_with_reviewers(db, "skip-draft")
    rs.deadline = datetime.now(timezone.utc) + timedelta(hours=2)
    rs.reminder_offsets = ["-P1D"]  # resolves to ~22h ago — due
    db.flush()
    db.commit()

    scheduled_events.observe_scheduled_events(
        db, rs, build_invite_url=_stub_build_url
    )
    skipped = _audit_rows(db, rs, "session.scheduled_reminders_skipped")
    assert len(skipped) == 1
    assert skipped[0].detail["reason"] == "not_ready"
    assert skipped[0].detail["context"]["offset_index"] == 0

    # Second pass: dedup holds.
    scheduled_events.observe_scheduled_events(
        db, rs, build_invite_url=_stub_build_url
    )
    assert len(_audit_rows(db, rs, "session.scheduled_reminders_skipped")) == 1


def test_skip_when_no_invitations(db: Session) -> None:
    """Session ready but no Invitation rows → skip with reason=no_invitations."""
    rs = _seed_session_with_reviewers(db, "skip-no-inv-rem")
    rs.status = lifecycle.SessionStatus.ready.value
    rs.deadline = datetime.now(timezone.utc) + timedelta(hours=2)
    rs.reminder_offsets = ["-P1D"]
    db.flush()
    db.commit()

    scheduled_events.observe_scheduled_events(
        db, rs, build_invite_url=_stub_build_url
    )
    skipped = _audit_rows(db, rs, "session.scheduled_reminders_skipped")
    assert len(skipped) == 1
    assert skipped[0].detail["reason"] == "no_invitations"


def test_skip_when_past_deadline(db: Session) -> None:
    """Session ready + invitations exist, but now is past deadline →
    skip with reason=outside_response_window."""
    rs = _ready_session_with_invitations(db, "skip-past-dl")
    # deadline two hours in the past
    rs.deadline = datetime.now(timezone.utc) - timedelta(hours=2)
    rs.reminder_offsets = ["-PT4H"]  # resolves to 6h ago — due
    db.flush()
    db.commit()

    scheduled_events.observe_scheduled_events(
        db, rs, build_invite_url=_stub_build_url
    )
    skipped = _audit_rows(db, rs, "session.scheduled_reminders_skipped")
    assert len(skipped) == 1
    assert skipped[0].detail["reason"] == "outside_response_window"


# --------------------------------------------------------------------------- #
# Happy fire + dedup                                                          #
# --------------------------------------------------------------------------- #


def test_fires_to_incomplete_reviewers_at_due_time(db: Session) -> None:
    """Past-due offset + ready session + invitations exist + incomplete
    reviewers → reminders dispatched, audit emitted with counts.sent."""
    rs = _ready_session_with_invitations(db, "fire-happy-rem", reviewer_count=3)
    rs.deadline = datetime.now(timezone.utc) + timedelta(hours=4)
    # -PT8H resolves to 4h ago → due. Offset is anchored on deadline.
    rs.reminder_offsets = ["-PT8H"]
    db.flush()
    db.commit()

    scheduled_events.observe_scheduled_events(
        db, rs, build_invite_url=_stub_build_url
    )

    fired = _audit_rows(db, rs, "session.scheduled_reminders_fired")
    assert len(fired) == 1
    assert fired[0].detail["counts"]["sent"] == 3
    assert fired[0].detail["context"]["offset_index"] == 0
    assert "actual_fired_at" in fired[0].detail["context"]
    assert "scheduled_at" in fired[0].detail["context"]
    assert "anchor_at" in fired[0].detail["context"]

    # All three reviewers got an outbox row stamped with the
    # per-reviewer correlation_id.
    reviewers = db.execute(
        select(Reviewer).where(Reviewer.session_id == rs.id)
    ).scalars().all()
    for reviewer in reviewers:
        cid = f"reminder:{rs.id}:{reviewer.id}:0"
        row = db.execute(
            select(EmailOutbox).where(EmailOutbox.correlation_id == cid)
        ).scalar_one_or_none()
        assert row is not None


def test_idempotent_on_repeated_observer_calls(db: Session) -> None:
    """A second observer pass after a successful fire does not re-fire
    the same entry (dedup via audit log)."""
    rs = _ready_session_with_invitations(db, "idempotent-rem")
    rs.deadline = datetime.now(timezone.utc) + timedelta(hours=4)
    rs.reminder_offsets = ["-PT8H"]
    db.flush()
    db.commit()

    for _ in range(3):
        scheduled_events.observe_scheduled_events(
            db, rs, build_invite_url=_stub_build_url
        )

    fired = _audit_rows(db, rs, "session.scheduled_reminders_fired")
    assert len(fired) == 1

    # Each reviewer received exactly one reminder-correlated outbox row.
    rows = db.execute(
        select(EmailOutbox).where(EmailOutbox.session_id == rs.id)
    ).scalars().all()
    reminder_rows = [r for r in rows if (r.correlation_id or "").startswith("reminder:")]
    assert len(reminder_rows) == 2  # two reviewers, one each


def test_per_reviewer_dedup_via_correlation_id(db: Session) -> None:
    """Pre-stamp an outbox row with the dedup correlation_id; the
    trigger should skip that reviewer and only dispatch to the other."""
    rs = _ready_session_with_invitations(db, "per-rev-dedup", reviewer_count=2)
    reviewers = db.execute(
        select(Reviewer).where(Reviewer.session_id == rs.id).order_by(Reviewer.id)
    ).scalars().all()
    pre_reviewer = reviewers[0]
    pre_cid = f"reminder:{rs.id}:{pre_reviewer.id}:0"
    db.add(
        EmailOutbox(
            session_id=rs.id,
            reviewer_id=pre_reviewer.id,
            kind=invitations_service.REMINDER_KIND,
            to_email=pre_reviewer.email,
            subject="pre-existing",
            body="pre",
            status="sent",
            correlation_id=pre_cid,
        )
    )
    rs.deadline = datetime.now(timezone.utc) + timedelta(hours=4)
    rs.reminder_offsets = ["-PT8H"]
    db.flush()
    db.commit()

    scheduled_events.observe_scheduled_events(
        db, rs, build_invite_url=_stub_build_url
    )

    fired = _audit_rows(db, rs, "session.scheduled_reminders_fired")
    assert len(fired) == 1
    # Only one new reminder dispatched (the other reviewer was deduped).
    assert fired[0].detail["counts"]["sent"] == 1


def test_multi_entry_fires_in_chronological_order(db: Session) -> None:
    """Two past-due entries fire on a single observer pass, earliest first.

    Each offset_index is an independent dedup key (per the plan's
    ``reminder:{sid}:{rid}:{n}`` correlation_id), so a reviewer
    receives one reminder per past-due offset entry. In a typical
    operator-visit cadence each entry fires alone; the catch-up case
    here (two past-due at once) deliberately delivers two — the
    operator picks fewer cadences to avoid that.
    """
    rs = _ready_session_with_invitations(
        db, "multi-entry-rem", reviewer_count=1
    )
    rs.deadline = datetime.now(timezone.utc) + timedelta(hours=4)
    # Both resolve to the past; list order is out of chronological order.
    rs.reminder_offsets = ["-PT8H", "-P2D"]
    db.flush()
    db.commit()

    scheduled_events.observe_scheduled_events(
        db, rs, build_invite_url=_stub_build_url
    )

    fired = _audit_rows(db, rs, "session.scheduled_reminders_fired")
    assert len(fired) == 2
    first_scheduled = fired[0].detail["context"]["scheduled_at"]
    second_scheduled = fired[1].detail["context"]["scheduled_at"]
    assert first_scheduled < second_scheduled
    # Both offsets dispatch to the (single) incomplete reviewer; the
    # dedup key differs by offset_index so each fire dispatches anew.
    assert fired[0].detail["counts"]["sent"] == 1
    assert fired[1].detail["counts"]["sent"] == 1
    # Outbox rows exist under both correlation_ids.
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == rs.id)
    ).scalar_one()
    for idx in (0, 1):
        cid = f"reminder:{rs.id}:{reviewer.id}:{idx}"
        row = db.execute(
            select(EmailOutbox).where(EmailOutbox.correlation_id == cid)
        ).scalar_one_or_none()
        assert row is not None


def test_reschedule_resets_per_entry_dedup(db: Session) -> None:
    """Changing deadline (different anchor_at) lets an already-fired
    entry fire again against the new anchor.

    Note: the per-reviewer correlation_id key is keyed on
    (session_id, reviewer_id, offset_index) — *not* on anchor_at — so
    after a reschedule the per-offset audit dedup resets but the
    per-reviewer outbox dedup may still bite. This test asserts the
    audit consume resets (a new ``_fired`` row gets emitted); count of
    actually-dispatched reminders can legitimately be zero.
    """
    rs = _ready_session_with_invitations(
        db, "reanchor-rem", reviewer_count=1
    )
    first_deadline = datetime.now(timezone.utc) + timedelta(hours=4)
    rs.deadline = first_deadline
    rs.reminder_offsets = ["-PT8H"]
    db.flush()
    db.commit()

    scheduled_events.observe_scheduled_events(
        db, rs, build_invite_url=_stub_build_url
    )
    assert len(_audit_rows(db, rs, "session.scheduled_reminders_fired")) == 1

    # Operator reschedules deadline; the same offset entry should
    # re-evaluate against the new anchor.
    new_deadline = datetime.now(timezone.utc) + timedelta(hours=2)
    rs.deadline = new_deadline
    db.flush()
    db.commit()

    scheduled_events.observe_scheduled_events(
        db, rs, build_invite_url=_stub_build_url
    )
    fired = _audit_rows(db, rs, "session.scheduled_reminders_fired")
    assert len(fired) == 2
    assert (
        fired[0].detail["context"]["anchor_at"]
        != fired[1].detail["context"]["anchor_at"]
    )


def test_unparseable_offset_skipped_silently(db: Session) -> None:
    """A malformed entry in reminder_offsets resolves to None and is
    silently skipped — no audit event, observer continues with valid
    entries."""
    rs = _ready_session_with_invitations(db, "bad-offset-rem")
    rs.deadline = datetime.now(timezone.utc) + timedelta(hours=4)
    rs.reminder_offsets = ["NOT-AN-ISO-DURATION", "-PT8H"]
    db.flush()
    db.commit()

    scheduled_events.observe_scheduled_events(
        db, rs, build_invite_url=_stub_build_url
    )
    fired = _audit_rows(db, rs, "session.scheduled_reminders_fired")
    assert len(fired) == 1
    assert fired[0].detail["context"]["offset"] == "-PT8H"
