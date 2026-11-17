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
_DAY = re.compile(r"(\d{1,2}) ([A-Z][a-z]{2})(?: (\d{4}))?")


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


@dataclass(frozen=True)
class Timeline:
    stages: tuple[StageView, ...]
    start: date | None
    end: date | None
    today: date

    @property
    def now(self) -> StageView | None:
        return next((s for s in self.stages if s.state == "Now"), None)

    def at(self, d: date) -> float:
        """Where a day falls along the whole track, 0 to 1."""
        if not self.start or not self.end or self.end <= self.start:
            return 0.0
        return min(1.0, max(0.0, (d - self.start).days / (self.end - self.start).days))


def short(d: date) -> str:
    return f"{d.day} {d.strftime('%b')}"


def _dates(text: str, year: int) -> tuple[date | None, date | None]:
    """A stage's "1 Sep – 30 Sep" or "1 Nov 2026 – 31 Jan 2027, 23:59"
    as days: a year left out is the one before it, rolling over when the
    end comes before the start; anything else is no dates."""
    found = _DAY.findall(text)
    if not found or any(m not in _MONTHS for _, m, _ in found):
        return None, None
    days: list[date] = []
    for day, month, y in found[:2]:
        year = int(y) if y else year
        d = date(year, _MONTHS[month], int(day))
        if days and d < days[0] and not y:
            d = date(year + 1, d.month, d.day)
        days.append(d)
    return days[0], days[-1]


def _year(e: Exercise) -> int:
    m = re.search(r"\d{4}", e.opens)
    return int(m.group()) if m else TODAY.year


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
            if c.released:
                when = c.released.split(" · ")[0]
                vs = list(c.values)
                values = ", ".join(vs[:-1]) + (" or " if len(vs) > 1 else "") + vs[-1] if vs else ""
                text = f"{c.label}: {values}." if values else f"{c.label}."
                out.append(Item("outcome", f"Outcome · released {when}", text))
            else:
                expected = c.due or e.expected_outcome
                kicker = "Outcome" + (f" · expected {expected}" if expected != "Not set" else "")
                out.append(Item("outcome-due", kicker, f"{c.label}."))
    return tuple(out)


def of(e: Exercise, today: date = TODAY) -> Timeline:
    """The exercise's timeline from Process's stages (Semantics, AD1I)."""
    plan = stages.plan_of(e.public_id)
    year = _year(e)
    spans: list[tuple[date | None, date | None]] = []
    for st in plan.stages:
        s, f = _dates(st.dates, year)
        spans.append((s, f))
        if f:
            year = f.year
    known = [d for span in spans for d in span if d]
    start, end = (min(known), max(known)) if known else (None, None)
    # A dated stage's share is its days' part of the dated stages' share;
    # an undated one splits what is left equally (Semantics).
    n = len(spans)
    days = [(f - s).days + 1 if s and f else 0 for s, f in spans]
    dated = sum(1 for d in days if d)
    dated_share = dated / n if dated < n else 1.0
    views: list[StageView] = []
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
        progress = ((today - s).days / max(1, (f - s).days)) if state == "Now" and s and f else 0.0
        when = f"{short(s)} – {short(f)}" if s and f else "Dates not set"
        views.append(
            StageView(st.number, st.label, s, f, when, state, share, progress, _items(st, e))
        )
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
