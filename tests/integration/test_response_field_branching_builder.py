"""19T Item 10 rungs 6–7 — the builder: a saved branch renders in Band 3
as one ruled group (the parent, its condition row and the fields it
governs, under a bar), with ⑂ in its three states, and the row script
wires ⑂, the condition, and the rules inside a branch.

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
    _rf_fn,
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
    checkbox column, its checkbox in +'s, its + in ⑂'s, and its detach
    in the join column (rung 7b). Every row, the condition row included,
    spans the table's twelve columns."""
    _, _, card, _ = _page(client, db, "br-builder-align")
    table = _rows_table(card)
    parent, governed = _row(table, "Rating"), _row(table, "Comments")
    assert parent.count("<td") == governed.count("<td") == 12
    governed_cells = re.findall(r"<td[^>]*>", governed)
    assert 'class="col-shrink rf-branch-bar"' in governed_cells[0]
    assert "data-new-model-rf-active" in governed.split("<td")[2]
    assert "data-new-model-rf-add" in governed.split("<td")[3]
    assert "data-new-model-rf-join" in governed.split("<td")[4]
    assert "data-new-model-rf-join" in parent.split("<td")[4]
    assert "data-new-model-rf-name" in governed.split("<td")[5]
    assert "data-new-model-rf-name" in parent.split("<td")[5]
    assert "data-new-model-rf-fork" not in governed
    condition = table.split("<tr data-new-model-rf-condition>")[1].split("</tr>")[0]
    # Bar, (Active), "+", then "If the above" in the join column, the
    # operator in the name column and the rest across seven (19T Item 12A):
    # twelve columns, like a field row.
    assert condition.count("<td") == 6 and 'colspan="7"' in condition
    assert "If the above" in condition.split("<td")[4]
    assert "data-new-model-rf-condition-op" in condition.split("<td")[5]
    assert "<span data-new-model-rf-condition-then>then<select data-new-model-rf-condition-mode" in condition.split("<td")[6]


def test_fork_shows_its_three_states(client: TestClient, db: Session) -> None:
    _, _, card, _ = _page(client, db, "br-builder-fork")
    parent = _row(_rows_table(card), "Rating")
    fork = re.search(r"<button[^>]*data-new-model-rf-fork[^>]*>", parent).group(0)
    # Selected, and off, on a parent with a branch.
    assert 'class="btn rf-glyph"' in fork and 'aria-pressed="true"' in fork
    assert 'title="This field has a branch"' in fork and " disabled" in fork
    _, _, card, _ = _page(client, db, "br-builder-fork-none", branched=False)
    table = _rows_table(card)
    rating = re.search(
        r"<button[^>]*data-new-model-rf-fork[^>]*>", _row(table, "Rating")
    ).group(0)
    comments = re.search(
        r"<button[^>]*data-new-model-rf-fork[^>]*>", _row(table, "Comments")
    ).group(0)
    # Outline, and live, where a branch can be added; off on a String field.
    assert 'class="btn rf-glyph secondary"' in rating and " disabled" not in rating
    assert 'title="Add a branch below this field"' in rating
    assert 'onclick="newModelRfFork(this)"' in rating
    assert 'title="A String field can\'t have a branch"' in comments
    assert " disabled" in comments


def test_the_condition_row_shows_the_saved_condition(
    client: TestClient, db: Session
) -> None:
    _, _, card, _ = _page(client, db, "br-builder-cond")
    condition = _rows_table(card).split("<tr data-new-model-rf-condition>")[1]
    select = condition.split("</select>")[0]
    assert (
        '<option value="ge" data-symbol="≥" selected>is more than (inclusive)</option>'
        in select
    )
    # An Integer parent offers the ten spelled-out operators in the
    # author's order (19T Item 12), not "is" / "is not".
    assert re.findall(r'<option value="(\w+)"', select) == [
        "eq", "ne", "ge", "gt", "le", "lt", "in_inc", "in_exc", "out_inc", "out_exc"
    ]
    assert re.search(
        r'<input type="text" data-new-model-rf-condition-value[^>]*value="4"',
        condition,
    )


