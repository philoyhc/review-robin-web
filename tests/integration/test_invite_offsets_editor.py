"""Editor + caption + timeline coverage for Segment 18G PR 2B.

End-to-end checks on the Auto-send (``invite_offsets``) input on
the Create / Edit session forms, the Manage Invitations card
caption, and the Schedule timeline preview block.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession
from app.services import scheduled_events
from app.web.views._workflow_card import (
    build_auto_send_invites_caption,
    build_schedule_timeline,
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
    return response.status_code, response, int(
        response.headers["location"].rsplit("/", 1)[-1]
    ) if response.status_code == 303 else (response.status_code, response, 0)


# --------------------------------------------------------------------------- #
# Parser unit tests                                                            #
# --------------------------------------------------------------------------- #


def test_parser_returns_none_for_empty(db: Session) -> None:
    """Empty or whitespace-only inputs round-trip to None (cleared)."""
    assert (
        scheduled_events.parse_and_validate_invite_offsets(
            None, scheduled_activate_at=None
        )
        is None
    )
    assert (
        scheduled_events.parse_and_validate_invite_offsets(
            "", scheduled_activate_at=None
        )
        is None
    )
    assert (
        scheduled_events.parse_and_validate_invite_offsets(
            "   ", scheduled_activate_at=None
        )
        is None
    )


def test_parser_splits_comma_separated_entries(db: Session) -> None:
    """Multi-entry strings parse to a clean list with stripped whitespace."""
    start = datetime.now(timezone.utc) + timedelta(days=30)
    result = scheduled_events.parse_and_validate_invite_offsets(
        "-P1D , -PT4H", scheduled_activate_at=start
    )
    assert result == ["-P1D", "-PT4H"]


def test_parser_rejects_invalid_iso_entry(db: Session) -> None:
    start = datetime.now(timezone.utc) + timedelta(days=30)
    try:
        scheduled_events.parse_and_validate_invite_offsets(
            "NOT-AN-ISO", scheduled_activate_at=start
        )
    except scheduled_events.ScheduledActivateError as exc:
        assert "isn't a valid ISO 8601 duration" in str(exc)
    else:
        raise AssertionError("expected ScheduledActivateError")


def test_parser_rejects_positive_offset(db: Session) -> None:
    """Positive offsets fire at or after Start — flag at save."""
    start = datetime.now(timezone.utc) + timedelta(days=30)
    try:
        scheduled_events.parse_and_validate_invite_offsets(
            "P1D", scheduled_activate_at=start
        )
    except scheduled_events.ScheduledActivateError as exc:
        assert "fires at or after Start" in str(exc)
    else:
        raise AssertionError("expected ScheduledActivateError")


def test_parser_rejects_too_small_notice_gap(db: Session) -> None:
    """|offset| less than REVIEWER_NOTICE_MIN_HOURS is rejected."""
    start = datetime.now(timezone.utc) + timedelta(days=30)
    try:
        scheduled_events.parse_and_validate_invite_offsets(
            "-PT30M", scheduled_activate_at=start
        )
    except scheduled_events.ScheduledActivateError as exc:
        assert "minimum reviewer notice" in str(exc)
    else:
        raise AssertionError("expected ScheduledActivateError")


def test_parser_rejects_too_close_to_now(db: Session) -> None:
    """Resolved fire moment before now + SCHEDULED_OPERATIONAL_LEAD_HOURS rejected."""
    # Start in 30 minutes; offset of -PT1H resolves to 30 minutes ago.
    start = datetime.now(timezone.utc) + timedelta(minutes=30)
    try:
        scheduled_events.parse_and_validate_invite_offsets(
            "-PT1H", scheduled_activate_at=start
        )
    except scheduled_events.ScheduledActivateError:
        pass
    else:
        raise AssertionError("expected ScheduledActivateError")


def test_parser_accepts_when_start_unset(db: Session) -> None:
    """Without Start, only the parse-validity check runs (offsets are inert)."""
    result = scheduled_events.parse_and_validate_invite_offsets(
        "-P1D, -PT2H", scheduled_activate_at=None
    )
    assert result == ["-P1D", "-PT2H"]


# --------------------------------------------------------------------------- #
# Editor end-to-end                                                            #
# --------------------------------------------------------------------------- #


def test_create_accepts_invite_offsets_with_valid_start(
    client: TestClient, db: Session
) -> None:
    start = datetime.now(timezone.utc) + timedelta(days=30)
    status_code, _, session_id = _create_session(
        client,
        "create-inv",
        scheduled_activate_at=_fmt_local_input(start),
        invite_offsets="-P1D, -PT4H",
    )
    assert status_code == 303
    rs = db.get(ReviewSession, session_id)
    assert rs is not None
    assert rs.invite_offsets == ["-P1D", "-PT4H"]


def test_create_rejects_invalid_invite_offset(client: TestClient) -> None:
    start = datetime.now(timezone.utc) + timedelta(days=30)
    response = client.post(
        "/operator/sessions",
        data={
            "name": "x",
            "code": "create-bad-inv",
            "scheduled_activate_at": _fmt_local_input(start),
            "invite_offsets": "-PT30M",  # less than 1hr gap
        },
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert "minimum reviewer notice" in response.text


def test_edit_round_trips_invite_offsets(
    client: TestClient, db: Session
) -> None:
    _, _, session_id = _create_session(client, "edit-inv")
    start = datetime.now(timezone.utc) + timedelta(days=30)

    # Set
    response = client.post(
        f"/operator/sessions/{session_id}/edit",
        data={
            "name": "Sess edit-inv",
            "code": "edit-inv",
            "scheduled_activate_at": _fmt_local_input(start),
            "invite_offsets": "-P1D",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    rs = db.get(ReviewSession, session_id)
    assert rs.invite_offsets == ["-P1D"]

    # Edit GET prefills the input value
    page = client.get(f"/operator/sessions/{session_id}/edit")
    assert page.status_code == 200
    assert 'name="invite_offsets"' in page.text
    assert "-P1D" in page.text

    # Clear
    client.post(
        f"/operator/sessions/{session_id}/edit",
        data={
            "name": "Sess edit-inv",
            "code": "edit-inv",
            "scheduled_activate_at": _fmt_local_input(start),
            "invite_offsets": "",
        },
        follow_redirects=False,
    )
    db.refresh(rs)
    assert rs.invite_offsets is None


def test_edit_emits_invite_schedule_updated_audit(
    client: TestClient, db: Session
) -> None:
    _, _, session_id = _create_session(client, "audit-inv")
    start = datetime.now(timezone.utc) + timedelta(days=30)
    client.post(
        f"/operator/sessions/{session_id}/edit",
        data={
            "name": "x",
            "code": "audit-inv",
            "scheduled_activate_at": _fmt_local_input(start),
            "invite_offsets": "-P1D",
        },
        follow_redirects=False,
    )
    audits = db.execute(
        select(AuditEvent)
        .where(AuditEvent.session_id == session_id)
        .where(AuditEvent.event_type == "session.invite_schedule_updated")
    ).scalars().all()
    assert len(audits) == 1


# --------------------------------------------------------------------------- #
# Schedule timeline preview                                                    #
# --------------------------------------------------------------------------- #


def test_timeline_empty_when_no_anchor(db: Session) -> None:
    """No Start anchor → no timeline rows."""
    from app.db.models import User
    from app.schemas.sessions import SessionCreate
    from app.services import sessions as sessions_service

    op = User(email="op-tl-empty@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    rs = sessions_service.create_session(
        db,
        user=op,
        payload=SessionCreate(name="t", code="tl-empty", description="d"),
    )
    rows = build_schedule_timeline(rs, "UTC")
    assert rows == []


def test_timeline_renders_start_and_invite_offsets_chronologically(
    db: Session,
) -> None:
    from app.db.models import User
    from app.schemas.sessions import SessionCreate
    from app.services import sessions as sessions_service

    op = User(email="op-tl-rows@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    rs = sessions_service.create_session(
        db,
        user=op,
        payload=SessionCreate(name="t", code="tl-rows", description="d"),
    )
    rs.scheduled_activate_at = datetime(
        2099, 6, 1, 9, 0, tzinfo=timezone.utc
    )
    rs.invite_offsets = ["-PT2H", "-P1D"]
    db.flush()
    db.commit()

    rows = build_schedule_timeline(rs, "UTC")
    assert len(rows) == 3
    # Earlier offset (-P1D = 1 day before Start) → first row.
    assert "Auto-send" in rows[0]["label"]
    assert "-P1D" in rows[0]["label"]
    assert "Auto-send" in rows[1]["label"]
    assert "-PT2H" in rows[1]["label"]
    assert "activates" in rows[2]["label"]


# --------------------------------------------------------------------------- #
# Manage Invitations caption                                                   #
# --------------------------------------------------------------------------- #


def test_caption_none_without_offsets(db: Session) -> None:
    from app.db.models import User
    from app.schemas.sessions import SessionCreate
    from app.services import sessions as sessions_service

    op = User(email="op-cap-empty@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    rs = sessions_service.create_session(
        db,
        user=op,
        payload=SessionCreate(name="t", code="cap-empty", description="d"),
    )
    assert build_auto_send_invites_caption(db, rs) is None


def test_caption_amber_when_offsets_but_no_invitations(db: Session) -> None:
    from app.db.models import User
    from app.schemas.sessions import SessionCreate
    from app.services import sessions as sessions_service

    op = User(email="op-cap-amber@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    rs = sessions_service.create_session(
        db,
        user=op,
        payload=SessionCreate(name="t", code="cap-amber", description="d"),
    )
    rs.scheduled_activate_at = datetime(
        2099, 6, 1, 9, 0, tzinfo=timezone.utc
    )
    rs.invite_offsets = ["-P1D"]
    db.flush()
    db.commit()

    caption = build_auto_send_invites_caption(db, rs)
    assert caption is not None
    assert caption["tone"] == "amber-warning"
    assert "create invitations" in caption["text"]


def test_caption_green_when_invitations_exist(db: Session) -> None:
    from app.db.models import (
        Assignment,
        Instrument,
        Reviewee,
        Reviewer,
        SessionRuleSet,
        User,
    )
    from app.schemas.sessions import SessionCreate
    from app.services import (
        invitations as invitations_service,
        sessions as sessions_service,
    )

    op = User(email="op-cap-green@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    rs = sessions_service.create_session(
        db,
        user=op,
        payload=SessionCreate(name="t", code="cap-green", description="d"),
    )
    reviewer = Reviewer(
        session_id=rs.id, name="A", email="a-cap-green@example.edu"
    )
    reviewee = Reviewee(
        session_id=rs.id,
        name="C",
        email_or_identifier="c-cap-green@example.edu",
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

    rs.scheduled_activate_at = datetime(
        2099, 6, 1, 9, 0, tzinfo=timezone.utc
    )
    rs.invite_offsets = ["-P1D"]
    db.flush()
    db.commit()

    caption = build_auto_send_invites_caption(db, rs)
    assert caption is not None
    assert caption["tone"] == "green"
    assert "dispatch automatically" in caption["text"]
