"""Integration tests for response-field operator CRUD via the
bulk-save handler — labels / required / help text / order /
add / delete / RTD selection. Includes the reviewer-side
interleave check that confirms the operator's bulk save renders
correctly on the reviewer's review surface.

Carved out of test_display_field_routes.py per
guide/major_refactor.md §12.D.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import (
    AuditEvent,
    InstrumentDisplayField,
    InstrumentResponseField,
    ResponseTypeDefinition,
)
from ._display_field_helpers import (
    _activate,
    _generate_full_matrix,
    _instrument,
    _make_session,
    _populate_rosters,
    _seed_pair_context_display_fields,
)

@pytest.fixture
def reviewer_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="r-oid",
        email="r@example.edu",
        name="R Reviewer",
        provider="aad",
    )
def test_response_field_label_and_required_persist_via_bulk_save(
    client: TestClient, db: Session
) -> None:
    """Slice 2 — operator types a Friendly Label on a Response Fields
    row and toggles Required, hits Save, the values stick on reload."""
    review_session = _make_session(client, db, code="rf-save")
    instrument = _instrument(db, review_session.id)
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()
    comments = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "comments",
        )
    ).scalar_one()

    # Submit a bulk save touching Response Fields only: rename rating
    # to "Score", flip comments' Required from off to on.
    save = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields/save",
        data={
            "kind": ["response", "response"],
            "id": [str(rating.id), str(comments.id)],
            "order": ["0", "1"],
            "label": ["Score", "Comments"],
            "required_ids": [str(rating.id), str(comments.id)],
        },
        follow_redirects=False,
    )
    assert save.status_code == 303

    db.refresh(rating)
    db.refresh(comments)
    assert rating.label == "Score"
    assert rating.required is True
    assert comments.required is True


def test_response_field_add_row_preserves_editing_param(
    client: TestClient, db: Session
) -> None:
    """Slice 2 — clicking ➕ on the Response Fields table redirects
    back with ``?editing={iid}`` so the operator stays in edit mode."""
    review_session = _make_session(client, db, code="rf-add")
    instrument = _instrument(db, review_session.id)

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields/add-row",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert f"editing={instrument.id}" in response.headers["location"]

    keys = sorted(
        r.field_key
        for r in db.execute(
            select(InstrumentResponseField).where(
                InstrumentResponseField.instrument_id == instrument.id
            )
        ).scalars()
    )
    assert "rating3" in keys


def test_response_field_delete_preserves_editing_param(
    client: TestClient, db: Session
) -> None:
    """Slice 2 — clicking ✗ on a Response Fields row redirects back
    with ``?editing={iid}``."""
    review_session = _make_session(client, db, code="rf-del")
    instrument = _instrument(db, review_session.id)
    comments = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "comments",
        )
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}"
        f"/fields/{comments.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert f"editing={instrument.id}" in response.headers["location"]


def test_response_field_move_preserves_editing_param(
    client: TestClient, db: Session
) -> None:
    """Slice 2 — clicking ▲ / ▼ on a Response Fields row swaps and
    redirects back with ``?editing={iid}``."""
    review_session = _make_session(client, db, code="rf-move")
    instrument = _instrument(db, review_session.id)
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}"
        f"/fields/{rating.id}/move",
        data={"direction": "down"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert f"editing={instrument.id}" in response.headers["location"]

    keys_in_order = [
        r.field_key
        for r in db.execute(
            select(InstrumentResponseField)
            .where(InstrumentResponseField.instrument_id == instrument.id)
            .order_by(InstrumentResponseField.order)
        ).scalars()
    ]
    assert keys_in_order == ["comments", "rating"]


def test_response_field_help_text_and_visible_persist_via_bulk_save(
    client: TestClient, db: Session
) -> None:
    """Section B Response Fields Help: editing a row's help text +
    Show checkbox persists via the same bulk-save form as the rest
    of the field-builder."""
    review_session = _make_session(client, db, code="rf-help")
    instrument = _instrument(db, review_session.id)
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()
    comments = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "comments",
        )
    ).scalar_one()

    save = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields/save",
        data={
            "kind": ["response", "response"],
            "id": [str(rating.id), str(comments.id)],
            "order": ["0", "1"],
            "label": ["Rating", "Comments"],
            "required_ids": [str(rating.id)],
            "help_text_id": [str(rating.id), str(comments.id)],
            "help_text": ["Score 1-5", "Free-form remarks"],
            # Show only checked for rating.
            "help_text_visible_ids": [str(rating.id)],
        },
        follow_redirects=False,
    )
    assert save.status_code == 303

    db.refresh(rating)
    db.refresh(comments)
    assert rating.help_text == "Score 1-5"
    assert rating.help_text_visible is True
    assert comments.help_text == "Free-form remarks"
    assert comments.help_text_visible is False


def test_friendly_label_persistence_round_trip_via_edit_route(
    client: TestClient, db: Session
) -> None:
    """The headline P0 fix: an operator-typed Friendly Label survives a
    page reload — it persists via the existing ``/display-fields/{id}/edit``
    route, not via the JS-only placeholder of yore (item #13)."""
    review_session = _make_session(client, db, code="lbl-persist")
    instrument = _instrument(db, review_session.id)
    db.add(
        InstrumentDisplayField(
            instrument_id=instrument.id,
            label="",
            source_type="reviewee",
            source_field="tag_1",
            order=2,
            visible=True,
        )
    )
    db.commit()
    df = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == instrument.id,
            InstrumentDisplayField.source_field == "tag_1",
        )
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}"
        f"/display-fields/{df.id}/edit",
        data={"label": "Cohort", "visible": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.refresh(df)
    assert df.label == "Cohort"


def test_bulk_fields_save_interleaves_and_renders_on_reviewer_surface(
    db: Session,
    alice: AuthenticatedUser,
    reviewer_user: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _make_session(operator, db, code="bulk-render")
    _populate_rosters(operator, review_session.id)
    _generate_full_matrix(operator, review_session.id)

    instrument = _instrument(db, review_session.id)
    _seed_pair_context_display_fields(db, instrument)
    pair_one = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == instrument.id,
            InstrumentDisplayField.source_field == "1",
        )
    ).scalar_one()
    pair_two = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == instrument.id,
            InstrumentDisplayField.source_field == "2",
        )
    ).scalar_one()
    pair_three = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == instrument.id,
            InstrumentDisplayField.source_field == "3",
        )
    ).scalar_one()
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()
    comments = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "comments",
        )
    ).scalar_one()

    # Submit a hide on pair_two and a label override on pair_one.
    # Order doesn't change relative to seed; the form only flips
    # visibility + label here so we don't need to model the merged sort.
    payload = {
        "kind": ["display", "display", "display", "response", "response"],
        "id": [
            str(pair_one.id),
            str(pair_two.id),
            str(pair_three.id),
            str(rating.id),
            str(comments.id),
        ],
        "order": ["0", "1", "2", "3", "4"],
        "label": ["P1", "", "", "", ""],
        # visible_ids: pair_one + pair_three (pair_two unchecked → hidden)
        "visible_ids": [str(pair_one.id), str(pair_three.id)],
    }
    response = operator.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}"
        f"/fields/save",
        data=payload,
        follow_redirects=False,
    )
    assert response.status_code == 303

    db.refresh(pair_one)
    db.refresh(pair_two)
    db.refresh(pair_three)
    assert pair_one.label == "P1"
    assert pair_one.visible is True
    assert pair_two.visible is False
    assert pair_three.visible is True

    # Reviewer surface should render P1 header for pair_one, omit pair_two,
    # show pair_three with default label.
    _activate(operator, db, review_session.id)
    reviewer_client = make_client(reviewer_user)
    body = reviewer_client.get(
        f"/reviewer/sessions/{review_session.id}"
    ).text
    assert "<th>P1</th>" in body
    assert "<th>Pair context 2</th>" not in body
    assert "<th>Pair context 3</th>" in body

    saved_event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "instrument.display_fields_saved",
            AuditEvent.session_id == review_session.id,
        )
    ).scalars().all()
    assert len(saved_event) == 1


