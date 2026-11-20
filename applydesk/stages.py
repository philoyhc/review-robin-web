"""The exercise's stages, their gates and outcomes (rulings 13, 15), on
sample data.

An exercise's timeline is a sequence of stages; a stage holds the
form, or gates (which may run together), and may hold an outcome
after them. Process will set them up (a later segment); here they are fixed, and each
application's place at each gate and outcome is worked out from a seeded
score, so the Dossiers page reads as an exercise partway through.
Nothing is saved."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import cast

from applydesk import sample_data
from applydesk.sample_data import Application

#: Gate admittance, in the order a chip cycles (author, 2026-11-13): no
#: status yet, then whether the application is sent through the gate.
#: Outcomes keep their own values, with Pending, from Process.
NO_STATUS = "—"
ADMITTANCE: tuple[str, ...] = (NO_STATUS, "Entered", "Not entered")


@dataclass(frozen=True)
class Rule:
    """How a column is filled, set with it on Process (rulings 13, 14);
    the Dossiers page only applies it, and a hand can override.

    ``when`` holds conditions that must all hold, each (kind, key, op,
    value): ("status", "", "is", "Submitted"); ("last", "", "le", "1"),
    one of the applicant's last N submitted; ("out", outcome, "is",
    value); for an outcome only, ("res", "gate.result", "ge"/"lt", "4.0") on
    a gate's numeric result, or "is" a value of its list result (ruling 21), on a gate
    in its scope, ("ent", gate, "is", "Entered") and ("comb", "", "ge"/"lt",
    "4.2") on its combined result. A gate never reads another gate.

    Ruling 30 adds ("form", question, "is", value), the application's
    answer to a *List* question on Form, and ("top", "gate.result", "le",
    "20"), the best N by a result among the dossiers its branch reaches
    (ties at the cut all taken); and ``more``, further branches tried in
    order after the first: the first whose conditions all hold gives its
    value, none holding gives ``otherwise``."""

    when: tuple[tuple[str, str, str, str], ...]
    then: str
    otherwise: str
    more: tuple[tuple[tuple[tuple[str, str, str, str], ...], str], ...] = ()

    @property
    def branches(self) -> tuple[tuple[tuple[tuple[str, str, str, str], ...], str], ...]:
        """Every branch in order, (conditions, value), the first included."""
        return ((self.when, self.then), *self.more)


#: A response field's types, as Review Robin's instrument fields take
#: them (ruling 21): (key, label).
FIELD_TYPES: tuple[tuple[str, str], ...] = (
    ("integer", "Integer"),
    ("decimal", "Decimal"),
    ("list", "List"),
    ("string", "String"),
)

#: How a result is derived from its field's responses (ruling 21): (key,
#: label), and the ones each field type allows. Every gate runs in Review
#: Robin (ruling 28), so every result is derived; none is entered here.
DERIVATIONS: tuple[tuple[str, str], ...] = (
    ("mean", "Mean"),
    ("median", "Median"),
    ("min", "Lowest"),
    ("max", "Highest"),
    ("sum", "Sum"),
    ("share", "Share choosing"),
    ("mode", "Most common"),
    ("join", "All, joined"),
    # Any field's, so last: each type's menu reads as ALLOWED lists it.
    ("count", "Count of responses"),
)
ALLOWED: dict[str, tuple[str, ...]] = {
    "integer": ("mean", "median", "min", "max", "sum", "count"),
    "decimal": ("mean", "median", "min", "max", "sum", "count"),
    # Count, how many responded, is any field's (author, 2026-11-14).
    "list": ("share", "mode", "count"),
    "string": ("join", "count"),
}


@dataclass(frozen=True)
class Field:
    """The response field each evaluator fills in (ruling 21), in Review
    Robin's terms: a type and its bounds, or a list's options."""

    type: str = "integer"
    min: str = ""
    max: str = ""
    step: str = ""
    options: str = ""  # a list's, comma-separated


@dataclass(frozen=True)
class GateResult:
    """One of a gate's results (ruling 21): a name, the field evaluators
    answer, and how the answers become the result; the derivation sets
    its type. ``value`` is the option a share counts; ``at_least`` the
    responses it needs before it has a result."""

    key: str
    name: str
    field: Field
    derive: str
    value: str = ""
    at_least: int = 1
    # The response field it collates, by key (ruling 28). ``field`` is that
    # field's definition as the sample gives it; on Process the chosen
    # field's governs (``collated``). "" on a gate listing no fields reads
    # the field in its place (``fields_of``'s fallback).
    source: str = ""
    # Ruling 30: a mean or median leaving out the 0s, for a scale whose 0
    # means *no view* (*Don't know enough about this applicant*).
    ignore_zero: bool = False


@dataclass(frozen=True)
class ResponseField:
    """What each evaluator answers in Review Robin (ruling 28): a label,
    its type and bounds, whether it must be answered, and the help shown
    under it. ``key`` is what Review Robin reports the answers under."""

    key: str
    label: str
    field: Field
    required: bool = False
    help: str = ""


#: The kinds of evaluator source (ruling 27): the people a candidate named
#: in a *Select people* question on Form, or a panel's members.
SOURCE_KINDS: tuple[tuple[str, str], ...] = (("nominated", "Nominated"), ("panel", "Panel"))
#: How a gate's pairs are made (ruling 27).
MODES: tuple[tuple[str, str], ...] = (
    ("automatic", "Automatic"),
    ("suggested", "Suggested, then approved"),
    ("assigned", "Assigned by the operator"),
)


@dataclass(frozen=True)
class Source:
    """One of a gate's evaluator sources (ruling 27), ranked by its place
    in ``Gate.sources``: ``kind`` is ``nominated`` (``ref`` the Form's
    *Select people* question) or ``panel`` (``ref`` the panel's key); it
    gives ``min`` to ``max`` evaluators to each dossier."""

    kind: str
    ref: str
    min: int
    max: int
    # Ruling 62: a panel source giving each dossier its whole panel, its
    # min and max the panel's size as it stands (``sources_of`` reads them
    # so, the typed ones kept but unused).
    all_members: bool = False


@dataclass(frozen=True)
class Total:
    """A gate's overall evaluators per dossier (ruling 27's *Total*)."""

    min: int
    max: int


@dataclass(frozen=True)
class Gate:
    key: str
    number: int
    label: str
    via: str  # "RRW": a Review Robin session
    results: tuple[GateResult, ...] = ()  # up to three (ruling 21); the first is the headline
    rule: Rule | None = None
    panel: str = ""  # who evaluates: a sample_data.Panel key, "" for none yet (ruling 19)
    # Ruling 27 (segment AD1G): the ranked sources, the Total and the mode.
    # Empty sources read as ``panel`` alone (``sources_of``): the sample's
    # older gates name only a panel. What uses a panel reads ``sources_of``
    # (``gate_panels``), never ``panel`` (AD-49); AD2 stores sources alone.
    sources: tuple[Source, ...] = ()
    total: Total | None = None
    mode: str = "automatic"
    # Ruling 28: the gate card's own fields, and what evaluators answer.
    description: str = ""
    confidential: bool = False
    fields: tuple[ResponseField, ...] = ()
    # Its review window, inside its stage's dates (author, 2026-11-18);
    # None runs it on the stage's (``window``).
    when: StageDates | None = None
    # Its ``fields`` are its own, even none (a scratch exercise's, as
    # Process saved them): no field is made up per result in their place,
    # as for a sample gate listing none (``fields_of``; Codex on #4026).
    own_fields: bool = False

    @property
    def measure(self) -> str:
        """Its headline result's name ("" for none): Result 1, shown under
        its chip on Dossiers; rules name a result by key (ruling 21)."""
        return self.results[0].name if self.results else ""


@dataclass(frozen=True)
class Outcome:
    key: str
    number: int
    label: str
    values: tuple[str, ...]  # the decided values; Pending is always offered
    # When it is to be released, inside its stage and after the gates it
    # reads close (author, 2026-11-18); None is the stage's end (``window``).
    due_at: datetime | None
    released: str  # "" until released, else when and to whom
    # Its combined result: a weighted average of the gates in its scope
    # (author, 2026-11-13), set with the outcome on Process; the sample's.
    weights: tuple[tuple[str, float], ...] = ()
    rule: Rule | None = None

    @property
    def due(self) -> str:
        """Its due day as the pages print it, e.g. "4 Dec"; "" unset."""
        return short_day(self.due_at) if self.due_at else ""


def short_day(d: datetime | date) -> str:
    """A day as the pages print it, e.g. "1 Sep"."""
    return f"{d.day} {d.strftime('%b')}"


@dataclass(frozen=True)
class StageDates:
    """A stage's start and end (segment AD1K, author 2026-11-18): each a
    date and a time in the exercise's time zone, declared before the
    stage can be published, its end what completes it."""

    start: datetime
    end: datetime

    @property
    def valid(self) -> bool:
        """Its end after its start: a reversed range is no dates to the
        timeline and to a stage's status, and refused at publishing
        (Codex; the old parser refused it too)."""
        return self.end > self.start


def day(y: int, m: int, d: int, hh: int = 0, mm: int = 0) -> datetime:
    return datetime(y, m, d, hh, mm)


def span(start: datetime, end: datetime) -> StageDates:
    """A stage running from ``start`` to ``end``, a bare day's end taken
    as its last minute (23:59)."""
    if end.hour == 0 and end.minute == 0:
        end = end.replace(hour=23, minute=59)
    return StageDates(start, end)


#: A stage's declared status (ruling 35); Completed and Overdue follow
#: from its end and its items (``stage_status``).
STAGE_STATUSES = ("Draft", "Published")


@dataclass(frozen=True)
class Stage:
    """A step of the exercise's timeline (ruling 15): it holds the
    application form, or gates, and may hold an outcome; never the form
    and a gate together. Named by the operator, "Stage N" until then.
    ``when`` is its declared start and end, None until set; ``status``
    the operator's Draft or Published (ruling 35)."""

    number: int
    name: str  # "" until the operator names it
    when: StageDates | None
    columns: tuple[Gate | Outcome, ...] = ()
    form: bool = False  # holds the application form (ruling 15)
    status: str = "Draft"
    shown: bool = True  # on the applicant's timeline (ruling 46); False hides it there
    # The form's open and close, inside the stage's dates (author,
    # 2026-11-18); None is the stage's (``window``).
    form_when: StageDates | None = None

    @property
    def dates(self) -> str:
        """The dates as the pages print them, e.g. "1 Sep – 30 Sep"."""
        if self.when is None:
            return "Dates not set"
        return f"{short_day(self.when.start)} – {short_day(self.when.end)}"

    @property
    def label(self) -> str:
        return self.name or f"Stage {self.number}"


