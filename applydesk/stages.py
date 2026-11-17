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
from dataclasses import dataclass, replace
from datetime import date, datetime

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
    "4.2") on its combined result. A gate never reads another gate."""

    when: tuple[tuple[str, str, str, str], ...]
    then: str
    otherwise: str


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
    # Empty sources read as ``panel`` alone (``sources_of``) until the pages
    # move to them (AD1G rung 3).
    sources: tuple[Source, ...] = ()
    total: Total | None = None
    mode: str = "automatic"
    # Ruling 28: the gate card's own fields, and what evaluators answer.
    description: str = ""
    confidential: bool = False
    fields: tuple[ResponseField, ...] = ()

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
    due: str
    released: str  # "" until released, else when and to whom
    # Its combined result: a weighted average of the gates in its scope
    # (author, 2026-11-13), set with the outcome on Process; the sample's.
    weights: tuple[tuple[str, float], ...] = ()
    rule: Rule | None = None


@dataclass(frozen=True)
class Stage:
    """A step of the exercise's timeline (ruling 15): it holds the
    application form, or gates, and may hold an outcome; never the form
    and a gate together. Named by the operator, "Stage N" until then."""

    number: int
    name: str  # "" until the operator names it
    dates: str
    columns: tuple[Gate | Outcome, ...] = ()
    form: bool = False  # holds the application form (ruling 15)

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


# The model exercise's rules, as Setup will hold them (author, 2026-11-13).
# Gates 1 and 2 run together and take each applicant's last submitted
# application; the shortlist reads their combined result; the interview
# takes the shortlist; Finalists reads the interview; Final results is
# decided by hand.
_EVERYONE = Rule(
    (("status", "", "is", "Submitted"), ("last", "", "le", "1")), "Entered", "Not entered"
)
_LIKERT = Field("integer", "1", "5", "1")
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

_STAGES: dict[str, tuple[Stage, ...]] = {
    # A draft still being set up (segment AD1F): its selection gate added
    # just in time, its panel not chosen yet.
    "c4xh2ndv6s": (
        Stage(1, "", "Dates not set", form=True),
        Stage(
            2,
            "Selection",
            "Dates not set",
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
        Stage(1, "Call for applications", "1 Sep – 15 Oct", form=True),
        Stage(2, "Review", "16 Oct – 10 Nov", (_G1, _G2, _O1)),
        Stage(3, "Interview", "11 Nov – 24 Nov", (_G3, _O2)),
        # The reviews and interviews collated for an offline discussion,
        # then the decision: a stage holding only an outcome.
        Stage(4, "Decision", "25 Nov – 12 Dec", (_O3,)),
    ),
    # A smaller exercise, read blind by one panel; its second stage not
    # yet named.
    "k7mfr3pq8z": (
        Stage(1, "Call for applications", "1 Sep – 31 Oct", form=True),
        Stage(
            2,
            "",
            "1 Nov – 30 Nov",
            (
                Gate(
                    "g1",
                    1,
                    "Panel Review",
                    "RRW",
                    (GateResult("r1", "Score", _LIKERT, "mean"),),
                    panel="panel-a",
                ),
                Outcome(
                    "o1",
                    1,
                    "Final results",
                    ("Awarded", "Not awarded"),
                    "15 Dec",
                    "",
                    (("g1.r1", 1.0),),
                ),
            ),
        ),
    ),
}


def _model_rows(apps: tuple[Application, ...]) -> tuple[Row, ...]:
    """The model exercise mid-way, as its rules left it plus a few hands:
    one application excluded as not eligible, one added to the interview,
    two whose peer reviews are still coming; the Interview stage's outcomes not yet
    decided."""
    rng = random.Random("wa9juxbc2t rounds")
    rating = {a.public_id: round(rng.uniform(2.4, 4.9), 1) for a in apps}
    score = {
        a.public_id: round(min(5.0, rating[a.public_id] + rng.uniform(-0.6, 0.6)), 1) for a in apps
    }
    rank = submitted_rank(tuple(Row(a, {}) for a in apps))
    submitted = [a for a in apps if a.state == "Submitted"]
    excluded = submitted[5].public_id  # not eligible, set by hand
    late = {submitted[-1].public_id, submitted[-2].public_id}  # reviews still coming
    keys = ("g1", "g2", "o1", "g3", "o2", "o3")
    interviews = ("Interviewed 11 Nov", "Interviewed 12 Nov", "Scheduled 18 Nov", "")
    added = ""

    rows: list[Row] = []
    for n, a in enumerate(apps):
        i = a.public_id
        cells: dict[str, Cell] = {k: Cell("") for k in keys}
        if a.state == "Draft":
            rows.append(Row(a, cells))
            continue
        if a.state == "Withdrawn":
            # It keeps what it had, and "—" where it was never entered:
            # withdrawn before the Review stage opened (16 Oct), nothing; during it,
            # its place at the Review stage's gates only.
            day = int(a.submitted.split()[0])
            if day >= 16:
                cells["g1"] = Cell("Entered", f"Withdrew {day} Oct")
                cells["g2"] = Cell("Entered", f"Withdrew {day} Oct")
            rows.append(Row(a, cells))
            continue
        if rank.get(i, 0) != 1:  # not the applicant's last submitted
            for k in ("g1", "g2"):
                cells[k] = Cell("Not entered", "Not the applicant's last")
            cells["g3"] = Cell("Not entered")  # Shortlist not reached: "—"
            rows.append(Row(a, cells))
            continue
        if i == excluded:
            for k in ("g1", "g2"):
                cells[k] = Cell("Not entered", "Excluded: not eligible", by_hand=True)
            cells["g3"] = Cell("Not entered")  # Shortlist not reached: "—"
            rows.append(Row(a, cells))
            continue
        if i in late:
            cells["g1"] = Cell("Entered", f"Rating {rating[i]} · 1 of 3")
            cells["g2"] = Cell("Entered", f"Score {score[i]} · 2 of 4")
            cells["o1"] = Cell("Pending", "Due 10 Nov")
            cells["g3"] = Cell(NO_STATUS)
            cells["o2"] = Cell("Pending", "Due 24 Nov")
            cells["o3"] = Cell("Pending", "Due 12 Dec")
            rows.append(Row(a, cells))
            continue
        cells["g1"] = Cell("Entered", f"Rating {rating[i]} · 3 of 3", rating[i])
        # The faculty panel's recommendations: of four, how many said Fund.
        funds = random.Random(f"recommend {i}").randint(0, 4) * 25
        cells["g2"] = Cell(
            "Entered", f"Score {score[i]} · 4 of 4", score[i], extra=(("r2", str(funds)),)
        )
        mixed = round(0.3 * rating[i] + 0.7 * score[i], 2)
        shortlisted = mixed >= 4.2
        cells["o1"] = Cell("Shortlisted" if shortlisted else "Not shortlisted", "10 Nov")
        if not shortlisted and not added and mixed >= 4.0:
            added = i  # the panel asked to interview one just below
            cells["g3"] = Cell("Entered", "Added by operator: panel request", by_hand=True)
        elif shortlisted:
            note = interviews[n % len(interviews)]
            if note.startswith("Interviewed"):
                mark = round(min(5.0, score[i] + rng.uniform(-0.5, 0.5)), 1)
                cells["g3"] = Cell("Entered", f"Score {mark} · {note.split(' ', 1)[1]}", mark)
            else:
                cells["g3"] = Cell("Entered", note or "Not yet scheduled")
        else:
            cells["g3"] = Cell("Not entered")
        if cells["g3"].value == "Entered":
            cells["o2"] = Cell("Pending", "Due 24 Nov")
            cells["o3"] = Cell("Pending", "Due 12 Dec")
        rows.append(Row(a, cells))
    return tuple(rows)


def _small_rows(apps: tuple[Application, ...]) -> tuple[Row, ...]:
    return tuple(
        Row(
            a,
            {
                "g1": Cell("Entered", "Score 4.1 · 2 of 2", 4.1),
                "o1": Cell("Pending", "Due 15 Dec"),
            },
        )
        for a in apps
    )


def plan_of(exercise_id: str) -> Plan:
    """The stages and every application's cells for one exercise. An
    exercise not yet set up has one stage, holding the form, as a
    new exercise starts (ruling 15)."""
    apps = sample_data.applications_of(exercise_id)
    if exercise_id not in _STAGES:
        e = sample_data.exercise(exercise_id)
        dates = (
            "Dates not set"
            if e is None or "Not set" in (e.opens, e.application_stage_ends)
            else f"{e.opens} – {e.application_stage_ends}"
        )
        return Plan((Stage(1, "", dates, form=True),), tuple(Row(a, {}) for a in apps))
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


def counts(plan: Plan, column: Gate | Outcome) -> str:
    """A column header's tally across every application, e.g.
    "86 entered · 2 to decide"; an outcome's, "24 shortlisted · 2 pending"."""
    values = [
        r.cells[column.key].value for r in plan.rows if r.cells.get(column.key, Cell("")).value
    ]
    if isinstance(column, Gate):
        order = [("Entered", "entered"), (NO_STATUS, "to decide")]
    else:
        order = [(v, v.lower()) for v in column.values[:1]] + [("Pending", "pending")]
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

    parts: list[str] = []
    for kind, key, op, value in column.rule.when:
        sign = {"ge": "≥", "lt": "<"}.get(op, "is")
        if kind == "last":
            parts.append(_SAID["last"] if value == "1" else _SAID["lastN"].format(v=value))
        elif kind == "res":
            parts.append(f"{result_label(plan, key)} {sign} {value}")
        elif kind == "ent":
            parts.append(f"Entry at {name(key)} is {value}")
        elif kind == "out":
            parts.append(f"{name(key)} is {value or '—'}")
        else:
            parts.append(f"{_SAID[kind]} {sign} {value}")
    then, otherwise = column.rule.then or "—", column.rule.otherwise or "—"
    return f"{' and '.join(parts)} → {then}, else {otherwise}"


