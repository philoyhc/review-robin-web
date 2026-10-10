"""19T Item 12A — small adjustments to Band 3's response-field table, on
the author's instruction: join reads ↰ and detach ↳; a number's condition
boxes take the parent's Min width; the Active checkbox is centered in its
cell."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from .test_instrument_builder_routes import _card_slice, _rf_fn
from .test_reviewer_response_flow import intro_columns
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
    assert len(calls) == 11, calls
    detach_titles = {
        "A field with a branch can't leave its branch",
        "Its branch has saved responses, so its fields can't change",
        "Detach this field and end its branch",
        "Move this field out of its branch",
    }
    for glyph, title in calls:
        assert glyph == ("↳" if title in detach_titles else "↰"), (glyph, title)
    template = flat.split("<template data-new-model-rf-row-template>")[1].split("</template>")[0]
    assert re.search(r"<button[^>]*data-new-model-rf-join[^>]*>↰</button>", template)


def test_the_name_chip_starts_every_row_flush_left(
    client: TestClient, db: Session
) -> None:
    """ux_refinements Item 1 (12A centered the checkbox it replaces): the
    Active checkbox sits in the field's name chip, the row's first cell,
    flush left and capped."""
    _, _, card, flat = _page(client, db, "12a-active")
    table = _rows_table(card)
    for name in ("Rating", "Comments"):
        row = _row(table, name)
        first = re.search(r"<td[^>]*>.*?</td>", row.split(">", 1)[1]).group(0)
        assert first.startswith('<td class="col-shrink rf-active-cell"><label class="pill pill-count tag-chip rf-name-chip"'), name
        assert "data-new-model-rf-active" in first, name
        assert f"<span data-new-model-rf-chip-label>{name}</span>" in first, name
    # A row the script adds from the template has one too, labeled by the
    # row script.
    template = flat.split("<template data-new-model-rf-row-template>")[1].split("</template>")[0]
    assert '<td class="col-shrink rf-active-cell"><label class="pill pill-count tag-chip rf-name-chip"' in template
    assert "<span data-new-model-rf-chip-label></span>" in template
    assert "body.ui-v2 table.rf-table td.rf-active-cell { text-align: left; }" in flat
    assert "max-width: 8em;" in flat.split("body.ui-v2 table.rf-table label.rf-name-chip {")[1].split("}")[0]


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
    of the same width, on the server's rows and the template's. 19T Item
    14 made the space two empty slot columns, which a branch's rows
    shift into: two after a top-level row's join, none after a level-1
    row's, whose ↰ fills the last (rung 5)."""
    _, _, card, flat = _page(client, db, "12a-join-room")
    table = _rows_table(card)
    slot = '<td class="col-shrink rf-slot"></td>'
    for name, slots in (("Rating", 2), ("Comments", 0)):
        row = _row(table, name)
        assert '<td class="col-shrink rf-join-cell" data-new-model-rf-join-cell>' in row
        after_join = row.split("data-new-model-rf-join-cell>")[1].split('<td class="rf-name">')[0]
        assert after_join.count(slot) == slots, name
    template = flat.split("<template data-new-model-rf-row-template>")[1].split("</template>")[0]
    assert '<td class="col-shrink rf-join-cell" data-new-model-rf-join-cell>' in template
    assert template.count(slot) == 2
    # Each slot is a button wide (``.rf-glyph``'s width, one variable for
    # both), with a cell's two paddings, as a button's cell has.
    # R, ≡, ▲, ▼ and X set the width (ux_refinements Item 1).
    assert "body.ui-v2 table.rf-table { --rf-glyph-width: 2rem; }" in flat
    assert (
        "body.ui-v2 table.rf-table .btn.rf-glyph, "
        "body.ui-v2 table.rf-table td.col-shrink > .btn { width: var(--rf-glyph-width);"
    ) in flat
    assert "body.ui-v2 table.rf-table td.rf-slot { width: var(--rf-glyph-width); }" in flat
    assert "padding-right: calc(2 * var(--rf-glyph-width)" not in flat