def test_branch_controls_are_wired(client: TestClient, db: Session) -> None:
    """Nothing is inert: the condition edits and adds, a governed row's R
    is live (19T Item 11), and a parent's X waits for its branch to go."""
    _, _, card, flat = _page(client, db, "br-builder-wired")
    assert "data-new-model-rf-branch-inert" not in flat
    table = _rows_table(card)
    condition = table.split("<tr data-new-model-rf-condition>")[1].split("</tr>")[0]
    assert 'onclick="newModelRfConditionAdd(this)"' in condition
    assert 'onchange="newModelRfConditionChanged(this)"' in condition
    assert 'oninput="newModelRfConditionChanged(this)"' in condition
    # No control is disabled; the mode's Require option is, until the rule
    # lands (19T Item 13 rung 1).
    assert " disabled" not in condition.replace('<option value="require" disabled>', "")
    governed = _row(table, "Comments")
    r = re.search(r"<button[^>]*data-new-model-rf-required[^>]*>", governed).group(0)
    assert " disabled" not in r and "can't be required" not in r
    assert 'onclick="newModelRfRequiredChanged(this)"' in r
    x = re.search(r"<button[^>]*data-new-model-rf-delete[^>]*>", _row(table, "Rating"))
    assert " disabled" in x.group(0) and 'title="Delete its branch first"' in x.group(0)
    # The operators by parent type, for a new condition row's select.
    ops = re.search(r"data-new-model-rf-branch-ops='([^']*)'", table).group(1)
    assert json.loads(ops.replace("&#34;", '"')) == {
        "numeric": [
            ["eq", "is equal to", "="], ["ne", "is not equal to", "≠"],
            ["ge", "is more than (inclusive)", "≥"],
            ["gt", "is more than (exclusive)", ">"],
            ["le", "is less than (inclusive)", "≤"],
            ["lt", "is less than (exclusive)", "<"],
            ["in_inc", "is within (inclusive)", "≤"],
            ["in_exc", "is within (exclusive)", "<"],
            ["out_inc", "is outside (inclusive)", "≤"],
            ["out_exc", "is outside (exclusive)", "<"],
        ],
        "list": [["is", "is", "is"], ["is_not", "is not", "is not"]],
        "range": ["in_exc", "in_inc", "out_exc", "out_inc"],
    }
    assert "<template data-new-model-rf-condition-template>" in flat


def test_governed_answers_lock_the_branch_on_the_page(
    client: TestClient, db: Session
) -> None:
    from sqlalchemy import select

    from app.db.models import Assignment, Response, Reviewee, Reviewer

    review_session, instrument, _, _ = _page(client, db, "br-builder-lock")
    comments = next(f for f in instrument.response_fields if f.label == "Comments")
    assignment = Assignment(
        session_id=review_session.id,
        reviewer_id=db.execute(
            select(Reviewer.id).where(Reviewer.session_id == review_session.id)
        ).scalars().first(),
        reviewee_id=db.execute(
            select(Reviewee.id).where(Reviewee.session_id == review_session.id)
        ).scalars().first(),
        instrument_id=instrument.id,
    )
    db.add(assignment)
    db.flush()
    db.add(Response(assignment_id=assignment.id, response_field_id=comments.id, value="x"))
    db.commit()
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    table = _rows_table(_card_slice(" ".join(body.split()), instrument.id))
    group = table.split("<tbody data-new-model-rf-group")[1]
    assert group.startswith(' data-new-model-rf-branch data-new-model-rf-branch-locked="true">')
    condition = group.split("<tr data-new-model-rf-condition>")[1].split("</tr>")[0]
    # The operator, both boxes (19T Item 12), the condition's "+" and the
    # mode select (19T Item 13), plus the mode's Require option, which the
    # scaffold always disables.
    assert condition.count(" disabled") == 6


def test_the_row_script_holds_the_branch_rules(client: TestClient, db: Session) -> None:
    review_session, instrument, _, flat = _page(client, db, "br-builder-js")
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text

    def _fn(_flat: str, name: str) -> str:
        return _rf_fn(body, name)

    recompute = _fn(flat, "newModelRfRecomputeActionStates")
    for rule in (
        "? !window.newModelRfBranchSibling(row, up)",
        "? 'Delete its branch first'",
        "'Delete this field and its branch'",
        "if (stringOpt) { stringOpt.disabled = isParent; }",
        "activeBox.disabled = parentHidden;",
        "window.newModelRfRecomputeCondition(group);",
    ):
        assert rule in recompute, rule
    # 19T Item 11 — R is live inside a branch: nothing turns it off there,
    # and the stager sends a governed row's R as it stands.
    assert "requiredBtn.setAttribute('data-required', 'false');" not in recompute
    stager = body[body.index("rf.row_key = row.getAttribute('data-row-key')"):]
    stager = stager[: stager.index("var cond = group")]
    assert "rf.required = false" not in stager
    # The condition mirrors ``condition_error``'s messages.
    error = _fn(flat, "newModelRfConditionError")
    for message in (
        "A String field can't have a branch.",
        "Choose at least one option for the branch condition.",
        "The branch condition names an option the list doesn't have: ",
        "Choose a comparison for the branch condition.",
        "The branch condition needs a number.",
    ):
        assert message in error, message
    # ⑂ makes the field a parent with a condition and one governed field.
    fork = _fn(flat, "newModelRfFork")
    assert "row.setAttribute('data-new-model-rf-parent', 'true');" in fork
    assert "window.newModelRfNewGovernedRow(band3, cond)" in fork
    # The last governed field's X takes the condition with it.
    delete = _fn(flat, "newModelRfDeleteRow")
    assert "if (last) { window.newModelRfEndBranch(group); }" in delete
    end = _fn(flat, "newModelRfEndBranch")
    assert "if (cond) { cond.remove(); }" in end
    assert "parent.removeAttribute('data-new-model-rf-parent');" in end
    # The Active cascade.
    active = _fn(flat, "newModelRfToggleActive")
    assert "group.querySelectorAll('[data-new-model-rf-governed]')" in active
    # The stager sends the row key, the parent by row key and the condition.
    start = flat.index("function saveBand2State(card, opts) {")
    stager = flat[start : flat.index("window.newModelStageBand2State = saveBand2State;")]
    for line in (
        "rf.row_key = row.getAttribute('data-row-key') || '';",
        "rf.branch_parent = parentRow ? parentRow.getAttribute('data-row-key') : null;",
        "rf.branch_op = opSel && opSel.value ? opSel.value : null;",
        "rf.branch_value = window.newModelRfConditionValue(cond);",
    ):
        assert line in stager, line
    # The preview mutes a governed column.
    assert "branchHint: row.hasAttribute('data-new-model-rf-governed')" in flat
    assert "class=\"rs-branch-closed\"" in flat


