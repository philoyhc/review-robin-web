"""Integration tests for the per-instrument editing-state machine
on the operator's Instruments page — ?editing= URL state, the
lock-card override on a ready session, the saved-state pill, and
the RTD-card / per-instrument-card mutual-exclusion gates.

Carved out of test_display_field_routes.py per
guide/major_refactor.md §12.D.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    InstrumentDisplayField,
    ResponseTypeDefinition,
)
from ._display_field_helpers import (
    _activate,
    _generate_full_matrix,
    _instrument,
    _make_session,
    _populate_rosters,
)

def test_state_machine_editing_param_renders_save_cancel(
    client: TestClient, db: Session
) -> None:
    """``?editing={iid}`` opens the per-instrument card for editing —
    the Section E ``Save`` button (form="dfsave-{iid}") is rendered."""
    review_session = _make_session(client, db, code="state-edit")
    instrument = _instrument(db, review_session.id)
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    # Section E Save is identified by ``form="dfsave-{iid}"``.
    assert f'form="dfsave-{instrument.id}"' in body
    assert ">Save</button>" in body
    # Section E Cancel is the only Cancel anchor on the page.
    assert ">Cancel</a>" in body



def test_state_machine_default_renders_edit_only(
    client: TestClient, db: Session
) -> None:
    """Without ``?editing``, the per-instrument card is locked — the
    Section E Edit anchor links forward to ``?editing={iid}``."""
    review_session = _make_session(client, db, code="state-locked")
    instrument = _instrument(db, review_session.id)
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    # Section E Edit anchor.
    assert f"?editing={instrument.id}" in body
    # Section E bulk-save form ``dfsave-{iid}`` not present in locked
    # mode (the form wraps editable inputs only).
    assert f'form="dfsave-{instrument.id}"' not in body


def test_state_machine_locked_when_session_ready(
    client: TestClient, db: Session
) -> None:
    """Even with ``?editing={iid}``, a ``ready`` session keeps the
    card locked and greys out the Edit button."""
    review_session = _make_session(client, db, code="state-ready")
    _populate_rosters(client, review_session.id)
    _generate_full_matrix(client, db, review_session.id)
    _activate(client, db, review_session.id)
    db.refresh(review_session)
    assert review_session.status == "ready"
    instrument = _instrument(db, review_session.id)

    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    # Section E bulk-save form is suppressed; Edit anchor renders with
    # the disabled-look styling.
    assert "pointer-events: none" in body
    assert f'form="dfsave-{instrument.id}"' not in body


def test_saved_state_pill_flips_after_save(
    client: TestClient, db: Session
) -> None:
    """A fresh instrument renders the ``not saved`` pill; after the
    operator submits a bulk save (touches a Display Fields label), the
    pill flips to ``saved``."""
    review_session = _make_session(client, db, code="saved-pill")
    instrument = _instrument(db, review_session.id)

    fresh = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    assert "not saved</span>" in fresh
    assert ">saved</span>" not in fresh

    # Submit a bulk save touching the locked Name row's label.
    name_row = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == instrument.id,
            InstrumentDisplayField.source_field == "name",
        )
    ).scalar_one()
    email_row = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == instrument.id,
            InstrumentDisplayField.source_field == "email_or_identifier",
        )
    ).scalar_one()

    save = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields/save",
        data={
            "kind": ["display", "display"],
            "id": [str(name_row.id), str(email_row.id)],
            "order": ["0", "1"],
            "label": ["Reviewee Name", "Reviewee Email"],
            "visible_ids": [str(name_row.id), str(email_row.id)],
        },
        follow_redirects=False,
    )
    assert save.status_code == 303

    after = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    assert ">saved</span>" in after
    assert ">not saved</span>" not in after


def test_state_machine_response_fields_render_inputs_in_edit_mode(
    client: TestClient, db: Session
) -> None:
    """In edit mode the Response Fields table renders editable label
    inputs + required checkboxes + ➕ / ✗ buttons."""
    review_session = _make_session(client, db, code="rf-edit-render")
    instrument = _instrument(db, review_session.id)
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    # Inputs for label + required participate in the bulk-save form.
    assert f'form="dfsave-{instrument.id}"' in body
    assert 'name="required_ids"' in body
    # ✗ delete + ➕ add are JS-driven; clicks defer to the bulk-save
    # form so Cancel discards the row mutation.
    assert "deleteRow(this" in body
    assert "addRow(this" in body
    assert f'id="rf-template-{instrument.id}"' in body
    assert f'id="rfhelp-template-{instrument.id}"' in body


def test_instruments_page_unifies_edit_under_section_e(
    client: TestClient, db: Session
) -> None:
    """The legacy ``<details>`` Edit toggle in Section A is gone; the
    description is plain text when not editing, and renders as a
    textarea joined to the ``dfsave-{iid}`` bulk-save form when the
    Section E Edit button has put the card in edit mode."""
    review_session = _make_session(client, db, code="edit-unified")
    instrument = _instrument(db, review_session.id)

    locked = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    # Section A: no inline ``<details>`` Edit toggle, no description form.
    assert "<details>" not in locked
    assert (
        f'action="/operator/sessions/{review_session.id}/instruments/{instrument.id}/edit"'
        not in locked
    )
    # Preview Instrument stub + Section C separator are gone.
    assert "Preview rendering lands" not in locked
    assert "Preview Instrument" not in locked

    editing = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    # In edit mode, description renders as a textarea on the bulk-save form.
    assert (
        f'<textarea form="dfsave-{instrument.id}" name="description"'
        in editing
    )


def test_instrument_edit_locks_rtd_card_affordances(
    client: TestClient, db: Session
) -> None:
    """Slice 4d Gap 1 — when ``?editing={iid}`` is set, every operator-
    defined RTD row's Edit + the Add a Response Type Add button
    render disabled with the mutual-exclusion tooltip."""
    review_session = _make_session(client, db, code="mx-instr")
    instrument = _instrument(db, review_session.id)
    # Operator-add an ODT so we have an Edit button to assert against.
    client.post(
        f"/operator/sessions/{review_session.id}/response-types",
        data={
            "response_type": "MX",
            "data_type": "Integer",
            "min": "0",
            "max": "5",
            "step": "1",
        },
        follow_redirects=False,
    )

    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    # The would-be Edit anchor is replaced with a disabled <a>.
    assert "Save or cancel the instrument edit before editing a Response Type" in body
    # Add card's Add button is disabled.
    add_button = body.split('id="rtd-add-button"', 1)[1].split(">", 1)[0]
    assert "disabled" in add_button


def test_rtd_edit_locks_instrument_card_affordances(
    client: TestClient, db: Session
) -> None:
    """Slice 4d Gap 1 — when ``?editing_rtd_id={id}`` is set, every
    per-instrument card's Edit anchors render disabled."""
    review_session = _make_session(client, db, code="mx-rtd")
    client.post(
        f"/operator/sessions/{review_session.id}/response-types",
        data={
            "response_type": "MXrtd",
            "data_type": "Integer",
            "min": "0",
            "max": "5",
            "step": "1",
        },
        follow_redirects=False,
    )
    custom = db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.response_type == "MXrtd"
        )
    ).scalar_one()

    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing_rtd_id={custom.id}"
    ).text
    assert (
        "Save or cancel the Response Type Definitions edit before editing an instrument"
        in body
    )