def rule_json(column: Gate | Outcome) -> dict[str, object] | None:
    """The column's rule as the page's script reads it."""
    if column.rule is None:
        return None
    return {
        "when": [list(c) for c in column.rule.when],
        "then": column.rule.then,
        "otherwise": column.rule.otherwise,
    }


def panel_uses(exercise_id: str) -> dict[str, tuple[str, ...]]:
    """What uses each of the exercise's panels (ruling 19), by panel key,
    in page order: the form's Select people questions, then each gate in
    timeline order, e.g. ("Form: Preferred reviewer", "Gate 1: Peer
    Review"). A panel nothing uses has no entry."""
    uses: dict[str, list[str]] = {}
    for c in sample_data.form_cards(exercise_id):
        if c.kind == "field" and c.type == "people" and c.pool != "institution":
            uses.setdefault(c.pool, []).append(f"Form: {c.label or 'Untitled question'}")
    for column in plan_of(exercise_id).columns:
        if isinstance(column, Gate) and column.panel:
            uses.setdefault(column.panel, []).append(f"Gate {column.number}: {column.label}")
    return {k: tuple(v) for k, v in uses.items()}


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


def derivation_text(r: GateResult) -> str:
    """How the responses become the result, e.g. "Mean of 2 or more"."""
    label = dict(DERIVATIONS).get(r.derive, r.derive)
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
        lo, hi = total_bounds(gate.sources)
        return gate.sources, gate.total or Total(lo, hi)
    if not gate.panel:
        return (), Total(0, 0)
    pool = sample_data.panel_pools(exercise_id).get(gate.panel)
    size = len(pool["members"]) if pool else 0
    return (Source("panel", gate.panel, size, size),), Total(size, size)