def test_join_and_detach_show_their_states(client: TestClient, db: Session) -> None:
    """Rung 7b: join on a plain row, detach on a governed one; +, ⑂ and it
    share one width (``.rf-glyph``). Join reads ↰ and detach ↳ (the author,
    19T Item 12A: they were the other way round)."""
    _, _, card, flat = _page(client, db, "br-builder-join")
    table = _rows_table(card)
    detach = re.search(r"<button[^>]*data-new-model-rf-join[^>]*>↳", _row(table, "Comments"))
    assert detach and 'title="Detach this field and end its branch"' in detach.group(0)
    parent_join = re.search(r"<button[^>]*data-new-model-rf-join[^>]*>↰", _row(table, "Rating"))
    # The first row, and a parent, can't join.
    assert parent_join and " disabled" in parent_join.group(0)
    for marker in ("data-new-model-rf-add", "data-new-model-rf-fork", "data-new-model-rf-join"):
        button = re.search(rf"<button[^>]*{marker}[^>]*>", _row(table, "Rating")).group(0)
        assert "rf-glyph" in button, marker
    assert (
        "body.ui-v2 table.rf-table .btn.rf-glyph { width: var(--rf-glyph-width); padding-left: 0; "
        "padding-right: 0; text-align: center; }"
    ) in flat


def test_the_row_script_joins_and_detaches(client: TestClient, db: Session) -> None:
    review_session, instrument, _, _ = _page(client, db, "br-builder-join-js")
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    sync = _rf_fn(body, "newModelRfSyncJoin")
    for title in (
        "The first field can't join a branch",
        "A field with a branch can't join another",
        "It has saved responses, so it can't move into a branch",
        "Its branch has saved responses, so no field can join it",
        "The field above is String, so it can't have a branch",
        "Join the branch above",
        "Start a branch on the field above with this field",
        "Detach this field and end its branch",
        "Move this field out of its branch",
    ):
        assert title in sync, title
    join = _rf_fn(body, "newModelRfJoin")
    # Detach lands the row directly below its branch; the last one ends it.
    assert "group.insertAdjacentElement('afterend', own);" in join
    assert "window.newModelRfEndBranch(group);" in join
    # A detached row's Active box comes back, though its hidden parent had
    # turned it off (Codex on #2646).
    ungoverned = _rf_fn(body, "newModelRfMakeUngoverned")
    assert "active.disabled = false;" in ungoverned
    # Joining a plain field starts a branch with an empty condition.
    assert "parent.setAttribute('data-new-model-rf-parent', 'true');" in join
    assert "window.newModelRfMakeGoverned(row);" in join
    recompute = _rf_fn(body, "newModelRfRecomputeActionStates")
    assert "window.newModelRfSyncJoin(row);" in recompute


def test_the_preview_counts_items_as_the_surface_does(
    client: TestClient, db: Session
) -> None:
    """The cumulative read's finding 4: the sample row is unanswered, so a
    governed field's branch is closed and it isn't an item, as the
    surface's "All items completed" counts it."""
    review_session, instrument, card, _ = _page(client, db, "br-builder-count")
    assert "<span data-new-model-intro-all-count>1</span>" in card
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    skip_governed = "return !row.hasAttribute('data-new-model-rf-governed');"
    for start in ("window.newModelUpdateIntroProgress =", "function buildProgressPills(card) {"):
        at = body.index(start)
        assert skip_governed in body[at : body.index("\n          }", at)], start


def test_saving_the_card_keeps_the_branch(client: TestClient, db: Session) -> None:
    """A payload without branch keys keeps the stored branch (rung 2's
    rules): the keys are each independently present."""
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
