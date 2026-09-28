"""19T Item 12A — small adjustments to Band 3's response-field table, on
the author's instruction: join reads ↰ and detach ↳; a number's condition
boxes take the parent's Min width; the Active checkbox is centered in its
cell."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from .test_instrument_builder_routes import _card_slice, _rf_fn
from .test_response_field_branching_builder import _page, _row, _rows_table


def test_join_reads_the_up_arrow_and_detach_the_down_arrow(
    client: TestClient, db: Session
) -> None:
    """The row script rewrites every join button's glyph at load, so the
    glyph an operator sees is the one ``newModelRfSyncJoin`` sets: pin each
    of its ``set(...)`` calls, and the template row's (the item's read)."""
    review_session, instrument, _, flat = _page(client, db, "12a-glyphs")
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    sync = _rf_fn(body, "newModelRfSyncJoin")
    calls = [
        (glyph, dq or sq)
        for glyph, dq, sq in re.findall(r"""set\('(.)', (?:"([^"]+)"|'([^']+)')""", sync)
    ]
    assert len(calls) == 12, calls
    detach_titles = {
        "Its branch has saved responses, so its fields can't change",
        "Detach this field and end its branch",
        "Move this field out of its branch",
    }
    for glyph, title in calls:
        assert glyph == ("↳" if title in detach_titles else "↰"), (glyph, title)
    template = flat.split("<template data-new-model-rf-row-template>")[1].split("</template>")[0]
    assert re.search(r"<button[^>]*data-new-model-rf-join[^>]*>↰</button>", template)


def test_the_active_checkbox_is_centered_on_every_row(
    client: TestClient, db: Session
) -> None:
    _, _, card, flat = _page(client, db, "12a-active")
    table = _rows_table(card)
    for name in ("Rating", "Comments"):
        cell = re.search(
            r'<td class="([^"]*)"><input type="checkbox" data-new-model-rf-active',
            _row(table, name),
        )
        assert cell and "rf-active-cell" in cell.group(1).split(), name
    # A row the script adds from the template is centered too.
    template = flat.split("<template data-new-model-rf-row-template>")[1].split("</template>")[0]
    assert '<td class="col-shrink rf-active-cell"><input type="checkbox" data-new-model-rf-active' in template
    assert "body.ui-v2 table.rf-table td.rf-active-cell { text-align: center; }" in flat


def test_a_numbers_condition_boxes_follow_the_parents_min_box(
    client: TestClient, db: Session
) -> None:
    review_session, instrument, _, flat = _page(client, db, "12a-width")
    assert (
        "body.ui-v2 table.rf-table td.rf-condition-cell input { "
        "width: var(--rf-condition-box, 12em); box-sizing: border-box; }"
    ) in flat
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    size = _rf_fn(body, "newModelRfSizeCondition")
    assert "parent.querySelector('[data-new-model-rf-bound=\"min\"]')" in size
    assert "cond.style.setProperty('--rf-condition-box', width + 'px');" in size
    # A hidden Min (a List parent) falls back to the stylesheet's width.
    assert "cond.style.removeProperty('--rf-condition-box');" in size
    assert "new ResizeObserver(apply)" in size
    # A row that stops being a parent stops sizing (Codex on #2661).
    assert "if (!row || !row.hasAttribute('data-new-model-rf-parent')) { return; }" in size
    recompute = _rf_fn(body, "newModelRfRecomputeCondition")
    assert "window.newModelRfSizeCondition(parent);" in recompute


def test_join_and_detach_leave_room_for_two_more_buttons(
    client: TestClient, db: Session
) -> None:
    """The author's later 12A entries: after ↰ / ↳, space for two more
    buttons, ahead of a second level of branching (it was one), still
    of the same width, on the server's rows and the template's."""
    _, _, card, flat = _page(client, db, "12a-join-room")
    table = _rows_table(card)
    for name in ("Rating", "Comments"):
        assert '<td class="col-shrink rf-join-cell" data-new-model-rf-join-cell>' in _row(table, name)
    template = flat.split("<template data-new-model-rf-row-template>")[1].split("</template>")[0]
    assert '<td class="col-shrink rf-join-cell" data-new-model-rf-join-cell>' in template
    # The cell's own padding, then two buttons (``.rf-glyph``'s width, one
    # variable for both), each with the two paddings between cells.
    assert "body.ui-v2 table.rf-table { --rf-glyph-width: 2.25rem; }" in flat
    assert "width: var(--rf-glyph-width);" in flat
    assert (
        "body.ui-v2 table.rf-table td.rf-join-cell { "
        "padding-right: calc(2 * var(--rf-glyph-width) + 5 * var(--space-1)); }"
    ) in flat


def test_the_operator_takes_the_name_column_and_the_lead_aligns_right(
    client: TestClient, db: Session
) -> None:
    """The author's later 12A entry: the condition's operator sits in the
    name column at the name box's width, with "If the above" right-aligned
    before it."""
    _, _, card, flat = _page(client, db, "12a-operator")
    condition = _rows_table(card).split("<tr data-new-model-rf-condition>")[1].split("</tr>")[0]
    cells = condition.split("<td")[1:]
    assert 'class="col-shrink rf-condition-cell rf-condition-lead">If the above</td>' in cells[3]
    assert 'class="rf-condition-cell rf-condition-op">' in cells[4]
    assert "<select data-new-model-rf-condition-op" in cells[4]
    assert "body.ui-v2 table.rf-table td.rf-condition-lead { text-align: right; }" in flat
    assert (
        "body.ui-v2 table.rf-table td.rf-condition-op select { "
        "width: 100%; margin: 0; box-sizing: border-box; }"
    ) in flat


