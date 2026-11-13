"""Where an exercise stands, item by item (ruling 14, segment AD1D), on
sample data.

Each item goes live on its own: the application form, each gate, each
outcome, then the exercise's close. This module gives each its state
for the chrome's status row and the Workflow card. Until AD2 saves an
exercise, the states are fixed per sample exercise; nothing is saved."""

from __future__ import annotations

from dataclasses import dataclass

from applydesk import rounds, sample_data
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

#: The templates to applicants each sample exercise keeps on Emails:
#: (name, when it is sent, set up). Process says which steps send one.
_EMAILS: dict[str, tuple[tuple[str, str, bool], ...]] = {
    "wa9juxbc2t": (
        ("Receipt", "When an application is submitted", True),
        ("Reminder", "To drafts, 7 days before the form closes", True),
        ("Shortlist for interview", "When the outcome is released", True),
        ("Finalists", "When the outcome is released", True),
        ("Final results", "When the outcome is released", False),
    ),
    "k7mfr3pq8z": (
        ("Receipt", "When an application is submitted", True),
        ("Award decision", "When the outcome is released", False),
    ),
    "r6tm4kq9wz": (("Receipt", "When an application is submitted", True),),
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
    return "Open" if exercise.stage == "Application" else "Closed"


def gate_state(exercise_id: str, key: str) -> tuple[str, str]:
    """A gate's state and its line, e.g. ("Sent", "18 of 27 interviewed")."""
    return _GATES.get(exercise_id, {}).get(key, ("Not ready", ""))


def emails(exercise_id: str) -> tuple[tuple[str, str, bool], ...]:
    return _EMAILS.get(exercise_id, ())


def status_row(exercise: Exercise) -> tuple[Pill, ...]:
    """The chrome's status row: the exercise, then the form, gates,
    outcomes and emails, then applications received."""
    plan = rounds.plan_of(exercise.public_id)
    gates = [c for c in plan.columns if isinstance(c, rounds.Gate)]
    outcomes = [c for c in plan.columns if isinstance(c, rounds.Outcome)]
    apps = sample_data.applications_of(exercise.public_id)
    submitted = sum(a.state == "Submitted" for a in apps)
    form = form_state(exercise)
    done = sum(gate_state(exercise.public_id, g.key)[0] == "Results in" for g in gates)
    released = sum(bool(o.released) for o in outcomes)
    mail = emails(exercise.public_id)
    kept = sum(ok for _, _, ok in mail)
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