def test_the_operator_takes_the_name_column_and_the_lead_aligns_right(
    client: TestClient, db: Session
) -> None:
    """The author's later 12A entry: the condition's operator sits in the
    name column at the name box's width, with "If the above" right-aligned
    before it."""
    _, _, card, flat = _page(client, db, "12a-operator")
    condition = _rows_table(card).split("<tr data-new-model-rf-condition>")[1].split("</tr>")[0]
    cells = condition.split("<td")[1:]
    # A level-1 condition's lead spans the join column and both slots.
    assert 'class="col-shrink rf-condition-cell rf-condition-lead" colspan="3">If the above</td>' in cells[3]
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
    and "then [mode]" (19T Item 13) follow it in the operator's cell, which
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
    assert "<span data-new-model-rf-condition-then>then<select data-new-model-rf-condition-mode" in op
    assert cells[5].startswith(' colspan="7" class="rf-condition-cell" hidden>')
    # One value box, in the operator's cell, not a second in the hidden one.
    assert condition.count("data-new-model-rf-condition-value") == 1
    assert "data-new-model-rf-condition-value" not in cells[5]
    # No gap-making whitespace between the box and its text, as the script
    # leaves none (the item's read).
    assert '"> <span data-new-model-rf-condition-then>' not in op
    # The script's two layouts, and the List box measured when Min hides.
    # The call that makes a fork, a join or a type change re-lay the row.
    sync = _rf_fn(body, "newModelRfSyncConditionOps")
    assert "window.newModelRfPlaceConditionValue(cond, isList);" in sync
    place = _rf_fn(body, "newModelRfPlaceConditionValue")
    assert "opCell.colSpan = isList ? 8 : 1;" in place
    assert "rest.hidden = isList;" in place
    size = _rf_fn(body, "newModelRfSizeCondition")
    assert "|| (list ? list.getBoundingClientRect().width : 0);" in size
    assert (
        "body.ui-v2 table.rf-table tr.rf-condition-list td.rf-condition-op select "
        "{ width: auto; }"
    ) in flat


def test_a_quick_fill_preset_snaps_the_type_before_the_options_event(
    client: TestClient, db: Session
) -> None:
    """A Quick fill preset on a List parent used to turn "is not" into "is":
    the options' input event recomputed the row while the type still read
    ``preset:…``, rebuilding the condition's operators as numbers. The type
    snaps to "list" first now (found by the item's read of #2665)."""
    review_session, instrument, _, _ = _page(client, db, "12a-quick-fill")
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    bounds = _rf_fn(body, "newModelRfSyncBounds")
    snap = bounds.index("select.value = 'list';")
    fire = bounds.index("listInput.dispatchEvent(new Event('input', { bubbles: true }));")
    assert snap < fire


def test_the_response_field_table_scrolls_rather_than_squeezing(
    client: TestClient, db: Session
) -> None:
    """The author's later 12A entry: on a narrow card the response-field
    table scrolls sideways in its ``.table-scroll``, as the display-field
    table does. Its track has a 0 minimum, and the table a floor, since its
    boxes would otherwise shrink to nothing before it scrolled."""
    _, _, card, flat = _page(client, db, "12a-rf-scroll")
    assert "grid-template-columns: minmax(0, 3fr) minmax(0, 17fr);" in flat
    assert "body.ui-v2 table.rf-table { min-width: 66rem; }" in flat
    assert ".band3-grid[inert]" not in flat
    table_at = card.index('<table class="rf-table" data-new-model-rf-rows')
    assert card.rindex('<div class="table-scroll">', 0, table_at) > card.rindex("</div>", 0, table_at)


def test_a_locked_card_locks_band_3s_tables_not_their_scrollers(
    client: TestClient, db: Session
) -> None:
    """The author's later 12A entry: a locked card scrolls both Band 3
    tables too. An inert element can't be scrolled, so the lock regions
    are the tables themselves; the band and the ``.table-scroll`` wrappers
    stay outside them."""
    review_session, instrument, _, _ = _page(client, db, "12a-locked-scroll")
    for query, locked in (("", True), (f"?editing={instrument.id}", False)):
        body = client.get(
            f"/operator/sessions/{review_session.id}/instruments{query}"
        ).text
        card = _card_slice(" ".join(body.split()), instrument.id)
        band3 = card[card.index("<div data-new-model-band3 ") :]
        assert band3[: band3.index(">")] == '<div data-new-model-band3 class="band3-grid"'
        for marker in ("data-new-model-df-table", "data-new-model-rf-rows"):
            at = band3.index(marker)
            tag = band3[band3.rindex("<table", 0, at) : band3.index(">", at)]
            assert "data-lock-region" in tag, marker
            assert ('inert aria-hidden="true"' in tag) is locked, (marker, locked)
            before = band3[: band3.rindex("<table", 0, at)]
            assert before.rindex('<div class="table-scroll">') > before.rfind("</div>")
            assert "inert" not in before[before.rindex('<div class="table-scroll">') :]
        # Nothing Band 3 holds outside its two tables and its templates
        # may take input, since only the tables are locked (the item's read).
        band3 = band3[: band3.index("<template data-new-model-rf-condition-template>")]
        band3 = re.sub(r"<template\b.*?</template>", "", band3)
        outside = re.sub(r"<table\b.*?</table>", "", band3)
        assert re.search(r"<(input|button|select|textarea|a)\b", outside) is None


def _open_tag(html: str, marker: str) -> str:
    at = html.index(marker)
    return html[html.rindex("<", 0, at) : html.index(">", at)]


