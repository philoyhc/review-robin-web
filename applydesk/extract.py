"""What Extract data's files hold (segment AD1J): each file's name and
columns, and each gate's rows, as Review Robin's Extract data cuts a
session's data. The page's cards and, from rung 3, the downloads read this
one shape; nothing here is drawn on screen as data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from applydesk import sample_data, stages, workflow
from applydesk.sample_data import Exercise

#: Every application file's first columns: who and when.
APPLICATION_KEYS = ("application_id", "dossier_id", "applicant", "email", "state", "submitted")
#: A gate file's first columns, a row per pair.
PAIR_KEYS = ("dossier_id", "evaluator", "evaluator_email")
#: The alias key: the one file that joins a Dossier ID to its applicant.
ALIAS_KEYS = ("dossier_id", "application_id", "applicant", "email")
#: Extract setup's files, one per Setup page (author, 2026-11-18: CSV).
SETUP_FILES = ("form.csv", "process.csv", "panels.csv", "emails.csv")


@dataclass(frozen=True)
class GateFile:
    """One gate's file: its name, columns and rows (pairs), or not sent."""

    number: int
    label: str
    name: str  # gate_<n>_<slug>.csv
    columns: tuple[str, ...]
    pairs: int
    sent: bool  # its Review Robin session has opened, so it has answers
    confidential: bool


@dataclass(frozen=True)
class Extract:
    zip_name: str
    submitted: int  # submitted applications: none, and there is nothing to extract
    draft: bool
    application_columns: tuple[str, ...]
    gates: tuple[GateFile, ...]
    outcome_columns: tuple[str, ...]

    @property
    def files(self) -> tuple[str, ...]:
        """What *Extract all data* carries by default, the manifest first;
        a gate not sent has no file."""
        gates = tuple(g.name for g in self.gates if g.sent)
        return ("manifest.csv", "applications.csv", *gates, "outcomes.csv")


def slug(text: str) -> str:
    """A file name's part: lower case, every run of other characters one
    underscore, e.g. "Staff interview" → "staff_interview"."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "untitled"


def _questions(exercise_id: str) -> tuple[str, ...]:
    """A column per form question, in the form's order; a section's title,
    a page break and a text block's title are no column."""
    return tuple(
        c.label
        for c in sample_data.form_cards(exercise_id)
        if c.kind == "field" and c.type != "text" and c.label
    )


def _gate(e: Exercise, g: stages.Gate) -> GateFile:
    state, line = workflow.gate_state(e.public_id, g.key)
    rows, _ = stages.assignments(e.public_id, g)
    pairs = len([p for p in stages.pairs_of(rows) if p.email])
    columns = PAIR_KEYS + tuple(f.label for f in stages.fields_of(g))
    return GateFile(
        g.number,
        g.label or "Untitled gate",
        f"gate_{g.number}_{slug(g.label or 'untitled')}.csv",
        columns,
        pairs,
        e.state != "Draft" and workflow.gate_opened(state, line),
        g.confidential,
    )


def _outcome_columns(plan: stages.Plan) -> tuple[str, ...]:
    """Each gate's results as Dossiers collates them, then each outcome's
    value and when it was released, in the timeline's order."""
    out: list[str] = ["dossier_id", "applicant"]
    for c in plan.columns:
        if isinstance(c, stages.Gate):
            out += [f"{c.label}: {r.name}" for r in c.results]
        else:
            out += [c.label, f"{c.label} released"]
    return tuple(out)


def of(e: Exercise) -> Extract:
    plan = stages.plan_of(e.public_id)
    apps = sample_data.applications_of(e.public_id)
    gates = tuple(_gate(e, c) for c in plan.columns if isinstance(c, stages.Gate))
    return Extract(
        f"{slug(e.code or e.public_id)}_extract.zip",
        sum(a.state == "Submitted" for a in apps),
        e.state == "Draft",
        APPLICATION_KEYS + _questions(e.public_id),
        gates,
        _outcome_columns(plan),
    )
