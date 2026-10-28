"""The mock CSVs in `residentialapps/docs/sample_data/` follow the slots,
the rosters' appointments, terms and assignments (`residentialapps/guide/todo_master.md`,
2026-10-27 and 2026-10-28) and agree with one another, so the browser tests
they feed start from a coherent Unit."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "docs" / "sample_data"

ROSTER = ["Name", "Email", "Appointment", "Abbrev", "From", "To", "Enterprise name"]
LEVELS = ["Level1.Wing", "Level2.Precinct", "Level3.Neighborhood"]
UNITS = [*LEVELS, "Notes"]
HEADERS = {
    "staff_roster": ROSTER,
    "ra_roster": [*ROSTER, "Student ID"],
    "assignments_slots": ["Term", *UNITS],
    "assignments": ["Term", *UNITS, "Staff", "RA"],
    "terms": ["Year", "Term", "Name", "Start", "End"],
    "quick_setup": [*UNITS, "Roster", "Name", "Email", "Appointment", "Abbrev", "From", "To", "Enterprise name",
                    "Student ID"],
}


def rows(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(newline="") as handle:
        return list(csv.DictReader(handle))


def slots(name: str = "assignments.csv") -> list[dict[str, str]]:
    """An Assignments file's rows less their Term."""
    return [{k: v for k, v in row.items() if k != "Term"} for row in rows(name)]


def test_every_mock_csv_has_its_ruled_header() -> None:
    files = sorted(DATA.glob("*.csv"))
    assert files
    for path in files:
        if path.name == "sign_ins.csv":
            continue
        kind = max((k for k in HEADERS if path.name.startswith(k)), key=len)
        with path.open(newline="") as handle:
            assert next(csv.reader(handle)) == HEADERS[kind], path.name


def held(people: list[dict[str, str]]) -> dict[str, set[str]]:
    """Each appointment a roster's rows hold, with the abbreviations given it."""
    pairs: dict[str, set[str]] = {}
    for p in people:
        pairs.setdefault(p["Appointment"], set()).add(p["Abbrev"])
    return pairs


def test_the_rosters_hold_the_unit_s_people() -> None:
    staff = rows("staff_roster.csv")
    ras = rows("ra_roster.csv")
    assert held(staff) == {
        "Master": {"Master"},
        "Residential Admin": {"Admin"},
        "Residential Student Life Manager": {"RSLM"},
        "Residential Fellow": {"RF"},
    }  # one abbreviation per appointment, every row giving it
    assert held(ras) == {"Residential Assistant": {"RA"}}
    assert Counter(p["Appointment"] for p in staff) == {
        "Master": 1,
        "Residential Admin": 1,
        "Residential Student Life Manager": 3,
        "Residential Fellow": 9,
    }
    assert len(ras) == 30
    emails = [p["Email"] for p in (*staff, *ras)]
    assert len(emails) == len(set(emails))


def test_the_roster_error_files_warn_on_one_identity_change_each() -> None:
    """Ruling point 2: a known email with a different name, enterprise name
    or student ID warns. Each error file has one such row, differing from
    the roster in exactly the fields its README row names."""
    for file, roster, email, changed in (
        ("staff_roster_errors.csv", "staff_roster.csv", "meiling.tan@example.edu", {"Name", "Enterprise name"}),
        ("ra_roster_errors.csv", "ra_roster.csv", "ethan.wong@example.edu", {"Student ID"}),
    ):
        on_file = {p["Email"]: p for p in rows(roster)}
        row = next(r for r in rows(file) if r["Email"] == email)
        assert {k for k in row if row[k] != on_file[email][k]} == changed, file


