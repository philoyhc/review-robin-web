"""Example data for segment 1B's placeholder screens: one Unit, "Example
College", with one Wing, three Precincts and ten Neighborhoods.

Every page that shows it is labeled "Sample data". It lives here alone so
that the wiring items (1B items 3–5) delete it in one place
(`residentialapps/guide/segment_1B_rosters_and_organization.md`).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

UNIT_NAME = "Example College"

LEVEL_LABELS = ("Wing", "Precinct", "Neighborhood")


@dataclass(frozen=True)
class Node:
    name: str
    level: int  # 0 the Unit, then 1–3 for the Unit's three levels
    floors: str
    appointed: tuple[str, ...]  # derived from the rosters: who holds each post


TREE: tuple[Node, ...] = (
    Node("Master, Admin-01", 0, "Cypress A, Cypress B", ("Sam Lee · Master", "Rachel Yeo · Admin-01")),
    Node("RSLM-01", 1, "Cypress A, Cypress B", ("Priya Raman",)),
    Node("RF-01", 2, "Cypress A 04–12", ("Daniel Koh",)),
    Node("RA-01", 3, "Cypress A 04-05-06", ("Chloe Lim",)),
    Node("RA-02", 3, "Cypress A 07-08-09", ("Ethan Wong",)),
    Node("RA-03", 3, "Cypress A 10-11-12", ("Hana Ito",)),
    Node("RF-02, RF-04", 2, "Cypress A 13–15; Cypress B 01–06", ("Mei Ling Tan · RF-02", "Grace Ho · RF-04 to 31 Dec")),
    Node("RA-04", 3, "Cypress A 13-14-15", ("Isaac Goh",)),
    Node("RA-05", 3, "Cypress B 01-02-03", ("Jia Hui Ong",)),
    Node("RA-06", 3, "Cypress B 04-05-06", ("Kai Ng",)),
    Node("RF-03", 2, "Cypress B 07–16", ("Arjun Nair",)),
    Node("RA-07", 3, "Cypress B 07-08-09", ("Lucas Teo",)),
    Node("RA-08", 3, "Cypress B 10-11-12", ("Maya Seah",)),
    Node("RA-09", 3, "Cypress B 13-14", ("Nur Aisyah",)),
    Node("RA-10", 3, "Cypress B 15-16", ()),
)

FLOOR_GAPS = ("Cypress A 16",)

# A Unit has up to five levels below the whole Unit and up to ten
# appointments (author, 2026-10-27); floors sit on the lowest level.
MAX_LEVELS = 5
MAX_APPOINTMENTS = 10

APPOINTMENT_TYPES = ("Staff", "Student")

# The Unit's appointments as (title, abbreviation, type, level), level 0
# the whole Unit; rows are added and removed, not a fixed number. Five
# come prefilled for every Unit; the last is Example College's own.
APPOINTMENTS = (
    ("Master", "Master", "Staff", 0),
    ("Residential Fellow", "RF", "Staff", 2),
    ("Residential Admin", "Admin", "Staff", 0),
    ("Residential Assistant", "RA", "Student", 3),
    ("Other Staff", "", "Staff", 0),
    ("Residential Student Life Manager", "RSLM", "Staff", 1),
)

# Excerpts of the setup CSVs (residentialapps/guide/todo_master.md,
# organization setup CSVs; the full files are in docs/sample_data/).
APPOINTMENT_TYPES_CSV = """\
Title,Abbrev,Type,Level
Master,Master,Staff,Unit
Residential Admin,Admin,Staff,Unit
Residential Fellow,RF,Staff,Level2.Precinct"""

STRUCTURE_CSV = """\
Level,Dorms,Post
Unit,Cypress A; Cypress B,Master
Level2.Precinct,Cypress A 13-14-15; Cypress B 01-02-03-04-05-06,RF-02
Level2.Precinct,Cypress A 13-14-15; Cypress B 01-02-03-04-05-06,RF-04"""


@dataclass(frozen=True)
class StaffMember:
    name: str
    email: str
    appointment: str
    node: str  # the post: an appointment type's abbreviation and number
    dates: str
    linked: bool
    access: tuple[str, ...]  # read-only chips: what each person is granted


STAFF: tuple[StaffMember, ...] = (
    StaffMember("Sam Lee", "sam.lee@example.edu", "Master", "Master", "2026-08-01 –", True,
                ("Sys admin", "Support Logs · senior")),
    StaffMember("Rachel Yeo", "rachel.yeo@example.edu", "Residential Admin", "Admin-01", "2026-08-01 –", True,
                ("Sys admin", "Support Logs · senior")),
    StaffMember("Priya Raman", "priya.raman@example.edu", "RSLM", "RSLM-01", "2026-08-01 –", True,
                ("Support Logs · frontline",)),
    StaffMember("Daniel Koh", "daniel.koh@example.edu", "RF", "RF-01", "2026-08-01 –", True,
                ("Support Logs · frontline",)),
    StaffMember("Mei Ling Tan", "meiling.tan@example.edu", "RF", "RF-02", "2026-08-01 –", True,
                ("Support Logs · frontline",)),
    StaffMember("Arjun Nair", "arjun.nair@example.edu", "RF", "RF-03", "2026-08-01 –", True,
                ("Support Logs · frontline",)),
    StaffMember("Tom Lim", "tom.lim@example.edu", "Other Staff", "—", "2026-09-15 –", True,
                ("Support Logs · view (aggregate)",)),
    StaffMember("Grace Ho", "grace.ho@example.edu", "RF", "RF-04", "2026-10-01 – 2026-12-31", False,
                ("Team Viewer",)),
)

STAFF_APPOINTMENTS = ("Master", "Residential Admin", "RSLM", "RF", "Other Staff")


@dataclass(frozen=True)
class RosterRA:
    name: str
    email: str
    neighborhood: str
    precinct: tuple[str, ...]  # derived from the tree: the Precinct's posts
    floors: str  # derived from the tree: the post's node's Dorms
    reports_to: tuple[str, ...]  # derived: every RF on the RA's Precinct
    linked: bool


# Precinct RF-02 holds a second, dated post: a backup is its own post.
TWO_RFS = ("Mei Ling Tan", "Grace Ho to 31 Dec")
RF_02 = ("RF-02", "RF-04")

RAS: tuple[RosterRA, ...] = (
    RosterRA("Chloe Lim", "chloe.lim@example.edu", "RA-01", ("RF-01",), "Cypress A 04-05-06", ("Daniel Koh",), True),
    RosterRA("Ethan Wong", "ethan.wong@example.edu", "RA-02", ("RF-01",), "Cypress A 07-08-09", ("Daniel Koh",), True),
    RosterRA("Hana Ito", "hana.ito@example.edu", "RA-03", ("RF-01",), "Cypress A 10-11-12", ("Daniel Koh",), True),
    RosterRA("Isaac Goh", "isaac.goh@example.edu", "RA-04", RF_02, "Cypress A 13-14-15", TWO_RFS, True),
    RosterRA("Jia Hui Ong", "jiahui.ong@example.edu", "RA-05", RF_02, "Cypress B 01-02-03", TWO_RFS, True),
    RosterRA("Kai Ng", "kai.ng@example.edu", "RA-06", RF_02, "Cypress B 04-05-06", TWO_RFS, True),
    RosterRA("Lucas Teo", "lucas.teo@example.edu", "RA-07", ("RF-03",), "Cypress B 07-08-09", ("Arjun Nair",), True),
    RosterRA("Maya Seah", "maya.seah@example.edu", "RA-08", ("RF-03",), "Cypress B 10-11-12", ("Arjun Nair",), True),
    RosterRA("Nur Aisyah", "nur.aisyah@example.edu", "RA-09", ("RF-03",), "Cypress B 13-14", ("Arjun Nair",), False),
)

RA_DATES = "2026-08-01 –"

VACANT_NEIGHBORHOODS = (("RA-10", "Cypress B 15-16", "RF-03"),)

PRECINCTS = ("RF-01", "RF-02", "RF-03")
BUILDINGS = ("Cypress A", "Cypress B")

STAFF_CSV = """\
Name,Email,Appointment,Post,From,To
Daniel Koh,daniel.koh@example.edu,RF,RF-01,2026-08-01,
Priya Raman,priya.raman@example.edu,RSLM,RSLM-01,2026-08-01,"""

RA_CSV = """\
Name,Email,Post,From,To
Chloe Lim,chloe.lim@example.edu,RA-01,2026-08-01,
Ethan Wong,ethan.wong@example.edu,RA-02,2026-08-01,"""


def linked_count(people: tuple[StaffMember, ...] | tuple[RosterRA, ...]) -> tuple[int, int]:
    """On the roster, and linked to a sign-in."""
    return len(people), sum(1 for p in people if p.linked)


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
        "enterprise_name": "LIM WEI LING, CHLOE",
        "student_id": "A0234567X",
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
        "enterprise_name": "NUR AISYAH BINTE ISMAIL",
        "history": (
            ("2026-08-01 08:05", "Added by roster import (Rachel Yeo)"),
            ("2026-09-02 10:41", "Sign-in not matched: roster email differs from the account's"),
        ),
    },
}


def _people() -> dict[str, Person]:
    people = [
        Person(_IDS[s.email], s.name, "staff", s.email, s.linked,
               (" · ".join(dict.fromkeys((s.appointment, s.node, s.dates))),), **_WORKED.get(s.email, {}))
        for s in STAFF
    ] + [
        Person(_IDS[r.email], r.name, "ra", r.email, r.linked,
               (f"RA · {r.neighborhood} ({r.floors}) · {RA_DATES}",),
               **({"enterprise_name": r.name.upper()} | _WORKED.get(r.email, {})))
        for r in RAS
    ]
    return {p.person_id: p for p in people}


PEOPLE = _people()

SUPER_ADMIN = "[Super-admin name]"

SYS_ADMINS = (
    ("Sam Lee", "sam.lee@example.edu", "Master", f"2026-08-01 by {SUPER_ADMIN}"),
    ("Rachel Yeo", "rachel.yeo@example.edu", "Residential Admin", f"2026-08-01 by {SUPER_ADMIN}"),
)

GRANT_CANDIDATES = ("Priya Raman · RSLM", "Daniel Koh · RF", "Tom Lim · Other Staff")

AUDIT_KINDS = ("Rosters", "Organization", "Access grants", "RA Leave", "RA Events")

AUDIT_RANGE = ("2026-10-01", "2026-10-26")

# (when, event, kind, actor, detail)
AUDIT_EVENTS = (
    ("2026-10-26 09:42", "Post added", "Organization", "Rachel Yeo",
     "RF-04 beside RF-02, 2026-10-01 to 2026-12-31"),
    ("2026-10-26 09:40", "Person added", "Rosters", "Rachel Yeo", "Grace Ho · RF on RF-04, from 2026-10-01"),
    ("2026-10-25 16:05", "Appointment ended", "Rosters", "Sam Lee", "RA-10 · previous RA, ended 2026-10-24"),
    ("2026-10-24 11:18", "Structure imported", "Organization", "Rachel Yeo",
     "14 nodes: 0 new, 2 changed, 0 retired; 1 floor gap (Cypress A 16)"),
    ("2026-10-24 11:02", "Level labels changed", "Organization", "Rachel Yeo", "Level 2: “Zone” → “Precinct”"),
    ("2026-10-20 14:30", "Team Viewer granted", "Access grants", "Sam Lee", "Grace Ho"),
    ("2026-09-15 10:11", "Person added", "Rosters", "Rachel Yeo", "Tom Lim · Other Staff"),
    ("2026-08-01 08:05", "Roster imported", "Rosters", "Rachel Yeo", "Staff roster: 6 added; RA roster: 10 added"),
    ("2026-08-01 08:00", "Sys admin granted", "Access grants", SUPER_ADMIN, "Sam Lee, Rachel Yeo"),
)
