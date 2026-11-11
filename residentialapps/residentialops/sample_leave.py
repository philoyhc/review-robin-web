"""Example data for RA Leave's placeholder screens (segment 1C item 1),
built on the Rosters sample (`sample_data`): the same Unit, RAs, slots and
terms. Every page that shows it is labeled "Sample data"; it lives here
alone so that 1C items 2–5 delete it in one place
(`residentialapps/guide/segment_1C_ra_leave.md`).
"""

from __future__ import annotations

from collections.abc import Iterable
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import TypedDict, cast

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


def type_abbrev(name: str) -> str:
    """A leave type's abbreviation from Policy, as Records shows it (author,
    2026-11-10); a name Policy no longer lists shows whole."""
    return next((t.abbrev for t in LEAVE_TYPES if t.name == name), name)


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
# Who approves an appeal opened by invitation (author, 2026-11-10): the
# usual first and final approvers, or the usual first approver and then the
# Master, so the Master is involved. With no separate first approver,
# either skips that step. An appeal made while appeals are Open goes
# straight to the Master.
APPEAL_APPROVALS = (
    ("usual", "the normal first, and final approver"),
    ("master", "the normal first approver, and the Master"),
)
# By invitation by default (author, 2026-11-09): a default deployment does
# not show extra leave to RAs. An RA appeals offline; if it is agreed, an
# admin opens an invitation, and only that RA may then send it.
APPEALS_DEFAULT = "By invitation"
COVER_MODES = ("Named only", "Named and confirmed")
COVER_POOLS = ("Any RA", "Same Precinct", "Same Wing")
# The sample's appeal mode can be previewed per browser (`Leave policy`'s
# sample switch, a cookie read once a request), so the by-invitation and
# off screens can be seen without editing this file (audit, 2026-10-29).
APPEALS_PREVIEW: ContextVar[str | None] = ContextVar("appeals_preview", default=None)


class Policy(TypedDict):
    """The sample policy's settings, as `POLICY` is read."""

    day_count: str
    appeals: str
    inviters: str
    inviter_types: tuple[str, ...]
    inviter_names: tuple[str, ...]
    appeal_terms: str
    appeal_approval: str
    cover_required: bool
    cover_mode: str
    cover_pool: str
    first: str
    first_types: tuple[str, ...]
    final: str
    final_types: tuple[str, ...]
    final_names: tuple[str, ...]
    viewer_types: tuple[str, ...]


class _Policy(dict[str, object]):
    """The sample policy; reading `appeals` gives the previewed mode, if any."""

    def __getitem__(self, key: str) -> object:
        if key == "first":
            # A first approval is needed while Permissions ticks someone for
            # it (author, 2026-11-10: the Approvals card is gone); no tick,
            # none needed, so a ticked-but-nobody gap cannot arise.
            ticked = bool(super().__getitem__("first_types"))
            return super().__getitem__("first") if ticked else "none"
        preview = APPEALS_PREVIEW.get() if key == "appeals" else None
        return preview if preview in APPEAL_MODES else super().__getitem__(key)

    def stored(self, key: str) -> object:
        """A key's own value, never the preview."""
        return super().__getitem__(key)

    def get(self, key: str, default: object = None) -> object:
        return self[key] if key in self else default  # noqa: SIM401 -- this is get(); self.get would recurse


PREVIEW_COOKIE = "residential-sample-appeals"


def policy_appeals() -> str:
    """The sample policy's own appeal mode, whatever is previewed."""
    return cast(str, _POLICY.stored("appeals"))


def appeals_preview() -> str | None:
    """The appeal mode previewed in this browser, if it differs from the policy's."""
    mode = APPEALS_PREVIEW.get()
    return mode if mode in APPEAL_MODES and mode != policy_appeals() else None


_POLICY = _Policy(
    {
        "day_count": "Every day",  # one of DAY_COUNTS; see leave_days()
        # Appeals beyond entitlement (author, 2026-10-28, refined 2026-10-29):
        # open to every RA, by invitation once someone the policy names agrees
        # in principle, or off.
        "appeals": APPEALS_DEFAULT,  # one of APPEAL_MODES
        # Who may open an appeal by invitation (author, 2026-10-29), chosen as
        # approvers are: appointments on the RA's slot, Unit-level
        # appointments, or named staff.
        "inviters": "unit",  # "slot", "unit" or "named"
        "inviter_types": ("Master", "Admin"),
        "inviter_names": (),
        "appeal_terms": (
            "Granted on the understanding that you take on extra duties, as agreed with your RF."
        ),
        "appeal_approval": "master",
        "cover_required": True,
        "cover_mode": "Named and confirmed",
        "cover_pool": "Same Precinct",
        # Approvals (author, 2026-10-28): first by one or more of the
        # appointments on the RA's slot, whichever approves first, or none;
        # final by one or more Unit-level appointments, or by named staff.
        # Since 2026-11-10 the ticks alone say whether one is needed: reading
        # "first" gives "none" while no one is ticked (`_Policy`); "none"
        # stored here remains only for tests that turn first approval off.
        "first": "slot",  # or "none"
        "first_types": ("RF",),
        "final": "unit",  # or "named"
        "final_types": ("Admin",),
        "final_names": (),
        # Who views Leave records without approving (author, 2026-11-10):
        # the appointments given View records in Permissions. RSLMs need no
        # RA Leave (author, 2026-11-09), so they are not among them.
        "viewer_types": ("RF", "Master", "Admin"),
    }
)
# Read through its keys' types: `_Policy` is the runtime object, `Policy`
# what each key holds.
POLICY = cast(Policy, _POLICY)


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
        "Working days": (
            "Dates falling only on weekends or public holidays count no days, "
            "and cannot be submitted."
        ),
    }.get(POLICY["day_count"], "")


PERIOD_LABEL = "AY2026-2027"

APPEAL_DECIDER = "Sam Lee"  # the Master


def _appointments(names: Iterable[str]) -> tuple[tuple[str, str], ...]:
    staff = {p.name: p for p in sample_data.STAFF}
    return sample_data.appointments(tuple(staff[n] for n in dict.fromkeys(names)))


def slot_appointments() -> tuple[tuple[str, str], ...]:
    """(appointment, abbreviation) for each staff appointment found in the
    slots' Staff cells, in the order first met."""
    return _appointments(n for s in sample_data.SLOTS for n in s.staff)


def unit_appointments() -> tuple[tuple[str, str], ...]:
    """The Unit's own appointments, on no slot's Staff cell
    (`sample_data.unit_appointments`)."""
    return sample_data.unit_appointments()


def final_approvers() -> tuple[str, ...]:
    """Whom the policy names for final approval, whichever does first; each
    approves only where they hold a place in the RA's slot (`final_for`)."""
    if POLICY["final"] == "named":
        return tuple(POLICY["final_names"])
    return tuple(p.name for p in sample_data.STAFF if p.abbrev in POLICY["final_types"])


def in_slots(person: str, precinct: str) -> bool:
    """Whether a person holds a place in a Precinct's slots: on their Staff
    cell, or as an overseer, in every slot. A Precinct's slots share their
    Staff cell (Assignments; `routes` reads the first), so a place in the
    Precinct is a place in each RA's slot. Only such a person approves,
    first or final, decides or opens an appeal for its RAs (author,
    2026-10-29)."""
    return person in overseers() or any(
        person in s.staff for s in sample_data.SLOTS if s.precinct == precinct
    )


def precincts() -> tuple[str, ...]:
    return tuple(dict.fromkeys(s.precinct for s in sample_data.SLOTS))


def with_roles(names: Iterable[str], by_role: bool = True) -> str:
    """Names for Approval chain (author, 2026-11-10), comma separated, each
    with its Staff-roster abbreviation when the role decided it."""
    abbrev = {p.name: p.abbrev for p in sample_data.STAFF}
    once = dict.fromkeys(names)  # a person once, however often named
    return ", ".join(f"{n} ({abbrev[n]})" if by_role and abbrev.get(n) else n for n in once)


def appeal_finals(precinct: str) -> tuple[str, ...]:
    """Who gives an appeal its final decision for a Precinct: the usual
    final approvers when they decide invited appeals, else the Master
    while in its slots."""
    if appeal_route() == "usual":
        return final_for(precinct)
    return (APPEAL_DECIDER,) if decides_appeals(precinct) else ()


def final_for(precinct: str) -> tuple[str, ...]:
    """Who gives final approval for a Precinct's RAs: those the policy
    names who hold a place in its slots."""
    return tuple(n for n in final_approvers() if in_slots(n, precinct))


def final_gap(precinct: str | None = None) -> bool:
    """No one may give final approval for the Precinct, or, with none
    given, for some Precinct."""
    return not final_for(precinct) if precinct else any(not final_for(p) for p in precincts())


def final_gaps() -> tuple[str, ...]:
    return tuple(p for p in precincts() if not final_for(p))


def final_precincts(person: str) -> tuple[str, ...]:
    return tuple(p for p in precincts() if person in final_for(p))


def decides_appeals(precinct: str) -> bool:
    """The Master decides a Precinct's appeals while in its slots, as an
    overseer is in every slot."""
    return in_slots(APPEAL_DECIDER, precinct)


def first_label() -> str:
    return " or ".join(POLICY["first_types"]) if POLICY["first"] == "slot" else "none"


def final_label(full: bool = False) -> str:
    """The final approvers as a phrase; `full` names a Unit appointment as
    Policy does, "Residential Admin (Admin)", rather than by its abbreviation."""
    if POLICY["final"] != "unit":
        return " or ".join(POLICY["final_names"])
    titles = {abbrev: title for title, abbrev in unit_appointments()}
    return " or ".join(
        f"{titles[t]} ({t})" if full and titles.get(t, t) != t else t for t in POLICY["final_types"]
    )


def final_decider(application: Application) -> str:
    """The sample's final approver on a decided application: the first who
    may give it for its Precinct."""
    return next(iter(final_for(application.precinct)), "the final approver")


