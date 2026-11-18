"""What Extract data's files hold (segment AD1J): each file's name and
columns, and each gate's rows, as Review Robin's Extract data cuts a
session's data. The page's cards and the downloads (rung 3) read this one
shape; nothing here is drawn on screen as data.

The files are CSV in Review Robin's envelope (UTF-8 with a byte-order mark,
a header row). A gate's answers per pair are sample answers seeded per
pair until Review Robin's handoff returns real ones (AD5); every other
value is the sample's own.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
import zipfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from applydesk import sample_data, stages, workflow
from applydesk.sample_data import Exercise

#: Every application file's first columns: who and when.
APPLICATION_KEYS = ("application_id", "dossier_id", "applicant", "email", "state", "submitted")
#: A gate file's first columns, a row per pair.
PAIR_KEYS = ("dossier_id", "evaluator", "evaluator_email")
#: The alias key: the one file that joins a Dossier ID to its applicant.
ALIAS_KEYS = ("dossier_id", "application_id", "applicant", "email")
#: What *Extract all data* may carry until Extract setup's files (rung 4).
CARRIES = frozenset({"applications", "gates", "outcomes"})
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


def _who(names: bool) -> tuple[str, ...]:
    """The applicant's columns, or none for a file by Dossier ID alone."""
    return ("applicant", "email") if names else ()


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


def _outcome_columns(plan: stages.Plan, names: bool = True) -> tuple[str, ...]:
    """Each gate's results as Dossiers collates them, then each outcome's
    value and when it was released, in the timeline's order."""
    out: list[str] = ["dossier_id", *_who(names)]
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


# --- The files (rung 3) ---

Table = tuple[tuple[str, ...], list[list[str]]]  # a header and its rows


def csv_bytes(table: Table) -> bytes:
    """A table as Review Robin's CSV envelope: UTF-8 with a BOM, so Excel
    reads it as UTF-8, and a header row."""
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\r\n")
    w.writerow(table[0])
    w.writerows(table[1])
    return ("\ufeff" + out.getvalue()).encode("utf-8")


def _number(x: float | None) -> str:
    return "" if x is None else f"{round(x, 2):g}"


def _shown(plan: stages.Plan, rows: str, drafts: bool = False) -> list[stages.Row]:
    """*Last applications* or *All applications* (ruling 13), submitted
    ones only unless drafts are asked for."""
    last = stages.last_submitted(plan.rows) if rows == "last" else None
    return [
        r
        for r in plan.rows
        if (last is None or r.application.public_id in last)
        and (drafts or r.application.state == "Submitted")
    ]


def applications(e: Exercise, rows: str = "last", drafts: bool = False) -> Table:
    """A row per application: who and when, then each form question's
    answer, in the form's order."""
    plan = stages.plan_of(e.public_id)
    questions = _questions(e.public_id)
    out: list[list[str]] = []
    for r in _shown(plan, rows, drafts):
        a = r.application
        answers = sample_data.answers(e.public_id, a)
        out.append(
            [a.public_id, a.dossier_id, a.applicant, a.email, a.state, a.submitted]
            + [answers.get(q, "") for q in questions]
        )
    return APPLICATION_KEYS + questions, out


def _results(c: stages.Cell | None, g: stages.Gate) -> list[str]:
    """A gate's results for one dossier as Dossiers collates them: the
    first is the cell's ``result``, the others its ``extra``."""
    if c is None:
        return ["" for _ in g.results]
    extra = dict(c.extra)
    return [_number(c.result) if i == 0 else extra.get(r.key, "") for i, r in enumerate(g.results)]


def _seed(*parts: str) -> int:
    return int.from_bytes(hashlib.sha256("|".join(parts).encode()).digest()[:4], "big")


_COMMENTS = ("", "", "Thoughtful and reliable.", "Knows the house well.", "Needs more experience.")


def _answer(f: stages.ResponseField, *key: str) -> str:
    """A sample answer, the same every time for the same pair and field."""
    n = _seed(*key, f.key)
    t = f.field
    if t.type in ("integer", "decimal") and t.min and t.max:
        lo, hi = int(float(t.min)), int(float(t.max))
        return str(lo + n % (hi - lo + 1))
    if t.type == "list" and t.options:
        options = [o.strip() for o in t.options.split(",")]
        return options[0] if n % 10 < 7 else options[n % len(options)]
    return _COMMENTS[n % len(_COMMENTS)]


