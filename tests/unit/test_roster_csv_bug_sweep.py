"""Roster CSV parse fixes from `guide/findings_2026-10-16_bugs.md`.

* **S7** — a NUL character refuses the file; Postgres refused it at
  flush with a 500, SQLite stored it.
* **S9** — two headers naming one column refuse the file; `DictReader`
  kept the last and dropped the other silently.
"""

from __future__ import annotations

import pytest

from app.services import csv_imports, relationships


@pytest.mark.parametrize(
    "parse,content",
    [
        (
            csv_imports.parse_reviewer_csv,
            b"ReviewerName,ReviewerEmail\nAda\x00,ada@example.org\n",
        ),
        (
            csv_imports.parse_reviewee_csv,
            b"RevieweeName,RevieweeEmail\nAda,ada@example.org\x00\n",
        ),
        (
            csv_imports.parse_observer_csv,
            b"ObserverEmail,ObserverName\no@example.org,O\x00\n",
        ),
    ],
)
def test_a_nul_character_refuses_the_roster_file(parse, content: bytes) -> None:
    result = parse(content)

    assert result.is_blocked
    assert result.rows == []
    assert [issue.message for issue in result.issues] == [csv_imports.NUL_MESSAGE]


def test_decode_csv_refuses_a_nul_for_every_roster_importer() -> None:
    """Relationships reads through the same `decode_csv`."""
    text, issue = csv_imports.decode_csv(b"a,b\n\x00,c\n", "relationships")
    assert text is None
    assert issue is not None and issue.message == csv_imports.NUL_MESSAGE
    assert relationships.decode_csv is csv_imports.decode_csv


@pytest.mark.parametrize(
    "header",
    [
        "ReviewerName,ReviewerEmail,ReviewerTag1,ReviewerTag1.Tutor",
        "ReviewerName,ReviewerEmail,ReviewerTag1.Tutor,ReviewerTag1.Group",
        "ReviewerName,ReviewerEmail,ReviewerEmail",
    ],
)
def test_a_column_named_twice_refuses_the_file(header: str) -> None:
    content = f"{header}\nAda,ada@example.org,x,y\n".encode()

    result = csv_imports.parse_reviewer_csv(content)

    assert result.is_blocked
    assert result.rows == []
    assert [issue.message for issue in result.issues] == [
        f"The {header.split(',')[-1].split('.')[0]} column appears more than once"
    ]


def test_blank_header_cells_are_not_a_repeat() -> None:
    """Trailing commas give empty header cells; they name no column."""
    content = b"ReviewerName,ReviewerEmail,,\nAda,ada@example.org,,\n"

    result = csv_imports.parse_reviewer_csv(content)

    assert not result.is_blocked, result.issues
    assert len(result.rows) == 1


def test_a_repeated_column_the_file_does_not_define_is_ignored() -> None:
    """An extra column is ignored (``spec/csv_contracts.md`` §1), so two
    of one lose nothing and don't refuse the file (findings S9's read)."""
    content = b"ReviewerName,ReviewerEmail,Notes,Notes\nAda,ada@example.org,a,b\n"

    result = csv_imports.parse_reviewer_csv(content)

    assert not result.is_blocked, result.issues
    assert len(result.rows) == 1