# Cover is tracked beside the workflow, not as a stage of it: an
# application whose cover is unconfirmed waits at first approval (spec §11).
STAGES = (
    "Pending first approval",
    "Pending final approval",
    "Appeal to the Master",
    "Approved",
    "Rejected",
    "Withdrawn",
    # Approved, then cancelled: by an admin (spec §30, §21.4), or by the RA
    # before it begins (2026-11-10).
    "Cancelled",
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
        application recorded as awaiting it awaits final approval; an
        invited appeal awaiting the Master awaits final approval instead
        when the usual approvers decide it (a wired policy change moves the
        records themselves)."""
        if self.recorded == "Pending first approval" and POLICY["first"] == "none":
            return "Pending final approval"
        if self.recorded == "Appeal to the Master" and appeal_route() == "usual":
            return "Pending final approval"
        return self.recorded

    @property
    def appeal(self) -> bool:
        """An extra-leave appeal: decided by the Master, or by the usual
        approvers for an invited one when Policy says so (`appeal_route`),
        and kept apart from normal entitlement once granted (spec §7.5)."""
        return (
            self.recorded == "Appeal to the Master" or self.id in GRANTED_APPEALS | REJECTED_APPEALS
        )

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
    """ "28 Oct": the day without a leading zero, built by hand because
    `%-d` is glibc's and Windows' strftime refuses it."""
    return f"{day.day} {day.strftime('%b')}"


def _d(text: str) -> date:
    return date.fromisoformat(text)


#: An application's fields after its id; ``remarks`` is optional.
_ApplicationRow = tuple[str, str, date, date, str, str, str, date, *tuple[str, ...]]
_APPLICATION_ROWS: tuple[_ApplicationRow, ...] = (
    (
        "Chloe Lim",
        "Personal leave",
        _d("2026-11-06"),
        _d("2026-11-08"),
        "Ethan Wong",
        "Confirmed",
        "Pending first approval",
        _d("2026-10-27"),
    ),
    (
        "Isaac Goh",
        "Personal leave",
        _d("2026-11-12"),
        _d("2026-11-14"),
        "Kai Ng",
        "Awaiting",
        "Pending first approval",
        _d("2026-10-26"),
    ),
    (
        "Bella Koh",
        "Personal leave",
        _d("2026-10-30"),
        _d("2026-11-01"),
        "Cheng Hao Lin",
        "Confirmed",
        "Pending final approval",
        _d("2026-10-23"),
    ),
    (
        "Leon Chia",
        "Personal leave",
        _d("2026-12-01"),
        _d("2026-12-05"),
        "Mira Sato",
        "Confirmed",
        "Pending first approval",
        _d("2026-10-21"),
    ),
    # Cover not yet confirmed: the appeal waits for it, as ordinary leave
    # does (author, 2026-11-10).
    (
        "Gwen Ho",
        "Personal leave",
        _d("2026-11-20"),
        _d("2026-11-23"),
        "Elise Tan",
        "Awaiting",
        "Appeal to the Master",
        _d("2026-10-25"),
        "Balance exhausted; family wedding overseas.",
    ),
    (
        "Maya Seah",
        "Personal leave",
        _d("2026-10-27"),
        _d("2026-10-29"),
        "Lucas Teo",
        "Confirmed",
        "Approved",
        _d("2026-10-12"),
    ),
    (
        "Olivia Ng",
        "Personal leave",
        _d("2026-10-28"),
        _d("2026-10-30"),
        "Pranav Iyer",
        "Confirmed",
        "Approved",
        _d("2026-10-14"),
    ),
    (
        "Pranav Iyer",
        "Personal leave",
        _d("2026-10-29"),
        _d("2026-10-31"),
        "Qi Xuan Lim",
        "Confirmed",
        "Approved",
        _d("2026-10-15"),
    ),
    (
        "Hana Ito",
        "Official leave",
        _d("2026-11-02"),
        _d("2026-11-03"),
        "Chloe Lim",
        "Declined",
        "Pending first approval",
        _d("2026-10-24"),
    ),
    (
        "Faris Iskandar",
        "Personal leave",
        _d("2026-10-10"),
        _d("2026-10-11"),
        "Elise Tan",
        "Confirmed",
        "Rejected",
        _d("2026-10-02"),
    ),
    (
        "Ethan Wong",
        "Personal leave",
        _d("2026-10-17"),
        _d("2026-10-18"),
        "Hana Ito",
        "Confirmed",
        "Withdrawn",
        _d("2026-10-05"),
    ),
    (
        "Gwen Ho",
        "Personal leave",
        _d("2026-08-17"),
        _d("2026-08-19"),
        "Elise Tan",
        "Confirmed",
        "Approved",
        _d("2026-08-05"),
    ),
    (
        "Gwen Ho",
        "Personal leave",
        _d("2026-09-21"),
        _d("2026-09-22"),
        "Faris Iskandar",
        "Confirmed",
        "Approved",
        _d("2026-09-10"),
    ),
    # Chloe Lim, the RA pages' sample viewer, is asked to cover one
    # and has agreed to cover another.
    (
        "Ethan Wong",
        "Personal leave",
        _d("2026-12-04"),
        _d("2026-12-06"),
        "Chloe Lim",
        "Awaiting",
        "Pending first approval",
        _d("2026-10-27"),
    ),
    (
        "Hana Ito",
        "Personal leave",
        _d("2026-12-14"),
        _d("2026-12-15"),
        "Chloe Lim",
        "Confirmed",
        "Approved",
        _d("2026-10-20"),
    ),
    (
        "Kai Ng",
        "Personal leave",
        _d("2026-11-04"),
        _d("2026-11-05"),
        "Isaac Goh",
        "Confirmed",
        "Cancelled",
        _d("2026-10-08"),
    ),
    (
        "Chloe Lim",
        "Official leave",
        _d("2026-09-25"),
        _d("2026-09-25"),
        "Hana Ito",
        "Confirmed",
        "Approved",
        _d("2026-09-14"),
        "Representing the hall at the inter-hall games.",
    ),
    (
        "Lucas Teo",
        "Personal leave",
        _d("2026-09-07"),
        _d("2026-09-09"),
        "Maya Seah",
        "Confirmed",
        "Approved",
        _d("2026-08-28"),
        "Balance used; grandmother's funeral abroad.",
    ),
    # The leave that used Lucas Teo's balance before his appeal.
    (
        "Lucas Teo",
        "Personal leave",
        _d("2026-08-24"),
        _d("2026-08-28"),
        "Maya Seah",
        "Confirmed",
        "Approved",
        _d("2026-08-17"),
    ),
    # An appeal the Master refused (scenario I; audit, 2026-10-29).
    (
        "Maya Seah",
        "Personal leave",
        _d("2026-09-21"),
        _d("2026-09-27"),
        "Lucas Teo",
        "Confirmed",
        "Rejected",
        _d("2026-09-08"),
        "Seven days, two more than my five: a friend's wedding overseas.",
    ),
)


def _application(n: int, row: _ApplicationRow) -> Application:
    ra, leave_type, start, end, cover, cover_recorded, recorded, submitted, *remarks = row
    return Application(
        f"L-{n:04d}",
        ra,
        leave_type,
        start,
        end,
        cover,
        cover_recorded,
        recorded,
        submitted,
        *remarks,
    )


APPLICATIONS: tuple[Application, ...] = tuple(
    _application(n, row) for n, row in enumerate(_APPLICATION_ROWS, start=101)
)


GRANTED_APPEALS: frozenset[str] = frozenset({"L-0118"})  # extra leave the Master granted
REJECTED_APPEALS: frozenset[str] = frozenset({"L-0120"})  # an appeal the Master refused

# The sample's record of each decision: its date and remarks, by step
# (spec §14, §15, §19). Who decided is read from today's chain in
# `timeline`; a wired record keeps the person too.
DECISIONS: dict[str, dict[str, tuple[date, str]]] = {
    "L-0103": {
        "first": (_d("2026-10-24"), "Cover agreed; the Precinct is fully staffed that weekend.")
    },
    "L-0105": {
        "staff": (
            _d("2026-10-26"),
            "Gwen has taken extra duty nights this term; I support the appeal.",
        )
    },
    "L-0106": {"first": (_d("2026-10-13"), ""), "final": (_d("2026-10-14"), "")},
    "L-0107": {"first": (_d("2026-10-15"), ""), "final": (_d("2026-10-16"), "")},
    "L-0108": {
        "first": (_d("2026-10-16"), ""),
        "final": (_d("2026-10-19"), "Two of the Precinct are away on the 29th; cover is key."),
    },
    "L-0110": {
        "rejected": (
            _d("2026-10-05"),
            "Clashes with the Precinct's orientation duties that weekend.",
        )
    },
    "L-0111": {"withdrawn": (_d("2026-10-09"), "")},
    "L-0112": {"first": (_d("2026-08-06"), ""), "final": (_d("2026-08-07"), "")},
    "L-0113": {"first": (_d("2026-09-11"), ""), "final": (_d("2026-09-14"), "")},
    "L-0115": {"first": (_d("2026-10-21"), "Fine."), "final": (_d("2026-10-22"), "")},
    "L-0116": {
        "first": (_d("2026-10-09"), ""),
        "final": (_d("2026-10-12"), ""),
        "cancelled": (
            _d("2026-10-20"),
            "Kai Ng is leading the Precinct's November event; cancelled at his request.",
        ),
    },
    "L-0117": {
        "first": (_d("2026-09-15"), "Good luck at the games."),
        "final": (_d("2026-09-16"), ""),
    },
    "L-0119": {"first": (_d("2026-08-18"), ""), "final": (_d("2026-08-19"), "")},
    "L-0120": {
        "appeal": (
            _d("2026-09-11"),
            "The Precinct is short that week; take your five days, or apply in a quieter week.",
        )
    },
    "L-0118": {
        "staff": (_d("2026-08-29"), "Lucas has covered two extra weekends; I support it."),
        "appeal": (_d("2026-08-31"), "Granted, on the extra duties agreed with Arjun Nair."),
    },
}
CANCELLED_BY = "Rachel Yeo"  # the sample's Leave admin


def decision(application: Application, step: str) -> tuple[str, str]:
    """A recorded step's date, as shown, and remarks; blank when the sample
    keeps no record of it."""
    when, remarks = DECISIONS.get(application.id, {}).get(step, (None, ""))
    return (short_date(when) if when else "", remarks)


def _step(application: Application, step: str, what: str) -> tuple[str, str, str]:
    when, remarks = decision(application, step)
    return (when, what, remarks)


def history_steps(application: Application) -> tuple[tuple[str, str, str], ...]:
    """The decisions and closing actions on an application, as its timeline
    shows them under today's policy, for a history item (spec §19): each
    with its date and remarks."""
    return tuple(
        s
        for s in timeline(application)
        if not s[1].startswith(("Submitted", "Cover ", "Sent to", "Sent as"))
    )


def by_id(application_id: str) -> Application | None:
    return next((a for a in APPLICATIONS if a.id == application_id), None)


def stages(open_only: bool = False) -> tuple[str, ...]:
    """The stages the policy uses: no appeal stage while appeals are off,
    no first-approval stage when none is needed."""
    # Appeals off removes the route for new applications; an appeal already
    # made keeps its stage and is decided (author, 2026-10-28).
    skip: set[str] = set() if appeals_decided() else {"Appeal to the Master"}
    if POLICY["first"] == "none":
        skip.add("Pending first approval")
    return tuple(s for s in (OPEN_STAGES if open_only else STAGES) if s not in skip)


def pending_by_stage() -> tuple[tuple[str, int], ...]:
    return tuple(
        (stage, sum(1 for a in APPLICATIONS if a.stage == stage))
        for stage in stages(open_only=True)
    )


def cover_unconfirmed() -> tuple[Application, ...]:
    """Open applications whose cover has not confirmed (spec §25,
    outstanding cover confirmations)."""
    return tuple(
        a
        for a in APPLICATIONS
        if a.stage in OPEN_STAGES and a.cover_status != "Confirmed" and confirmation_needed(a)
    )


def upcoming() -> tuple[Application, ...]:
    """Approved leave starting after this week, to the term's end (spec
    §25, upcoming leave), soonest first."""
    after = date.fromordinal(TODAY.toordinal() + 6)
    return tuple(
        sorted(
            (a for a in APPLICATIONS if a.stage == "Approved" and after < a.start <= TERM.end),
            key=lambda a: a.start,
        )
    )


def extra_by_term() -> tuple[tuple[str, int, int], ...]:
    """Extra leave the Master granted, per term of the year: (term,
    appeals, days), kept apart from entitlement (spec §25, §7.5)."""
    granted = [a for a in APPLICATIONS if a.appeal and a.stage == "Approved"]
    return tuple(
        (
            t.label,
            sum(1 for a in granted if t.start <= a.start <= t.end),
            sum(appeal_split(a)["extra"] for a in granted if t.start <= a.start <= t.end),
        )
        for t in sample_data.TERMS
        if t.year == PERIOD_LABEL
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
    Correction(
        date(2026, 10, 20),
        "Rachel Yeo",
        "Cancelled approved leave for Kai Ng",
        "Leading the Precinct's November event; at his request",
        "L-0116",
    ),
    Correction(
        date(2026, 8, 3),
        "Rachel Yeo",
        "Adjusted Leon Chia's Personal leave by +2",
        "Days charged twice for one application",
    ),
)


def away_this_week() -> tuple[Application, ...]:
    """Approved leave overlapping the seven days from TODAY."""
    return away_between(*period()[2:])


# Leave records' period (the Precinct page until 2026-11-10; spec §22,
# "for a selected period"; author, 2026-10-29): a week from TODAY by
# default, the week after, four weeks from TODAY, or what is left of the
# term.
PERIODS = (
    ("last", "Last week"),
    ("week", "This week"),
    ("next", "Next week"),
    ("four", "These four weeks"),
    ("term", "Rest of term"),
    # Looking back, so taken, rejected and withdrawn leave can show on
    # Leave records too (the cold read, 2026-11-10).
    ("sofar", "Term so far"),
    ("whole", "Whole term"),
)


def period(key: str | None = None) -> tuple[str, str, date, date]:
    """A period's key, label and first and last days; an unknown key is
    this week."""
    key = key if key in dict(PERIODS) else "week"
    first = TODAY.toordinal()
    span = {"last": (-7, -1), "week": (0, 6), "next": (7, 13), "four": (0, 27)}.get(key)
    if span:
        start, end = date.fromordinal(first + span[0]), date.fromordinal(first + span[1])
    else:
        start = TERM.start if key in ("sofar", "whole") else TODAY
        end = TODAY if key == "sofar" else TERM.end
    return key, dict(PERIODS)[key], start, end


def away_between(start: date, end: date) -> tuple[Application, ...]:
    """Approved leave overlapping the days from start to end."""
    return tuple(
        a for a in APPLICATIONS if a.stage == "Approved" and a.start <= end and a.end >= start
    )


def clashes(
    start: date | None = None, end: date | None = None
) -> tuple[tuple[str, tuple[str, str]], ...]:
    """Each pair of RAs in one Precinct away on approved or pending leave on
    overlapping days, one row per pair; given a period, only pairs whose
    shared days fall in it."""
    live = [a for a in APPLICATIONS if a.stage in ("Approved", *OPEN_STAGES)]
    return tuple(
        (a.precinct, (a.ra, b.ra))
        for a in live
        for b in live
        if a.id < b.id
        and a.ra != b.ra
        and a.precinct == b.precinct
        and a.start <= b.end
        and b.start <= a.end
        and (
            start is None
            or end is None
            or max(a.start, b.start) <= end
            and min(a.end, b.end) >= start
        )
    )


@dataclass(frozen=True)
class Email:
    """An outbox row (spec §17.2): written first, then sent as the actor; a
    failed send stays here, and the actor or a Leave admin resends it."""

    application: str
    sender: str  # the actor, whose account sends it
    to: str
    about: str
    at: str
    status: str  # Sent, Failed
    why: str = ""


OUTBOX: tuple[Email, ...] = (
    Email("L-0101", "Chloe Lim", "Ethan Wong", "Cover asked", "27 Oct, 09:12", "Sent"),
    Email("L-0101", "Ethan Wong", "Chloe Lim", "Cover confirmed", "27 Oct, 11:30", "Sent"),
    Email(
        "L-0101",
        "Chloe Lim",
        "Daniel Koh",
        "Application submitted",
        "27 Oct, 09:12",
        "Failed",
        "Microsoft 365 did not accept the send: the sign-in had expired",
    ),
    Email(
        "L-0115",
        "Daniel Koh",
        "Hana Ito",
        "First approval",
        "21 Oct, 18:40",
        "Failed",
        "Microsoft 365 did not accept the send: the sign-in had expired",
    ),
    Email(
        "L-0116",
        "Rachel Yeo",
        "Kai Ng",
        "Approved leave cancelled",
        "20 Oct, 14:03",
        "Failed",
        "Microsoft 365 did not accept the send: no mailbox for the address",
    ),
    Email("L-0116", "Rachel Yeo", "Isaac Goh", "Cover released", "20 Oct, 14:03", "Sent"),
)


def emails_for(application: Application, sender: str | None = None) -> tuple[Email, ...]:
    """An application's outbox rows, or only those one actor sent."""
    return tuple(
        e for e in OUTBOX if e.application == application.id and sender in (None, e.sender)
    )


