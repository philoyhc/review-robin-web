"""What Extract data's files hold (segment AD1J): each file's name and
columns, and each gate's rows, as Review Robin's Extract data cuts a
session's data. The page's cards and the downloads (rung 3) read this one
shape; nothing here is drawn on screen as data.

The files are CSV with a header row, UTF-8 with a byte-order mark so
Excel reads them as UTF-8: Apply Desk's choice, which Review Robin's
importers tolerate on read (`spec/csv_contracts.md` §1) though its own
extracts write none. Where the sample has no answer (a gate's answers per
pair, a form's text, number and photo questions) the files carry sample
answers seeded per application or pair, the same every time, until the
forms and Review Robin's handoff supply real ones (AD4, AD5).
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
import zipfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import date

from applydesk import clock, locks, sample_data, stages, workflow
from applydesk.sample_data import Exercise

#: Every application file's first columns: who and when.
APPLICATION_KEYS = ("application_id", "dossier_id", "applicant", "email", "state", "submitted")
#: A gate file's first columns, a row per pair.
PAIR_KEYS = ("dossier_id", "evaluator", "evaluator_email")
#: The alias key: the one file that joins a Dossier ID to its applicant.
ALIAS_KEYS = ("dossier_id", "application_id", "applicant", "email")
#: What *Extract all data* may carry; the alias key never (kept apart).
CARRIES = frozenset({"applications", "gates", "outcomes", "setup"})
#: What it carries until a viewer says otherwise: setup is for cloning.
DEFAULT_CARRIES = frozenset({"applications", "gates", "outcomes"})
#: Extract setup's files, one per Setup page (author, 2026-11-18: CSV).
SETUP_FILES = ("form.csv", "process.csv", "panels.csv", "emails.csv")
SETUP_PARTS = frozenset(f.removesuffix(".csv") for f in SETUP_FILES)


@dataclass(frozen=True)
class GateFile:
    """One gate's file: its name, columns and rows (pairs), or not sent."""

    number: int  # for display only
    key: str  # its handle (ruling 37, AD-48): the download is gate_<key>.csv
    label: str
    name: str  # <key>_<slug>.csv
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


