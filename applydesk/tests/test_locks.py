"""A stage's status and what it locks (segment AD1K rung 2, ruling 35):
the model alone, no page reads it yet."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

from applydesk import locks, sample_data, stages, timeline

RA = "wa9juxbc2t"  # stages 1–2 done, stage 3 under way
DRAFT = "c4xh2ndv6s"  # nothing published, a gate with no evaluators
BLANK = "n5wg8tjr3e"


def _e(public_id: str) -> sample_data.Exercise:
    e = sample_data.exercise(public_id)
    assert e is not None
    return e


def _stage(public_id: str, n: int) -> stages.Stage:
    return stages.plan_of(public_id).stages[n - 1]


def test_a_stage_completes_when_its_end_has_passed_and_its_items_are_done() -> None:
    e = _e(RA)
    assert [locks.stage_status(e, st) for st in stages.plan_of(RA).stages] == [
        "Completed",  # its form closed, its end passed
        "Completed",  # both gates' results in, Shortlisting released
        "Published",  # its end, 4 Dec, still ahead
    ]
    assert locks.exercise_status(e) == "Published"


def test_an_item_open_after_the_end_leaves_the_stage_overdue() -> None:
    e, st = _e(RA), _stage(RA, 3)
    later = datetime(2026, 12, 5, 9)
    assert locks.stage_status(e, st, later) == "Overdue"
    assert locks.outstanding(e, st) == (
        "Staff interview's results are not in",
        "Selection is not released",
    )


def test_an_extension_keeps_the_stage_open() -> None:
    """Author, 2026-11-18: moving the end later is how a stage is kept
    from completing or reopened."""
    e, st = _e(RA), _stage(RA, 3)
    assert st.when is not None
    extended = replace(st, when=stages.span(st.when.start, stages.day(2026, 12, 18)))
    assert locks.stage_status(e, extended, datetime(2026, 12, 5, 9)) == "Published"
    assert locks.end_lock(e, extended) == locks.OPEN  # the end stays editable


def test_a_draft_stage_is_draft_whatever_its_dates() -> None:
    e = _e(DRAFT)
    assert {locks.stage_status(e, st) for st in stages.plan_of(DRAFT).stages} == {"Draft"}
    assert locks.exercise_status(e) == "Draft"


def test_publishing_names_what_the_stage_lacks() -> None:
    """AD-20: Process's Outline problems block the stage, not only Home's."""
    e = _e(DRAFT)
    first, second = stages.plan_of(DRAFT).stages
    assert locks.publish_problems(e, first) == ("Stage 1 has no start and end.",)
    assert locks.publish_problems(e, second) == (
        "Selection has no start and end.",
        "Stage 1 is not published yet.",
        "Gate 1 (Placement interview) has no evaluators.",
    )
    blank = _e(BLANK)
    assert locks.publish_problems(blank, _stage(BLANK, 1)) == (
        "Stage 1 has no start and end.",
        "Exercise Code is not set.",
        "Description is not set.",
        "Who may apply is not set.",
        "The application form has no questions.",
    )
    assert locks.publish_problems(_e(RA), _stage(RA, 3)) == ()


def test_a_published_stage_locks_what_it_holds_and_says_why() -> None:
    e = _e(RA)
    review, interviews = _stage(RA, 2), _stage(RA, 3)
    assert locks.stage_lock(e, interviews).fixed
    assert "Interviews is published" in locks.stage_lock(e, interviews).reason
    assert locks.form_lock(e).fixed  # AD-03
    g1, o2 = review.columns[0], interviews.columns[1]
    assert isinstance(g1, stages.Gate) and isinstance(o2, stages.Outcome)
    # An opened gate says the stronger reason, which a revert does not lift.
    assert locks.item_lock(e, g1).reason.startswith("Its Review Robin session has opened")
    assert locks.item_lock(e, o2).fixed  # AD-01
    assert locks.cells_lock(e, g1).fixed  # AD-04
    g3 = interviews.columns[0]
    assert isinstance(g3, stages.Gate) and not locks.cells_lock(e, g3).fixed  # not sent yet
    assert locks.blind_lock(e).fixed  # AD-05


def test_a_draft_locks_nothing() -> None:
    e = _e(DRAFT)
    st = _stage(DRAFT, 2)
    g = st.columns[0]
    assert isinstance(g, stages.Gate)
    for lock in (
        locks.stage_lock(e, st),
        locks.form_lock(e),
        locks.item_lock(e, g),
        locks.blind_lock(e),
    ):
        assert lock == locks.OPEN


def test_a_revert_says_what_stays() -> None:
    e = _e(RA)
    assert locks.revert_warnings(e, _stage(RA, 1)) == (
        "100 submitted applications stay submitted.",
    )
    assert locks.revert_warnings(e, _stage(RA, 2)) == (
        "Gate 1's Review Robin session has opened: it stays fixed.",
        "Gate 2's Review Robin session has opened: it stays fixed.",
    )
    assert locks.revert_warnings(e, _stage(RA, 3)) == ()


def test_publishing_reads_the_outline_s_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Codex: a gate whose Total cannot hold, or a rule reading what is
    gone, blocks its stage as Process's Outline says."""
    e = _e(RA)
    model = stages._STAGES[RA]  # pyright: ignore[reportPrivateUsage]  -- a sample's shape
    interviews = model[2]
    g3, o2 = interviews.columns
    assert isinstance(g3, stages.Gate) and isinstance(o2, stages.Outcome) and o2.rule
    bad_gate = replace(g3, total=stages.Total(0, 999))
    bad_rule = replace(o2.rule, when=(("out", "o9", "is", "Interview"),), then="Hired")
    broken = replace(interviews, columns=(bad_gate, replace(o2, rule=bad_rule)))
    monkeypatch.setitem(stages._STAGES, RA, (*model[:2], broken))  # pyright: ignore[reportPrivateUsage]  -- as above
    problems = locks.publish_problems(e, broken)
    assert any(p.startswith("Gate 3 (Staff interview): the Total's") for p in problems)
    assert "Selection's rule reads an outcome no longer in the process." in problems
    assert "Selection's rule decides \u201cHired\u201d, not among its values." in problems


