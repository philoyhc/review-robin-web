"""The rule engine's edges (segment AD2C rung 6, `applydesk/rules.py`):
a fixed column, a tie at a ranking's cut, a ranking that waits on a
result not in, the cells it cannot judge yet, a combined result that is
unknown, and a hand's value kept unless asked. Parity with the page's
script is `test_rules_parity_browser.py`'s."""

from __future__ import annotations

from applydesk import rules
from applydesk.rules import Cell, Column, Dossier
from applydesk.stages import Rule


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
