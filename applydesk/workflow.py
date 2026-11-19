"""Where an exercise stands, item by item (ruling 14, segment AD1D), on
sample data.

Each item goes live on its own: the application form, each gate, each
outcome, then the exercise's close. This module gives each its state
for the chrome's status row and the current stage (the Workflow card
was removed, author 2026-11-15: it can wait). Until AD2 saves an
exercise, the states are fixed per sample exercise; nothing is saved."""

from __future__ import annotations

from dataclasses import dataclass

from applydesk import sample_data, stages
from applydesk.sample_data import Exercise

#: Each sample gate sent to Review Robin, its state and its line (ruling
#: 14: Not ready → Ready → Sent → Results in). A gate missing here is not
#: sent: whether it is Ready is derived (``gate_readiness``, AD-33).
_GATES: dict[str, dict[str, tuple[str, str]]] = {
    "wa9juxbc2t": {
        "g1": ("Results in", "100 of 100 reviewed"),
        "g2": ("Results in", "100 of 100 reviewed"),
        # Mid Stage 3 (rulings 29, 30): the staff interview entered, its
        # pairs being approved on Evaluations, not yet sent: its state is
        # derived (gate_readiness, AD-33).
    },
    "k7mfr3pq8z": {"g1": ("Sent", "3 of 5 reviewed")},
}


APPLICANTS, EVALUATORS = "Applicants", "Evaluators"


@dataclass(frozen=True)
class Email:
    """A template owed (ruling 16): Process says which items email whom,
    and Emails lists one template per item and audience, named for its
    stage, e.g. "Review: Outcome · Applicants". ``item`` is "receipt",
    "reminder" or an outcome's key; ``ok`` whether it is written."""

    name: str
    when: str
    ok: bool
    item: str
    audience: str

    @property
    def greeting(self) -> str:
        """Whom its body addresses: "applicant" or "evaluator"."""
        return "applicant" if self.audience == APPLICANTS else "evaluator"

    @property
    def kind(self) -> str:
        """Its kind, which sets its fields and its default (segment AD1L):
        "receipt", "reminder", "outcome-applicants" or "outcome-evaluators"."""
        if self.item in _FORM_MAIL:
            return self.item
        return "outcome-applicants" if self.audience == APPLICANTS else "outcome-evaluators"


#: The merge fields each kind of template may name (segment AD1L): a
#: bracketed name, filled when the email is sent (AD7). An evaluator's
#: email has no applicant field, so a blind exercise's names no one.
EMAIL_FIELDS: dict[str, tuple[str, ...]] = {
    "receipt": ("Applicant name", "Exercise", "Application ID", "Link", "Help contact"),
    "reminder": ("Applicant name", "Exercise", "Closes", "Link", "Help contact"),
    "outcome-applicants": (
        "Applicant name",
        "Exercise",
        "Stage",
        "Outcome",
        "Link",
        "Help contact",
    ),
    "outcome-evaluators": (
        "Evaluator name",
        "Exercise",
        "Stage",
        "Outcome",
        "Link",
        "Help contact",
    ),
}

#: Each kind's default subject and body, written with its own fields.
DEFAULT_TEMPLATES: dict[str, tuple[str, str]] = {
    "receipt": (
        "[Exercise]: application received",
        "Dear [Applicant name],\n\nThank you for applying to [Exercise]. Your application,"
        " [Application ID], has been received.\n\nYou can see it, and how the exercise"
        " stands, at [Link].\n\nQuestions: [Help contact].",
    ),
    "reminder": (
        "[Exercise]: your application is still a draft",
        "Dear [Applicant name],\n\nYour application to [Exercise] is saved as a draft and"
        " has not been submitted. Applications close on [Closes].\n\nFinish and submit it"
        " at [Link].\n\nQuestions: [Help contact].",
    ),
    "outcome-applicants": (
        "[Exercise]: [Stage] outcome",
        "Dear [Applicant name],\n\nThe outcome of [Stage] for your application to"
        " [Exercise] is: [Outcome].\n\nMore at [Link].\n\nQuestions: [Help contact].",
    ),
    "outcome-evaluators": (
        "[Exercise]: [Stage] outcome released",
        "Dear [Evaluator name],\n\nThe outcome of [Stage] in [Exercise] has been released:"
        " [Outcome].\n\nThank you for your evaluations. More at [Link].\n\nQuestions:"
        " [Help contact].",
    ),
}