def test_the_terms_never_overlap_and_match_the_pages() -> None:
    """Up to five a year, numbered in order, each ending before the next
    starts (author, 2026-10-28)."""
    from residentialapps.residentialops import sample_data

    terms = rows("terms.csv")
    assert [(t.year, str(t.number), t.name, str(t.start), str(t.end)) for t in sample_data.TERMS] == [
        tuple(t.values()) for t in terms
    ]
    for earlier, later in zip(sample_data.TERMS, sample_data.TERMS[1:]):
        assert earlier.end < later.start
    years = Counter(t["Year"] for t in terms)
    assert max(years.values()) <= sample_data.MAX_TERMS
    for year in years:
        assert [t["Term"] for t in terms if t["Year"] == year] == [str(n) for n in range(1, years[year] + 1)]
    lines = (DATA / "terms.csv").read_text().splitlines()
    assert all(line in lines for line in sample_data.TERMS_CSV.splitlines())


def test_the_assignments_files_name_set_up_terms() -> None:
    """Each file's Term is one the Terms page holds (author, 2026-10-28):
    the clean files the current term, the Add a term file the next, with
    two RAs swapping slots; the errors file adds a past term and one not
    set up."""
    from residentialapps.residentialops import sample_data

    codes = {t.code: t for t in sample_data.TERMS}
    term1, term2 = (t for t in sample_data.TERMS if t.year == "AY2026-2027" and t.number in (1, 2))
    for file in ("assignments.csv", "assignments_slots.csv"):
        assert {row["Term"] for row in rows(file)} == {term1.code} == {sample_data.CURRENT_TERM.code}, file
    assert {row["Term"] for row in rows("assignments_term2.csv")} == {term2.code}
    first, second = slots(), slots("assignments_term2.csv")
    assert [{k: v for k, v in r.items() if k != "RA"} for r in first] == [
        {k: v for k, v in r.items() if k != "RA"} for r in second
    ]
    swapped = [(a["Level3.Neighborhood"], a["RA"], b["RA"]) for a, b in zip(first, second) if a["RA"] != b["RA"]]
    assert sorted(ra for _, ra, _ in swapped) == sorted(ra for _, _, ra in swapped) and len(swapped) == 2
    errors = [row["Term"] for row in rows("assignments_errors.csv")]
    assert [codes[e].status for e in errors if e in codes and e != term1.code] == ["Past"]
    assert [e for e in errors if e not in codes] == ["AY2027-2028 Term 1"]


def test_one_assignee_starts_partway_into_the_term() -> None:
    """The guard's warning case: Umairah Salleh's appointment starts 14
    days into Term 1, and her assignment stands (author, 2026-10-28)."""
    from residentialapps.residentialops import sample_data

    start = sample_data.CURRENT_TERM.start
    late = {p["Email"]: p["From"] for p in (*rows("staff_roster.csv"), *rows("ra_roster.csv")) if p["From"] > str(start)}
    assert late == {"umairah.salleh@example.edu": "2026-08-17"}
    assert sample_data.late_starts(sample_data.CURRENT_TERM) == (("Umairah Salleh", "Willow B 10-11-12", 14),)


def test_the_guard_covers_qualifies_and_refuses() -> None:
    """Ruling point 6: whole cover qualifies (0), part cover warns with the
    days missed at either end, and none at all is refused (None)."""
    from residentialapps.residentialops.sample_data import CURRENT_TERM as term, gap_days

    assert gap_days("2026-08-01 –", term) == 0
    assert gap_days("2026-08-17 –", term) == 14
    assert gap_days("2026-08-01 – 2026-12-31", term) == 10  # ends ten days early
    assert gap_days("2026-08-10 – 2027-01-05", term) == 7 + 5
    assert gap_days("2027-01-11 –", term) is None  # starts after the term
    assert gap_days("2025-01-01 – 2026-08-02", term) is None  # ends before it


def test_every_person_cell_names_someone_on_its_roster() -> None:
    """A slot's Staff are its RF and its Wing's RSLM, from the Staff roster;
    its RA is one person from the RA roster."""
    staff = {p["Email"]: p["Appointment"] for p in rows("staff_roster.csv")}
    ras = {p["Email"] for p in rows("ra_roster.csv")}
    for slot in slots():
        people = slot["Staff"].split("; ")
        assert sorted(staff[e] for e in people) == ["Residential Fellow", "Residential Student Life Manager"], slot
        assert slot["RA"] in ras