def test_a_locked_card_scrolls_band_2s_visibility_table(
    client: TestClient, db: Session
) -> None:
    """The author's later 12A entry, after the read of Band 3's: Band 2's
    lock regions are the intro card, the visibility editor and the
    preview, so the locked "Who can see what you wrote" table, which holds
    no control, keeps a scroller that scrolls. That card fades with the
    intro card beside it. The preview's own scroller wraps it from outside
    (a later entry), so it scrolls too."""
    review_session, instrument, _, flat = _page(client, db, "12a-band2-scroll")
    assert (
        '[data-instrument-card][data-instrument-locked="true"] '
        "[data-new-model-band2-vp-preview-card] { opacity: 0.75; }"
    ) in flat
    for query, locked in (("", True), (f"?editing={instrument.id}", False)):
        body = client.get(
            f"/operator/sessions/{review_session.id}/instruments{query}"
        ).text
        card = _card_slice(" ".join(body.split()), instrument.id)
        band2 = card[card.index("<div data-new-model-band2-editable") :]
        band2 = band2[: band2.index("<script>")]
        assert band2.startswith("<div data-new-model-band2-editable>")
        for marker in (
            "data-intro-edit-block",
            "data-new-model-vp-editor",
            "data-new-model-band2-preview",
        ):
            tag = _open_tag(band2, marker)
            assert "data-lock-region" in tag, marker
            assert ('inert aria-hidden="true"' in tag) is locked, (marker, locked)
        # The preview's .table-scroll wraps it directly, outside its lock.
        wrapper = band2[: band2.index("<div data-new-model-band2-preview ")]
        assert wrapper.endswith('<div class="table-scroll" style="margin-top: 16px;"> ')
        table = _open_tag(band2, 'class="table-scroll" data-lock-only')
        assert "inert" not in table and "data-lock-region" not in table
        # Band 2 holds no control outside its lock regions (the
        # item's read). Each region is cut out up to the next sibling
        # after it: the vp card's heading, then its editor's close.
        outside = band2[: band2.index('<div class="card rs-instrument-card rs-intro-name" data-intro-edit-block')]
        vp = band2[band2.index("data-new-model-band2-vp-preview-card") :]
        outside += vp[: vp.index("data-new-model-vp-editor")]
        after_editor = vp[vp.index("</table>", vp.index("data-new-model-vp-editor")) :]
        outside += after_editor[: after_editor.index("data-new-model-band2-preview")]
        for control in (r"<(input|button|select|textarea|a)\b", r'role="button"', r"tabindex"):
            assert re.search(control, outside) is None, control


def test_band_1_scrolls_rather_than_spilling(
    client: TestClient, db: Session
) -> None:
    """The author's later 12A entry: Band 1's three columns keep a floor
    and scroll in a ``.table-scroll`` on a narrow card, locked or not; the
    grid inside it is the lock region, never the scroller."""
    review_session, instrument, _, flat = _page(client, db, "12a-band1-scroll")
    assert re.search(
        r"body\.ui-v2 \.band1-grid \{ display: grid; "
        r"grid-template-columns: 1fr 1fr 1fr; gap: 0; min-width: 76rem; \}",
        flat,
    )
    for query, locked in (("", True), (f"?editing={instrument.id}", False)):
        body = client.get(
            f"/operator/sessions/{review_session.id}/instruments{query}"
        ).text
        card = _card_slice(" ".join(body.split()), instrument.id)
        tag = _open_tag(card, 'class="band1-grid"')
        assert "data-lock-region" in tag
        assert ('inert aria-hidden="true"' in tag) is locked
        before = card[: card.index('class="band1-grid"')]
        assert before.endswith('<div class="table-scroll"> <div data-lock-region ')
        # A rule's tag select gives way to a wider operator ("IS DIFFERENT
        # FROM" spilled at every width) rather than holding half its row.
        selects = re.findall(r'<select style="([^"]*)" form="dfsave-\d+" name="link\d_field"', card)
        assert selects and all(s.startswith("flex: 0 1 50%;") for s in selects)


def test_band_2s_intro_is_two_columns(client: TestClient, db: Session) -> None:
    """19T Item 17: Band 2's intro mirrors the reviewer surface's two
    columns — the name card over the visibility card on the left, and
    the JS-built help cards in the right column's one stack, out of the
    preview. Rung 4 retired the measured split, so nothing re-places them."""
    _, _, card, _ = _page(client, db, "17-intro-columns")
    cols = intro_columns(card)
    assert cols["left"].index("rs-intro-name") < cols["left"].index("rs-intro-visibility")
    assert "data-rs-help-stack" not in cols["left"]
    assert '<div class="rs-help-stack" data-rs-help-stack>' in cols["right"]
    assert "rs-intro-name" not in cols["right"] and "rs-intro-visibility" not in cols["right"]
    assert "rs-intro-grid" not in card and "rs-help-grid" not in card
    # The help cards are placed in the stack, not the preview container.
    assert "helpStack.innerHTML = buildResponseFieldHelpCards(card)" in card
    assert "container.innerHTML = buildResponseFieldHelpCards(card)" not in card
    for retired in ("data-rs-intro-js", "rrwIntro", "data-rs-intro-split"):
        assert retired not in card
