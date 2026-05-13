"""Bulk `responses_visible_when_closed` toggle on the Instruments page.

Backfills integration coverage for `bulk_set_visibility`
(`POST /sessions/{id}/instruments/visibility/all-on` /
`/visibility/all-off`) and the
`instruments.bulk_visibility_when_closed` audit event — the one
10C-shipped surface that didn't pick up integration tests during
Segment 10D's backfill (see `guide/unfinished_business.md` item
#15, post-2026-05-02 re-audit).
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Instrument, ReviewSession
from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


def _create_session(
    client: TestClient, db: Session, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Bulk Visibility", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _populate_rosters(client: TestClient, db: Session, session_id: int) -> None:
    client.post(
        f"/operator/sessions/{session_id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nRae,rae@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{session_id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    pin_full_matrix_on_all_instruments(db, session_id)
    generate_via_page_button(client, session_id)


def _add_instrument(
    client: TestClient, db: Session, session_id: int, after_id: int
) -> Instrument:
    client.post(
        f"/operator/sessions/{session_id}/instruments/add",
        data={"after": str(after_id)},
        follow_redirects=False,
    )
    return list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == session_id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )[-1]


def _instruments(db: Session, session_id: int) -> list[Instrument]:
    return list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == session_id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )


def _bulk_visibility_events(
    db: Session, session_id: int
) -> list[AuditEvent]:
    return list(
        db.execute(
            select(AuditEvent)
            .where(
                AuditEvent.event_type == "instruments.bulk_visibility_when_closed"
            )
            .where(AuditEvent.session_id == session_id)
            .order_by(AuditEvent.id)
        ).scalars()
    )


def test_bulk_visibility_all_on_flips_mixed_state_and_emits_audit(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="bv-on")
    [default] = _instruments(db, session.id)
    second = _add_instrument(client, db, session.id, after_id=default.id)
    # Default state: both False. Toggle just the second to True so the
    # initial state is mixed.
    second.responses_visible_when_closed = True
    db.commit()

    response = client.post(
        f"/operator/sessions/{session.id}/instruments/visibility/all-on",
        follow_redirects=False,
    )
    assert response.status_code == 303

    instruments = _instruments(db, session.id)
    assert all(inst.responses_visible_when_closed for inst in instruments)

    [event] = _bulk_visibility_events(db, session.id)
    assert event.detail["context"]["target"] is True
    assert event.detail["session_id"] == session.id
    # Only the previously-False instrument is in the changed list — the
    # second was already True so it's a no-op for that row.
    assert event.detail["set_changes"]["updated"] == [
        {"instrument_id": default.id}
    ]


def test_bulk_visibility_all_off_flips_to_false_and_emits_audit(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="bv-off")
    [default] = _instruments(db, session.id)
    second = _add_instrument(client, db, session.id, after_id=default.id)
    # Walk both to True via the route, then test that all-off flips them
    # back.
    client.post(
        f"/operator/sessions/{session.id}/instruments/visibility/all-on",
        follow_redirects=False,
    )
    db.refresh(default)
    db.refresh(second)
    assert default.responses_visible_when_closed is True
    assert second.responses_visible_when_closed is True

    response = client.post(
        f"/operator/sessions/{session.id}/instruments/visibility/all-off",
        follow_redirects=False,
    )
    assert response.status_code == 303

    instruments = _instruments(db, session.id)
    assert not any(inst.responses_visible_when_closed for inst in instruments)

    events = _bulk_visibility_events(db, session.id)
    assert len(events) == 2
    on_event, off_event = events
    assert on_event.detail["context"]["target"] is True
    assert off_event.detail["context"]["target"] is False
    assert sorted(
        e["instrument_id"] for e in off_event.detail["set_changes"]["updated"]
    ) == sorted([default.id, second.id])


def test_bulk_visibility_is_idempotent_no_audit_when_already_target(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="bv-noop")
    [default] = _instruments(db, session.id)
    _add_instrument(client, db, session.id, after_id=default.id)
    # Walk both to True. That writes one audit row.
    client.post(
        f"/operator/sessions/{session.id}/instruments/visibility/all-on",
        follow_redirects=False,
    )
    assert len(_bulk_visibility_events(db, session.id)) == 1

    # A second all-on call is a no-op — the service only writes when
    # `changed` is non-empty.
    response = client.post(
        f"/operator/sessions/{session.id}/instruments/visibility/all-on",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert len(_bulk_visibility_events(db, session.id)) == 1


def test_bulk_visibility_does_not_invalidate_validated_session(
    client: TestClient, db: Session
) -> None:
    """Pins the visibility-when-closed exemption from the
    ``validated → draft`` rule. Settled 2026-05-02 (PR for items
    #3 + #16): visibility-when-closed is a display flag, not part
    of the validation snapshot. The exemption is documented in
    code at ``app/services/instruments.py::bulk_set_visibility``
    and ``app/services/session_lifecycle.py::set_responses_visible_when_closed``.
    """
    session = _create_session(client, db, code="bv-validated")
    _populate_rosters(client, db, session.id)
    response = client.get(f"/operator/sessions/{session.id}?validated=1")
    assert response.status_code == 200
    db.refresh(session)
    assert session.status == "validated"

    response = client.post(
        f"/operator/sessions/{session.id}/instruments/visibility/all-on",
        follow_redirects=False,
    )
    assert response.status_code == 303

    db.refresh(session)
    assert session.status == "validated"

    # No `session.invalidated` audit event should fire either.
    inv = db.execute(
        select(AuditEvent)
        .where(AuditEvent.event_type == "session.invalidated")
        .where(AuditEvent.session_id == session.id)
    ).all()
    assert inv == []
