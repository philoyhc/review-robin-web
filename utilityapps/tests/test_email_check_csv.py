"""The checker's CSV in and out (`utilityapps/email_check/csvio.py`;
spec §4 and acceptance tests 1, 2, 10 and 12's formula guard)."""

from __future__ import annotations

import csv
import io

import pytest

from utilityapps.email_check import csvio
from utilityapps.email_check.csvio import CsvRejected, parse


def _csv(*lines: str) -> bytes:
    return ("\r\n".join(lines) + "\r\n").encode()


def test_email_column_is_found_by_name_in_any_case() -> None:
    assert parse(_csv("Name, EMAIL ,Role", "A,a@x.edu,R")).email_column == 1


@pytest.mark.parametrize("header", ["Name,Work email", "email,Email"])
def test_no_single_email_column_leaves_the_choice(header: str) -> None:
    assert parse(_csv(header, "a,b")).email_column is None


def test_bom_and_quoting_are_read() -> None:
    data = b"\xef\xbb\xbfemail,note\r\n" + b'a@x.edu,"one, two\r\nlines"\r\n'
    upload = parse(data)
    assert upload.header == ("email", "note")
    assert upload.rows == (("a@x.edu", "one, two\r\nlines"),)


def test_short_rows_are_padded_and_inner_blank_lines_kept() -> None:
    upload = parse(b"\r\n" + _csv("email,a,b", "x@y.edu", "", ",,") + b"\r\n\r\n")
    assert upload.rows == (("x@y.edu", "", ""), ("", "", ""), ("", "", ""))


def test_a_one_column_file_keeps_a_blank_cell_as_a_row() -> None:
    upload = parse(_csv("email", "a@x.edu", "", "b@x.edu"))
    assert upload.rows == (("a@x.edu",), ("",), ("b@x.edu",))


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"", "no header row"),
        (b",,\r\n", "no header row"),
        (_csv("email"), "header but no rows"),
        (b"email\r\n\xff\xfe\r\n", "not UTF-8"),
        (b"email\r\na\x00b\r\n", "NUL"),
        (_csv("email", "a,b"), "Line 2 has more cells"),
        (b'email\r\n"unclosed\r\n', "not a well-formed CSV"),
        (_csv("email", *["a@x.edu"] * (csvio.MAX_ROWS + 1)), "the limit is 500"),
        (b"email\r\n" + b"a" * csvio.MAX_BYTES, "larger than 1024 KiB"),
    ],
)
def test_a_file_that_cannot_be_checked_is_refused_whole(data: bytes, message: str) -> None:
    with pytest.raises(CsvRejected, match=message):
        parse(data)


def test_a_cell_over_the_csv_modules_limit_is_named() -> None:
    """The limit is process-wide and RRW relies on it, so it is reported
    rather than raised; a cell just under it is kept whole."""
    limit = csv.field_size_limit()
    kept = parse(_csv("email,note", "a@x.edu," + "x" * limit))
    assert kept.rows[0][1] == "x" * limit
    with pytest.raises(CsvRejected, match=f"A cell is longer than {limit:,} characters"):
        parse(_csv("email,note", "a@x.edu," + "x" * (limit + 1)))


def test_the_row_limit_is_inclusive() -> None:
    assert len(parse(_csv("email", *["a@x.edu"] * csvio.MAX_ROWS)).rows) == csvio.MAX_ROWS


@pytest.mark.parametrize(
    ("cell", "key"),
    [
        ("  Jane.Tan@Example.EDU ", "jane.tan@example.edu"),
        ("", None),
        ("   ", None),
        ("jane", None),
        ("jane@example", None),
        ("a b@x.edu", None),
        ("a@@x.edu", None),
    ],
)
def test_lookup_key_strips_and_lowercases_or_refuses(cell: str, key: str | None) -> None:
    assert csvio.lookup_key(cell) == key


def test_preview_counts_invalid_and_repeats_and_keys_once() -> None:
    upload = parse(_csv("email", "a@x.edu", "A@X.edu ", "", "nope", "b@x.edu", "a@x.edu"))
    p = csvio.preview(upload, 0)
    assert (p.rows, p.valid, p.invalid, p.repeated, p.distinct) == (6, 4, 2, 2, 2)
    assert p.keys == ("a@x.edu", "b@x.edu")


def test_result_columns_follow_the_input_and_dodge_collisions() -> None:
    header = csvio.result_header(("email", "Status", "check_status", "notes"))
    assert header[:4] == ("email", "Status", "check_status", "notes")
    assert header[4] == "check_check_status"
    assert header[-1] == "check_notes"
    assert header[5:-1] == csvio.RESULT_COLUMNS[1:-1]


def test_write_keeps_every_row_in_order_with_its_result() -> None:
    upload = parse(_csv("Name,email", "B,b@x.edu", "A,a@x.edu", "B,b@x.edu"))
    results = [[str(i)] * len(csvio.RESULT_COLUMNS) for i in range(3)]
    rows = list(csv.reader(io.StringIO(csvio.write(upload, results))))
    assert rows[0] == ["Name", "email", *csvio.RESULT_COLUMNS]
    assert [r[:2] for r in rows[1:]] == [["B", "b@x.edu"], ["A", "a@x.edu"], ["B", "b@x.edu"]]
    assert [r[2] for r in rows[1:]] == ["0", "1", "2"]


@pytest.mark.parametrize("value", ["=1+1", "+1", "-1", "@SUM(A1)", "\tx", "\rx"])
def test_a_cell_a_spreadsheet_would_run_is_made_text(value: str) -> None:
    upload = parse(_csv("email,note", f'a@x.edu,"{value}"'))
    out = csvio.write(upload, [[value] + [""] * (len(csvio.RESULT_COLUMNS) - 1)])
    row = list(csv.reader(io.StringIO(out)))[1]
    assert row[1] == "'" + value and row[2] == "'" + value


def test_write_refuses_results_that_do_not_match_the_rows() -> None:
    upload = parse(_csv("email", "a@x.edu"))
    with pytest.raises(ValueError):
        csvio.write(upload, [])