def test_the_units_are_the_author_s_breakdown() -> None:
    units = slots()
    assert [len({row[level] for row in units}) for level in LEVELS] == [3, 9, 30]
    assert [{k: row[k] for k in UNITS} for row in units] == slots("assignments_slots.csv")
    assert all(row["Notes"] for row in units)


def test_the_placeholders_show_the_mock_data() -> None:
    """The pages' sample module is these files: the same people, slots and
    cells, and its CSV excerpts are rows of them."""
    from residentialapps.residentialops import sample_data

    staff, ras = rows("staff_roster.csv"), rows("ra_roster.csv")
    def dates(p: dict[str, str]) -> str:
        return f"{p['From']} – {p['To']}".rstrip()

    assert [(p.name, p.email, p.appointment, p.abbrev, p.dates, p.enterprise_name) for p in sample_data.STAFF] == [
        (p["Name"], p["Email"], p["Appointment"], p["Abbrev"], dates(p), p["Enterprise name"]) for p in staff
    ]
    assert [
        (p.name, p.email, p.appointment, p.abbrev, p.dates, p.enterprise_name, p.student_id) for p in sample_data.RAS
    ] == [
        (p["Name"], p["Email"], p["Appointment"], p["Abbrev"], dates(p), p["Enterprise name"], p["Student ID"])
        for p in ras
    ]
    name = {p["Email"]: p["Name"] for p in (*staff, *ras)}
    assert [
        (s.wing, s.precinct, s.neighborhood, s.notes, s.staff, s.ras) for s in sample_data.SLOTS
    ] == [
        (*(row[k] for k in UNITS), tuple(name[e] for e in row["Staff"].split("; ")), (name[row["RA"]],))
        for row in slots()
    ]
    for sample, file in (
        (sample_data.STAFF_CSV, "staff_roster.csv"),
        (sample_data.RA_CSV, "ra_roster.csv"),
        (sample_data.ASSIGNMENTS_CSV, "assignments.csv"),
    ):
        lines = (DATA / file).read_text().splitlines()
        assert all(line in lines for line in sample.splitlines()), file


def test_quick_setup_holds_every_other_file() -> None:
    """Read back, the Quick setup file gives the rosters, the appointments
    they hold and the Assignments file with every cell. Its format is held
    for further rulings (2026-10-28); this checks the file as it stands."""
    quick = rows("quick_setup.csv")
    slot_of: dict[str, dict[str, str]] = {}
    for row in quick:  # a slot is given once; later rows carry its name alone
        name = row["Level3.Neighborhood"]
        if name in slot_of:
            assert not any(row[k] for k in ("Level1.Wing", "Level2.Precinct", "Notes")), name
            row.update(slot_of[name])
        elif name:
            slot_of[name] = {k: row[k] for k in UNITS}
    first: dict[str, dict[str, str]] = {}
    for row in quick:  # details are given once, on a person's first row
        if row["Email"] in first:
            assert not any(row[k] for k in ("Roster", "Name", "Appointment", "From")), row["Email"]
            row.update({k: v for k, v in first[row["Email"]].items() if k not in UNITS})
        else:
            first[row["Email"]] = dict(row)
    person = ["Name", "Email", "Appointment", "Abbrev", "From", "To", "Enterprise name"]
    for roster, file in (("Staff", "staff_roster.csv"), ("RA", "ra_roster.csv")):
        extra = ["Student ID"] if roster == "RA" else []
        people = {r["Email"]: {k: r[k] for k in person + extra} for r in quick if r["Roster"] == roster}
        by_email = {p["Email"]: p for p in rows(file)}
        assert people == by_email, file  # the same people; the file's order is its own
    slots_of_file = slots()
    held: dict[str, dict[str, str]] = {}
    for r in quick:
        if r["Level3.Neighborhood"]:
            slot = held.setdefault(r["Level3.Neighborhood"], {k: r[k] for k in UNITS} | {"Staff": [], "RA": []})
            slot[r["Roster"]].append(r["Email"])
    assert [s | {"Staff": "; ".join(s["Staff"]), "RA": "; ".join(s["RA"])} for s in held.values()] == slots_of_file
