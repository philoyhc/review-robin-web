"""Where an exercise stands, item by item (ruling 14, segment AD1D), on
sample data.

Each item goes live on its own: the application form, each gate, each
outcome, then the exercise's close. This module gives each its state
for the chrome's status row and the current stage (the Workflow card
was removed, author 2026-11-15: it can wait). Until AD2 saves an
exercise, the states are fixed per sample exercise; nothing is saved."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from applydesk import clock, sample_data, stages, tones
from applydesk.sample_data import Exercise

if TYPE_CHECKING:
    from applydesk.email_store import Template

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
    # Ruling 57's states (segment AD1M): the second reading's session
    # closed in Review Robin, its results waiting for *Pull final
    # results*; the moderation unlinked there, so detached here.
    "k7mfr3pq8z": {
        "g1": ("Sent", "3 of 5 reviewed"),
        "g2": ("Closed", "4 of 4 reviewed"),
        "g3": ("Detached", "2 of 4 reviewed when unlinked"),
    },
}


APPLICANTS, EVALUATORS = "Applicants", "Evaluators"


def email_anchor(item: str, audience: str) -> str:
    """The id of an email's card on Emails (ruling 65): ``em-<item>-<audience>``,
    naming the email rather than its place, so Process's *Template →* links
    reach it whatever comes before it."""
    return f"em-{item}-{audience}"


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
    def anchor(self) -> str:
        """Its card's id on Emails (ruling 65), as Process links to it."""
        return email_anchor(self.item, self.audience)

    @property
    def process_anchor(self) -> str:
        """The id Process opens for what ticks it (ruling 65): the form's
        card, or its outcome's."""
        return "form" if self.item in _FORM_MAIL else f"outcome-{self.item}"

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


#: The merge tags each kind of template may name (segment AD1L; ruling
#: 54): Review Robin's ``$tag`` syntax (``app/services/email_templates.py``),
#: filled when the email is sent (AD7). An evaluator's email has no
#: applicant tag, so a blind exercise's names no one.
EMAIL_FIELDS: dict[str, tuple[str, ...]] = {
    "receipt": (
        "applicant_name",
        "exercise_name",
        "application_id",
        "exercise_url",
        "help_contact",
    ),
    "reminder": ("applicant_name", "exercise_name", "closes", "exercise_url", "help_contact"),
    "outcome-applicants": (
        "applicant_name",
        "exercise_name",
        "stage_name",
        "outcome",
        "exercise_url",
        "help_contact",
    ),
    "outcome-evaluators": (
        "evaluator_name",
        "exercise_name",
        "stage_name",
        "outcome",
        "exercise_url",
        "help_contact",
    ),
}

#: Each kind's name, as the Emails side card lists a tag's kinds.
KIND_LABELS: dict[str, str] = {
    "receipt": "Receipt",
    "reminder": "Reminder",
    "outcome-applicants": "Outcome · Applicants",
    "outcome-evaluators": "Outcome · Evaluators",
}


#: What each tag stands for, shown beside it in *Insert field* and on the
#: Emails side card.
TAG_HELP: dict[str, str] = {
    "applicant_name": "the applicant's name",
    "evaluator_name": "the evaluator's name",
    "exercise_name": "the exercise's name",
    "application_id": "the application's ID",
    "closes": "when the form closes",
    "stage_name": "the stage's name",
    "outcome": "the outcome (to evaluators, its tally)",
    "exercise_url": "the link to the exercise's page",
    "help_contact": "the exercise's help contact",
}

