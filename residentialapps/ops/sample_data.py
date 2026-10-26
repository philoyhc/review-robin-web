"""Example data for segment 1B's placeholder screens: one Unit, "Example
College", with one Wing, three Precincts and ten Neighborhoods.

Every page that shows it is labelled "Sample data". It lives here alone so
that the wiring items (1B items 3–5) delete it in one place
(`residentialapps/guide/segment_1B_rosters_and_organization.md`).
"""

from __future__ import annotations

from dataclasses import dataclass

UNIT_NAME = "Example College"

LEVEL_LABELS = ("Wing", "Precinct", "Neighborhood")


@dataclass(frozen=True)
class Node:
    name: str
    level: int  # 0 the Unit, then 1–3 for the Unit's three levels
    floors: str
    appointed: str | None


TREE: tuple[Node, ...] = (
    Node(UNIT_NAME, 0, "Cypress A, Cypress B", "Sam Lee (Master) · Rachel Yeo (admin)"),
    Node("Cypress", 1, "Cypress A, Cypress B", "Priya Raman (RSLM)"),
    Node("RF1", 2, "Cypress A 04–12", "Daniel Koh"),
    Node("RA1", 3, "Cypress A 04-05-06", "Chloe Lim"),
    Node("RA2", 3, "Cypress A 07-08-09", "Ethan Wong"),
    Node("RA3", 3, "Cypress A 10-11-12", "Hana Ito"),
    Node("RF2", 2, "Cypress A 13–15; Cypress B 01–06", "Mei Ling Tan"),
    Node("RA4", 3, "Cypress A 13-14-15", "Isaac Goh"),
    Node("RA5", 3, "Cypress B 01-02-03", "Jia Hui Ong"),
    Node("RA6", 3, "Cypress B 04-05-06", "Kai Ng"),
    Node("RF3", 2, "Cypress B 07–16", "Arjun Nair"),
    Node("RA7", 3, "Cypress B 07-08-09", "Lucas Teo"),
    Node("RA8", 3, "Cypress B 10-11-12", "Maya Seah"),
    Node("RA9", 3, "Cypress B 13-14", "Nur Aisyah"),
    Node("RA10", 3, "Cypress B 15-16", None),
)

FLOOR_GAPS = ("Cypress A 16",)

APPOINTMENT_LEVELS = (
    ("RSLM", 1),
    ("RF", 2),
    ("RA", 3),
    ("Master, admin", 0),
)

STRUCTURE_CSV = """\
Level1.Wing,Level2.Precinct,Level3.Neighborhood,Floors
Cypress,RF1,RA1,Cypress A 04-05-06
Cypress,RF1,RA2,Cypress A 07-08-09
Cypress,RF3,RA9,Cypress B 13-14"""


@dataclass(frozen=True)
class StaffMember:
    name: str
    email: str
    appointment: str
    node: str
    dates: str
    linked: bool
    access: tuple[str, ...]  # read-only chips: what each person is granted


STAFF: tuple[StaffMember, ...] = (
    StaffMember("Sam Lee", "sam.lee@example.edu", "Master", UNIT_NAME, "2026-08-01 –", True,
                ("Sys admin", "Support Logs · senior")),
    StaffMember("Rachel Yeo", "rachel.yeo@example.edu", "admin", UNIT_NAME, "2026-08-01 –", True,
                ("Sys admin", "Support Logs · senior")),
    StaffMember("Priya Raman", "priya.raman@example.edu", "RSLM", "Cypress", "2026-08-01 –", True,
                ("Support Logs · frontline",)),
    StaffMember("Daniel Koh", "daniel.koh@example.edu", "RF", "RF1", "2026-08-01 –", True,
                ("Support Logs · frontline",)),
    StaffMember("Mei Ling Tan", "meiling.tan@example.edu", "RF", "RF2", "2026-08-01 –", True,
                ("Support Logs · frontline",)),
    StaffMember("Arjun Nair", "arjun.nair@example.edu", "RF", "RF3", "2026-08-01 –", True,
                ("Support Logs · frontline",)),
    StaffMember("Tom Lim", "tom.lim@example.edu", "Other Staff", "—", "2026-09-15 –", True,
                ("Support Logs · view (aggregate)",)),
    StaffMember("Grace Ho", "grace.ho@example.edu", "RF", "RF2 (backup)", "2026-10-01 – 2026-12-31", False,
                ("Team Viewer",)),
)

STAFF_APPOINTMENTS = ("Master", "admin", "RSLM", "RF", "Other Staff")


@dataclass(frozen=True)
class RosterRA:
    name: str
    email: str
    neighborhood: str
    precinct: str
    floors: str
    reports_to: str
    linked: bool
    backup: str | None = None  # a dated backup reporting line, when one is set


RAS: tuple[RosterRA, ...] = (
    RosterRA("Chloe Lim", "chloe.lim@example.edu", "RA1", "RF1", "Cypress A 04-05-06", "Daniel Koh", True),
    RosterRA("Ethan Wong", "ethan.wong@example.edu", "RA2", "RF1", "Cypress A 07-08-09", "Daniel Koh", True),
    RosterRA("Hana Ito", "hana.ito@example.edu", "RA3", "RF1", "Cypress A 10-11-12", "Daniel Koh", True),
    RosterRA("Isaac Goh", "isaac.goh@example.edu", "RA4", "RF2", "Cypress A 13-14-15", "Mei Ling Tan", True),
    RosterRA("Jia Hui Ong", "jiahui.ong@example.edu", "RA5", "RF2", "Cypress B 01-02-03", "Mei Ling Tan", True,
             "Grace Ho to 31 Dec"),
    RosterRA("Kai Ng", "kai.ng@example.edu", "RA6", "RF2", "Cypress B 04-05-06", "Mei Ling Tan", True),
    RosterRA("Lucas Teo", "lucas.teo@example.edu", "RA7", "RF3", "Cypress B 07-08-09", "Arjun Nair", True),
    RosterRA("Maya Seah", "maya.seah@example.edu", "RA8", "RF3", "Cypress B 10-11-12", "Arjun Nair", True),
    RosterRA("Nur Aisyah", "nur.aisyah@example.edu", "RA9", "RF3", "Cypress B 13-14", "Arjun Nair", False),
)

RA_DATES = "2026-08-01 –"

VACANT_NEIGHBORHOODS = (("RA10", "Cypress B 15-16", "RF3"),)

PRECINCTS = ("RF1", "RF2", "RF3")
BUILDINGS = ("Cypress A", "Cypress B")

STAFF_CSV = """\
Name,Email,Appointment,Node,From,To
Daniel Koh,daniel.koh@example.edu,RF,RF1,2026-08-01,
Priya Raman,priya.raman@example.edu,RSLM,Cypress,2026-08-01,"""

RA_CSV = """\
Name,Email,Level3.Neighborhood,From,To
Chloe Lim,chloe.lim@example.edu,RA1,2026-08-01,
Ethan Wong,ethan.wong@example.edu,RA2,2026-08-01,"""


def linked_count(people: tuple[StaffMember, ...] | tuple[RosterRA, ...]) -> tuple[int, int]:
    """On the roster, and linked to a sign-in."""
    return len(people), sum(1 for p in people if p.linked)
