"""Example data for RA Leave's placeholder screens (segment 1C item 1),
built on the Rosters sample (`sample_data`): the same Unit, RAs, slots and
terms. Every page that shows it is labeled "Sample data"; it lives here
alone so that 1C items 2–5 delete it in one place
(`residentialapps/guide/segment_1C_ra_leave.md`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from residentialapps.residentialops import sample_data

TODAY = sample_data.TODAY

# Leave policy (author, 2026-10-28; `residentialapps/guide/todo_master.md`,
# leave policy): the leave types that need an application, each with its
# own entitlement rule; blackout periods; appeals beyond entitlement;
# cover; approvals. These are the sample's choices.


@dataclass(frozen=True)
class LeaveType:
    name: str
    abbrev: str
    accrual: str  # one of ACCRUALS
    amount: int  # days per term, or per month served
    cap: int  # the most an RA may have in a cap period
    cap_per: str  # "year" or "term"


ACCRUALS = ("Per term", "Per month served")
CAP_PERIODS = ("year", "term")
LEAVE_TYPES = (
    LeaveType("Personal leave", "PL", "Per term", 5, 12, "year"),
    LeaveType("Official leave", "OL", "Per month served", 1, 8, "year"),
)


@dataclass(frozen=True)
class Blackout:
    """A run of weeks in a term when leave is refused, or only open to
    appeal; counted by week so it carries to the next year. Week 1 starts on
    the Sunday on or before the term's first day; weeks run Sunday to
    Saturday, clipped to the term's own dates (author, 2026-10-28)."""

    term: int
    week_from: int
    week_to: int
    label: str
    effect: str  # one of BLACKOUT_EFFECTS


BLACKOUT_EFFECTS = ("Refused", "Appeal only")
BLACKOUTS = (
    Blackout(1, 1, 2, "Move-in and orientation", "Refused"),
    Blackout(1, 16, 17, "Examinations", "Appeal only"),
    Blackout(2, 1, 1, "Re-opening", "Refused"),
)


def week_dates(blackout: Blackout, year: str = "AY2026-2027") -> tuple[date, date] | None:
    """The blackout's dates in a year's term: its Sunday-to-Saturday weeks,
    clipped to the term, so a blackout never reaches into the next or the
    last term; None when no day of it falls in the term (or its weeks run
    backwards), which the wired form refuses."""
    term = next(t for t in sample_data.TERMS if t.year == year and t.number == blackout.term)
    sunday = date.fromordinal(term.start.toordinal() - (term.start.isoweekday() % 7))
    first = date.fromordinal(sunday.toordinal() + 7 * (blackout.week_from - 1))
    last = date.fromordinal(sunday.toordinal() + 7 * blackout.week_to - 1)
    first, last = max(first, term.start), min(last, term.end)
    return (first, last) if first <= last else None


APPEAL_MODES = ("Open", "By invitation", "Off")
COVER_MODES = ("Named only", "Named and confirmed")
COVER_POOLS = ("Any RA", "Same Precinct", "Same Wing")
POLICY = {
    # Appeals beyond entitlement (author, 2026-10-28, refined 2026-10-29):
    # open to every RA, by invitation once the Master or the Master's admin
    # delegate agrees in principle, or off.
    "appeals": "Open",  # one of APPEAL_MODES
    # Who may open an appeal by invitation (author, 2026-10-29), chosen as
    # approvers are: appointments on the RA's slot, Unit-level
    # appointments, or named staff.
    "inviters": "unit",  # "slot", "unit" or "named"
    "inviter_types": ("Master", "Admin"),
    "inviter_names": (),
    "appeal_terms": "Granted on the understanding that you take on extra duties, as agreed with your RF.",
    "cover_required": True,
    "cover_mode": "Named and confirmed",
    "cover_pool": "Same Precinct",
    # Approvals (author, 2026-10-28): first by one or more of the
    # appointments on the RA's slot, whichever approves first, or none;
    # final by one or more Unit-level appointments, or by named staff.
    "first": "slot",  # or "none"
    "first_types": ("RF",),
    "final": "unit",  # or "named"
    "final_types": ("Admin",),
    "final_names": (),
}
PERIOD_LABEL = "AY2026-2027"

