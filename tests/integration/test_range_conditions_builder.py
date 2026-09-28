"""19T Item 12 rung 3 — the builder authors a range condition: the card's
Save stores "low to high", the condition row renders two boxes for a range
and one otherwise, and the row script joins, checks and titles them."""

from __future__ import annotations

import html
import json
import re
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.responses import RANGE_OPS, condition_error

from .test_instrument_builder_routes import _card_slice, _rf_fn
from .test_response_field_branching_builder import _page, _rows_table
from .test_response_field_branching_save import _branched, _rfs, _save


def test_the_card_saves_a_range_and_refuses_a_bad_one(
    client: TestClient, db: Session
) -> None:
    review_session, instrument, rating, _ = _branched(client, db, "range-save")
    response = _save(client, review_session, instrument, _rfs(
        instrument, Rating={"branch_op": "out_exc", "branch_value": "2 to 4"}
    ))
    assert response.status_code == 200, response.text
    db.expire_all()
    assert (rating.branch_op, rating.branch_value) == ("out_exc", "2 to 4")

    response = _save(client, review_session, instrument, _rfs(
        instrument, Rating={"branch_op": "in_inc", "branch_value": "2 to "}
    ))
    assert response.status_code == 422
    assert response.json()["errors"] == ["Rating: The range's high end needs a number."]


def _condition(client: TestClient, review_session, instrument) -> str:
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    table = _rows_table(_card_slice(" ".join(body.split()), instrument.id))
    return table.split("<tr data-new-model-rf-condition>")[1].split("</tr>")[0]


def test_a_range_renders_two_boxes_and_a_single_value_one(
    client: TestClient, db: Session
) -> None:
    review_session, instrument, _, flat = _page(client, db, "range-render")
    condition = flat.split("<tr data-new-model-rf-condition>")[1].split("</tr>")[0]
    # "ge 4": the second box is hidden and empty.
    assert "<span data-new-model-rf-condition-range hidden>" in condition
    assert re.search(r'data-new-model-rf-condition-high[^>]*value=""', condition)

    rating = next(f for f in instrument.response_fields if f.label == "Rating")
    rating.branch_op, rating.branch_value = "in_exc", "1.5 to 4"
    db.commit()
    condition = _condition(client, review_session, instrument)
    assert "<span data-new-model-rf-condition-range>" in condition
    assert re.search(r'data-new-model-rf-condition-value[^>]*value="1.5"', condition)
    assert re.search(r'data-new-model-rf-condition-high[^>]*value="4"', condition)
    assert (
        '<option value="in_exc" data-symbol="&lt;" selected>is within (exclusive)</option>'
        in condition
    )


def test_the_row_script_joins_checks_and_titles_a_range(
    client: TestClient, db: Session
) -> None:
    review_session, instrument, _, _ = _page(client, db, "range-js")
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    value = _rf_fn(body, "newModelRfConditionValue")
    assert "return lowText + ' to ' + (high ? high.value.trim() : '');" in value
    sync = _rf_fn(body, "newModelRfSyncConditionRange")
    assert "span.hidden = !isRange;" in sync
    assert "if (!isRange && high) { high.value = ''; }" in sync
    error = _rf_fn(body, "newModelRfConditionError")
    for message in (
        "The branch condition needs a range: a low and a high number.",
        "The range's low end needs a number.",
        "The range's high end needs a number.",
        "The range's low end must be below its high end.",
    ):
        assert message in error, message
    # The operators come from the server, not a list in the script (the
    # hardcode Item 11 found).
    assert "['eq', 'ne', 'gt', 'ge', 'lt', 'le']" not in body
    assert "window.newModelRfBranchOps().numeric" in error
    hint = _rf_fn(body, "newModelRfBranchHint")
    assert "option.getAttribute('data-symbol')" in hint


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_builders_check_agrees_with_save(client: TestClient, db: Session) -> None:
    """``newModelRfConditionError`` run in node, over the page's own operators,
    against ``condition_error`` on the value Save sees (stripped): every pair
    of boxes is refused or accepted alike, with the same message (the item's
    cumulative read)."""
    review_session, instrument, _, _ = _page(client, db, "range-parity")
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    ops = html.unescape(
        re.search(r"data-new-model-rf-branch-ops='([^']*)'", body).group(1)
    )
    boxes = ["", " ", "2", " 2 ", "4", "-1", "1.", "x", "to", "2 to", "to 4",
             "3 to 5", "inf", "1_000"]
    cases = [
        [op, low, high]
        for op in sorted(RANGE_OPS) + ["ge", "eq"]
        for low in boxes
        for high in boxes
    ]
    script = (
        "var window = {newModelRfBranchOps: function () { return "
        + ops + "; }};\n"
        + _rf_fn(body, "newModelRfIsRangeOp") + "\n        };\n"
        + _rf_fn(body, "newModelRfConditionError") + "\n        };\n"
        + "const cases = JSON.parse(process.argv[1]);\n"
        + "console.log(JSON.stringify(cases.map(function (c) {\n"
        + "  var value = window.newModelRfIsRangeOp(c[0])\n"
        + "    ? c[1].trim() + ' to ' + c[2].trim() : c[1].trim();\n"
        + "  return [value, window.newModelRfConditionError('integer', '', c[0], value)];\n"
        + "})));\n"
    )
    out = subprocess.run(
        ["node", "-e", script, json.dumps(cases)],
        capture_output=True, text=True, check=True,
    ).stdout
    results = json.loads(out)
    mismatches = [
        (op, value, js)
        for (op, _, _), (value, js) in zip(cases, results)
        if js != condition_error("Integer", None, op, value.strip())
    ]
    assert not mismatches, mismatches[:10]
    assert any(js is None for _, js in results)


def test_no_button_on_the_page_is_inline_styled(client: TestClient, db: Session) -> None:
    """``spec/ui_elements.md`` §6: an inline ``style`` on a button is a
    defect. The builders' last eight moved to the Observers builder's
    classes (Codex on #2659)."""
    review_session, instrument, _, _ = _page(client, db, "range-no-inline")
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    for tag in re.finditer(r"<button\b[^>]*>", body, re.S):
        assert "style=" not in tag.group(0), tag.group(0)[:120]
    source = open("app/web/templates/operator/instruments_index.html").read()
    for tag in re.finditer(r"<button\b[^>]*>", source, re.S):
        assert "style=" not in tag.group(0), tag.group(0)[:120]
