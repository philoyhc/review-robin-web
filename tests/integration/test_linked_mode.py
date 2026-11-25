"""A linked instrument's gate type (segment 23G rung 2,
`guide/segment_23G_linked_custom_instrument.md`): ``Instrument.linked_mode``,
``locked`` by default; the Settings row ``instruments[N].linked_mode``,
read and written only when not the default; and a linked application's
re-send owning the row, a change audited. No page reads it yet."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Instrument, ReviewSession, User
from app.db.models.instrument import LINKED_MODE_DEFAULT, LINKED_MODES
from app.services import linked_instruments
from app.services.instruments import ensure_default_instrument
from app.services.session_config_io import Row, apply_session_config, serialize_session_config
from utilityapps.interop_poc import mock

from ._lookups import detail_of
from .test_handoff_update import _created, _resend, _update_bundle, _with
from .test_handoffs import REVIEWEES, REVIEWERS


def _bare(db: Session, code: str) -> ReviewSession:
    user = User(email=f"op-{code}@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(name=code, code=code, created_by_user_id=user.id)
    db.add(review_session)
    db.flush()
    return review_session


def test_locked_is_the_default_and_the_two_modes_are_the_plan_s() -> None:
    assert LINKED_MODES == ("locked", "custom") and LINKED_MODE_DEFAULT == "locked"


def test_a_new_instrument_is_locked_and_writes_no_row(db: Session) -> None:
    review_session = _bare(db, "23g-new")
    instrument = ensure_default_instrument(db, review_session)
    db.commit()
    assert instrument.linked_mode == "locked"
    fields = {r.field for r in serialize_session_config(db, review_session)}
    assert "instruments[1].linked_mode" not in fields


def test_a_custom_instrument_round_trips_through_the_settings_csv(db: Session) -> None:
    source = _bare(db, "23g-src")
    ensure_default_instrument(db, source).linked_mode = "custom"
    db.commit()
    rows = serialize_session_config(db, source)
    assert Row("instruments[1].linked_mode", "custom", "enum") in rows
    destination = _bare(db, "23g-dst")
    result = apply_session_config(db, destination, rows)
    assert result.ok, result.errors
    got = db.scalars(select(Instrument).where(Instrument.session_id == destination.id)).one()
    assert got.linked_mode == "custom"


def test_the_settings_csv_refuses_an_unknown_mode(db: Session) -> None:
    result = apply_session_config(
        db,
        _bare(db, "23g-bad"),
        [
            Row("instruments[1].name", "Eval", "string"),
            Row("instruments[1].linked_mode", "open", "enum"),
        ],
    )
    assert not result.ok
    assert any("linked_mode" in str(error) for error in result.errors)


def test_the_application_owns_the_row() -> None:
    assert linked_instruments.owns_row("instruments[1].linked_mode")
    assert not linked_instruments.owns_row("instruments[2].linked_mode")


def _custom_settings() -> str:
    return mock.settings_csv() + "instruments[1].linked_mode,custom,enum\r\n"


def _typed(mode: str) -> str:
    """A re-send's settings carrying the type, with the gate's name the
    parse requires beside any instrument row."""
    return (
        "field,value,data_type\r\n"
        "instruments[1].name,Gate 2,string\r\n"
        f"instruments[1].linked_mode,{mode},enum\r\n"
    )


def test_a_create_takes_the_type_the_gate_sends(client: TestClient, db: Session) -> None:
    files = {"reviewers": REVIEWERS, "reviewees": REVIEWEES, "settings": _custom_settings()}
    _created(client, db, files=files)
    assert db.scalars(select(Instrument.linked_mode)).one() == "custom"


def test_a_resend_switches_the_type_audited_and_a_same_type_writes_nothing(
    client: TestClient, db: Session
) -> None:
    files = {"reviewers": REVIEWERS, "reviewees": REVIEWEES, "settings": mock.settings_csv()}
    _, created = _created(client, db, files=files)
    assert db.scalars(select(Instrument.linked_mode)).one() == "locked"
    typed = _typed("custom")
    reply = _resend(client, created, _update_bundle(files=_with(typed)))
    assert reply.status_code == 200, reply.text
    db.expire_all()
    instrument = db.scalars(select(Instrument)).one()
    assert instrument.linked_mode == "custom"
    # Nothing else of the instrument moved: its fields are as created.
    assert {f.field_key for f in instrument.response_fields} == {"score", "comment"}
    events = list(
        db.scalars(select(AuditEvent).where(AuditEvent.event_type == "instrument.linked_mode_set"))
    )
    assert len(events) == 1
    detail = detail_of(events[0])
    assert detail["changes"] == {"linked_mode": ["locked", "custom"]}
    assert detail["refs"] == {"instrument_id": instrument.id}
    again = _resend(client, created, _update_bundle(files=_with(typed)))
    assert again.status_code == 200, again.text
    assert (
        len(
            list(
                db.scalars(
                    select(AuditEvent).where(AuditEvent.event_type == "instrument.linked_mode_set")
                )
            )
        )
        == 1
    )


def test_a_resend_refuses_an_unknown_type(client: TestClient, db: Session) -> None:
    files = {"reviewers": REVIEWERS, "reviewees": REVIEWEES, "settings": mock.settings_csv()}
    _, created = _created(client, db, files=files)
    bad = _typed("open")
    reply = _resend(client, created, _update_bundle(files=_with(bad)))
    body = reply.json()
    assert reply.status_code == 422 and body["slot"] == "settings"
    assert any("linked_mode" in d for d in body["details"])
    db.expire_all()
    assert db.scalars(select(Instrument.linked_mode)).one() == "locked"