#: The form's emails, each to applicants: what it is, and when it goes.
_FORM_MAIL = {
    "receipt": ("Receipt", "When an application is submitted"),
    "reminder": ("Reminder", "To drafts, 7 days before the form closes"),
}

#: What each sample exercise's Process says emails whom: (item, audience).
_SENDS: dict[str, frozenset[tuple[str, str]]] = {
    "wa9juxbc2t": frozenset(
        {
            ("receipt", APPLICANTS),
            ("reminder", APPLICANTS),
            ("o1", APPLICANTS),
            ("o2", APPLICANTS),
            ("o2", EVALUATORS),
        }
    ),
    "k7mfr3pq8z": frozenset({("receipt", APPLICANTS), ("o1", APPLICANTS)}),
    "r6tm4kq9wz": frozenset({("receipt", APPLICANTS)}),
}

#: A form's receipt, for an exercise whose Process is not set up yet.
_DEFAULT_SENDS = frozenset({("receipt", APPLICANTS)})

#: The templates already written on Emails; the rest are owed.
_WRITTEN: dict[str, frozenset[tuple[str, str]]] = {
    "wa9juxbc2t": frozenset(
        {
            ("receipt", APPLICANTS),
            ("reminder", APPLICANTS),
            ("o1", APPLICANTS),
        }
    ),
    "k7mfr3pq8z": frozenset({("receipt", APPLICANTS)}),
    "r6tm4kq9wz": frozenset({("receipt", APPLICANTS)}),
}


@dataclass(frozen=True)
class Pill:
    """One entry in the status row: its label, its text, its tone (a
    chip class: ok, info, warn, mute)."""

    label: str
    text: str
    tone: str


def form_state(exercise: Exercise) -> str:
    """The application form's state: Draft, Open or Closed."""
    if exercise.state == "Draft":
        return "Draft"
    return "Open" if exercise.form_open else "Closed"


def gate_opened(state: str, line: str) -> bool:
    """Whether a gate's Review Robin session has opened (ruling 29): its
    results are in, or it is sent and under way. A sent gate whose session
    has not opened is still changed on Process, each change re-sent."""
    return state == "Results in" or (state == "Sent" and bool(line))


def gate_sent(exercise_id: str, key: str) -> tuple[str, str]:
    """A gate's state as Review Robin reports it: *Sent* or *Results in*
    with its line, else ("Not sent", ""). For the many callers that ask
    only whether a gate is sent, opened or complete: no readiness is
    worked out (the cold read on AD-33: deriving it for every row on
    Dossiers nearly doubled the page's time)."""
    known = _GATES.get(exercise_id, {}).get(key)
    if known and known[0] in ("Sent", "Results in"):
        return known
    return ("Not sent", "")


def gate_state(exercise_id: str, key: str) -> tuple[str, str]:
    """A gate's state and its line, e.g. ("Sent", "18 of 27 interviewed").
    A gate not yet sent is *Ready* only as ``gate_readiness`` derives it
    (AD-33): the sample records only what Review Robin would report."""
    sent = gate_sent(exercise_id, key)
    if sent[0] != "Not sent":
        return sent
    gate = next(
        (
            c
            for c in stages.plan_of(exercise_id).columns
            if isinstance(c, stages.Gate) and c.key == key
        ),
        None,
    )
    if gate is None:
        return ("Not ready", "")
    why = gate_readiness(exercise_id, gate)
    return ("Not ready", why) if why else ("Ready", "")


