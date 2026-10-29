"""Support Logs' sample data, for the placeholder screens of segment 1D
item 1 (`residentialapps/guide/segment_1D_support_logs.md`). Deleted in one
place by items 2–5.

Support Logs may not import Residential Operations
(`residentialapps/spec/architecture.md`, "Import boundaries"), so the
staff below are copied from the Staff roster's mock,
`residentialapps/docs/sample_data/staff_roster.csv`; a test holds the copy
to the file. Students and support content, as later rungs add them, are
invented and bland: nothing here may read as a real case."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from urllib.parse import quote

UNIT_NAME = "Example College"

# Support Logs' authorization types (functional spec §3.5; roles rules 1
# and 8), in the Access page's order. The super-admin holds administration
# from the platform, not as a grant (§3.4).
FRONTLINE = "Frontline"
SENIOR = "Senior identifiable"
RECIPIENT = "Safety-flag recipient"
CONSULTATION = "Consultation check"
VIEW_AGGREGATE = "Other Staff view: aggregate"
VIEW_IDENTIFIABLE = "Other Staff view: identifiable"
SYS_ADMIN = "Sys admin"
SUPER_ADMIN = "Super-admin"
VIEW = (VIEW_AGGREGATE, VIEW_IDENTIFIABLE)
ADMINISTRATION = (SYS_ADMIN, SUPER_ADMIN)


@dataclass(frozen=True)
class Viewer:
    name: str
    appointment: str  # from the Staff roster's mock; empty for the super-admin
    grants: frozenset[str]


# One sample viewer per authorization type; a frontline recipient (Priya
# Raman, whose dashboard lists every active flag); someone reaching two
# pages off the frontline (Nadia Hassan, whose Home lists them); the
# super-admin; and a rostered RF with no grant (the 403 page): access is a
# deliberate grant, never an appointment (§3.5).
VIEWERS = (
    Viewer("Daniel Koh", "RF", frozenset({FRONTLINE})),
    Viewer("Priya Raman", "RSLM", frozenset({FRONTLINE, RECIPIENT})),
    Viewer("Sam Lee", "Master", frozenset({SENIOR, RECIPIENT})),
    Viewer("Hui Min Goh", "Exec", frozenset({RECIPIENT})),
    Viewer("Marcus Tan", "RSLM", frozenset({CONSULTATION})),
    Viewer("Kenneth Lau", "RF", frozenset({VIEW_AGGREGATE})),
    Viewer("Siti Rahman", "RF", frozenset({VIEW_IDENTIFIABLE})),
    Viewer("Nadia Hassan", "RSLM", frozenset({CONSULTATION, VIEW_IDENTIFIABLE})),
    Viewer("Rachel Yeo", "Admin", frozenset({SYS_ADMIN})),
    Viewer("Platform super-admin", "", frozenset({SUPER_ADMIN})),
    Viewer("Wei Jie Ong", "RF", frozenset()),
)
DEFAULT = VIEWERS[0]


def viewer(name: str | None) -> Viewer:
    """The sample viewer a page is drawn for (`?as=`); the default for an
    unknown or absent name."""
    return next((v for v in VIEWERS if v.name == name), DEFAULT)


def as_query(v: Viewer) -> str:
    """The `?as=` every link carries, empty for the default viewer."""
    return "" if v == DEFAULT else f"?as={quote(v.name)}"


def holds(v: Viewer, *grants: str) -> bool:
    return bool(v.grants & set(grants))


def what(v: Viewer) -> str:
    """The viewer's access, as the sample card lists it."""
    if not v.grants:
        return f"{v.appointment}, no Support Logs access"
    held = ", ".join(g for g in (FRONTLINE, SENIOR, RECIPIENT, CONSULTATION, *VIEW, *ADMINISTRATION) if g in v.grants)
    return f"{v.appointment}: {held}" if v.appointment else held


# --- The frontline's sample (rung 2). Invented students and bland notes;
# the seeded lists of the functional spec, which Sys admin configures
# (§5.5–5.9, §6.4, §7.3–7.4).

TODAY = date(2026, 10, 29)  # a Thursday
NOW = datetime(2026, 10, 29, 14, 0)

