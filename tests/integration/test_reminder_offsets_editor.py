"""Editor + caption + timeline coverage for Segment 18G PR 3B.

End-to-end checks on the Auto-send reminders (``reminder_offsets``)
input on the Create / Edit session forms, the Manage Invitations card
caption, and the Schedule timeline preview block. Mirrors the Part 2
``test_invite_offsets_editor.py`` structure.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession
from app.services import scheduled_events, session_lifecycle as lifecycle
from app.web.views._workflow_card import (
    build_auto_send_reminders_caption,
    build_schedule_timeline,
)


def _fmt_local_input(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M")


def _create_session(
    client: TestClient,
    code: str,
    *,
    deadline: str | None = None,
    reminder_offsets: str | None = None,
) -> tuple[int, object, int]:
    data: dict[str, str] = {
        "name": f"Sess {code}",
        "code": code,
        "description": "d",
    }
    if deadline:
        data["deadline"] = deadline
    if reminder_offsets:
        data["reminder_offsets"] = reminder_offsets
    response = client.post(
        "/operator/sessions", data=data, follow_redirects=False
    )
    session_id = 0
    if response.status_code == 303:
        session_id = int(response.headers["location"].rsplit("/", 1)[-1])
    return response.status_code, response, session_id


# --------------------------------------------------------------------------- #
# Parser unit tests                                                            #
# --------------------------------------------------------------------------- #


def test_parser_returns_none_for_empty(db: Session) -> None:
    assert (
        scheduled_events.parse_and_validate_reminder_offsets(
            None, deadline=None
        )
        is None
    )
    assert (
        scheduled_events.parse_and_validate_reminder_offsets(
            "", deadline=None
        )
        is None
    )
    assert (
        scheduled_events.parse_and_validate_reminder_offsets(
            "   ", deadline=None
        )
        is None
    )


def test_parser_splits_comma_separated_entries(db: Session) -> None:
    deadline = datetime.now(timezone.utc) + timedelta(days=30)
    result = scheduled_events.parse_and_validate_reminder_offsets(
        "-P1D , -PT4H", deadline=deadline
    )
    assert result == ["-P1D", "-PT4H"]


def test_parser_rejects_invalid_iso_entry(db: Session) -> None:
    deadline = datetime.now(timezone.utc) + timedelta(days=30)
    try:
        scheduled_events.parse_and_validate_reminder_offsets(
            "NOT-AN-ISO", deadline=deadline
        )
    except scheduled_events.ScheduledActivateError as exc:
        assert "isn't a valid ISO 8601 duration" in str(exc)
    else:
        raise AssertionError("expected ScheduledActivateError")


def test_parser_rejects_positive_offset(db: Session) -> None:
    """Positive offsets fire at or after End — flag at save."""
    deadline = datetime.now(timezone.utc) + timedelta(days=30)
    try:
        scheduled_events.parse_and_validate_reminder_offsets(
            "P1D", deadline=deadline
        )
    except scheduled_events.ScheduledActivateError as exc:
        assert "fires at or after End" in str(exc)
    else:
        raise AssertionError("expected ScheduledActivateError")


def test_parser_rejects_too_small_notice_gap(db: Session) -> None:
    deadline = datetime.now(timezone.utc) + timedelta(days=30)
    try:
        scheduled_events.parse_and_validate_reminder_offsets(
            "-PT30M", deadline=deadline
        )
    except scheduled_events.ScheduledActivateError as exc:
        assert "minimum reviewer notice" in str(exc)
    else:
        raise AssertionError("expected ScheduledActivateError")


def test_parser_rejects_too_close_to_now(db: Session) -> None:
    """deadline + offset before now + SCHEDULED_OPERATIONAL_LEAD_HOURS rejected."""
    deadline = datetime.now(timezone.utc) + timedelta(minutes=30)
    try:
        scheduled_events.parse_and_validate_reminder_offsets(
            "-PT1H", deadline=deadline
        )
    except scheduled_events.ScheduledActivateError:
        pass
    else:
        raise AssertionError("expected ScheduledActivateError")


def test_parser_accepts_when_deadline_unset(db: Session) -> None:
    """Without deadline, only the parse-validity check runs (offsets inert)."""
    result = scheduled_events.parse_and_validate_reminder_offsets(
        "-P1D, -PT2H", deadline=None
    )
    assert result == ["-P1D", "-PT2H"]


# --------------------------------------------------------------------------- #
# Editor end-to-end                                                            #
# --------------------------------------------------------------------------- #


def test_create_accepts_reminder_offsets_with_valid_deadline(
    client: TestClient, db: Session
) -> None:
    deadline = datetime.now(timezone.utc) + timedelta(days=30)
    status_code, _, session_id = _create_session(
        client,
        "create-rem",
        deadline=_fmt_local_input(deadline),
        reminder_offsets="-P1D, -PT4H",
    )
    assert status_code == 303
    rs = db.get(ReviewSession, session_id)
    assert rs is not None
    assert rs.reminder_offsets == ["-P1D", "-PT4H"]


def test_create_rejects_invalid_reminder_offset(client: TestClient) -> None:
    deadline = datetime.now(timezone.utc) + timedelta(days=30)
    response = client.post(
        "/operator/sessions",
        data={
            "name": "x",
            "code": "create-bad-rem",
            "deadline": _fmt_local_input(deadline),
            "reminder_offsets": "-PT30M",  # less than 1hr notice gap
        },
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert "minimum reviewer notice" in response.text


def test_edit_round_trips_reminder_offsets(
    client: TestClient, db: Session
) -> None:
    _, _, session_id = _create_session(client, "edit-rem")
    deadline = datetime.now(timezone.utc) + timedelta(days=30)

    # Set
    response = client.post(
        f"/operator/sessions/{session_id}/edit",
        data={
            "name": "Sess edit-rem",
            "code": "edit-rem",
            "deadline": _fmt_local_input(deadline),
            "reminder_offsets": "-P1D",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    rs = db.get(ReviewSession, session_id)
    assert rs.reminder_offsets == ["-P1D"]

    # Edit GET prefills the input value
    page = client.get(f"/operator/sessions/{session_id}/edit")
    assert page.status_code == 200
    assert 'name="reminder_offsets"' in page.text
    # The disabled attribute should be gone now.
    assert 'name="reminder_offsets"\n                     disabled' not in page.text
    assert "-P1D" in page.text

    # Clear
    client.post(
        f"/operator/sessions/{session_id}/edit",
        data={
            "name": "Sess edit-rem",
            "code": "edit-rem",
            "deadline": _fmt_local_input(deadline),
            "reminder_offsets": "",
        },
        follow_redirects=False,
    )
    db.refresh(rs)
    assert rs.reminder_offsets is None


def test_edit_emits_reminder_schedule_updated_audit(
    client: TestClient, db: Session
) -> None:
    _, _, session_id = _create_session(client, "audit-rem")
    deadline = datetime.now(timezone.utc) + timedelta(days=30)
    client.post(
        f"/operator/sessions/{session_id}/edit",
        data={
            "name": "x",
            "code": "audit-rem",
            "deadline": _fmt_local_input(deadline),
            "reminder_offsets": "-P1D",
        },
        follow_redirects=False,
    )
    audits = db.execute(
        select(AuditEvent)
        .where(AuditEvent.session_id == session_id)
        .where(AuditEvent.event_type == "session.reminder_schedule_updated")
    ).scalars().all()
    assert len(audits) == 1


# --------------------------------------------------------------------------- #
# Schedule timeline preview                                                    #
# --------------------------------------------------------------------------- #


def test_timeline_includes_end_and_reminder_offsets(db: Session) -> None:
    from app.db.models import User
    from app.schemas.sessions import SessionCreate
    from app.services import sessions as sessions_service

    op = User(email="op-tl-rem@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    rs = sessions_service.create_session(
        db,
        user=op,
        payload=SessionCreate(name="t", code="tl-rem", description="d"),
    )
    rs.deadline = datetime(2099, 6, 5, 17, 0, tzinfo=timezone.utc)
    rs.reminder_offsets = ["-PT4H", "-P1D"]
    db.flush()
    db.commit()

    rows = build_schedule_timeline(rs, "UTC")
    # 1 End row + 2 reminder rows = 3.
    assert len(rows) == 3
    # Earliest reminder (-P1D = 1 day before End) → first row.
    assert "Auto-send reminders" in rows[0]["label"]
    assert "-P1D" in rows[0]["label"]
    assert "Auto-send reminders" in rows[1]["label"]
    assert "-PT4H" in rows[1]["label"]
    assert "ends" in rows[2]["label"]


def test_timeline_combines_start_invites_reminders_end(db: Session) -> None:
    """Full lifecycle: Start + invites + reminders + End render together,
    sorted chronologically."""
    from app.db.models import User
    from app.schemas.sessions import SessionCreate
    from app.services import sessions as sessions_service

    op = User(email="op-tl-all@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    rs = sessions_service.create_session(
        db,
        user=op,
        payload=SessionCreate(name="t", code="tl-all", description="d"),
    )
    rs.scheduled_activate_at = datetime(
        2099, 6, 1, 9, 0, tzinfo=timezone.utc
    )
    rs.invite_offsets = ["-P1D"]
    rs.deadline = datetime(2099, 6, 5, 17, 0, tzinfo=timezone.utc)
    rs.reminder_offsets = ["-P1D"]
    db.flush()
    db.commit()

    rows = build_schedule_timeline(rs, "UTC")
    labels = [row["label"] for row in rows]
    # Order: invite (May 31), activate (Jun 1), reminder (Jun 4), end (Jun 5).
    assert "Auto-send invites" in labels[0]
    assert "activates" in labels[1]
    assert "Auto-send reminders" in labels[2]
    assert "ends" in labels[3]


# --------------------------------------------------------------------------- #
# Manage Invitations caption                                                   #
# --------------------------------------------------------------------------- #


def test_caption_none_without_offsets(db: Session) -> None:
    from app.db.models import User
    from app.schemas.sessions import SessionCreate
    from app.services import sessions as sessions_service

    op = User(email="op-rem-cap-empty@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    rs = sessions_service.create_session(
        db,
        user=op,
        payload=SessionCreate(name="t", code="rcap-empty", description="d"),
    )
    assert build_auto_send_reminders_caption(db, rs) is None


def test_caption_amber_grey_when_offsets_but_no_deadline(db: Session) -> None:
    from app.db.models import User
    from app.schemas.sessions import SessionCreate
    from app.services import sessions as sessions_service

    op = User(email="op-rem-cap-grey@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    rs = sessions_service.create_session(
        db,
        user=op,
        payload=SessionCreate(name="t", code="rcap-grey", description="d"),
    )
    rs.reminder_offsets = ["-P1D"]
    db.flush()
    db.commit()

    caption = build_auto_send_reminders_caption(db, rs)
    assert caption is not None
    assert caption["tone"] == "amber-grey"
    assert "no End to anchor against" in caption["text"]


def test_caption_amber_warning_when_not_ready(db: Session) -> None:
    """Offsets + deadline set, but session not yet ``ready`` → amber warn."""
    from app.db.models import User
    from app.schemas.sessions import SessionCreate
    from app.services import sessions as sessions_service

    op = User(email="op-rem-cap-amber@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    rs = sessions_service.create_session(
        db,
        user=op,
        payload=SessionCreate(name="t", code="rcap-amber", description="d"),
    )
    rs.deadline = datetime(2099, 6, 5, 17, 0, tzinfo=timezone.utc)
    rs.reminder_offsets = ["-P1D"]
    db.flush()
    db.commit()

    caption = build_auto_send_reminders_caption(db, rs)
    assert caption is not None
    assert caption["tone"] == "amber-warning"
    assert "activate the session" in caption["text"]


def test_caption_amber_warning_when_ready_but_no_invitations(
    db: Session,
) -> None:
    """Reminders piggyback on Invitation rows; with none created the
    trigger skips with reason=no_invitations — the caption should
    surface that as amber rather than misleading green."""
    from app.db.models import User
    from app.schemas.sessions import SessionCreate
    from app.services import sessions as sessions_service

    op = User(email="op-rem-cap-amber-ni@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    rs = sessions_service.create_session(
        db,
        user=op,
        payload=SessionCreate(name="t", code="rcap-amber-ni", description="d"),
    )
    rs.deadline = datetime(2099, 6, 5, 17, 0, tzinfo=timezone.utc)
    rs.reminder_offsets = ["-P1D"]
    rs.status = lifecycle.SessionStatus.ready.value
    db.flush()
    db.commit()

    caption = build_auto_send_reminders_caption(db, rs)
    assert caption is not None
    assert caption["tone"] == "amber-warning"
    assert "create invitations" in caption["text"]


def test_caption_green_when_ready_and_invitations_exist(
    db: Session,
) -> None:
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

    op = User(email="op-rem-cap-green@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    rs = sessions_service.create_session(
        db,
        user=op,
        payload=SessionCreate(name="t", code="rcap-green", description="d"),
    )
    reviewer = Reviewer(
        session_id=rs.id, name="A", email="a-rcap-green@example.edu"
    )
    reviewee = Reviewee(
        session_id=rs.id,
        name="C",
        email_or_identifier="c-rcap-green@example.edu",
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

    rs.deadline = datetime(2099, 6, 5, 17, 0, tzinfo=timezone.utc)
    rs.reminder_offsets = ["-P1D"]
    rs.status = lifecycle.SessionStatus.ready.value
    db.flush()
    db.commit()

    caption = build_auto_send_reminders_caption(db, rs)
    assert caption is not None
    assert caption["tone"] == "green"
    assert "dispatch automatically" in caption["text"]


# --------------------------------------------------------------------------- #
# Workflow-card right-column rendering (Manage Invitations no longer hosts)   #
# --------------------------------------------------------------------------- #


def test_caption_renders_on_workflow_card_not_invitations_page(
    client: TestClient, db: Session
) -> None:
    """The auto-send reminders caption is now part of the Workflow
    card's right-column aside (consolidated 2026-05-21); the
    Invitations page no longer renders it as a standalone banner."""
    deadline = datetime.now(timezone.utc) + timedelta(days=30)
    _, _, session_id = _create_session(
        client,
        "rcap-loc",
        deadline=_fmt_local_input(deadline),
        reminder_offsets="-P1D",
    )
    rs = db.get(ReviewSession, session_id)
    assert rs.reminder_offsets == ["-P1D"]

    body = client.get(f"/operator/sessions/{session_id}/invitations").text
    # New caption id sits inside the Workflow card right column.
    assert 'id="next-action-auto-send-reminders-caption"' in body
    # Old standalone caption id is gone from the Invitations page.
    assert 'id="auto-send-reminders-caption"' not in body