def test_publishing_reads_each_source(monkeypatch: pytest.MonkeyPatch) -> None:
    """Codex: a source whose panel is gone gives no evaluators, whatever
    its Total, so the stage cannot be published."""
    e = _e(RA)
    model = stages._STAGES[RA]  # pyright: ignore[reportPrivateUsage]  -- a sample's shape
    interviews = model[2]
    g3, o2 = interviews.columns
    assert isinstance(g3, stages.Gate)
    gone = replace(
        g3, sources=(stages.Source("panel", "missing-panel", 2, 2),), total=stages.Total(2, 2)
    )
    broken = replace(interviews, columns=(gone, o2))
    monkeypatch.setitem(stages._STAGES, RA, (*model[:2], broken))  # pyright: ignore[reportPrivateUsage]  -- as above
    assert locks.publish_problems(e, broken) == (
        "Gate 3 (Staff interview): source 1's panel is gone.",
    )


def test_a_reversed_range_is_no_dates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Codex: an end before the start is refused at publishing, never
    completes a stage, and the timeline shows no dates for it."""
    e = _e(RA)
    model = stages._STAGES[RA]  # pyright: ignore[reportPrivateUsage]  -- a sample's shape
    interviews = model[2]
    assert interviews.when is not None
    back = replace(interviews, when=stages.StageDates(interviews.when.end, interviews.when.start))
    monkeypatch.setitem(stages._STAGES, RA, (*model[:2], back))  # pyright: ignore[reportPrivateUsage]  -- as above
    assert "Interviews ends before it starts." in locks.publish_problems(e, back)
    assert locks.stage_status(e, back, datetime(2027, 1, 1)) == "Published"
    assert timeline.of(e).stages[2].when == "Dates not set"


def test_publishing_reads_how_a_rule_compares(monkeypatch: pytest.MonkeyPatch) -> None:
    """Codex: a result compared with what is not a number, or a combined
    result likewise, blocks the stage as Process's Outline says."""
    e = _e(RA)
    model = stages._STAGES[RA]  # pyright: ignore[reportPrivateUsage]  -- a sample's shape
    interviews = model[2]
    g3, o2 = interviews.columns
    assert isinstance(o2, stages.Outcome) and o2.rule
    bad = replace(
        o2.rule,
        when=(("res", "g3.r1", "ge", "not-a-number"), ("comb", "", "ge", "x")),
    )
    broken = replace(interviews, columns=(g3, replace(o2, rule=bad)))
    monkeypatch.setitem(stages._STAGES, RA, (*model[:2], broken))  # pyright: ignore[reportPrivateUsage]  -- as above
    problems = locks.publish_problems(e, broken)
    assert "Selection's rule compares with \u201cnot-a-number\u201d, not a number." in problems
    assert "Selection's rule compares with \u201cx\u201d, not a number." in problems


