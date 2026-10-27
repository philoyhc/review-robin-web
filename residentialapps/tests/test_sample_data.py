"""The mock CSVs in `residentialapps/docs/sample_data/` follow the setup
CSVs ruled in `residentialapps/guide/todo_master.md` and agree with one
another, so the browser tests they feed start from a coherent Unit."""

from __future__ import annotations

import csv
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "docs" / "sample_data"

HEADERS = {
    "appointment_types": ["Title", "Abbrev", "Type", "Level"],
    "structure": ["Level", "Dorms", "Post"],
    "staff_roster": ["Name", "Email", "Appointment", "Post", "From", "To", "Enterprise name"],
    "ra_roster": ["Name", "Email", "Post", "From", "To", "Enterprise name", "Student ID"],
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
        kind = next(k for k in HEADERS if path.name.startswith(k))
        with path.open(newline="") as handle:
            assert next(csv.reader(handle)) == HEADERS[kind], path.name


def test_the_clean_files_describe_one_coherent_unit() -> None:
    """Every post is a type at its level; every roster post is in the tree."""
    types = {(t["Abbrev"], t["Level"]) for t in rows("appointment_types.csv") if t["Abbrev"]}
    structure = rows("structure.csv")
    posts = [r["Post"] for r in structure]
    assert len(posts) == len(set(posts)), "a post appears twice"
    for row in structure:
        assert (row["Post"].split("-")[0], row["Level"]) in types, row
    for roster in ("staff_roster.csv", "ra_roster.csv"):
        for person in rows(roster):
            assert not person["Post"] or person["Post"] in posts, (roster, person["Name"])


def test_a_node_can_hold_two_posts() -> None:
    nodes: dict[tuple[str, str], list[str]] = {}
    for row in rows("structure.csv"):
        nodes.setdefault((row["Level"], row["Dorms"]), []).append(row["Post"])
    assert ["RF-02", "RF-04"] in nodes.values()
    assert ["Master", "Admin-01"] in nodes.values()