@dataclass(frozen=True)
class Cell:
    value: str  # an admittance, an outcome value, or "" for none ("—")
    note: str = ""  # under the chip: a gate's result, a reason, a date
    result: float | None = None  # a gate's finished result, which a rule reads
    by_hand: bool = False  # set by hand, overriding the column's rule
    # A gate's other finished results, by result key ("r2", "r3"); its
    # first is ``result`` (ruling 21). As text: a share's percent, a list's value.
    extra: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Row:
    application: Application
    cells: dict[str, Cell]


@dataclass(frozen=True)
class Plan:
    """What the Dossiers page draws for one exercise."""

    stages: tuple[Stage, ...]
    rows: tuple[Row, ...]

    @property
    def columns(self) -> tuple[Gate | Outcome, ...]:
        return tuple(c for st in self.stages for c in st.columns)

    @property
    def form_stage(self) -> Stage | None:
        """The one stage holding the form, if any: an exercise
        whose applications came from elsewhere has none (ruling 15)."""
        return next((st for st in self.stages if st.form), None)


_LIKERT = Field("integer", "1", "5", "1")

# The model exercise (ruling 30, segment AD1H): the RA recruitment. One
# application each, so a gate takes every submitted one. Stage 2 reviews
# every applicant twice over: the current RAs score them (0 is *don't
# know*, so the mean leaves it out) and the offices flag concerns; the
# shortlist sends a current RA to re-appointment and a new applicant to
# interview. Stage 3 interviews them, two residential staff each, and
# selects the best 20 beside the re-appointed.
_SUBMITTED = Rule((("status", "", "is", "Submitted"),), "Entered", "Not entered")
_SCORE = Field("integer", "0", "5", "1")
_CONCERNS = Field("list", options="No concerns, Minor concerns, Major concerns")
_COMMENT = Field("string", max="2000")
_G1 = Gate(
    "g1",
    1,
    "Peer review",
    "RRW",
    (
        GateResult("r1", "Mean score", _SCORE, "mean", source="score", ignore_zero=True),
        GateResult("r2", "Comments", _COMMENT, "join", source="comment"),
    ),
    _SUBMITTED,
    "current-ras",
    # Every current RA reviews every applicant but themselves: 30 for a
    # new applicant, 29 for a returning one.
    (Source("panel", "current-ras", 29, 30),),
    Total(29, 30),
    description="Every current RA scores every applicant, never themselves.",
    fields=(
        ResponseField("score", "Score", _SCORE, True, "0 = Don't know enough about this applicant"),
        ResponseField("comment", "Comment", _COMMENT),
    ),
    when=span(day(2026, 10, 1), day(2026, 10, 31)),
)
_G2 = Gate(
    "g2",
    2,
    "Office checks",
    "RRW",
    (
        GateResult("r1", "Major concerns", _CONCERNS, "share", "Major concerns", source="concerns"),
        GateResult("r2", "Minor concerns", _CONCERNS, "share", "Minor concerns", source="concerns"),
        GateResult("r3", "Comments", _COMMENT, "join", source="comment"),
    ),
    _SUBMITTED,
    "office",
    (Source("panel", "office", 5, 5),),
    Total(5, 5),
    description="Each office checks every applicant, mainly to mark out cases with concerns.",
    confidential=True,
    fields=(
        ResponseField("concerns", "Concerns", _CONCERNS, True),
        ResponseField("comment", "Comment", _COMMENT),
    ),
    when=span(day(2026, 10, 1), day(2026, 10, 31)),
)
_PASSED = (("res", "g1.r1", "ge", "3.5"), ("res", "g2.r1", "lt", "1"))
_O1 = Outcome(
    "o1",
    1,
    "Shortlisting",
    ("Re-appointment", "Interview", "Not shortlisted"),
    day(2026, 11, 6, 17),
    "6 Nov · to applicants",
    rule=Rule(
        (*_PASSED, ("form", "Currently an RA?", "is", "Yes")),
        "Re-appointment",
        "Not shortlisted",
        ((_PASSED, "Interview"),),
    ),
)
_G3 = Gate(
    "g3",
    3,
    "Staff interview",
    "RRW",
    (
        GateResult("r1", "Interview score", _LIKERT, "mean", at_least=2, source="score"),
        GateResult("r2", "Comments", _COMMENT, "join", source="comment"),
    ),
    Rule((("out", "o1", "is", "Interview"),), "Entered", "Not entered"),
    "residential-staff",
    (Source("panel", "residential-staff", 2, 2),),
    Total(2, 2),
    mode="suggested",
    description="Two residential staff interview each applicant, the load spread.",
    when=span(day(2026, 11, 9), day(2026, 12, 2)),
    fields=(
        ResponseField("score", "Score", _LIKERT, True, "1 weak, 5 outstanding"),
        ResponseField("comment", "Comment", _COMMENT, True),
    ),
)
_O2 = Outcome(
    "o2",
    2,
    "Selection",
    ("Selected", "Not selected"),
    day(2026, 12, 4, 17),
    "",
    (("g3.r1", 1.0),),
    Rule(
        (("out", "o1", "is", "Re-appointment"),),
        "Selected",
        "Not selected",
        (((("out", "o1", "is", "Interview"), ("top", "g3.r1", "le", "20")), "Selected"),),
    ),
)

