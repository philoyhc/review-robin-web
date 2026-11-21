"""The exercise's timeline as Home and the applicant's page draw it
(segment AD1I): each stage with its dates, its state against today, how
far today is through it, and its items in words every participant
reads (segment AD1S: each item names its audience, never *you*).
Nothing operator-only goes in (panels, rules, pairs, modes), so one shape
serves both pages. Today is the sample's until AD2.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from applydesk import stages, workflow
from applydesk.sample_data import Exercise

#: The sample's today (the model exercise is mid Stage 3, ruling 30).
TODAY = date(2026, 11, 17)


@dataclass(frozen=True)
class Item:
    """One line of a stage: *applicants*, *milestone*, *step*, *outcome*,
    *outcome-due* or *next* (the stage under way's first outcome due, AD1S),
    with its kicker (e.g. "Outcome · released 6 Nov") and its text."""

    kind: str
    kicker: str
    text: str


@dataclass(frozen=True)
class StageView:
    number: int
    name: str
    start: date | None
    end: date | None
    when: str  # "1 Sep – 30 Sep", or "Dates not set"
    state: str  # Closed, Done, Now, Next
    progress: float  # how far today is through it, 0 to 1
    items: tuple[Item, ...]


@dataclass(frozen=True)
class Timeline:
    stages: tuple[StageView, ...]
    start: date | None
    end: date | None
    today: date

    @property
    def now(self) -> StageView | None:
        return next((s for s in self.stages if s.state == "Now"), None)

    @property
    def today_text(self) -> str:
        """Where today falls, in words: the track's marker for a reader
        who cannot see it."""
        when = short(self.today)
        if self.now:
            return f"Today, {when}, is in {self.now.name}."
        dated = [s for s in self.stages if s.start and s.end]
        if not dated:
            return ""
        before = [s for s in dated if s.end and s.end < self.today]
        after = [s for s in dated if s.start and s.start > self.today]
        if before and after:
            return f"Today, {when}, is between {before[-1].name} and {after[0].name}."
        return (
            f"Today, {when}, is before {after[0].name}."
            if after
            else f"Today, {when}, is after {before[-1].name}."
        )


def short(d: date) -> str:
    return f"{d.day} {d.strftime('%b')}"


def _items(st: stages.Stage, e: Exercise) -> tuple[Item, ...]:
    out: list[Item] = []
    if st.form:
        out.append(Item("applicants", "Applicants", "Apply online with the application form."))
        if e.application_stage_ends != "Not set":
            close = f"Applications close {e.application_stage_ends}."
            out.append(Item("milestone", "Milestone", close))
    for c in st.columns:
        if isinstance(c, stages.Gate):
            out.append(Item("step", "Step", f"{c.label}." if c.label else "A step."))
        else:
            # Released to applicants: its values are theirs to read; one
            # released to anyone else reads as still to come (cold read).
            when, _, to = c.released.partition(" · ")
            if c.released and (not to or "applicants" in to.lower()):
                vs = list(c.values)
                values = ", ".join(vs[:-1]) + (" or " if len(vs) > 1 else "") + vs[-1] if vs else ""
                text = f"{c.label}: {values}." if values else f"{c.label}."
                out.append(Item("outcome", f"Outcome · released {when}", text))
            else:
                expected = e.expected_outcome  # the applicants' estimate, not Process's due
                kicker = "Outcome" + (f" · expected {expected}" if expected != "Not set" else "")
                out.append(Item("outcome-due", kicker, f"{c.label}."))
    return tuple(out)


def of(e: Exercise, today: date = TODAY, applicant: bool = False) -> Timeline:
    """The exercise's timeline from Process's stages (Semantics, AD1I);
    for an ``applicant``, only the stages *Shown to applicants* (ruling 46)."""
    plan = stages.plan_of(e.public_id)
    kept = [st for st in plan.stages if st.shown or not applicant]
    # A stage's declared start and end (segment AD1K): typed, no parsing.
    spans: list[tuple[date | None, date | None]] = [
        (st.when.start.date(), st.when.end.date()) if st.when and st.when.valid else (None, None)
        for st in kept
    ]
    known = [d for span in spans for d in span if d]
    start, end = (min(known), max(known)) if known else (None, None)
    views: list[StageView] = []
    for st, (s, f) in zip(kept, spans, strict=True):
        d = (f - s).days + 1 if s and f else 0
        if s and f and f < today:
            state = "Closed" if st.form else "Done"
        elif s and f and s <= today <= f:
            state = "Now"
        else:
            state = "Next"
        # Counted in days, a stage's last day in it.
        progress = ((today - s).days + 0.5) / d if state == "Now" and s and d else 0.0
        when = f"{short(s)} – {short(f)}" if s and f else "Dates not set"
        items = _items(st, e)
        if state == "Now":
            items = _next_in(items)
        views.append(StageView(st.number, st.label, s, f, when, state, progress, items))
    return Timeline(tuple(views), start, end, today)


def _next_in(items: tuple[Item, ...]) -> tuple[Item, ...]:
    """The stage under way's first outcome due, as its *Next:* item
    (segment AD1S): what comes next, and when it is expected."""
    due = next((i for i in items if i.kind == "outcome-due"), None)
    if due is None:
        return items
    nxt = Item("next", "Next: " + due.kicker, due.text)
    return tuple(nxt if i is due else i for i in items)


def next_step(e: Exercise, t: Timeline) -> str:
    """The line under the timeline, only where the today marker cannot
    say it (segment AD1S): a draft, or no stage under way. While a stage
    is under way the timeline itself carries *Now* and *Next*, so none."""
    if e.state == "Draft":
        return "A draft: the timeline is what participants will see once it is published."
    if t.now is not None:
        return ""
    ahead = next((s for s in t.stages if s.state == "Next"), None)
    if ahead is None:
        return "Every stage is done."
    return (
        f"Next: {ahead.name}, from {short(ahead.start)}." if ahead.start else f"Next: {ahead.name}."
    )


def running_gate(e: Exercise, t: Timeline) -> int | None:
    """The gate being worked in the stage under way, so the Now stage's
    operator part points to its page (AD-24, AD1S): the stage's first gate whose results are
    not in, else its last; none for a draft, or a stage holding no gate."""
    if e.state == "Draft" or t.now is None:
        return None
    st = next((s for s in stages.plan_of(e.public_id).stages if s.number == t.now.number), None)
    gates = [c for c in st.columns if isinstance(c, stages.Gate)] if st else []
    if not gates:
        return None
    working = (g for g in gates if workflow.gate_sent(e.public_id, g.key)[0] != "Results in")
    return next(working, gates[-1]).number
