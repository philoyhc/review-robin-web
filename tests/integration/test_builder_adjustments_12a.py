"""19T Item 12A — small adjustments to Band 3's response-field table, on
the author's instruction: join reads ↰ and detach ↳; a number's condition
boxes take the parent's Min width; the Active checkbox is centered in its
cell."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from .test_instrument_builder_routes import _rf_fn
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
    recompute = _rf_fn(body, "newModelRfRecomputeCondition")
    assert "window.newModelRfSizeCondition(parent);" in recompute