#: Each kind's default subject and body, written with its own tags. As
#: Review Robin's, a default body drops a line whose tag comes out empty.
DEFAULT_TEMPLATES: dict[str, tuple[str, str]] = {
    "receipt": (
        "$exercise_name: application received",
        "Dear $applicant_name,\n\nThank you for applying to $exercise_name. Your application,"
        " $application_id, has been received.\n\nYou can see it, and how the exercise"
        " stands, at $exercise_url\n\nQuestions? Contact $help_contact.",
    ),
    "reminder": (
        "$exercise_name: your application is still a draft",
        "Dear $applicant_name,\n\nYour application to $exercise_name is saved as a draft and"
        " has not been submitted. Applications close on $closes.\n\nFinish and submit it"
        " at $exercise_url\n\nQuestions? Contact $help_contact.",
    ),
    "outcome-applicants": (
        "$exercise_name: $stage_name outcome",
        "Dear $applicant_name,\n\nThe outcome of $stage_name for your application to"
        " $exercise_name is: $outcome.\n\nMore at $exercise_url\n\nQuestions? Contact"
        " $help_contact.",
    ),
    "outcome-evaluators": (
        "$exercise_name: $stage_name outcome released",
        "Dear $evaluator_name,\n\nThe outcome of $stage_name in $exercise_name has been"
        " released: $outcome.\n\nThank you for your evaluations. More at"
        " $exercise_url\n\nQuestions? Contact $help_contact.",
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


def _stored_form(exercise_id: str) -> str | None:
    from applydesk import db, process_store

    session = db.new_session()
    try:
        return process_store.form_state(session, exercise_id)
    finally:
        session.close()


def form_state(exercise: Exercise) -> str:
    """The application form's state: Draft, Open or Closed; as stored on
    its stage once the timeline is (ruling 76), else the exercise's."""
    stored = _stored_form(exercise.public_id)
    if stored is not None:
        return {"draft": "Draft", "open": "Open", "closed": "Closed"}.get(stored, "Draft")
    if exercise.state == "Draft":
        return "Draft"
    return "Open" if exercise.form_open else "Closed"


def form_action(exercise: Exercise) -> tuple[str, str, str] | None:
    """The move Home's next step offers on the application form (ruling
    76): its label, the move it posts ("open" or "closed"), and why it is
    not offered yet ("" when it is). None with no form, or one closed."""
    if stages.plan_of(exercise.public_id).form_stage is None:
        return None
    state = form_state(exercise)
    if state == "Open":
        return ("Close form", "closed", "")
    if state == "Closed":
        return None
    from applydesk import locks  # locks reads this module's steps

    # Published as its stages are, not the sample's stored state: an
    # exercise made as a draft is published by publishing a stage (Codex
    # on #4161).
    if locks.exercise_status(exercise) == "Draft":
        return ("Open form", "open", "A draft's form opens once the exercise is published.")
    return ("Open form", "open", "")


#: A gate's states once sent (segment AD1M): *Closed* is a session
#: Review Robin has closed whose results are not yet pulled (ruling 57);
#: *Detached* one unlinked there, re-sent and pulled no more.
SENT_STATES = ("Sent", "Closed", "Detached", "Results in")


def gate_opened(state: str, line: str) -> bool:
    """Whether a gate's Review Robin session has opened (ruling 29): its
    results are in, its session closed or detached there (segment AD1M),
    or it is sent and under way. A sent gate whose session has not opened
    is still changed on Process, each change re-sent."""
    return state in ("Results in", "Closed", "Detached") or (state == "Sent" and bool(line))


def gate_sent(exercise_id: str, key: str) -> tuple[str, str]:
    """A gate's state as Review Robin reports it, one of ``SENT_STATES``
    with its line, else ("Not sent", ""). For the many callers that ask
    only whether a gate is sent, opened or complete: no readiness is
    worked out (the cold read on AD-33: deriving it for every row on
    Dossiers nearly doubled the page's time)."""
    known = _GATES.get(exercise_id, {}).get(key)
    if known and known[0] in SENT_STATES:
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


def progress_of(
    state: str, line: str, people: tuple[tuple[str, str, int], ...]
) -> tuple[tuple[str, str, int, int], ...]:
    """Each paired evaluator's progress as *Pull results* would read it
    from Review Robin (segment AD1M rung 5): (name, email, pairs, done).
    The sample keeps only the gate's line, "3 of 5 reviewed", so each
    evaluator is shown that share of their pairs; a closed session or
    results in, all of them; a gate not opened, none."""
    found = re.match(r"\s*(\d+) of (\d+)", line)
    if state in ("Results in", "Closed"):
        share = 1.0
    elif state in ("Sent", "Detached") and found and int(found.group(2)):
        share = int(found.group(1)) / int(found.group(2))
    else:
        share = 0.0
    return tuple((name, email, n, round(n * share)) for name, email, n in people)


def awaits_approval(exercise_id: str, gate: stages.Gate) -> bool:
    """Whether all a Suggested gate owes before it is *Ready* is its
    approvals, which the gate page makes in the tab until AD2 (segment
    AD1M: the card may then send it once the tab has approved them)."""
    return gate.mode == "suggested" and gate_readiness(exercise_id, gate).endswith(" to approve")


def sends(exercise_id: str, item: str, audience: str) -> bool:
    """Whether Process has the item ("receipt", "reminder" or an outcome's
    key) email the audience: as Process last recorded its ticks (segment
    AD2L), else the sample's."""
    saved = _stored_sends(exercise_id)
    if saved is not None:
        return (item, audience) in saved
    return (item, audience) in _SENDS.get(exercise_id, _DEFAULT_SENDS)


_TAG = re.compile(r"\$\$|\$(?:([A-Za-z_][A-Za-z0-9_]*)|\{([A-Za-z_][A-Za-z0-9_]*)\})")


def _stored_sends(exercise_id: str) -> frozenset[tuple[str, str]] | None:
    """The ticks Process last recorded (segment AD2L), else None."""
    from applydesk import email_store

    return email_store.stored_sends(exercise_id)


def _stored_templates(exercise_id: str) -> dict[tuple[str, str], Template]:
    """Each template an Emails card saved (segment AD2L), by (item,
    audience)."""
    from applydesk import email_store

    return dict(email_store.stored_templates(exercise_id))


def _blank_emails(exercise_id: str) -> bool:
    """An exercise none of whose templates is written until saved: an
    ordinary one (segment AD2G), not a sample."""
    return not sample_data.is_sample(exercise_id)


def process_revision(exercise_id: str) -> int:
    """How many times Process has saved the exercise (segment AD2C): an
    Emails page opened before the latest names outcomes the save may have
    retired, so its saves are refused (Codex on #4028)."""
    from applydesk import process_store

    return process_store.revision(exercise_id)


def foreign_tags(kind: str, text: str) -> tuple[str, ...]:
    """The merge tags a template's text names that its kind does not take
    (another kind's): refused on Save, as the card's script refuses them.
    An unknown tag stays as typed."""
    every = {f for fields in EMAIL_FIELDS.values() for f in fields}
    mine = set(EMAIL_FIELDS[kind])
    out: list[str] = []
    for m in _TAG.finditer(text):
        tag = m.group(1) or m.group(2)
        if tag and tag in every and tag not in mine and tag not in out:
            out.append(tag)
    return tuple(out)


def template_text(exercise_id: str, email: Email) -> tuple[str, str, int]:
    """A card's subject, body and version as the page opens it, from one
    read, so the text and the version a card carries always agree (cold
    read): as its card last saved them (segment AD2L); else a sample's
    written one its kind's default, an owed one (or a scratch exercise's)
    empty, at version 0."""
    own = _stored_templates(exercise_id).get((email.item, email.audience))
    if own is not None:
        return own.subject, own.body, own.version
    subject, body = DEFAULT_TEMPLATES[email.kind] if email.ok else ("", "")
    return subject, body, 0


def emails(exercise_id: str) -> tuple[Email, ...]:
    """Every template the exercise's Process makes owed, in timeline
    order: the form's, then each outcome's per audience (ruling 16). One
    is written once its card saved a subject and a body (segment AD2L);
    one never saved, as the sample has it (a scratch exercise's, owed)."""
    plan = stages.plan_of(exercise_id)
    stored = _stored_templates(exercise_id)
    ticked = _stored_sends(exercise_id)  # one read for every item (cold read)

    def ticks(item: str, audience: str) -> bool:
        if ticked is not None:
            return (item, audience) in ticked
        return (item, audience) in _SENDS.get(exercise_id, _DEFAULT_SENDS)

    sample: frozenset[tuple[str, str]] = (
        frozenset() if _blank_emails(exercise_id) else _WRITTEN.get(exercise_id, frozenset())
    )

    def is_written(pair: tuple[str, str]) -> bool:
        own = stored.get(pair)
        return own.written if own is not None else pair in sample

    out: list[Email] = []
    for st in plan.stages:
        if st.form:
            for item, (what, when) in _FORM_MAIL.items():
                if ticks(item, APPLICANTS):
                    name = f"{st.label}: {what} · {APPLICANTS}"
                    ok = is_written((item, APPLICANTS))
                    out.append(Email(name, when, ok, item, APPLICANTS))
        for c in st.columns:
            if isinstance(c, stages.Outcome):
                for who in (APPLICANTS, EVALUATORS):
                    if ticks(c.key, who):
                        name = f"{st.label}: Outcome · {who}"
                        when = f"When {c.label} is released"
                        out.append(Email(name, when, is_written((c.key, who)), c.key, who))
    return tuple(out)


def tag_rows(emails: tuple[Email, ...]) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    """The Emails side card's merge tags (author, 2026-11-19): each tag some
    email on the page can take, its description and the kinds that take
    it, in ``TAG_HELP``'s order."""
    kinds = [k for k in EMAIL_FIELDS if any(e.kind == k for e in emails)]
    return tuple(
        (tag, help, tuple(KIND_LABELS[k] for k in kinds if tag in EMAIL_FIELDS[k]))
        for tag, help in TAG_HELP.items()
        if any(tag in EMAIL_FIELDS[k] for k in kinds)
    )


def sample_values(exercise: Exercise, email: Email) -> dict[str, str]:
    """What Preview fills a template's fields with (segment AD1L): the
    exercise's first submitted application, the outcome's value in its row
    (to an applicant) or its tally (to an evaluator), and the evaluator
    the first member of the first panel evaluating at that stage's gates.
    ``exercise_url`` is the participant page's app path; the route adds
    the mount.
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
        "applicant_name": row.application.applicant if row else "",
        "exercise_name": exercise.name,
        "application_id": row.application.public_id if row else "",
        "closes": exercise.application_stage_ends,
        "stage_name": stage.label if stage else "",
        "outcome": (
            stages.counts(plan, outcome)
            if outcome and email.audience == EVALUATORS
            else value or "Pending"
        ),
        "evaluator_name": member.name if member else "",
        "exercise_url": f"/me/exercises/{exercise.public_id}",
        "help_contact": sample_data.help_contact(exercise),
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
        Pill("Exercise", ex_status, tones.tone(ex_status)),
        Pill("Form", form, tones.tone(form)),
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
    stage: int = 0  # the stage's number; 0 for the close (segment AD1T)


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
                    stage=r.number,
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
                        "" if state in SENT_STATES else "Send…",
                        state == "Results in",
                        link="evaluations" if state in ("Sent", "Closed", "Detached") else "",
                        stage=r.number,
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
                        stage=r.number,
                    )
                )
    # The close follows the last stage with something to decide: one
    # holding only the application gives no date for it.
    decided = [st for st in plan.stages if st.columns]
    last_when = decided[-1].when if decided else None
    last = clock.short(last_when.end) if last_when else ""
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


def stage_position(exercise: Exercise) -> tuple[int, int, str]:
    """Where the exercise stands on Process, as the Operator Lobby's Status
    prints it (segment AD1T): the number of the stage holding its next
    step, or the last once every step is done (as `current_stage`); how
    many stages; and that stage's name ("" when unnamed), e.g.
    (3, 3, "Interviews"). Found by number, as two stages may share a name."""
    plan = stages.plan_of(exercise.public_id)
    if not plan.stages:
        return (0, 0, "")
    now = next_step(steps(exercise))
    at = next((st for st in plan.stages if now and st.number == now.stage), plan.stages[-1])
    return (plan.stages.index(at) + 1, len(plan.stages), at.name)


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