APPEAL_DECIDER = "Sam Lee"  # the Master


def _appointments(names) -> tuple[tuple[str, str], ...]:
    staff = {p.name: p for p in sample_data.STAFF}
    return sample_data.appointments(tuple(staff[n] for n in dict.fromkeys(names)))


def slot_appointments() -> tuple[tuple[str, str], ...]:
    """(appointment, abbreviation) for each staff appointment found in the
    slots' Staff cells, in the order first met."""
    return _appointments(n for s in sample_data.SLOTS for n in s.staff)


def unit_appointments() -> tuple[tuple[str, str], ...]:
    """The staff appointments that no slot's Staff cell holds: the Unit's
    own. By appointment, not person, so an RF between slots stays a slot
    appointment."""
    on_slots = set(slot_appointments())
    return tuple(a for a in sample_data.STAFF_APPOINTMENTS if a not in on_slots)


def final_approvers() -> tuple[str, ...]:
    """Who may give final approval, whichever does first."""
    if POLICY["final"] == "named":
        return tuple(POLICY["final_names"])
    return tuple(p.name for p in sample_data.STAFF if p.abbrev in POLICY["final_types"])


def first_label() -> str:
    return " or ".join(POLICY["first_types"]) if POLICY["first"] == "slot" else "none"


def final_label() -> str:
    return " or ".join(POLICY["final_types"] if POLICY["final"] == "unit" else POLICY["final_names"])


def final_decider() -> str:
    """The sample's final approver on a decided application: the first who
    may give it."""
    return next(iter(final_approvers()), "the final approver")

# Cover is tracked beside the workflow, not as a stage of it: an
# application whose cover is unconfirmed waits at first approval (spec §11).
STAGES = (
    "Pending first approval",
    "Pending final approval",
    "Appeal to the Master",
    "Approved",
    "Rejected",
    "Withdrawn",
)
OPEN_STAGES = STAGES[:3]
OVERDUE_DAYS = 3  # a pending application older than this is flagged


@dataclass(frozen=True)
class Application:
    id: str
    ra: str
    leave_type: str
    start: date
    end: date
    cover: str
    cover_status: str  # Confirmed, Awaiting, Declined
    stage: str
    submitted: date
    remarks: str = ""

    @property
    def appeal(self) -> bool:
        """An extra-leave appeal: decided by the Master, and kept apart from
        normal entitlement once granted (spec §7.5)."""
        return self.stage == "Appeal to the Master" or self.id in GRANTED_APPEALS

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    @property
    def slot(self) -> sample_data.Slot:
        return next(s for s in sample_data.SLOTS if self.ra in s.ras)

    @property
    def precinct(self) -> str:
        return self.slot.precinct

    @property
    def age(self) -> int:
        return (TODAY - self.submitted).days

    @property
    def overdue(self) -> bool:
        return self.stage in OPEN_STAGES and self.age > OVERDUE_DAYS

    @property
    def dates(self) -> str:
        if self.start == self.end:
            return short_date(self.start)
        return f"{short_date(self.start)} – {short_date(self.end)}"


def short_date(day: date) -> str:
    """"28 Oct": the day without a leading zero, built by hand because
    `%-d` is glibc's and Windows' strftime refuses it."""
    return f"{day.day} {day.strftime('%b')}"


def _d(text: str) -> date:
    return date.fromisoformat(text)


