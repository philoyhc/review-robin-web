"""19T Item 14 rung 3 — the builder renders a two-level branch, as the
author's mockup and ours laid it out: each level shifts one column right,
into the two empty slots after join, so the name column never moves; a
level-1 row carries ⑂ (inert until rung 4), a level-2 row none; a
condition row's "+" sits under its parent's ⑂. The structure rules still
refuse a second level, so each test seeds the chain in the database:
Familiarity > 0 governs Rating, and Rating ≥ 4 governs Comments."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import InstrumentResponseField

from .test_instrument_builder_routes import _card_slice, _rf_fn
from .test_response_field_branching_builder import _page, _row, _rows_table


def _chain_page(client: TestClient, db: Session, code: str, **modes: str):
    review_session, instrument, _, _ = _page(client, db, code)
    fields = {f.label: f for f in instrument.response_fields}
    familiarity = InstrumentResponseField(
        instrument_id=instrument.id, field_key="familiarity", label="Familiarity",
        order=fields["Rating"].order - 1, _inline_data_type="Integer",
        branch_op="gt", branch_value="0", branch_mode=modes.get("familiarity"),
    )
    db.add(familiarity)
    db.flush()
    fields["Rating"].branch_parent_id = familiarity.id
    fields["Rating"].branch_mode = modes.get("rating")
    db.commit()
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    flat = " ".join(body.split())
    return review_session, instrument, _card_slice(flat, instrument.id), flat, body


def _cells(row: str) -> list[str]:
    return row.split("<td")[1:]


def test_a_chain_is_one_ruled_group_with_two_condition_rows(
    client: TestClient, db: Session
) -> None:
    _, _, card, _, _ = _chain_page(client, db, "two-level-group")
    table = _rows_table(card)
    groups = table.split("<tbody data-new-model-rf-group")[1:]
    chain = next(g for g in groups if 'data-label="Familiarity"' in g)
    order = [
        m.group(1) or "condition"
        for m in re.finditer(r'<tr data-new-model-rf-(?:row[^>]*data-label="([^"]+)"|condition)', chain)
    ]
    assert order == ["Familiarity", "condition", "Rating", "condition", "Comments"]
    for label, level in (("Familiarity", 0), ("Rating", 1), ("Comments", 2)):
        assert f'data-new-model-rf-level="{level}"' in _row(table, label), label


def test_each_level_shifts_one_column_and_the_name_stays(
    client: TestClient, db: Session
) -> None:
    _, _, card, _, _ = _chain_page(client, db, "two-level-align")
    table = _rows_table(card)
    rows = {label: _cells(_row(table, label)) for label in ("Familiarity", "Rating", "Comments")}
    for label, cells in rows.items():
        assert len(cells) == 14, label
        assert "data-new-model-rf-name" in cells[6], label
    # Familiarity: Active, +, ⑂, ↰, two slots.
    fam = rows["Familiarity"]
    assert "data-new-model-rf-active" in fam[0] and "rf-branch-bar-start" in fam[0]
    assert "data-new-model-rf-fork" in fam[2] and "data-new-model-rf-join" in fam[3]
    assert fam[4].startswith(' class="col-shrink rf-slot">') and fam[5].startswith(' class="col-shrink rf-slot">')
    # Rating: bar, Active (its own bar starts here), +, ⑂, ↳, one slot.
    rating = rows["Rating"]
    assert "rf-branch-bar" in rating[0]
    assert "data-new-model-rf-active" in rating[1] and "rf-branch-bar-start" in rating[1]
    assert "data-new-model-rf-add" in rating[2]
    assert "data-new-model-rf-fork" in rating[3] and "data-new-model-rf-join" in rating[4]
    assert rating[5].startswith(' class="col-shrink rf-slot">')
    # Comments: two bars, Active, +, ⑂'s slot left empty, ↳.
    comments = rows["Comments"]
    assert "rf-branch-bar" in comments[0] and "rf-branch-bar" in comments[1]
    assert "data-new-model-rf-active" in comments[2] and "data-new-model-rf-add" in comments[3]
    assert comments[4].startswith(' class="col-shrink rf-slot">')
    assert "data-new-model-rf-join" in comments[5] and ">↳</button>" in comments[5]
    assert "data-new-model-rf-fork" not in _row(table, "Comments")


def test_a_condition_rows_plus_sits_under_its_parents_fork(
    client: TestClient, db: Session
) -> None:
    _, _, card, _, _ = _chain_page(client, db, "two-level-conditions")
    table = _rows_table(card)
    conditions = [c.split("</tr>")[0] for c in table.split("<tr data-new-model-rf-condition")[1:]]
    level1, level2 = (_cells(c) for c in conditions)
    # Level 1: bar, blank, "+" (under Familiarity's ⑂), the lead across 3.
    assert "rf-branch-bar" in level1[0] and "data-new-model-rf-condition-add" in level1[2]
    assert 'colspan="3">If the above' in level1[3]
    # Level 2: two bars, blank, "+" (under Rating's ⑂), the lead across 2.
    assert "rf-branch-bar" in level2[0] and "rf-branch-bar" in level2[1]
    assert "data-new-model-rf-condition-add" in level2[3]
    assert 'colspan="2">If the above' in level2[4]
    # Each shows its own condition.
    assert 'value="0"' in conditions[0] and 'value="4"' in conditions[1]


def test_a_level_one_fork_shows_but_stays_off(client: TestClient, db: Session) -> None:
    _, _, card, _, body = _chain_page(client, db, "two-level-fork")
    table = _rows_table(card)
    fork = re.search(r"<button[^>]*data-new-model-rf-fork[^>]*>", _row(table, "Rating")).group(0)
    assert " disabled" in fork and 'title="This field has a branch"' in fork
    join = re.search(r"<button[^>]*data-new-model-rf-join[^>]*>", _row(table, "Rating")).group(0)
    assert " disabled" in join and "A field with a branch can't leave its branch" in join
    recompute = " ".join(_rf_fn(body, "newModelRfRecomputeActionStates").split())
    assert (
        "} else if (row.hasAttribute('data-new-model-rf-governed')) { "
        "// 19T Item 14 rung 3 — shown on a level-1 row, not yet live. "
        "forkBtn.disabled = true; "
        "forkBtn.setAttribute('title', \"A branch inside a branch isn't available yet\");"
    ) in recompute


def test_a_plain_governed_rows_fork_is_off_with_the_reason(
    client: TestClient, db: Session
) -> None:
    """One level, as today: Comments is a String, so its ⑂ says so; an
    Integer governed row's ⑂ says a branch inside a branch isn't
    available yet."""
    review_session, instrument, card, _ = _page(client, db, "two-level-fork-plain")
    comments = next(f for f in instrument.response_fields if f.label == "Comments")
    fork = re.search(r"<button[^>]*data-new-model-rf-fork[^>]*>", _row(_rows_table(card), "Comments")).group(0)
    assert " disabled" in fork
    comments._inline_data_type = "Integer"
    db.commit()
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    card = _card_slice(" ".join(body.split()), instrument.id)
    fork = re.search(r"<button[^>]*data-new-model-rf-fork[^>]*>", _row(_rows_table(card), "Comments")).group(0)
    assert " disabled" in fork and "A branch inside a branch isn&#39;t available yet" in fork


def test_the_preview_counts_an_item_only_if_every_branch_above_is_require(
    client: TestClient, db: Session
) -> None:
    for modes, items in (
        ({}, 1),
        ({"rating": "require"}, 1),
        ({"familiarity": "require"}, 2),
        ({"familiarity": "require", "rating": "require"}, 3),
    ):
        code = "two-level-count-" + "-".join(sorted(modes)) if modes else "two-level-count"
        _, _, card, _, _ = _chain_page(client, db, code, **modes)
        assert f"<span data-new-model-intro-all-count>{items}</span>" in card, modes


def test_the_row_script_reads_a_rows_own_parent_and_condition(
    client: TestClient, db: Session
) -> None:
    _, _, _, flat, body = _chain_page(client, db, "two-level-js")
    at = body.index("function rfRowParent(row) {")
    parent = " ".join(body[at : body.index("function rfRowCondition", at)].split())
    assert "if (prev.hasAttribute('data-new-model-rf-row') && rfRowLevel(prev) < level) {" in parent
    start = flat.index("function saveBand2State(card, opts) {")
    stager = flat[start : flat.index("window.newModelStageBand2State = saveBand2State;")]
    assert "var parentRow = rfRowParent(row);" in stager
    assert "? rfRowCondition(row) : null;" in stager
    hint = " ".join(_rf_fn(body, "newModelRfBranchHint").split())
    assert "var parent = window.newModelRfParentOf(row); var cond = window.newModelRfConditionOf(parent);" in hint
    sync = " ".join(_rf_fn(body, "newModelRfSyncConditionOps").split())
    assert "var parent = parentRow || group.querySelector('[data-new-model-rf-parent]');" in sync
