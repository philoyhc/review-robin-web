"""Segment 19C Item 1 — roster-CSV friendly-label header transport.

Pure (no-DB) coverage for the header grammar: the ``split_header`` /
``normalize_headers`` helpers and the parse-side capture on
``parse_reviewer_csv`` / ``parse_reviewee_csv``. The import→storage→
export round-trip, bare-header-clears, and the export header live in
``tests/integration/test_field_label_roster_roundtrip.py``.
"""
from __future__ import annotations

from app.services import field_label_csv
from app.services.csv_imports import parse_reviewee_csv, parse_reviewer_csv


def _b(text: str) -> bytes:
    return text.encode("utf-8")


# --------------------------------------------------------------------------- #
# split_header — first-period split, labelable columns only
# --------------------------------------------------------------------------- #


def test_split_bare_labelable_column() -> None:
    assert field_label_csv.split_header("ReviewerTag1") == ("ReviewerTag1", None)


def test_split_labelable_column_with_suffix() -> None:
    assert field_label_csv.split_header("ReviewerTag1.Tutor") == (
        "ReviewerTag1",
        "Tutor",
    )


def test_split_on_first_period_only_label_may_contain_periods() -> None:
    assert field_label_csv.split_header("RevieweeTag2.Dept. Head") == (
        "RevieweeTag2",
        "Dept. Head",
    )


def test_non_labelable_column_never_splits() -> None:
    # An identity / unknown column keeps its whole name even with a period.
    assert field_label_csv.split_header("ReviewerName.Foo") == (
        "ReviewerName.Foo",
        None,
    )
    assert field_label_csv.split_header("Notes.2024") == ("Notes.2024", None)


# --------------------------------------------------------------------------- #
# normalize_headers — canonical names + captured labels
# --------------------------------------------------------------------------- #


def test_normalize_strips_suffix_and_captures() -> None:
    canonical, captured = field_label_csv.normalize_headers(
        ["ReviewerName", "ReviewerEmail", "ReviewerTag1.Tutor", "ReviewerTag2"]
    )
    assert canonical == [
        "ReviewerName",
        "ReviewerEmail",
        "ReviewerTag1",
        "ReviewerTag2",
    ]
    assert captured == {("reviewer", "tag_1"): "Tutor"}


def test_normalize_empty_suffix_captures_nothing() -> None:
    canonical, captured = field_label_csv.normalize_headers(
        ["RevieweeTag1.", "RevieweeTag2.  "]
    )
    assert canonical == ["RevieweeTag1", "RevieweeTag2"]
    assert captured == {}


def test_normalize_pair_context_columns() -> None:
    canonical, captured = field_label_csv.normalize_headers(
        ["ReviewerEmail", "RevieweeEmail", "PairContextTag1.Mentor of"]
    )
    assert canonical == ["ReviewerEmail", "RevieweeEmail", "PairContextTag1"]
    assert captured == {("pair_context", "1"): "Mentor of"}


# --------------------------------------------------------------------------- #
# parse capture — labels ride in, values still read under canonical name
# --------------------------------------------------------------------------- #


def test_reviewer_parse_captures_label_and_still_reads_value() -> None:
    result = parse_reviewer_csv(
        _b(
            "ReviewerName,ReviewerEmail,ReviewerTag1.Tutor\n"
            "Alice,alice@example.edu,senior\n"
        )
    )
    assert result.issues == []
    assert result.field_labels == {("reviewer", "tag_1"): "Tutor"}
    # The tag *value* is still read under the bare canonical column.
    assert result.rows[0].tag_1 == "senior"


def test_reviewee_parse_captures_multiple_labels() -> None:
    result = parse_reviewee_csv(
        _b(
            "RevieweeName,RevieweeEmail,RevieweeTag1.House,RevieweeTag2.Year\n"
            "Carol,carol@example.edu,Gryffindor,3\n"
        )
    )
    assert result.issues == []
    assert result.field_labels == {
        ("reviewee", "tag_1"): "House",
        ("reviewee", "tag_2"): "Year",
    }
    assert result.rows[0].tag_1 == "Gryffindor"
    assert result.rows[0].tag_2 == "3"


def test_bare_header_captures_nothing() -> None:
    result = parse_reviewer_csv(
        _b("ReviewerName,ReviewerEmail,ReviewerTag1\nAlice,alice@example.edu,x\n")
    )
    assert result.field_labels == {}