APPLICATIONS: tuple[Application, ...] = tuple(
    Application(f"L-{n:04d}", *row)
    for n, row in enumerate(
        (
            ("Chloe Lim", "Personal leave", _d("2026-11-06"), _d("2026-11-08"), "Ethan Wong", "Confirmed", "Pending first approval", _d("2026-10-27")),
            ("Isaac Goh", "Personal leave", _d("2026-11-12"), _d("2026-11-14"), "Kai Ng", "Awaiting", "Pending first approval", _d("2026-10-26")),
            ("Bella Koh", "Personal leave", _d("2026-10-30"), _d("2026-11-01"), "Cheng Hao Lin", "Confirmed", "Pending final approval", _d("2026-10-23")),
            ("Leon Chia", "Personal leave", _d("2026-12-01"), _d("2026-12-05"), "Mira Sato", "Confirmed", "Pending first approval", _d("2026-10-21")),
            ("Gwen Ho", "Personal leave", _d("2026-11-20"), _d("2026-11-23"), "Elise Tan", "Confirmed", "Appeal to the Master", _d("2026-10-25"),
             "Balance exhausted; family wedding overseas."),
            ("Maya Seah", "Personal leave", _d("2026-10-27"), _d("2026-10-29"), "Lucas Teo", "Confirmed", "Approved", _d("2026-10-12")),
            ("Olivia Ng", "Personal leave", _d("2026-10-28"), _d("2026-10-30"), "Pranav Iyer", "Confirmed", "Approved", _d("2026-10-14")),
            ("Pranav Iyer", "Personal leave", _d("2026-10-29"), _d("2026-10-31"), "Qi Xuan Lim", "Confirmed", "Approved", _d("2026-10-15")),
            ("Hana Ito", "Official leave", _d("2026-11-02"), _d("2026-11-03"), "Chloe Lim", "Declined", "Pending first approval", _d("2026-10-24")),
            ("Faris Iskandar", "Personal leave", _d("2026-10-10"), _d("2026-10-11"), "Elise Tan", "Confirmed", "Rejected", _d("2026-10-02")),
            ("Ethan Wong", "Personal leave", _d("2026-10-17"), _d("2026-10-18"), "Hana Ito", "Confirmed", "Withdrawn", _d("2026-10-05")),
            ("Gwen Ho", "Personal leave", _d("2026-08-17"), _d("2026-08-19"), "Elise Tan", "Confirmed", "Approved", _d("2026-08-05")),
            ("Gwen Ho", "Personal leave", _d("2026-09-21"), _d("2026-09-22"), "Faris Iskandar", "Confirmed", "Approved", _d("2026-09-10")),
            # Chloe Lim, the RA pages' sample viewer, is asked to cover one
            # and has agreed to cover another.
            ("Ethan Wong", "Personal leave", _d("2026-12-04"), _d("2026-12-06"), "Chloe Lim", "Awaiting", "Pending first approval", _d("2026-10-27")),
            ("Hana Ito", "Personal leave", _d("2026-12-14"), _d("2026-12-15"), "Chloe Lim", "Confirmed", "Approved", _d("2026-10-20")),
        ),
        start=101,
    )
)


GRANTED_APPEALS: frozenset[str] = frozenset()  # none granted yet in the sample


def by_id(application_id: str) -> Application | None:
    return next((a for a in APPLICATIONS if a.id == application_id), None)


def stages(open_only: bool = False) -> tuple[str, ...]:
    """The stages the policy uses: no appeal stage while appeals are off,
    no first-approval stage when none is needed."""
    # Appeals off removes the route for new applications; an appeal already
    # made keeps its stage and is decided (author, 2026-10-28).
    open_appeal = any(a.stage == "Appeal to the Master" for a in APPLICATIONS)
    skip = {"Appeal to the Master"} if not appeals_on() and not open_appeal else set()
    if POLICY["first"] == "none":
        skip.add("Pending first approval")
    return tuple(s for s in (OPEN_STAGES if open_only else STAGES) if s not in skip)


def pending_by_stage() -> tuple[tuple[str, int], ...]:
    return tuple((stage, sum(1 for a in APPLICATIONS if a.stage == stage)) for stage in stages(open_only=True))


def cover_unconfirmed() -> tuple[Application, ...]:
    """Open applications whose cover has not confirmed (spec §25,
    outstanding cover confirmations)."""
    return tuple(
        a for a in APPLICATIONS if a.stage in OPEN_STAGES and a.cover_status != "Confirmed" and confirmation_needed(a)
    )


def away_this_week() -> tuple[Application, ...]:
    """Approved leave overlapping the seven days from TODAY."""
    end = date.fromordinal(TODAY.toordinal() + 6)
    return tuple(a for a in APPLICATIONS if a.stage == "Approved" and a.start <= end and a.end >= TODAY)