DURATIONS = ("5 min", "10 min", "15 min", "30 min", "45 min", "60 min", "60+ min")
MINUTES = {"5 min": 5, "10 min": 10, "15 min": 15, "30 min": 30, "45 min": 45, "60 min": 60, "60+ min": 60}
ENCOUNTER_TYPES = (
    "Check-in",
    "Student-initiated conversation",
    "Staff-initiated conversation",
    "Welfare follow-up",
    "Practical support",
    "Other",
)
# Types that already say who started the encounter (UI spec §3, screen 3).
SAYS_WHO = {"Student-initiated conversation", "Staff-initiated conversation"}
CONCERN_AREAS = (
    ("Academic / career", "academic concerns, career, internships"),
    ("Adjustment", "transition, settling in, homesickness"),
    ("Wellbeing", "emotional and mental wellbeing, stress"),
    ("Health and accessibility", "medical matters, accessibility support, disability accommodations, substance use"),
    ("Family", "family circumstances"),
    ("Relationships", "friends, partners, roommates, other interpersonal matters"),
    ("Financial / practical", "money, logistics, practical arrangements"),
    ("Residential / community", "room or housing issues, hall and community life"),
    ("Conduct-related", "disciplinary matters"),
    ("Other", "anything else"),
)
MODES = ("In person", "Phone", "Online", "Other")
STARTED_BY = ("Student", "Staff", "Other")
FOLLOW_UP_CADENCES = ("No fixed cadence", "Fortnightly", "Weekly", "Custom")
NOTE_LIMIT = 300  # within §5.8's 250–500 (UI spec §3)
NOTE_GUIDANCE = "Brief context only. Detailed case notes belong in the appropriate substantive record system."
# Days between expected contacts; "3+ times weekly" is every second day.
INTERVALS = {"Monthly": 30, "Fortnightly": 14, "Weekly": 7, "Twice weekly": 3, "3+ times weekly": 2}


@dataclass(frozen=True)
class Student:
    id: str
    name: str
    email: str


STUDENTS = tuple(
    Student(f"S-{n:02d}", name, name.lower().replace(" ", ".") + "@u.example.edu")
    for n, name in enumerate(
        ("Aiden Chen", "Bao Nguyen", "Clara Tan", "Dev Menon", "Elena Park",
         "Farid Osman", "Gwyneth Low", "Hana Rahim", "Ivan Seet", "Jia Wen Lee"),
        start=1,
    )
)


def student(sid: str | None) -> Student | None:
    return next((s for s in STUDENTS if s.id == sid), None)


@dataclass(frozen=True)
class Encounter:
    id: str
    student: str  # a student id
    staff: str
    when: datetime
    duration: str
    type: str
    concerns: tuple[str, ...] = ()
    follow_up: str = ""  # "Yes", "No" or unset
    mode: str = ""
    note: str = ""


ENCOUNTERS = (
    Encounter("E-01", "S-03", "Daniel Koh", datetime(2026, 10, 13, 18, 0), "30 min", "Check-in", ("Wellbeing",), "Yes", "In person", "Regular check-in; going to plan."),
    Encounter("E-02", "S-01", "Daniel Koh", datetime(2026, 10, 15, 21, 0), "10 min", "Check-in", ("Adjustment",), "Yes", "In person"),
    Encounter("E-03", "S-04", "Daniel Koh", datetime(2026, 10, 19, 12, 0), "15 min", "Welfare follow-up", ("Academic / career",), "Yes", "Online"),
    Encounter("E-04", "S-03", "Daniel Koh", datetime(2026, 10, 20, 18, 30), "30 min", "Check-in", ("Wellbeing",), "Yes", "In person", "Regular check-in; going to plan."),
    Encounter("E-05", "S-01", "Daniel Koh", datetime(2026, 10, 22, 21, 0), "15 min", "Check-in", ("Adjustment",), "Yes", "In person", "Settling in better; joined a club."),
    Encounter("E-06", "S-02", "Daniel Koh", datetime(2026, 10, 24, 20, 0), "10 min", "Practical support", ("Financial / practical",), "No", "In person", "Pointed to the bursary office."),
    Encounter("E-07", "S-05", "Daniel Koh", datetime(2026, 10, 26, 19, 0), "30 min", "Student-initiated conversation", ("Relationships",), "Yes", "In person"),
    Encounter("E-08", "S-06", "Daniel Koh", datetime(2026, 10, 27, 13, 0), "5 min", "Staff-initiated conversation", ("Residential / community",), "No", "In person", "Noise on the floor; passed on."),
    Encounter("E-09", "S-08", "Priya Raman", datetime(2026, 10, 14, 17, 0), "15 min", "Check-in", ("Adjustment",), "Yes", "In person"),
    Encounter("E-10", "S-09", "Priya Raman", datetime(2026, 10, 25, 11, 0), "10 min", "Practical support", ("Residential / community",), "No", "Phone", "Room repair chased."),
    Encounter("E-11", "S-10", "Priya Raman", datetime(2026, 10, 28, 20, 0), "30 min", "Student-initiated conversation", ("Academic / career",), "", "In person"),
)