def test_bulk_save_deletes_rows_listed_in_response_delete_ids(
    client: TestClient, db: Session
) -> None:
    """JS-deferred ✗ on Response Fields adds the row id to the bulk-
    save form's ``response_delete_ids`` set; the route deletes those
    rows before applying the rest of the payload, so Cancel (which
    just navigates away) discards the deletion."""
    review_session = _make_session(client, db, code="bulk-del")
    instrument = _instrument(db, review_session.id)
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()
    comments = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "comments",
        )
    ).scalar_one()
    comments_id = comments.id

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields/save",
        data={
            "kind": ["response", "response"],
            "id": [str(rating.id), str(comments.id)],
            "order": ["0", "1"],
            "label": ["Rating", "Comments"],
            "required_ids": [str(rating.id)],
            "response_delete_ids": [str(comments.id)],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    remaining = [
        f.field_key
        for f in db.execute(
            select(InstrumentResponseField)
            .where(InstrumentResponseField.instrument_id == instrument.id)
            .order_by(InstrumentResponseField.order)
        ).scalars()
    ]
    assert remaining == ["rating"]
    assert db.get(InstrumentResponseField, comments_id) is None


def test_bulk_save_creates_rows_for_new_id_placeholders(
    client: TestClient, db: Session
) -> None:
    """JS-deferred ➕ on Response Fields inserts a row with ``id=new_N``
    on the bulk-save form. The route allocates a real field via
    ``add_default_response_field`` and applies the operator's typed
    label / required / help to that new row."""
    review_session = _make_session(client, db, code="bulk-add")
    instrument = _instrument(db, review_session.id)
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()
    comments = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "comments",
        )
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields/save",
        data={
            "kind": ["response", "response", "response"],
            "id": [str(rating.id), "new_1", str(comments.id)],
            "order": ["0", "1", "2"],
            "label": ["Rating", "Quality", "Comments"],
            "required_ids": [str(rating.id), "new_1"],
            "help_text_id": [str(rating.id), "new_1", str(comments.id)],
            "help_text": ["", "Rate quality 1-5.", ""],
            "help_text_visible_ids": ["new_1"],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    fields = list(
        db.execute(
            select(InstrumentResponseField)
            .where(InstrumentResponseField.instrument_id == instrument.id)
            .order_by(InstrumentResponseField.order)
        ).scalars()
    )
    labels = [f.label for f in fields]
    assert labels == ["Rating", "Quality", "Comments"]
    quality = fields[1]
    assert quality.required is True
    assert quality.help_text == "Rate quality 1-5."
    assert quality.help_text_visible is True


def test_bulk_save_skips_new_row_marked_for_delete_in_same_submit(
    client: TestClient, db: Session
) -> None:
    """If the operator adds a row (id=new_N) and then ✗-deletes it
    before clicking Save, the bulk-save route does not create + delete
    a stub row — the new id is silently dropped."""
    review_session = _make_session(client, db, code="bulk-add-del")
    instrument = _instrument(db, review_session.id)
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()
    comments = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "comments",
        )
    ).scalar_one()

    before_keys = {
        f.field_key
        for f in db.execute(
            select(InstrumentResponseField).where(
                InstrumentResponseField.instrument_id == instrument.id
            )
        ).scalars()
    }

    # JS-side, the row's id="new_1" is removed from DOM entirely on
    # ✗ — so the form simply omits new_1 from the rows list. We model
    # that here by leaving new_1 out of the payload.
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields/save",
        data={
            "kind": ["response", "response"],
            "id": [str(rating.id), str(comments.id)],
            "order": ["0", "1"],
            "label": ["Rating", "Comments"],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    after_keys = {
        f.field_key
        for f in db.execute(
            select(InstrumentResponseField).where(
                InstrumentResponseField.instrument_id == instrument.id
            )
        ).scalars()
    }
    assert before_keys == after_keys


def test_bulk_save_persists_instrument_description(
    client: TestClient, db: Session
) -> None:
    """Section A description rides along with the bulk-save form so a
    single Save commits description + table edits together. Plain
    text in non-editing mode; textarea joined to ``dfsave-{iid}`` in
    editing mode."""
    review_session = _make_session(client, db, code="bulk-desc")
    instrument = _instrument(db, review_session.id)
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields/save",
        data={
            "description": "Spring 2026 Peer Review",
            "kind": ["response"],
            "id": [str(rating.id)],
            "order": ["0"],
            "label": ["Rating"],
            "required_ids": [str(rating.id)],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.refresh(instrument)
    assert instrument.description == "Spring 2026 Peer Review"


def test_response_fields_type_cell_renders_rtd_select(
    client: TestClient, db: Session
) -> None:
    """Each Response Fields row's Type cell renders a disabled
    ``<select>`` over the session's RTD names, with the row's current
    RTD pre-selected."""
    review_session = _make_session(client, db, code="rf-rtd-select")
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    # The default seeded ``rating`` row uses ``1-to-5int``.
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.field_key == "rating"
        )
    ).scalar_one()
    assert (
        f'<option value="{rating.response_type_id}" selected>1-to-5int</option>'
        in body
    )
    # The default seeded ``comments`` row uses ``Long_text``.
    comments = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.field_key == "comments"
        )
    ).scalar_one()
    assert (
        f'<option value="{comments.response_type_id}" selected>Long_text</option>'
        in body
    )