def clashes() -> tuple[tuple[str, tuple[str, str]], ...]:
    """Each pair of RAs in one Precinct away on approved or pending leave on
    overlapping days, one row per pair."""
    live = [a for a in APPLICATIONS if a.stage in ("Approved", *OPEN_STAGES)]
    return tuple(
        (a.precinct, (a.ra, b.ra))
        for a in live for b in live
        if a.id < b.id and a.ra != b.ra and a.precinct == b.precinct and a.start <= b.end and b.start <= a.end
    )


def cover_while_away() -> tuple[Application, ...]:
    """Applications whose cover is away themselves on overlapping dates."""
    live = [a for a in APPLICATIONS if a.stage in ("Approved", *OPEN_STAGES)]
    return tuple(
        a for a in live
        if any(b.ra == a.cover and b.start <= a.end and a.start <= b.end for b in live)
    )


# Adjustments for TERM: (RA, leave type) -> (adjustment, reason); a wired
# store keys them by term too.
ADJUSTMENTS = {
    ("Leon Chia", "Personal leave"): (2, "Correction: days charged twice for one application, 2026-08-03"),
}


def term_labels(year: str = PERIOD_LABEL) -> tuple[str, ...]:
    return tuple(f"Term {t.number}" for t in sample_data.TERMS if t.year == year)


TERM = sample_data.CURRENT_TERM  # the term whose days the pages show


def months_served(start: date, term: sample_data.Term = TERM) -> int:
    """Whole months served in a term, to TODAY or the term's end: from the
    later of the appointment's first day and the term's."""
    start, end = max(start, term.start), min(TODAY, term.end)
    if end < start:
        return 0
    months = (end.year * 12 + end.month) - (start.year * 12 + start.month)
    return months - (1 if end.day < start.day else 0)


def earned(leave_type: LeaveType, appointment_start: date, term: sample_data.Term) -> int:
    """A term's days before any cap: the per-term amount, or what the months
    served in it have earned."""
    if leave_type.accrual == "Per term":
        return leave_type.amount if appointment_start <= term.end else 0
    return leave_type.amount * months_served(appointment_start, term)


def entitlement(leave_type: LeaveType, appointment_start: date, term: sample_data.Term = TERM) -> int:
    """A term's entitlement so far. Leave days go with their term and are
    available only within it (author, 2026-10-28): nothing carries to the
    next. A cap per term holds the term's days; a cap per year holds them to
    what the year's earlier terms have not already taken. Adjustments sit
    outside the cap: they are the admin's deliberate exceptions, each with
    its reason."""
    days = earned(leave_type, appointment_start, term)
    if leave_type.cap_per == "term":
        return min(days, leave_type.cap)
    before = sum(
        min(earned(leave_type, appointment_start, t), leave_type.cap)
        for t in sample_data.TERMS if t.year == term.year and t.number < term.number
    )
    return max(0, min(days, leave_type.cap - before))


def days_in_term(application: Application, term: sample_data.Term = TERM) -> int:
    """The application's days falling in the term: leave across a term's
    end is charged to each term for its own days."""
    first, last = max(application.start, term.start), min(application.end, term.end)
    return max(0, (last - first).days + 1)


def entitlement_rows() -> tuple[dict, ...]:
    rows = []
    for ra in sample_data.RAS:
        start = date.fromisoformat(ra.dates.split()[0])
        for leave_type in LEAVE_TYPES:
            name, days = leave_type.name, entitlement(leave_type, start)
            adjustment, reason = ADJUSTMENTS.get((ra.name, name), (0, ""))
            mine = [a for a in APPLICATIONS if a.ra == ra.name and a.leave_type == name and not a.appeal]
            used = sum(days_in_term(a) for a in mine if a.stage == "Approved")
            pending = sum(days_in_term(a) for a in mine if a.stage in OPEN_STAGES)
            rows.append({
                "ra": ra.name, "email": ra.email, "type": name, "entitlement": days, "adjustment": adjustment,
                "reason": reason, "used": used, "pending": pending, "available": days + adjustment - used - pending,
            })
    return tuple(rows)


ENTITLEMENTS_CSV = """\
Email,Leave type,Adjustment,Reason
leon.chia@example.edu,Personal leave,2,Correction: days charged twice for one application"""


