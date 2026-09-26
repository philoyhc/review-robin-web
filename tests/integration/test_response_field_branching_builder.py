"""19T Item 10 rung 6 — the builder scaffold: a saved branch renders in
Band 3 as one ruled group (the parent, its condition row and the fields
it governs, under a bar), with ⑂ in its three states. The branch
controls are inert until the builder rung wires them.

The new-model instrument gets a branch directly: Rating (Integer) governs
Comments while Rating ≥ 4."""

from __future__ import annotations

import json
import re

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from .test_instrument_builder_routes import (
    _band2_rfs,
    _card_slice,
    _new_model_with_tags,
)


def _page(client: TestClient, db: Session, code: str, *, branched: bool = True):
    review_session, instrument = _new_model_with_tags(client, db, code=code)
    if branched:
        fields = {f.label: f for f in instrument.response_fields}
        fields["Rating"].branch_op, fields["Rating"].branch_value = "ge", "4"
        fields["Comments"].branch_parent_id = fields["Rating"].id
        db.commit()
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    flat = " ".join(body.split())
    return review_session, instrument, _card_slice(flat, instrument.id), flat


def _rows_table(card: str) -> str:
    start = card.index("<table class=\"rf-table\" data-new-model-rf-rows")
    return card[start : card.index("</table>", start)]


def _row(table: str, label: str) -> str:
    for chunk in table.split("<tr ")[1:]:
        if f'data-label="{label}"' in chunk:
            return chunk.split("</tr>")[0]
    raise AssertionError(label)


def test_a_branch_is_one_ruled_group(client: TestClient, db: Session) -> None:
    _, _, card, _ = _page(client, db, "br-builder-group")
    table = _rows_table(card)
    groups = table.split("<tbody data-new-model-rf-group")[1:]
    assert len(groups) == 1
    group = groups[0]
    assert group.startswith(" data-new-model-rf-branch>")
    # Parent, then its condition row, then the governed field.
    assert group.index('data-label="Rating"') < group.index(
        "data-new-model-rf-condition>"
    ) < group.index('data-label="Comments"')


def test_rows_align_from_the_name_onward(client: TestClient, db: Session) -> None:
    """A governed row shifts one column before the name: the bar in the
    checkbox column, its checkbox in +'s, its + in ⑂'s. Every row, the
    condition row included, spans the table's eleven columns."""
    _, _, card, _ = _page(client, db, "br-builder-align")
    table = _rows_table(card)
    parent, governed = _row(table, "Rating"), _row(table, "Comments")
    assert parent.count("<td") == governed.count("<td") == 11
    governed_cells = re.findall(r"<td[^>]*>", governed)
    assert 'class="col-shrink rf-branch-bar"' in governed_cells[0]
    assert "data-new-model-rf-active" in governed.split("<td")[2]
    assert "data-new-model-rf-add" in governed.split("<td")[3]
    assert "data-new-model-rf-name" in governed.split("<td")[4]
    assert "data-new-model-rf-name" in parent.split("<td")[4]
    assert "data-new-model-rf-fork" not in governed
    condition = table.split("<tr data-new-model-rf-condition>")[1].split("</tr>")[0]
    assert condition.count("<td") == 4 and 'colspan="8"' in condition
    assert "If the above" in condition and "then show the below" in condition


def test_fork_shows_its_three_states(client: TestClient, db: Session) -> None:
    _, _, card, _ = _page(client, db, "br-builder-fork")
    parent = _row(_rows_table(card), "Rating")
    fork = re.search(r"<button[^>]*data-new-model-rf-fork[^>]*>", parent).group(0)
    # Selected on a parent with a branch.
    assert 'class="btn"' in fork and 'aria-pressed="true"' in fork
    assert 'title="This field has a branch"' in fork
    _, _, card, _ = _page(client, db, "br-builder-fork-none", branched=False)
    table = _rows_table(card)
    rating = re.search(
        r"<button[^>]*data-new-model-rf-fork[^>]*>", _row(table, "Rating")
    ).group(0)
    comments = re.search(
        r"<button[^>]*data-new-model-rf-fork[^>]*>", _row(table, "Comments")
    ).group(0)
    # Outline where a branch can be added; inactive on a String field.
    assert 'class="btn secondary"' in rating
    assert 'title="Add a branch below this field"' in rating
    assert 'title="A String field can\'t have a branch"' in comments
    # All inert until the builder rung.
    assert all(" disabled" in b for b in (fork, rating, comments))


def test_the_condition_row_shows_the_saved_condition(
    client: TestClient, db: Session
) -> None:
    _, _, card, _ = _page(client, db, "br-builder-cond")
    condition = _rows_table(card).split("<tr data-new-model-rf-condition>")[1]
    select = condition.split("</select>")[0]
    assert '<option value="ge" selected>≥</option>' in select
    # An Integer parent offers the six comparisons, not "is".
    assert re.findall(r'<option value="(\w+)"', select) == [
        "eq", "ne", "gt", "ge", "lt", "le"
    ]
    assert re.search(
        r'<input type="text" data-new-model-rf-condition-value[^>]*value="4"',
        condition,
    )


def test_branch_controls_are_inert_until_wired(
    client: TestClient, db: Session
) -> None:
    """Marked inert, and the row recompute keeps them disabled; a
    parent's X reads "Delete its branch first"."""
    _, _, card, flat = _page(client, db, "br-builder-inert")
    table = _rows_table(card)
    governed = _row(table, "Comments")
    for marker in ("data-new-model-rf-active", "data-new-model-rf-add",
                   "data-new-model-rf-required", 'data-new-model-rf-move="up"',
                   'data-new-model-rf-move="down"', "data-new-model-rf-delete"):
        control = re.search(rf"<(?:button|input)[^>]*{marker}[^>]*>", governed).group(0)
        assert "data-new-model-rf-branch-inert" in control, marker
    parent = _row(table, "Rating")
    x = re.search(r"<button[^>]*data-new-model-rf-delete[^>]*>", parent).group(0)
    assert "data-new-model-rf-branch-inert" in x
    assert 'title="Delete its branch first"' in x
    r = re.search(r"<button[^>]*data-new-model-rf-required[^>]*>", governed).group(0)
    assert "A field inside a branch can't be required" in r
    recompute = flat[flat.index("window.newModelRfRecomputeActionStates = "):]
    recompute = recompute[: recompute.index("window.newModelRfFieldChanged")]
    assert "row.querySelectorAll('[data-new-model-rf-branch-inert]')" in recompute
    assert "control.disabled = true;" in recompute


def test_saving_the_card_keeps_the_branch(client: TestClient, db: Session) -> None:
    """The card's Save sends the governed row like any other, without
    branch keys, and the branch stays stored (rung 2's rules)."""
    review_session, instrument, _, _ = _page(client, db, "br-builder-save")
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/save",
        data={"band2_state_snapshot": json.dumps(
            {"selected_display_keys": [], "response_fields": _band2_rfs(instrument)}
        )},
        follow_redirects=False,
    )
    assert response.status_code == 200, response.text
    db.expire_all()
    fields = {f.label: f for f in instrument.response_fields}
    assert fields["Comments"].branch_parent_id == fields["Rating"].id
    assert fields["Rating"].branch_op == "ge"