def failed_emails() -> tuple[Email, ...]:
    return tuple(e for e in OUTBOX if e.status == "Failed")


def cover_while_away() -> tuple[Application, ...]:
    """Applications whose cover is away themselves on overlapping dates."""
    live = [a for a in APPLICATIONS if a.stage in ("Approved", *OPEN_STAGES)]
    return tuple(
        a
        for a in live
        if any(b.ra == a.cover and b.start <= a.end and a.start <= b.end for b in live)
    )


# Adjustments for TERM: (RA, leave type) -> (adjustment, reason); a wired
# store keys them by term too.
ADJUSTMENTS = {
    ("Leon Chia", "Personal leave"): (
        2,
        "Correction: days charged twice for one application, 2026-08-03",
    ),
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


def entitlement(
    leave_type: LeaveType, appointment_start: date, term: sample_data.Term = TERM
) -> int:
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
        for t in sample_data.TERMS
        if t.year == term.year and t.number < term.number
    )
    return max(0, min(days, leave_type.cap - before))


def days_in_term(application: Application, term: sample_data.Term = TERM) -> int:
    """The application's days falling in the term: leave across a term's
    end is charged to each term for its own days."""
    first, last = max(application.start, term.start), min(application.end, term.end)
    return leave_days(first, last) if first <= last else 0


def entitlement_anomalies() -> tuple[tuple[EntitlementRow, str], ...]:
    """Entitlement rows to look at (spec §25): over entitlement, or an adjustment
    with no reason recorded."""
    found: list[tuple[EntitlementRow, str]] = []
    for r in entitlement_rows():
        if r["available"] < 0:
            found.append(
                (
                    r,
                    (
                        f"Over entitlement by {-r['available']} "
                        f"day{'s' if r['available'] != -1 else ''}, pending included"
                    ),
                )
            )
        elif r["adjustment"] and not r["reason"]:
            found.append((r, "Adjusted with no reason recorded"))
    return tuple(found)


def _appeal_charges() -> dict[str, int]:
    """How many of each live appeal's days its RA's own entitlement covers
    (§7.5): what the ordinary leave leaves, taken by appeals in the order
    they were made; the rest is extra leave. A wired record keeps the split
    it was decided with rather than working it out again."""
    charges: dict[str, int] = {}
    for ra in sample_data.RAS:
        start = date.fromisoformat(ra.dates.split()[0])
        for leave_type in LEAVE_TYPES:
            name = leave_type.name
            mine = [a for a in APPLICATIONS if a.ra == ra.name and a.leave_type == name]
            left = (
                entitlement(leave_type, start)
                + ADJUSTMENTS.get((ra.name, name), (0, ""))[0]
                - sum(
                    days_in_term(a)
                    for a in mine
                    if not a.appeal and (a.stage == "Approved" or a.stage in OPEN_STAGES)
                )
            )
            for a in sorted(
                (a for a in mine if a.appeal and (a.stage == "Approved" or a.stage in OPEN_STAGES)),
                key=lambda a: a.submitted,
            ):
                charges[a.id] = min(days_in_term(a), max(left, 0))
                left -= charges[a.id]
    return charges


class EntitlementRow(TypedDict):
    """An RA's entitlement for one leave type, and what is taken of it."""

    ra: str
    email: str
    type: str
    entitlement: int
    adjustment: int
    reason: str
    used: int
    pending: int
    available: int


def entitlement_rows() -> tuple[EntitlementRow, ...]:
    rows: list[EntitlementRow] = []
    charges = _appeal_charges()
    for ra in sample_data.RAS:
        start = date.fromisoformat(ra.dates.split()[0])
        for leave_type in LEAVE_TYPES:
            name, days = leave_type.name, entitlement(leave_type, start)
            adjustment, reason = ADJUSTMENTS.get((ra.name, name), (0, ""))
            mine = [a for a in APPLICATIONS if a.ra == ra.name and a.leave_type == name]
            # An appeal's own-days part is charged as ordinary leave is; its
            # extra part never touches the entitlement (§7.5).
            used = sum(charges.get(a.id, days_in_term(a)) for a in mine if a.stage == "Approved")
            pending = sum(
                charges.get(a.id, days_in_term(a)) for a in mine if a.stage in OPEN_STAGES
            )
            rows.append(
                {
                    "ra": ra.name,
                    "email": ra.email,
                    "type": name,
                    "entitlement": days,
                    "adjustment": adjustment,
                    "reason": reason,
                    "used": used,
                    "pending": pending,
                    "available": days + adjustment - used - pending,
                }
            )
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
    unfit: bool = False  # a delegate for its approver holds no place in these slots


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
        if self.start is None:
            return f"Until {short_date(self.end)}" if self.end else "Until removed"
        if self.end is None:
            return f"From {short_date(self.start)}"
        return f"{short_date(self.start)} – {short_date(self.end)}"


# A delegate holds a place in the slots they stand in for: here each
# Wing's RSLM (author, 2026-10-29).
DELEGATES = (
    Delegate("Grace Ho", "Marcus Tan", None, None, "has not signed in yet"),
    Delegate("Daniel Koh", "Priya Raman", date(2026, 12, 7), date(2026, 12, 18), "is on leave"),
)


def delegate_fits(d: Delegate) -> bool:
    """Whether a delegate holds a place in every slot of the person they
    stand in for; one who does not cannot approve there."""
    return all(
        d.delegate in s.staff or d.delegate in overseers()
        for s in sample_data.SLOTS
        if d.acting_for in s.staff
    )


def delegate_choices(person: str) -> list[str]:
    """Who may stand in for a person: staff holding a place in every slot
    they approve for (the overseers hold one in every slot)."""
    if not any(person in s.staff for s in sample_data.SLOTS):
        return []  # in no slot: no one stands in for them
    return [
        p.name
        for p in sample_data.STAFF
        if p.name != person and delegate_fits(Delegate(person, p.name, None, None, ""))
    ]


def delegable() -> list[str]:
    """Who a delegate may stand in for: the people on the slots holding an
    appointment the policy ticks for first approval; with no first approval,
    every slot approver, so a kept delegation still reads."""
    on_slots = {n for s in sample_data.SLOTS for n in s.staff}
    ticked = (
        POLICY["first_types"] if POLICY["first"] == "slot" else {a for _, a in slot_appointments()}
    )
    return [p.name for p in sample_data.STAFF if p.name in on_slots and p.abbrev in ticked]


def acting(person: str, day: date | None = None) -> Delegate | None:
    """The delegate standing in for a person on the day, if one fits."""
    day = day or TODAY
    return next(
        (d for d in DELEGATES if d.acting_for == person and d.active(day) and delegate_fits(d)),
        None,
    )