@dataclass(frozen=True)
class Route:
    precinct: str
    wing: str
    ras: int
    rf: str
    rslm: str
    first: str  # the first approver, by the policy, or a delegate
    delegate: bool
    note: str  # why a delegate stands in on this day, or why no one approves first
    gap: bool = False  # the policy's ticked appointments match no one on these slots


@dataclass(frozen=True)
class Delegate:
    """A person who approves first in another's place, on every slot that
    person approves for, between optional dates (author, 2026-10-28). First
    approval only: final approval and appeals are not delegable."""

    acting_for: str
    delegate: str
    start: date | None
    end: date | None
    reason: str  # reads after the name: "Grace Ho has not signed in yet"

    def active(self, day: date = TODAY) -> bool:
        return (self.start is None or self.start <= day) and (self.end is None or day <= self.end)

    @property
    def dates(self) -> str:
        if self.start is None and self.end is None:
            return "Until removed"
        if self.end is None:
            return f"From {short_date(self.start)}"
        if self.start is None:
            return f"Until {short_date(self.end)}"
        return f"{short_date(self.start)} – {short_date(self.end)}"


DELEGATES = (
    Delegate("Grace Ho", "Benjamin Chua", None, None, "has not signed in yet"),
    Delegate("Daniel Koh", "Mei Ling Tan", date(2026, 12, 7), date(2026, 12, 18), "is on leave"),
)


def delegable() -> list[str]:
    """Who a delegate may stand in for: the people on the slots holding an
    appointment the policy ticks for first approval; with no first approval,
    every slot approver, so a kept delegation still reads."""
    on_slots = {n for s in sample_data.SLOTS for n in s.staff}
    ticked = POLICY["first_types"] if POLICY["first"] == "slot" else {a for _, a in slot_appointments()}
    return [p.name for p in sample_data.STAFF if p.name in on_slots and p.abbrev in ticked]


def acting(person: str, day: date | None = None) -> Delegate | None:
    day = day or TODAY
    return next((d for d in DELEGATES if d.acting_for == person and d.active(day)), None)


def routes(day: date | None = None) -> tuple[Route, ...]:
    """The approval chain per Precinct, derived from the current term's
    assignments and the policy's first approver, a delegate standing in for
    an approver whose delegation is active on the day (default TODAY)."""
    staff = {p.name: p for p in sample_data.STAFF}
    found: dict[str, Route] = {}
    for slot in sample_data.SLOTS:
        if slot.precinct in found:
            found[slot.precinct] = Route(**{**found[slot.precinct].__dict__, "ras": found[slot.precinct].ras + len(slot.ras)})
            continue
        rf = next(n for n in slot.staff if staff[n].abbrev == "RF")
        rslm = next(n for n in slot.staff if staff[n].abbrev == "RSLM")
        by_type = {staff[n].abbrev: n for n in slot.staff}
        named = [by_type[t] for t in POLICY["first_types"] if t in by_type] if POLICY["first"] == "slot" else []
        standing_in = [d for n in named if (d := acting(n, day))]
        first = " or ".join(d.delegate if (d := acting(n, day)) else n for n in named)
        note = "; ".join(f"{d.acting_for} {d.reason}" for d in standing_in)
        gap = POLICY["first"] == "slot" and not named
        if POLICY["first"] == "none":
            first = "None needed"
        elif gap:
            first, note = "No one", f"no {first_label() or 'ticked appointment'} on its slots"
        found[slot.precinct] = Route(
            slot.precinct, slot.wing, len(slot.ras), rf, rslm, first, bool(standing_in), note, gap
        )
    return tuple(found.values())