def gate_readiness(exercise_id: str, gate: stages.Gate) -> str:
    """Why a gate not yet sent is not ready, else "" (rulings 24, 27, 34),
    the first reason in this order: its stage published; a result; its
    evaluators; every submitted row's entry decided, at least one entered;
    every dossier entered assigned, none short; and, under *Suggested,
    then approved*, every dossier's evaluators approved. Approvals made on
    the gate page are the tab's until AD2, so the sample's Suggested pairs
    count as not yet approved."""
    plan = stages.plan_of(exercise_id)
    stage = next((s for s in plan.stages if gate in s.columns), None)
    if stage is None or stage.status != "Published":
        return "Its stage is not published"
    if not gate.results:
        return "No result yet"
    srcs, _ = stages.sources_of(exercise_id, gate)
    if not srcs:
        return "No evaluators yet"
    undecided = sum(
        1
        for r in plan.rows
        if r.application.state == "Submitted"
        and r.cells.get(gate.key, stages.Cell("")).value not in ("Entered", "Not entered")
    )
    if undecided:
        return f"{undecided} {'entry' if undecided == 1 else 'entries'} to decide"
    rows, _ = stages.assignments(exercise_id, gate)
    if not rows:
        return "No dossiers entered yet"
    if gate.mode == "assigned" and not any(a.evaluators for a in rows):
        return f"{len(rows)} {'dossier' if len(rows) == 1 else 'dossiers'} to assign"
    short = sum(1 for a in rows if a.short or a.unmet or not a.evaluators)
    if short:
        return f"{short} {'dossier' if short == 1 else 'dossiers'} short of evaluators"
    if gate.mode == "suggested":
        return f"{len(rows)} {'dossier' if len(rows) == 1 else 'dossiers'} to approve"
    return ""


def sends(exercise_id: str, item: str, audience: str) -> bool:
    """Whether Process has the item ("receipt", "reminder" or an outcome's
    key) email the audience."""
    return (item, audience) in _SENDS.get(exercise_id, _DEFAULT_SENDS)


def emails(exercise_id: str) -> tuple[Email, ...]:
    """Every template the exercise's Process makes owed, in timeline
    order: the form's, then each outcome's per audience (ruling 16)."""
    plan = stages.plan_of(exercise_id)
    written = _WRITTEN.get(exercise_id, frozenset())
    out: list[Email] = []
    for st in plan.stages:
        if st.form:
            for item, (what, when) in _FORM_MAIL.items():
                if sends(exercise_id, item, APPLICANTS):
                    name = f"{st.label}: {what} · {APPLICANTS}"
                    ok = (item, APPLICANTS) in written
                    out.append(Email(name, when, ok, item, APPLICANTS))
        for c in st.columns:
            if isinstance(c, stages.Outcome):
                for who in (APPLICANTS, EVALUATORS):
                    if sends(exercise_id, c.key, who):
                        name = f"{st.label}: Outcome · {who}"
                        when = f"When {c.label} is released"
                        out.append(Email(name, when, (c.key, who) in written, c.key, who))
    return tuple(out)


def sample_values(exercise: Exercise, email: Email) -> dict[str, str]:
    """What Preview fills a template's fields with (segment AD1L): the
    exercise's first submitted application, the outcome's value in its row
    (to an applicant) or its tally (to an evaluator), and the evaluator
    the first member of the first panel evaluating at that stage's gates.
    ``Link`` is the participant page's app path; the page adds the mount.
    Only the email's kind's fields."""
    plan = stages.plan_of(exercise.public_id)
    row = next((r for r in plan.rows if r.application.state == "Submitted"), None)
    stage = next((st for st in plan.stages if any(c.key == email.item for c in st.columns)), None)
    outcome = next((c for c in plan.columns if c.key == email.item), None)
    panels = {p.key: p for p in sample_data.panels_of(exercise.public_id)}
    refs = [
        s.ref
        for c in (stage.columns if stage else ())
        if isinstance(c, stages.Gate)
        for s in stages.sources_of(exercise.public_id, c)[0]
        if s.kind == "panel" and s.ref in panels and panels[s.ref].members
    ]
    member = panels[refs[0]].members[0] if refs else None
    value = row.cells[email.item].value if row and email.item in row.cells else ""
    every = {
        "Applicant name": row.application.applicant if row else "",
        "Exercise": exercise.name,
        "Application ID": row.application.public_id if row else "",
        "Closes": exercise.application_stage_ends,
        "Stage": stage.label if stage else "",
        "Outcome": (
            stages.counts(plan, outcome)
            if outcome and email.audience == EVALUATORS
            else value or "Pending"
        ),
        "Evaluator name": member.name if member else "",
        "Link": f"/me/exercises/{exercise.public_id}",
        "Help contact": sample_data.help_contact(exercise),
    }
    return {f: every[f] for f in EMAIL_FIELDS[email.kind]}


