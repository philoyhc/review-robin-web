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
    "day_count": "Every day",  # one of DAY_COUNTS; see leave_days()
    # Appeals beyond entitlement (author, 2026-10-28, refined 2026-10-29):
    # open to every RA, by invitation once someone the policy names agrees
    # in principle, or off.
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
    # Who oversees every RA, as if in every slot (author, 2026-10-29): the
    # Master and the designated admin, chosen as Unit-level appointments.
    "overseers": ("Master", "Admin"),
}


# How an application's days are counted (author, 2026-10-29): RAs work
# weekends and public holidays, so every day counts by default. The
# holidays are the admin's list of observed dates, a Sunday holiday's
# Monday in lieu entered as its own row.
DAY_COUNTS = ("Every day", "Weekdays", "Working days")
PUBLIC_HOLIDAYS = (
    (date(2026, 8, 10), "National Day (observed)"),
    (date(2026, 11, 9), "Deepavali (observed)"),
    (date(2026, 12, 25), "Christmas Day"),
    (date(2027, 1, 1), "New Year's Day"),
)


def leave_days(first: date, last: date) -> int:
    """The days an application charges, by the policy's day count: every
    day, weekdays only, or working days (weekdays less public holidays)."""
    holidays = {d for d, _ in PUBLIC_HOLIDAYS}
    days = [date.fromordinal(n) for n in range(first.toordinal(), last.toordinal() + 1)]
    if POLICY["day_count"] in ("Weekdays", "Working days"):
        days = [d for d in days if d.isoweekday() < 6]
    if POLICY["day_count"] == "Working days":
        days = [d for d in days if d not in holidays]
    return len(days)


def zero_day_rule() -> str:
    """Why an application may count no days, by the day count; empty when
    every day counts. An application counting none is not submitted
    (author, 2026-10-29)."""
    return {
        "Weekdays": "Dates falling only on a weekend count no days, and cannot be submitted.",
        "Working days": "Dates falling only on weekends or public holidays count no days, and cannot be submitted.",
    }.get(POLICY["day_count"], "")


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


def final_gap() -> bool:
    """The policy names no one who may give final approval."""
    return not final_approvers()


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
    "Cancelled",  # approved, then cancelled by an admin (spec §30, §21.4)
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
    cover_recorded: str  # Confirmed, Awaiting, Declined; `cover_status` reads it
    recorded: str  # the stage as recorded; `stage` reads it under today's policy
    submitted: date
    remarks: str = ""

    @property
    def cover_status(self) -> str:
        """The cover's status, kept apart from the stage (spec §30): an
        application withdrawn or cancelled releases its cover."""
        return "Cancelled" if self.recorded in ("Withdrawn", "Cancelled") else self.cover_recorded

    @property
    def stage(self) -> str:
        """The stage under the policy: with no first approval needed, an
        application recorded as awaiting it awaits final approval (a wired
        policy change moves the records themselves)."""
        if self.recorded == "Pending first approval" and POLICY["first"] == "none":
            return "Pending final approval"
        return self.recorded

    @property
    def appeal(self) -> bool:
        """An extra-leave appeal: decided by the Master, and kept apart from
        normal entitlement once granted (spec §7.5)."""
        return self.stage == "Appeal to the Master" or self.id in GRANTED_APPEALS

    @property
    def days(self) -> int:
        return leave_days(self.start, self.end)

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
            ("Kai Ng", "Personal leave", _d("2026-11-04"), _d("2026-11-05"), "Isaac Goh", "Confirmed", "Cancelled", _d("2026-10-08")),
            ("Chloe Lim", "Official leave", _d("2026-09-25"), _d("2026-09-25"), "Hana Ito", "Confirmed", "Approved", _d("2026-09-14"),
             "Representing the hall at the inter-hall games."),
            ("Lucas Teo", "Personal leave", _d("2026-09-07"), _d("2026-09-09"), "Maya Seah", "Confirmed", "Approved", _d("2026-08-28"),
             "Balance used; grandmother's funeral abroad."),
            # The leave that used Lucas Teo's balance before his appeal.
            ("Lucas Teo", "Personal leave", _d("2026-08-24"), _d("2026-08-28"), "Maya Seah", "Confirmed", "Approved", _d("2026-08-17")),
        ),
        start=101,
    )
)


GRANTED_APPEALS: frozenset[str] = frozenset({"L-0118"})  # extra leave the Master granted

