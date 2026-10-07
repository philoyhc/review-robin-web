"""Findings Bc1 (ruled 2026-10-07): an auto-send entry already sent on
the anchor a save keeps stays at its list position.

The invite and reminder observers record a sent entry by its position on
its anchor, so a different entry on that position would never be sent.
A Save that puts one there is refused, by name, before the per-entry
rules; a sent entry kept in place skips the lead-time floor. The anchor
is two days out and the sent entry, ``-P3D``, resolved a day ago. (The
session stays in draft: the check reads the record whatever the state,
as a revert to draft keeps it.)"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession
from app.services.date_formatting import format_datetime_local
from app.services.scheduled_events import _ensure_aware_utc

KINDS = ("invite", "reminder")


def _session(
    client: TestClient, db: Session, code: str, *, kind: str
) -> ReviewSession:
    """The ``kind`` list's anchor two days out (Start a day before End
    for reminders, End a day after Start for invites); ``[-P3D, -P1D]``
    on that list, the first recorded as sent on its anchor."""
    client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    session.display_timezone = "UTC"
    two_days = now + timedelta(days=2)
    session.scheduled_activate_at = (
        two_days if kind == "invite" else two_days - timedelta(days=1)
    )
    session.deadline = (
        two_days + timedelta(days=1) if kind == "invite" else two_days
    )
    anchor = (
        session.scheduled_activate_at if kind == "invite" else session.deadline
    )
    setattr(session, f"{kind}_offsets", ["-P3D", "-P1D"])
    _record_sent(db, session, kind, anchor, "-P3D")
    db.commit()
    return session


def _record_sent(
    db: Session,
    session: ReviewSession,
    kind: str,
    anchor: datetime,
    entry: str,
    index: int = 0,
) -> None:
    db.add(
        AuditEvent(
            session_id=session.id,
            event_type=f"session.scheduled_{kind}s_fired",
            summary="sent",
            detail={
                "context": {
                    "anchor_at": _ensure_aware_utc(anchor).isoformat(),
                    "offset_index": index,
                    "offset": entry,
                }
            },
        )
    )


def _save(
    client: TestClient,
    session: ReviewSession,
    *,
    kind: str,
    offsets: str,
    anchor: datetime | None = None,
):
    start = session.scheduled_activate_at
    deadline = session.deadline
    if anchor is not None:
        if kind == "invite":
            start = anchor
        else:
            deadline = anchor
    return client.post(
        f"/operator/sessions/{session.id}/config",
        data={
            "name": session.name,
            "code": session.code,
            "display_timezone": "UTC",
            "scheduled_activate_at": format_datetime_local(start, "UTC"),
            "deadline": format_datetime_local(deadline, "UTC"),
            "invite_offsets": offsets if kind == "invite" else "",
            "reminder_offsets": offsets if kind == "reminder" else "",
        },
        follow_redirects=False,
    )


def test_removing_a_sent_entry_before_another_is_refused(
    client: TestClient, db: Session
) -> None:
    for kind in KINDS:
        session = _session(client, db, f"bc1-remove-{kind}", kind=kind)
        response = _save(client, session, kind=kind, offsets="-P1D")
        assert response.status_code == 422, kind
        assert "-P3D was already sent (or skipped) at position 1" in (
            response.text
        )
        db.expire_all()
        assert getattr(session, f"{kind}_offsets") == ["-P3D", "-P1D"]


def test_inserting_before_a_sent_entry_is_refused_by_name(
    client: TestClient, db: Session
) -> None:
    """Not as "leave more lead time": the moved -P3D is in the past, but
    the operator is told what actually went wrong."""
    for kind in KINDS:
        session = _session(client, db, f"bc1-insert-{kind}", kind=kind)
        response = _save(
            client, session, kind=kind, offsets="-P1DT12H, -P3D, -P1D"
        )
        assert response.status_code == 422, kind
        assert "so -P1DT12H there would never be sent" in response.text
        assert "lead time" not in response.text


def test_keeping_a_sent_entry_and_editing_after_it_saves(
    client: TestClient, db: Session
) -> None:
    for kind in KINDS:
        session = _session(client, db, f"bc1-append-{kind}", kind=kind)
        response = _save(
            client, session, kind=kind, offsets="-P3D, -P1DT12H, -PT12H"
        )
        assert response.status_code == 303, (kind, response.text)
        db.expire_all()
        assert getattr(session, f"{kind}_offsets") == [
            "-P3D", "-P1DT12H", "-PT12H"
        ]


def test_removing_only_trailing_sent_entries_saves(
    client: TestClient, db: Session
) -> None:
    """Clearing the list puts nothing on a sent position."""
    session = _session(client, db, "bc1-clear", kind="invite")
    assert _save(client, session, kind="invite", offsets="").status_code == 303


def test_a_new_anchor_frees_the_list_and_returning_restores_its_record(
    client: TestClient, db: Session
) -> None:
    """Start A → B drops the sent -P3D; back to A, A's record applies
    again, so -P1D can't take its position. Putting -P3D back is allowed
    even though it is past: it was sent there."""
    session = _session(client, db, "bc1-return", kind="invite")
    first_start = session.scheduled_activate_at
    other_start = first_start + timedelta(hours=1)
    assert (
        _save(client, session, kind="invite", offsets="-P1D", anchor=other_start)
        .status_code
        == 303
    )
    db.expire_all()
    back = _save(client, session, kind="invite", offsets="-P1D", anchor=first_start)
    assert back.status_code == 422
    assert "-P3D was already sent" in back.text
    restored = _save(
        client, session, kind="invite", offsets="-P3D, -P1D", anchor=first_start
    )
    assert restored.status_code == 303, restored.text


def test_a_save_that_leaves_the_schedule_alone_is_not_refused(
    client: TestClient, db: Session
) -> None:
    """A list already in conflict with the record (stored before this
    check, say) does not block a rename that leaves it and its anchor
    as stored: the B4 rule, never refused over stored state."""
    session = _session(client, db, "bc1-untouched", kind="invite")
    session.invite_offsets = ["-P1D"]
    db.commit()
    response = _save(client, session, kind="invite", offsets="-P1D")
    assert response.status_code == 303, response.text


def test_a_sent_position_past_the_lists_end_takes_no_new_entry(
    client: TestClient, db: Session
) -> None:
    """A position sent and then emptied (before this check) still never
    fires again, so an entry appended onto it is refused."""
    session = _session(client, db, "bc1-past-end", kind="invite")
    _record_sent(
        db, session, "invite", session.scheduled_activate_at, "-P1D", index=1
    )
    session.invite_offsets = ["-P3D"]
    db.commit()
    response = _save(
        client, session, kind="invite", offsets="-P3D, -PT12H"
    )
    assert response.status_code == 422
    assert "-P1D was already sent (or skipped) at position 2" in response.text


def test_the_lobby_cannot_move_end_back_onto_sent_reminders(
    client: TestClient, db: Session
) -> None:
    """The lobby expander edits End alone: moving it back to an End
    whose -P3D was sent, with -P1D now at that position, is refused
    there too."""
    session = _session(client, db, "bc1-lobby", kind="reminder")
    first_end = session.deadline
    other_end = first_end + timedelta(hours=1)
    moved = _save(
        client, session, kind="reminder", offsets="-P1D", anchor=other_end
    )
    assert moved.status_code == 303, moved.text
    db.expire_all()
    back = client.post(
        f"/operator/sessions/{session.id}/lobby-edit",
        data={
            "name": session.name,
            "code": session.code,
            "deadline": format_datetime_local(first_end, "UTC"),
            "tags": "",
        },
        follow_redirects=False,
    )
    assert back.status_code == 422
    assert "-P3D was already sent" in back.text