def outcome_emails(exercise_id: str, outcome_key: str) -> tuple[Email, ...]:
    """The emails an outcome's release sends, as Process sets them."""
    return tuple(e for e in emails(exercise_id) if e.item == outcome_key)


@dataclass(frozen=True)
class Counts:
    """An exercise's applications by state, the one count every page uses
    (AD-41): the lobby, Home's form line and the status row."""

    submitted: int
    drafts: int
    withdrawn: int


def closed_by(exercise_id: str) -> dict[str, str]:
    """Rulings 45 and 49: a submitted application may be withdrawn, or
    returned to draft by the operator, until a gate holding its dossier
    completes (*Results in*), as the gate itself may go back to draft until
    then (ruling 48). By application: the first such gate's label, for
    every submitted application it has closed."""
    plan = stages.plan_of(exercise_id)
    completed = [
        c
        for c in plan.columns
        if isinstance(c, stages.Gate) and gate_sent(exercise_id, c.key)[0] == "Results in"
    ]
    out: dict[str, str] = {}
    for r in plan.rows:
        if r.application.state != "Submitted":
            continue
        for c in completed:
            cell = r.cells.get(c.key)
            if cell and cell.value == "Entered":
                out[r.application.public_id] = c.label or f"Gate {c.number}"
                break
    return out


def withdrawal_closed_by(exercise_id: str, public_id: str) -> str:
    """The gate that closed this application's withdrawal, else ""."""
    return closed_by(exercise_id).get(public_id, "")


def counts_of(exercise_id: str) -> Counts:
    apps = sample_data.applications_of(exercise_id)
    return Counts(
        sum(a.state == "Submitted" for a in apps),
        sum(a.state == "Draft" for a in apps),
        sum(a.state == "Withdrawn" for a in apps),
    )


def plural(n: int, one: str, many: str = "") -> str:
    """ "1 draft", "3 drafts": the one pluralizer (AD-41)."""
    return f"{n:,} {one if n == 1 else (many or one + 's')}"


def status_row(exercise: Exercise) -> tuple[Pill, ...]:
    """The chrome's status row: the exercise, then the form, gates,
    outcomes and emails, then applications received."""
    plan = stages.plan_of(exercise.public_id)
    gates = [c for c in plan.columns if isinstance(c, stages.Gate)]
    outcomes = [c for c in plan.columns if isinstance(c, stages.Outcome)]
    counted = counts_of(exercise.public_id)
    submitted, drafts = counted.submitted, counted.drafts
    # The exercise's status follows its stages (segment AD1K); imported
    # here, as locks reads this module.
    from applydesk import locks

    ex_status = locks.exercise_status(exercise)
    form = form_state(exercise)
    done = sum(gate_sent(exercise.public_id, g.key)[0] == "Results in" for g in gates)
    released = sum(bool(o.released) for o in outcomes)
    mail = emails(exercise.public_id)
    kept = sum(e.ok for e in mail)
    return (
        # As each stage's chip on Process and Home (locks.STATUS_CHIP).
        Pill(
            "Exercise", ex_status, {"Published": "info", "Completed": "ok"}.get(ex_status, "warn")
        ),
        Pill("Form", form, "warn" if form == "Draft" else "info"),
        Pill(
            "Gates",
            f"{done} of {len(gates)} done" if gates else "none",
            "info" if gates else "warn",
        ),
        Pill(
            "Outcomes",
            f"{released} of {len(outcomes)} released" if outcomes else "none",
            "info" if outcomes else "warn",
        ),
        Pill(
            "Emails",
            f"{kept} of {len(mail)}" if mail else "none",
            "info" if mail and kept == len(mail) else "warn",
        ),
        # With the drafts, as Home's Counts card had them (segment AD1I).
        Pill(
            "Applications",
            f"{submitted:,} submitted" + (f" · {plural(drafts, 'draft')}" if drafts else ""),
            "info" if submitted else "mute",
        ),
    )