# The sample's record of each decision: its date and remarks, by step
# (spec §14, §15, §19). Who decided is read from today's chain in
# `timeline`; a wired record keeps the person too.
DECISIONS: dict[str, dict[str, tuple[date, str]]] = {
    "L-0103": {"first": (_d("2026-10-24"), "Cover agreed; the Precinct is fully staffed that weekend.")},
    "L-0105": {"staff": (_d("2026-10-26"), "Gwen has taken extra duty nights this term; I support the appeal.")},
    "L-0106": {"first": (_d("2026-10-13"), ""), "final": (_d("2026-10-14"), "")},
    "L-0107": {"first": (_d("2026-10-15"), ""), "final": (_d("2026-10-16"), "")},
    "L-0108": {"first": (_d("2026-10-16"), ""), "final": (_d("2026-10-19"), "Two of the Precinct are away on the 29th; cover is key.")},
    "L-0110": {"rejected": (_d("2026-10-05"), "Clashes with the Precinct's orientation duties that weekend.")},
    "L-0111": {"withdrawn": (_d("2026-10-09"), "")},
    "L-0112": {"first": (_d("2026-08-06"), ""), "final": (_d("2026-08-07"), "")},
    "L-0113": {"first": (_d("2026-09-11"), ""), "final": (_d("2026-09-14"), "")},
    "L-0115": {"first": (_d("2026-10-21"), "Fine."), "final": (_d("2026-10-22"), "")},
    "L-0116": {
        "first": (_d("2026-10-09"), ""), "final": (_d("2026-10-12"), ""),
        "cancelled": (_d("2026-10-20"), "Kai Ng is leading the Precinct's November event; cancelled at his request."),
    },
    "L-0117": {"first": (_d("2026-09-15"), "Good luck at the games."), "final": (_d("2026-09-16"), "")},
    "L-0119": {"first": (_d("2026-08-18"), ""), "final": (_d("2026-08-19"), "")},
    "L-0118": {
        "staff": (_d("2026-08-29"), "Lucas has covered two extra weekends; I support it."),
        "appeal": (_d("2026-08-31"), "Granted, on the extra duties agreed with Arjun Nair."),
    },
}
CANCELLED_BY = "Rachel Yeo"  # the sample's Leave admin


def decision(application: "Application", step: str) -> tuple[str, str]:
    """A recorded step's date, as shown, and remarks; blank when the sample
    keeps no record of it."""
    when, remarks = DECISIONS.get(application.id, {}).get(step, (None, ""))
    return (short_date(when) if when else "", remarks)


def _step(application: "Application", step: str, what: str) -> tuple[str, str, str]:
    when, remarks = decision(application, step)
    return (when, what, remarks)


def history_steps(application: "Application") -> tuple[tuple[str, str, str], ...]:
    """The decisions and closing actions on an application, as its timeline
    shows them under today's policy, for a history item (spec §19): each
    with its date and remarks."""
    return tuple(s for s in timeline(application) if not s[1].startswith(("Submitted", "Cover ", "Sent to")))


def by_id(application_id: str) -> Application | None:
    return next((a for a in APPLICATIONS if a.id == application_id), None)


def stages(open_only: bool = False) -> tuple[str, ...]:
    """The stages the policy uses: no appeal stage while appeals are off,
    no first-approval stage when none is needed."""
    # Appeals off removes the route for new applications; an appeal already
    # made keeps its stage and is decided (author, 2026-10-28).
    skip = set() if appeals_decided() else {"Appeal to the Master"}
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


def upcoming() -> tuple[Application, ...]:
    """Approved leave starting after this week, to the term's end (spec
    §25, upcoming leave), soonest first."""
    after = date.fromordinal(TODAY.toordinal() + 6)
    return tuple(sorted((a for a in APPLICATIONS if a.stage == "Approved" and after < a.start <= TERM.end), key=lambda a: a.start))


def extra_by_term() -> tuple[tuple[str, int, int], ...]:
    """Extra leave the Master granted, per term of the year: (term,
    appeals, days), kept apart from entitlement (spec §25, §7.5)."""
    granted = [a for a in APPLICATIONS if a.appeal and a.stage == "Approved"]
    return tuple(
        (t.label, sum(1 for a in granted if t.start <= a.start <= t.end),
         sum(a.days for a in granted if t.start <= a.start <= t.end))
        for t in sample_data.TERMS if t.year == PERIOD_LABEL
    )