@dataclass(frozen=True)
class Plan:
    """A check-in plan: a formal assignment (§7) or an informal follow-up
    (§6), kept apart by `formal`."""

    id: str
    student: str
    staff: str
    formal: bool
    start: date
    cadence: str
    source: str = ""  # formal only (§7.3)
    assigned_by: str = ""
    review: date | None = None
    instruction: str = ""  # a short operational instruction, never a reason (§7.5)
    safety_plan: bool = False  # the safety-plan support marker (§5.10)
    status: str = "Active"


PLANS = (
    Plan("P-01", "S-03", "Daniel Koh", True, date(2026, 9, 21), "Weekly", "Counselling", "Sam Lee",
         date(2026, 11, 16), "Weekly check-in; a reminder of the coping plan.", safety_plan=True),
    Plan("P-02", "S-04", "Daniel Koh", True, date(2026, 10, 5), "Fortnightly", "Dean's Office", "Sam Lee",
         date(2026, 12, 7), "Fortnightly check-in on settling in."),
    Plan("P-03", "S-01", "Daniel Koh", False, date(2026, 10, 8), "Weekly"),
    Plan("P-04", "S-05", "Daniel Koh", False, date(2026, 10, 20), "No fixed cadence"),
    Plan("P-05", "S-08", "Priya Raman", False, date(2026, 10, 1), "Fortnightly"),
)


def encounters_by(staff: str, sid: str | None = None) -> list[Encounter]:
    """A staff member's own encounters, the latest first (§11.1)."""
    found = [e for e in ENCOUNTERS if e.staff == staff and (sid is None or e.student == sid)]
    return sorted(found, key=lambda e: e.when, reverse=True)


def plans_of(staff: str, sid: str | None = None) -> list[Plan]:
    """A staff member's active plans, formal assignments first."""
    found = [p for p in PLANS if p.staff == staff and p.status == "Active" and (sid is None or p.student == sid)]
    return sorted(found, key=lambda p: (not p.formal, p.start))


def last_contact(p: Plan) -> date | None:
    seen = encounters_by(p.staff, p.student)
    return seen[0].when.date() if seen else None


def next_due(p: Plan) -> date | None:
    days = INTERVALS.get(p.cadence)
    if days is None:
        return None
    return (last_contact(p) or p.start) + timedelta(days=days)


def due(p: Plan) -> tuple[str, str]:
    """A plan's due state and its label, in words (UI spec §5): overdue,
    today, this week, later, or none without a cadence."""
    when = next_due(p)
    if when is None:
        return "none", "No fixed cadence"
    days = (when - TODAY).days
    if days < 0:
        return "overdue", f"Overdue {-days} day{'s' if days != -1 else ''}"
    if days == 0:
        return "today", "Due today"
    if days < 7:
        return "week", f"Due {when:%a} {when.day} {when:%b}"
    return "later", f"Due {when.day} {when:%b}"


def attention(staff: str) -> list[Plan]:
    """Due and overdue (§10.1): plans overdue, due today or this week, the
    most urgent first."""
    order = {"overdue": 0, "today": 1, "week": 2}
    found = [p for p in plans_of(staff) if due(p)[0] in order]
    return sorted(found, key=lambda p: (order[due(p)[0]], next_due(p)))


def working_set(staff: str) -> list[tuple[Student, list[str], date | None]]:
    """A staff member's own students (§4.3): their plans and follow-ups
    first, then everyone they have logged an encounter with, the most
    recently seen first; each with why it is theirs and when last seen."""
    ids = [p.student for p in plans_of(staff)]
    ids += [e.student for e in encounters_by(staff) if e.student not in ids]
    found = []
    for sid in ids:
        reasons = [f"Plan · {p.source}" if p.formal else "Following" for p in plans_of(staff, sid)]
        seen = encounters_by(staff, sid)
        found.append((student(sid), reasons, seen[0].when.date() if seen else None))
    return found


def recent_window(staff: str, days: int = 14) -> dict:
    """My last 14 days (§10.1): encounters, minutes, students and a count
    by encounter type."""
    since = TODAY - timedelta(days=days - 1)
    mine = [e for e in encounters_by(staff) if e.when.date() >= since]
    by_type: dict[str, int] = {}
    for e in mine:
        by_type[e.type] = by_type.get(e.type, 0) + 1
    return {
        "encounters": len(mine),
        "minutes": sum(MINUTES[e.duration] for e in mine),
        "students": len({e.student for e in mine}),
        "by_type": sorted(by_type.items(), key=lambda kv: (-kv[1], kv[0])),
    }


def short_date(d: date) -> str:
    return f"{d.day} {d:%b}"
