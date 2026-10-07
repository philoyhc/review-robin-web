"""Findings Bc1 (ruled 2026-10-07): an auto-send entry already fired on
the anchor it keeps stays at its list position.

The invite and reminder observers record a fired entry by its index on
its anchor, so a Save that changes, removes or shifts that entry would
leave a later one on a position that reads as already sent, and it
would never fire. Such a Save is refused; appending after it, or moving
the anchor (which resets the record), is not."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession
from app.services.date_formatting import format_datetime_local
from app.services.scheduled_events import _ensure_aware_utc


def _session(
    client: TestClient, db: Session, code: str, *, kind: str
) -> ReviewSession:
    """A draft with Start five days out and End six, two offsets on the
    ``kind`` list, and the first of them recorded as fired."""
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
    session.scheduled_activate_at = now + timedelta(days=5)
    session.deadline = now + timedelta(days=6)
    setattr(session, f"{kind}_offsets", ["-P3D", "-P1D"])
    anchor = (
        session.scheduled_activate_at if kind == "invite" else session.deadline
    )
    db.add(
        AuditEvent(
            session_id=session.id,
            event_type=f"session.scheduled_{kind}s_fired",
            summary="fired",
            detail={
                "context": {
                    "anchor_at": _ensure_aware_utc(anchor).isoformat(),
                    "offset_index": 0,
                    "offset": "-P3D",
                }
            },
        )
    )
    db.commit()
    return session


def _save(
    client: TestClient,
    session: ReviewSession,
    *,
    kind: str,
    offsets: str,
    start: datetime | None = None,
):
    return client.post(
        f"/operator/sessions/{session.id}/config",
        data={
            "name": session.name,
            "code": session.code,
            "display_timezone": "UTC",
            "scheduled_activate_at": format_datetime_local(
                start or session.scheduled_activate_at, "UTC"
            ),
            "deadline": format_datetime_local(session.deadline, "UTC"),
            "invite_offsets": offsets if kind == "invite" else "",
            "reminder_offsets": offsets if kind == "reminder" else "",
        },
        follow_redirects=False,
    )


KINDS = ("invite", "reminder")


def test_removing_a_fired_entry_is_refused(
    client: TestClient, db: Session
) -> None:
    for kind in KINDS:
        session = _session(client, db, f"bc1-remove-{kind}", kind=kind)
        response = _save(client, session, kind=kind, offsets="-P1D")
        assert response.status_code == 422, kind
        assert "-P3D has already fired" in response.text
        db.expire_all()
        assert getattr(session, f"{kind}_offsets") == ["-P3D", "-P1D"]


def test_inserting_before_a_fired_entry_is_refused(
    client: TestClient, db: Session
) -> None:
    for kind in KINDS:
        session = _session(client, db, f"bc1-insert-{kind}", kind=kind)
        response = _save(
            client, session, kind=kind, offsets="-P4D, -P3D, -P1D"
        )
        assert response.status_code == 422, kind
        assert "keep it at position 1" in response.text


def test_changing_a_fired_entry_is_refused(
    client: TestClient, db: Session
) -> None:
    session = _session(client, db, "bc1-change", kind="invite")
    response = _save(client, session, kind="invite", offsets="-P2D, -P1D")
    assert response.status_code == 422
    assert "Auto-send invite -P3D has already fired for this Start" in (
        response.text
    )


def test_keeping_a_fired_entry_and_editing_after_it_saves(
    client: TestClient, db: Session
) -> None:
    for kind in KINDS:
        session = _session(client, db, f"bc1-append-{kind}", kind=kind)
        response = _save(
            client, session, kind=kind, offsets="-P3D, -P2D, -PT12H"
        )
        assert response.status_code == 303, (kind, response.text)
        db.expire_all()
        assert getattr(session, f"{kind}_offsets") == ["-P3D", "-P2D", "-PT12H"]


def test_moving_the_anchor_frees_the_list(
    client: TestClient, db: Session
) -> None:
    """A new Start resets the fired record, so the entry can go."""
    session = _session(client, db, "bc1-new-start", kind="invite")
    new_start = session.scheduled_activate_at + timedelta(hours=1)
    response = _save(
        client, session, kind="invite", offsets="-P1D", start=new_start
    )
    assert response.status_code == 303, response.text
