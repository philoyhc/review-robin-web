"""19T Item 14 rung 4a — two levels become authorable on the server: the
card's Save and the settings CSV accept a branch inside a branch and
refuse a third level by name; answers anywhere lock every branch above
them; a hidden parent hides its whole subtree; Replicate copies the chain.

The chain: Familiarity (Integer, required, the anchor) > 0 governs Rating,
and Rating ≥ 4 governs Comments."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from fastapi.testclient import TestClient

from app.db.models import AuditEvent, Instrument, InstrumentResponseField
from app.services import instruments as instruments_service
from app.services.session_config_io import Row, apply_session_config, serialize_session_config

from .test_instrument_builder_routes import _band2_rfs, _new_model_with_tags
from .test_response_field_branching_roundtrip import _fields, _session
from .test_response_field_branching_save import _add_response, _rfs, _save

DEEP = "A branch inside a branch can't have a branch of its own."


def _chain_payload(instrument: Instrument, **changes: dict) -> list[dict]:
    """The card's payload building the chain on the default instrument:
    a new Familiarity row on top, Rating under it, Comments under Rating."""
    by_name = {rf["name"]: {**rf, "row_key": f"rf_{rf['id']}"} for rf in _band2_rfs(instrument)}
    familiarity = {
        "name": "Familiarity", "data_type": "integer", "min": "0", "max": "5", "step": "1",
        "list_options": "", "selected": True, "required": True, "help_text_visible": False,
        "help_text": "", "row_key": "rf_new", "branch_parent": None,
        "branch_op": "gt", "branch_value": "0", "branch_mode": None,
    }
    rating = {**by_name["Rating"], "branch_parent": "rf_new", "branch_op": "ge",
              "branch_value": "4", "branch_mode": None}
    comments = {**by_name["Comments"], "branch_parent": rating["row_key"],
                "branch_op": None, "branch_value": None, "branch_mode": None}
    out = []
    for entry in (familiarity, rating, comments):
        change = changes.get(entry["name"], {})
        if change is not None:
            out.append({**entry, **change})
    return out


def _chained(client: TestClient, db: Session, code: str):
    review_session, instrument = _new_model_with_tags(client, db, code=code)
    response = _save(client, review_session, instrument, _chain_payload(instrument))
    assert response.status_code == 200, response.text
    db.expire_all()
    fields = {f.label: f for f in instrument.response_fields}
    return review_session, instrument, fields


def test_the_cards_save_stores_and_audits_a_chain(client: TestClient, db: Session) -> None:
    review_session, instrument, fields = _chained(client, db, "two-level-save")
    familiarity, rating, comments = fields["Familiarity"], fields["Rating"], fields["Comments"]
    assert familiarity.branch_parent_id is None
    assert (familiarity.branch_op, familiarity.branch_value) == ("gt", "0")
    assert rating.branch_parent_id == familiarity.id
    assert (rating.branch_op, rating.branch_value) == ("ge", "4")
    assert comments.branch_parent_id == rating.id
    audited = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "instrument.field_updated")
    ).scalars().all()
    changed = {e.detail["context"]["field_key"] for e in audited if "branch_parent_id" in (e.detail.get("changes") or {})}
    assert {rating.field_key, comments.field_key} <= changed


def test_the_cards_save_refuses_a_third_level(client: TestClient, db: Session) -> None:
    review_session, instrument = _new_model_with_tags(client, db, code="two-level-deep")
    payload = _chain_payload(
        instrument,
        Comments={"data_type": "integer", "min": "1", "max": "5", "step": "1",
                  "branch_op": "ge", "branch_value": "1"},
    )
    payload.append({
        "name": "Deeper", "data_type": "string", "min": "", "max": "", "step": "",
        "list_options": "", "selected": True, "required": False,
        "help_text_visible": False, "help_text": "", "row_key": "rf_deeper",
        "branch_parent": payload[2]["row_key"],
    })
    response = _save(client, review_session, instrument, payload)
    assert response.status_code == 422
    assert f"Deeper: {DEEP}" in response.json()["errors"]


def test_an_answer_two_levels_down_locks_both_conditions(
    client: TestClient, db: Session
) -> None:
    review_session, instrument, fields = _chained(client, db, "two-level-lock")
    _add_response(db, review_session, instrument, fields["Comments"])
    db.commit()
    for name, change in (("Familiarity", {"branch_value": "1"}), ("Rating", {"branch_value": "5"})):
        payload = [
            {**rf, "row_key": f"rf_{rf['id']}"} for rf in _band2_rfs(instrument)
        ]
        for rf in payload:
            parent = next(
                (f for f in instrument.response_fields if f.id == fields[rf["name"]].branch_parent_id),
                None,
            )
            rf["branch_parent"] = f"rf_{parent.id}" if parent else None
            field = fields[rf["name"]]
            rf["branch_op"], rf["branch_value"] = field.branch_op, field.branch_value
            if rf["name"] == name:
                rf.update(change)
        response = _save(client, review_session, instrument, payload)
        assert response.status_code == 422, name
        assert any(e.startswith(f"{name}: ") for e in response.json()["errors"]), name
        db.rollback()


def test_hiding_the_top_hides_the_whole_chain(client: TestClient, db: Session) -> None:
    review_session, instrument = _new_model_with_tags(client, db, code="two-level-hide")
    response = _save(
        client, review_session, instrument,
        _chain_payload(instrument, Familiarity={"selected": False, "required": False},
                       Rating={"required": False}),
    )
    # With Familiarity hidden there's no anchor, so nothing may be required
    # below it; the save goes through with the whole chain hidden.
    assert response.status_code == 200, response.text
    db.expire_all()
    visible = {f.label: f.visible for f in instrument.response_fields}
    assert visible == {"Familiarity": False, "Rating": False, "Comments": False}


def test_a_level_one_parent_is_deleted_bottom_up(client: TestClient, db: Session) -> None:
    """As at one level: an entry without branch keys keeps its stored
    parent, so dropping Rating while Comments still names it is refused."""
    review_session, instrument, _ = _chained(client, db, "two-level-delete")
    response = _save(client, review_session, instrument, _rfs(instrument, Rating=None))
    assert response.status_code == 422
    assert response.json()["errors"] == ["Rating: Delete its branch first."]


# The settings CSV and Replicate.


def _chain_instrument(db: Session, review_session) -> Instrument:
    instrument = Instrument(session_id=review_session.id, name="Survey", order=1)
    db.add(instrument)
    db.flush()
    familiarity = InstrumentResponseField(
        instrument_id=instrument.id, field_key="familiarity", label="Familiarity",
        order=1, required=True, _inline_data_type="Integer", _inline_response_type="Likert5",
        branch_op="gt", branch_value="0",
    )
    db.add(familiarity)
    db.flush()
    rating = InstrumentResponseField(
        instrument_id=instrument.id, field_key="rating", label="Rating", order=2,
        _inline_data_type="Integer", _inline_response_type="Likert5",
        branch_parent_id=familiarity.id, branch_op="ge", branch_value="4",
        branch_mode="require",
    )
    db.add(rating)
    db.flush()
    db.add(InstrumentResponseField(
        instrument_id=instrument.id, field_key="why", label="Why", order=3,
        _inline_data_type="String", _inline_response_type="Text",
        branch_parent_id=rating.id,
    ))
    db.flush()
    return instrument


def test_the_settings_csv_round_trips_a_chain(db: Session) -> None:
    source, _ = _session(db, "two-level-csv-src")
    _chain_instrument(db, source)
    rows = serialize_session_config(db, source)
    assert {r.field: r.value for r in rows}[
        "instruments[1].response_fields[3].branch_parent"
    ] == "rating"
    target, _ = _session(db, "two-level-csv-dst")
    result = apply_session_config(db, target, [r for r in rows if r.field.startswith("instruments")])
    assert result.errors == []
    instrument = db.execute(select(Instrument).where(Instrument.session_id == target.id)).scalar_one()
    fields = _fields(db, instrument.id)
    assert fields["rating"].branch_parent_id == fields["familiarity"].id
    assert fields["why"].branch_parent_id == fields["rating"].id
    assert fields["rating"].branch_mode == "require"


def _chain_rows(**extra: tuple[str, str]) -> list[Row]:
    base = {
        "instruments[1].name": ("Survey", "string"),
        "instruments[1].response_fields[1].field_key": ("familiarity", "string"),
        "instruments[1].response_fields[1].label": ("Familiarity", "string"),
        "instruments[1].response_fields[1].response_type": ("Likert5", "string"),
        "instruments[1].response_fields[1].data_type": ("Integer", "string"),
        "instruments[1].response_fields[1].required": ("true", "boolean"),
        "instruments[1].response_fields[1].branch_op": ("gt", "enum"),
        "instruments[1].response_fields[1].branch_value": ("0", "string"),
        "instruments[1].response_fields[2].field_key": ("rating", "string"),
        "instruments[1].response_fields[2].label": ("Rating", "string"),
        "instruments[1].response_fields[2].response_type": ("Likert5", "string"),
        "instruments[1].response_fields[2].data_type": ("Integer", "string"),
        "instruments[1].response_fields[2].branch_parent": ("familiarity", "string"),
        "instruments[1].response_fields[2].branch_op": ("ge", "enum"),
        "instruments[1].response_fields[2].branch_value": ("4", "string"),
        "instruments[1].response_fields[3].field_key": ("why", "string"),
        "instruments[1].response_fields[3].label": ("Why", "string"),
        "instruments[1].response_fields[3].response_type": ("Text", "string"),
        "instruments[1].response_fields[3].data_type": ("String", "string"),
        "instruments[1].response_fields[3].branch_parent": ("rating", "string"),
        **extra,
    }
    return [Row(field, value, data_type) for field, (value, data_type) in base.items()]


def test_the_settings_csv_refuses_a_third_level_by_name(db: Session) -> None:
    review_session, _ = _session(db, "two-level-csv-deep")
    rows = _chain_rows(**{
        "instruments[1].response_fields[3].data_type": ("Integer", "string"),
        "instruments[1].response_fields[3].branch_op": ("ge", "enum"),
        "instruments[1].response_fields[3].branch_value": ("1", "string"),
        "instruments[1].response_fields[4].field_key": ("deeper", "string"),
        "instruments[1].response_fields[4].label": ("Deeper", "string"),
        "instruments[1].response_fields[4].response_type": ("Text", "string"),
        "instruments[1].response_fields[4].data_type": ("String", "string"),
        "instruments[1].response_fields[4].branch_parent": ("why", "string"),
    })
    result = apply_session_config(db, review_session, rows)
    assert any(f"Deeper: {DEEP}" in e.message for e in result.errors), result.errors
    assert db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).first() is None


def test_the_settings_csv_hides_a_hidden_tops_whole_chain(db: Session) -> None:
    review_session, _ = _session(db, "two-level-csv-hidden")
    rows = _chain_rows(**{
        "instruments[1].response_fields[1].required": ("false", "boolean"),
        "instruments[1].response_fields[1].visible": ("false", "boolean"),
    })
    result = apply_session_config(db, review_session, rows)
    assert result.errors == []
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    fields = _fields(db, instrument.id)
    assert [fields[k].visible for k in ("familiarity", "rating", "why")] == [False, False, False]


def test_replicate_instrument_copies_a_chain(db: Session) -> None:
    review_session, op = _session(db, "two-level-replicate")
    source = _chain_instrument(db, review_session)
    copy = instruments_service.replicate_instrument(
        db, review_session=review_session, source=source, actor=op
    )
    fields = _fields(db, copy.id)
    assert fields["rating"].branch_parent_id == fields["familiarity"].id
    assert fields["why"].branch_parent_id == fields["rating"].id
    assert fields["why"].branch_parent_id != _fields(db, source.id)["rating"].id


# The Item 14 cumulative read's gaps: the lock and the move rule reach
# through a level, and the hide cascade walks stored parents too.


def _stored(instrument: Instrument) -> list[dict]:
    """The card's payload as the builder sends it: every row keyed, each
    naming its stored parent and condition."""
    by_id = {f.id: f for f in instrument.response_fields}
    out = []
    for rf in _band2_rfs(instrument):
        field = by_id[rf["id"]]
        out.append({
            **rf, "row_key": f"rf_{rf['id']}",
            "branch_parent": f"rf_{field.branch_parent_id}" if field.branch_parent_id else None,
            "branch_op": field.branch_op, "branch_value": field.branch_value,
            "branch_mode": field.branch_mode,
        })
    return out


def test_an_answer_two_levels_down_locks_the_top_branchs_membership(
    client: TestClient, db: Session
) -> None:
    """Comments' answer sits in Rating's branch; Familiarity's branch
    gains no direct field while it does."""
    review_session, instrument, fields = _chained(client, db, "two-level-member")
    _add_response(db, review_session, instrument, fields["Comments"])
    payload = _stored(instrument)
    payload.append({
        "name": "Later", "data_type": "string", "min": "", "max": "", "step": "",
        "list_options": "", "selected": True, "required": False,
        "help_text_visible": False, "help_text": "", "row_key": "rf_later",
        "branch_parent": f"rf_{fields['Familiarity'].id}",
    })
    response = _save(client, review_session, instrument, payload)
    assert response.status_code == 422
    assert response.json()["errors"] == [
        "Later: Its branch has saved responses, so the branch's fields can't change."
    ]


def test_a_parent_with_answers_below_it_cant_move_into_a_branch(
    client: TestClient, db: Session
) -> None:
    """Rating heads its own branch with Comments answered; putting it
    under Familiarity would carry that answer into a closed branch."""
    review_session, instrument = _new_model_with_tags(client, db, code="two-level-move")
    response = _save(client, review_session, instrument, _chain_payload(
        instrument,
        Familiarity={"branch_op": None, "branch_value": None},
        Rating={"branch_parent": None},
    ))
    assert response.status_code == 200, response.text
    db.expire_all()
    fields = {f.label: f for f in instrument.response_fields}
    assert fields["Rating"].branch_parent_id is None
    _add_response(db, review_session, instrument, fields["Comments"])
    payload = _stored(instrument)
    for rf in payload:
        if rf["name"] == "Familiarity":
            rf.update(branch_op="gt", branch_value="0")
        if rf["name"] == "Rating":
            rf["branch_parent"] = f"rf_{fields['Familiarity'].id}"
    response = _save(client, review_session, instrument, payload)
    assert response.status_code == 422
    assert response.json()["errors"] == [
        "Rating: Its branch has saved responses, so it can't move into a branch."
    ]


def test_hiding_a_level_one_parent_hides_its_branch_only(
    client: TestClient, db: Session
) -> None:
    """With the branch keys sent and, as a caller ignorant of branching
    sends it, without them (the stored parents are walked)."""
    for code, payload_of in (
        ("two-level-hide-mid", _stored),
        ("two-level-hide-mid-bare", lambda i: [
            {k: v for k, v in rf.items() if not k.startswith("branch_")}
            for rf in _stored(i)
        ]),
    ):
        review_session, instrument, _ = _chained(client, db, code)
        payload = payload_of(instrument)
        for rf in payload:
            if rf["name"] == "Rating":
                rf.update(selected=False, required=False)
        response = _save(client, review_session, instrument, payload)
        assert response.status_code == 200, (code, response.text)
        db.expire_all()
        visible = {f.label: f.visible for f in instrument.response_fields}
        assert visible == {"Familiarity": True, "Rating": False, "Comments": False}, code


def test_save_accepts_a_level_one_field_joining_the_branch_above_it(
    client: TestClient, db: Session
) -> None:
    """Rung 5's ↰: Other moves from Familiarity's branch into Rating's,
    the branch that ends directly above it."""
    review_session, instrument, fields = _chained(client, db, "two-level-nest-save")
    payload = _stored(instrument)
    payload.append({
        "name": "Other", "data_type": "string", "min": "", "max": "", "step": "",
        "list_options": "", "selected": True, "required": False,
        "help_text_visible": False, "help_text": "", "row_key": "rf_other",
        "branch_parent": f"rf_{fields['Familiarity'].id}",
    })
    assert _save(client, review_session, instrument, payload).status_code == 200
    db.expire_all()
    other = next(f for f in instrument.response_fields if f.label == "Other")
    assert other.branch_parent_id == fields["Familiarity"].id
    payload = _stored(instrument)
    for rf in payload:
        if rf["name"] == "Other":
            rf["branch_parent"] = f"rf_{fields['Rating'].id}"
    response = _save(client, review_session, instrument, payload)
    assert response.status_code == 200, response.text
    db.expire_all()
    assert other.branch_parent_id == fields["Rating"].id


def test_clone_session_copies_a_chain(db: Session) -> None:
    """The close's check of the definition of done: cloning re-points
    each level at its own parent's clone."""
    from app.services import session_clone

    review_session, op = _session(db, "two-level-clone")
    source = _chain_instrument(db, review_session)
    clone = session_clone.clone_session(db, source=review_session, user=op, mode="all")
    db.flush()
    copied = db.execute(
        select(Instrument).where(Instrument.session_id == clone.id)
    ).scalar_one()
    fields = _fields(db, copied.id)
    assert fields["rating"].branch_parent_id == fields["familiarity"].id
    assert fields["why"].branch_parent_id == fields["rating"].id
    assert fields["rating"].branch_mode == "require"
    assert fields["why"].branch_parent_id != _fields(db, source.id)["rating"].id