def gate(e: Exercise, number: int, shape: str = "pair", names: bool = False) -> Table | None:
    """A gate's file: a row per pair with each response field's answer, or
    a row per application with its results. None for a gate not sent."""
    plan = stages.plan_of(e.public_id)
    g = next((c for c in plan.columns if isinstance(c, stages.Gate) and c.number == number), None)
    if g is None or not _gate(e, g).sent:
        return None
    rows, _ = stages.assignments(e.public_id, g)
    who = _who(names)
    if shape == "application":
        cells = {r.application.public_id: r.cells.get(g.key) for r in plan.rows}
        header = ("dossier_id", *who, *(r.name for r in g.results))
        body = [
            [a.application.dossier_id]
            + ([a.application.applicant, a.application.email] if names else [])
            + _results(cells.get(a.application.public_id), g)
            for a in rows
        ]
        return header, body
    fields = stages.fields_of(g)
    header = ("dossier_id", *who, "evaluator", "evaluator_email", *(f.label for f in fields))
    body: list[list[str]] = []
    for p in stages.pairs_of(rows):
        if not p.email:
            continue  # a dossier with no evaluator yet has no answers
        a = p.of.application
        body.append(
            [a.dossier_id]
            + ([a.applicant, a.email] if names else [])
            + [p.name, p.email]
            + [_answer(f, a.dossier_id, p.email.casefold()) for f in fields]
        )
    return header, body


def outcomes(e: Exercise, rows: str = "last", names: bool = True) -> Table:
    """A row per application: each gate's results, then each outcome's
    value and, once released, when."""
    plan = stages.plan_of(e.public_id)
    body: list[list[str]] = []
    for r in _shown(plan, rows):
        a = r.application
        line = [a.dossier_id] + ([a.applicant, a.email] if names else [])
        for c in plan.columns:
            cell = r.cells.get(c.key)
            if isinstance(c, stages.Gate):
                line += _results(cell, c)
            else:
                value = cell.value if cell else ""
                decided = value not in ("", "Pending")
                line += [value, c.released.partition(" · ")[0] if c.released and decided else ""]
        body.append(line)
    return _outcome_columns(plan, names), body


def _zip(files: Iterable[tuple[str, Table]], notes: Sequence[tuple[str, str]] = ()) -> bytes:
    """A ZIP of CSVs, a manifest first: each file and its rows, then what
    was left out and why."""
    files = list(files)
    manifest: Table = (
        ("file", "rows", "note"),
        [[n, str(len(t[1])), ""] for n, t in files] + [[n, "", why] for n, why in notes],
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.csv", csv_bytes(manifest))
        for name, table in files:
            z.writestr(name, csv_bytes(table))
    return buf.getvalue()


def gates_zip(e: Exercise, shape: str = "pair", names: bool = False) -> bytes:
    x = of(e)
    files: list[tuple[str, Table]] = []
    notes: list[tuple[str, str]] = []
    for g in x.gates:
        table = gate(e, g.number, shape, names)
        if table is None:
            notes.append((g.name, "Not sent"))
        else:
            files.append((g.name, table))
    return _zip(files, notes)


def all_zip(
    e: Exercise,
    carries: frozenset[str] = CARRIES,
    names: bool = True,
    rows: str = "last",
    drafts: bool = False,
    shape: str = "pair",
    outcome_rows: str = "last",
) -> bytes:
    """*Extract all data*: the files the cards make as each is set, the
    applicants named or not as the card says (the applications file is
    the applicants' own, so it always names them). ``rows`` and ``drafts``
    are the Applications card's, ``shape`` By gate's, ``outcome_rows``
    the Outcomes card's (Codex)."""
    x = of(e)
    files: list[tuple[str, Table]] = []
    notes: list[tuple[str, str]] = []
    if "applications" in carries:
        files.append(("applications.csv", applications(e, rows, drafts)))
    if "gates" in carries:
        for g in x.gates:
            table = gate(e, g.number, shape, names)
            if table is None:
                notes.append((g.name, "Not sent"))
            else:
                files.append((g.name, table))
    if "outcomes" in carries:
        files.append(("outcomes.csv", outcomes(e, outcome_rows, names)))
    return _zip(files, notes)
