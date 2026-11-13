"""Where an exercise stands, item by item (ruling 14, segment AD1D), on
sample data.

Each item goes live on its own: the application form, each gate, each
outcome, then the exercise's close. This module gives each its state
for the chrome's status row and the Workflow card. Until AD2 saves an
exercise, the states are fixed per sample exercise; nothing is saved."""

from __future__ import annotations

from dataclasses import dataclass

from applydesk import sample_data, stages
from applydesk.sample_data import Exercise

#: Each sample gate's state and its line (ruling 14: Not ready → Ready →
#: Sent → Results in). A gate missing here is not ready.
_GATES: dict[str, dict[str, tuple[str, str]]] = {
    "wa9juxbc2t": {
        "g1": ("Results in", "92 of 92 reviewed"),
        "g2": ("Results in", "92 of 92 reviewed"),
        "g3": ("Sent", "18 of 27 interviewed"),
    },
    "k7mfr3pq8z": {"g1": ("Sent", "3 of 5 reviewed")},
}


@dataclass(frozen=True)
class Email:
    """A template to applicants, kept on Emails (ruling 14): its name, when
    it is sent, whether it is set up, and the outcome whose release sends
    it ("" for the receipt and reminders)."""

    name: str
    when: str
    ok: bool
    outcome: str = ""


_RELEASE = "When the outcome is released"

#: The templates each sample exercise keeps; Process says which steps
#: send one.
_EMAILS: dict[str, tuple[Email, ...]] = {
    "wa9juxbc2t": (
        Email("Receipt", "When an application is submitted", True),
        Email("Reminder", "To drafts, 7 days before the form closes", True),
        Email("Shortlist for interview", _RELEASE, True, "o1"),
        Email("Finalists", _RELEASE, True, "o2"),
        Email("Final results", _RELEASE, False, "o3"),
    ),
    "k7mfr3pq8z": (
        Email("Receipt", "When an application is submitted", True),
        Email("Award decision", _RELEASE, False, "o1"),
    ),
    "r6tm4kq9wz": (Email("Receipt", "When an application is submitted", True),),
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


def gate_state(exercise_id: str, key: str) -> tuple[str, str]:
    """A gate's state and its line, e.g. ("Sent", "18 of 27 interviewed")."""
    return _GATES.get(exercise_id, {}).get(key, ("Not ready", ""))


def emails(exercise_id: str) -> tuple[Email, ...]:
    return _EMAILS.get(exercise_id, ())


def outcome_email(exercise_id: str, outcome_key: str) -> Email | None:
    """The email an outcome's release sends, if Process says it sends one."""
    return next((e for e in emails(exercise_id) if e.outcome == outcome_key), None)


def status_row(exercise: Exercise) -> tuple[Pill, ...]:
    """The chrome's status row: the exercise, then the form, gates,
    outcomes and emails, then applications received."""
    plan = stages.plan_of(exercise.public_id)
    gates = [c for c in plan.columns if isinstance(c, stages.Gate)]
    outcomes = [c for c in plan.columns if isinstance(c, stages.Outcome)]
    apps = sample_data.applications_of(exercise.public_id)
    submitted = sum(a.state == "Submitted" for a in apps)
    form = form_state(exercise)
    done = sum(gate_state(exercise.public_id, g.key)[0] == "Results in" for g in gates)
    released = sum(bool(o.released) for o in outcomes)
    mail = emails(exercise.public_id)
    kept = sum(e.ok for e in mail)
    return (
        Pill("Exercise", exercise.state, "ok" if exercise.state == "Published" else "warn"),
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
        Pill("Applications", f"{submitted} submitted", "info" if submitted else "mute"),
    )


@dataclass(frozen=True)
class Step:
    """One step on the Workflow card: the form, a gate, an outcome or the
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
    """The exercise's timeline as the Workflow card steps through it: each
    stage's application form, gates and outcomes in their set order, then
    the close (ruling 15). An exercise whose applications came from
    elsewhere has no form step."""
    plan = stages.plan_of(exercise.public_id)
    apps = sample_data.applications_of(exercise.public_id)
    form = form_state(exercise)
    out: list[Step] = []
    for r in plan.stages:
        if r.application:  # the form, where its stage sits in the timeline
            out.append(
                Step(
                    r.label,
                    "",
                    "Application form",
                    form,
                    r.dates,
                    f"{len(apps)} received" if form != "Draft" else "Not open yet",
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
                email = outcome_email(exercise.public_id, c.key)
                blocked = (
                    "" if email is None or email.ok else "Not ready: no email for this outcome"
                )
                out.append(
                    Step(
                        r.label,
                        f"Outcome {c.number}",
                        c.label,
                        "Released" if released else "Pending",
                        c.released or f"Due {c.due}",
                        "" if released else "Decided on Applications",
                        "" if released else "Release…",
                        released,
                        blocked,
                    )
                )
    # The close follows the last stage with something to decide: one
    # holding only the application gives no date for it.
    decided = [st for st in plan.stages if st.columns]
    last = decided[-1].dates.split("–")[-1].strip() if decided else ""
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
    """The earliest step not yet done: the one the card marks."""
    return next((s for s in all_steps if not s.done), None)


def groups(all_steps: tuple[Step, ...]) -> tuple[tuple[str, tuple[Step, ...]], ...]:
    """The card's groups in order, each with its steps."""
    out: list[tuple[str, list[Step]]] = []
    for s in all_steps:
        if out and out[-1][0] == s.group:
            out[-1][1].append(s)
        else:
            out.append((s.group, [s]))
    return tuple((label, tuple(members)) for label, members in out)


def current_stage(exercise: Exercise) -> str:
    """The stage the exercise is in: the one holding its next step, or
    its last once every step is done (ruling 15)."""
    all_steps = steps(exercise)
    now = next_step(all_steps)
    if now is not None and now.group != "Close":
        return now.group
    plan = stages.plan_of(exercise.public_id)
    return plan.stages[-1].label if plan.stages else ""
