"""Rounds of gates and outcomes (ruling 13, segment AD1C), on sample data.

An exercise's evaluation runs in sequential rounds; a round holds gates,
which may run together, and outcomes placed after them. Setup and the
Timeline will hold these (a later segment); here they are fixed, and each
application's place at each gate and outcome is worked out from a seeded
score, so the Applications page reads as an exercise partway through.
Nothing is saved."""

from __future__ import annotations

import random
from dataclasses import dataclass

from applydesk import sample_data
from applydesk.sample_data import Application

#: Gate admittance, in the order a chip cycles (author, 2026-11-13): no
#: status yet, then whether the application is sent through the gate.
#: Outcomes keep their own values, with Pending, from Setup.
NO_STATUS = "—"
ADMITTANCE: tuple[str, ...] = (NO_STATUS, "Entered", "Not entered")


@dataclass(frozen=True)
class Gate:
    key: str
    number: int
    label: str
    via: str  # "RRW": a Review Robin session
    measure: str  # what its result is called: "Rating", "Score", ""


@dataclass(frozen=True)
class Outcome:
    key: str
    number: int
    label: str
    values: tuple[str, ...]  # the decided values; Pending is always offered
    due: str
    released: str  # "" until released, else when and to whom


@dataclass(frozen=True)
class Round:
    label: str
    dates: str
    columns: tuple[Gate | Outcome, ...]


@dataclass(frozen=True)
class Cell:
    value: str  # an admittance, an outcome value, or "" for none ("—")
    note: str = ""  # under the chip: a gate's result, a reason, a date
    result: float | None = None  # a gate's finished result, which a rule reads


@dataclass(frozen=True)
class Row:
    application: Application
    cells: dict[str, Cell]


@dataclass(frozen=True)
class Plan:
    """What the Applications page draws for one exercise."""

    stage_dates: str  # the Application stage's From–To
    rounds: tuple[Round, ...]
    rows: tuple[Row, ...]

    @property
    def columns(self) -> tuple[Gate | Outcome, ...]:
        return tuple(c for r in self.rounds for c in r.columns)


_G1 = Gate("g1", 1, "Peer Review", "RRW", "Rating")
_G2 = Gate("g2", 2, "Faculty Panel Review", "RRW", "Score")
_O1 = Outcome(
    "o1",
    1,
    "Shortlist for interview",
    ("Shortlisted", "Not shortlisted"),
    "10 Nov",
    "10 Nov · to applicants",
)
_G3 = Gate("g3", 3, "Interview", "RRW", "")
_O2 = Outcome("o2", 2, "Finalists", ("Finalist", "Not a finalist"), "24 Nov", "")
_O3 = Outcome("o3", 3, "Final results", ("Awarded", "Waitlisted", "Not awarded"), "12 Dec", "")

_ROUNDS: dict[str, tuple[str, tuple[Round, ...]]] = {
    # The model exercise (author, 2026-11-12/13): mock-up v3's setup.
    "wa9juxbc2t": (
        "1 Sep – 15 Oct",
        (
            Round("Round 1", "16 Oct – 10 Nov", (_G1, _G2, _O1)),
            Round("Round 2", "11 Nov – 24 Nov", (_G3, _O2)),
            Round("Final", "25 Nov – 12 Dec", (_O3,)),
        ),
    ),
    # A smaller exercise: one round, read blind by one panel.
    "k7mfr3pq8z": (
        "1 Sep – 31 Oct",
        (
            Round(
                "Round 1",
                "1 Nov – 30 Nov",
                (
                    Gate("g1", 1, "Panel Review", "RRW", "Score"),
                    Outcome("o1", 1, "Final results", ("Awarded", "Not awarded"), "15 Dec", ""),
                ),
            ),
        ),
    ),
}

#: The model exercise's thresholds, as a rule would set them (rung 3).
_PANEL_FROM = 3.5  # Rating at Peer Review to enter the Faculty Panel
_SHORTLIST = 24  # the top Scores at the Faculty Panel