def _questions(exercise_id: str) -> tuple[sample_data.FormCard, ...]:
    """A column per form question, in the form's order, its header the
    question's label and its answers read by key (segment AD2D); a
    section's title, a page break and a text block's title are no column."""
    return tuple(
        c
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
        g.key,
        g.label or "Untitled gate",
        f"{g.key}_{slug(g.label or 'untitled')}.csv",
        columns,
        pairs,
        not locks.is_draft(e) and workflow.gate_opened(state, line),
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


def sensitive(e: Exercise) -> bool:
    """Blind review on, or a confidential gate: files name applicants only
    when asked (Semantics: such a gate's file defaults to Dossier IDs)."""
    plan = stages.plan_of(e.public_id)
    return e.blind or any(isinstance(c, stages.Gate) and c.confidential for c in plan.columns)


def names_by_default(e: Exercise, file: str) -> bool:
    """*Applicants as*'s starting value for a file: a gate's by Dossier ID;
    *Extract all data* by name unless ``sensitive``; the outcomes by name
    unless blind review is on (AD-65); the rest by name."""
    if file.startswith("gate"):
        return False
    if file == "all.zip":
        return not sensitive(e)
    return not (file == "outcomes.csv" and e.blind)


def zip_name(e: Exercise, kind: str, on: date | None = None, ext: str = "zip") -> str:
    """``<code>_<kind>_<date>.zip`` (Semantics), e.g. ra_2027_extract_2026-11-18.zip;
    ``ext`` names another file the same way (Dossiers' CSV, AD-66). Dated
    by the one clock, in the exercise's timezone (AD-40)."""
    day = on or clock.today(sample_data.timezone(e))
    return f"{slug(e.code or e.public_id)}_{kind}_{day.isoformat()}.{ext}"


def of(e: Exercise) -> Extract:
    plan = stages.plan_of(e.public_id)
    apps = sample_data.applications_of(e.public_id)
    gates = tuple(_gate(e, c) for c in plan.columns if isinstance(c, stages.Gate))
    return Extract(
        zip_name(e, "extract"),
        sum(a.state == "Submitted" for a in apps),
        locks.is_draft(e),
        APPLICATION_KEYS + tuple(c.label for c in _questions(e.public_id)),
        gates,
        _outcome_columns(plan, names_by_default(e, "outcomes.csv")),
    )


# --- The files (rung 3) ---

Table = tuple[tuple[str, ...], list[list[str]]]  # a header and its rows


_FORMULA = re.compile(r"[=+\-@\t\r]")
_NUMBER = re.compile(r"-?[0-9]+(\.[0-9]+)?")


def safe(cell: str) -> str:
    """A cell a spreadsheet will not run as a formula: one starting with
    =, +, -, @, a tab or a return gets a leading apostrophe, a number
    aside (applicants' own text lands here from AD4; cold read)."""
    return "'" + cell if _FORMULA.match(cell) and not _NUMBER.fullmatch(cell) else cell


def guarded(text: str) -> str:
    """A CSV's text with each cell :func:`safe`, as written for a person to
    open: a gate's bundle file on its download, while the handoff to Review
    Robin keeps the bytes Review Robin's import reads (findings 2026-11-20
    S12, ruled 2026-11-20)."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerows([safe(cell) for cell in row] for row in csv.reader(io.StringIO(text)))
    return out.getvalue()


def csv_bytes(table: Table) -> bytes:
    """A table as CSV: a header row, each cell ``safe``, UTF-8 with a BOM
    so Excel reads it as UTF-8 (Apply Desk's choice; module docstring)."""
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\r\n")
    w.writerow([safe(c) for c in table[0]])
    w.writerows([[safe(c) for c in row] for row in table[1]])
    return ("\ufeff" + out.getvalue()).encode("utf-8")


def _number(x: float | None) -> str:
    return "" if x is None else f"{round(x, 2):g}"


def _shown(plan: stages.Plan, rows: str, drafts: bool = False) -> list[stages.Row]:
    """*Last applications* or *All applications* (ruling 13), submitted
    ones only unless drafts are asked for: drafts, never a withdrawn one."""
    last = stages.last_submitted(plan.rows) if rows == "last" else None
    return [
        r
        for r in plan.rows
        if (last is None or r.application.public_id in last)
        and (r.application.state == "Submitted" or (drafts and r.application.state == "Draft"))
    ]


def applications(e: Exercise, rows: str = "last", drafts: bool = False) -> Table:
    """A row per application: who and when, then each form question's
    answer, in the form's order."""
    plan = stages.plan_of(e.public_id)
    questions = _questions(e.public_id)
    out: list[list[str]] = []
    for r in _shown(plan, rows, drafts):
        a = r.application
        known = sample_data.answers(e.public_id, a)
        out.append(
            [a.public_id, a.dossier_id, a.applicant, a.email, a.state, a.submitted]
            + [known.get(c.key) or _form_answer(e, a, c) for c in questions]
        )
    return APPLICATION_KEYS + tuple(c.label for c in questions), out


_TEXT = (
    "I enjoy bringing people together.",
    "Two years on my house committee.",
    "Organised orientation week for first years.",
    "",
)


def _form_answer(e: Exercise, a: sample_data.Application, c: sample_data.FormCard) -> str:
    """An answer the sample does not hold, seeded per application and
    question (module docstring): a Select people question's nominees
    (Codex) and a choose-any list's choices joined by "; " (Semantics); a
    number within its bounds; a photo its file name; text a canned line."""
    n = _seed(a.public_id, c.label)
    if c.type == "people":
        return "; ".join(sample_data.nominees(e.public_id, a, c.key))
    if c.type == "list":
        options = [o.strip() for o in c.options.split(",") if o.strip()]
        if not options:
            return ""
        picked = [o for i, o in enumerate(options) if (n >> i) & 1] or options[:1]
        return options[n % len(options)] if c.exclusive else "; ".join(picked)
    if c.type in ("integer", "decimal"):
        lo = int(float(c.min)) if _NUMBER.fullmatch(c.min) else 0
        hi = int(float(c.max)) if _NUMBER.fullmatch(c.max) else lo + 10
        return str(lo + n % (max(hi - lo, 0) + 1))
    if c.type == "photo":
        return f"{a.dossier_id}.jpg"
    label = c.label.lower()
    if "name" in label:
        return a.applicant.split()[0]
    if "number" in label:
        return f"A{n % 10**7:07d}{'ABEHJLMNRUWX'[n % 12]}"
    text = _TEXT[n % len(_TEXT)]
    return text or ("" if not c.required else _TEXT[0])


def form_answers(
    e: Exercise, a: sample_data.Application
) -> tuple[tuple[tuple[str, str], ...], tuple[tuple[str, str], ...]]:
    """The application as its form asks it (AD-26), the same answers
    Extract writes: each question of the Form's cards, in order, "—" where
    it has none; split into shown to evaluators and not shown. Text blocks
    and unlabeled questions are not questions; the title is the page's own."""
    known = sample_data.answers(e.public_id, a)
    shown: list[tuple[str, str]] = []
    hidden: list[tuple[str, str]] = []
    for c in sample_data.form_cards(e.public_id):
        if c.kind != "field" or c.type == "text" or not c.label:
            continue
        value = known.get(c.key) or _form_answer(e, a, c)
        (shown if c.shown else hidden).append((c.label, value or "—"))
    return tuple(shown), tuple(hidden)


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


def gate_file(
    e: Exercise, key: str, shape: str = "pair", names: bool = False
) -> tuple[str, Table] | None:
    """A gate's file and its name, or None for a gate not sent or none."""
    g = next((x for x in of(e).gates if x.key == key), None)
    table = gate(e, key, shape, names) if g else None
    return (g.name, table) if g and table else None


def gate(e: Exercise, key: str, shape: str = "pair", names: bool = False) -> Table | None:
    """A gate's file: a row per pair with each response field's answer, or
    a row per application with its results. None for a gate not sent."""
    plan = stages.plan_of(e.public_id)
    g = stages.gate_keyed(plan, key)
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
        table = gate(e, g.key, shape, names)
        if table is None:
            notes.append((g.name, "Not sent"))
        else:
            files.append((g.name, table))
    return _zip(files, notes)


def all_zip(
    e: Exercise,
    carries: frozenset[str] = DEFAULT_CARRIES,
    names: bool = True,
    rows: str = "last",
    drafts: bool = False,
    shape: str = "pair",
    outcome_rows: str = "last",
    setup_parts: frozenset[str] = SETUP_PARTS,
) -> bytes:
    """*Extract all data*: the files the cards make as each is set, the
    applicants named or not as the card says (the applications file is
    the applicants' own, so it always names them). ``rows`` and ``drafts``
    are the Applications card's, ``shape`` By gate's, ``outcome_rows``
    the Outcomes card's, ``setup_parts`` Extract setup's (Codex)."""
    x = of(e)
    files: list[tuple[str, Table]] = []
    notes: list[tuple[str, str]] = []
    if "applications" in carries:
        files.append(("applications.csv", applications(e, rows, drafts)))
    if "gates" in carries:
        for g in x.gates:
            table = gate(e, g.key, shape, names)
            if table is None:
                notes.append((g.name, "Not sent"))
            else:
                files.append((g.name, table))
    if "outcomes" in carries:
        files.append(("outcomes.csv", outcomes(e, outcome_rows, names)))
    if "setup" in carries:
        files += [(f"setup/{n}", t) for n, t in setup(e, setup_parts)]
    return _zip(files, notes)


# --- The alias key and the setup (rung 4) ---


def alias_key(e: Exercise) -> Table:
    """Dossier ID to applicant, every application's, drafts included: the
    one file joining what Review Robin sees to who it is."""
    return ALIAS_KEYS, [
        [a.dossier_id, a.public_id, a.applicant, a.email]
        for a in sample_data.applications_of(e.public_id)
    ]


def _yes(flag: bool) -> str:
    return "yes" if flag else "no"


def _form(e: Exercise) -> Table:
    """The form's cards in order, each as the Form page sets it."""
    header = (
        "order", "kind", "type", "label", "help", "min", "max", "step",
        "options", "choose", "required", "shown_to_evaluators", "pool",
    )  # fmt: skip
    body = [
        [
            str(i),
            c.kind,
            c.type if c.kind == "field" else "",
            c.label,
            c.help,
            c.min,
            c.max,
            c.step,
            c.options,
            ("one" if c.exclusive else "any") if c.type == "list" else "",
            _yes(c.required),
            _yes(c.shown),
            c.pool if c.type == "people" else "",
        ]  # fmt: skip
        for i, c in enumerate(sample_data.form_cards(e.public_id), 1)
    ]
    return header, body


def _field(f: stages.Field) -> dict[str, str]:
    out = {"type": f.type, "min": f.min, "max": f.max, "step": f.step, "options": f.options}
    if f.scale:  # segment AD2S: shown only where set, as the other blanks
        out |= {"scale": "yes", "scale_labels": f.scale_labels}
    return out


def _detail(**settings: str) -> str:
    """Settings as ``name=value; …``, the empty ones left out."""
    return "; ".join(f"{k}={v}" for k, v in settings.items() if v)


def _process(e: Exercise) -> Table:
    """Each stage and what it holds, a row each: the form, each gate with
    its evaluators and results, each outcome with its values; the rules
    in words, as Process reads them. Under each gate, a ``field`` row per
    response field and a ``result`` row per result, their settings in
    ``detail`` as ``name=value; …`` (Codex: enough to rebuild the gate)."""
    plan = stages.plan_of(e.public_id)
    pools = sample_data.panel_pools(e.public_id)
    header = (
        "stage", "stage_name", "dates", "kind", "number", "label",
        "evaluators", "mode", "results", "values", "due", "rule", "detail",
    )  # fmt: skip
    body: list[list[str]] = []
    for st in plan.stages:
        head = [str(st.number), st.label, st.dates]
        if st.form:
            body.append(head + ["form", "", "Application form", "", "", "", "", "", "", ""])
        for c in st.columns:
            rule = stages.rule_text(plan, c)
            if isinstance(c, stages.Gate):
                sources, total = stages.sources_of(e.public_id, c)
                body.append(
                    head
                    + [
                        "gate",
                        str(c.number),
                        c.label,
                        stages.sources_summary(sources, total, pools),
                    ]
                    + [dict(stages.MODES).get(c.mode, c.mode), "; ".join(r.name for r in c.results)]
                    + [
                        "",
                        "",
                        rule,
                        _detail(
                            type=stages.gate_type(c),
                            confidential=_yes(c.confidential),
                            about=c.description,
                        ),
                    ]
                )
                for f in stages.fields_of(c):
                    body.append(
                        head
                        + ["field", str(c.number), f.label, "", "", "", "", "", ""]
                        + [
                            _detail(
                                key=f.key, **_field(f.field), required=_yes(f.required), help=f.help
                            )
                        ]
                    )
                for r in c.results:
                    body.append(
                        head
                        + ["result", str(c.number), r.name, "", "", "", "", "", ""]
                        + [
                            _detail(
                                key=r.key,
                                derive=r.derive,
                                source=r.source,
                                value=r.value,
                                at_least=str(r.at_least),
                                ignore_zero=_yes(r.ignore_zero),
                                # A result is a number, never a scale (AD2S).
                                **_field(replace(r.field, scale=False)),
                            )
                        ]
                    )
            else:
                body.append(
                    head
                    + ["outcome", str(c.number), c.label, "", "", ""]
                    + ["; ".join(c.values), c.due, rule]
                    + [_detail(weights=", ".join(f"{k} {w:g}" for k, w in c.weights))]
                )
    return header, body


def _panels(e: Exercise) -> Table:
    """Each panel's members, a row each."""
    return ("panel", "name", "email", "note"), [
        [p.name, m.name, m.email, m.note]
        for p in sample_data.panels_of(e.public_id)
        for m in p.members
    ]


def _emails(e: Exercise) -> Table:
    """Each template Process makes owed, and whether it is written."""
    return ("template", "when", "item", "audience", "written"), [
        [m.name, m.when, m.item, m.audience, _yes(m.ok)] for m in workflow.emails(e.public_id)
    ]


_SETUP = {"form": _form, "process": _process, "panels": _panels, "emails": _emails}


def setup(e: Exercise, parts: frozenset[str] = SETUP_PARTS) -> list[tuple[str, Table]]:
    """Extract setup's files, in Setup's order, the ones asked for."""
    return [(f"{k}.csv", fn(e)) for k, fn in _SETUP.items() if k in parts]


def setup_zip(e: Exercise, parts: frozenset[str] = SETUP_PARTS) -> bytes:
    return _zip(setup(e, parts))
