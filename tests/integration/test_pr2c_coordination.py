"""Coverage for the Segment 18G PR 2C cross-Part coordination
behaviours between Start (Part 1) and Auto-send invites (Part 2).

The five behaviours land together with PR 2C:

1. Edit-Start re-resolution — changing scheduled_activate_at
   re-runs the per-entry invite_offsets save-time rules.
2. Unset-Start warning — when the operator clears Start while
   invite_offsets is non-empty, the auto-send caption flips to
   an amber-grey "inactive: no Start" notice.
3. Manual-activate cancellation modal — the Activate button
   carries a data-manual-activate-confirm attribute that fires
   a browser confirm() when Start + invite_offsets are set.
4. Scheduled-activate catch-up — observer fires past-due invites
   BEFORE the activation in the same pass.
5. Manual-activate clears Start; invite_offsets becomes inert.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    AuditEvent,
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
from app.web.views._workflow_card import (
    build_auto_send_invites_caption,
    build_manual_activate_cancellation,
)


def _fmt_local_input(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M")


def _create_session(
    client: TestClient,
    code: str,
    *,
    scheduled_activate_at: str | None = None,
    invite_offsets: str | None = None,
) -> int:
    data: dict[str, str] = {
        "name": f"Sess {code}",
        "code": code,
        "description": "d",
    }
    if scheduled_activate_at:
        data["scheduled_activate_at"] = scheduled_activate_at
    if invite_offsets:
        data["invite_offsets"] = invite_offsets
    response = client.post(
        "/operator/sessions", data=data, follow_redirects=False
    )
    assert response.status_code == 303, response.text
    return int(response.headers["location"].rsplit("/", 1)[-1])


def _audit_types(db: Session, session_id: int) -> list[str]:
    return list(
        db.execute(
            select(AuditEvent.event_type)
            .where(AuditEvent.session_id == session_id)
            .order_by(AuditEvent.id)
        ).scalars()
    )


# --------------------------------------------------------------------------- #
# (1) Edit-Start re-resolution                                                #
# --------------------------------------------------------------------------- #


def test_edit_start_change_revalidates_invite_offsets(
    client: TestClient, db: Session
) -> None:
    """Operator moves Start closer to now; previously-valid
    invite_offsets now violates the operational-lead rule → 422."""
    far_start = datetime.now(timezone.utc) + timedelta(days=10)
    session_id = _create_session(
        client,
        "revalidate",
        scheduled_activate_at=_fmt_local_input(far_start),
        invite_offsets="-P5D",  # fires 5 days before Start = now + 5d (future, OK)
    )

    # Move Start to 1 day from now; the same -P5D offset would resolve
    # to 4 days ago — well before now + 1hr operational lead.
    near_start = datetime.now(timezone.utc) + timedelta(days=1)
    response = client.post(
        f"/operator/sessions/{session_id}/edit",
        data={
            "name": "x",
            "code": "revalidate",
            "scheduled_activate_at": _fmt_local_input(near_start),
            "invite_offsets": "-P5D",
        },
        follow_redirects=False,
    )
    assert response.status_code == 422
    # Original Start remains unchanged in the DB
    rs = db.get(ReviewSession, session_id)
    assert rs.invite_offsets == ["-P5D"]


def test_edit_start_change_within_rules_succeeds(
    client: TestClient, db: Session
) -> None:
    """Counterpart to the above — moving Start while keeping the
    rules satisfied saves cleanly."""
    far_start = datetime.now(timezone.utc) + timedelta(days=10)
    session_id = _create_session(
        client,
        "revalidate-ok",
        scheduled_activate_at=_fmt_local_input(far_start),
        invite_offsets="-P2D",
    )

    further_start = datetime.now(timezone.utc) + timedelta(days=20)
    response = client.post(
        f"/operator/sessions/{session_id}/edit",
        data={
            "name": "x",
            "code": "revalidate-ok",
            "scheduled_activate_at": _fmt_local_input(further_start),
            "invite_offsets": "-P2D",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text


# --------------------------------------------------------------------------- #
# (2) Unset-Start warning                                                     #
# --------------------------------------------------------------------------- #


def test_caption_amber_grey_when_start_cleared_with_offsets_set(
    db: Session,
) -> None:
    """Operator clears Start but invite_offsets persists → caption
    flips to the amber-grey 'inactive: no Start' notice."""
    op = User(email="op-unset@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    rs = sessions_service.create_session(
        db,
        user=op,
        payload=SessionCreate(name="t", code="unset-start", description="d"),
    )
    rs.invite_offsets = ["-P1D", "-PT4H"]
    # scheduled_activate_at stays None — that's the unset-Start state
    db.flush()
    db.commit()

    caption = build_auto_send_invites_caption(db, rs)
    assert caption is not None
    assert caption["tone"] == "amber-grey"
    assert "no Start" in caption["text"]
    assert "2 entries" in caption["text"]


# --------------------------------------------------------------------------- #
# (3) Manual-activate cancellation modal                                      #
# --------------------------------------------------------------------------- #


def test_cancellation_message_when_validated_with_offsets(db: Session) -> None:
    """build_manual_activate_cancellation returns the modal message
    only when the session is validated, Start is set, and there are
    one or more invite_offsets entries."""
    op = User(email="op-cancel@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    rs = sessions_service.create_session(
        db,
        user=op,
        payload=SessionCreate(name="t", code="cancel-msg", description="d"),
    )
    rs.status = lifecycle.SessionStatus.validated.value
    rs.scheduled_activate_at = datetime.now(timezone.utc) + timedelta(days=10)
    rs.invite_offsets = ["-P2D"]
    db.flush()
    db.commit()

    cancellation = build_manual_activate_cancellation(rs)
    assert cancellation is not None
    assert cancellation["pending_count"] == 1
    assert "1 scheduled auto-send invitation will be cancelled" in cancellation["message"]


def test_cancellation_none_when_not_validated(db: Session) -> None:
    """Draft session — Activate isn't offered, so no modal."""
    op = User(email="op-cancel-draft@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    rs = sessions_service.create_session(
        db,
        user=op,
        payload=SessionCreate(name="t", code="cancel-draft", description="d"),
    )
    rs.scheduled_activate_at = datetime.now(timezone.utc) + timedelta(days=10)
    rs.invite_offsets = ["-P2D"]
    db.flush()
    db.commit()

    assert build_manual_activate_cancellation(rs) is None


