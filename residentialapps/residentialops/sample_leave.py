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
    amount: int  # days per term or per year, or per month served
    cap: int  # the most an RA may have in a cap period
    cap_per: str  # "year" or "term"


ACCRUALS = ("Per term", "Per academic year", "Per month served")
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
FIRST_APPROVERS = ("RF", "RSLM", "Either")
FINAL_APPROVERS = ("Admin", "Master", "RSLM")
POLICY = {
    "appeal_terms": "Granted on the understanding that you take on extra duties, as agreed with your RF.",
    "cover_required": True,
    "cover_mode": "Named and confirmed",
    "cover_pool": "Same Precinct",
    "first_approver": "RF",
    "final_approver": "Admin",
}
PERIOD_LABEL = "AY2026-2027"

FINAL_APPROVER = "Rachel Yeo"  # the Residential Admin appointment, the policy's final approver
APPEAL_DECIDER = "Sam Lee"  # the Master

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
            ("Gwen Ho", "Personal leave", _d("2026-08-17"), _d("2026-08-26"), "Elise Tan", "Confirmed", "Approved", _d("2026-08-05")),
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


# Entitlements for the period: (RA, leave type) -> (entitlement, adjustment, reason).
ADJUSTMENTS = {
    ("Leon Chia", "Personal leave"): (2, "Carried over by the Master's decision, 2026-08-03"),
}


def term_labels(year: str = PERIOD_LABEL) -> tuple[str, ...]:
    return tuple(f"Term {t.number}" for t in sample_data.TERMS if t.year == year)


def year_start(year: str = PERIOD_LABEL) -> date:
    return min(t.start for t in sample_data.TERMS if t.year == year)


def months_served(start: date) -> int:
    """Whole months served this year: from the later of the appointment's
    first day and the year's, to TODAY, so earlier years' months are never
    counted again."""
    start = max(start, year_start())
    months = (TODAY.year * 12 + TODAY.month) - (start.year * 12 + start.month)
    return months - (1 if TODAY.day < start.day else 0)


def entitlement(leave_type: LeaveType, appointment_start: date) -> int:
    """The year's entitlement so far: a per-term amount over the year's
    terms, a yearly amount, or what the months served have earned, held to
    the cap. A cap per term holds the year to the cap times its terms.
    Adjustments sit outside the cap: they are the admin's deliberate
    exceptions, each with its reason."""
    terms = sum(1 for t in sample_data.TERMS if t.year == PERIOD_LABEL)
    cap = leave_type.cap * (terms if leave_type.cap_per == "term" else 1)
    if leave_type.accrual == "Per term":
        days = leave_type.amount * terms
    elif leave_type.accrual == "Per academic year":
        days = leave_type.amount
    else:
        days = leave_type.amount * months_served(appointment_start)
    return min(days, cap)


def entitlement_rows() -> tuple[dict, ...]:
    rows = []
    for ra in sample_data.RAS:
        start = date.fromisoformat(ra.dates.split()[0])
        for leave_type in LEAVE_TYPES:
            name, days = leave_type.name, entitlement(leave_type, start)
            adjustment, reason = ADJUSTMENTS.get((ra.name, name), (0, ""))
            mine = [a for a in APPLICATIONS if a.ra == ra.name and a.leave_type == name and not a.appeal]
            used = sum(a.days for a in mine if a.stage == "Approved")
            pending = sum(a.days for a in mine if a.stage in OPEN_STAGES)
            rows.append({
                "ra": ra.name, "email": ra.email, "type": name, "entitlement": days, "adjustment": adjustment,
                "reason": reason, "used": used, "pending": pending, "available": days + adjustment - used - pending,
            })
    return tuple(rows)


ENTITLEMENTS_CSV = """\
Email,Leave type,Adjustment,Reason
leon.chia@example.edu,Personal leave,2,Carried over by the Master's decision"""


@dataclass(frozen=True)
class Route:
    precinct: str
    wing: str
    ras: int
    rf: str
    rslm: str
    first: str  # the first approver, by the policy, or a delegate
    delegate: bool
    gap: str  # why routing is incomplete, or ""


DELEGATES = {"Maple 03-08": ("Benjamin Chua", "Grace Ho has not signed in yet")}


def routes() -> tuple[Route, ...]:
    """The approval chain per Precinct, derived from the current term's
    assignments and the policy's first approver."""
    staff = {p.name: p for p in sample_data.STAFF}
    found: dict[str, Route] = {}
    for slot in sample_data.SLOTS:
        if slot.precinct in found:
            found[slot.precinct] = Route(**{**found[slot.precinct].__dict__, "ras": found[slot.precinct].ras + len(slot.ras)})
            continue
        rf = next(n for n in slot.staff if staff[n].abbrev == "RF")
        rslm = next(n for n in slot.staff if staff[n].abbrev == "RSLM")
        first = {"RF": rf, "RSLM": rslm, "Either": f"{rf} or {rslm}"}[POLICY["first_approver"]]
        delegate, gap = DELEGATES.get(slot.precinct, (None, ""))
        found[slot.precinct] = Route(
            slot.precinct, slot.wing, len(slot.ras), rf, rslm, delegate or first, bool(delegate), gap
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
    if application.stage in ("Pending final approval", "Approved"):
        steps.append(("", f"First approval by {route.first}"))
    if application.stage == "Approved":
        steps.append(("", f"Final approval by {FINAL_APPROVER}"))
    if application.stage == "Rejected":
        steps.append(("", f"Rejected by {route.first}"))
    if application.stage == "Withdrawn":
        steps.append(("", f"Withdrawn by {application.ra}"))
    return tuple(steps)