def timeline(application: Application) -> tuple[tuple[str, str], ...]:
    """The application's steps so far, as (when, what)."""
    submitted = short_date(application.submitted)
    steps = [(submitted, f"Submitted by {application.ra}")]
    if application.cover_status == "Confirmed":
        steps.append((submitted, f"Cover confirmed by {application.cover}"))
    elif application.cover_status == "Declined":
        steps.append((submitted, f"Cover declined by {application.cover}"))
    # The sample reads today's chain; a wired timeline records who decided.
    route = next(r for r in routes() if r.precinct == application.precinct)
    first = "the first approver" if route.gap else route.first.split(" or ")[0]
    if application.appeal:
        steps.append(("", f"Sent to {APPEAL_DECIDER} as an extra-leave appeal"))
        if application.stage == "Approved":
            steps.append(("", f"Granted by {APPEAL_DECIDER}"))
        return tuple(steps)
    if application.stage in ("Pending final approval", "Approved") and POLICY["first"] == "slot":
        steps.append(("", f"First approval by {first}"))
    if application.stage == "Approved":
        steps.append(("", f"Final approval by {final_decider()}"))
    if application.stage == "Rejected":
        steps.append(("", f"Rejected by {first if POLICY['first'] == 'slot' else final_decider()}"))
    if application.stage == "Withdrawn":
        steps.append(("", f"Withdrawn by {application.ra}"))
    return tuple(steps)


# The RA pages (`/ra-leave/`) render for one sample viewer until identity
# is wired (segment 1C plan, "Viewing as").
VIEWER = "Chloe Lim"


def my_applications(ra: str = VIEWER) -> tuple[Application, ...]:
    return tuple(sorted((a for a in APPLICATIONS if a.ra == ra), key=lambda a: a.submitted, reverse=True))


def my_balances(ra: str = VIEWER) -> tuple[dict, ...]:
    return tuple(r for r in entitlement_rows() if r["ra"] == ra)


def my_extra(ra: str = VIEWER) -> dict[str, int]:
    """Extra leave, shown apart from entitlement (spec §8.1, §7.5)."""
    mine = [a for a in APPLICATIONS if a.ra == ra and a.appeal]
    return {
        "granted": sum(a.days for a in mine if a.stage == "Approved"),
        "pending": sum(a.days for a in mine if a.stage in OPEN_STAGES),
    }


def confirmation_needed(application: Application) -> bool:
    """Whether the cover must confirm: always for an appeal (spec §7.4); for
    ordinary leave only when the policy requires named and confirmed cover
    (§12)."""
    return application.appeal or (POLICY["cover_required"] and POLICY["cover_mode"] == "Named and confirmed")


def cover_asked(ra: str = VIEWER) -> dict[str, tuple[Application, ...]]:
    """Where an RA is named as cover (spec §23): to answer, covering now or
    to come (agreed, or named where no answer is owed), and the rest."""
    named = [a for a in APPLICATIONS if a.cover == ra and a.stage not in ("Rejected", "Withdrawn")]
    answer = tuple(
        a for a in named if a.cover_status == "Awaiting" and a.stage in OPEN_STAGES and confirmation_needed(a)
    )
    coming = tuple(
        a for a in named if a not in answer and a.end >= TODAY
        and (a.cover_status == "Confirmed" or (a.cover_status == "Awaiting" and not confirmation_needed(a)))
    )
    past = tuple(a for a in named if a not in answer and a not in coming)
    return {"answer": answer, "coming": coming, "past": past}


def cover_choices(ra: str = VIEWER) -> tuple[str, ...]:
    """Whom an RA may name as cover under the policy's pool, never
    themselves (spec §9.2)."""
    slot_of = {name: s for s in sample_data.SLOTS for name in s.ras}
    mine = slot_of[ra]
    level = {"Same Precinct": "precinct", "Same Wing": "wing"}.get(POLICY["cover_pool"])
    return tuple(
        name for s in sample_data.SLOTS for name in s.ras
        if name != ra and (level is None or getattr(s, level) == getattr(mine, level))
    )


# The staff pages (`/ra-leave/staff/`) render for a sample viewer chosen on
# the sample banner (`?as=`), one per role, until identity is wired.
STAFF_VIEWERS = (
    ("Daniel Koh", "RF, first approver for Cypress A 04-12"),
    ("Rachel Yeo", "Residential Admin, final approver"),
    ("Sam Lee", "Master, decides appeals"),
)


def staff_viewer(name: str | None) -> str:
    names = [n for n, _ in STAFF_VIEWERS]
    return name if name in names else names[0]


