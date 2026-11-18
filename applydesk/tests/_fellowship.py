"""The fellowship's process, kept for the Process page's browser tests
(segment AD1H). The model exercise became the RA recruitment (ruling 30);
the editor's tests still want a process with a combined result and its
weights, a nominated source, an outcome decided by hand and four stages,
so they install this one on the conference grant (``EX``), whose form
asks for a preferred reviewer and whose panels are the fellowship's. Its
gates are as the fellowship left them: Review sent and in, the Interview
ready (ruling 29).

It is a copy, frozen as the fellowship left it: nothing ties it to
`applydesk/stages.py`, and the conference grant it sits on is open for
applications, which the fellowship never was while sending gates. Use it
for what the editor does with a process's shape, never for what an
exercise's state means."""

from __future__ import annotations

import pytest

from applydesk import stages, workflow
from applydesk.stages import (
    Field,
    Gate,
    GateResult,
    Outcome,
    ResponseField,
    Rule,
    Source,
    Stage,
    Total,
    day,
    span,
)

EX = "r6tm4kq9wz"

_LIKERT = Field("integer", "1", "5", "1")
_EVERYONE = Rule(
    (("status", "", "is", "Submitted"), ("last", "", "le", "1")), "Entered", "Not entered"
)
_G1 = Gate(
    "g1",
    1,
    "Peer Review",
    "RRW",
    (
        GateResult("r1", "Rating", _LIKERT, "mean", at_least=2, source="rating"),
        GateResult("r2", "Comments", Field("string", max="2000"), "join", source="comments"),
    ),
    _EVERYONE,
    "panel-a",
    # Ruling 27's shape (segment AD1G): the candidate's preferred reviewer
    # first, Panel A topping up to two.
    (Source("nominated", "Preferred reviewer", 0, 1), Source("panel", "panel-a", 1, 2)),
    Total(2, 2),
    description=(
        "Two reviewers read each dossier's Shown to reviewers part and rate it,"
        " one the applicant's preferred reviewer where they named one."
    ),
    fields=(
        ResponseField("rating", "Rating", _LIKERT, True, "1 weak, 5 outstanding"),
        ResponseField("comments", "Comments", Field("string", max="2000")),
    ),
)
_G2 = Gate(
    "g2",
    2,
    "Faculty Panel Review",
    "RRW",
    (
        GateResult("r1", "Score", _LIKERT, "mean"),
        GateResult(
            "r2",
            "Recommendation",
            Field("list", options="Fund, Fund if possible, Do not fund"),
            "share",
            "Fund",
        ),
    ),
    _EVERYONE,
    "panel-b",
    # Its pairs were suggested, then approved before sending (AD1G).
    mode="suggested",
)
_O1 = Outcome(
    "o1",
    1,
    "Shortlist for interview",
    ("Shortlisted", "Not shortlisted"),
    "10 Nov",
    "10 Nov · to applicants",
    (("g1.r1", 0.3), ("g2.r1", 0.7)),
    Rule((("comb", "", "ge", "4.2"),), "Shortlisted", "Not shortlisted"),
)
_G3 = Gate(
    "g3",
    3,
    "Interview",
    "RRW",
    (GateResult("r1", "Score", _LIKERT, "mean", at_least=2),),
    Rule((("out", "o1", "is", "Shortlisted"),), "Entered", "Not entered"),
    "interviewers",
)
_O2 = Outcome(
    "o2",
    2,
    "Finalists",
    ("Finalist", "Not a finalist"),
    "24 Nov",
    "",
    (("g3.r1", 1.0),),
    Rule((("res", "g3.r1", "ge", "4.0"),), "Finalist", "Not a finalist"),
)
_O3 = Outcome("o3", 3, "Final results", ("Awarded", "Waitlisted", "Not awarded"), "12 Dec", "")


STAGES: tuple[Stage, ...] = (
    Stage(1, "Call for applications", span(day(2026, 9, 1), day(2026, 10, 15)), form=True),
    Stage(2, "Review", span(day(2026, 10, 16), day(2026, 11, 10)), (_G1, _G2, _O1)),
    Stage(3, "Interview", span(day(2026, 11, 11), day(2026, 11, 24)), (_G3, _O2)),
    Stage(4, "Decision", span(day(2026, 11, 25), day(2026, 12, 12)), (_O3,)),
)
GATES = {
    "g1": ("Results in", "92 of 92 reviewed"),
    "g2": ("Results in", "92 of 92 reviewed"),
    "g3": ("Ready", ""),
}
APPLICANTS, EVALUATORS = workflow.APPLICANTS, workflow.EVALUATORS
SENDS = frozenset(
    {
        ("receipt", APPLICANTS),
        ("reminder", APPLICANTS),
        ("o1", APPLICANTS),
        ("o2", APPLICANTS),
        ("o2", EVALUATORS),
        ("o3", APPLICANTS),
    }
)


WRITTEN = frozenset(
    {
        ("receipt", APPLICANTS),
        ("reminder", APPLICANTS),
        ("o1", APPLICANTS),
        ("o2", APPLICANTS),
    }
)


def install(monkeypatch: pytest.MonkeyPatch) -> str:
    """The fellowship's process on ``EX``, for one test; its ID."""
    monkeypatch.setitem(stages._STAGES, EX, STAGES)  # pyright: ignore[reportPrivateUsage]  -- a test's sample
    monkeypatch.setitem(workflow._GATES, EX, GATES)  # pyright: ignore[reportPrivateUsage]  -- as above
    monkeypatch.setitem(workflow._SENDS, EX, SENDS)  # pyright: ignore[reportPrivateUsage]  -- as above
    monkeypatch.setitem(workflow._WRITTEN, EX, WRITTEN)  # pyright: ignore[reportPrivateUsage]  -- as above
    return EX
