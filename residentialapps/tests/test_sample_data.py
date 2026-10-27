"""The mock CSVs in `residentialapps/docs/sample_data/` follow organization
by units (`residentialapps/guide/todo_master.md`, 2026-10-27) and agree with
one another, so the browser tests they feed start from a coherent Unit."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "docs" / "sample_data"

ROSTER = ["Name", "Email", "Appointment", "From", "To", "Enterprise name"]
LEVELS = ["Level1.Wing", "Level2.Precinct", "Level3.Neighborhood"]
UNITS = [*LEVELS, "Notes"]
HEADERS = {
    "staff_appointment_types": ["Title", "Abbrev"],
    "student_appointment_types": ["Title", "Abbrev"],
    "staff_roster": ROSTER,
    "ra_roster": [*ROSTER, "Student ID"],
    "organization_units": UNITS,
    "organization": [*UNITS, "Staff", "RA"],
}


def rows(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(newline="") as handle:
        return list(csv.DictReader(handle))


def test_every_mock_csv_has_its_ruled_header() -> None:
    files = sorted(DATA.glob("*.csv"))
    assert files
    for path in files:
        if path.name == "sign_ins.csv":
            continue
        kind = max((k for k in HEADERS if path.name.startswith(k)), key=len)
        with path.open(newline="") as handle:
            assert next(csv.reader(handle)) == HEADERS[kind], path.name


def test_the_rosters_hold_the_unit_s_people() -> None:
    staff_types = {t["Title"] for t in rows("staff_appointment_types.csv")}
    student_types = {t["Title"] for t in rows("student_appointment_types.csv")}
    staff = rows("staff_roster.csv")
    ras = rows("ra_roster.csv")
    assert {p["Appointment"] for p in staff} <= staff_types
    assert {p["Appointment"] for p in ras} <= student_types
    assert Counter(p["Appointment"] for p in staff) == {
        "Master": 1,
        "Residential Admin": 1,
        "Residential Student Life Manager": 3,
        "Residential Fellow": 9,
    }
    assert len(ras) == 30
    emails = [p["Email"] for p in (*staff, *ras)]
    assert len(emails) == len(set(emails))


def test_every_person_cell_names_someone_on_its_roster() -> None:
    """A slot's Staff are its RF and its Wing's RSLM, from the Staff roster;
    its RA is one person from the RA roster."""
    staff = {p["Email"]: p["Appointment"] for p in rows("staff_roster.csv")}
    ras = {p["Email"] for p in rows("ra_roster.csv")}
    for slot in rows("organization.csv"):
        people = slot["Staff"].split("; ")
        assert sorted(staff[e] for e in people) == ["Residential Fellow", "Residential Student Life Manager"], slot
        assert slot["RA"] in ras


def test_the_units_are_the_author_s_breakdown() -> None:
    units = rows("organization.csv")
    assert [len({row[level] for row in units}) for level in LEVELS] == [3, 9, 30]
    assert [{k: row[k] for k in UNITS} for row in units] == rows("organization_units.csv")
    assert all(row["Notes"] for row in units)