def routes(day: date | None = None) -> tuple[Route, ...]:
    """The approval chain per Precinct, derived from the current term's
    assignments and the policy's first approver, a delegate standing in for
    an approver whose delegation is active on the day (default TODAY)."""
    staff = {p.name: p for p in sample_data.STAFF}
    found: dict[str, Route] = {}
    for slot in sample_data.SLOTS:
        if slot.precinct in found:
            found[slot.precinct] = replace(
                found[slot.precinct], ras=found[slot.precinct].ras + len(slot.ras)
            )
            continue
        rf = next(n for n in slot.staff if staff[n].abbrev == "RF")
        rslm = next(n for n in slot.staff if staff[n].abbrev == "RSLM")
        by_type = {staff[n].abbrev: n for n in slot.staff}
        named = (
            [by_type[t] for t in POLICY["first_types"] if t in by_type]
            if POLICY["first"] == "slot"
            else []
        )
        standing_in = [d for n in named if (d := acting(n, day))]
        first = " or ".join(d.delegate if (d := acting(n, day)) else n for n in named)
        unfit = [
            d
            for n in named
            for d in DELEGATES
            if d.acting_for == n and d.active(day or TODAY) and not delegate_fits(d)
        ]
        note = "; ".join(
            [f"{d.acting_for} {d.reason}" for d in standing_in]
            + [f"{d.acting_for}'s delegate {d.delegate} is not in these slots" for d in unfit]
        )
        gap = POLICY["first"] == "slot" and not named
        if POLICY["first"] == "none":
            first = "None needed"
        elif gap:
            first, note = "No one", f"no {first_label()} on its slots"
        found[slot.precinct] = Route(
            slot.precinct,
            slot.wing,
            len(slot.ras),
            rf,
            rslm,
            first,
            bool(standing_in),
            note,
            gap,
            bool(unfit),
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
    if application.appeal and application.stage == "Pending final approval":
        # An invited appeal the usual approvers decide (author, 2026-11-10).
        steps.append(("", "Sent as an extra-leave appeal, to the usual approvers", ""))
        if "staff" in DECISIONS.get(application.id, {}):
            steps.append(_step(application, "staff", f"Remarks from {route.rf}, RF"))
        if appeal_takes_first():
            steps.append(_step(application, "first", f"First approval by {first}"))
        return tuple(steps)
    if application.appeal:
        if appeal_takes_first() and application.stage == "Appeal to the Master":
            steps.append(_step(application, "first", f"First approval by {first}"))
        decider = (
            APPEAL_DECIDER
            if decides_appeals(application.precinct)
            else "the Master (no one holds a place in these slots to decide it)"
        )
        steps.append(("", f"Sent to {decider} as an extra-leave appeal", ""))
        if "staff" in DECISIONS.get(application.id, {}):
            steps.append(_step(application, "staff", f"Remarks from {route.rf}, RF"))
        if application.stage in ("Approved", "Rejected"):
            verb = "Granted" if application.stage == "Approved" else "Rejected"
            steps.append(_step(application, "appeal", f"{verb} by {APPEAL_DECIDER}"))
        return tuple(steps)
    if (
        application.stage in ("Pending final approval", "Approved", "Cancelled")
        and POLICY["first"] == "slot"
    ):
        steps.append(_step(application, "first", f"First approval by {first}"))
    if application.stage in ("Approved", "Cancelled"):
        steps.append(_step(application, "final", f"Final approval by {final_decider(application)}"))
    if application.stage == "Rejected":
        who = first if POLICY["first"] == "slot" else final_decider(application)
        steps.append(_step(application, "rejected", f"Rejected by {who}"))
    if application.stage == "Withdrawn":
        steps.append(_step(application, "withdrawn", f"Withdrawn by {application.ra}"))
    if application.stage == "Cancelled":
        steps.append(
            _step(application, "cancelled", f"Cancelled by {CANCELLED_BY}, Residential Admin")
        )
    return tuple(steps)


# The RA pages (`/ra-leave/`) render for a sample viewer until identity is
# wired (segment 1C plan, "Viewing as"): Chloe Lim by default.
VIEWER = "Chloe Lim"
# The RA pages' sample viewers (`?as=`; audit, 2026-10-29), each reaching
# states Chloe Lim's applications do not. Extra leave is not shown to RAs
# by default (author, 2026-11-09), so the viewers there for it alone (an
# appeal with the Master, granted, refused) are gone; Kai Ng's invitation
# is the one way an RA reaches it.
RA_VIEWERS = (
    ("Chloe Lim", "cover asked of her, a draft, an email not sent"),
    ("Hana Ito", "her cover declined: name new cover"),
    ("Ethan Wong", "awaiting cover confirmation; a withdrawn application; a draft"),
    ("Faris Iskandar", "a rejected application"),
    ("Kai Ng", "approved leave cancelled; invited to apply for extra leave"),
)


def ra_viewer(name: str | None) -> str:
    """The RA pages' sample viewer: one of RA_VIEWERS, else Chloe Lim."""
    return name if name in dict(RA_VIEWERS) else VIEWER


@dataclass(frozen=True)
class Draft:
    """An application saved, not submitted (spec §11: Draft, then Pending
    first approval on submit). Ordinary leave only; an appeal's draft
    (§30, `APPEAL_DRAFT`) waits for the wiring. The RA's alone: no one is asked or told, and
    it counts against nothing, until it is submitted (author, 2026-10-29)."""

    id: str
    ra: str
    leave_type: str
    start: date
    end: date
    cover: str
    remarks: str
    saved: date

    @property
    def dates(self) -> str:
        return (
            short_date(self.start)
            if self.start == self.end
            else f"{short_date(self.start)} – {short_date(self.end)}"
        )

    @property
    def days(self) -> int:
        return leave_days(self.start, self.end)


DRAFTS: tuple[Draft, ...] = (
    Draft(
        "D-0001",
        "Chloe Lim",
        "Official leave",
        _d("2026-12-18"),
        _d("2026-12-20"),
        "Ethan Wong",
        "Hall games away fixture; dates to confirm.",
        _d("2026-10-26"),
    ),
    Draft(
        "D-0002",
        "Ethan Wong",
        "Personal leave",
        _d("2026-12-21"),
        _d("2026-12-22"),
        "Chloe Lim",
        "",
        _d("2026-10-27"),
    ),  # another RA's: not the sample viewer's to open
)


def my_drafts(ra: str = VIEWER) -> tuple[Draft, ...]:
    return tuple(d for d in DRAFTS if d.ra == ra)


def my_applications(ra: str = VIEWER) -> tuple[Application, ...]:
    return tuple(
        sorted((a for a in APPLICATIONS if a.ra == ra), key=lambda a: a.submitted, reverse=True)
    )


def my_balances(ra: str = VIEWER) -> tuple[EntitlementRow, ...]:
    return tuple(r for r in entitlement_rows() if r["ra"] == ra)


def my_extra(ra: str = VIEWER) -> dict[str, int]:
    """Extra leave, shown apart from entitlement (spec §8.1, §7.5)."""
    mine = [a for a in APPLICATIONS if a.ra == ra and a.appeal]
    return {
        "granted": sum(appeal_split(a)["extra"] for a in mine if a.stage == "Approved"),
        "pending": sum(appeal_split(a)["extra"] for a in mine if a.stage in OPEN_STAGES),
    }


def confirmation_needed(application: Application) -> bool:
    """Whether the cover must confirm: when the policy requires named and
    confirmed cover (§12), for an appeal as for ordinary leave (author,
    2026-11-10: the two are harmonized, with no override)."""
    del application  # one rule for every application
    return POLICY["cover_required"] and POLICY["cover_mode"] == "Named and confirmed"


def cover_asked(ra: str = VIEWER) -> dict[str, tuple[Application, ...]]:
    """Where an RA is named as cover (spec §23): to answer, covering now or
    to come (agreed, or named where no answer is owed), and the rest."""
    named = [
        a
        for a in APPLICATIONS
        if a.cover == ra and a.stage not in ("Rejected", "Withdrawn", "Cancelled")
    ]
    answer = tuple(
        a
        for a in named
        if a.cover_status == "Awaiting" and a.stage in OPEN_STAGES and confirmation_needed(a)
    )
    coming = tuple(
        a
        for a in named
        if a not in answer
        and a.end >= TODAY
        and (
            a.cover_status == "Confirmed"
            or (a.cover_status == "Awaiting" and not confirmation_needed(a))
        )
    )
    past = tuple(a for a in named if a not in answer and a not in coming)
    return {"answer": answer, "coming": coming, "past": past}


def cover_summary(ra: str = VIEWER) -> dict[str, int]:
    """The Cover page's summary (author, 2026-11-09): days an RA has
    covered, days they cover now or are to cover, and the requests to
    answer and declined. Days count cover agreed to, or named for where no
    answer is owed."""
    asked = cover_asked(ra)

    def agreed(a: Application) -> bool:
        return a.cover_status == "Confirmed" or (
            a.cover_status == "Awaiting" and not confirmation_needed(a)
        )

    return {
        "covered": sum(a.days for a in asked["past"] if agreed(a) and a.end < TODAY),
        "coming": sum(a.days for a in asked["coming"]),
        "to_answer": len(asked["answer"]),
        "declined": sum(1 for a in asked["past"] if a.cover_status == "Declined"),
    }


def cover_choices(ra: str = VIEWER) -> tuple[str, ...]:
    """Whom an RA may name as cover under the policy's pool, never
    themselves (spec §9.2)."""
    slot_of = {name: s for s in sample_data.SLOTS for name in s.ras}
    mine = slot_of[ra]
    level = {"Same Precinct": "precinct", "Same Wing": "wing"}.get(POLICY["cover_pool"])
    return tuple(
        name
        for s in sample_data.SLOTS
        for name in s.ras
        if name != ra and (level is None or getattr(s, level) == getattr(mine, level))
    )


# The staff pages (`/ra-leave/staff/`) render for a sample viewer chosen on
# the sample banner (`?as=`), one per role, until identity is wired.
# The sample's Residential Admin, whom the retired admin Appeals page now
# sends to the staff Appeals as (author, 2026-11-10).
SAMPLE_ADMIN = "Rachel Yeo"
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
    does: list[str] = []
    first = [r.precinct for r in routes() if not r.gap and name in r.first.split(" or ")]
    if first and POLICY["first"] == "slot":
        does.append("first approver for " + ", ".join(first))
    if final_precincts(name):
        mine = final_precincts(name)
        does.append(
            "final approver" + ("" if len(mine) == len(precincts()) else " for " + ", ".join(mine))
        )
    if (
        name == APPEAL_DECIDER
        and appeals_decided()
        and any(decides_appeals(p) for p in precincts())
    ):
        does.append("decides appeals")
    if POLICY["appeals"] == "By invitation" and invitable_ras(name):
        does.append("opens appeals")
    if not scope(name):
        if any(name in s.staff for s in sample_data.SLOTS):
            return f"{appointment}, no tick in Permissions, so RA Leave is not shown"
        return f"{appointment}, oversees no RA, so RA Leave is not shown"
    return (
        f"{appointment}, {', '.join(does)}"
        if does
        else f"{appointment}, no decisions under the policy"
    )


def staff_viewer(name: str | None) -> str:
    names = [n for n, _ in STAFF_VIEWERS]
    return name if name in names else names[0]


def first_decider_of(application: Application) -> str:
    """Who gave an application's first approval in the sample: the first
    named by its Precinct's chain today (a wired record keeps who did)."""
    return next(iter(routes_first(application)), "")


def first_by_cover(application: Application) -> str:
    """Who first approved an application in place of the RA's RF, a
    delegate or an ad hoc cover, or "" when the RF did or it has had no
    first approval (author, 2026-11-10: Records marks the odd case rather
    than carrying a column)."""
    if application.appeal or application.stage not in (
        "Pending final approval",
        "Approved",
        "Cancelled",
    ):
        return ""
    who = first_decider_of(application)
    return who if who and who != rf_of(application) else ""


def queue(viewer: str) -> tuple[tuple[Application, str], ...]:
    """What awaits the viewer's decision, oldest first (spec §16, §24), with
    the decision it needs."""
    found: list[tuple[Application, str]] = []
    for a in APPLICATIONS:
        if a.stage == "Pending first approval" and viewer in routes_first(a):
            found.append((a, "First approval"))
        elif a.stage == "Pending final approval" and viewer in final_for(a.precinct):
            found.append((a, "Final approval"))
        elif (
            a.stage == "Appeal to the Master"
            and viewer == APPEAL_DECIDER
            and decides_appeals(a.precinct)
        ):
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
    found: list[tuple[Application, str, str]] = []
    for a in APPLICATIONS:
        if a.appeal and a.stage != "Pending final approval":
            if (
                viewer == APPEAL_DECIDER
                and decides_appeals(a.precinct)
                and a.stage in ("Approved", "Rejected")
            ):
                found.append((a, "Appeal", a.stage))
            continue
        if (
            a.stage in ("Pending final approval", "Approved", "Cancelled")
            and first_decider_of(a) == viewer
        ):
            found.append((a, "First approval", "Approved"))
        if a.stage == "Rejected" and first_decider_of(a) == viewer:
            found.append((a, "First approval", "Rejected"))
        if a.stage == "Rejected" and POLICY["first"] == "none" and final_decider(a) == viewer:
            found.append((a, "Final approval", "Rejected"))
        if a.stage in ("Approved", "Cancelled") and final_decider(a) == viewer:
            found.append((a, "Final approval", "Approved"))
    return tuple(sorted(found, key=lambda t: t[0].submitted, reverse=True))


def overseers() -> tuple[str, ...]:
    """Who oversees every RA: those in every slot for the term, set on
    Assignments (author, 2026-10-29)."""
    return sample_data.every_slot_people(TERM)


def scope(viewer: str) -> tuple[str, ...]:
    """The Precincts whose RAs a staff member oversees (spec §22; author,
    2026-10-29): the overseers every one, as if in every slot; an RF their
    slots' Precincts, an RSLM their Wing's if Permissions gives one a tick
    (none by default). Decisions stay confined to slots (`in_slots`); a
    delegate standing in as first approver, or the Master while deciding
    appeals, sees their own scope without a tick (`_standing_in`). Staff
    with none, such as Unit-level staff holding no slot, see no RA Leave.

    Permissions decide who sees any (author, 2026-11-10): staff with no
    tick but Admin pages see none, and a person named there adds the
    Precincts their chosen scope holds (a slot widens to its Precinct, as
    the sample keeps scope by Precinct)."""
    every = precincts()
    named = set(_named_precincts(viewer))
    if not (_granted(viewer) - {"admin"}) and not _standing_in(viewer):
        # No tick of their own: only what a named grant holds (cold read).
        return tuple(p for p in every if p in named)
    if viewer in overseers():
        return every
    abbrev = {p.name: p.abbrev for p in sample_data.STAFF}.get(viewer)
    held = [s for s in sample_data.SLOTS if viewer in s.staff]
    wings = {s.wing for s in held if abbrev == "RSLM"}
    found = {s.precinct for s in held} | {s.precinct for s in sample_data.SLOTS if s.wing in wings}
    return tuple(p for p in every if p in found | named)


def _standing_in(name: str) -> bool:
    """Who has RA Leave without a Permissions tick (2026-11-10): a delegate
    standing in as first approver today (Approval chain), and the Master
    while deciding appeals (who decides is the Appeals card's, so it is no
    column of Permissions)."""
    delegate = POLICY["first"] == "slot" and any(
        name in r.first.split(" or ") for r in routes() if not r.gap
    )
    return delegate or (appeals_decided() and name == APPEAL_DECIDER)


def _named_precincts(name: str) -> tuple[str, ...]:
    """The Precincts a person's named grants hold: All RAs every one, a
    Wing its Precincts, a Precinct itself, a slot its Precinct."""
    chosen = {
        c
        for g in NAMED_GRANTS
        if g.name == name and g.perms - {"admin"}
        for c in resolve_scope(g.scope)
    }
    return tuple(
        dict.fromkeys(
            s.precinct
            for s in sample_data.SLOTS
            if chosen & {SCOPE_ALL, s.wing, s.precinct, s.neighborhood}
        )
    )


def can_open(viewer: str, application: Application) -> bool:
    """Decide opens an application in the viewer's scope, or one that is
    (or was) theirs to decide or open an appeal for; every such role is
    confined to the slots the viewer holds a place in, so these agree."""
    return (
        application.precinct in scope(viewer)
        or application.ra in invitable_ras(viewer)
        or any(a.id == application.id for a, _ in queue(viewer))
        or any(a.id == application.id for a, _, _ in decided(viewer))
    )


def other_leave(application: Application) -> tuple[Application, ...]:
    """The applicant's other applications this term, for the decider (spec
    §15): leave days go with their term."""
    return tuple(
        a
        for a in APPLICATIONS
        if a.ra == application.ra
        and a.id != application.id
        and a.start <= TERM.end
        and a.end >= TERM.start
    )


class PrecinctStrength(TypedDict):
    """A Precinct's establishment strength and, over a period, how many of
    its days it stood at full strength, one down, two down, and three or
    more down."""

    precinct: str
    ras: int
    days: tuple[int, int, int, int]


# What Leave records' Summary counts as an RA down on a day (author,
# 2026-11-10), each a chip: approved leave on a day up to today, approved
# leave on a day after it, and an application not yet decided.
STRENGTH_COUNTS = ("Leave taken", "Leave approved", "Leave approval pending")
# Which days the Summary counts (author, 2026-11-10), each a chip:
# Monday to Friday, and Saturday and Sunday.
STRENGTH_DAYS = ("Weekdays", "Weekends")


def day_kind(day: date) -> str:
    """Which of `STRENGTH_DAYS` a day is."""
    return "Weekends" if day.isoweekday() > 5 else "Weekdays"


def strength_kind(application: Application, day: date) -> str:
    """Which of `STRENGTH_COUNTS` an application's day is: taken up to and
    including today, approved after it; pending while undecided, an appeal
    awaiting the Master included (author, 2026-11-10: once the invitation is
    given it counts as normal leave); none for a decided one not approved."""
    if application.stage == "Approved":
        return "Leave taken" if day <= TODAY else "Leave approved"
    return "Leave approval pending" if application.stage in OPEN_STAGES else ""


def by_precinct(
    viewer: str,
    start: date | None = None,
    end: date | None = None,
    hidden: frozenset[str] = frozenset(),
) -> tuple[PrecinctStrength, ...]:
    """Leave records' Summary (author, 2026-11-10): per Precinct in the
    viewer's scope, its establishment strength and, day by day over the
    period (this week without both ends), how many days it stood at full
    strength, one, two, and three or more RAs down. An RA is down on a day
    their leave covers, counting only the kinds of `STRENGTH_COUNTS` not in
    `hidden`; an RA with two applications that day is down once. Only the
    days of `STRENGTH_DAYS` not in `hidden` are counted at all."""
    if not (start and end):
        start, end = period()[2:]
    live = [a for a in APPLICATIONS if a.stage == "Approved" or a.stage in OPEN_STAGES]
    rows: list[PrecinctStrength] = []
    for p in scope(viewer):
        mine = [a for a in live if a.precinct == p and a.start <= end and a.end >= start]
        days = [0, 0, 0, 0]
        day = start
        while day <= end:
            if day_kind(day) in hidden:
                day += timedelta(days=1)
                continue
            down = {
                a.ra
                for a in mine
                if a.start <= day <= a.end and strength_kind(a, day) not in hidden | {""}
            }
            days[min(len(down), 3)] += 1
            day += timedelta(days=1)
        rows.append(
            {
                "precinct": p,
                "ras": sum(len(s.ras) for s in sample_data.SLOTS if s.precinct == p),
                "days": (days[0], days[1], days[2], days[3]),
            }
        )
    return tuple(rows)


def strength_hidden(value: str | None) -> frozenset[str]:
    """The Summary's chips turned off, from `?uncount=`: what counts as
    down, and which days."""
    known = set(STRENGTH_COUNTS) | set(STRENGTH_DAYS)
    return frozenset(v for v in (value or "").split(",") if v in known)


def counted_days(start: date, end: date, hidden: frozenset[str]) -> int:
    """How many of the period's days the Summary counts."""
    return sum(
        1
        for n in range((end - start).days + 1)
        if day_kind(start + timedelta(days=n)) not in hidden
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
        b
        for b in live
        if b.id != application.id
        and b.ra != application.ra
        and b.precinct == application.precinct
        and b.start <= application.end
        and application.start <= b.end
    )


def appeal_split(application: Application) -> dict[str, int]:
    """An appeal's days split as §7.5 keeps them: what the RA's own
    entitlement covers is charged to it, the rest is extra leave."""
    charged = _appeal_charges().get(application.id, 0)
    return {"charged": charged, "extra": application.days - charged}


def blackouts_on(application: Application) -> tuple[tuple[Blackout, date, date], ...]:
    """The blackouts an application's dates touch, with their dates (§6)."""
    found: list[tuple[Blackout, date, date]] = []
    for b in BLACKOUTS:
        span = week_dates(b)
        if span and span[0] <= application.end and span[1] >= application.start:
            found.append((b, *span))
    return tuple(found)


def approvers_for(ra: str) -> str:
    """Who decides an RA's ordinary leave, in order, as Apply names them
    (§9.1; audit, 2026-10-29): the slot's first approver, then the final."""
    precinct = next(s.precinct for s in sample_data.SLOTS if ra in s.ras)
    route = next(r for r in routes() if r.precinct == precinct)
    final = (
        " or ".join(final_for(precinct))
        or "no final approver yet (none holds a place in your slot)"
    )
    if POLICY["first"] == "none":
        return final
    first = "the first approver (none named yet)" if route.gap else route.first
    return f"{first}, then {final}"


def term_blackouts() -> tuple[tuple[Blackout, date, date], ...]:
    """This term's blackouts not yet over, with their dates (§6)."""
    found: list[tuple[Blackout, date, date]] = []
    for b in BLACKOUTS:
        span = week_dates(b, PERIOD_LABEL)
        if span and span[0] <= TERM.end and span[1] >= max(TERM.start, TODAY):
            found.append((b, *span))
    return tuple(found)


class DateCheck(TypedDict):
    """What Apply and Request extra leave show under Days of leave, and
    whether the form may be sent (author, 2026-11-09)."""

    days: int | None
    message: str
    ok: bool


def own_leave_between(name: str, first: date, last: date) -> Application | None:
    """An RA's leave, approved or asked for, touching the days given: they
    cannot cover anyone then (author, 2026-11-10)."""
    return next(
        (
            a
            for a in sorted(APPLICATIONS, key=lambda a: a.start)
            if a.ra == name
            and (a.stage == "Approved" or a.stage in OPEN_STAGES)
            and a.start <= last
            and a.end >= first
        ),
        None,
    )


def covering_between(name: str, first: date, last: date) -> Application | None:
    """Leave an RA covers, agreed or named, touching the days given: they
    cannot be on leave then (author, 2026-11-10)."""
    return next(
        (
            a
            for a in sorted(APPLICATIONS, key=lambda a: a.start)
            if a.cover == name
            and (a.stage == "Approved" or a.stage in OPEN_STAGES)
            and a.cover_status not in ("Declined", "Cancelled")
            and a.start <= last
            and a.end >= first
        ),
        None,
    )


def away_between_names(first: date, last: date) -> tuple[str, ...]:
    """Every RA with leave, approved or asked for, touching the days given:
    none of them may be named as cover for those days."""
    return tuple(
        sorted(
            {
                a.ra
                for a in APPLICATIONS
                if (a.stage == "Approved" or a.stage in OPEN_STAGES)
                and a.start <= last
                and a.end >= first
            }
        )
    )


def check_dates(
    ra: str,
    leave_type: str,
    first: date | None,
    last: date | None,
    appeal: bool = False,
    cover: str = "",
) -> DateCheck:
    """Check an application as the RA keys it in (author, 2026-11-09; spec
    §10): a known leave type, both dates chosen, in order, not past, within
    this term, clear of the RA's own leave, clear of leave the RA covers
    and, given a cover, clear of the cover's own leave (author,
    2026-11-10), counting a day, clear of a Refused blackout and within
    the balance. Where the RA may appeal, an
    Appeal-only blackout or more than the balance still submits, as an
    appeal or by offering Request extra leave (author, 2026-10-29; §7.2
    "should not simply block"), so the message is a note, not a refusal;
    on the appeal page itself it needs no note (§7)."""
    if leave_type not in {lt.name for lt in LEAVE_TYPES}:
        return {"days": None, "message": "Choose a leave type.", "ok": False}
    if first is None or last is None:
        return {"days": None, "message": "Choose your dates.", "ok": False}
    if last < first:
        return {"days": None, "message": "The last day is before the first day.", "ok": False}

    def no(message: str, days: int | None = None) -> DateCheck:
        return {"days": days, "message": message, "ok": False}

    if first < TODAY:
        return no("The first day has passed.")
    if first < TERM.start or last > TERM.end:
        return no(
            f"Leave falls within {TERM.label}: {short_date(TERM.start)} – {short_date(TERM.end)}."
        )
    clash = next(
        (
            a
            for a in my_applications(ra)
            if (a.stage in OPEN_STAGES or a.stage == "Approved")
            and a.start <= last
            and a.end >= first
        ),
        None,
    )
    if clash is not None:
        return no(f"These dates overlap your leave of {clash.dates} ({clash.stage.lower()}).")
    # No one is on leave while covering, nor covers while on leave (author,
    # 2026-11-10: "You can't be on leave if you are covering").
    covering = covering_between(ra, first, last)
    if covering is not None:
        return no(
            f"You are covering {covering.ra} on {covering.dates}: you cannot be on leave then."
        )
    if cover:
        away = own_leave_between(cover, first, last)
        if away is not None:
            return no(
                f"{cover} is on leave, or has asked to be, on {away.dates}: name another cover."
            )
    days = leave_days(first, last)
    if days == 0:
        return no("These dates count no days of leave.", 0)
    may_appeal = appeal or can_appeal(ra)
    note = ""
    for b in BLACKOUTS:
        span = week_dates(b, PERIOD_LABEL)
        if not span or span[0] > last or span[1] < first:
            continue
        when = f"{b.label}, {short_date(span[0])} – {short_date(span[1])}"
        if b.effect == "Refused" or not may_appeal:
            return no(f"These dates fall in a blackout ({when}): no leave.", days)
        if not appeal:
            who = appeal_decider_name()
            note = (
                f"These dates fall in an Appeal-only blackout ({when}): submitting sends "
                f"it to {who} as an appeal, which {who} decide"
                f"{'s' if who == 'the Master' else ''} at discretion."
            )
    available = max(next(r["available"] for r in my_balances(ra) if r["type"] == leave_type), 0)
    short = days - available
    if short > 0 and not appeal:
        plural = "s" if short != 1 else ""
        over = f"{short} day{plural} more than your {leave_type} ({available} available)"
        if not may_appeal:
            return no(f"{over}: shorten it.", days)
        who = appeal_decider_name()
        note = note or (
            f"{over}: submitting offers Request extra leave, which {who} decide"
            f"{'s' if who == 'the Master' else ''} at discretion."
        )
    return {"days": days, "message": note, "ok": True}


def draft_short(draft: Draft) -> int:
    """How many days a draft asks beyond what the RA has of its type; 0 when
    it fits (§10, scenario G)."""
    available = next(
        r["available"]
        for r in entitlement_rows()
        if r["ra"] == draft.ra and r["type"] == draft.leave_type
    )
    return max(draft.days - max(available, 0), 0)


def away_today(viewer: str) -> tuple[Application, ...]:
    """Staff Home's This week (author, 2026-11-09): approved leave covering
    today, in the viewer's scope."""
    return tuple(a for a in away_between(TODAY, TODAY) if a.precinct in scope(viewer))


def later_this_week(viewer: str) -> tuple[Application, ...]:
    """Staff Home's Later this week (author, 2026-11-09): approved leave
    starting from tomorrow to the end of the week's seven days, in the
    viewer's scope, soonest first."""
    _, _, _, last = period("week")
    return tuple(
        sorted(
            (
                a
                for a in away_between(TODAY, last)
                if a.start > TODAY and a.precinct in scope(viewer)
            ),
            key=lambda a: a.start,
        )
    )


class CalendarDay(TypedDict):
    """One day of staff Home's leave calendar (author, 2026-11-09)."""

    day: date
    in_month: bool
    today: bool
    leave: tuple[tuple[Application, bool], ...]  # (application, approved)
    blackout: str  # the blackout's label, or ""


def month_of(value: str | None) -> date:
    """A `YYYY-MM` query value as the month's first day; anything else, or
    a year more than 50 from today's (the calendar pads to whole weeks and
    steps a month either way, so the far ends of the calendar must not be
    reached), is this month."""
    try:
        year, month = (int(part) for part in (value or "").split("-"))
        if abs(year - TODAY.year) > 50:
            raise ValueError(year)
        return date(year, month, 1)
    except ValueError:
        return TODAY.replace(day=1)


def shift_month(first: date, by: int) -> date:
    """The first day of the month `by` months from `first`'s."""
    n = first.year * 12 + first.month - 1 + by
    return date(n // 12, n % 12 + 1, 1)


CALENDAR_STATUSES = ("Approved", "Pending")


def calendar_wings(viewer: str) -> tuple[str, ...]:
    """The Wings a viewer's calendar filters by (author, 2026-11-10): one
    chip a Wing when the viewer's scope spans the whole Unit; none for an RF
    or an RSLM, whose scope is a Precinct or one Wing."""
    precincts = set(scope(viewer))
    unit = {s.precinct for s in sample_data.SLOTS}
    if not precincts or precincts != unit:
        return ()
    return tuple(sorted({s.wing for s in sample_data.SLOTS}))


def calendar_hidden(viewer: str, value: str | None) -> frozenset[str]:
    """The calendar filters turned off, from `?hide=` (a comma list): only
    the viewer's own chips count, so a stray or another scope's value is
    dropped."""
    known = set(CALENDAR_STATUSES) | set(calendar_wings(viewer))
    return frozenset(v for v in (value or "").split(",") if v in known)


def calendar_filters(viewer: str, hidden: frozenset[str]) -> tuple[tuple[str, bool, str], ...]:
    """Each calendar chip as (label, on, the `hide` value its link sets):
    Approved and Pending, then a Wing each for a whole-Unit viewer. The
    link toggles its own chip and keeps the others as they are."""
    return toggle_filters(CALENDAR_STATUSES + calendar_wings(viewer), hidden)


def toggle_filters(
    labels: tuple[str, ...], hidden: frozenset[str]
) -> tuple[tuple[str, bool, str], ...]:
    """On/off chips as (label, on, the `hide` value its link sets): each
    link toggles its own chip and keeps the others as they are, `hide`
    written sorted so one state has one form."""
    return tuple(
        (
            label,
            label not in hidden,
            ",".join(sorted(x for x in labels if (x in hidden) != (x == label))),
        )
        for label in labels
    )


def leave_calendar(
    viewer: str, first: date, hidden: frozenset[str] = frozenset()
) -> tuple[tuple[CalendarDay, ...], ...]:
    """Staff Home's leave calendar (author, 2026-11-09): the month's weeks,
    Sunday to Saturday, each day with the approved and pending leave of RAs
    in the viewer's scope, appeals awaiting the Master left off, and the
    blackout it falls in. `hidden` names the filters turned off (author,
    2026-11-10): Approved, Pending, or a Wing."""
    wing_of = {s.precinct: s.wing for s in sample_data.SLOTS}
    last = shift_month(first, 1) - timedelta(days=1)
    start = first - timedelta(days=first.isoweekday() % 7)
    end = last + timedelta(days=6 - last.isoweekday() % 7)
    live = [
        a
        for a in APPLICATIONS
        # Open appeals stay off (author, 2026-11-09), wherever they wait;
        # one granted is approved leave like any other.
        if (a.stage == "Approved" or (a.stage in OPEN_STAGES and not a.appeal))
        and a.precinct in scope(viewer)
        and a.start <= end
        and a.end >= start
        and ("Approved" if a.stage == "Approved" else "Pending") not in hidden
        and wing_of.get(a.precinct) not in hidden
    ]
    # Every academic year's blackouts, so a month in another year shows its own.
    years = sorted({t.year for t in sample_data.TERMS})
    spans = [(b.label, week_dates(b, year)) for b in BLACKOUTS for year in years]
    days: list[CalendarDay] = []
    day = start
    while day <= end:
        days.append(
            {
                "day": day,
                "in_month": day.month == first.month,
                "today": day == TODAY,
                "leave": tuple(
                    (a, a.stage == "Approved")
                    for a in sorted(live, key=lambda a: (a.start, a.ra))
                    if a.start <= day <= a.end
                ),
                "blackout": next(
                    (label for label, span in spans if span and span[0] <= day <= span[1]), ""
                ),
            }
        )
        day += timedelta(days=1)
    return tuple(tuple(days[i : i + 7]) for i in range(0, len(days), 7))


def month_blackouts(first: date) -> tuple[tuple[str, date, date], ...]:
    """The blackouts a calendar month touches, any academic year's, with
    their dates, named in one line under the calendar."""
    last = shift_month(first, 1) - timedelta(days=1)
    years = sorted({t.year for t in sample_data.TERMS})
    return tuple(
        (b.label, *span)
        for b in BLACKOUTS
        for year in years
        if (span := week_dates(b, year)) and span[0] <= last and span[1] >= first
    )


def calendar_has_leave(weeks: tuple[tuple[CalendarDay, ...], ...]) -> bool:
    """Whether any day of the calendar's own month has leave."""
    return any(c["leave"] for week in weeks for c in week if c["in_month"])


def balance_of(application: Application) -> EntitlementRow:
    return next(
        r
        for r in entitlement_rows()
        if r["ra"] == application.ra and r["type"] == application.leave_type
    )


def waiting_on_cover_count(viewer: str) -> int:
    return sum(1 for a, _ in queue(viewer) if waiting_on_cover(a))


def appeals_on() -> bool:
    """Whether the system has appeals at all: open, or by invitation."""
    return POLICY["appeals"] != "Off"


def appeal_route() -> str:
    """How an appeal is decided (author, 2026-11-10): "usual", by the
    usual first and final approvers, only for an appeal by invitation
    with Policy's choice so; otherwise "master", the Master deciding,
    after the usual first approver for an invited appeal."""
    invited = POLICY["appeals"] == "By invitation"
    return "usual" if invited and POLICY["appeal_approval"] == "usual" else "master"


def appeal_takes_first() -> bool:
    """Whether an appeal takes the usual first approval before its
    decider: an invited appeal, under a policy that has a first
    approver (with none, either choice skips that step)."""
    return POLICY["appeals"] == "By invitation" and POLICY["first"] == "slot"


def appeal_deciders() -> str:
    """Who decides appeals, in a few words, for the Dashboard's Policy summary."""
    if not appeals_on():
        return "Off"
    master = f"the Master ({APPEAL_DECIDER}), personally"
    if appeal_route() == "usual":
        return "The usual first and final approvers"
    if appeal_takes_first():
        return "The usual first approver, then " + master
    return master[0].upper() + master[1:]


# Leave records' statuses (author, 2026-11-10), in the order of their
# chips, the author's order: approved leave split by where today falls,
# then each stage.
RECORD_STATUSES = (
    "On leave",
    "Approved",
    "Taken",
    "Pending first approval",
    "Pending final approval",
    "Rejected",
    "Appeal to the Master",
    "Withdrawn",
    "Cancelled",
)


def record_status(application: Application) -> str:
    """An application's status on Leave records: approved leave is On leave
    while today falls in it, Approved while still to come, Taken once past;
    any other its stage."""
    if application.stage == "Approved":
        if application.end < TODAY:
            return "Taken"
        return "On leave" if application.start <= TODAY else "Approved"
    return application.stage


def record_statuses() -> tuple[str, ...]:
    """The status chips the policy uses: no appeal chip while appeals are
    not decided, no first-approval chip when none is needed (`stages`)."""
    used = set(stages())
    return tuple(s for s in RECORD_STATUSES if s not in STAGES or s in used)


# Leave records' Cover chips (author, 2026-11-10), one per cover status,
# named apart from the status chips (a Cancelled stage, a released cover).
COVER_CHIPS = {
    "Confirmed": "Cover confirmed",
    "Awaiting": "Cover awaiting",
    "Declined": "Cover declined",
    "Cancelled": "Cover released",
}


def records_scope(viewer: str | None) -> tuple[str, ...]:
    """The Precincts Leave records covers: a staff member's scope, or the
    whole Unit on the admin's Leave records (viewer None)."""
    return precincts() if viewer is None else scope(viewer)


def record_precincts(viewer: str | None) -> tuple[str, ...]:
    """The Precinct chips on Leave records: one each where the page covers
    more than one Precinct (author, 2026-11-10); none for one."""
    covered = records_scope(viewer)
    return covered if len(covered) > 1 else ()


def records_hidden(viewer: str | None, value: str | None) -> frozenset[str]:
    """Leave records' filters turned off, from `?hide=`: only the page's
    own chips count."""
    known = set(record_statuses()) | set(COVER_CHIPS.values()) | set(record_precincts(viewer))
    return frozenset(v for v in (value or "").split(",") if v in known)


def record_filters(viewer: str | None, hidden: frozenset[str]) -> tuple[tuple[str, bool, str], ...]:
    """Leave records' chips: each status, each cover status, then each
    Precinct where there is more than one."""
    labels = record_statuses() + tuple(COVER_CHIPS.values()) + record_precincts(viewer)
    return toggle_filters(labels, hidden)


class FilterGroup(TypedDict):
    """One row of Leave records' chips, with its Select all and Clear all
    links' `hide` values."""

    name: str
    chips: tuple[tuple[str, bool, str], ...]
    select_all: str
    clear_all: str


def record_groups(viewer: str | None, hidden: frozenset[str]) -> tuple[FilterGroup, ...]:
    """Leave records' chips in groups (author, 2026-11-10): Status, Cover,
    then Precinct where there is more than one, each ending in Select all
    and Clear all, which turn that group's chips all on or all off and keep
    the other groups' as they are."""
    chips = record_filters(viewer, hidden)
    groups: list[FilterGroup] = []
    for name, labels in (
        ("Status", record_statuses()),
        ("Cover", tuple(COVER_CHIPS.values())),
        ("Precinct", record_precincts(viewer)),
    ):
        if not labels:
            continue
        group = set(labels)
        groups.append(
            {
                "name": name,
                "chips": tuple(c for c in chips if c[0] in group),
                "select_all": ",".join(sorted(hidden - group)),
                "clear_all": ",".join(sorted(hidden | group)),
            }
        )
    return tuple(groups)


def records_hide_except(*kept: str) -> str:
    """A `hide` value that leaves only the chips named on, the rest of
    their groups off: the admin dashboard's links into Leave records."""
    groups = (record_statuses(), tuple(COVER_CHIPS.values()))
    off = [label for g in groups if any(k in g for k in kept) for label in g if label not in kept]
    return ",".join(sorted(off))


def records(
    viewer: str | None, start: date, end: date, hidden: frozenset[str] = frozenset()
) -> tuple[tuple[Application, str], ...]:
    """Leave records' table (author, 2026-11-10): every application in the
    page's scope whose dates touch the period, whatever its stage, with its
    status, soonest first; the filters turned off left out."""
    covered = records_scope(viewer)
    return tuple(
        (a, record_status(a))
        for a in sorted(APPLICATIONS, key=lambda a: (a.start, a.ra))
        if a.precinct in covered
        and a.start <= end
        and a.end >= start
        and record_status(a) not in hidden
        and COVER_CHIPS.get(a.cover_status, "") not in hidden
        and a.precinct not in hidden
    )


# The longest From–To range Leave records takes: two years, the Summary
# counting each day of it (the cold read, 2026-11-10).
MAX_RANGE_DAYS = 731


def period_range(
    key: str | None, start: str | None, end: str | None, default: str = "week"
) -> tuple[str, str, date, date]:
    """Leave records' period (author, 2026-11-10): one of `PERIODS`
    (`default` when none is named), or, when the period is "custom" or
    none is named, the From and To dates given, when both parse, run
    forwards and span at most `MAX_RANGE_DAYS`. A named period wins over
    dates sent with it, so the form works without scripts."""
    if key not in (None, "", "custom"):
        return period(key)
    try:
        first, last = date.fromisoformat(start or ""), date.fromisoformat(end or "")
    except ValueError:
        return period(default)
    if first > last or (last - first).days >= MAX_RANGE_DAYS:
        return period(default)
    return "custom", f"{short_date(first)} – {short_date(last)}", first, last


def is_rf(viewer: str) -> bool:
    """Whether a staff member's appointment is RF."""
    return next((s.abbrev for s in sample_data.STAFF if s.name == viewer), "") == "RF"


def sees_appeals(viewer: str) -> bool:
    """Whether a staff member has the Appeals tab: while appeals are on,
    or one made before is still decided, for everyone but an RF (author,
    2026-11-09), whose appeals are not theirs to decide or open. Under the
    usual approvers it stays, for opening invitations (2026-11-10)."""
    return (appeals_on() or appeals_decided()) and not is_rf(viewer)


def appeals_decided() -> bool:
    """Whether the Master still decides appeals: while they are on and
    the Master decides them (`appeal_route`), or while one is open before
    the Master (author, 2026-10-28: existing appeals stand)."""
    master = appeals_on() and appeal_route() == "master"
    return master or any(a.stage == "Appeal to the Master" for a in APPLICATIONS)


def open_appeals() -> tuple[Application, ...]:
    """Appeals not yet decided, wherever they wait (author, 2026-11-10)."""
    return tuple(a for a in APPLICATIONS if a.appeal and a.stage in OPEN_STAGES)


def appeal_decider_name() -> str:
    """Who decides a new appeal, for the RA's and staff's copy."""
    return "the usual approvers" if appeal_route() == "usual" else "the Master"


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
    Invitation(
        "Gwen Ho",
        "Sam Lee",
        date(2026, 10, 24),
        date(2026, 11, 7),
        "Family wedding overseas; agreed in principle",
        "L-0105",
    ),
    Invitation(
        "Kai Ng",
        "Rachel Yeo",
        date(2026, 10, 27),
        date(2026, 11, 10),
        "Sibling's graduation abroad; agreed in principle",
    ),
    Invitation(
        "Nathan Yeo",
        "Sam Lee",
        date(2026, 9, 14),
        date(2026, 9, 28),
        "Conference abroad; not sent in time",
    ),
)


def inviters_for(ra: str) -> tuple[str, ...]:
    """Who may open an appeal for an RA, by the policy's inviter setting,
    and only among those holding a place in the RA's slot."""
    slot = next((s for s in sample_data.SLOTS if ra in s.ras), None)
    if slot is None:
        return ()
    if POLICY["inviters"] == "named":
        named = tuple(POLICY["inviter_names"])
    elif POLICY["inviters"] == "slot":
        abbrev = {p.name: p.abbrev for p in sample_data.STAFF}
        named = tuple(n for n in slot.staff if abbrev[n] in POLICY["inviter_types"])
    else:
        named = tuple(p.name for p in sample_data.STAFF if p.abbrev in POLICY["inviter_types"])
    return tuple(n for n in named if n in slot.staff or n in overseers())


def inviters_in(precinct: str) -> tuple[str, ...]:
    """Who may open an appeal for a Precinct's RAs."""
    return tuple(
        dict.fromkeys(
            n
            for s in sample_data.SLOTS
            if s.precinct == precinct
            for ra in s.ras
            for n in inviters_for(ra)
        )
    )


def inviter_gaps() -> tuple[str, ...]:
    """The Precincts whose RAs no one may open an appeal for, while appeals
    are by invitation."""
    return (
        tuple(p for p in precincts() if not inviters_in(p))
        if POLICY["appeals"] == "By invitation"
        else ()
    )


def appeal_gaps() -> tuple[str, ...]:
    """The Precincts whose appeals the Master cannot decide, holding no
    place in their slots, while the Master decides appeals."""
    return tuple(p for p in precincts() if not decides_appeals(p)) if appeals_decided() else ()


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
    return next(
        (i for i in INVITATIONS if i.ra == ra and not i.used_by and i.opened <= day <= i.until),
        None,
    )


def invitation_status(invitation: Invitation) -> str:
    if invitation.used_by:
        return f"Sent: {invitation.used_by}"
    if invitation.until < TODAY:
        return "Lapsed"
    return "Open" if invitation.opened <= TODAY else "From " + short_date(invitation.opened)


def can_withdraw(application: Application) -> bool:
    """An RA may withdraw an application at any pending stage (spec §11)."""
    return application.stage in OPEN_STAGES


def withdraws_to_draft(application: Application) -> bool:
    """Withdrawing ordinary leave takes it back to the RA's drafts, filled in
    as sent, to change and send again (author, 2026-11-10); My history keeps
    the sent one as Withdrawn (§20). The prototype has no appeal draft yet
    (§30's `APPEAL_DRAFT` waits for the wiring, as `Draft` says), so for now
    withdrawing an appeal ends it."""
    return can_withdraw(application) and not application.appeal


def can_cancel(application: Application) -> bool:
    """An RA may cancel an approved application (author, 2026-11-10). It
    keeps its record, as Cancelled (§30), and releases its days and its
    cover, as Applications' admin cancel does. Proposed here, for the author
    to confirm: only ordinary leave not yet begun, leave under way being the
    RF's to approve on the RA's request, or a senior's or the Residential
    Admin's to cancel (author, 2026-11-10; `under_way`), and a granted
    appeal, which §30 gives no cancelled state, a request too
    (`cancel_by_request`)."""
    return application.stage == "Approved" and application.start > TODAY and not application.appeal


def under_way(application: Application) -> bool:
    """Approved leave whose first day has come and whose last has not
    passed, ordinary or a granted appeal."""
    return application.stage == "Approved" and application.start <= TODAY <= application.end


def cancel_by_request(application: Application) -> bool:
    """Approved leave the RA asks to cancel rather than cancelling it
    themselves (author, 2026-11-10): leave under way, and a granted appeal
    not yet ended, which the RA does not cancel alone (§30)."""
    return (
        application.stage == "Approved" and application.end >= TODAY and not can_cancel(application)
    )


def rf_of(application: Application) -> str:
    """The RF of the RA's slot (author, 2026-11-10: a request to cancel
    leave under way goes to the RF, who is told of a cancel): the slot's
    RF by appointment, whoever the policy names as first approver today."""
    return next((r.rf for r in routes() if r.precinct == application.precinct), "")


def cancels_under_way(viewer: str, application: Application) -> bool:
    """Whether a staff member may cancel leave under way themselves (author,
    2026-11-10): a senior, any staff member above RF whose scope holds the
    RA's Precinct, the Residential Admin among them, who also may from
    Applications; the RA and the RF are told. An RF approves an RA's
    request instead."""
    # In the RA's slots, not merely viewing them (cold read, 2026-11-10).
    return (
        under_way(application)
        and not is_rf(viewer)
        and in_slots(viewer, application.precinct)
        and application.precinct in scope(viewer)
    )


def can_appeal(ra: str) -> bool:
    """Whether an RA may send an appeal now: always while appeals are open,
    with an invitation while they are by invitation, never while off."""
    return POLICY["appeals"] == "Open" or (
        POLICY["appeals"] == "By invitation" and invitation_for(ra) is not None
    )


# Policy's Permissions (author, 2026-11-10): who may do what, and over
# which RAs, in one table. A role's row is read from the Policy fields the
# rest of RA Leave already uses, so the table and the Approvals and
# Appeals cards never disagree; a person named on it carries a scope of
# their own.
PERMISSIONS = (
    ("first", "First approval"),
    ("final", "Final approval"),
    ("open", "Open appeals"),
    ("view", "View records"),
    ("admin", "Admin pages"),
)
PERMISSION_KEYS = tuple(key for key, _ in PERMISSIONS)
SCOPE_ALL = "All RAs"


@dataclass(frozen=True)
class NamedGrant:
    """A person given permissions by name, over a scope of their own."""

    name: str
    scope: tuple[str, ...]
    perms: frozenset[str]


NAMED_GRANTS: tuple[NamedGrant, ...] = (
    NamedGrant("Hui Min Goh", ("Cypress", "Maple 03-08"), frozenset({"view"})),
)


def scope_levels() -> dict[str, tuple[str, ...]]:
    """Every scope a named person may be given, each with the broader
    scopes that hold it: All RAs, a Wing, a Precinct, a slot."""
    levels: dict[str, tuple[str, ...]] = {SCOPE_ALL: ()}
    for s in sample_data.SLOTS:
        levels.setdefault(s.wing, (SCOPE_ALL,))
        levels.setdefault(s.precinct, (SCOPE_ALL, s.wing))
        levels.setdefault(s.neighborhood, (SCOPE_ALL, s.wing, s.precinct))
    return levels


def add_scope(scope: tuple[str, ...], choice: str) -> tuple[str, ...]:
    """A named scope with one more choice, overlaps resolved (author,
    2026-11-10): a choice inside one already there is not added; a choice
    holding ones already there replaces them."""
    levels = scope_levels()
    if choice not in levels or choice in scope:
        return scope
    if any(broader in scope for broader in levels[choice]):
        return scope
    kept = tuple(s for s in scope if choice not in levels.get(s, ()))
    return (*kept, choice)


def resolve_scope(choices: Iterable[str]) -> tuple[str, ...]:
    """Choices typed in order, overlaps resolved as `add_scope` does."""
    scope: tuple[str, ...] = ()
    for choice in choices:
        scope = add_scope(scope, choice.strip())
    return scope


class PermissionRow(TypedDict):
    """One row of Permissions: a role or a named person, its scope, and
    the permissions ticked."""

    who: str
    kind: str
    note: str
    scope: tuple[str, ...]
    perms: frozenset[str]


def _granted(name: str) -> set[str]:
    """What a person may do by their appointment, read from the functions
    that grant it: first and final approval and opening appeals from
    Policy, viewing records from Policy's View records, the admin pages from the
    sys admins. Named grants are their own rows; `scope` reads both."""
    abbrev = {p.name: p.abbrev for p in sample_data.STAFF}.get(name, "")
    granted: set[str] = set()
    if POLICY["first"] == "slot" and abbrev in POLICY["first_types"]:
        granted.add("first")
    if name in final_approvers():
        granted.add("final")
    if POLICY["inviters"] == "named":
        if name in POLICY["inviter_names"]:
            granted.add("open")
    elif abbrev in POLICY["inviter_types"]:
        granted.add("open")
    if abbrev in POLICY["viewer_types"]:
        granted.add("view")
    if any(n == name for n, *_ in sample_data.SYS_ADMINS):
        granted.add("admin")
    return granted


def _scope_of(name: str) -> tuple[str, ...]:
    return ("RAs in every slot",) if name in overseers() else ("RAs assigned to staff's slots",)


def permission_rows() -> tuple[PermissionRow, ...]:
    """Permissions' rows: each appointment, then each person holding more
    than their appointment gives. Every tick is read from the function that
    grants it (`_granted`), so the table cannot disagree with routing: a
    role is ticked for what all its holders may do, and a person with more
    gets a named row for the rest, scoped as routing scopes it (the RAs in
    their slots, or every slot for an overseer). `NAMED_GRANTS` rows are
    shown as chosen, and `scope` adds the Precincts they hold."""
    rows: list[PermissionRow] = []
    by_role: dict[str, set[str]] = {}
    for title, abbrev in (*slot_appointments(), *unit_appointments()):
        holders = [p.name for p in sample_data.STAFF if p.abbrev == abbrev]
        common: set[str] = set(PERMISSION_KEYS) if holders else set()
        for h in holders:
            common &= _granted(h)
        # Approvers or inviters chosen by name are a person's grant, not the
        # role's, so they get named rows even when they hold the role alone.
        if POLICY["final"] == "named":
            common.discard("final")
        if POLICY["inviters"] == "named":
            common.discard("open")
        by_role[abbrev] = common
        whole = bool(holders) and all(h in overseers() for h in holders)
        rows.append(
            {
                "who": title,
                "kind": "role",
                "note": abbrev,
                "scope": _scope_of(holders[0]) if whole else _scope_of(""),
                "perms": frozenset(common),
            }
        )
    titles = {abbrev: title for title, abbrev in (*slot_appointments(), *unit_appointments())}
    abbrevs = {p.name: p.abbrev for p in sample_data.STAFF}
    # A person with more than their role gives, scoped as routing scopes
    # them; then each chosen grant on its own row with its own scope, so
    # neither hides the other (Codex on #3758).
    named: list[tuple[str, frozenset[str], tuple[str, ...]]] = []
    for person in sample_data.STAFF:
        extra = _granted(person.name) - by_role.get(person.abbrev, set())
        if extra:
            named.append((person.name, frozenset(extra), _scope_of(person.name)))
    for g in NAMED_GRANTS:
        named.append((g.name, g.perms, resolve_scope(g.scope)))
    for name, perms, chosen in named:
        role = abbrevs.get(name, "")
        rows.append(
            {
                "who": name,
                "kind": "named",
                "note": titles.get(role, role),
                "scope": chosen,
                "perms": perms,
            }
        )
    return tuple(rows)


# The admin Dashboard (author, 2026-11-10): the leave system's set-up and
# where it needs attention, three cards across, each card linking to the
# page that fixes it.


def next_term() -> sample_data.Term | None:
    """The term after the current one, if the year has one."""
    later = [t for t in sample_data.TERMS if t.start > TERM.end]
    return min(later, key=lambda t: t.start) if later else None


def roster_counts() -> tuple[tuple[str, int], ...]:
    """Staff by appointment, in roster order, as (abbreviation, count)."""
    seen: dict[str, int] = {}
    for p in sample_data.STAFF:
        seen[p.abbrev] = seen.get(p.abbrev, 0) + 1
    return tuple(seen.items())


def coming_up() -> tuple[tuple[str, str], ...]:
    """The next blackout and public holidays from today, as (when, what)."""
    found: list[tuple[date, str, str]] = []
    for b in BLACKOUTS:
        span = week_dates(b)
        if span and span[1] >= TODAY:
            when = f"{short_date(span[0])} – {short_date(span[1])}"
            found.append((span[0], when, f"{b.label}, {b.effect.lower()}"))
    found.sort()
    holidays = [(d, short_date(d), name) for d, name in PUBLIC_HOLIDAYS if d >= TODAY]
    return tuple((when, what) for _, when, what in sorted(found[:1] + holidays[:2]))


def roster_mismatches() -> tuple[str, ...]:
    """What in the rosters quietly breaks leave: an RA in no slot (no
    approver), a slot with no RF, no one in every slot next term, a person
    named in Permissions who is not on the Staff roster."""
    found: list[str] = []
    slotted = {ra for s in sample_data.SLOTS for ra in s.ras}
    loose = [p.name for p in sample_data.RAS if p.name not in slotted]
    if loose:
        found.append(f"RAs in no slot: {', '.join(loose)}")
    abbrev = {p.name: p.abbrev for p in sample_data.STAFF}
    bare = [
        s.neighborhood for s in sample_data.SLOTS if not any(abbrev.get(n) == "RF" for n in s.staff)
    ]
    if bare:
        found.append(f"Slots with no RF: {', '.join(bare)}")
    later = next_term()
    if later and not sample_data.every_slot_people(later):
        found.append(f"No one is in every slot for {later.label}")
    gone = [g.name for g in NAMED_GRANTS if g.name not in abbrev]
    if gone:
        found.append(f"Named in Permissions but not on the Staff roster: {', '.join(gone)}")
    return tuple(found)


def staff_access() -> tuple[tuple[str, int, str], ...]:
    """Who reaches the staff pages, by Permissions: (who, how many, over
    which RAs) for each role with a tick beyond Admin pages, then each
    person named."""
    rows: list[tuple[str, int, str]] = []
    for r in permission_rows():
        if not (r["perms"] - {"admin"}):
            continue
        if r["kind"] == "role":
            count = sum(1 for p in sample_data.STAFF if p.abbrev == r["note"])
            rows.append((r["who"], count, r["scope"][0]))
        else:
            rows.append((r["who"], 1, ", ".join(r["scope"])))
    return tuple(rows)


def roles_without_access() -> tuple[str, ...]:
    """Appointments, held by someone, whose holders reach no staff page by
    a Permissions tick."""
    held = {p.abbrev for p in sample_data.STAFF}
    return tuple(
        r["who"]
        for r in permission_rows()
        if r["kind"] == "role" and r["note"] in held and not (r["perms"] - {"admin"})
    )


def standing_in_now() -> tuple[str, ...]:
    """Staff who reach the staff pages today without a tick: a delegate
    standing in, or the Master while deciding appeals (`_standing_in`)."""
    named = {r["who"] for r in permission_rows() if r["kind"] == "named"}
    return tuple(
        p.name
        for p in sample_data.STAFF
        if p.name not in named and not (_granted(p.name) - {"admin"}) and _standing_in(p.name)
    )