# The small exercise's outcome, due at its stage's end: its gate has no
# window of its own, so it runs to that end too (Codex).
_K_O1 = Outcome(
    "o1",
    1,
    "Final results",
    ("Awarded", "Not awarded"),
    day(2026, 11, 30, 23, 59),
    "",
    (("g1.r1", 1.0),),
)


_STAGES: dict[str, tuple[Stage, ...]] = {
    # A draft still being set up (segment AD1F): its selection gate added
    # just in time, its panel not chosen yet.
    "c4xh2ndv6s": (
        Stage(1, "", None, form=True),
        Stage(
            2,
            "Selection",
            None,
            (
                Gate(
                    "g1",
                    1,
                    "Placement interview",
                    "RRW",
                    (GateResult("r1", "Score", Field("decimal", "0", "10", "0.5"), "mean"),),
                ),
            ),
        ),
    ),
    # The model exercise (author, 2026-11-13): its stages named.
    "wa9juxbc2t": (
        Stage(
            1,
            "Applications",
            span(day(2026, 9, 1), day(2026, 9, 30)),
            form=True,
            status="Published",
        ),
        Stage(
            2,
            "Review",
            span(day(2026, 10, 1), day(2026, 11, 6)),
            (_G1, _G2, _O1),
            status="Published",
        ),
        Stage(
            3,
            "Interviews",
            span(day(2026, 11, 9), day(2026, 12, 4)),
            (_G3, _O2),
            status="Published",
        ),
    ),
    # A smaller exercise, read blind by one panel; its second stage not
    # yet named.
    "k7mfr3pq8z": (
        Stage(
            1,
            "Call for applications",
            span(day(2026, 9, 1), day(2026, 10, 31)),
            form=True,
            status="Published",
        ),
        Stage(
            2,
            "",
            span(day(2026, 11, 1), day(2026, 11, 30)),
            (
                Gate(
                    "g1",
                    1,
                    "Panel review",
                    "RRW",
                    (GateResult("r1", "Score", _LIKERT, "mean"),),
                    panel="panel-a",
                ),
                # Two more readings, there to show a gate's later link
                # states (author, 2026-11-19; segment AD1M): the second
                # closed in Review Robin, its results not yet pulled;
                # the third unlinked there, so detached here.
                Gate(
                    "g2",
                    2,
                    "Second reading",
                    "RRW",
                    (GateResult("r1", "Score", _LIKERT, "mean"),),
                    panel="panel-a",
                ),
                Gate(
                    "g3",
                    3,
                    "Moderation",
                    "RRW",
                    (GateResult("r1", "Score", _LIKERT, "mean"),),
                    panel="panel-a",
                ),
                _K_O1,
            ),
            status="Published",
        ),
    ),
}