def total_bounds(sources: tuple[Source, ...]) -> tuple[int, int]:
    """What the Total may be: no lower than the sources' mins together, no
    higher than their maxes (ruling 27)."""
    return sum(s.min for s in sources), sum(s.max for s in sources)


def total_problem(sources: tuple[Source, ...], total: Total) -> str:
    """Why the gate's Total cannot hold, or "" (shown on the Outline, not
    silently clamped)."""
    if not sources:
        return "no evaluators"
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
    return bool(total_problem(sources, total)) or any(
        (s.kind == "panel" and s.ref not in pools)
        or (s.kind == "nominated" and not s.ref)
        or s.min > s.max
        for s in sources
    )


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
    the lower sources' mins. Evaluators are distinct by email (any case),
    a person in two sources counted for the higher-ranked, and the
    candidate never their own. A panel gives its least-loaded members
    first; ``load`` counts each evaluator's dossiers across calls, from
    every source, so the work spreads evenly."""
    chosen: list[tuple[str, int]] = []
    seen = {candidate.casefold()} if candidate else set[str]()
    unmet: list[int] = []
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
        want = source.max if rank == 0 else max(source.min, total.min - len(chosen))
        given = available[: max(0, min(len(available), source.max, want, room))]
        for person in given:
            seen.add(person.casefold())
            chosen.append((person, rank))
            if load is not None:  # every dossier counts, a nominated one too (Codex)
                load[person.casefold()] = load.get(person.casefold(), 0) + 1
        if len(given) < source.min:
            unmet.append(rank)
    return Filling(tuple(chosen), max(0, total.min - len(chosen)), tuple(unmet))


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
    if gate.fields:
        return gate.fields
    return tuple(ResponseField(f"f{i}", r.name, r.field) for i, r in enumerate(gate.results, 1))


def source_field(gate: Gate, result: GateResult) -> ResponseField | None:
    """The response field a result collates: by its ``source`` key, else
    the field in its place (``fields_of``'s fallback)."""
    fields = fields_of(gate)
    if result.source:
        return next((f for f in fields if f.key == result.source), None)
    if gate.fields:
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
