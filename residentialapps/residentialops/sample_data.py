"""Example data for segment 1B's placeholder screens: one Unit, "Example
College", organized by units (`residentialapps/guide/todo_master.md`,
2026-10-27): 30 area slots under 9 Precincts and 3 Wings, a Staff roster of
14 and an RA roster of 30. It is the mock data in
`residentialapps/docs/sample_data/`, which `residentialapps/tests/test_sample_data.py`
holds it to.

Every page that shows it is labeled "Sample data". It lives here alone so
that the wiring items (1B items 3–5) delete it in one place
(`residentialapps/guide/segment_1B_rosters_and_organization.md`).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

UNIT_NAME = "Example College"

# The Unit's names for its levels, top first; the last level is the slot.
LEVEL_LABELS = ("Wing", "Precinct", "Neighborhood")

# Up to five levels (author, 2026-10-27).
MAX_LEVELS = 5

# Terms, up to five a year, never overlapping; an assignment is made for a
# term (author, 2026-10-28). The placeholders read "today" as this date.
MAX_TERMS = 5
TODAY = date(2026, 10, 28)


@dataclass(frozen=True)
class Term:
    year: str
    number: int
    name: str
    start: date
    end: date

    @property
    def label(self) -> str:
        return f"{self.year}, Term {self.number}"

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    @property
    def status(self) -> str:
        """Past (read-only), Current or Upcoming, against `TODAY`."""
        if self.end < TODAY:
            return "Past"
        return "Current" if self.start <= TODAY else "Upcoming"


TERMS: tuple[Term, ...] = tuple(
    Term(year, n, name, date.fromisoformat(start), date.fromisoformat(end))
    for year, n, name, start, end in (
        ("AY2025-2026", 1, "Sem 1 + Winter break", "2025-08-04", "2026-01-11"),
        ("AY2025-2026", 2, "Sem 2", "2026-01-12", "2026-05-10"),
        ("AY2025-2026", 3, "Summer break", "2026-05-11", "2026-08-02"),
        ("AY2026-2027", 1, "Sem 1 + Winter break", "2026-08-03", "2027-01-10"),
        ("AY2026-2027", 2, "Sem 2", "2027-01-11", "2027-05-09"),
        ("AY2026-2027", 3, "Summer break", "2027-05-10", "2027-08-01"),
    )
)
CURRENT_TERM = next(t for t in TERMS if t.status != "Past")  # the page opens on it

# A roster row names its appointment and its abbreviation; there are no
# appointment types tables (author, 2026-10-28).
ABBREV = {
    "Master": "Master",
    "Residential Admin": "Admin",
    "Residential Student Life Manager": "RSLM",
    "Residential Fellow": "RF",
    "Residential Assistant": "RA",
}


@dataclass(frozen=True)
class Slot:
    wing: str
    precinct: str
    neighborhood: str  # the slot, named by its floors
    notes: str  # its room unit numbers, kept as text
    staff: tuple[str, ...]  # the Staff cell: its RF and its Wing's RSLM
    ras: tuple[str, ...]  # the RA cell


SLOTS: tuple[Slot, ...] = tuple(
    Slot(*row) for row in (
        ('Cypress', 'Cypress A 04-12', 'Cypress A 04-05-06', 'RC1A L4: 101, 102-105; Else: 101, 102', ('Daniel Koh', 'Priya Raman'), ('Chloe Lim',)),
        ('Cypress', 'Cypress A 04-12', 'Cypress A 07-08-09', 'RC1A L7: 101, 102-105; Else: 101, 102', ('Daniel Koh', 'Priya Raman'), ('Ethan Wong',)),
        ('Cypress', 'Cypress A 04-12', 'Cypress A 10-11-12', 'RC1A L10: 101, 102-105; Else: 101, 102', ('Daniel Koh', 'Priya Raman'), ('Hana Ito',)),
        ('Cypress', 'Cypress A 13-20', 'Cypress A 13-14-15', 'RC1A 101, 102', ('Mei Ling Tan', 'Priya Raman'), ('Isaac Goh',)),
        ('Cypress', 'Cypress A 13-20', 'Cypress A 16-17-18', 'RC1A 101, 102', ('Mei Ling Tan', 'Priya Raman'), ('Jia Hui Ong',)),
        ('Cypress', 'Cypress A 13-20', 'Cypress A 19-20', 'RC1A 101, 102', ('Mei Ling Tan', 'Priya Raman'), ('Kai Ng',)),
        ('Cypress', 'Cypress B 03-14', 'Cypress B 03-04-05', 'RC1B 108, 107', ('Arjun Nair', 'Priya Raman'), ('Lucas Teo',)),
        ('Cypress', 'Cypress B 03-14', 'Cypress B 06-07-08', 'RC1B 108, 107', ('Arjun Nair', 'Priya Raman'), ('Maya Seah',)),
        ('Cypress', 'Cypress B 03-14', 'Cypress B 09-10-11', 'RC1B 108, 107', ('Arjun Nair', 'Priya Raman'), ('Nur Aisyah',)),
        ('Cypress', 'Cypress B 03-14', 'Cypress B 12-13-14', 'RC1B 108, 107', ('Arjun Nair', 'Priya Raman'), ('Aaron Sim',)),
        ('Maple', 'Maple 03-08', 'Maple 03-04', 'RC2 L3: 203-206, 202, 201; Else: 203, 202, 201', ('Grace Ho', 'Marcus Tan'), ('Bella Koh',)),
        ('Maple', 'Maple 03-08', 'Maple 05-06', 'RC2 L5: 203-206, 202, 201; Else: 203, 202, 201', ('Grace Ho', 'Marcus Tan'), ('Cheng Hao Lin',)),
        ('Maple', 'Maple 03-08', 'Maple 07-08', 'RC2 L7: 203-206, 202, 201; Else: 203, 202, 201', ('Grace Ho', 'Marcus Tan'), ('Dhruv Menon',)),
        ('Maple', 'Maple 09-14', 'Maple 09-10', 'RC2 203, 202, 201', ('Benjamin Chua', 'Marcus Tan'), ('Elise Tan',)),
        ('Maple', 'Maple 09-14', 'Maple 11-12', 'RC2 203, 202, 201', ('Benjamin Chua', 'Marcus Tan'), ('Faris Iskandar',)),
        ('Maple', 'Maple 09-14', 'Maple 13-14', 'RC2 203, 202, 201', ('Benjamin Chua', 'Marcus Tan'), ('Gwen Ho',)),
        ('Maple', 'Maple 15-22', 'Maple 15-16', 'RC2 203, 202, 201', ('Farah Aziz', 'Marcus Tan'), ('Haikal Rahim',)),
        ('Maple', 'Maple 15-22', 'Maple 17-18', 'RC2 203, 202, 201', ('Farah Aziz', 'Marcus Tan'), ('Ivy Toh',)),
        ('Maple', 'Maple 15-22', 'Maple 19-20', 'RC2 203, 202, 201', ('Farah Aziz', 'Marcus Tan'), ('Jasper Lee',)),
        ('Maple', 'Maple 15-22', 'Maple 21-22', 'RC2 203, 202, 201', ('Farah Aziz', 'Marcus Tan'), ('Kavya Pillai',)),
        ('Willow', 'Willow A 04-12', 'Willow A 04-05-06', 'RC3A 501, 502', ('Kenneth Lau', 'Nadia Hassan'), ('Leon Chia',)),
        ('Willow', 'Willow A 04-12', 'Willow A 07-08-09', 'RC3A 501, 502', ('Kenneth Lau', 'Nadia Hassan'), ('Mira Sato',)),
        ('Willow', 'Willow A 04-12', 'Willow A 10-11-12', 'RC3A 501, 502', ('Kenneth Lau', 'Nadia Hassan'), ('Nathan Yeo',)),
        ('Willow', 'Willow A 13-25', 'Willow A 13-14-15', 'RC3A 501, 502', ('Siti Rahman', 'Nadia Hassan'), ('Olivia Ng',)),
        ('Willow', 'Willow A 13-25', 'Willow A 16-17-18', 'RC3A 501, 502', ('Siti Rahman', 'Nadia Hassan'), ('Pranav Iyer',)),
        ('Willow', 'Willow A 13-25', 'Willow A 19-20-21', 'RC3A 501, 502', ('Siti Rahman', 'Nadia Hassan'), ('Qi Xuan Lim',)),
        ('Willow', 'Willow A 13-25', 'Willow A 22-23-24-25', 'RC3A 501, 502', ('Siti Rahman', 'Nadia Hassan'), ('Rui Chen',)),
        ('Willow', 'Willow B 04-12', 'Willow B 04-05-06', 'RC3B L4: 506-509, 505; Else: 506, 505', ('Wei Jie Ong', 'Nadia Hassan'), ('Sofia Wee',)),
        ('Willow', 'Willow B 04-12', 'Willow B 07-08-09', 'RC3B L7: 506-509, 505; Else: 506, 505', ('Wei Jie Ong', 'Nadia Hassan'), ('Timothy Low',)),
        ('Willow', 'Willow B 04-12', 'Willow B 10-11-12', 'RC3B L10: 506-509, 505; Else: 506, 505', ('Wei Jie Ong', 'Nadia Hassan'), ('Umairah Salleh',)),
    )
)


@dataclass(frozen=True)
class StaffMember:
    name: str
    email: str
    appointment: str
    abbrev: str
    dates: str
    linked: bool
    access: tuple[str, ...]  # read-only chips: what each person is granted
    enterprise_name: str


@dataclass(frozen=True)
class RosterRA:
    name: str
    email: str
    appointment: str
    abbrev: str
    dates: str
    linked: bool
    enterprise_name: str
    student_id: str


DATES = "2026-08-01 –"
FRONTLINE = ("Support Logs · frontline",)
SENIOR = ("Sys admin", "Support Logs · senior")


def _email(name: str) -> str:
    *given, family = name.lower().split()
    return f"{''.join(given)}.{family}@example.edu"


def _enterprise(name: str) -> str:
    *given, family = name.upper().split()
    return f"{family} {' '.join(given)}"


def _student_id(n: int) -> str:
    return f"A0{230000 + 4127 * n:06d}{'XBMHKLRTUWY'[n % 11]}"


def _staff(name: str, appointment: str, access: tuple[str, ...], linked: bool = True) -> StaffMember:
    return StaffMember(name, _email(name), appointment, ABBREV[appointment], DATES, linked, access, _enterprise(name))


STAFF: tuple[StaffMember, ...] = (
    _staff("Sam Lee", "Master", SENIOR),
    _staff("Rachel Yeo", "Residential Admin", SENIOR),
    *(_staff(name, "Residential Student Life Manager", FRONTLINE) for name in ("Priya Raman", "Marcus Tan", "Nadia Hassan")),
    *(
        _staff(name, "Residential Fellow", ("Team Viewer",) if name == "Grace Ho" else FRONTLINE, name != "Grace Ho")
        for name in ("Daniel Koh", "Mei Ling Tan", "Arjun Nair", "Grace Ho", "Benjamin Chua",
                     "Farah Aziz", "Kenneth Lau", "Siti Rahman", "Wei Jie Ong")
    ),
)

RAS: tuple[RosterRA, ...] = tuple(
    RosterRA(name, _email(name), "Residential Assistant", "RA", DATES, name != "Nur Aisyah", _enterprise(name), _student_id(n))
    for n, name in enumerate(slot.ras[0] for slot in SLOTS)
)


def appointments(people: tuple[StaffMember, ...] | tuple[RosterRA, ...]) -> tuple[tuple[str, str], ...]:
    """A roster's appointments, as (appointment, abbreviation): the pairs its
    rows hold, in first-held order."""
    return tuple(dict.fromkeys((p.appointment, p.abbrev) for p in people))


STAFF_APPOINTMENTS = appointments(STAFF)
RA_APPOINTMENTS = appointments(RAS)

# Excerpts of the mock files, shown on the pages' CSV cards.
STAFF_CSV = """\
Name,Email,Appointment,Abbrev,From,To,Enterprise name
Sam Lee,sam.lee@example.edu,Master,Master,2026-08-01,,LEE SAM
Priya Raman,priya.raman@example.edu,Residential Student Life Manager,RSLM,2026-08-01,,RAMAN PRIYA"""

TERMS_CSV = """\
Year,Term,Name,Start,End
AY2026-2027,1,Sem 1 + Winter break,2026-08-03,2027-01-10
AY2026-2027,2,Sem 2,2027-01-11,2027-05-09"""

RA_CSV = """\
Name,Email,Appointment,Abbrev,From,To,Enterprise name,Student ID
Chloe Lim,chloe.lim@example.edu,Residential Assistant,RA,2026-08-01,,LIM CHLOE,A0230000X"""

ORGANIZATION_CSV = """\
Level1.Wing,Level2.Precinct,Level3.Neighborhood,Notes,Staff,RA
Cypress,Cypress A 04-12,Cypress A 04-05-06,"RC1A L4: 101, 102-105; Else: 101, 102",daniel.koh@example.edu; priya.raman@example.edu,chloe.lim@example.edu"""


def linked_count(people: tuple[StaffMember, ...] | tuple[RosterRA, ...]) -> tuple[int, int]:
    """On the roster, and linked to a sign-in."""
    return len(people), sum(1 for p in people if p.linked)


def slots_of(name: str) -> tuple[str, ...]:
    """The slots whose cells name a person: derived, shown on person detail."""
    return tuple(s.neighborhood for s in SLOTS if name in s.staff or name in s.ras)


# Identity and access (rung 3): person detail, sys admin grants, the audit log.

ROSTER_ADDED = "Added by roster import, 2026-08-01."


@dataclass(frozen=True)
class Person:
    person_id: str
    name: str
    roster: str  # "staff" or "ra": the roster the person was opened from
    roster_email: str
    linked: bool
    appointments: tuple[str, ...]
    slots: tuple[str, ...]  # derived: the slots whose cells name them
    enterprise_name: str | None = None
    student_id: str | None = None
    entra_display_name: str | None = None
    entra_email: str | None = None
    entra_upn: str | None = None
    entra_object_id: str | None = None
    history: tuple[tuple[str, str], ...] = ()
    added: str = ROSTER_ADDED


# A random UUIDv4 per sample person, as Residential generates one
# (`residentialapps/docs/residentialapps_identity.md` §3.1.1): never
# derived from an email. Keyed by roster email only to find the samples.
_IDS = {person.email: str(uuid.uuid4()) for person in (*STAFF, *RAS)}


def person_id_of(email: str) -> str:
    return _IDS[email]


PERSON_IDS = dict(_IDS)

_WORKED = {
    "chloe.lim@example.edu": {
        "entra_display_name": "Chloe Lim Wei Ling",
        "entra_email": "chloe.lim@u.example.edu",
        "entra_upn": "e0234567@u.example.edu",
        "entra_object_id": "3f2a9c1e-…-7b41",
        "history": (
            ("2026-08-01 08:05", "Added by roster import (Rachel Yeo)"),
            ("2026-08-03 21:14", "Linked on first sign-in: exact match on roster email"),
        ),
    },
    "nur.aisyah@example.edu": {
        "history": (
            ("2026-08-01 08:05", "Added by roster import (Rachel Yeo)"),
            ("2026-09-02 10:41", "Sign-in not matched: roster email differs from the account's"),
        ),
    },
}


def _people() -> dict[str, Person]:
    people = [
        Person(_IDS[s.email], s.name, "staff", s.email, s.linked, (f"{s.appointment} · {s.dates}",),
               slots_of(s.name), enterprise_name=s.enterprise_name, **_WORKED.get(s.email, {}))
        for s in STAFF
    ] + [
        Person(_IDS[r.email], r.name, "ra", r.email, r.linked, (f"{r.appointment} · {r.dates}",),
               slots_of(r.name), enterprise_name=r.enterprise_name, student_id=r.student_id,
               **_WORKED.get(r.email, {}))
        for r in RAS
    ]
    return {p.person_id: p for p in people}


PEOPLE = _people()

SUPER_ADMIN = "[Super-admin name]"

SYS_ADMINS = (
    ("Sam Lee", "sam.lee@example.edu", "Master", f"2026-08-01 by {SUPER_ADMIN}"),
    ("Rachel Yeo", "rachel.yeo@example.edu", "Residential Admin", f"2026-08-01 by {SUPER_ADMIN}"),
)

GRANT_CANDIDATES = ("Priya Raman · RSLM", "Marcus Tan · RSLM", "Daniel Koh · RF")

AUDIT_KINDS = ("Rosters", "Organization", "Access grants", "RA Leave", "RA Events")

AUDIT_RANGE = ("2026-10-01", "2026-10-26")

# (when, event, kind, actor, detail)
AUDIT_EVENTS = (
    ("2026-10-26 09:42", "Cell changed", "Organization", "Rachel Yeo",
     "Maple 03-04 · Staff: + Grace Ho"),
    ("2026-10-25 16:05", "Appointment ended", "Rosters", "Sam Lee", "A previous RA, ended 2026-10-24"),
    ("2026-10-24 11:18", "Organization imported", "Organization", "Rachel Yeo",
     "30 slots: 0 new, 2 changed, 0 retired"),
    ("2026-10-24 11:02", "Level labels changed", "Organization", "Rachel Yeo", "Level 2: “Zone” → “Precinct”"),
    ("2026-10-20 14:30", "Team Viewer granted", "Access grants", "Sam Lee", "Grace Ho"),
    ("2026-08-01 08:05", "Roster imported", "Rosters", "Rachel Yeo", "Staff roster: 14 added; RA roster: 30 added"),
    ("2026-08-01 08:00", "Sys admin granted", "Access grants", SUPER_ADMIN, "Sam Lee, Rachel Yeo"),
)
