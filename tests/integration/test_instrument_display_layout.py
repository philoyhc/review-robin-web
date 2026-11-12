"""Segment 20M rung 3 — where an instrument's display fields sit.

``Instrument.display_layout`` is ``across`` (a column per display field;
the default), ``stacked`` or ``joined`` (under the reviewee). This rung
stores it: the setter, its audit event and the revert of a validated
session, Replicate, Duplicate and the Settings CSV. Nothing renders it. Rung 4 adds
Band 3's *Display fields* chip, which both Saves store.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Instrument, ReviewSession, User
from app.db.models.instrument import DISPLAY_LAYOUT_DEFAULT, DISPLAY_LAYOUTS
from app.services import session_clone
from app.services.instruments import (
    DisplayLayoutError,
    effective_display_layout,
    ensure_default_instrument,
    is_untouched_default,
    replicate_instrument,
    set_display_layout,
)
from app.services.session_config_io import (
    Row,
    apply_session_config,
    serialize_session_config,
)
from app.web.views._instruments import DISPLAY_LAYOUT_CHOICES, display_layout_for

from ._lookups import must_get


def _seed(db: Session, *, code: str) -> tuple[User, ReviewSession, Instrument]:
    user = User(email=f"op-{code}@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(name="20M", code=code, created_by_user_id=user.id)
    db.add(review_session)
    db.flush()
    instrument = ensure_default_instrument(db, review_session)
    db.commit()
    return user, review_session, instrument


def _bare(db: Session, code: str) -> ReviewSession:
    user = User(email=f"op-{code}@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(name=code, code=code, created_by_user_id=user.id)
    db.add(review_session)
    db.flush()
    return review_session


def _layout_events(db: Session) -> list[AuditEvent]:
    return list(
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.event_type == "instrument.display_layout_set")
            .order_by(AuditEvent.id)
        ).scalars()
    )


def test_across_is_the_default_and_first_in_the_cycle() -> None:
    assert DISPLAY_LAYOUTS == ("across", "stacked", "joined")
    assert DISPLAY_LAYOUT_DEFAULT == "across"


def test_a_new_instrument_takes_across(db: Session) -> None:
    _, _, instrument = _seed(db, code="20m-default")
    assert instrument.display_layout == "across"


def test_a_stray_stored_value_reads_as_across() -> None:
    assert effective_display_layout(Instrument(display_layout="stacked")) == "stacked"
    assert effective_display_layout(Instrument(display_layout="sideways")) == "across"


def test_the_setter_stores_audits_and_skips_a_no_op(db: Session) -> None:
    user, _, instrument = _seed(db, code="20m-setter")
    set_display_layout(db, instrument=instrument, layout="stacked", actor=user)
    set_display_layout(db, instrument=instrument, layout="stacked", actor=user)
    db.commit()
    assert instrument.display_layout == "stacked"
    events = _layout_events(db)
    assert len(events) == 1
    assert events[0].detail is not None
    assert events[0].detail["changes"] == {"display_layout": ["across", "stacked"]}
    assert events[0].detail["refs"] == {"instrument_id": instrument.id}


def test_the_setter_refuses_an_unknown_layout(db: Session) -> None:
    user, _, instrument = _seed(db, code="20m-unknown")
    with pytest.raises(DisplayLayoutError):
        set_display_layout(db, instrument=instrument, layout="sideways", actor=user)
    assert instrument.display_layout == "across"
    assert _layout_events(db) == []


def test_a_change_reverts_a_validated_session_and_a_no_op_does_not(db: Session) -> None:
    user, review_session, instrument = _seed(db, code="20m-validated")
    review_session.status = "validated"
    db.commit()
    set_display_layout(db, instrument=instrument, layout="across", actor=user)
    assert review_session.status == "validated"
    set_display_layout(db, instrument=instrument, layout="stacked", actor=user)
    db.commit()
    assert review_session.status == "draft"
    invalidated = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "session.invalidated")
    ).scalar_one()
    assert invalidated.detail is not None
    assert invalidated.detail["reason"] == "instrument_display_layout_set"


def test_a_stacked_instrument_is_not_the_untouched_default(db: Session) -> None:
    _, _, instrument = _seed(db, code="20m-untouched")
    assert is_untouched_default(instrument)
    instrument.display_layout = "stacked"
    assert not is_untouched_default(instrument)


def test_replicate_carries_the_layout(db: Session) -> None:
    user, review_session, instrument = _seed(db, code="20m-repl")
    instrument.display_layout = "stacked"
    db.commit()
    replica = replicate_instrument(db, review_session=review_session, source=instrument, actor=user)
    assert replica.display_layout == "stacked"


def test_duplicate_carries_each_instruments_layout(db: Session) -> None:
    user, review_session, first = _seed(db, code="20m-dup")
    second = Instrument(session_id=review_session.id, name="Second", order=1)
    db.add(second)
    db.flush()
    first.display_layout = "stacked"
    db.commit()
    clone = session_clone.clone_session(db, source=review_session, user=user, mode="config")
    layouts = dict(
        db.execute(
            select(Instrument.name, Instrument.display_layout).where(
                Instrument.session_id == clone.id
            )
        ).all()
    )
    assert layouts == {first.name: "stacked", "Second": "across"}


def test_settings_csv_round_trip_carries_each_instruments_layout(db: Session) -> None:
    _, source, first = _seed(db, code="20m-csv-src")
    second = Instrument(session_id=source.id, name="Second", order=1)
    db.add(second)
    db.flush()
    first.display_layout = "stacked"
    db.commit()

    rows = serialize_session_config(db, source)
    by_field = {r.field: r for r in rows}
    assert by_field["instruments[1].display_layout"] == Row(
        "instruments[1].display_layout", "stacked", "enum"
    )
    assert by_field["instruments[2].display_layout"].value == "across"

    destination = _bare(db, "20m-csv-dst")
    result = apply_session_config(db, destination, rows)
    assert result.ok, result.errors
    layouts = [
        layout
        for (layout,) in db.execute(
            select(Instrument.display_layout)
            .where(Instrument.session_id == destination.id)
            .order_by(Instrument.order)
        ).all()
    ]
    assert layouts == ["stacked", "across"]


def test_an_older_settings_csv_takes_the_default(db: Session) -> None:
    destination = _bare(db, "20m-csv-old")
    result = apply_session_config(db, destination, [Row("instruments[1].name", "Eval", "string")])
    assert result.ok, result.errors
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == destination.id)
    ).scalar_one()
    assert instrument.display_layout == "across"


def test_the_settings_csv_refuses_an_unknown_layout(db: Session) -> None:
    destination = _bare(db, "20m-csv-bad")
    result = apply_session_config(
        db,
        destination,
        [
            Row("instruments[1].name", "Eval", "string"),
            Row("instruments[1].display_layout", "sideways", "enum"),
        ],
    )
    assert not result.ok
    assert any("display_layout" in str(error) for error in result.errors)


def test_a_stray_stored_value_exports_as_across(db: Session) -> None:
    _, review_session, instrument = _seed(db, code="20m-stray")
    instrument.display_layout = "sideways"
    db.commit()
    rows = serialize_session_config(db, review_session)
    assert {r.field: r.value for r in rows}["instruments[1].display_layout"] == "across"


# --- Rung 4: the Display fields chip -----------------------------------


def _make_session(client: TestClient, db: Session, *, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Display", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(select(ReviewSession).where(ReviewSession.code == code)).scalar_one()


def _instrument(db: Session, review_session: ReviewSession) -> Instrument:
    return db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()


def _chip(client: TestClient, review_session: ReviewSession) -> tuple[str, str]:
    flat = " ".join(
        client.get(f"/operator/sessions/{review_session.public_id}/instruments").text.split()
    )
    header = flat.index("Display fields</h3>")
    chip = re.search(r"<span [^>]*data-display-layout-chip[^>]*>([^<]*)</span>", flat)
    assert chip is not None and chip.start() > header
    return chip.group(1), flat


def test_the_chip_vocabulary_follows_the_model() -> None:
    assert tuple(c["value"] for c in DISPLAY_LAYOUT_CHOICES) == DISPLAY_LAYOUTS
    assert [c["label"] for c in DISPLAY_LAYOUT_CHOICES] == ["Across", "Stacked", "Joined"]


def test_the_chip_sits_right_of_the_header_and_carries_the_stored_value(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="20m-chip")
    instrument = _instrument(db, review_session)
    instrument.display_layout = "joined"
    db.commit()
    label, flat = _chip(client, review_session)
    assert label == "Joined"
    assert re.search(
        rf'<input type="hidden" form="dfsave-{instrument.id}" name="display_layout" '
        r'value="joined" autocomplete="off" data-display-layout-input>',
        flat,
    )


def test_a_group_instrument_shows_a_stored_across_as_joined_but_keeps_it(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="20m-chip-group")
    instrument = _instrument(db, review_session)
    instrument.group_kind = "r1"
    db.commit()
    label, flat = _chip(client, review_session)
    assert label == "Joined"
    # The stored value rides the Save until the operator cycles the chip.
    assert 'name="display_layout" value="across"' in flat
    assert display_layout_for(instrument) == "joined"


@pytest.mark.parametrize("path", ["fields/save", "save"])
def test_both_saves_store_the_layout(client: TestClient, db: Session, path: str) -> None:
    review_session = _make_session(client, db, code=f"20m-{path.replace('/', '-')}")
    instrument = _instrument(db, review_session)
    response = client.post(
        f"/operator/sessions/{review_session.public_id}/instruments/{instrument.id}/{path}",
        data={"display_layout": "stacked"},
        follow_redirects=False,
    )
    assert response.status_code in (200, 303), response.text
    db.expire_all()
    assert must_get(db, Instrument, instrument.id).display_layout == "stacked"
    assert len(_layout_events(db)) == 1


@pytest.mark.parametrize(("path", "status_code"), [("fields/save", 400), ("save", 422)])
def test_both_saves_refuse_an_unknown_layout(
    client: TestClient, db: Session, path: str, status_code: int
) -> None:
    review_session = _make_session(client, db, code=f"20m-bad-{path.replace('/', '-')}")
    instrument = _instrument(db, review_session)
    response = client.post(
        f"/operator/sessions/{review_session.public_id}/instruments/{instrument.id}/{path}",
        data={"display_layout": "sideways", "short_label": "Changed"},
        follow_redirects=False,
    )
    assert response.status_code == status_code
    db.expire_all()
    stored = must_get(db, Instrument, instrument.id)
    assert stored.display_layout == "across"
    assert stored.short_label != "Changed"