def test_an_item_s_dates_default_to_its_stage_s() -> None:
    """Author, 2026-11-18: an item with no dates of its own runs on its
    stage's; an outcome's are the stage's start to its due."""
    first, review = _stage(RA, 1), _stage(RA, 2)
    assert stages.window(first, None) == first.when
    g1, o1 = review.columns[0], review.columns[2]
    assert isinstance(g1, stages.Gate) and isinstance(o1, stages.Outcome)
    assert stages.window(review, g1) == g1.when
    w = stages.window(review, o1)
    assert review.when is not None and w is not None
    assert (w.start, w.end) == (review.when.start, o1.due_at)
    blank = replace(o1, due_at=None)
    assert stages.window(review, blank) == review.when


def test_items_fall_inside_their_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    """Author, 2026-11-18: each item's dates sit inside its stage's, and
    an outcome is due no sooner than the gates it reads close."""
    e = _e(RA)
    model = stages._STAGES[RA]  # pyright: ignore[reportPrivateUsage]  -- a sample's shape
    interviews = model[2]
    g3, o2 = interviews.columns
    assert isinstance(g3, stages.Gate) and isinstance(o2, stages.Outcome)
    late = replace(g3, when=stages.span(stages.day(2026, 11, 9), stages.day(2026, 12, 9)))
    early = replace(o2, due_at=stages.day(2026, 11, 20, 17))
    broken = replace(interviews, columns=(late, early))
    monkeypatch.setitem(stages._STAGES, RA, (*model[:2], broken))  # pyright: ignore[reportPrivateUsage]  -- as above
    assert locks.publish_problems(e, broken) == (
        "Gate 3 (Staff interview) runs outside the dates of Interviews.",
        "Selection is due before Staff interview closes.",
    )
    after = replace(o2, due_at=stages.day(2026, 12, 10))
    backwards = replace(
        g3, when=stages.StageDates(stages.day(2026, 12, 1), stages.day(2026, 11, 10))
    )
    broken = replace(interviews, columns=(backwards, after))
    monkeypatch.setitem(stages._STAGES, RA, (*model[:2], broken))  # pyright: ignore[reportPrivateUsage]  -- as above
    assert locks.publish_problems(e, broken) == (
        "Gate 3 (Staff interview) ends before it starts.",
        "Selection is due outside the dates of Interviews.",
    )


def test_the_form_s_dates_sit_inside_its_stage() -> None:
    e, first = _e(RA), _stage(RA, 1)
    assert first.when is not None
    wide = replace(first, form_when=stages.span(first.when.start, stages.day(2026, 10, 3)))
    assert locks.publish_problems(e, wide) == ("The form runs outside the dates of Applications.",)
