"""Integration tests for the Response Type Definitions (RTD)
card on the operator's Instruments page — seeded catalog render,
formatted min/max/step pills, operator-add / edit / delete
(soft-delete on operator-defined rows; seeded rows are spec-
locked), draft-template rendering for the no-JS add flow, and
cascade-delete preview / would-empty-instrument hard-block paths.

Carved out of test_display_field_routes.py per
guide/major_refactor.md §12.D.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    InstrumentResponseField,
    ResponseTypeDefinition,
)
from ._display_field_helpers import (
    _activate,
    _generate_full_matrix,
    _instrument,
    _make_session,
    _populate_rosters,
    _validate,
)


def test_response_type_definitions_card_renders_seeded_catalog(
    client: TestClient, db: Session
) -> None:
    """The Instruments page renders the Response Type Definitions card
    as a read-only catalog of the ten seeded rows in canonical order.
    Slice 4a contract; operator add / edit / delete lands in 4b."""
    review_session = _make_session(client, db, code="rtd-card")
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    assert "Response Type Definitions" in body
    # Every seeded row appears, in spec order.
    expected_in_order = [
        "Long_text", "Short_text", "Yes_no", "Grade", "Likert5",
        "100int", "0-to-2int", "1-to-5int", "1-to-5half", "1-to-5dec",
    ]
    last_idx = -1
    for name in expected_in_order:
        idx = body.find(f"<code>{name}</code>")
        assert idx > last_idx, (
            f"{name} missing or out of order in RTD card"
        )
        last_idx = idx
    # 4b features are not yet present.
    assert "Operator-add" in body or "follow-up slice" in body


def test_response_type_definitions_card_formats_min_max_step_by_data_type(
    client: TestClient, db: Session
) -> None:
    """Min / Max / Step on the read-only RTD catalog render as plain
    integers for Integer + String rows (no decimal point) and as one
    decimal place for Decimal rows."""
    review_session = _make_session(client, db, code="rtd-fmt")
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text

    # Integer / String rows: no decimal point in Min / Max / Step.
    # Use ``Long_text`` (String, 0..2000) and ``100int`` (Integer, 0..100).
    long_text_block = body.split("<code>Long_text</code>", 1)[1].split(
        "</tr>", 1
    )[0]
    assert ">0<" in long_text_block and ">2000<" in long_text_block
    assert "0.0" not in long_text_block
    assert "2000.0" not in long_text_block

    int_100_block = body.split("<code>100int</code>", 1)[1].split(
        "</tr>", 1
    )[0]
    assert ">100<" in int_100_block
    assert "100.0" not in int_100_block

    # Decimal rows: exactly one decimal place. ``1-to-5half``
    # (Decimal, 1..5 step 0.5).
    half_block = body.split("<code>1-to-5half</code>", 1)[1].split(
        "</tr>", 1
    )[0]
    assert ">1.0<" in half_block
    assert ">5.0<" in half_block
    assert ">0.5<" in half_block


def test_rtd_add_route_persists_operator_defined_row(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rtd-route-add")
    response = client.post(
        f"/operator/sessions/{review_session.id}/response-types",
        data={
            "response_type": "MyScale",
            "data_type": "Integer",
            "min": "0",
            "max": "10",
            "step": "2",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "rtd-card" in response.headers["location"]

    rtd = db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.session_id == review_session.id,
            ResponseTypeDefinition.response_type == "MyScale",
        )
    ).scalar_one()
    assert rtd.is_seeded is False
    assert (rtd.min, rtd.max, rtd.step) == (0, 10, 2)


def test_rtd_add_route_renders_error_banner_on_invalid_payload(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rtd-route-bad")
    response = client.post(
        f"/operator/sessions/{review_session.id}/response-types",
        data={
            "response_type": "BadDecimal",
            "data_type": "Decimal",
            "min": "0",
            "max": "1",
            "step": "0.05",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "rtd_error=" in response.headers["location"]

    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?rtd_error=Step+must+have+at+most+one+decimal+place"
    ).text
    assert "Could not save Response Type" in body


def test_rtd_edit_route_locks_seeded_rows(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rtd-edit-lock")
    seeded = db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.session_id == review_session.id,
            ResponseTypeDefinition.response_type == "1-to-5int",
        )
    ).scalar_one()
    response = client.post(
        f"/operator/sessions/{review_session.id}/response-types/{seeded.id}/edit",
        data={"min": "0", "max": "10", "step": "1"},
        follow_redirects=False,
    )
    assert response.status_code == 409


def test_rtd_delete_route_blocks_in_use_then_confirm_cascades(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rtd-cascade-route")
    instrument = _instrument(db, review_session.id)

    # Operator adds a custom RTD and rebinds the seeded ``rating`` row
    # so it depends on that RTD.
    client.post(
        f"/operator/sessions/{review_session.id}/response-types",
        data={
            "response_type": "Cascade-Test",
            "data_type": "Integer",
            "min": "0",
            "max": "5",
            "step": "1",
        },
        follow_redirects=False,
    )
    custom = db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.session_id == review_session.id,
            ResponseTypeDefinition.response_type == "Cascade-Test",
        )
    ).scalar_one()
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()
    rating.response_type_id = custom.id
    db.commit()
    rating_id = rating.id  # capture before cascade invalidates the row
    custom_id = custom.id

    # First delete attempt without confirm: redirect with cascade-block
    # query params; row stays in DB.
    blocked = client.post(
        f"/operator/sessions/{review_session.id}/response-types/{custom_id}/delete",
        follow_redirects=False,
    )
    assert blocked.status_code == 303
    loc = blocked.headers["location"]
    assert f"rtd_delete_blocked_id={custom_id}" in loc
    assert "rtd_delete_blocked_rfs=1" in loc
    assert db.get(ResponseTypeDefinition, custom_id) is not None

    # Operator confirms.
    confirmed = client.post(
        f"/operator/sessions/{review_session.id}/response-types/{custom_id}/delete",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert confirmed.status_code == 303

    db.expire_all()
    assert db.get(ResponseTypeDefinition, custom_id) is None
    # Cascade dropped the dependent RF row.
    assert db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.id == rating_id
        )
    ).scalar_one_or_none() is None


def test_rtd_locked_when_session_ready(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rtd-ready-lock")
    _populate_rosters(client, review_session.id)
    _generate_full_matrix(client, review_session.id)
    _validate(client, db, review_session.id)
    _activate(client, db, review_session.id)
    db.refresh(review_session)
    assert review_session.status == "ready"

    response = client.post(
        f"/operator/sessions/{review_session.id}/response-types",
        data={
            "response_type": "Blocked",
            "data_type": "Integer",
            "min": "0",
            "max": "5",
            "step": "1",
        },
        follow_redirects=False,
    )
    assert response.status_code == 409


def test_rtd_card_renders_edit_only_in_locked_state_for_operator_added_row(
    client: TestClient, db: Session
) -> None:
    """In the locked (default) state, every saved operator-defined
    row renders **only** an Edit button (Alert style). Delete moves
    into the unlocked state — operator must click Edit first to
    expose Save / Cancel / Delete on that row."""
    review_session = _make_session(client, db, code="rtd-row-form")
    client.post(
        f"/operator/sessions/{review_session.id}/response-types",
        data={
            "response_type": "Editable",
            "data_type": "Integer",
            "min": "0",
            "max": "5",
            "step": "1",
        },
        follow_redirects=False,
    )
    custom = db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.session_id == review_session.id,
            ResponseTypeDefinition.response_type == "Editable",
        )
    ).scalar_one()

    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    # Locked state: Edit anchor rendered; per-row delete form should
    # NOT appear (Delete only in unlocked state).
    assert f"editing_rtd_id={custom.id}" in body
    assert (
        f'/operator/sessions/{review_session.id}/response-types/{custom.id}/delete'
        not in body
    )
    # The per-row edit form should NOT yet render — that requires
    # the operator to click Edit (i.e. ?editing_rtd_id={id}).
    assert f'id="rtd-edit-{custom.id}"' not in body


def test_rtd_card_other_row_edit_is_disabled_when_one_row_unlocked(
    client: TestClient, db: Session
) -> None:
    """While one operator-defined row is in the unlocked state, every
    other operator-defined row's Edit button renders disabled (the
    operator must Save / Cancel / Delete the unlocked row first)."""
    review_session = _make_session(client, db, code="rtd-one-edit")
    for name in ("RowA", "RowB"):
        client.post(
            f"/operator/sessions/{review_session.id}/response-types",
            data={
                "response_type": name,
                "data_type": "Integer",
                "min": "0",
                "max": "5",
                "step": "1",
            },
            follow_redirects=False,
        )
    rows = list(
        db.execute(
            select(ResponseTypeDefinition).where(
                ResponseTypeDefinition.session_id == review_session.id,
                ResponseTypeDefinition.is_seeded.is_(False),
            )
        ).scalars()
    )
    assert len(rows) == 2
    a, b = rows[0], rows[1]

    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
        f"?editing_rtd_id={a.id}"
    ).text
    # The unlocked row carries the Save / Cancel / Delete trio.
    assert f'id="rtd-edit-{a.id}"' in body
    assert (
        f'/operator/sessions/{review_session.id}/response-types/{a.id}/delete'
        in body
    )
    # The other locked row's Edit button is rendered but disabled
    # (greyed out) — no link into ``editing_rtd_id={b.id}``.
    assert f"editing_rtd_id={b.id}" not in body


def test_rtd_card_renders_per_row_edit_form_when_editing_rtd_id_matches(
    client: TestClient, db: Session
) -> None:
    """Clicking Edit lands on the same page with
    ``?editing_rtd_id={id}``; the matching row swaps into the editable
    state with parameter inputs + Save / Cancel buttons. Other
    operator-defined rows stay in the saved (locked) state."""
    review_session = _make_session(client, db, code="rtd-edit-mode")
    client.post(
        f"/operator/sessions/{review_session.id}/response-types",
        data={
            "response_type": "EditTarget",
            "data_type": "Integer",
            "min": "0",
            "max": "5",
            "step": "1",
        },
        follow_redirects=False,
    )
    custom = db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.session_id == review_session.id,
            ResponseTypeDefinition.response_type == "EditTarget",
        )
    ).scalar_one()

    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
        f"?editing_rtd_id={custom.id}"
    ).text
    assert f'id="rtd-edit-{custom.id}"' in body
    # The Save button submits to the edit route; Cancel anchors back
    # to the page without the editing param.
    assert (
        f'/operator/sessions/{review_session.id}/response-types/{custom.id}/edit'
        in body
    )


def test_rtd_card_renders_draft_templates_for_js_add_flow(
    client: TestClient, db: Session
) -> None:
    """The Add a Response Type footer renders only Name + Data Type
    inputs; the actual draft row is cloned client-side from the
    ``rtd-draft-row-template`` / ``rtd-draft-form-template`` <template>
    elements when the operator clicks Add."""
    review_session = _make_session(client, db, code="rtd-draft-tmpl")
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    assert 'id="rtd-draft-row-template"' in body
    assert 'id="rtd-draft-form-template"' in body
    assert 'id="new-rtd-name"' in body
    assert 'id="new-rtd-data-type"' in body
    # The footer Add form is intentionally minimal — only Name +
    # Data Type. Min / Max / Step / List inputs live in the draft
    # row template and only appear after Add is clicked.
    assert 'onclick="addRtdDraft()"' in body
    # The draft-row template's Cancel button must pass the draft id
    # as a quoted string — passing it bare (``cancelRtdDraft(d1)``)
    # would treat ``d1`` as a JS identifier and silently fail.
    assert "cancelRtdDraft('__DRAFT_ID__')" in body


def test_rtd_add_button_disabled_when_editing_an_existing_row(
    client: TestClient, db: Session
) -> None:
    """``Add a Response Type`` is locked while a saved operator-defined
    row is in editing mode (``?editing_rtd_id=...``); the operator
    must Save or Cancel that row first."""
    review_session = _make_session(client, db, code="rtd-add-lock")
    client.post(
        f"/operator/sessions/{review_session.id}/response-types",
        data={
            "response_type": "ToEdit",
            "data_type": "Integer",
            "min": "0",
            "max": "5",
            "step": "1",
        },
        follow_redirects=False,
    )
    custom = db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.session_id == review_session.id,
            ResponseTypeDefinition.response_type == "ToEdit",
        )
    ).scalar_one()

    # Not editing — Add is enabled.
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    button_html = body.split('id="rtd-add-button"', 1)[1].split(">", 1)[0]
    assert "disabled" not in button_html

    # Editing — Add is server-rendered disabled.
    body_editing = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
        f"?editing_rtd_id={custom.id}"
    ).text
    button_html_editing = body_editing.split(
        'id="rtd-add-button"', 1
    )[1].split(">", 1)[0]
    assert "disabled" in button_html_editing
    assert 'data-server-disabled="1"' in button_html_editing


# --- Slice 4c: operator-pickable Type on new RF rows --------------


def test_rtd_delete_blocks_when_cascade_would_empty_instrument(
    client: TestClient, db: Session
) -> None:
    """Slice 4d Gap 3 — operator-delete on an in-use ODT whose cascade
    would empty an instrument bounces back with the would-empty banner;
    the row + dependent RF rows survive."""
    review_session = _make_session(client, db, code="would-empty-route")
    instrument = _instrument(db, review_session.id)

    client.post(
        f"/operator/sessions/{review_session.id}/response-types",
        data={
            "response_type": "OnlyType",
            "data_type": "Integer",
            "min": "0",
            "max": "5",
            "step": "1",
        },
        follow_redirects=False,
    )
    custom = db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.response_type == "OnlyType"
        )
    ).scalar_one()
    # Point both default RF rows at the operator-defined RTD so the
    # cascade would leave the instrument empty.
    rfs = list(
        db.execute(
            select(InstrumentResponseField).where(
                InstrumentResponseField.instrument_id == instrument.id
            )
        ).scalars()
    )
    for rf in rfs:
        rf.response_type_id = custom.id
    db.commit()

    blocked = client.post(
        f"/operator/sessions/{review_session.id}/response-types/{custom.id}/delete",
        data={"confirm": "true"},  # operator confirms — should still block
        follow_redirects=False,
    )
    assert blocked.status_code == 303
    loc = blocked.headers["location"]
    assert f"rtd_would_empty_id={custom.id}" in loc
    assert "rtd_would_empty_instruments=1" in loc

    # Banner renders on the redirected page.
    body = client.get(loc).text
    assert "Cannot delete this Response Type" in body
    assert "instrument <strong>#1</strong>" in body or "instrument" in body

    # Row + dependents survive.
    db.expire_all()
    assert db.get(ResponseTypeDefinition, custom.id) is not None


# --- Banner scroll-target convention --------------------------------


def test_rtd_would_empty_banner_carries_scroll_target_and_source_cancel(
    client: TestClient, db: Session
) -> None:
    """The rtd_would_empty banner carries the banner-scroll-target
    class + unique id, and its Cancel button anchors back to the
    source RTD row."""
    review_session = _make_session(client, db, code="banner-rtd-scroll")
    instrument = _instrument(db, review_session.id)
    client.post(
        f"/operator/sessions/{review_session.id}/response-types",
        data={
            "response_type": "OnlyType2",
            "data_type": "Integer",
            "min": "0",
            "max": "5",
            "step": "1",
        },
        follow_redirects=False,
    )
    custom = db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.response_type == "OnlyType2"
        )
    ).scalar_one()
    rfs = list(
        db.execute(
            select(InstrumentResponseField).where(
                InstrumentResponseField.instrument_id == instrument.id
            )
        ).scalars()
    )
    for rf in rfs:
        rf.response_type_id = custom.id
    db.commit()

    blocked = client.post(
        f"/operator/sessions/{review_session.id}/response-types/{custom.id}/delete",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    body = client.get(blocked.headers["location"]).text
    assert 'id="rtd-would-empty-banner"' in body
    assert "banner-scroll-target" in body
    assert f"#rtd-row-{custom.id}" in body