# --- Slice 4b: operator add / edit / delete on RTD card --------------


def test_rf_draft_template_renders_enabled_type_select_with_rtd_target(
    client: TestClient, db: Session
) -> None:
    """The hidden ``rf-template-{iid}`` for a new Response Field row
    renders an enabled (no ``disabled`` attribute) ``<select>`` over
    the session's RTDs, paired with a hidden ``new_rtd_target`` input
    that lets the bulk-save route key the chosen RTD by draft id."""
    review_session = _make_session(client, db, code="rf-draft-rtd")
    instrument = _instrument(db, review_session.id)
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text

    template_block = body.split(
        f'id="rf-template-{instrument.id}"', 1
    )[1].split("</template>", 1)[0]
    assert 'name="new_rtd_target"' in template_block
    assert 'name="new_rtd_id"' in template_block
    # The select is *not* disabled (saved-row Type stays disabled).
    select_block = template_block.split('name="new_rtd_id"', 1)[1].split(
        ">", 1
    )[0]
    assert "disabled" not in select_block
    # Every seeded RTD shows up as an option.
    for name in [
        "Long_text", "Short_text", "Yes_no", "Grade", "Likert5",
        "100int", "0-to-2int", "1-to-5int", "1-to-5half", "1-to-5dec",
    ]:
        assert f">{name}</option>" in template_block