def first_decider_of(application: Application) -> str:
    """Who gave an application's first approval in the sample: the first
    named by its Precinct's chain today (a wired record keeps who did)."""
    return next(iter(routes_first(application)), "")


def queue(viewer: str) -> tuple[tuple[Application, str], ...]:
    """What awaits the viewer's decision, oldest first (spec §16, §24), with
    the decision it needs."""
    found = []
    for a in APPLICATIONS:
        if a.stage == "Pending first approval" and viewer in routes_first(a):
            found.append((a, "First approval"))
        elif a.stage == "Pending final approval" and viewer in final_approvers():
            found.append((a, "Final approval"))
        elif a.stage == "Appeal to the Master" and viewer == APPEAL_DECIDER:
            found.append((a, "Appeal"))
    return tuple(sorted(found, key=lambda pair: pair[0].submitted))


def routes_first(application: Application) -> tuple[str, ...]:
    """Everyone who may give an application's first approval today."""
    route = next(r for r in routes() if r.precinct == application.precinct)
    return () if route.gap or POLICY["first"] == "none" else tuple(route.first.split(" or "))


def waiting_on_cover(application: Application) -> bool:
    return application.cover_status != "Confirmed" and confirmation_needed(application)


def decided(viewer: str) -> tuple[tuple[Application, str, str], ...]:
    """The viewer's own past decisions, newest application first, as
    (application, decision, outcome)."""
    found = []
    for a in APPLICATIONS:
        if a.appeal:
            if viewer == APPEAL_DECIDER and a.stage in ("Approved", "Rejected"):
                found.append((a, "Appeal", a.stage))
            continue
        if a.stage in ("Pending final approval", "Approved") and first_decider_of(a) == viewer:
            found.append((a, "First approval", "Approved"))
        if a.stage == "Rejected" and first_decider_of(a) == viewer:
            found.append((a, "First approval", "Rejected"))
        if a.stage == "Rejected" and POLICY["first"] == "none" and final_decider() == viewer:
            found.append((a, "Final approval", "Rejected"))
        if a.stage == "Approved" and final_decider() == viewer:
            found.append((a, "Final approval", "Approved"))
    return tuple(sorted(found, key=lambda t: t[0].submitted, reverse=True))


def scope(viewer: str) -> tuple[str, ...]:
    """The Precincts a staff member's leave view covers (spec §22): an RF's
    own, an RSLM's Wing's, everyone else's the whole Unit."""
    abbrev = {p.name: p.abbrev for p in sample_data.STAFF}.get(viewer)
    held = [s for s in sample_data.SLOTS if viewer in s.staff]
    rf = {s.precinct for s in held if abbrev == "RF"}
    wing = {s.wing for s in held if abbrev == "RSLM"}
    every = tuple(dict.fromkeys(s.precinct for s in sample_data.SLOTS))
    if rf:
        return tuple(p for p in every if p in rf)
    if wing:
        return tuple(dict.fromkeys(s.precinct for s in sample_data.SLOTS if s.wing in wing))
    return every


def can_open(viewer: str, application: Application) -> bool:
    """Decide opens an application in the viewer's Precinct-leave scope, or
    one that is (or was) theirs to decide, wherever it is: a delegate's or a
    named final approver's (spec §13-§15)."""
    return (
        application.precinct in scope(viewer)
        or any(a.id == application.id for a, _ in queue(viewer))
        or any(a.id == application.id for a, _, _ in decided(viewer))
    )


def other_leave(application: Application) -> tuple[Application, ...]:
    """The applicant's other applications, for the decider (spec §15)."""
    return tuple(a for a in APPLICATIONS if a.ra == application.ra and a.id != application.id)


def by_precinct(viewer: str) -> tuple[dict, ...]:
    """Numbers away and pending per Precinct in the viewer's scope (§22)."""
    away = away_this_week()
    return tuple(
        {
            "precinct": p,
            "ras": sum(len(s.ras) for s in sample_data.SLOTS if s.precinct == p),
            "away": sum(1 for a in away if a.precinct == p),
            "pending": sum(1 for a in APPLICATIONS if a.precinct == p and a.stage in OPEN_STAGES),
        }
        for p in scope(viewer)
    )


