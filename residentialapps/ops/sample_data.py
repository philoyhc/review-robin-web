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

STAFF_COUNT = (8, 7)  # on the roster, linked to a sign-in
RA_COUNT = (9, 8)
