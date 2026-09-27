"""19T Item 11 rung 4 — an operator can mark a governed field required,
on the card and through the settings CSV, when the instrument has an
active required field outside any branch (the author's ruling on the
item's pre-positioning 4). Item 10's guards are gone."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument
from app.services.responses._branching import REQUIRED_GOVERNED_NEEDS_ANCHOR_MESSAGE
from app.services.session_config_io import Row, apply_session_config, serialize_session_config

from .test_instrument_builder_routes import _card_slice
from .test_response_field_branching_builder import _page, _row, _rows_table
from .test_response_field_branching_roundtrip import (
    _branched_instrument,
    _fields,
    _session,
)
from .test_response_field_branching_save import _branched, _rfs, _save


def test_the_card_saves_a_required_governed_field(
    client: TestClient, db: Session
) -> None:
    review_session, instrument, rating, comments = _branched(client, db, "rg-save")
    assert rating.required
    response = _save(
        client, review_session, instrument, _rfs(instrument, Comments={"required": True})
    )
    assert response.status_code == 200, response.text
    db.expire_all()
    assert comments.required is True
    assert comments.branch_parent_id == rating.id


def test_the_anchor_can_be_any_active_required_field(
    client: TestClient, db: Session
) -> None:
    """Not only the parent: with Rating optional, another active required
    field outside the branch will do, and hiding it is refused."""
    review_session, instrument, rating, comments = _branched(client, db, "rg-anchor")
    rfs = _rfs(instrument, Rating={"required": False}, Comments={"required": True})
    rfs.append({"name": "Overall", "data_type": "string", "required": True, "selected": True})
    response = _save(client, review_session, instrument, rfs)
    assert response.status_code == 200, response.text
    db.expire_all()
    assert (rating.required, comments.required) == (False, True)

    rfs = _rfs(instrument, Overall={"selected": False})
    response = _save(client, review_session, instrument, rfs)
    assert response.status_code == 422
    assert response.json()["errors"] == [
        f"Comments: {REQUIRED_GOVERNED_NEEDS_ANCHOR_MESSAGE}"
    ]


def test_the_settings_csv_round_trips_a_required_governed_field(db: Session) -> None:
    source, _ = _session(db, "rg-csv-src")
    instrument = _branched_instrument(db, source)
    fields = _fields(db, instrument.id)
    fields["colour"].required = True
    fields["why"].required = True
    db.flush()
    rows = [r for r in serialize_session_config(db, source) if r.field.startswith("instruments")]
    target, _ = _session(db, "rg-csv-dst")
    result = apply_session_config(db, target, rows)
    assert result.errors == []
    copied = _fields(
        db,
        db.execute(select(Instrument.id).where(Instrument.session_id == target.id)).scalar_one(),
    )
    assert (copied["colour"].required, copied["why"].required) == (True, True)
    assert copied["why"].branch_parent_id == copied["colour"].id

    # Without the anchor, the parse phase names the field and nothing applies.
    unanchored = [
        Row(r.field, "false", r.data_type) if r.field.endswith("response_fields[1].required") else r
        for r in rows
    ]
    other, _ = _session(db, "rg-csv-bad")
    result = apply_session_config(db, other, unanchored)
    assert [e.message for e in result.errors] == [
        f"Why: {REQUIRED_GOVERNED_NEEDS_ANCHOR_MESSAGE}"
    ]
    assert db.execute(
        select(Instrument).where(Instrument.session_id == other.id)
    ).first() is None


def test_a_required_governed_row_renders_r_pressed(
    client: TestClient, db: Session
) -> None:
    review_session, instrument, _, _ = _page(client, db, "rg-builder")
    comments = next(f for f in instrument.response_fields if f.label == "Comments")
    comments.required = True
    db.commit()
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    governed = _row(_rows_table(_card_slice(" ".join(body.split()), instrument.id)), "Comments")
    r = re.search(r"<button[^>]*data-new-model-rf-required[^>]*>", governed).group(0)
    assert 'data-required="true"' in r and 'aria-pressed="true"' in r
    assert " disabled" not in r
