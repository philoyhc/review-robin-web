"""The rule engine's edges (segment AD2C rung 6, `applydesk/rules.py`):
a fixed column, a tie at a ranking's cut, a ranking that waits on a
result not in, the cells it cannot judge yet, a combined result that is
unknown, and a hand's value kept unless asked. Parity with the page's
script is `test_rules_parity_browser.py`'s."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from applydesk import locks, rules, stages
from applydesk.rules import Cell, Column, Dossier
from applydesk.stages import Rule
from applydesk.tests._host import host_with


def _row(app: str, gate: str, result: str | None, out: str = "", **more: Cell) -> Dossier:
    results = {"r1": result} if result is not None else {}
    cells = {"g1": Cell(gate, results), "o1": Cell(out), **more}
    return Dossier(app, app.upper(), "Submitted", 1, {}, cells)


def _top(n: str) -> Column:
    rule = Rule((("top", "g1.r1", "le", n),), "Yes", "No")
    return Column("o1", "outcome", "Award", rule, scope=("g1",))


def test_a_fixed_column_is_left_and_said() -> None:
    rule = Rule((("status", "", "is", "Submitted"),), "Entered", "Not entered")
    got = rules.propose(
        [Column("g1", "gate", "Read", rule, fixed=True)],
        [_row("a", "—", None)],
        only_pending=False,
        replace_hand=False,
    )
    assert got.changes == ()
    assert got.skipped == ("Read: fixed, its Review Robin session has opened.",)


def test_the_best_n_takes_every_tie_at_the_cut() -> None:
    rows = [_row("a", "Entered", "5"), _row("b", "Entered", "4"), _row("c", "Entered", "4")]
    got = rules.propose([_top("2")], rows, only_pending=False, replace_hand=False)
    assert {(c.app, c.new) for c in got.changes} == {("a", "Yes"), ("b", "Yes"), ("c", "Yes")}
    assert got.skipped == ("Award: 3 at the cut of 2: tied.",)


def test_a_ranking_waits_on_a_result_not_in() -> None:
    rows = [_row("a", "Entered", "5"), _row("b", "—", None)]
    got = rules.propose([_top("1")], rows, only_pending=False, replace_hand=False)
    # a cannot be ranked while b's result is out: both left, named.
    assert got.changes == ()
    assert got.skipped == (
        "Award: 2 dossiers cannot be judged yet (a result not in), left as is: A, B.",
    )


def test_one_not_entered_has_no_place_in_the_ranking() -> None:
    rows = [_row("a", "Entered", "5"), _row("b", "Not entered", None)]
    got = rules.propose([_top("1")], rows, only_pending=False, replace_hand=False)
    assert {(c.app, c.new) for c in got.changes} == {("a", "Yes")}


def test_a_combined_result_with_a_result_out_is_unknown() -> None:
    rule = Rule((("comb", "", "ge", "3"),), "Yes", "No")
    column = Column("o1", "outcome", "Award", rule, scope=("g1",), weights=(("g1.r1", 1.0),))
    known = rules.propose(
        [column], [_row("a", "Entered", "3.5")], only_pending=False, replace_hand=False
    )
    assert [c.new for c in known.changes] == ["Yes"]
    unknown = rules.propose(
        [column], [_row("a", "—", None)], only_pending=False, replace_hand=False
    )
    assert unknown.changes == () and "cannot be judged yet" in unknown.skipped[0]


def test_a_hand_set_cell_is_kept_unless_asked() -> None:
    rule = Rule((("status", "", "is", "Submitted"),), "Yes", "No")
    column = Column("o1", "outcome", "Award", rule)
    row = Dossier("a", "A", "Submitted", 1, {}, {"o1": Cell("No", by_hand=True)})
    kept = rules.propose([column], [row], only_pending=False, replace_hand=False)
    assert kept.changes == ()
    replaced = rules.propose([column], [row], only_pending=False, replace_hand=True)
    assert [(c.old, c.new) for c in replaced.changes] == [("No", "Yes")]


def test_a_later_column_reads_what_this_run_gave_an_earlier_one() -> None:
    first = Column(
        "o1", "outcome", "Shortlist", Rule((("status", "", "is", "Submitted"),), "Yes", "No")
    )
    second = Column(
        "o2", "outcome", "Award", Rule((("out", "o1", "is", "Yes"),), "Given", "Not given")
    )
    row = Dossier("a", "A", "Submitted", 1, {}, {"o1": Cell(""), "o2": Cell("")})
    got = rules.propose([first, second], [row], only_pending=True, replace_hand=False)
    assert [(c.key, c.new) for c in got.changes] == [("o1", "Yes"), ("o2", "Given")]


URL = "/applydesk/operator/exercises/wa9juxbc2t/dossiers/proposal"


def _client() -> TestClient:
    return TestClient(host_with(("applydesk",))[0], follow_redirects=False)


def test_the_proposal_route_answers_for_the_table_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    """*Apply rules* (ruling 78): the page's table in, the engine's
    proposal out; a gate whose session has opened is left, said; a hand
    change the server has not seen is read."""
    client = _client()
    plan = stages.plan_of("wa9juxbc2t")
    row = next(r for r in plan.rows if r.application.state == "Submitted")
    app = row.application.public_id
    body = {"only_pending": False, "replace_hand": True, "cells": {}}
    reply = client.post(URL, json=body)
    assert reply.status_code == 200, reply.text
    got = reply.json()
    assert set(got) == {"changes", "skipped"}
    assert "Peer review: fixed, its Review Robin session has opened." in got["skipped"]
    monkeypatch.setattr(locks, "cells_lock", lambda e, g: locks.OPEN)
    # Its gate set to Not entered by hand on the page: the server reads
    # it, and the gate's rule (a submitted one is entered) moves it back.
    sent = {**body, "cells": {app: {"g1": ["Not entered", True]}}}
    after = client.post(URL, json=sent).json()
    assert {"app": app, "key": "g1", "from": "Not entered", "to": "Entered"} in after["changes"]
    kept = client.post(URL, json={**sent, "replace_hand": False}).json()
    assert not any(c["app"] == app and c["key"] == "g1" for c in kept["changes"])


def test_the_proposal_route_refuses_a_malformed_table() -> None:
    client = _client()
    for bad in (
        {"only_pending": True, "replace_hand": False, "cells": []},
        {"only_pending": "yes", "replace_hand": False, "cells": {}},
        {"only_pending": True, "replace_hand": False, "cells": {"a": {"g1": ["x"]}}},
        {"only_pending": True, "replace_hand": False, "cells": {"a": {"g1": ["x", "no"]}}},
    ):
        reply = client.post(URL, json=bad)
        assert reply.status_code == 400 and "malformed" in reply.json()["error"], bad
    assert client.post(URL, content=b"x", headers={"content-type": "text/plain"}).status_code == 415


def test_the_problems_route_says_what_a_rule_reads_amiss() -> None:
    """Process asks the server what each rule reads amiss (ruling 78), by
    the page's own keys, a new column's too; nothing is kept."""
    client = _client()
    outcome = {
        "key": "onew1",
        "label": "Award",
        "due": "",
        "values": ["Yes", "No"],
        "weights": {},
        "rule": {"when": [["status", "", "is", "Submitted"]], "then": "Maybe", "otherwise": "No"},
        "applicants_email": False,
        "evaluators_email": False,
    }
    stage = {
        "key": "",
        "name": "Review",
        "from": "",
        "to": "",
        "shown": True,
        "published": False,
        "form": None,
        "gates": [],
        "outcome": outcome,
    }
    url = "/applydesk/operator/exercises/wa9juxbc2t/process/problems"
    reply = client.post(url, json={"revision": 0, "stages": [stage]})
    assert reply.status_code == 200, reply.text
    assert reply.json()["problems"] == {"onew1": ["decides “Maybe”, not among its values"]}
    assert stages.plan_of("wa9juxbc2t").columns[0].key == "g1"  # nothing kept
    bad = client.post(url, json={"stages": "x"})
    assert bad.status_code == 400 and "malformed" in bad.json()["error"]


def test_rules_are_checked_while_another_field_is_half_typed() -> None:
    """Codex on #4156: a stage with one date, or a weight not yet a whole
    percent, no longer stops the rules being checked; Save still refuses
    them."""
    from applydesk import process_save

    client = _client()
    outcome = {
        "key": "onew1",
        "label": "Award",
        "due": "",
        "values": ["Yes", "No"],
        "weights": {"g1.r1": "ab"},
        "rule": {"when": [["status", "", "is", "Submitted"]], "then": "Maybe", "otherwise": "No"},
        "applicants_email": False,
        "evaluators_email": False,
    }
    stage = {
        "key": "",
        "name": "Review",
        "from": "2027-02-01T09:00",
        "to": "",
        "shown": True,
        "published": False,
        "form": None,
        "gates": [],
        "outcome": outcome,
    }
    sent = {"revision": 0, "stages": [stage]}
    url = "/applydesk/operator/exercises/wa9juxbc2t/process/problems"
    reply = client.post(url, json=sent)
    assert reply.status_code == 200, reply.text
    assert reply.json()["problems"]["onew1"] == ["decides “Maybe”, not among its values"]
    # Saving the same snapshot is still refused, the half-typed field named.
    with pytest.raises(process_save.Refused):
        process_save.build(sent, "wa9juxbc2t")


def test_a_long_outcome_value_does_not_spoil_the_proposal() -> None:
    """Codex on #4156: an outcome value may run to 500 characters."""
    plan = stages.plan_of("wa9juxbc2t")
    row = next(r for r in plan.rows if r.application.state == "Submitted")
    long = "x" * 400
    body = {
        "only_pending": True,
        "replace_hand": False,
        "cells": {row.application.public_id: {"o1": [long, True]}},
    }
    assert _client().post(URL, json=body).status_code == 200


@pytest.mark.parametrize("text", ["1_000", "nan", "inf", "-Infinity", "", "  ", "12x"])
def test_a_threshold_python_reads_but_a_rule_cannot_is_not_a_number(text: str) -> None:
    """The cold read on rung 6: ``float`` reads ``1_000``, ``nan`` and
    ``inf``, which the engine would read as ``1`` or never hold; the
    check must flag each, as the deleted page check did."""
    assert not stages._is_number(text)  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize("text", ["1000", " 2.5 ", "-3", "1e3"])
def test_a_threshold_that_is_a_number_reads_as_one(text: str) -> None:
    assert stages._is_number(text)  # pyright: ignore[reportPrivateUsage]


def test_a_body_nested_too_deep_is_refused_not_a_500() -> None:
    """The cold read on rung 6: ``json.loads`` raises ``RecursionError`` on
    a deep body; it reads as malformed rather than failing the request."""
    deep = b"[" * 100_000 + b"]" * 100_000
    reply = _client().post(URL, content=deep, headers={"content-type": "application/json"})
    assert reply.status_code == 400, reply.status_code
