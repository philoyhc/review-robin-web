"""The exercise's timeline as Home and the applicant's page draw it
(segment AD1I): each stage with its dates, its state against today, its
share of the exercise's days, and its items in words an applicant reads.
Nothing operator-only goes in (panels, rules, pairs, modes), so one shape
serves both pages. Today is the sample's until AD2.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from applydesk import stages
from applydesk.sample_data import Exercise

#: The sample's today (the model exercise is mid Stage 3, ruling 30).
TODAY = date(2026, 11, 17)

_MONTHS = {
    m: i
    for i, m in enumerate(
        ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1
    )
}
_DAY = re.compile(r"\b(\d{1,2}) ([A-Z][a-z]{2})[a-z]*(?: (\d{4}))?\b")


@dataclass(frozen=True)
class Item:
    """One line of a stage: *you*, *milestone*, *step* or *outcome*, with
    its kicker (e.g. "Outcome · released 6 Nov") and its text."""

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
    share: float  # of the exercise's days, for the horizontal track
    progress: float  # how far today is through it, 0 to 1
    items: tuple[Item, ...]
    offset: float = 0.0  # where it starts along the track: the shares before it


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
    def today_at(self) -> float | None:
        """Where today falls along the track, in the stages' shares (as
        the segments are drawn): within the stage under way, at the start
        of the next one when between two, at either end outside them;
        None when no stage has dates."""
        dated = [s for s in self.stages if s.start and s.end]
        if not dated:
            return None
        for s in self.stages:
            if s.state == "Now":
                return s.offset + s.share * s.progress
        ahead = next((s for s in dated if s.start and self.today < s.start), None)
        return ahead.offset if ahead else 1.0

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


def _dates(text: str, after: date) -> tuple[date | None, date | None]:
    """A stage's "1 Sep – 30 Sep" or "1 Nov 2026 – 31 Jan 2027, 23:59"
    as days. A day without its year takes the first that puts it on or
    after ``after`` (the stage before it ends, or the exercise opens);
    one date is a one-day stage. Anything else, an impossible day or an
    end before its start among them, is no dates (cold read)."""
    found = _DAY.findall(text)
    if not found or any(m not in _MONTHS for _, m, _ in found):
        return None, None
    days: list[date] = []
    for day, month, y in found[:2]:
        floor = days[-1] if days else after
        try:
            d = date(int(y) if y else floor.year, _MONTHS[month], int(day))
            if not y and d < floor:
                d = date(d.year + 1, d.month, d.day)
        except ValueError:
            return None, None
        days.append(d)
    return (days[0], days[-1]) if days[-1] >= days[0] else (None, None)


def _opens(e: Exercise) -> date:
    """Where the stages' days begin to count: the exercise's opening, or
    the start of today's year."""
    start, _ = _dates(e.opens, date(TODAY.year, 1, 1))
    return start or date(TODAY.year, 1, 1)


def _items(st: stages.Stage, e: Exercise) -> tuple[Item, ...]:
    out: list[Item] = []
    if st.form:
        out.append(Item("you", "You", "Apply online with the application form."))
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


def of(e: Exercise, today: date = TODAY) -> Timeline:
    """The exercise's timeline from Process's stages (Semantics, AD1I)."""
    plan = stages.plan_of(e.public_id)
    floor = _opens(e)
    spans: list[tuple[date | None, date | None]] = []
    for st in plan.stages:
        s, f = _dates(st.dates, floor)
        spans.append((s, f))
        if f:
            floor = f
    known = [d for span in spans for d in span if d]
    start, end = (min(known), max(known)) if known else (None, None)
    # A dated stage's share is its days' part of the dated stages' share;
    # an undated one splits what is left equally (Semantics).
    n = len(spans)
    days = [(f - s).days + 1 if s and f else 0 for s, f in spans]
    dated = sum(1 for d in days if d)
    dated_share = dated / n if dated < n else 1.0
    views: list[StageView] = []
    offset = 0.0
    for st, (s, f), d in zip(plan.stages, spans, days, strict=True):
        if d:
            share = d / sum(days) * dated_share
        else:
            share = (1.0 - (dated_share if dated else 0.0)) / (n - dated)
        if s and f and f < today:
            state = "Closed" if st.form else "Done"
        elif s and f and s <= today <= f:
            state = "Now"
        else:
            state = "Next"
        # As the share counts days: a stage's last day is in it.
        progress = ((today - s).days + 0.5) / d if state == "Now" and s and d else 0.0
        when = f"{short(s)} – {short(f)}" if s and f else "Dates not set"
        views.append(
            StageView(
                st.number, st.label, s, f, when, state, share, progress, _items(st, e), offset
            )
        )
        offset += share
    return Timeline(tuple(views), start, end, today)


def next_step(e: Exercise, t: Timeline) -> str:
    """The line under the timeline, from where today falls (author,
    2026-11-17): the stage under way and what comes next."""
    if e.state == "Draft":
        return "A draft: the timeline is what applicants will see once it is published."
    now = t.now
    if now is None:
        ahead = next((s for s in t.stages if s.state == "Next"), None)
        if ahead is None:
            return "Every stage is done."
        return (
            f"Next: {ahead.name}, from {short(ahead.start)}."
            if ahead.start
            else f"Next: {ahead.name}."
        )
    due = next((i for i in now.items if i.kind == "outcome-due"), None)
    line = f"Now: {now.name}, until {short(now.end)}." if now.end else f"Now: {now.name}."
    if due:
        expected = due.kicker.partition(" · ")[2]
        line += f" Next: {due.text.rstrip('.')}" + (f", {expected}." if expected else ".")
    return line