def in_scope(viewer: str) -> tuple[Application, ...]:
    precincts = scope(viewer)
    return tuple(a for a in APPLICATIONS if a.precinct in precincts)


def away_on(application: Application) -> tuple[Application, ...]:
    """Others in the same Precinct away or asking to be away on overlapping
    days: the Precinct context a decision needs (spec §13)."""
    live = [a for a in APPLICATIONS if a.stage in ("Approved", *OPEN_STAGES)]
    return tuple(
        b for b in live
        if b.id != application.id and b.ra != application.ra and b.precinct == application.precinct
        and b.start <= application.end and application.start <= b.end
    )


def balance_of(application: Application) -> dict:
    return next(r for r in entitlement_rows() if r["ra"] == application.ra and r["type"] == application.leave_type)


def waiting_on_cover_count(viewer: str) -> int:
    return sum(1 for a, _ in queue(viewer) if waiting_on_cover(a))


def appeals_on() -> bool:
    """Whether the system has appeals at all: open, or by invitation."""
    return POLICY["appeals"] != "Off"


@dataclass(frozen=True)
class Invitation:
    """By invitation, an RA may send an appeal once the Master or the
    Master's admin delegate, having heard from them, agrees in principle and
    opens it for them on Appeals (author, 2026-10-29)."""

    ra: str
    agreed_by: str
    opened: date
    until: date
    note: str
    used_by: str = ""  # the appeal sent under it, once sent


INVITATIONS = (
    Invitation("Gwen Ho", "Sam Lee", date(2026, 10, 24), date(2026, 11, 7), "Family wedding overseas; agreed in principle", "L-0105"),
    Invitation("Kai Ng", "Rachel Yeo", date(2026, 10, 27), date(2026, 11, 10), "Sibling's graduation abroad; the Master agreed by email"),
    Invitation("Nathan Yeo", "Sam Lee", date(2026, 9, 14), date(2026, 9, 28), "Conference abroad; not sent in time"),
)


def inviters_for(ra: str) -> tuple[str, ...]:
    """Who may open an appeal for an RA, by the policy's inviter setting."""
    if POLICY["inviters"] == "named":
        return tuple(POLICY["inviter_names"])
    abbrev = {p.name: p.abbrev for p in sample_data.STAFF}
    if POLICY["inviters"] == "slot":
        slot = next((s for s in sample_data.SLOTS if ra in s.ras), None)
        return tuple(n for n in (slot.staff if slot else ()) if abbrev[n] in POLICY["inviter_types"])
    return tuple(p.name for p in sample_data.STAFF if p.abbrev in POLICY["inviter_types"])


def all_inviters() -> tuple[str, ...]:
    return tuple(dict.fromkeys(n for ra in sample_data.RAS for n in inviters_for(ra.name)))


def invitable_ras(viewer: str) -> tuple[str, ...]:
    """The RAs a staff member may open an appeal for."""
    return tuple(ra.name for ra in sample_data.RAS if viewer in inviters_for(ra.name))


def inviter_label() -> str:
    if POLICY["inviters"] == "named":
        return " or ".join(POLICY["inviter_names"]) or "no one named"
    whose = "the RA's slot's" if POLICY["inviters"] == "slot" else "the Unit's"
    return f"{whose} {' or '.join(POLICY['inviter_types']) or 'no appointment ticked'}"


def invitation_for(ra: str, day: date | None = None) -> Invitation | None:
    """An RA's unused invitation still in date."""
    day = day or TODAY
    return next((i for i in INVITATIONS if i.ra == ra and not i.used_by and i.opened <= day <= i.until), None)


def invitation_status(invitation: Invitation) -> str:
    if invitation.used_by:
        return f"Sent: {invitation.used_by}"
    if invitation.until < TODAY:
        return "Lapsed"
    return "Open" if invitation.opened <= TODAY else "From " + short_date(invitation.opened)


def can_appeal(ra: str) -> bool:
    """Whether an RA may send an appeal now: always while appeals are open,
    with an invitation while they are by invitation, never while off."""
    return POLICY["appeals"] == "Open" or (POLICY["appeals"] == "By invitation" and invitation_for(ra) is not None)
