"""Segment 20K — an instrument picks how its response fields are laid out.

``Instrument.response_layout`` is ``columns`` (a column per response
field; the default) or ``stacked`` (one field per line in a single
cell). Rung 2 stores it: the setter, its audit event and the revert of a
validated session, Replicate, Duplicate and the Settings CSV. Rung 3
adds the instrument card's *Responses* chip, which both Saves store; the
preview does not follow it yet.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Instrument, ReviewSession, User
from app.db.models.instrument import RESPONSE_LAYOUT_DEFAULT, RESPONSE_LAYOUTS
from app.services import session_clone
from app.services.instruments import (
    ResponseLayoutError,
    effective_response_layout,
    ensure_default_instrument,
    is_untouched_default,
    replicate_instrument,
    set_response_layout,
)
from app.services.session_config_io import (
    Row,
    apply_session_config,
    serialize_session_config,
)
from app.web.views._instruments import RESPONSE_LAYOUT_CHOICES

from ._lookups import must_get


def _seed(db: Session, *, code: str) -> tuple[User, ReviewSession, Instrument]:
    user = User(email=f"op-{code}@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(name="20K", code=code, created_by_user_id=user.id)
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
            .where(AuditEvent.event_type == "instrument.response_layout_set")
            .order_by(AuditEvent.id)
        ).scalars()
    )


def test_columns_is_the_default_and_first_in_the_cycle() -> None:
    assert RESPONSE_LAYOUTS == ("columns", "stacked")
    assert RESPONSE_LAYOUT_DEFAULT == "columns"


def test_a_new_instrument_takes_columns(db: Session) -> None:
    _, _, instrument = _seed(db, code="20k-default")
    assert instrument.response_layout == "columns"


def test_a_stray_stored_value_reads_as_columns() -> None:
    assert effective_response_layout(Instrument(response_layout="stacked")) == "stacked"
    assert effective_response_layout(Instrument(response_layout="sideways")) == "columns"


def test_the_setter_stores_audits_and_skips_a_no_op(db: Session) -> None:
    user, _, instrument = _seed(db, code="20k-setter")
    set_response_layout(db, instrument=instrument, layout="stacked", actor=user)
    set_response_layout(db, instrument=instrument, layout="stacked", actor=user)
    db.commit()
    assert instrument.response_layout == "stacked"
    events = _layout_events(db)
    assert len(events) == 1
    assert events[0].detail is not None
    assert events[0].detail["changes"] == {"response_layout": ["columns", "stacked"]}
    assert events[0].detail["refs"] == {"instrument_id": instrument.id}


def test_the_setter_refuses_an_unknown_layout(db: Session) -> None:
    user, _, instrument = _seed(db, code="20k-unknown")
    with pytest.raises(ResponseLayoutError):
        set_response_layout(db, instrument=instrument, layout="sideways", actor=user)
    assert instrument.response_layout == "columns"
    assert _layout_events(db) == []


def test_a_change_reverts_a_validated_session_and_a_no_op_does_not(db: Session) -> None:
    user, review_session, instrument = _seed(db, code="20k-validated")
    review_session.status = "validated"
    db.commit()
    set_response_layout(db, instrument=instrument, layout="columns", actor=user)
    assert review_session.status == "validated"
    set_response_layout(db, instrument=instrument, layout="stacked", actor=user)
    db.commit()
    assert review_session.status == "draft"
    invalidated = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "session.invalidated")
    ).scalar_one()
    assert invalidated.detail is not None
    assert invalidated.detail["reason"] == "instrument_response_layout_set"


def test_a_stacked_instrument_is_not_the_untouched_default(db: Session) -> None:
    _, _, instrument = _seed(db, code="20k-untouched")
    assert is_untouched_default(instrument)
    instrument.response_layout = "stacked"
    assert not is_untouched_default(instrument)


def test_replicate_carries_the_layout(db: Session) -> None:
    user, review_session, instrument = _seed(db, code="20k-repl")
    instrument.response_layout = "stacked"
    db.commit()
    replica = replicate_instrument(db, review_session=review_session, source=instrument, actor=user)
    assert replica.response_layout == "stacked"


def test_duplicate_carries_each_instruments_layout(db: Session) -> None:
    user, review_session, first = _seed(db, code="20k-dup")
    second = Instrument(session_id=review_session.id, name="Second", order=1)
    db.add(second)
    db.flush()
    first.response_layout = "stacked"
    db.commit()
    clone = session_clone.clone_session(db, source=review_session, user=user, mode="config")
    layouts = dict(
        db.execute(
            select(Instrument.name, Instrument.response_layout).where(
                Instrument.session_id == clone.id
            )
        ).all()
    )
    assert layouts == {first.name: "stacked", "Second": "columns"}


def test_settings_csv_round_trip_carries_each_instruments_layout(db: Session) -> None:
    _, source, first = _seed(db, code="20k-csv-src")
    second = Instrument(session_id=source.id, name="Second", order=1)
    db.add(second)
    db.flush()
    first.response_layout = "stacked"
    db.commit()

    rows = serialize_session_config(db, source)
    by_field = {r.field: r for r in rows}
    assert by_field["instruments[1].response_layout"] == Row(
        "instruments[1].response_layout", "stacked", "enum"
    )
    assert by_field["instruments[2].response_layout"].value == "columns"

    destination = _bare(db, "20k-csv-dst")
    result = apply_session_config(db, destination, rows)
    assert result.ok, result.errors
    layouts = [
        layout
        for (layout,) in db.execute(
            select(Instrument.response_layout)
            .where(Instrument.session_id == destination.id)
            .order_by(Instrument.order)
        ).all()
    ]
    assert layouts == ["stacked", "columns"]


def test_an_older_settings_csv_takes_the_default(db: Session) -> None:
    destination = _bare(db, "20k-csv-old")
    result = apply_session_config(db, destination, [Row("instruments[1].name", "Eval", "string")])
    assert result.ok, result.errors
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == destination.id)
    ).scalar_one()
    assert instrument.response_layout == "columns"


def test_the_settings_csv_refuses_an_unknown_layout(db: Session) -> None:
    destination = _bare(db, "20k-csv-bad")
    result = apply_session_config(
        db,
        destination,
        [
            Row("instruments[1].name", "Eval", "string"),
            Row("instruments[1].response_layout", "sideways", "enum"),
        ],
    )
    assert not result.ok
    assert any("response_layout" in str(error) for error in result.errors)


def test_a_stray_stored_value_exports_as_columns(db: Session) -> None:
    _, review_session, instrument = _seed(db, code="20k-stray")
    instrument.response_layout = "sideways"
    db.commit()
    rows = serialize_session_config(db, review_session)
    assert {r.field: r.value for r in rows}["instruments[1].response_layout"] == "columns"


# --- Rung 3: the Responses chip ----------------------------------------


def _make_session(client: TestClient, db: Session, *, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Responses", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(select(ReviewSession).where(ReviewSession.code == code)).scalar_one()


def _instrument(db: Session, review_session: ReviewSession) -> Instrument:
    return db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()


def _flat_page(client: TestClient, review_session: ReviewSession) -> str:
    return " ".join(
        client.get(f"/operator/sessions/{review_session.public_id}/instruments").text.split()
    )


def test_the_chip_vocabulary_follows_the_model() -> None:
    assert tuple(c["value"] for c in RESPONSE_LAYOUT_CHOICES) == RESPONSE_LAYOUTS
    assert [c["label"] for c in RESPONSE_LAYOUT_CHOICES] == [
        "Responses across",
        "Responses stacked",
    ]


def test_the_chip_sits_after_the_layout_chip_and_before_refresh(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="20k-card")
    instrument = _instrument(db, review_session)
    instrument.response_layout = "stacked"
    db.commit()
    flat = _flat_page(client, review_session)
    heading = flat.index("Preview review instrument</h3>")
    layout_chip = re.search(r"<span [^>]*data-intro-layout-chip[^>]*>", flat)
    chip = re.search(r"<span [^>]*data-response-layout-chip[^>]*>([^<]*)</span>", flat)
    refresh = flat.index("Refresh sample", heading)
    assert layout_chip is not None and chip is not None
    assert heading < layout_chip.start() < chip.start() < refresh
    assert chip.group(1) == "Responses stacked"
    assert 'role="button"' in chip.group(0)
    # The card renders locked: out of the tab order, read disabled.
    assert 'aria-disabled="true"' in chip.group(0)
    assert "tabindex" not in chip.group(0)
    assert re.search(
        rf'<input type="hidden" form="dfsave-{instrument.id}" name="response_layout" '
        r'value="stacked" autocomplete="off" data-response-layout-input>',
        flat,
    )


def test_a_stray_stored_value_reads_as_responses_across_on_the_card(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="20k-card-stray")
    instrument = _instrument(db, review_session)
    instrument.response_layout = "sideways"
    db.commit()
    flat = _flat_page(client, review_session)
    chip = re.search(r"<span [^>]*data-response-layout-chip[^>]*>([^<]*)</span>", flat)
    assert chip is not None and chip.group(1) == "Responses across"
    assert 'name="response_layout" value="columns"' in flat


@pytest.mark.parametrize("path", ["fields/save", "save"])
def test_both_saves_store_the_layout(client: TestClient, db: Session, path: str) -> None:
    review_session = _make_session(client, db, code=f"20k-{path.replace('/', '-')}")
    instrument = _instrument(db, review_session)
    response = client.post(
        f"/operator/sessions/{review_session.public_id}/instruments/{instrument.id}/{path}",
        data={"response_layout": "stacked"},
        follow_redirects=False,
    )
    assert response.status_code in (200, 303), response.text
    db.expire_all()
    assert must_get(db, Instrument, instrument.id).response_layout == "stacked"
    assert len(_layout_events(db)) == 1


@pytest.mark.parametrize("path", ["fields/save", "save"])
def test_a_save_without_the_input_keeps_the_layout(
    client: TestClient, db: Session, path: str
) -> None:
    review_session = _make_session(client, db, code=f"20k-keep-{path.replace('/', '-')}")
    instrument = _instrument(db, review_session)
    instrument.response_layout = "stacked"
    db.commit()
    response = client.post(
        f"/operator/sessions/{review_session.public_id}/instruments/{instrument.id}/{path}",
        data={},
        follow_redirects=False,
    )
    assert response.status_code in (200, 303), response.text
    db.expire_all()
    assert must_get(db, Instrument, instrument.id).response_layout == "stacked"


@pytest.mark.parametrize(("path", "status_code"), [("fields/save", 400), ("save", 422)])
def test_both_saves_refuse_an_unknown_layout(
    client: TestClient, db: Session, path: str, status_code: int
) -> None:
    review_session = _make_session(client, db, code=f"20k-bad-{path.replace('/', '-')}")
    instrument = _instrument(db, review_session)
    response = client.post(
        f"/operator/sessions/{review_session.public_id}/instruments/{instrument.id}/{path}",
        data={"response_layout": "sideways", "short_label": "Changed"},
        follow_redirects=False,
    )
    assert response.status_code == status_code
    db.expire_all()
    stored = must_get(db, Instrument, instrument.id)
    assert stored.response_layout == "columns"
    assert stored.short_label != "Changed"


# --- Rung 5: the stacked layout's two widths ---------------------------


def test_set_column_widths_keeps_the_stack_widths(db: Session) -> None:
    from app.services.instruments import set_column_widths

    user, _, instrument = _seed(db, code="20k-widths")
    set_column_widths(
        db,
        instrument=instrument,
        widths={"stack_label": 180, "stack_input": 5000, "stack_other": 90},
        actor=user,
    )
    db.commit()
    # Clamped as every width is; an unknown key is dropped.
    assert instrument.column_widths == {"stack_label": 180, "stack_input": 1200}


def test_the_settings_csv_carries_the_stack_widths(db: Session) -> None:
    _, source, instrument = _seed(db, code="20k-widths-src")
    instrument.response_layout = "stacked"
    instrument.column_widths = {"stack_label": 180, "stack_input": 400}
    db.commit()
    rows = serialize_session_config(db, source)
    destination = _bare(db, "20k-widths-dst")
    result = apply_session_config(db, destination, rows)
    assert result.ok, result.errors
    copied = db.execute(
        select(Instrument).where(Instrument.session_id == destination.id)
    ).scalar_one()
    assert copied.column_widths == {"stack_label": 180, "stack_input": 400}


def test_the_card_carries_the_stack_widths_for_its_preview(client: TestClient, db: Session) -> None:
    review_session = _make_session(client, db, code="20k-widths-card")
    instrument = _instrument(db, review_session)
    instrument.column_widths = {"stack_label": 180, "stack_input": 400}
    db.commit()
    flat = _flat_page(client, review_session)
    assert 'data-new-model-band2-stack-label-width="180"' in flat
    assert 'data-new-model-band2-stack-input-width="400"' in flat
