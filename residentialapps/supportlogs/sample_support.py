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

import re
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
    # Colleagues who are not sample viewers, so Overview has a team (rung 5).
    Encounter("E-12", "S-07", "Mei Ling Tan", datetime(2026, 10, 17, 18, 0), "15 min", "Check-in", ("Adjustment",), "Yes", "In person"),
    Encounter("E-13", "S-07", "Mei Ling Tan", datetime(2026, 10, 22, 19, 0), "30 min", "Welfare follow-up", ("Wellbeing",), "Yes", "In person"),
    Encounter("E-14", "S-07", "Mei Ling Tan", datetime(2026, 10, 28, 21, 0), "30 min", "Student-initiated conversation", ("Wellbeing",), "Yes", "In person"),
    Encounter("E-15", "S-08", "Arjun Nair", datetime(2026, 10, 21, 12, 0), "10 min", "Practical support", ("Residential / community",), "No", "In person"),
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
    Plan("P-06", "S-07", "Mei Ling Tan", False, date(2026, 10, 17), "Weekly"),
    Plan("P-07", "S-09", "Arjun Nair", True, date(2026, 10, 12), "Monthly", "Residential staff referral", "Sam Lee",
         date(2026, 12, 14), "Monthly check-in on settling in."),
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
    today, this week (the next seven days, the reading this rung takes of
    UI spec screen 6's filter), later, or none without a fixed cadence."""
    when = next_due(p)
    if when is None:
        return "none", "Custom cadence" if p.cadence == "Custom" else "No fixed cadence"
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


# --- Safety flags (rung 3, §5.10). Generic by design: a flag records that
# escalation happened and the step taken, never method, plan or clinical
# detail. Each is raised from an encounter above, or before the sample's
# window (Clara Tan's, which led to her managed safety support plan).

ESCALATION_STEPS = (
    "Counselling duty line contacted",
    "Duty senior staff contacted",
    "Campus security contacted",
    "Emergency services called",
)
CLOSURE_OUTCOMES = ("Referred to counselling", "Assessed by counselling", "No further action")
# Placeholders until the institution supplies its crisis protocol (§17 Q7):
# the numbers dial nothing.
CRISIS_CONTACTS = (
    ("Emergency services", "+00000000001"),
    ("Campus security", "+00000000002"),
    ("Counselling duty line", "+00000000003"),
    ("Duty senior staff (on duty: to be named)", "+00000000004"),
)
CRISIS_STEPS = (
    "Make sure the student is not alone and is safe now.",
    "If there is immediate danger, call emergency services first.",
    "Call the counselling duty line, then tell the duty senior staff member.",
    "Record below the step you took and when.",
)
MINIMISE = "Record that escalation happened and the step taken; never method, plan or clinical detail."


@dataclass(frozen=True)
class Flag:
    id: str
    student: str
    raised_by: str
    raised_at: datetime
    step: str
    status: str  # "open", "acknowledged" or "closed" (§13, SafetyEscalation)
    step_at: datetime | None = None  # escalated_at; the raising time when it is the same
    acknowledged_by: str = ""
    acknowledged_at: datetime | None = None
    outcome: str = ""
    closed_by: str = ""
    closed_at: datetime | None = None

    @property
    def active(self) -> bool:
        return self.status != "closed"


FLAGS = (
    Flag("F-01", "S-05", "Daniel Koh", datetime(2026, 10, 26, 19, 40), "Counselling duty line contacted", "open",
         step_at=datetime(2026, 10, 26, 19, 25)),
    Flag("F-02", "S-10", "Priya Raman", datetime(2026, 10, 28, 20, 45), "Duty senior staff contacted", "acknowledged",
         acknowledged_by="Sam Lee", acknowledged_at=datetime(2026, 10, 29, 8, 30)),
    Flag("F-03", "S-03", "Daniel Koh", datetime(2026, 9, 18, 22, 0), "Counselling duty line contacted", "closed",
         acknowledged_by="Sam Lee", acknowledged_at=datetime(2026, 9, 18, 22, 30),
         outcome="Assessed by counselling", closed_by="Sam Lee", closed_at=datetime(2026, 9, 19, 16, 0)),
    Flag("F-04", "S-08", "Priya Raman", datetime(2026, 10, 3, 18, 15), "Duty senior staff contacted", "closed",
         acknowledged_by="Hui Min Goh", acknowledged_at=datetime(2026, 10, 3, 18, 40),
         outcome="No further action", closed_by="Hui Min Goh", closed_at=datetime(2026, 10, 4, 10, 0)),
)


def flag(fid: str | None) -> Flag | None:
    return next((f for f in FLAGS if f.id == fid), None)


def may_see(v: Viewer, f: Flag) -> bool:
    """Who sees a flag (§5.10): whoever raised it, and every safety-flag
    recipient."""
    return holds(v, RECIPIENT) or f.raised_by == v.name


def flags_for(v: Viewer, active: bool | None = None, sid: str | None = None) -> list[Flag]:
    """The flags a viewer may see: active first, unacknowledged above
    acknowledged, then closed ones, the latest first in each."""
    found = [f for f in FLAGS if may_see(v, f) and (active is None or f.active == active)
             and (sid is None or f.student == sid)]
    order = {"open": 0, "acknowledged": 1, "closed": 2}
    return sorted(sorted(found, key=lambda f: f.raised_at, reverse=True), key=lambda f: order[f.status])


def unacknowledged(v: Viewer) -> int:
    """The navigation's count for a recipient (UI spec screen 9): v1 has no
    automated alerts, so this is where a new flag is first seen."""
    return sum(1 for f in FLAGS if f.status == "open") if holds(v, RECIPIENT) else 0


def when(moment: datetime) -> str:
    return f"{moment.day} {moment:%b}, {moment:%H:%M}"


# --- Plans and sharing (rung 4, §7, §8, §11.1).

ASSIGNMENT_SOURCES = ("Counselling", "Dean's Office", "Master / residential leadership", "Residential staff referral", "Other")
ASSIGNMENT_CADENCES = ("Monthly", "Fortnightly", "Weekly", "Twice weekly", "3+ times weekly", "Custom")
PLAN_STATUSES = ("Active", "Paused", "Closed")
# Frontline colleagues a record can be shared with (§11.1): RFs and RSLMs
# holding frontline access, copied from the roster's mock with the sample
# viewers who hold it.
FRONTLINE_COLLEAGUES = ("Daniel Koh", "Priya Raman", "Mei Ling Tan", "Arjun Nair", "Grace Ho")
# Their Staff-roster emails, so a filter matches a name or an email.
STAFF_EMAILS = {"Daniel Koh": "daniel.koh@example.edu", "Priya Raman": "priya.raman@example.edu",
                "Mei Ling Tan": "meiling.tan@example.edu", "Arjun Nair": "arjun.nair@example.edu",
                "Grace Ho": "grace.ho@example.edu"}

# Each plan's history (§8): how it began and what changed, so a converted
# follow-up keeps one record rather than a disconnected duplicate.
PLAN_HISTORY = {
    "P-01": ((date(2026, 9, 21), "Sam Lee assigned it: Counselling, weekly, with safety-plan support"),),
    "P-02": ((date(2026, 9, 28), "Daniel Koh began following up, no fixed cadence"),
             (date(2026, 10, 5), "Sam Lee converted it to a formal assignment: Dean's Office, fortnightly, review 7 Dec")),
    "P-03": ((date(2026, 10, 8), "Daniel Koh began following up, weekly"),),
    "P-04": ((date(2026, 10, 20), "Daniel Koh began following up, no fixed cadence"),),
    "P-05": ((date(2026, 10, 1), "Priya Raman began following up, fortnightly"),),
    "P-06": ((date(2026, 10, 17), "Mei Ling Tan began following up, weekly"),),
    "P-07": ((date(2026, 10, 12), "Sam Lee assigned it: Residential staff referral, monthly"),),
}


@dataclass(frozen=True)
class Referral:
    """A student flagged for formal assignment by frontline staff (§3.1),
    for senior staff to review: no reason recorded, only a suggestion."""

    student: str
    flagged_by: str
    flagged_on: date
    cadence: str = ""


REFERRALS = (Referral("S-05", "Daniel Koh", date(2026, 10, 27), "Weekly"),)


@dataclass(frozen=True)
class PeerGrant:
    """A peer-view grant (§11.1): the grantor's records for one student,
    shared with one colleague; private by default, revocable."""

    student: str
    grantor: str
    viewer: str
    granted_on: date


PEER_GRANTS = (
    PeerGrant("S-03", "Daniel Koh", "Mei Ling Tan", date(2026, 10, 1)),
    PeerGrant("S-08", "Priya Raman", "Daniel Koh", date(2026, 10, 20)),
)


def plan(pid: str | None) -> Plan | None:
    return next((p for p in PLANS if p.id == pid), None)


def contacts_since_start(p: Plan) -> int:
    """Contacts in the plan's period (§7.7): its owner's encounters since it
    began."""
    return sum(1 for e in encounters_by(p.staff, p.student) if e.when.date() >= p.start)


def referral(sid: str) -> Referral | None:
    return next((r for r in REFERRALS if r.student == sid), None)


def grants_by(staff: str, sid: str) -> list[PeerGrant]:
    return [g for g in PEER_GRANTS if g.grantor == staff and g.student == sid]


def shared_with(staff: str) -> list[PeerGrant]:
    """Records colleagues have shared with a staff member."""
    return [g for g in PEER_GRANTS if g.viewer == staff]


def shared_plans(staff: str, sid: str) -> list[Plan]:
    """A colleague's active plans for a student shared with the viewer."""
    return [p for g in shared_with(staff) if g.student == sid for p in plans_of(g.grantor, sid)]


def may_read_plan(staff: str, p: Plan) -> bool:
    """A plan's owner, or a colleague its owner has shared the student's
    records with (§11.1)."""
    return p.staff == staff or any(g.grantor == p.staff and g.student == p.student for g in shared_with(staff))


def shared_encounters(staff: str, sid: str) -> list[Encounter]:
    """A colleague's encounters with a student shared with the viewer,
    labelled with that colleague when shown (UI spec screen 5)."""
    found = [e for g in shared_with(staff) if g.student == sid for e in encounters_by(g.grantor, sid)]
    return sorted(found, key=lambda e: e.when, reverse=True)


# --- Overview (rung 5, §10.2–10.6, §11.2–11.3). Clusters are shown as the
# core's Precincts until ruled (the plan's open question 2), copied from the
# Assignments mock; which cluster a student belongs to is Support Logs data,
# set by senior staff (§10.5).

CLUSTERS = ("Cypress A 04-12", "Cypress A 13-20", "Cypress B 03-14", "Maple 03-08")
STUDENT_CLUSTER = {
    "S-01": "Cypress A 04-12", "S-02": "Cypress A 04-12", "S-03": "Cypress A 04-12", "S-04": "Cypress A 13-20",
    "S-05": "Cypress A 13-20", "S-06": "Cypress A 13-20", "S-07": "Maple 03-08", "S-08": "Cypress B 03-14",
    "S-09": "Cypress B 03-14", "S-10": "Cypress B 03-14",
}
# Assignment load weighting (§10.3): an operational indicator, not a
# measure of complexity or performance.
WEIGHTS = {"Monthly": 1, "Fortnightly": 2, "Weekly": 4, "Twice weekly": 8, "3+ times weekly": 12}
PERIOD_DAYS = 30
REVIEW_SOON_DAYS = 21


def in_period(e: Encounter, days: int = PERIOD_DAYS, offset: int = 0) -> bool:
    """Whether an encounter falls in the `days` before TODAY, shifted back by
    `offset` days."""
    end = TODAY - timedelta(days=offset)
    return end - timedelta(days=days - 1) <= e.when.date() <= end


def workload() -> list[dict]:
    """Team workload (§10.2–10.3) over the last 30 days, every frontline
    colleague, heaviest load first."""
    rows = []
    for staff in FRONTLINE_COLLEAGUES:
        plans = plans_of(staff)
        recent = [e for e in encounters_by(staff) if in_period(e)]
        rows.append({
            "staff": staff,
            "formal": sum(1 for p in plans if p.formal),
            "informal": sum(1 for p in plans if not p.formal),
            "students": len({e.student for e in recent}),
            "encounters": len(recent),
            "minutes": sum(MINUTES[e.duration] for e in recent),
            "load": sum(WEIGHTS.get(p.cadence, 0) for p in plans if p.formal),
        })
    return sorted(rows, key=lambda r: (-r["load"], -r["encounters"], r["staff"]))


def totals() -> dict:
    recent = [e for e in ENCOUNTERS if in_period(e)]
    active = [p for p in PLANS if p.status == "Active"]
    return {
        "formal": sum(1 for p in active if p.formal),
        "informal": sum(1 for p in active if not p.formal),
        "students": len({e.student for e in recent}),
        "encounters": len(recent),
        "minutes": sum(MINUTES[e.duration] for e in recent),
    }


def hotspots() -> list[dict]:
    """Students by recent support (§10.4): contacts and minutes over the last
    14 days against the 14 before, staff involved, a formal plan, active
    flags. Rising is a sharp increase on the student's own baseline, not a
    high but stable one. Never a score (§15)."""
    rows = []
    for s in STUDENTS:
        mine = [e for e in ENCOUNTERS if e.student == s.id]
        now = [e for e in mine if in_period(e, 14)]
        before = [e for e in mine if in_period(e, 14, offset=14)]
        flags_active = sum(1 for f in FLAGS if f.student == s.id and f.active)
        if not now and not flags_active:
            continue
        rows.append({
            "student": s,
            "contacts": len(now),
            "before": len(before),
            "minutes": sum(MINUTES[e.duration] for e in now),
            "staff": len({e.staff for e in now}),
            "formal": any(p.formal for p in PLANS if p.student == s.id and p.status == "Active"),
            "flags": flags_active,
            "rising": len(now) >= 2 and len(now) > len(before),
        })
    return sorted(rows, key=lambda r: (-r["flags"], not r["rising"], -r["contacts"], r["student"].name))


def coverage() -> dict:
    """Coverage (§10.6): formal check-ins overdue and due soon, and
    assignments whose review is within three weeks or already past."""
    formal = [p for p in PLANS if p.formal and p.status == "Active"]
    return {
        "overdue": [p for p in formal if due(p)[0] == "overdue"],
        "soon": [p for p in formal if due(p)[0] in ("today", "week")],
        "review": [p for p in formal if p.review and (p.review - TODAY).days <= REVIEW_SOON_DAYS],
    }


def clusters() -> list[dict]:
    """Support by cluster (§10.5) over the last 30 days."""
    rising = {r["student"].id for r in hotspots() if r["rising"]}
    rows = []
    for c in CLUSTERS:
        ids = {sid for sid, cl in STUDENT_CLUSTER.items() if cl == c}
        recent = [e for e in ENCOUNTERS if e.student in ids and in_period(e)]
        supported = {p.student for p in PLANS if p.student in ids and p.status == "Active"} | {e.student for e in recent}
        rows.append({"cluster": c, "students": len(supported), "contacts": len(recent),
                     "minutes": sum(MINUTES[e.duration] for e in recent), "rising": len(ids & rising)})
    return rows


@dataclass(frozen=True)
class AuditEvent:
    """A support-activity audit event (§11.3): who did or saw what, of whom.
    Reviewable only by senior staff with identifiable access, and reviewing
    it is itself recorded."""

    at: datetime
    actor: str
    action: str
    student: str = ""


AUDIT = (
    AuditEvent(datetime(2026, 10, 29, 8, 30), "Sam Lee", "Acknowledged a safety flag", "S-10"),
    AuditEvent(datetime(2026, 10, 29, 8, 25), "Sam Lee", "Viewed a safety flag", "S-10"),
    AuditEvent(datetime(2026, 10, 28, 20, 45), "Priya Raman", "Raised a safety flag", "S-10"),
    AuditEvent(datetime(2026, 10, 28, 20, 0), "Priya Raman", "Logged an encounter", "S-10"),
    AuditEvent(datetime(2026, 10, 27, 13, 0), "Daniel Koh", "Logged an encounter", "S-06"),
    AuditEvent(datetime(2026, 10, 27, 9, 10), "Daniel Koh", "Flagged for formal assignment", "S-05"),
    AuditEvent(datetime(2026, 10, 26, 19, 40), "Daniel Koh", "Raised a safety flag", "S-05"),
    AuditEvent(datetime(2026, 10, 20, 9, 0), "Priya Raman", "Shared records with Daniel Koh", "S-08"),
    AuditEvent(datetime(2026, 10, 20, 8, 55), "Daniel Koh", "Viewed the student", "S-08"),
)


# --- Consultation check (rung 6; §10.7–10.8). Rule-based and transparent:
# named reasons, never a score, computed on demand. A check run records its
# purpose, the students checked, the states and reasons shown and whom to
# consult (§11.3), never a suitability decision.

NONE_INDICATED = "No consultation indicated"
SUGGESTED = "Consultation suggested"
REQUIRED = "Consultation required"
CONSULTATION_STATES = (REQUIRED, SUGGESTED, NONE_INDICATED)  # strongest first
# Each reason and the state it brings (§10.8); the thresholds are policy,
# configured before go-live (§17).
CONSULTATION_REASONS = (
    ("Unresolved safety escalation", REQUIRED),
    ("Active safety-plan support", REQUIRED),
    ("Active formal check-in assignment", SUGGESTED),
    ("Active informal follow-up", SUGGESTED),
    ("Marked increase in recent support", SUGGESTED),
    ("Several staff recently involved", SUGGESTED),
)
NONE_MEANS = ("No consultation indicated means only that nothing recorded in Support Logs prompted a second look. "
              "It never means a student is well or suitable.")
SAMPLE_EMAILS = ("clara.tan@u.example.edu", "gwyneth.low@u.example.edu", "hana.rahim@u.example.edu",
                 "jia.wen.lee@u.example.edu", "farid.osman@u.example.edu", "someone.else@u.example.edu")


@dataclass(frozen=True)
class Consultation:
    email: str
    student: Student | None
    state: str
    reasons: tuple[str, ...]
    consult: tuple[str, ...]  # staff with current or recent involvement


def consultation(email: str) -> Consultation:
    """One student's result (§10.7): the reasons met, the strongest state
    they bring, and whom to consult. An email with no Support Logs record
    is No consultation indicated, as nothing recorded prompts a look."""
    email = email.strip().lower()
    s = next((s for s in STUDENTS if s.email == email), None)
    if s is None:
        return Consultation(email, None, NONE_INDICATED, (), ())
    plans = [p for p in PLANS if p.student == s.id and p.status == "Active"]
    recent = [e for e in ENCOUNTERS if e.student == s.id and in_period(e)]
    hot = next((r for r in hotspots() if r["student"].id == s.id), None)
    met = {
        "Unresolved safety escalation": any(f.student == s.id and f.active for f in FLAGS),
        "Active safety-plan support": any(p.safety_plan for p in plans),
        "Active formal check-in assignment": any(p.formal for p in plans),
        "Active informal follow-up": any(not p.formal for p in plans),
        "Marked increase in recent support": bool(hot and hot["rising"]),
        "Several staff recently involved": len({e.staff for e in recent}) >= 2,
    }
    reasons = tuple(r for r, _ in CONSULTATION_REASONS if met[r])
    brought = {state for r, state in CONSULTATION_REASONS if r in reasons}
    state = next((st for st in CONSULTATION_STATES if st in brought), NONE_INDICATED)
    raisers = [f.raised_by for f in FLAGS if f.student == s.id and f.active]
    consult = () if not reasons else tuple(dict.fromkeys([p.staff for p in plans] + raisers + [e.staff for e in recent]))
    return Consultation(email, s, state, reasons, consult)


EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")


def emails_in(text: str) -> tuple[list[str], list[str]]:
    """The distinct emails in a pasted list, in order, and the entries read
    as none. Entries are separated by commas, semicolons or new lines; an
    address is taken from inside a name, angle brackets, quotes or
    `mailto:`. An entry with no address is never quietly dropped: a check
    that cannot read an entry must not show it as No consultation indicated
    (§10.7)."""
    emails, unread = [], []
    for entry in re.split(r"[,;\n]", text):
        entry = entry.strip()
        if not entry:
            continue
        found = EMAIL.findall(entry)
        if found:
            emails += [e.lower() for e in found]
        else:
            unread.append(entry)
    return list(dict.fromkeys(emails)), list(dict.fromkeys(unread))


@dataclass(frozen=True)
class CheckRun:
    on: date
    by: str
    purpose: str
    checked: int
    flagged: int  # suggested or required


CHECK_RUNS = (
    CheckRun(date(2026, 10, 22), "Marcus Tan", "Overseas field trip, Semester 2", 14, 2),
    CheckRun(date(2026, 9, 30), "Nadia Hassan", "Student exchange nominations", 8, 1),
)


# --- Sys admin (rung 6; §3.3, roles rules 1, 6, 8, 9). Administration
# sees who holds what, the configured lists and the administrative audit;
# never support content.

# The Staff roster's active members (`staff_roster.csv`, copied: Support
# Logs reads it as the eligibility list and never writes to it). A test
# holds the copy to the file.
STAFF_ROSTER = (
    ("Sam Lee", "Master"), ("Rachel Yeo", "Admin"), ("Priya Raman", "RSLM"), ("Marcus Tan", "RSLM"),
    ("Nadia Hassan", "RSLM"), ("Daniel Koh", "RF"), ("Mei Ling Tan", "RF"), ("Arjun Nair", "RF"),
    ("Grace Ho", "RF"), ("Benjamin Chua", "RF"), ("Farah Aziz", "RF"), ("Kenneth Lau", "RF"),
    ("Siti Rahman", "RF"), ("Wei Jie Ong", "RF"), ("Hui Min Goh", "Exec"),
)
APPOINTMENTS = {"Master": "Master", "Admin": "Residential Admin", "RSLM": "Residential Student Life Manager",
                "RF": "Residential Fellow", "Exec": "Residential Executive"}
# The Access page's columns, each a grant; Other Staff view is one column
# with its scope (roles rule 8).
ACCESS_COLUMNS = (FRONTLINE, SENIOR, RECIPIENT, CONSULTATION, "Other Staff view", SYS_ADMIN)
# Colleagues who hold grants but are not sample viewers.
_OTHER_GRANTS = {
    "Mei Ling Tan": frozenset({FRONTLINE}),
    "Arjun Nair": frozenset({FRONTLINE}),
    "Grace Ho": frozenset({FRONTLINE}),
}


def grants_of(name: str) -> frozenset[str]:
    v = next((v for v in VIEWERS if v.name == name), None)
    return v.grants if v else _OTHER_GRANTS.get(name, frozenset())


def view_scope(name: str) -> str:
    """Other Staff view's scope for a person: None, Aggregate or
    Identifiable."""
    held = grants_of(name)
    return "Identifiable" if VIEW_IDENTIFIABLE in held else "Aggregate" if VIEW_AGGREGATE in held else "None"


@dataclass(frozen=True)
class Lapsed:
    """A grant whose holder has no active Staff-roster entry: it stopped at
    once and stays listed until a sys admin revokes it (§3.5)."""

    name: str
    grants: tuple[str, ...]
    since: date
    why: str


LAPSED = (Lapsed("Jason Teo", (FRONTLINE,), date(2026, 9, 30), "Left the Staff roster: RF appointment ended"),)


@dataclass(frozen=True)
class AdminEvent:
    """An administrative audit event (§11.3): grants, configuration and
    other administration; reviewable by sys admins and the super-admin."""

    at: datetime
    actor: str
    kind: str  # "Access", "Configuration" or "Clusters"
    action: str
    reason: str = ""


ADMIN_AUDIT = (
    AdminEvent(datetime(2026, 10, 27, 10, 5), "Rachel Yeo", "Access", "Granted Consultation check to Nadia Hassan",
               "Exchange nominations, as the Master asked"),
    AdminEvent(datetime(2026, 10, 20, 9, 30), "Rachel Yeo", "Configuration", "Added the closure outcome “No further action”"),
    AdminEvent(datetime(2026, 10, 12, 16, 0), "Rachel Yeo", "Access", "Granted Other Staff view (identifiable) to Siti Rahman",
               "Covering the Master's oversight, as the Master asked"),
    AdminEvent(datetime(2026, 9, 30, 0, 0), "Support Logs", "Access", "Jason Teo's Frontline lapsed",
               "Residential Operations: Jason Teo's RF appointment ended"),
    AdminEvent(datetime(2026, 8, 3, 9, 15), "Rachel Yeo", "Clusters", "Added the cluster Maple 03-08"),
    AdminEvent(datetime(2026, 8, 1, 9, 0), "Platform super-admin", "Access", "Granted Sys admin to Rachel Yeo",
               "Support Logs set up for the term"),
)


# --- Your records (rung 7; author, 2026-10-30): a section at the end of
# Students and My plans, locked until its holder confirms, to download
# their own encounters or plans as CSV by term, upload a CSV to populate
# them, or purge them all. A purge hides records from every page and keeps
# them; senior identifiable access alone deletes them, a whole purge or
# one student's records in it (rung 8; author, 2026-10-30).

# Residential's terms (`residentialapps/docs/sample_data/terms.csv`,
# copied: Support Logs may not import Residential Operations, which sets
# them on /rosters/). A test holds the copy to the file.
@dataclass(frozen=True)
class Term:
    key: str  # "AY2026-2027.1"
    name: str  # "Sem 1 + Winter break"
    start: date
    end: date

    @property
    def label(self) -> str:
        """As Rosters and setup shows it: "AY2026-2027, Term 1 · Sem 1 +
        Winter break"."""
        year, n = self.key.split(".")
        return f"{year}, Term {n} · {self.name}"



TERMS = tuple(
    Term(f"{y}.{n}", name, date.fromisoformat(s), date.fromisoformat(e))
    for y, n, name, s, e in (
        ("AY2025-2026", 1, "Sem 1 + Winter break", "2025-08-04", "2026-01-11"),
        ("AY2025-2026", 2, "Sem 2", "2026-01-12", "2026-05-10"),
        ("AY2025-2026", 3, "Summer break", "2026-05-11", "2026-08-02"),
        ("AY2026-2027", 1, "Sem 1 + Winter break", "2026-08-03", "2027-01-10"),
        ("AY2026-2027", 2, "Sem 2", "2027-01-11", "2027-05-09"),
        ("AY2026-2027", 3, "Summer break", "2027-05-10", "2027-08-01"),
    )
)
CURRENT_TERM = next(t for t in TERMS if t.start <= TODAY <= t.end)


def term(key: str | None) -> Term | None:
    return next((t for t in TERMS if t.key == key), None)


ENCOUNTER_COLUMNS = ("Date", "Time", "Student email", "Student", "Duration", "Type", "Concern areas",
                     "Follow-up needed", "How", "Note")
PLAN_COLUMNS = ("Student email", "Student", "Kind", "Source", "Cadence", "Since", "Review", "Status")
# An upload adds follow-ups only: formal assignments are senior staff's
# (§7), so the plans template has no Kind or Source.
PLAN_TEMPLATE_COLUMNS = ("Student email", "Student", "Cadence", "Since")


def encounter_rows(staff: str, t: Term | None, sid: str | None = None) -> list[list[str]]:
    """The staff member's own encounters in a term (all terms when none),
    oldest first, never a colleague's shared records or a safety flag."""
    rows = []
    for e in sorted(encounters_by(staff), key=lambda e: e.when):
        if (t and not t.start <= e.when.date() <= t.end) or (sid and e.student != sid):
            continue
        s = student(e.student)
        rows.append([e.when.date().isoformat(), e.when.strftime("%H:%M"), s.email, s.name, e.duration, e.type,
                     "; ".join(e.concerns), e.follow_up, e.mode, e.note])
    return rows


def plan_rows(staff: str, t: Term | None, sid: str | None = None) -> list[list[str]]:
    """The staff member's own plans, closed ones included, begun on or
    before the term's end (all terms when none). The sample's plans carry no
    closing date, so a plan closed before a term still counts in it; wired,
    a plan counts when its open span overlaps the term."""
    rows = []
    for p in sorted((p for p in PLANS if p.staff == staff), key=lambda p: p.start):
        if (t and p.start > t.end) or (sid and p.student != sid):
            continue
        s = student(p.student)
        rows.append([s.email, s.name, "Formal assignment" if p.formal else "Follow-up", p.source, p.cadence,
                     p.start.isoformat(), p.review.isoformat() if p.review else "", p.status])
    return rows


@dataclass(frozen=True)
class Purge:
    """A purge: a staff member's records hidden from every page in one go,
    kept until senior identifiable access deletes them. Each record is
    about one student; `held` counts them by student, so a delete by
    student removes only that student's records and leaves the rest of the
    purge (author, 2026-10-30). Sys admin sees the count, never the
    records."""

    by: str
    what: str  # "Encounters" or "Plans"
    on: date
    held: tuple[tuple[str, int], ...]  # (student id, records about them)

    @property
    def count(self) -> int:
        return sum(n for _, n in self.held)

    def about(self, sid: str | None) -> int:
        """Its records about a student; all of them when none."""
        return self.count if sid is None else sum(n for s, n in self.held if s == sid)


PURGES = (
    Purge("Grace Ho", "Encounters", date(2026, 10, 9), (("S-02", 4), ("S-06", 2))),
    Purge("Arjun Nair", "Plans", date(2026, 5, 20), (("S-09", 2),)),
)


def term_of(d: date) -> Term | None:
    return next((t for t in TERMS if t.start <= d <= t.end), None)


# --- Records across staff (rung 8; author, 2026-10-30): senior
# identifiable access uploads records tagged to a staff member, downloads
# them by staff, student and term, and deletes purged records, every action
# audited. A download names the staff member in its own column.

RECORD_KINDS = {"encounters": ("Encounters", ENCOUNTER_COLUMNS), "plans": ("Plans", PLAN_COLUMNS)}
# What a senior upload takes after its Staff column: a plan may be a formal
# assignment (§7), and a new one is always Active, so no Status.
STAFF_TEMPLATE_COLUMNS = {"encounters": ENCOUNTER_COLUMNS,
                          "plans": tuple(c for c in PLAN_COLUMNS if c != "Status")}


def staff_rows(what: str, staff: str | None, t: Term | None,
               sid: str | None = None) -> tuple[tuple[str, ...], list[list[str]]]:
    """Every staff member's records of a kind (one staff member's when
    named) in a term or all terms, each row led by its staff member."""
    columns = ("Staff", *RECORD_KINDS[what][1])
    rows_of = encounter_rows if what == "encounters" else plan_rows
    rows = []
    for name in FRONTLINE_COLLEAGUES:
        if staff and name != staff:
            continue
        rows += [[name, *r] for r in rows_of(name, t, sid)]
    return columns, rows


def purges(staff: str | None = None, sid: str | None = None) -> list[Purge]:
    """Purges of a staff member's records (all staff when none) holding
    records about a student (any student when none). No term filter
    (author, 2026-10-30)."""
    return [p for p in PURGES if (not staff or p.by == staff) and p.about(sid)]


def record_students(staff: str, page: str = "students") -> list[Student]:
    """The students a staff member's own records of a page's kind are about
    (encounters on Students, plans on My plans), for Your records' student
    filter, by name."""
    ids = {e.student for e in encounters_by(staff)} if page == "students" else {p.student for p in PLANS if p.staff == staff}
    return sorted((s for s in STUDENTS if s.id in ids), key=lambda s: s.name)


def staff_choices() -> list[tuple[str, str, str]]:
    """(value, name, email) per frontline colleague, for a staff filter."""
    return [(n, n, STAFF_EMAILS[n]) for n in FRONTLINE_COLLEAGUES]


def student_choices(students=None) -> list[tuple[str, str, str]]:
    """(id, name, email) per student, for a student filter."""
    return [(s.id, s.name, s.email) for s in (STUDENTS if students is None else students)]
