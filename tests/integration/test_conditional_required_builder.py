"""19T Item 13 rung 1 — the condition row's "then [mode]" select, as a
scaffold: it reads "then" and a select of Show the below / Require the below
(else, optional), Show the only choice, and nothing reads or
saves it until the rule lands (rung 3)."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from .test_instrument_builder_routes import _card_slice
from .test_response_field_branching_builder import _page, _rows_table

_MODE = "data-new-model-rf-condition-mode"


def _mode_select(html: str) -> str:
    match = re.search(rf"<select {_MODE}[^>]*>.*?</select>", html, re.S)
    assert match, "no mode select"
    return match.group(0)


def test_the_condition_row_reads_then_and_a_mode_select(
    client: TestClient, db: Session
) -> None:
    _, _, card, flat = _page(client, db, "13-scaffold")
    condition = _rows_table(card).split("<tr data-new-model-rf-condition>")[1].split("</tr>")[0]
    assert "then show the below" not in flat
    then = condition[condition.index("<span data-new-model-rf-condition-then>") :]
    assert then.startswith(f"<span data-new-model-rf-condition-then>then<select {_MODE}")
    select = _mode_select(condition)
    assert 'aria-label="What the condition does to the fields below"' in select
    options = re.findall(r"<option ([^>]*)>([^<]*)</option>", select)
    assert options == [
        ('value="show" selected', "Show the below"),
        ('value="require" disabled', "Require the below (else, optional)"),
    ]
    # "then" keeps a 4px gap before the select in either layout.
    assert (
        "body.ui-v2 table.rf-table td.rf-condition-cell "
        "[data-new-model-rf-condition-then] select { margin: 0 0 0 4px; }"
    ) in flat
    # The ⑂ template's condition row carries the same select.
    template = flat.split("<template data-new-model-rf-condition-template>")[1].split("</template>")[0]
    assert _mode_select(template) == select


def test_the_mode_select_locks_with_its_condition_and_nothing_saves_it(
    client: TestClient, db: Session
) -> None:
    """A locked branch's condition can't change, so neither can its mode;
    the row script disables it with the operator. Scaffold: the only
    script that names the select is that lock."""
    review_session, instrument, _, flat = _page(client, db, "13-scaffold-lock")
    script = " ".join(re.findall(r"<script>(.*?)</script>", flat, re.S))
    # Each card carries the row script; each copy names the select once.
    assert script.count(_MODE) == script.count("var mode = cond.querySelector") > 0
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
