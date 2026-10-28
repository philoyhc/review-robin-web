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
    Saturday."""

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


def week_dates(blackout: Blackout, year: str = "AY2026-2027") -> tuple[date, date]:
    """The blackout's Sunday-to-Saturday dates in a year's term."""
    term = next(t for t in sample_data.TERMS if t.year == year and t.number == blackout.term)
    sunday = date.fromordinal(term.start.toordinal() - (term.start.isoweekday() % 7))
    first = date.fromordinal(sunday.toordinal() + 7 * (blackout.week_from - 1))
    return first, date.fromordinal(sunday.toordinal() + 7 * blackout.week_to - 1)


COVER_MODES = ("Named only", "Named and confirmed")
COVER_POOLS = ("Any RA", "Same Precinct", "Same Wing")
POLICY = {
    "appeals": True,  # on or off for the whole system (author, 2026-10-28)
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
            ("Faris Iskandar", "Personal leave", _d("2026-10-10"), _d("2026-10-11"), "Haikal Rahim", "Confirmed", "Rejected", _d("2026-10-02")),
            ("Ethan Wong", "Personal leave", _d("2026-10-17"), _d("2026-10-18"), "Hana Ito", "Confirmed", "Withdrawn", _d("2026-10-05")),
            ("Gwen Ho", "Personal leave", _d("2026-08-17"), _d("2026-08-19"), "Elise Tan", "Confirmed", "Approved", _d("2026-08-05")),
            ("Gwen Ho", "Personal leave", _d("2026-09-21"), _d("2026-09-22"), "Faris Iskandar", "Confirmed", "Approved", _d("2026-09-10")),
        ),
        start=101,
    )
)


GRANTED_APPEALS: frozenset[str] = frozenset()  # none granted yet in the sample


def by_id(application_id: str) -> Application | None:
    return next((a for a in APPLICATIONS if a.id == application_id), None)


def pending_by_stage() -> tuple[tuple[str, int], ...]:
    return tuple((stage, sum(1 for a in APPLICATIONS if a.stage == stage)) for stage in OPEN_STAGES)


def cover_unconfirmed() -> tuple[Application, ...]:
    """Open applications whose cover has not confirmed (spec §25,
    outstanding cover confirmations)."""
    return tuple(a for a in APPLICATIONS if a.stage in OPEN_STAGES and a.cover_status != "Confirmed")


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
    ("Leon Chia", "Personal leave"): (2, "Granted by the Master's decision, 2026-08-03"),
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
leon.chia@example.edu,Personal leave,2,Granted by the Master's decision"""


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
    steps = [(application.submitted.isoformat(), f"Submitted by {application.ra}")]
    if application.cover_status == "Confirmed":
        steps.append((application.submitted.isoformat(), f"Cover confirmed by {application.cover}"))
    elif application.cover_status == "Declined":
        steps.append((application.submitted.isoformat(), f"Cover declined by {application.cover}"))
    route = next(r for r in routes() if r.precinct == application.precinct)
    if application.appeal:
        steps.append(("", f"Sent to {APPEAL_DECIDER} as an extra-leave appeal"))
        if application.stage == "Approved":
            steps.append(("", f"Granted by {APPEAL_DECIDER}"))
        return tuple(steps)
    if application.stage in ("Pending final approval", "Approved") and POLICY["first"] == "slot":
        steps.append(("", f"First approval by {route.first}"))
    if application.stage == "Approved":
        steps.append(("", f"Final approval by {final_decider()}"))
    if application.stage == "Rejected":
        steps.append(("", f"Rejected by {route.first if POLICY['first'] == 'slot' else final_decider()}"))
    if application.stage == "Withdrawn":
        steps.append(("", f"Withdrawn by {application.ra}"))
    return tuple(steps)
