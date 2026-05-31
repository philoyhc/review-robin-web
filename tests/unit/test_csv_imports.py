from __future__ import annotations

from app.schemas.validation import Severity
from app.services.csv_imports import parse_reviewee_csv, parse_reviewer_csv


def _b(text: str) -> bytes:
    return text.encode("utf-8")


def test_valid_reviewer_csv_parses_two_rows() -> None:
    csv_text = (
        "ReviewerName,ReviewerEmail,ReviewerTag1\n"
        "Alice,alice@example.edu,senior\n"
        "Bob,bob@example.edu,\n"
    )
    result = parse_reviewer_csv(_b(csv_text))

    assert result.issues == []
    assert len(result.rows) == 2
    assert result.rows[0].name == "Alice"
    assert result.rows[0].tag_1 == "senior"
    assert result.rows[1].tag_1 is None


def test_valid_reviewer_csv_with_photolink_populates_profile_link() -> None:
    csv_text = (
        "ReviewerName,ReviewerEmail,PhotoLink\n"
        "Carol,carol@example.edu,https://example.edu/c.jpg\n"
        "Dan,dan@example.edu,\n"
    )
    result = parse_reviewer_csv(_b(csv_text))

    assert result.issues == []
    assert len(result.rows) == 2
    assert result.rows[0].profile_link == "https://example.edu/c.jpg"
    assert result.rows[1].profile_link is None


def test_reviewer_missing_email_column_blocks() -> None:
    csv_text = "ReviewerName,Department\nAlice,Math\n"

    result = parse_reviewer_csv(_b(csv_text))

    assert result.is_blocked
    assert result.rows == []
    assert any(
        i.severity is Severity.error and i.field == "ReviewerEmail"
        for i in result.issues
    )


def test_reviewer_duplicate_email_is_blocking_with_row_number() -> None:
    csv_text = (
        "ReviewerName,ReviewerEmail\n"
        "Alice,dup@example.edu\n"
        "Alice,dup@example.edu\n"
    )
    result = parse_reviewer_csv(_b(csv_text))

    assert result.is_blocked
    dup = next(i for i in result.issues if "Duplicate" in i.message)
    assert dup.row_number == 2
    assert "row 1" in dup.message


def test_reviewer_invalid_emails_are_blocking() -> None:
    csv_text = (
        "ReviewerName,ReviewerEmail\n"
        "Alice,alice@\n"
        "Bob,bob\n"
        "Carol,@example.edu\n"
    )
    result = parse_reviewer_csv(_b(csv_text))

    assert result.is_blocked
    bad = [i for i in result.issues if "not a valid email" in i.message]
    assert len(bad) == 3
    assert {i.row_number for i in bad} == {1, 2, 3}


def test_valid_reviewee_csv_with_photolink_populates_profile_link() -> None:
    csv_text = (
        "RevieweeName,RevieweeEmail,PhotoLink\n"
        "Carol,carol@example.edu,https://example.edu/c.jpg\n"
        "Dan,dan-2026,\n"
    )
    result = parse_reviewee_csv(_b(csv_text))

    assert result.issues == []
    assert len(result.rows) == 2
    assert result.rows[0].profile_link == "https://example.edu/c.jpg"
    assert result.rows[1].profile_link is None
    assert result.rows[1].email_or_identifier == "dan-2026"


def test_reviewee_non_email_identifier_is_accepted() -> None:
    """No-`@` reviewee values import as identifiers (asymmetric mode)."""
    csv_text = (
        "RevieweeName,RevieweeEmail\n"
        "Dan,dan-2026\n"
        "Eve,student-id-7\n"
    )
    result = parse_reviewee_csv(_b(csv_text))

    assert result.issues == []
    assert {r.email_or_identifier for r in result.rows} == {"dan-2026", "student-id-7"}


def test_reviewee_malformed_at_containing_identifier_is_blocking() -> None:
    """`foo@` / `@bar` were importing cleanly and dying later on send."""
    csv_text = (
        "RevieweeName,RevieweeEmail\n"
        "Carol,foo@\n"
        "Dan,@bar\n"
        "Eve,no-at-sign\n"
    )
    result = parse_reviewee_csv(_b(csv_text))

    assert result.is_blocked
    bad = [i for i in result.issues if "not a valid email" in i.message]
    assert {i.row_number for i in bad} == {1, 2}
    assert all(i.field == "RevieweeEmail" for i in bad)
    assert {r.email_or_identifier for r in result.rows} == {"no-at-sign"}


def test_reviewee_missing_name_column_blocks() -> None:
    csv_text = "RevieweeEmail\ncarol@example.edu\n"

    result = parse_reviewee_csv(_b(csv_text))

    assert result.is_blocked
    assert result.rows == []
    assert any(i.field == "RevieweeName" for i in result.issues)


def test_reviewer_csv_with_utf8_bom_parses() -> None:
    csv_bytes = "﻿".encode("utf-8") + _b(
        "ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n"
    )
    result = parse_reviewer_csv(csv_bytes)

    assert result.issues == []
    assert len(result.rows) == 1


def test_reviewer_unknown_columns_are_ignored() -> None:
    csv_text = (
        "ReviewerName,ReviewerEmail,Department\n"
        "Alice,alice@example.edu,Math\n"
    )
    result = parse_reviewer_csv(_b(csv_text))

    assert result.issues == []
    assert len(result.rows) == 1


def test_reviewer_empty_required_cell_is_blocking() -> None:
    csv_text = (
        "ReviewerName,ReviewerEmail\n"
        ",alice@example.edu\n"
        "Bob,\n"
    )
    result = parse_reviewer_csv(_b(csv_text))

    assert result.is_blocked
    assert result.rows == []
    assert {i.field for i in result.issues if i.row_number} == {
        "ReviewerName",
        "ReviewerEmail",
    }


def test_reviewer_same_email_different_name_is_blocking() -> None:
    """Email is the unique person-id; same email + different name errors."""
    csv_text = (
        "ReviewerName,ReviewerEmail\n"
        "Alice,shared@example.edu\n"
        "Alex,shared@example.edu\n"
    )
    result = parse_reviewer_csv(_b(csv_text))

    assert result.is_blocked
    mismatch = next(i for i in result.issues if "names must match" in i.message)
    assert mismatch.row_number == 2
    assert "row 1" in mismatch.message
    assert "Alice" in mismatch.message


def test_reviewee_same_identifier_different_name_is_blocking() -> None:
    """Same rule for reviewees; works for both email and non-email identifiers."""
    csv_text = (
        "RevieweeName,RevieweeEmail\n"
        "Carol,shared@example.edu\n"
        "Caroline,shared@example.edu\n"
        "Dan,dan-2026\n"
        "Daniel,dan-2026\n"
    )
    result = parse_reviewee_csv(_b(csv_text))

    assert result.is_blocked
    mismatches = [i for i in result.issues if "names must match" in i.message]
    assert {i.row_number for i in mismatches} == {2, 4}


def test_reviewer_oversize_file_is_blocking() -> None:
    big = b"ReviewerName,ReviewerEmail\n" + (b"A,a@b.c\n" * 200_000)
    result = parse_reviewer_csv(big)

    assert result.is_blocked
    assert any("too large" in i.message.lower() for i in result.issues)