def _model_rows(apps: tuple[Application, ...]) -> tuple[Row, ...]:
    rng = random.Random("wa9juxbc2t rounds")
    rating = {a.public_id: round(rng.uniform(2.4, 4.9), 1) for a in apps}
    score = {
        a.public_id: round(min(5.0, rating[a.public_id] + rng.uniform(-0.6, 0.6)), 1) for a in apps
    }
    submitted = [a for a in apps if a.state == "Submitted"]
    excluded = {submitted[5].public_id}  # not eligible, set by hand
    added = {next(a.public_id for a in submitted if 3.2 <= rating[a.public_id] < _PANEL_FROM)}
    late = {submitted[-1].public_id, submitted[-2].public_id}  # reviews still coming
    panel = [
        a
        for a in submitted
        if a.public_id not in excluded | late
        and (rating[a.public_id] >= _PANEL_FROM or a.public_id in added)
    ]
    shortlisted = {
        a.public_id for a in sorted(panel, key=lambda a: -score[a.public_id])[:_SHORTLIST]
    }
    interviews = ("Interviewed 11 Nov", "Interviewed 12 Nov", "Scheduled 18 Nov", "")

    rows: list[Row] = []
    for n, a in enumerate(apps):
        i = a.public_id
        cells: dict[str, Cell] = {}
        if a.state == "Draft":
            rows.append(Row(a, {k: Cell("") for k in ("g1", "g2", "o1", "g3", "o2", "o3")}))
            continue
        if a.state == "Withdrawn":
            # It keeps what it had, and "—" where it was never admitted
            # (the plan's Semantics): withdrawn before Round 1 opened (16
            # Oct), nothing; during it, its place at Peer Review only.
            day = int(a.submitted.split()[0])
            during = a.submitted.split()[1] != "Oct" or day >= 16
            cells = {k: Cell("") for k in ("g1", "g2", "o1", "g3", "o2", "o3")}
            if during:
                cells["g1"] = Cell("Entered", f"Withdrew {day} {a.submitted.split()[1]}")
            rows.append(Row(a, cells))
            continue
        if i in excluded:
            cells["g1"] = Cell("Not entered", "Excluded: not eligible")
        elif i in late:
            cells["g1"] = Cell("Entered", f"Rating {rating[i]} · 1 of 3")
        else:
            cells["g1"] = Cell("Entered", f"Rating {rating[i]} · 3 of 3", rating[i])
        if i in late:
            cells["g2"] = Cell(NO_STATUS, "Waiting on Peer Review")
            cells["o1"] = Cell("Pending", "Due 10 Nov")
        elif i in excluded:
            cells["g2"] = Cell("Not entered")
            cells["o1"] = Cell("Not shortlisted", "10 Nov")
        else:
            if i in added:
                cells["g2"] = Cell("Entered", "Added by operator: panel request", score[i])
            elif rating[i] >= _PANEL_FROM:
                cells["g2"] = Cell("Entered", f"Score {score[i]} · 4 of 4", score[i])
            else:
                cells["g2"] = Cell("Not entered", f"Below {_PANEL_FROM} (Rating)")
            cells["o1"] = Cell("Shortlisted" if i in shortlisted else "Not shortlisted", "10 Nov")
        if i in shortlisted:
            note = interviews[n % len(interviews)]
            cells["g3"] = Cell("Entered" if note else NO_STATUS, note or "Not yet scheduled")
            cells["o2"] = Cell("Pending", "Due 24 Nov")
            cells["o3"] = Cell("Pending", "Due 12 Dec")
        else:
            cells["g3"] = Cell(NO_STATUS if i in late else "Not entered")
            cells["o2"] = Cell("Pending", "Due 24 Nov") if i in late else Cell("")
            cells["o3"] = Cell("Pending", "Due 12 Dec") if i in late else Cell("")
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
    """The rounds and every application's cells for one exercise; an
    exercise with no rounds set up has none (columns end at Status)."""
    apps = sample_data.applications_of(exercise_id)
    if exercise_id not in _ROUNDS:
        return Plan("", (), tuple(Row(a, {}) for a in apps))
    stage, rounds = _ROUNDS[exercise_id]
    rows = _model_rows(apps) if exercise_id == "wa9juxbc2t" else _small_rows(apps)
    return Plan(stage, rounds, rows)


def counts(plan: Plan, column: Gate | Outcome) -> str:
    """A column header's tally across every application, e.g.
    "86 selected · 2 pending"."""
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
