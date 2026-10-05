"""Roster, relationship and observer CSVs refuse a cell longer than its
column (findings D11, 2026-10-05).

SQLite stores an over-long string and Postgres refuses it at flush, so
on the deployed database these files answered 500 instead of a report.
Each parser now checks every string it writes against the model's
declared ``String(n)``, as the Settings import already did; the friendly
label on a tag header is checked against ``session_field_labels.label``.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Reviewee, Reviewer, ReviewSession, User
from app.services.csv_imports import (
    parse_observer_csv,
    parse_reviewee_csv,
    parse_reviewer_csv,
)
from app.services.relationships import parse_relationship_csv

LONG = "x" * 256


def _fields(result) -> list[tuple[int | None, str | None]]:
    return [(i.row_number, i.field) for i in result.issues]


def test_reviewer_name_and_tag_over_their_columns() -> None:
    content = (
        "ReviewerName,ReviewerEmail,ReviewerTag2\n"
        f"{LONG},a@x.edu,ok\n"
        f"Bo,b@x.edu,{LONG}\n"
        "Cy,c@x.edu,ok\n"
    ).encode()
    result = parse_reviewer_csv(content)
    assert _fields(result) == [(1, "ReviewerName"), (2, "ReviewerTag2")]
    assert "256 characters; at most 255 fit" in result.issues[0].message
    assert [r.name for r in result.rows] == ["Cy"]


def test_reviewee_profile_link_over_2000() -> None:
    link = "https://x.edu/" + "p" * 2000
    content = (
        "RevieweeName,RevieweeEmail,ProfileLink\n"
        f"Al,a@x.edu,{link}\n"
    ).encode()
    result = parse_reviewee_csv(content)
    assert _fields(result) == [(1, "ProfileLink")]
    assert result.rows == []


def test_observer_name_over_its_column() -> None:
    content = f"ObserverEmail,ObserverName\no@x.edu,{LONG}\n".encode()
    result = parse_observer_csv(content)
    assert _fields(result) == [(1, "ObserverName")]


def test_a_tag_header_label_over_its_column() -> None:
    content = (
        f"ReviewerName,ReviewerEmail,ReviewerTag1.{LONG}\n"
        "Al,a@x.edu,t\n"
    ).encode()
    result = parse_reviewer_csv(content)
    assert result.rows == []
    assert len(result.issues) == 1
    # Names the column the operator wrote, not the slot it maps to.
    assert result.issues[0].field == "ReviewerTag1"
    assert result.issues[0].message.startswith(
        "The label on the ReviewerTag1 header is 256 characters"
    )


def test_a_legacy_photolink_cell_is_reported_under_its_own_header() -> None:
    link = "https://x.edu/" + "p" * 2000
    content = f"ReviewerName,ReviewerEmail,PhotoLink\nAl,a@x.edu,{link}\n".encode()
    result = parse_reviewer_csv(content)
    assert _fields(result) == [(1, "PhotoLink")]


def test_a_row_refused_for_length_does_not_reserve_its_email() -> None:
    """The later valid row is not "a duplicate of row 1": row 1 never
    parsed, so the caller cannot see it."""
    content = (
        "ReviewerName,ReviewerEmail\n"
        f"{LONG},a@x.edu\n"
        "Al,a@x.edu\n"
    ).encode()
    result = parse_reviewer_csv(content)
    assert _fields(result) == [(1, "ReviewerName")]
    assert [r.name for r in result.rows] == ["Al"]


def test_a_cell_over_the_csv_parser_limit_is_reported_not_raised() -> None:
    # 131,072 characters is the `csv` module's default field limit; a
    # file under MAX_BYTES can still carry a cell past it (Codex, #2830).
    huge = "x" * 200_000
    for content in (
        f"ReviewerEmail,ReviewerName\na@x.edu,{huge}\n".encode(),
        f"ReviewerEmail,{huge}\na@x.edu,Al\n".encode(),
    ):
        result = parse_reviewer_csv(content)
        assert result.rows == []
        assert result.is_blocked
        assert result.issues[0].message == (
            "A cell is longer than 131,072 characters"
        )


def test_relationship_tag_over_its_column(db: Session) -> None:
    op = User(email="op-len@x.edu", display_name="Op")
    db.add(op)
    db.flush()
    rs = ReviewSession(name="Len", code="rel-len", created_by_user_id=op.id)
    db.add(rs)
    db.flush()
    rvr = Reviewer(session_id=rs.id, name="R", email="r@x.edu")
    rve = Reviewee(session_id=rs.id, name="E", email_or_identifier="e@x.edu")
    db.add_all([rvr, rve])
    db.flush()
    content = (
        "ReviewerEmail,RevieweeEmail,PairContextTag3\n"
        f"r@x.edu,e@x.edu,{LONG}\n"
    ).encode()
    result = parse_relationship_csv(content, reviewers=[rvr], reviewees=[rve])
    assert _fields(result) == [(1, "PairContextTag3")]
    assert result.rows == []