@dataclass(frozen=True)
class Correction:
    """An administrative correction, as the audit log keeps it (spec §26)."""

    when: date
    actor: str
    what: str
    reason: str
    application: str = ""  # its application, if any


CORRECTIONS = (
    Correction(date(2026, 10, 20), "Rachel Yeo", "Cancelled approved leave for Kai Ng", "Leading the Precinct's November event; at his request", "L-0116"),
    Correction(date(2026, 8, 3), "Rachel Yeo", "Adjusted Leon Chia's Personal leave by +2", "Days charged twice for one application"),
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
    return leave_days(first, last) if first <= last else 0


def entitlement_anomalies() -> tuple[tuple[dict, str], ...]:
    """Entitlement rows to look at (spec §25): over entitlement, or an adjustment
    with no reason recorded."""
    found = []
    for r in entitlement_rows():
        if r["available"] < 0:
            found.append((r, f"Over entitlement by {-r['available']} day{'s' if r['available'] != -1 else ''}, pending included"))
        elif r["adjustment"] and not r["reason"]:
            found.append((r, "Adjusted with no reason recorded"))
    return tuple(found)


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


def timeline(application: Application) -> tuple[tuple[str, str, str], ...]:
    """The application's steps so far, as (when, what, remarks)."""
    submitted = short_date(application.submitted)
    steps = [(submitted, f"Submitted by {application.ra}", "")]
    if application.cover_recorded == "Confirmed":
        steps.append((submitted, f"Cover confirmed by {application.cover}", ""))
    elif application.cover_recorded == "Declined":
        steps.append((submitted, f"Cover declined by {application.cover}", ""))
    # The sample reads today's chain; a wired timeline records who decided.
    route = next(r for r in routes() if r.precinct == application.precinct)
    first = "the first approver" if route.gap else route.first.split(" or ")[0]
    if application.appeal:
        steps.append(("", f"Sent to {APPEAL_DECIDER} as an extra-leave appeal", ""))
        if "staff" in DECISIONS.get(application.id, {}):
            steps.append(_step(application, "staff", f"Remarks from {route.rf}, RF"))
        if application.stage in ("Approved", "Rejected"):
            verb = "Granted" if application.stage == "Approved" else "Rejected"
            steps.append(_step(application, "appeal", f"{verb} by {APPEAL_DECIDER}"))
        return tuple(steps)
    if application.stage in ("Pending final approval", "Approved", "Cancelled") and POLICY["first"] == "slot":
        steps.append(_step(application, "first", f"First approval by {first}"))
    if application.stage in ("Approved", "Cancelled"):
        steps.append(_step(application, "final", f"Final approval by {final_decider()}"))
    if application.stage == "Rejected":
        who = first if POLICY["first"] == "slot" else final_decider()
        steps.append(_step(application, "rejected", f"Rejected by {who}"))
    if application.stage == "Withdrawn":
        steps.append(_step(application, "withdrawn", f"Withdrawn by {application.ra}"))
    if application.stage == "Cancelled":
        steps.append(_step(application, "cancelled", f"Cancelled by {CANCELLED_BY}, Residential Admin"))
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
    named = [a for a in APPLICATIONS if a.cover == ra and a.stage not in ("Rejected", "Withdrawn", "Cancelled")]
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
    ("Daniel Koh", "RF"),
    ("Priya Raman", "RSLM"),
    ("Rachel Yeo", "Residential Admin"),
    ("Sam Lee", "Master"),
    ("Hui Min Goh", "Residential Executive"),
)


def staff_role(name: str) -> str:
    """A sample viewer's appointment and what the policy has them decide
    today, so the switch never claims a role the policy has taken away."""
    appointment = dict(STAFF_VIEWERS).get(name, "")
    does = []
    first = [r.precinct for r in routes() if not r.gap and name in r.first.split(" or ")]
    if first and POLICY["first"] == "slot":
        does.append("first approver for " + ", ".join(first))
    if name in final_approvers():
        does.append("final approver")
    if name == APPEAL_DECIDER and appeals_decided():
        does.append("decides appeals")
    if POLICY["appeals"] == "By invitation" and invitable_ras(name):
        does.append("opens appeals")
    if not scope(name):
        return f"{appointment}, oversees no RA, so RA Leave is not shown"
    return f"{appointment}, {', '.join(does)}" if does else f"{appointment}, no decisions under the policy"


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
        if a.stage in ("Pending final approval", "Approved", "Cancelled") and first_decider_of(a) == viewer:
            found.append((a, "First approval", "Approved"))
        if a.stage == "Rejected" and first_decider_of(a) == viewer:
            found.append((a, "First approval", "Rejected"))
        if a.stage == "Rejected" and POLICY["first"] == "none" and final_decider() == viewer:
            found.append((a, "Final approval", "Rejected"))
        if a.stage in ("Approved", "Cancelled") and final_decider() == viewer:
            found.append((a, "Final approval", "Approved"))
    return tuple(sorted(found, key=lambda t: t[0].submitted, reverse=True))