def _model_rows(apps: tuple[Application, ...]) -> tuple[Row, ...]:
    """The RA recruitment in the middle of Stage 3 (ruling 30): every
    submitted application reviewed and checked; 15 of the 20 current RAs
    to re-appointment and 40 new applicants to interview, one of them by
    hand; the interviews entered but not yet sent, so no scores and
    Selection pending, a re-appointed RA's as much as an interviewee's."""
    rng = random.Random("wa9juxbc2t ra rounds")
    ras = {m.email.casefold() for m in sample_data.CURRENT_RAS}
    submitted = [a for a in apps if a.state == "Submitted"]
    returning = [a for a in submitted if a.email.casefold() in ras]
    new = [a for a in submitted if a.email.casefold() not in ras]
    # Aisha returns and Kenji is interviewed: the pages' examples.
    back = {returning[0].public_id, *(a.public_id for a in rng.sample(returning[1:], 14))}
    ahead = {new[0].public_id, *(a.public_id for a in rng.sample(new[1:], 39))}
    # One the panel asked to interview, just under the bar (set by hand).
    by_hand = next(a.public_id for a in new if a.public_id not in ahead)
    ahead.add(by_hand)
    ahead.discard(next(a.public_id for a in reversed(new) if a.public_id in ahead))
    keys = ("g1", "g2", "o1", "g3", "o2")
    rows: list[Row] = []
    for a in apps:
        i = a.public_id
        cells: dict[str, Cell] = {k: Cell("") for k in keys}
        if a.state != "Submitted":
            # A draft has nothing; one withdrawn in September, before the
            # Review stage opened, was never entered.
            rows.append(Row(a, cells))
            continue
        r = random.Random(f"ra {i}")
        reviewers = 29 if a.email.casefold() in ras else 30
        passed = i in back or (i in ahead and i != by_hand)
        # Gate 1: each reviewer's score, 0 from those who do not know the
        # applicant, and their mean with the 0s left out (`averaged`).
        knew = reviewers - r.randint(0, 9)
        if passed:
            aim = round(r.uniform(3.6, 4.9), 1)
        elif i == by_hand:
            aim = 3.4
        else:
            aim = round(r.uniform(2.2, 4.6), 1)
        total = round(aim * knew)
        scores = (total // knew + 1,) * (total % knew) + (total // knew,) * (knew - total % knew)
        got, taken = averaged((*scores, *(0,) * (reviewers - knew)), "mean", True)
        mean = got if got is not None else 0.0
        # Gate 2: a major concern from any office keeps one off the list.
        major = 0 if passed or i == by_hand or mean < 3.5 else r.randint(1, 2)
        cells["g1"] = Cell("Entered", mean_note(got, taken, reviewers), got)
        minor = r.randint(0, 5 - major) if r.random() < 0.4 else 0
        concern = f"Major concerns from {major} of 5" if major else "No major concerns"
        cells["g2"] = Cell("Entered", concern, major * 20.0, extra=(("r2", str(minor * 20)),))
        if i in back:
            cells["o1"] = Cell("Re-appointment", "6 Nov")
        elif i == by_hand:
            cells["o1"] = Cell("Interview", "Set by hand: panel request", by_hand=True)
        elif i in ahead:
            cells["o1"] = Cell("Interview", "6 Nov")
        else:
            cells["o1"] = Cell("Not shortlisted", "6 Nov")
        if cells["o1"].value == "Interview":
            cells["g3"] = Cell("Entered", "Not yet sent")
        else:
            cells["g3"] = Cell("Not entered")
        if cells["o1"].value != "Not shortlisted":
            cells["o2"] = Cell("Pending", f"Due {_O2.due}")
        rows.append(Row(a, cells))
    return tuple(rows)


def _small_rows(apps: tuple[Application, ...]) -> tuple[Row, ...]:
    return tuple(
        Row(
            a,
            {
                "g1": Cell("Entered", "Score 4.1 · 2 of 2", 4.1),
                "g2": Cell("Entered", "Its session closed; results not pulled"),
                "g3": Cell("Entered", "Detached in Review Robin"),
                "o1": Cell("Pending", f"Due {_K_O1.due}"),
            },
        )
        for a in apps
    )


def _exercise_span(e: sample_data.Exercise) -> StageDates | None:
    """The one stage of an exercise with no stages laid out, from its
    opening and its applications' close ("1 Nov 2026", "31 Jan 2027,
    23:59"); None while either is "Not set"."""
    try:
        start = datetime.strptime(e.opens, "%d %b %Y")
        end = datetime.strptime(e.application_stage_ends, "%d %b %Y, %H:%M")
    except ValueError:
        return None
    return StageDates(start, end)


def _scratch_stages(exercise_id: str) -> tuple[Stage, ...] | None:
    """A scratch exercise's stages as Process last saved them (segment
    AD1N), else None."""
    from applydesk import scratch  # scratch builds on sample_data, as this does

    saved = scratch.page(exercise_id, "process")
    return cast(tuple[Stage, ...], saved[0]) if isinstance(saved, tuple) else None


def plan_of(exercise_id: str) -> Plan:
    """The stages and every application's cells for one exercise. An
    exercise not yet set up has one stage, holding the form, as a
    new exercise starts (ruling 15)."""
    apps = sample_data.applications_of(exercise_id)
    saved = _scratch_stages(exercise_id)
    if saved is not None:
        return Plan(saved, tuple(Row(a, {}) for a in apps))
    if exercise_id not in _STAGES:
        e = sample_data.exercise(exercise_id)
        when = _exercise_span(e) if e else None
        status = "Draft" if e is None or e.state == "Draft" else "Published"
        only = Stage(1, "", when, form=True, status=status)
        return Plan((only,), tuple(Row(a, {}) for a in apps))
    rows = _model_rows(apps) if exercise_id == "wa9juxbc2t" else _small_rows(apps)
    return Plan(_STAGES[exercise_id], rows)


def problems(stages: tuple[Stage, ...]) -> tuple[str, ...]:
    """What breaks ruling 15's shape: at most one stage holds the
    form, anywhere in the timeline (a gate may come first, its
    outcome deciding who may apply: author, 2026-11-13); no stage holds
    the form and a gate, or more than one outcome. (A stage left
    empty while it is set up is allowed.)"""
    out: list[str] = []
    holding = [st for st in stages if st.form]
    if len(holding) > 1:
        out.append("More than one stage holds the form.")
    for st in stages:
        if st.form and any(isinstance(c, Gate) for c in st.columns):
            out.append(f"{st.label} holds both the form and a gate.")
        if sum(isinstance(c, Outcome) for c in st.columns) > 1:
            out.append(f"{st.label} holds more than one outcome.")
    return tuple(out)


def going_on(outcome: Outcome) -> tuple[str, ...]:
    """An outcome's values that take an application on: every one but the
    last (ruling 30's Shortlisting: Re-appointment and Interview, not Not
    shortlisted); a single value is itself."""
    return outcome.values[:-1] if len(outcome.values) > 1 else outcome.values


def counts(plan: Plan, column: Gate | Outcome) -> str:
    """A column header's tally across every application, e.g.
    "86 entered · 2 to decide"; an outcome's, "24 shortlisted · 2 pending",
    each value that takes one on counted (`going_on`)."""
    values = [
        r.cells[column.key].value for r in plan.rows if r.cells.get(column.key, Cell("")).value
    ]
    if isinstance(column, Gate):
        order = [("Entered", "entered"), (NO_STATUS, "to decide")]
    else:
        order = [(v, v.lower()) for v in going_on(column)] + [("Pending", "pending")]
    parts = [f"{values.count(v)} {word}" for v, word in order if values.count(v)]
    return " · ".join(parts) or "none yet"


def last_submitted(rows: tuple[Row, ...]) -> frozenset[str]:
    """Application IDs shown under *Last applications*: per applicant (by
    email), the latest submitted, else the latest of any status (ruling
    13). Rows are in the order the applications came in."""
    latest: dict[str, str] = {}
    submitted: dict[str, str] = {}
    for r in rows:
        a = r.application
        latest[a.email.lower()] = a.public_id
        if a.state == "Submitted":
            submitted[a.email.lower()] = a.public_id
    return frozenset({**latest, **submitted}.values())


def scope(plan: Plan, outcome: Outcome) -> tuple[Gate, ...]:
    """The gates an outcome reads: those between it and the outcome
    before it, in column order (author, 2026-11-13)."""
    gates: list[Gate] = []
    for c in plan.columns:
        if c is outcome:
            return tuple(gates)
        gates = [] if isinstance(c, Outcome) else [*gates, c]
    return ()


def split_key(key: str) -> tuple[str, str]:
    """A rule's or a weight's key, "g1.r2", as (gate key, result key); a
    bare gate key reads its first result (ruling 21)."""
    gate, _, result = key.partition(".")
    return gate, result or "r1"


def comparable(r: GateResult) -> str:
    """What a rule may do with a result (ruling 21): "number" (compared,
    weighed), "list" (matched against an option) or "" (read only)."""
    if r.derive in ("mean", "median", "sum", "count", "share"):
        return "number"
    if r.field.type in ("integer", "decimal"):
        return "number"  # lowest or highest
    return "list" if r.field.type == "list" else ""


def result_of(plan: Plan, key: str) -> tuple[Gate | None, GateResult | None]:
    """The gate and result a key names, either None where gone."""
    gate_key, result_key = split_key(key)
    gate = next((c for c in plan.columns if isinstance(c, Gate) and c.key == gate_key), None)
    if gate is None:
        return None, None
    return gate, next((r for r in gate.results if r.key == result_key), None)


def local_value(d: datetime | None) -> str:
    """A date-time as a ``datetime-local`` input holds it, "" for none."""
    return d.strftime("%Y-%m-%dT%H:%M") if d else ""


def window_text(w: StageDates | None) -> str:
    """A window as a gate's send line says it, e.g. "1 Oct to 31 Oct"."""
    return f"{short_day(w.start)} to {short_day(w.end)}" if w and w.valid else ""


def window(st: Stage, item: Gate | Outcome | None) -> StageDates | None:
    """An item's dates, its own or else its stage's (author, 2026-11-18):
    the form's (``None``) open and close, a gate's review window, an
    outcome's from the stage's start to when it is due."""
    if st.when is None:
        return None
    if item is None:
        return st.form_when or st.when
    if isinstance(item, Gate):
        return item.when or st.when
    return StageDates(st.when.start, item.due_at or st.when.end)


def date_problems(plan: Plan, st: Stage) -> tuple[str, ...]:
    """Each item's dates against its stage's (author, 2026-11-18): inside
    them, the right way round, and an outcome due no sooner than the
    gates it reads close. Nothing while the stage's own are unset."""
    if st.when is None or not st.when.valid:
        return ()
    bounds = st.when
    named: list[tuple[str, Gate | Outcome | None]] = [("The form", None)] if st.form else []
    named += [
        (f"Gate {c.number} ({c.label or 'untitled'})", c)
        if isinstance(c, Gate)
        else (c.label or "The outcome", c)
        for c in st.columns
    ]
    out: list[str] = []
    for name, item in named:
        w = window(st, item)
        assert w is not None
        if not w.valid:
            out.append(f"{name} ends before it starts.")
        elif w.start < bounds.start or w.end > bounds.end:
            what = "is due" if isinstance(item, Outcome) else "runs"
            out.append(f"{name} {what} outside the dates of {st.label}.")
        if isinstance(item, Outcome):
            # A gate it reads may sit in an earlier stage (Codex).
            for g in scope(plan, item):
                home = next((s for s in plan.stages if g in s.columns), None)
                gw = window(home, g) if home else None
                if gw is not None and w.end < gw.end:
                    out.append(f"{name} is due before {g.label or 'its gate'} closes.")
    return tuple(out)


def _is_number(value: str) -> bool:
    """As the page's ``!isNaN(Number(v))`` on a non-blank value."""
    try:
        float(value.strip())
    except ValueError:
        return False
    return bool(value.strip())


def _compare_problems(
    plan: Plan, kind: str, key: str, op: str, value: str, gate: Gate, result: GateResult
) -> list[str]:
    """How a rule compares a result, as Process's Outline checks it
    (Codex): a list matched against one of its options, a number compared
    with a number, a ranking by a number."""
    rc = collated(result, source_field(gate, result))
    k, label = comparable(rc), result_label(plan, key)
    if kind == "top":
        return [] if k == "number" else [f"ranks by {label}, which is not a number"]
    if not k:
        return [f"reads {label}, which a rule cannot compare"]
    if k == "list" and op != "is":
        return [f"compares {label}, a list, as a number"]
    if k == "number" and op == "is":
        return [f"matches {label}, a number, as a list"]
    options = [o.strip() for o in rc.field.options.split(",") if o.strip()]
    if k == "list" and value not in options:
        return [f"reads \u201c{value}\u201d, not among the options of {label}"]
    if k == "number" and not _is_number(value):
        return [f"compares with \u201c{value}\u201d, not a number"]
    return []


def rule_problems(
    plan: Plan, column: Gate | Outcome, forms: dict[str, list[str]]
) -> tuple[str, ...]:
    """What a column's rule reads that no longer holds, as Process's
    Outline says it (segment AD1K, Codex): an outcome gone, or not before
    it; a gate or result gone, or outside an outcome's scope; a value not
    among an outcome's values or a list result's options; a form answer
    not a List question's option (``forms``, the form's List questions);
    a count not a whole number. The page's script says the same in place;
    publishing reads this."""
    rule = column.rule
    if rule is None:
        return ()
    found: list[str] = []
    cols = {c.key: c for c in plan.columns}
    order = list(plan.columns)
    earlier = order[: order.index(column)] if column in order else []
    in_scope = scope(plan, column) if isinstance(column, Outcome) else ()
    for when, _ in rule.branches:
        for kind, key, _op, value in when:
            if kind == "out":
                out = cols.get(key)
                if not isinstance(out, Outcome):
                    found.append("reads an outcome no longer in the process")
                elif out not in earlier:
                    found.append(f"reads {out.label}, which comes later")
                elif value and value not in out.values:
                    found.append(f"reads \u201c{value}\u201d, not among the values of {out.label}")
            elif kind in ("res", "top", "ent") and isinstance(column, Outcome):
                gate, result = result_of(plan, key) if kind != "ent" else (cols.get(key), None)
                if not isinstance(gate, Gate):
                    found.append("reads a gate no longer in the process")
                elif gate not in in_scope:
                    found.append(f"reads {gate.label}, outside the gates before it")
                elif kind != "ent" and result is None:
                    found.append(f"reads a result no longer on {gate.label}")
                elif result is not None:
                    found += _compare_problems(plan, kind, key, _op, value, gate, result)
            if kind == "comb" and not _is_number(value):
                found.append(f"compares with \u201c{value}\u201d, not a number")
            if kind in ("last", "top") and not re.fullmatch(r"[1-9][0-9]*", value):
                found.append(f"takes \u201c{value}\u201d, not a whole number")
            if kind == "form":
                if key not in forms:
                    found.append(f"reads \u201c{key}\u201d, not a List question on the form")
                elif value not in forms[key]:
                    found.append(f"reads \u201c{value}\u201d, not among the options of {key}")
    if isinstance(column, Outcome):
        allowed = set(column.values) | {"Pending"}
        for value in (*(then for _, then in rule.branches), rule.otherwise):
            if value and value not in allowed:
                found.append(f"decides \u201c{value}\u201d, not among its values")
    return tuple(dict.fromkeys(found))


def result_label(plan: Plan, key: str) -> str:
    """A key as a rule or a weight names it: "Rating at Peer Review"; as
    the Process page's script writes it."""
    gate, result = result_of(plan, key)
    where = (gate.label or "Untitled gate") if gate else "(removed)"
    what = (result.name or "Untitled result") if result else "Result"
    return f"{what} at {where}"


def _result_value(cell: Cell, result_key: str) -> float | None:
    if result_key == "r1":
        return cell.result
    raw = dict(cell.extra).get(result_key)
    try:
        return float(raw) if raw is not None else None
    except ValueError:
        return None


def combined(row: Row, outcome: Outcome) -> float | None:
    """An outcome's combined result for one application: the weighted
    average of its gates' finished results. A gate it was not entered
    into is left out and the other weights rescaled; one it entered with
    no finished result, or not yet decided, leaves it unknown (None)."""
    total = weight = 0.0
    for key, w in outcome.weights:
        gate_key, result_key = split_key(key)
        cell = row.cells.get(gate_key)
        if cell is None or not cell.value or cell.value == "Not entered":
            continue
        if not w:
            continue  # a result weighed at 0% plays no part
        value = _result_value(cell, result_key)
        if cell.value == NO_STATUS or value is None:
            return None
        total += w * value
        weight += w
    return round(total / weight, 2) if weight else None


def submitted_rank(rows: tuple[Row, ...]) -> dict[str, int]:
    """Each submitted application's place among its applicant's submitted
    ones, newest first (1 = last submitted); for "the last N submitted by
    each applicant" in a gate's rule (author, 2026-11-13)."""
    by_applicant: dict[str, list[tuple[date, int, str]]] = {}
    for n, r in enumerate(rows):
        a = r.application
        if a.state == "Submitted":
            when = datetime.strptime(a.submitted, "%d %b %Y").date()
            by_applicant.setdefault(a.email.lower(), []).append((when, n, a.public_id))
    return {
        app_id: rank
        for subs in by_applicant.values()
        for rank, (_, _, app_id) in enumerate(sorted(subs, reverse=True), start=1)
    }


_SAID = {
    "status": "Status",
    "last": "the applicant's last submitted",
    "lastN": "among the applicant's last {v} submitted",
    "comb": "Combined",
}


def rule_text(plan: Plan, column: Gate | Outcome) -> str:
    """A column's rule in a line, for its header, e.g. "Combined ≥ 4.2 →
    Shortlisted, else Not shortlisted"; "" for a column decided by hand."""
    if column.rule is None:
        return ""
    cols = {c.key: c for c in plan.columns}

    # As the Process page's script words them: a column gone reads
    # "(removed)", one unnamed "Untitled …", a result gone "Result".
    def name(key: str) -> str:
        c = cols.get(key)
        if c is None:
            return "(removed)"
        return c.label or ("Untitled gate" if isinstance(c, Gate) else "Untitled outcome")

    def said(kind: str, key: str, op: str, value: str) -> str:
        sign = {"ge": "≥", "lt": "<"}.get(op, "is")
        if kind == "last":
            return _SAID["last"] if value == "1" else _SAID["lastN"].format(v=value)
        if kind == "res":
            return f"{result_label(plan, key)} {sign} {value}"
        if kind == "ent":
            return f"Entry at {name(key)} is {value}"
        if kind == "out":
            return f"{name(key)} is {value or '—'}"
        if kind == "form":
            return f"{key or 'Untitled question'} is {value or '—'}"
        if kind == "top":
            return f"the best {value} by {result_label(plan, key)}"
        return f"{_SAID[kind]} {sign} {value}"

    lines = [
        f"{' and '.join(said(*c) for c in when)} → {then or '—'}"
        for when, then in column.rule.branches
    ]
    return f"{'; else if '.join(lines)}, else {column.rule.otherwise or '—'}"


def rule_json(column: Gate | Outcome) -> dict[str, object] | None:
    """The column's rule as the page's script reads it."""
    if column.rule is None:
        return None
    out: dict[str, object] = {
        "when": [list(c) for c in column.rule.when],
        "then": column.rule.then,
        "otherwise": column.rule.otherwise,
    }
    if column.rule.more:  # ruling 30's further branches, in order
        out["more"] = [
            {"when": [list(c) for c in when], "then": then} for when, then in column.rule.more
        ]
    return out


def panel_uses(exercise_id: str) -> dict[str, tuple[str, ...]]:
    """What uses each of the exercise's panels (ruling 19), by panel key,
    in page order: the form's Select people questions, then each gate in
    timeline order, e.g. ("Form: Preferred evaluator", "Gate 1: Peer
    Review"). A panel nothing uses has no entry."""
    uses: dict[str, list[str]] = {}
    for c in sample_data.form_cards(exercise_id):
        if c.kind == "field" and c.type == "people" and c.pool != "institution":
            uses.setdefault(c.pool, []).append(f"Form: {c.label or 'Untitled question'}")
    for column in plan_of(exercise_id).columns:
        if isinstance(column, Gate):
            for key in gate_panels(exercise_id, column):
                uses.setdefault(key, []).append(f"Gate {column.number}: {column.label}")
    return {k: tuple(v) for k, v in uses.items()}


def gate_panels(exercise_id: str, gate: Gate) -> tuple[str, ...]:
    """The panels a gate draws evaluators from, in rank order: every panel
    source, not just the first (AD-49)."""
    srcs, _ = sources_of(exercise_id, gate)
    return tuple(dict.fromkeys(s.ref for s in srcs if s.kind == "panel"))


def _bounds(lo: str, hi: str) -> str:
    """ "1 to 5", "up to 5", "at least 1", or ""."""
    if lo and hi:
        return f"{lo} to {hi}"
    if hi:
        return f"up to {hi}"
    if lo:
        return f"at least {lo}"
    return ""


def field_text(f: Field) -> str:
    """A response field as Review Robin's instrument will ask it, e.g.
    "Integer 1 to 5, step 1"; the page's script writes the same."""
    if f.type == "list":
        options = ", ".join(o.strip() for o in f.options.split(",") if o.strip())
        return f"List: {options}" if options else "List, no options yet"
    if f.type == "string":
        return f"String, up to {f.max} characters" if f.max else "String"
    name = "Integer" if f.type == "integer" else "Decimal"
    parts = [p for p in (_bounds(f.min, f.max), f"step {f.step}" if f.step else "") if p]
    return f"{name} {', '.join(parts)}" if parts else name


def result_type(r: GateResult) -> str:
    """The result's type, which its derivation sets (ruling 21)."""
    f = r.field
    if r.derive in ("mean", "median"):
        span = _bounds(f.min, f.max)
        return f"Decimal {span}" if span else "Decimal"
    if r.derive in ("min", "max"):
        return field_text(f)
    if r.derive == "sum":
        span = _bounds(f.min, f.max)
        name = "Integer" if f.type == "integer" else "Decimal"
        return f"{name}, n × {span}" if span else name
    if r.derive == "count":
        return "Integer, from 0"
    if r.derive == "share":
        return "Decimal 0 to 100 (%)"
    if r.derive == "mode":
        return field_text(f)
    return "String, for reading"


#: The derivations that may leave out the 0s (ruling 30).
ZERO_DERIVATIONS: tuple[str, ...] = ("mean", "median")


def averaged(values: tuple[float, ...], derive: str, ignore_zero: bool) -> tuple[float | None, int]:
    """A mean or median of the responses and how many it took: with
    ``ignore_zero``, the 0s (*no view*) left out, so all 0s give no
    result (ruling 30)."""
    taken = sorted(v for v in values if not (ignore_zero and v == 0))
    if not taken:
        return None, 0
    if derive == "median":
        mid = len(taken) // 2
        value = taken[mid] if len(taken) % 2 else (taken[mid - 1] + taken[mid]) / 2
    else:
        value = sum(taken) / len(taken)
    return round(value, 2), len(taken)


def mean_note(value: float | None, taken: int, of: int) -> str:
    """A mean's note under its chip: "3.7 from 27 of 29", the scores it
    took of those asked; "No view from 30" when none scored (ruling 30)."""
    if value is None:
        return f"No view from {of}"
    return f"{value:.1f} from {taken} of {of}"


def derivation_text(r: GateResult) -> str:
    """How the responses become the result, e.g. "Mean of 2 or more"."""
    label = dict(DERIVATIONS).get(r.derive, r.derive)
    if r.ignore_zero and r.derive in ZERO_DERIVATIONS:
        label = f"{label}, ignoring 0"
    if r.derive == "share":
        # As the page's menu: the first option when none is chosen.
        first = next((o.strip() for o in r.field.options.split(",") if o.strip()), "")
        label = f"Share choosing {r.value or first or '(no option)'}"
    return f"{label}, from {r.at_least} or more" if r.at_least > 1 else label


def result_summary(r: GateResult) -> str:
    """A result's row, collapsed: what is asked, how it is derived, and
    what it gives; the page's script writes the same."""
    return f"{field_text(r.field)} · {derivation_text(r)} → {result_type(r)}"


def weight_rows(plan: Plan, outcome: Outcome) -> tuple[tuple[str, int], ...]:
    """An outcome's weights as Process draws them (ruling 21): every
    numeric result of the gates in its scope, in order, each its percent,
    0 for one it does not weigh."""
    set_ = {".".join(split_key(k)): w for k, w in outcome.weights}  # a bare key reads r1
    return tuple(
        (f"{g.key}.{r.key}", round(set_.get(f"{g.key}.{r.key}", 0.0) * 100))
        for g in scope(plan, outcome)
        for r in g.results
        if comparable(r) == "number"
    )


# ── A gate's evaluators (ruling 27, segment AD1G) ─────────────────────────


def sources_of(exercise_id: str, gate: Gate) -> tuple[tuple[Source, ...], Total]:
    """The gate's ranked sources and Total. A sample gate that names only a
    panel reads as that panel, min = max = its size, so nothing it shows
    changes until edited (AD1G judgment call)."""
    if gate.sources:
        sources = tuple(_whole_panel(exercise_id, src) for src in gate.sources)
        lo, hi = total_bounds(sources)
        # A source taking *All* gives the gate its whole panel, whatever
        # its size (ruling 62, amended 2026-11-20): the Total is then the
        # sources' bounds, so a member joining or leaving changes nothing
        # the operator must retype and nothing the Outline flags.
        if any(s.all_members and s.kind == "panel" for s in gate.sources):
            return sources, Total(lo, hi)
        return sources, gate.total or Total(lo, hi)
    if not gate.panel:
        # A saved gate with no source yet keeps the Total it was given
        # (Codex on #4026); a sample one has none.
        return (), gate.total or Total(0, 0)
    pool = sample_data.panel_pools(exercise_id).get(gate.panel)
    size = len(pool["members"]) if pool else 0
    return (Source("panel", gate.panel, size, size, all_members=True),), Total(size, size)


def _whole_panel(exercise_id: str, source: Source) -> Source:
    """A source as it gives evaluators: one taking *All* of its panel
    (ruling 62) reads min = max = the panel's size now, so the bounds, the
    filling, the summaries and the handoff all follow the panel."""
    if not (source.all_members and source.kind == "panel"):
        return source
    pool = sample_data.panel_pools(exercise_id).get(source.ref)
    size = len(pool["members"]) if pool else 0
    return replace(source, min=size, max=size)


def total_bounds(sources: tuple[Source, ...]) -> tuple[int, int]:
    """What the Total may be: no lower than the sources' mins together, no
    higher than their maxes (ruling 27)."""
    return sum(s.min for s in sources), sum(s.max for s in sources)


def total_problem(sources: tuple[Source, ...], total: Total) -> str:
    """Why the gate's Total cannot hold, or "" (shown on the Outline, not
    silently clamped)."""
    if not sources:
        return "no evaluators"
    if any(s.all_members and s.kind == "panel" for s in sources):
        return ""  # the Total is the sources' own (ruling 62): a source's problem says it
    lo, hi = total_bounds(sources)
    if total.min > total.max:
        return "the Total's min is above its max"
    if total.min < lo:
        return f"the Total's min is below the sources' mins together ({lo})"
    if total.max > hi:
        return f"the Total's max is above the sources' maxes together ({hi})"
    return ""


def nominee_questions(exercise_id: str) -> tuple[str, ...]:
    """The form's *Select people* questions by label, as a nominated
    source picks one (ruling 27): offered only when the form has one."""
    return tuple(
        c.label or "Untitled question"
        for c in sample_data.form_cards(exercise_id)
        if c.kind == "field" and c.type == "people"
    )


def _n(lo: int, hi: int) -> str:
    return str(lo) if lo == hi else f"{lo}–{hi}"


def sources_summary(
    sources: tuple[Source, ...], total: Total, pools: dict[str, sample_data.Pool]
) -> str:
    """A gate head's chip (AD1G): each source by kind or panel with its
    min to max, then the Total, e.g. "Nominated 0–1 · Panel A 1–2 ·
    Total 2"; "No evaluators" for none. The page script reads the same."""
    if not sources:
        return "No evaluators"
    parts = [
        (
            "Nominated"
            if s.kind == "nominated"
            else pools[s.ref]["name"]
            if s.ref in pools
            else "No panel"
        )
        + " "
        + _n(s.min, s.max)
        for s in sources
    ]
    return " · ".join([*parts, f"Total {_n(total.min, total.max)}"])


def sources_warn(
    sources: tuple[Source, ...], total: Total, pools: dict[str, sample_data.Pool]
) -> bool:
    """Whether a gate head's chip warns, as the page script's
    ``sourceProblems``: no sources, a panel not chosen, a question not
    chosen, a min above its max, or a Total outside its bounds."""
    return bool(total_problem(sources, total) or source_problems(sources, pools))


def source_problems(
    sources: tuple[Source, ...], pools: dict[str, sample_data.Pool]
) -> tuple[str, ...]:
    """Each source that cannot give evaluators, in words, as the page
    script's ``sourceProblems``: a panel not chosen or gone, a question
    not chosen, a min above its max. Publishing reads it too (Codex)."""
    out: list[str] = []
    for n, s in enumerate(sources, 1):
        if s.kind == "panel" and s.ref not in pools:
            out.append(f"source {n} has no panel" if not s.ref else f"source {n}'s panel is gone")
        elif s.kind == "nominated" and not s.ref:
            out.append(f"source {n} has no question chosen")
        if s.min > s.max:
            out.append(f"source {n}'s min is above its max")
    return tuple(out)


@dataclass(frozen=True)
class Filling:
    """A dossier's evaluators as ``stages.fill`` gives them: each with the
    rank of the source it came from; ``short`` is how many the Total's
    min still lacks, ``unmet`` the sources given fewer than their min."""

    evaluators: tuple[tuple[str, int], ...]
    short: int = 0
    unmet: tuple[int, ...] = ()

    @property
    def filled(self) -> bool:
        return self.short == 0 and not self.unmet


def fill(
    sources: tuple[Source, ...],
    total: Total,
    offers: tuple[tuple[str, ...], ...],
    candidate: str = "",
    load: dict[str, int] | None = None,
) -> Filling:
    """One dossier's evaluators (ruling 27). ``offers[i]`` is who source
    ``i`` can give this dossier: a nominated source the people the
    candidate named, in their order; a panel its members. Sources are
    taken in rank order: the first gives as many as it has, up to its max;
    each lower one gives what the Total's min still needs, never fewer
    than its own min; nothing passes the Total's max, and room is kept for
    the lower sources' mins. A gate with an *All* source (ruling 62) has
    every source give as many as it has, up to its max. Evaluators are distinct by email (any case),
    a person in two sources counted for the higher-ranked, and the
    candidate never their own. A panel gives its least-loaded members
    first; ``load`` counts each evaluator's dossiers across calls, from
    every source, so the work spreads evenly."""
    chosen: list[tuple[str, int]] = []
    seen = {candidate.casefold()} if candidate else set[str]()
    unmet: list[int] = []
    # A gate taking *All* of a panel (ruling 62, amended 2026-11-20) has
    # no Total of the operator's: every source gives as many as it has, up
    # to its max, and an All source is met by every member it can give
    # (the candidate on their own panel is not a shortfall).
    whole = any(s.all_members and s.kind == "panel" for s in sources)
    needed = 0
    for rank, (source, people) in enumerate(zip(sources, offers, strict=True)):
        available: list[str] = []
        for person in people:
            if person.casefold() not in seen and person.casefold() not in {
                p.casefold() for p in available
            }:
                available.append(person)
        if source.kind == "panel" and load is not None:
            available.sort(key=lambda p: load.get(p.casefold(), 0))
        reserved = sum(s.min for s in sources[rank + 1 :])
        room = max(0, total.max - len(chosen) - reserved)
        want = source.max if rank == 0 or whole else max(source.min, total.min - len(chosen))
        given = available[: max(0, min(len(available), source.max, want, room))]
        for person in given:
            seen.add(person.casefold())
            chosen.append((person, rank))
            if load is not None:  # every dossier counts, a nominated one too (Codex)
                load[person.casefold()] = load.get(person.casefold(), 0) + 1
        floor = min(source.min, len(available)) if source.all_members else source.min
        needed += floor
        if len(given) < floor:
            unmet.append(rank)
    short = max(0, (needed if whole else total.min) - len(chosen))
    return Filling(tuple(chosen), short, tuple(unmet))


@dataclass(frozen=True)
class Assignment:
    """One dossier's row on Evaluations (AD1G): its application, its
    evaluators as (name, email, the source's label) and how ``fill``
    left it."""

    application: Application
    evaluators: tuple[tuple[str, str, str], ...]
    short: int
    unmet: tuple[int, ...]


def source_label(source: Source, pools: dict[str, sample_data.Pool]) -> str:
    """A pill's mark: *Nominated*, or the panel's name."""
    if source.kind == "nominated":
        return "Nominated"
    return pools[source.ref]["name"] if source.ref in pools else "No panel"


def assignments(
    exercise_id: str, gate: Gate
) -> tuple[tuple[Assignment, ...], tuple[tuple[str, tuple[tuple[str, int], ...]], ...]]:
    """The gate's dossiers and their evaluators (ruling 27), filled as
    Automatic and the suggestion fill them: every application entered at
    the gate, in Dossiers' order, through ``fill`` with one load across
    them; then, per panel source, each member's count of dossiers. An
    *Assigned by the operator* gate starts empty. Sample data: nothing is
    saved until AD2."""
    sources, total = sources_of(exercise_id, gate)
    panels = sample_data.panel_pools(exercise_id)
    names = {
        e.casefold(): n for n, e in sample_data.people_pools(exercise_id)["institution"]["members"]
    }
    for pool in panels.values():
        names.update({e.casefold(): n for n, e in pool["members"]})
    load: dict[str, int] = {}
    rows: list[Assignment] = []
    for row in plan_of(exercise_id).rows:
        if row.cells.get(gate.key, Cell("")).value != "Entered":
            continue
        app = row.application
        if gate.mode == "assigned" or not sources:
            rows.append(Assignment(app, (), total.min, ()))
            continue
        offers = tuple(
            sample_data.nominees(exercise_id, app, s.ref)
            if s.kind == "nominated"
            else tuple(e for _, e in panels.get(s.ref, {"name": "", "members": []})["members"])
            for s in sources
        )
        got = fill(sources, total, offers, candidate=app.email, load=load)
        pills = tuple(
            (names.get(e.casefold(), e), e, source_label(sources[rank], panels))
            for e, rank in got.evaluators
        )
        rows.append(Assignment(app, pills, got.short, got.unmet))
    spread = tuple(
        (
            panels[s.ref]["name"],
            tuple((n, load.get(e.casefold(), 0)) for n, e in panels[s.ref]["members"]),
        )
        for s in sources
        if s.kind == "panel" and s.ref in panels
    )
    return tuple(rows), spread


def released_results(exercise_id: str, public_id: str) -> tuple[tuple[str, str, str], ...]:
    """An application's results released to applicants (ruling 41, AD-28):
    (outcome, its value, when), in timeline order; none until released,
    and none undecided. Read from Dossiers' cells; AD7 stores them."""
    plan = plan_of(exercise_id)
    row = next((r for r in plan.rows if r.application.public_id == public_id), None)
    out: list[tuple[str, str, str]] = []
    for c in plan.columns:
        if not isinstance(c, Outcome) or not c.released:
            continue
        when, _, to = c.released.partition(" · ")
        cell = row.cells.get(c.key) if row else None
        if (not to or "applicants" in to.lower()) and cell and cell.value in c.values:
            out.append((c.label, cell.value, when))
    return tuple(out)


def gate_numbered(plan: Plan, number: int) -> Gate | None:
    """The plan's gate numbered ``number`` (its page under Evaluations,
    ``…/evaluations/gate_<n>``, segment AD1H), None if none is."""
    return next((c for c in plan.columns if isinstance(c, Gate) and c.number == number), None)


@dataclass(frozen=True)
class Pair:
    """One row on a gate's page (segment AD1H, author 2026-11-17): a
    dossier and one evaluator, by name, email and the source's label; a
    dossier with none yet is one row with an empty evaluator. ``of`` is
    the dossier's whole assignment, whose state the row shows."""

    of: Assignment
    name: str = ""
    email: str = ""
    source: str = ""


def pairs_of(rows: tuple[Assignment, ...]) -> tuple[Pair, ...]:
    """Every pair of the gate, a dossier's in the order ``fill`` gave."""
    return tuple(
        p for a in rows for p in (tuple(Pair(a, n, e, s) for n, e, s in a.evaluators) or (Pair(a),))
    )


def matching(pairs: tuple[Pair, ...], query: str, blind: bool = False) -> tuple[Pair, ...]:
    """The pairs whose candidate (name, email, application or dossier ID)
    or evaluator (name or email) holds ``query``, any case; all for an
    empty one. In a blind exercise a candidate is found by the dossier ID
    the page shows, never by who they are (Codex on #3958)."""
    q = query.strip().casefold()
    if not q:
        return pairs

    def holds(p: Pair) -> bool:
        app = p.of.application
        who = (
            (app.dossier_id,)
            if blind
            else (app.applicant, app.email, app.public_id, app.dossier_id)
        )
        said = (*who, p.name, p.email)
        return any(q in text.casefold() for text in said)

    return tuple(p for p in pairs if holds(p))


def sorted_pairs(
    pairs: tuple[Pair, ...],
    spec: tuple[tuple[str, bool], ...],
    gate: Gate,
    sent: bool,
    blind: bool = False,
) -> tuple[Pair, ...]:
    """The pairs in a gate table's sort cascade (segment AD1H): by
    candidate (the dossier ID in a blind exercise), evaluator, source or
    state, any case, each up or down; the fill's order breaks ties. As
    Review Robin's tables, an empty cell sorts last either way and a
    number as a number (*Short by 2* before *Short by 10*)."""

    def text(p: Pair, key: str) -> str:
        app = p.of.application
        if key == "candidate":
            return app.dossier_id if blind else app.applicant
        if key == "evaluator":
            return p.name
        if key == "source":
            return p.source
        return assignment_state(gate, sent, p.of)

    def value(p: Pair, key: str, desc: bool) -> tuple[bool, str]:
        t = text(p, key).casefold()
        natural = re.sub(r"\d+", lambda m: m.group().zfill(12), t)
        return (not t) != desc, natural

    out = list(pairs)
    for key, desc in reversed(spec):  # stable: the last key first
        out.sort(key=lambda p: value(p, key, desc), reverse=desc)
    return tuple(out)


def page_data(
    exercise_id: str,
    gate: Gate,
    rows: tuple[Assignment, ...],
    blind: bool = False,
    query: str = "",
    first: bool = True,
) -> dict[str, object]:
    """What a gate page's script needs to work its mode's operations in
    the browser (AD1G rung 6b): the Total, every dossier and pair (not
    only the page's), and each panel source's members, so a change shows
    in the states, the counts and the load line whatever page is open. A
    blind exercise or a confidential gate sends no applicant's name or
    email; each dossier's fourth field is the one evaluator + Pair must
    leave out, the applicant when they sit on its panels, else "" (author,
    2026-11-18), so no one is paired with themself.
    ``query`` and ``first`` are the page's search and whether it is the
    first page, where pairs added in the tab show. Emails are lowercased
    as the rows' ``data-ev-pair``. Nothing is saved until AD2."""
    sources, total = sources_of(exercise_id, gate)
    panels = sample_data.panel_pools(exercise_id)
    on_panels = {
        e.lower()
        for s in sources
        if s.kind == "panel" and s.ref in panels
        for _, e in panels[s.ref]["members"]
    }
    return {
        "key": f"{exercise_id}:{gate.key}",
        "mode": gate.mode,
        "min": total.min,
        "max": total.max,
        "sources": [[source_label(s, panels), s.min, s.max] for s in sources],
        "q": query.strip(),
        "first": first,
        "blind": blind,
        "dossiers": [
            [
                a.application.public_id,
                a.application.dossier_id if blind else a.application.applicant,
                "" if blind else a.application.email.lower(),
                a.application.email.lower() if a.application.email.lower() in on_panels else "",
            ]
            for a in rows
        ],
        "pairs": [
            [a.application.public_id, e.lower(), n, src] for a in rows for n, e, src in a.evaluators
        ],
        "panels": [
            [panels[s.ref]["name"], [[n, e.lower()] for n, e in panels[s.ref]["members"]]]
            for s in sources
            if s.kind == "panel" and s.ref in panels
        ],
    }


def assignment_state(gate: Gate, sent: bool, a: Assignment) -> str:
    """A row's state on Evaluations, by the gate's mode: *Short by n*
    when the Total's min is not met; else *Filled* (Automatic),
    *Suggested* or, once sent, *Approved* (Suggested), and *Not assigned*
    or *Assigned* (by the operator)."""
    if gate.mode == "assigned" and not a.evaluators:
        return "Not assigned"
    if a.short or a.unmet:
        return f"Short by {a.short}" if a.short else "Short"
    if gate.mode == "suggested":
        return "Approved" if sent else "Suggested"
    return "Assigned" if gate.mode == "assigned" else "Filled"


def assignment_counts(rows: tuple[Assignment, ...]) -> str:
    """A gate card's head: "92 dossiers · 90 filled · 2 short"."""
    short = sum(1 for a in rows if a.short or a.unmet or not a.evaluators)
    parts = [
        f"{len(rows)} {'dossier' if len(rows) == 1 else 'dossiers'}",
        f"{len(rows) - short} filled",
    ]
    if short:
        parts.append(f"{short} short")
    return " · ".join(parts)


#: A gate's kinds (ruling 28): only a Review Robin run for now, the menu
#: kept for other kinds later.
GATE_TYPES: tuple[tuple[str, str], ...] = (("RRW", "Review Robin session"),)


def fields_of(gate: Gate) -> tuple[ResponseField, ...]:
    """A gate's response fields (ruling 28). A sample gate that lists none
    reads one per result, from the field the result carries, so nothing
    it shows changes until edited (as ``sources_of``)."""
    if gate.fields or gate.own_fields:
        return gate.fields
    return tuple(ResponseField(f"f{i}", r.name, r.field) for i, r in enumerate(gate.results, 1))


def source_field(gate: Gate, result: GateResult) -> ResponseField | None:
    """The response field a result collates: by its ``source`` key, else
    the field in its place (``fields_of``'s fallback)."""
    fields = fields_of(gate)
    if result.source:
        return next((f for f in fields if f.key == result.source), None)
    if gate.fields or gate.own_fields:
        return None  # a gate listing its fields names them; none is assumed
    at = gate.results.index(result) if result in gate.results else -1
    return fields[at] if 0 <= at < len(fields) else None


def collated(result: GateResult, source: ResponseField | None) -> GateResult:
    """The result as its chosen field makes it (ruling 28): its derivation
    and type read that field's definition, as the page's script does."""
    return replace(result, field=source.field) if source else result


def field_summary(f: ResponseField) -> str:
    """A response field's row: "Integer 1 to 5, step 1 · Required · Help:
    1 weak, 5 outstanding"."""
    parts = [field_text(f.field), "Required" if f.required else "Optional"]
    if f.help:
        parts.append(f"Help: {f.help}")
    return " · ".join(parts)


def gate_summary(plan: Plan, gate: Gate) -> str:
    """The shut Gate card's line (ruling 28): its type, whether it is
    confidential, and who it enters."""
    rule = rule_text(plan, gate)
    parts = [dict(GATE_TYPES).get(gate.via or "RRW", "Review Robin session")]
    if gate.confidential:
        parts.append("Confidential")
    parts.append(f"Enters: {rule}" if rule else "Entry decided by hand")
    return " · ".join(parts)


def evaluators_summary(
    sources: tuple[Source, ...], total: Total, mode: str, pools: dict[str, sample_data.Pool]
) -> str:
    """The shut Evaluators card's line: the sources and Total, then the
    mode, e.g. "Nominated 0–1 · Panel A 1–2 · Total 2 · Automatic"."""
    return f"{sources_summary(sources, total, pools)} · {dict(MODES).get(mode, mode)}"