def test_the_first_value_box_starts_at_the_type_columns_edge(
    client: TestClient, db: Session
) -> None:
    """The author's later 12A entry: the gap after the operator matches the
    one between name and type, so the first value box drops its left
    margin and lines up with the type select."""
    _, _, card, flat = _page(client, db, "12a-value-gap")
    # It is the first control of the cell right after the operator's, so
    # dropping its margin puts it at the type column's edge (the item's
    # read: the CSS alone didn't pin that).
    condition = _rows_table(card).split("<tr data-new-model-rf-condition>")[1].split("</tr>")[0]
    rest = condition.split("<td")[6]
    assert rest.startswith(' colspan="7" class="rf-condition-cell">')
    assert rest.split(">", 1)[1].lstrip().startswith(
        '<input type="text" data-new-model-rf-condition-value'
    )
    assert (
        "body.ui-v2 table.rf-table td.rf-condition-cell "
        "input[data-new-model-rf-condition-value] { margin-left: 0; }"
    ) in flat


def test_the_operator_and_name_boxes_carry_their_full_text_as_tooltips(
    client: TestClient, db: Session
) -> None:
    """The author's later 12A entry: the name column cuts long names and
    operator labels, so each box's tooltip gives the full text (with a
    single-value operator's symbol), except while its row is amber, whose reason
    comes first."""
    review_session, instrument, _, _ = _page(client, db, "12a-tooltips")
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    title = _rf_fn(body, "newModelRfTitleOperator")
    assert "if (!option || pending) { sel.removeAttribute('title'); return; }" in title
    assert "label + ' (' + symbol + ')'" in title
    recompute = _rf_fn(body, "newModelRfRecomputeCondition")
    assert "window.newModelRfTitleOperator(sel, !!reason, locked);" in recompute
    # A range has no lone symbol; a locked branch keeps its reason (the
    # item's read).
    assert "window.newModelRfIsRangeOp(sel.value) ? ''" in title
    assert "if (locked) { title += '. ' + window.newModelRfConditionLockedMessage; }" in title
    assert "cond.setAttribute('title', window.newModelRfConditionLockedMessage);" in recompute
    states = _rf_fn(body, "newModelRfRecomputeActionStates")
    assert "if (typed && !reason) { nameBox.setAttribute('title', typed); }" in states
    assert "else { nameBox.removeAttribute('title'); }" in states


def test_a_lists_condition_puts_its_box_beside_a_shrunk_operator(
    client: TestClient, db: Session
) -> None:
    """The author's later 12A entry: a List condition's operator only needs
    room for "is not", so it shrinks, and its box (the List box's width)
    and "then show the below" follow it in the operator's cell, which
    takes the rest of the row; a number keeps the two-cell layout."""
    from .test_response_field_branching_save import _branched, _rfs, _save

    review_session, instrument, _, _ = _branched(client, db, "12a-list-condition")
    response = _save(client, review_session, instrument, _rfs(
        instrument,
        Rating={"data_type": "list", "list_options": "Agree, Neutral, Disagree",
                "min": "", "max": "", "step": "",
                "branch_op": "is_not", "branch_value": "Agree"},
    ))
    assert response.status_code == 200, response.text
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    flat = " ".join(body.split())
    condition = _rows_table(_card_slice(flat, instrument.id)).split(
        '<tr data-new-model-rf-condition class="rf-condition-list">'
    )[1].split("</tr>")[0]
    cells = condition.split("<td")[1:]
    op = cells[4]
    assert op.startswith(' class="rf-condition-cell rf-condition-op" colspan="8">')
    assert op.index("<select") < op.index("data-new-model-rf-condition-value")
    assert "<span data-new-model-rf-condition-then>then show the below</span>" in op
    assert cells[5].startswith(' colspan="7" class="rf-condition-cell" hidden>')
    # The script's two layouts, and the List box measured when Min hides.
    place = _rf_fn(body, "newModelRfPlaceConditionValue")
    assert "opCell.colSpan = isList ? 8 : 1;" in place
    assert "rest.hidden = isList;" in place
    size = _rf_fn(body, "newModelRfSizeCondition")
    assert "|| (list ? list.getBoundingClientRect().width : 0);" in size
    assert (
        "body.ui-v2 table.rf-table tr.rf-condition-list td.rf-condition-op select "
        "{ width: auto; }"
    ) in flat


def test_band_3_gives_display_fields_15_percent(client: TestClient, db: Session) -> None:
    """The author's later 12A entry: Band 3 splits 15 : 85 (was 1 : 4)."""
    _, _, _, flat = _page(client, db, "12a-band3-split")
    assert "grid-template-columns: minmax(0, 3fr) 17fr;" in flat
