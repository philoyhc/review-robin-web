"""19T Item 13 — the condition row's "then [mode]" select: "then" and a
select of Show the below / Require the below (else, optional) (rung 1's
scaffold), wired at rung 4: it shows the saved mode, the card's Save sends
it, a Require branch's rows grey out R, and the preview marks and counts
their fields as the surface does."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from .test_instrument_builder_routes import _card_slice, _rf_fn
from .test_response_field_branching_builder import _page, _row, _rows_table

_MODE = "data-new-model-rf-condition-mode"


def _mode_select(html: str) -> str:
    match = re.search(rf"<select {_MODE}[^>]*>.*?</select>", html, re.S)
    assert match, "no mode select"
    return match.group(0)


def test_the_condition_row_reads_then_and_a_mode_select(
    client: TestClient, db: Session
) -> None:
    _, _, card, flat = _page(client, db, "13-select")
    condition = _rows_table(card).split("<tr data-new-model-rf-condition>")[1].split("</tr>")[0]
    assert "then show the below" not in flat
    then = condition[condition.index("<span data-new-model-rf-condition-then>") :]
    assert then.startswith(f"<span data-new-model-rf-condition-then>then<select {_MODE}")
    select = _mode_select(condition)
    assert 'aria-label="What the condition does to the fields below"' in select
    assert 'onchange="newModelRfConditionChanged(this)"' in select
    options = re.findall(r"<option ([^>]*)>([^<]*)</option>", select)
    assert options == [
        ('value="show" selected', "Show the below"),
        ('value="require"', "Require the below (else, optional)"),
    ]
    # "then" keeps a 4px gap before the select in either layout.
    assert (
        "body.ui-v2 table.rf-table td.rf-condition-cell "
        "[data-new-model-rf-condition-then] select { margin: 0 0 0 4px; }"
    ) in flat
    # The ⑂ template's condition row carries the same select.
    template = flat.split("<template data-new-model-rf-condition-template>")[1].split("</template>")[0]
    assert _mode_select(template) == select


def test_the_mode_select_locks_with_its_condition(
    client: TestClient, db: Session
) -> None:
    """A locked branch's condition can't change, so neither can its mode;
    the row script disables it with the operator."""
    review_session, instrument, _, flat = _page(client, db, "13-select-lock")
    script = " ".join(re.findall(r"<script>(.*?)</script>", flat, re.S))
    assert (
        f"var mode = cond.querySelector('[{_MODE}]'); "
        "[sel, input, high, add, mode].forEach(function (c) { if (c) { c.disabled = locked; } });"
    ) in script
    # A branch with saved responses renders its mode select disabled.
    from sqlalchemy import select

    from app.db.models import Assignment, Response, Reviewee, Reviewer

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
    card = _card_slice(" ".join(body.split()), instrument.id)
    condition = _rows_table(card).split("<tr data-new-model-rf-condition>")[1].split("</tr>")[0]
    assert _mode_select(condition).startswith(f"<select {_MODE} disabled ")


def _require_page(client: TestClient, db: Session, code: str):
    """Rating ≥ 4 requires Comments, which is itself marked required."""
    review_session, instrument, _, _ = _page(client, db, code)
    fields = {f.label: f for f in instrument.response_fields}
    fields["Rating"].branch_mode = "require"
    fields["Comments"].required = True
    db.commit()
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    flat = " ".join(body.split())
    return review_session, instrument, _card_slice(flat, instrument.id), flat, body


def test_a_require_branch_renders_its_mode_and_greys_out_r(
    client: TestClient, db: Session
) -> None:
    """The saved mode is selected; a governed row's R is off, titled with
    what decides it, and keeps its own value for a return to Show. The
    parent's R, outside the branch, stays live."""
    _, instrument, card, _, _ = _require_page(client, db, "13-require-page")
    table = _rows_table(card)
    condition = table.split("<tr data-new-model-rf-condition>")[1].split("</tr>")[0]
    options = re.findall(r"<option ([^>]*)>([^<]*)</option>", _mode_select(condition))
    assert options == [
        ('value="show"', "Show the below"),
        ('value="require" selected', "Require the below (else, optional)"),
    ]
    r = re.search(r"<button[^>]*data-new-model-rf-required[^>]*>", _row(table, "Comments"))
    assert 'disabled aria-disabled="true" title="Required while the condition holds"' in r.group(0)
    assert 'data-required="true"' in r.group(0)
    parent = re.search(r"<button[^>]*data-new-model-rf-required[^>]*>", _row(table, "Rating"))
    assert " disabled" not in parent.group(0)


def test_a_require_branchs_fields_are_items_on_the_sample_row(
    client: TestClient, db: Session
) -> None:
    """The sample row is unanswered, so a Require branch's condition
    doesn't hold: its field is an item (unlike a Show branch's, which is
    closed) and not required, as the surface counts it."""
    _, instrument, card, _, _ = _require_page(client, db, "13-require-count")
    fields = {f.label: f for f in instrument.response_fields}
    assert "<span data-new-model-intro-all-count>2</span>" in card
    # Only the parent's own R counts; Comments' condition doesn't hold.
    required = int(fields["Rating"].required)
    assert f"<span data-new-model-intro-required-count>{required}</span>" in card


def test_the_row_script_wires_the_mode(client: TestClient, db: Session) -> None:
    _, _, _, flat, body = _require_page(client, db, "13-require-js")
    # The stager sends the mode with the condition, and null on every
    # other row, which clears one.
    start = flat.index("function saveBand2State(card, opts) {")
    stager = flat[start : flat.index("window.newModelStageBand2State = saveBand2State;")]
    for line in (
        "rf.branch_mode = null;",
        f"var modeSel = cond.querySelector('[{_MODE}]');",
        "rf.branch_mode = modeSel && modeSel.value ? modeSel.value : null;",
    ):
        assert line in stager, line
    # A governed row is under Require while its condition row says so.
    at = body.index("function rfRowUnderRequire(row) {")
    under = " ".join(body[at : body.index("\n          }", at)].split())
    # Its own parent's condition row, at either level (19T Item 14).
    assert "var cond = rfRowCondition(rfRowParent(row));" in under
    assert f"var mode = cond && cond.querySelector('[{_MODE}]');" in under
    assert "return !!(mode && mode.value === 'require');" in under
    # R greys out under Require, after the blank-row gate.
    recompute = " ".join(_rf_fn(body, "newModelRfRecomputeActionStates").split())
    gate = recompute.index("_blankRowGate(requiredBtn,")
    lock = recompute.index("window.newModelRfUnderRequire(row)")
    assert gate < lock
    assert "requiredBtn.setAttribute('title', 'Required while the condition holds');" in recompute
    # A mode change re-runs the governed rows' states.
    changed = " ".join(_rf_fn(body, "newModelRfConditionChanged").split())
    assert "group.querySelectorAll('[data-new-model-rf-governed]').forEach" in changed
    assert "window.newModelRfRecomputeActionStates(r);" in changed
    # The preview marks a Require branch's field "*", as it may be required.
    assert "required: rfRowUnderRequire(row) || rfRowRequired(row)," in flat