def test_bulk_save_creates_new_rf_row_with_operator_chosen_rtd_and_label(
    client: TestClient, db: Session
) -> None:
    """The bulk-save handler routes a ``new_*`` row through
    ``add_default_response_field(rtd_id=..., label=..., required=...)``
    so the new RF row lands at the operator-chosen Type, with a
    field_key derived from the typed label."""
    review_session = _make_session(client, db, code="bulk-add-rtd")
    instrument = _instrument(db, review_session.id)
    rtds = {
        r.response_type: r
        for r in db.execute(
            select(ResponseTypeDefinition).where(
                ResponseTypeDefinition.session_id == review_session.id
            )
        ).scalars()
    }
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()
    comments = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "comments",
        )
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields/save",
        data={
            "kind": ["response", "response", "response"],
            "id": [str(rating.id), "new_1", str(comments.id)],
            "order": ["0", "1", "2"],
            "label": ["Rating", "Decision", "Comments"],
            "required_ids": [str(rating.id), "new_1"],
            "new_rtd_target": ["new_1"],
            "new_rtd_id": [str(rtds["Yes_no"].id)],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    new_field = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.label == "Decision",
        )
    ).scalar_one()
    assert new_field.response_type == "Yes_no"
    assert new_field.field_key == "decision"
    assert new_field.required is True
    assert new_field.validation == {"choices": ["Yes", "No"]}


