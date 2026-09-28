"""19T Item 13 rung 3b — the writes: the card's save and the settings CSV
accept a parent's ``branch_mode`` (``show`` / ``require``, Show stored
null), refuse an unknown one by name, lock it with the condition once the
branch has saved responses, and audit its change like the condition's.

The default instrument's Rating (Integer 1–5, required) governs Comments
while Rating ≥ 4 (``_branched``)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Instrument
from app.services.session_config_io import Row, apply_session_config, serialize_session_config

from .test_response_field_branching_roundtrip import (
    _branched_instrument,
    _fields,
    _session,
)
from .test_response_field_branching_save import _add_response, _branched, _rfs, _save

# The card's save.


def test_the_cards_save_takes_a_mode_and_audits_it(
    client: TestClient, db: Session
) -> None:
    review_session, instrument, rating, _ = _branched(client, db, "13-save")
    response = _save(client, review_session, instrument, _rfs(
        instrument, Rating={"branch_mode": "require"},
    ))
    assert response.status_code == 200, response.text
    db.refresh(rating)
    assert (rating.branch_op, rating.branch_mode) == ("ge", "require")
    changes = [
        e.detail["changes"]
        for e in db.execute(
            select(AuditEvent).where(AuditEvent.event_type == "instrument.field_updated")
        ).scalars()
    ]
    assert {"branch_mode": [None, "require"]} in changes
    # Show is stored as null, and audited back to it.
    response = _save(client, review_session, instrument, _rfs(
        instrument, Rating={"branch_mode": "show"},
    ))
    assert response.status_code == 200, response.text
    db.refresh(rating)
    assert rating.branch_mode is None


def test_the_cards_save_keeps_a_mode_an_entry_omits(
    client: TestClient, db: Session
) -> None:
    """As for the other branch keys: a caller that knows nothing of modes
    can't clear one."""
    review_session, instrument, rating, _ = _branched(client, db, "13-save-omit")
    rating.branch_mode = "require"
    db.commit()
    rfs = [{k: v for k, v in rf.items() if k != "branch_mode"} for rf in _rfs(instrument)]
    assert _save(client, review_session, instrument, rfs).status_code == 200
    db.refresh(rating)
    assert rating.branch_mode == "require"


def test_the_cards_save_refuses_an_unknown_mode(
    client: TestClient, db: Session
) -> None:
    review_session, instrument, rating, _ = _branched(client, db, "13-save-bad")
    response = _save(client, review_session, instrument, _rfs(
        instrument, Rating={"branch_mode": "maybe"},
    ))
    assert response.status_code == 422
    assert response.json()["errors"] == ["Rating: Choose what the branch condition does."]
    db.refresh(rating)
    assert rating.branch_mode is None


def test_saved_responses_lock_the_mode(client: TestClient, db: Session) -> None:
    """Require → Show would strand answers on a now-closed branch."""
    review_session, instrument, rating, comments = _branched(client, db, "13-save-lock")
    rating.branch_mode = "require"
    db.commit()
    _add_response(db, review_session, instrument, comments)
    db.expire_all()
    response = _save(client, review_session, instrument, _rfs(
        instrument, Rating={"branch_mode": "show"},
    ))
    assert response.status_code == 422
    assert response.json()["errors"] == [
        "Rating: Its branch has saved responses, so its condition can't change."
    ]
    # The refused save's in-memory change is the test session's, not stored.
    db.rollback()
    db.refresh(rating)
    assert rating.branch_mode == "require"


def test_a_mode_goes_with_its_branch(client: TestClient, db: Session) -> None:
    """Detaching the last governed field ends the branch: the condition and
    its mode both clear."""
    review_session, instrument, rating, _ = _branched(client, db, "13-save-end")
    rating.branch_mode = "require"
    db.commit()
    response = _save(client, review_session, instrument, _rfs(
        instrument, Comments={"branch_parent": None},
    ))
    assert response.status_code == 200, response.text
    db.refresh(rating)
    assert (rating.branch_op, rating.branch_value, rating.branch_mode) == (None, None, None)


# The settings CSV.


def test_the_settings_csv_round_trips_a_mode(db: Session) -> None:
    source, _ = _session(db, "13-csv-src")
    instrument = _branched_instrument(db, source)
    fields = _fields(db, instrument.id)
    fields["colour"].branch_mode = "require"
    # Item 11's anchor: a require-mode branch needs an active required
    # field outside any branch.
    fields["notes"].required = True
    db.flush()
    rows = serialize_session_config(db, source)
    by_field = {r.field: r for r in rows}
    prefix = "instruments[1].response_fields"
    assert by_field[f"{prefix}[1].branch_mode"].value == "require"
    assert by_field[f"{prefix}[1].branch_mode"].data_type == "enum"
    # Show exports blank.
    assert by_field[f"{prefix}[3].branch_mode"].value == ""
    target, _ = _session(db, "13-csv-dst")
    result = apply_session_config(db, target, [r for r in rows if r.field.startswith("instruments")])
    assert result.errors == []
    copied = db.execute(select(Instrument).where(Instrument.session_id == target.id)).scalar_one()
    fields = _fields(db, copied.id)
    assert fields["colour"].branch_mode == "require"
    assert fields["why"].branch_mode is None and fields["notes"].branch_mode is None


def _with_mode(db: Session, code: str, key: str, value: str) -> list[Row]:
    source, _ = _session(db, code)
    _branched_instrument(db, source)
    rows = [r for r in serialize_session_config(db, source) if r.field.startswith("instruments")]
    return [
        Row(r.field, value, r.data_type) if r.field == key else r
        for r in rows
    ]


def test_the_settings_csv_reads_show_as_null(db: Session) -> None:
    rows = _with_mode(db, "13-csv-show", "instruments[1].response_fields[1].branch_mode", "show")
    target, _ = _session(db, "13-csv-show-dst")
    assert apply_session_config(db, target, rows).errors == []
    copied = db.execute(select(Instrument).where(Instrument.session_id == target.id)).scalar_one()
    assert _fields(db, copied.id)["colour"].branch_mode is None


def test_the_settings_csv_refuses_an_unknown_mode(db: Session) -> None:
    rows = _with_mode(db, "13-csv-bad", "instruments[1].response_fields[1].branch_mode", "maybe")
    target, _ = _session(db, "13-csv-bad-dst")
    errors = apply_session_config(db, target, rows).errors
    assert [(e.field, e.message) for e in errors] == [(
        "instruments[1].response_fields[1].branch_mode",
        "unknown branch_mode 'maybe'; expected one of ['require', 'show']",
    )]


def test_the_settings_csv_refuses_a_mode_without_a_branch(db: Session) -> None:
    """A mode on a field with no condition is an orphan, like a lone
    ``branch_value``."""
    rows = _with_mode(db, "13-csv-orphan", "instruments[1].response_fields[3].branch_mode", "require")
    target, _ = _session(db, "13-csv-orphan-dst")
    errors = apply_session_config(db, target, rows).errors
    assert [e.message for e in errors] == ["Notes: Its branch condition governs no field."]


def test_the_settings_csv_holds_a_require_mode_branch_to_the_anchor_rule(db: Session) -> None:
    """With no active required field outside the branch, a require-mode
    branch is refused, naming its governed field (19T Item 11's rule)."""
    rows = _with_mode(db, "13-csv-anchor", "instruments[1].response_fields[1].branch_mode", "require")
    target, _ = _session(db, "13-csv-anchor-dst")
    errors = apply_session_config(db, target, rows).errors
    assert [e.message for e in errors] == [
        "Why: A field inside a branch can be required only when the instrument "
        "has an active required field outside any branch."
    ]