@dataclass(frozen=True)
class Step:
    """One step of the timeline: the form, a gate, an outcome or the
    close, in timeline order (ruling 14)."""

    group: str  # the stage it sits in, by its label, or "Close"
    kind: str  # "Gate 1", "Outcome 2", "" for the form and the close
    title: str
    state: str
    when: str
    line: str  # progress, or what it waits on
    action: str  # what the step's button would do; inert until AD2
    done: bool
    blocked: str = ""  # why it is not ready, when it is not
    link: str = ""  # a page to open instead of an action, e.g. "evaluations"


def steps(exercise: Exercise) -> tuple[Step, ...]:
    """The exercise's timeline, step by step: each
    stage's application form, gates and outcomes in their set order, then
    the close (ruling 15). An exercise whose applications came from
    elsewhere has no form step."""
    plan = stages.plan_of(exercise.public_id)
    form = form_state(exercise)
    out: list[Step] = []
    for r in plan.stages:
        if r.form:  # the form, where its stage sits in the timeline
            out.append(
                Step(
                    r.label,
                    "",
                    "Application form",
                    form,
                    r.dates,
                    f"{counts_of(exercise.public_id).submitted:,} submitted"
                    if form != "Draft"
                    else "Not open yet",
                    {"Draft": "Open form…", "Open": "Close form…"}.get(form, ""),
                    form == "Closed",
                )
            )
        for c in r.columns:
            if isinstance(c, stages.Gate):
                state, line = gate_state(exercise.public_id, c.key)
                out.append(
                    Step(
                        r.label,
                        f"Gate {c.number}",
                        c.label,
                        state,
                        r.dates,
                        line,
                        "" if state in ("Sent", "Results in") else "Send…",
                        state == "Results in",
                        link="evaluations" if state == "Sent" else "",
                    )
                )
            else:
                released = bool(c.released)
                # An owed email holds back a release still to come (ruling 16).
                owed = [
                    e.audience.lower()
                    for e in outcome_emails(exercise.public_id, c.key)
                    if not e.ok and not released
                ]
                blocked = (
                    f"Not ready: its {'email' if len(owed) == 1 else 'emails'} to"
                    f" {' and '.join(owed)} {'is' if len(owed) == 1 else 'are'} not written"
                    if owed
                    else ""
                )
                out.append(
                    Step(
                        r.label,
                        f"Outcome {c.number}",
                        c.label,
                        "Released" if released else "Pending",
                        c.released or f"Due {c.due}",
                        "" if released else "Decided on Dossiers",
                        "" if released else "Release…",
                        released,
                        blocked,
                    )
                )
    # The close follows the last stage with something to decide: one
    # holding only the application gives no date for it.
    decided = [st for st in plan.stages if st.columns]
    last_when = decided[-1].when if decided else None
    last = stages.short_day(last_when.end) if last_when else ""
    out.append(
        Step(
            "Close",
            "",
            "Close and archive",
            exercise.state if exercise.state in ("Closed", "Archived") else "—",
            f"After {last}" if last else "After the last outcome",
            "Extract data first",
            "Close…",
            exercise.state == "Archived",
        )
    )
    return tuple(out)


def next_step(all_steps: tuple[Step, ...]) -> Step | None:
    """The earliest step not yet done: it names the current stage."""
    return next((s for s in all_steps if not s.done), None)


def current_stage(exercise: Exercise) -> str:
    """The stage the exercise is in: the one holding its next step, or
    its last once every step is done (ruling 15)."""
    all_steps = steps(exercise)
    now = next_step(all_steps)
    if now is not None and now.group != "Close":
        return now.group
    plan = stages.plan_of(exercise.public_id)
    return plan.stages[-1].label if plan.stages else ""


def panels_sent(exercise_id: str) -> dict[str, tuple[str, ...]]:
    """The opened gates each panel evaluates, by panel key (AD1F
    Semantics, ruling 29): a gate whose Review Robin session has opened
    keeps the roster it opened with, which the Panels page says, e.g.
    {"panel-a": ("Gate 1",)}. Every panel source counts (AD-49)."""
    sent: dict[str, list[str]] = {}
    for c in stages.plan_of(exercise_id).columns:
        if isinstance(c, stages.Gate) and gate_opened(*gate_sent(exercise_id, c.key)):
            for key in stages.gate_panels(exercise_id, c):
                sent.setdefault(key, []).append(f"Gate {c.number}")
    return {k: tuple(v) for k, v in sent.items()}