def test_bulk_save_ignores_response_type_id_for_existing_rows(
    client: TestClient, db: Session
) -> None:
    """Server-side defence: the bulk-save handler only honours
    ``new_rtd_target`` / ``new_rtd_id`` for rows whose id starts
    with ``new_`` — Type stays read-only post-create on saved rows
    even if a forged form attempts to flip it."""
    review_session = _make_session(client, db, code="bulk-rtd-defence")
    instrument = _instrument(db, review_session.id)
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()
    original_rtd_id = rating.response_type_id
    other_rtd = db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.session_id == review_session.id,
            ResponseTypeDefinition.response_type == "Yes_no",
        )
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields/save",
        data={
            "kind": ["response"],
            "id": [str(rating.id)],
            "order": ["0"],
            "label": ["Rating"],
            # Forged: target an existing row id with a different RTD.
            "new_rtd_target": [str(rating.id)],
            "new_rtd_id": [str(other_rtd.id)],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    db.refresh(rating)
    assert rating.response_type_id == original_rtd_id
    # And no rogue field crept in.
    fields = list(
        db.execute(
            select(InstrumentResponseField).where(
                InstrumentResponseField.instrument_id == instrument.id
            )
        ).scalars()
    )
    assert len(fields) == 2  # rating + comments only


# --- Slice 4d: cross-cutting consistency guards --------------------


def test_bulk_save_blocks_when_post_save_rf_count_is_zero(
    client: TestClient, db: Session
) -> None:
    """Slice 4d Gap 2 — saving an instrument with all RF rows queued
    for delete redirects back with the rf_save_error banner; row count
    in DB unchanged."""
    review_session = _make_session(client, db, code="zero-rf-block")
    instrument = _instrument(db, review_session.id)
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()
    comments = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "comments",
        )
    ).scalar_one()
    before_count = db.execute(
        select(func.count(InstrumentResponseField.id)).where(
            InstrumentResponseField.instrument_id == instrument.id
        )
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields/save",
        data={
            "kind": ["response", "response"],
            "id": [str(rating.id), str(comments.id)],
            "order": ["0", "1"],
            "label": ["Rating", "Comments"],
            "response_delete_ids": [str(rating.id), str(comments.id)],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    loc = response.headers["location"]
    assert "rf_save_error=" in loc
    assert f"editing={instrument.id}" in loc

    # Banner renders on the redirected page.
    body = client.get(loc).text
    assert "Could not save" in body
    assert "must have at least one response field" in body

    # Row count unchanged in DB.
    after_count = db.execute(
        select(func.count(InstrumentResponseField.id)).where(
            InstrumentResponseField.instrument_id == instrument.id
        )
    ).scalar_one()
    assert before_count == after_count


def test_rf_save_error_banner_carries_scroll_target_and_source_cancel(
    client: TestClient, db: Session
) -> None:
    """The rf_save_error banner carries the banner-scroll-target
    class + a unique id (so the page-wide JS scrolls to it), and its
    Cancel button anchors back to the source instrument card with
    editing mode preserved."""
    review_session = _make_session(client, db, code="banner-rf-scroll")
    instrument = _instrument(db, review_session.id)
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()
    comments = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "comments",
        )
    ).scalar_one()
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields/save",
        data={
            "kind": ["response", "response"],
            "id": [str(rating.id), str(comments.id)],
            "order": ["0", "1"],
            "label": ["Rating", "Comments"],
            "response_delete_ids": [str(rating.id), str(comments.id)],
        },
        follow_redirects=False,
    )
    body = client.get(response.headers["location"]).text
    assert 'id="rf-save-error-banner"' in body
    assert "banner-scroll-target" in body
    assert (
        f"?editing={instrument.id}#instrument-{instrument.id}" in body
    )