def test_cancellation_none_without_offsets(db: Session) -> None:
    """Validated session but no invite_offsets — no modal needed."""
    op = User(email="op-cancel-no-offsets@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    rs = sessions_service.create_session(
        db,
        user=op,
        payload=SessionCreate(name="t", code="cancel-no-off", description="d"),
    )
    rs.status = lifecycle.SessionStatus.validated.value
    rs.scheduled_activate_at = datetime.now(timezone.utc) + timedelta(days=10)
    db.flush()
    db.commit()

    assert build_manual_activate_cancellation(rs) is None


# --------------------------------------------------------------------------- #
# (4) Scheduled-activate catch-up                                             #
# --------------------------------------------------------------------------- #


def _seed_full_session(db: Session, code: str) -> ReviewSession:
    op = User(email=f"op-{code}@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    rs = sessions_service.create_session(
        db,
        user=op,
        payload=SessionCreate(name=code.title(), code=code, description="d"),
    )
    reviewer = Reviewer(
        session_id=rs.id, name="A", email=f"a-{code}@example.edu"
    )
    reviewee = Reviewee(
        session_id=rs.id,
        name="C",
        email_or_identifier=f"c-{code}@example.edu",
    )
    db.add_all([reviewer, reviewee])
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
    invitations_service.generate_invitations(
        db, review_session=rs, user=op
    )
    rs.status = lifecycle.SessionStatus.validated.value
    db.flush()
    db.commit()
    db.refresh(rs)
    return rs


def test_observer_fires_invites_before_activation_on_catch_up(
    db: Session,
) -> None:
    """A 48-hour window with no operator visits: the observer runs at
    Start+1min and fires the past-due invite AND the activation in
    one pass. Audit ordering: scheduled_invites_fired before
    session.activated."""
    rs = _seed_full_session(db, "catchup")
    rs.scheduled_activate_at = datetime.now(timezone.utc) - timedelta(
        seconds=30
    )  # already past
    rs.invite_offsets = ["-P1D"]  # also past
    db.flush()
    db.commit()

    scheduled_events.observe_scheduled_events(
        db,
        rs,
        build_invite_url=lambda token: f"https://test/invite/{token}",
    )
    db.refresh(rs)
    assert rs.status == lifecycle.SessionStatus.ready.value

    types = _audit_types(db, rs.id)
    fired_idx = types.index("session.scheduled_invites_fired")
    activated_idx = types.index("session.activated")
    assert fired_idx < activated_idx


# --------------------------------------------------------------------------- #
# (5) Manual-activate cancellation end-to-end                                 #
# --------------------------------------------------------------------------- #


def test_manual_activate_clears_start_invite_offsets_inert(
    db: Session,
) -> None:
    """Manual activate (via lifecycle.activate_session) clears
    scheduled_activate_at as a side effect. invite_offsets persists
    in the column but is now inert via anchor-null."""
    rs = _seed_full_session(db, "manual-cancel")
    rs.scheduled_activate_at = datetime.now(timezone.utc) + timedelta(days=5)
    rs.invite_offsets = ["-P2D"]
    db.flush()
    db.commit()

    op = db.execute(
        select(User).where(User.email == "op-manual-cancel@example.edu")
    ).scalar_one()
    report = lifecycle.build_readiness_report([])
    lifecycle.activate_session(
        db,
        review_session=rs,
        user=op,
        report=report,
        acknowledge_warnings=False,
    )
    db.refresh(rs)
    assert rs.scheduled_activate_at is None
    assert rs.invite_offsets == ["-P2D"]  # persisted but inert
    # The post-activation observer pass no-ops the invite trigger
    scheduled_events.observe_scheduled_events(
        db,
        rs,
        build_invite_url=lambda token: f"https://test/invite/{token}",
    )
    fired = db.execute(
        select(AuditEvent)
        .where(AuditEvent.session_id == rs.id)
        .where(AuditEvent.event_type == "session.scheduled_invites_fired")
    ).scalars().all()
    assert fired == []  # no fire after manual activate clears anchor
