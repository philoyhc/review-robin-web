"""19T Item 12A — small adjustments to Band 3's response-field table, on
the author's instruction: join reads ↰ and detach ↳ (pinned in
``test_join_and_detach_show_their_states``); a number's condition boxes
take the parent's Min width; the Active checkbox is centered in its cell."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from .test_instrument_builder_routes import _rf_fn
from .test_response_field_branching_builder import _page, _row, _rows_table


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