def overseers() -> tuple[str, ...]:
    """Who oversees every RA, as if in every slot: the staff holding the
    policy's ticked Unit-level appointments (author, 2026-10-29)."""
    return tuple(p.name for p in sample_data.STAFF if p.abbrev in POLICY["overseers"])


def scope(viewer: str) -> tuple[str, ...]:
    """The Precincts whose RAs a staff member oversees (spec §22; author,
    2026-10-29): the overseers every one; an RF their slots' Precincts, an
    RSLM their Wing's; and wherever the approval chain gives them a
    decision (a final approver or the Master every one, a delegate the
    slots of whom they stand in for, an inviter their RAs'). Staff with
    none, such as Unit-level staff holding no slot, see no RA Leave."""
    every = tuple(dict.fromkeys(s.precinct for s in sample_data.SLOTS))
    if viewer in overseers() or viewer in final_approvers() or viewer == APPEAL_DECIDER:
        return every
    abbrev = {p.name: p.abbrev for p in sample_data.STAFF}.get(viewer)
    held = [s for s in sample_data.SLOTS if viewer in s.staff]
    wings = {s.wing for s in held if abbrev == "RSLM"}
    found = {s.precinct for s in held} | {s.precinct for s in sample_data.SLOTS if s.wing in wings}
    for d in DELEGATES:
        if d.delegate == viewer and d.active() and POLICY["first"] == "slot":
            found |= {s.precinct for s in sample_data.SLOTS if d.acting_for in s.staff}
    found |= {s.precinct for s in sample_data.SLOTS if any(ra in s.ras for ra in invitable_ras(viewer))}
    return tuple(p for p in every if p in found)


def can_open(viewer: str, application: Application) -> bool:
    """Decide opens an application in the viewer's Precinct-leave scope, or
    one that is (or was) theirs to decide, wherever it is: a delegate's or a
    named final approver's (spec §13-§15), or an RA's they may open an
    appeal for."""
    return (
        application.precinct in scope(viewer)
        or application.ra in invitable_ras(viewer)
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


def ras_in_scope(viewer: str) -> tuple[str, ...]:
    """The RAs a staff member oversees: those in the slots of their scope."""
    precincts = scope(viewer)
    return tuple(ra for s in sample_data.SLOTS if s.precinct in precincts for ra in s.ras)


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


def appeals_decided() -> bool:
    """Whether the Master still decides appeals: while they are on, or
    while one made before they were turned off is open (author,
    2026-10-28: existing appeals stand)."""
    return appeals_on() or any(a.stage == "Appeal to the Master" for a in APPLICATIONS)


@dataclass(frozen=True)
class Invitation:
    """By invitation, an RA may send an appeal once someone the policy lets
    open appeals, having heard from them, agrees in principle and opens it
    for them on Appeals (author, 2026-10-29)."""

    ra: str
    agreed_by: str
    opened: date
    until: date
    note: str
    used_by: str = ""  # the appeal sent under it, once sent


INVITATIONS = (
    Invitation("Gwen Ho", "Sam Lee", date(2026, 10, 24), date(2026, 11, 7), "Family wedding overseas; agreed in principle", "L-0105"),
    Invitation("Kai Ng", "Rachel Yeo", date(2026, 10, 27), date(2026, 11, 10), "Sibling's graduation abroad; agreed in principle"),
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
    """Who may open an appeal, as a phrase; empty when the policy names
    no one."""
    if POLICY["inviters"] == "named":
        return " or ".join(POLICY["inviter_names"])
    if not POLICY["inviter_types"]:
        return ""
    whose = "the RA's slot's" if POLICY["inviters"] == "slot" else "the Unit's"
    return f"{whose} {' or '.join(POLICY['inviter_types'])}"


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
