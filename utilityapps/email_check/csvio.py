"""The checker's CSV in and out (spec §4, §6 output columns; segment U1,
rung 3). Pure functions: no Graph, no request, nothing kept.

A file is refused whole, with a message an operator can act on, rather
than processed in part (spec §4). Every row is kept, in order, with its
cells as uploaded; only the lookup key is normalized.
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

MAX_BYTES = 1024 * 1024
MAX_ROWS = 500

#: The columns the checker appends, in the spec's order (§6 example).
RESULT_COLUMNS = (
    "status",
    "match_type",
    "lookup_coverage",
    "recommended_email",
    "user_principal_name",
    "display_name",
    "entra_object_id",
    "duplicate_account_group",
    "notes",
)
#: The prefix a result column takes when the upload already has its name.
COLLISION_PREFIX = "check_"

#: A cell spreadsheet software may read as a formula (spec §4). A leading
#: `'` makes it text there and leaves the value readable.
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")

# Deliberately loose: one `@`, no whitespace, a dot in the domain. The
# directory decides what exists; this only keeps junk from being sent.
_ADDRESS = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class CsvRejected(ValueError):
    """The file as a whole cannot be checked; the message says why."""


@dataclass(frozen=True)
class Upload:
    """A parsed file: its header and rows, every row as long as the header."""

    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]

    @property
    def email_column(self) -> int | None:
        """The one column headed `email` (any case, trimmed), or `None`
        when there is none or more than one: the operator then chooses."""
        found = [i for i, name in enumerate(self.header) if name.strip().lower() == "email"]
        return found[0] if len(found) == 1 else None


@dataclass(frozen=True)
class Preview:
    rows: int
    valid: int
    invalid: int
    repeated: int
    keys: tuple[str, ...] = field(default=())

    @property
    def distinct(self) -> int:
        return len(self.keys)


def parse(data: bytes) -> Upload:
    if len(data) > MAX_BYTES:
        raise CsvRejected(f"The file is larger than {MAX_BYTES // 1024} KiB.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise CsvRejected("The file is not UTF-8 text. Save it as CSV UTF-8 and try again.") from None
    if "\x00" in text:
        raise CsvRejected("The file contains a NUL character, so it is not a CSV.")
    try:
        records = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    except csv.Error as exc:
        raise CsvRejected(f"The file is not a well-formed CSV ({exc}).") from None
    # Blank lines around the file are dropped. Inside it a blank line is a
    # row: a one-column file writes a blank cell as one (spec §4: kept).
    while records and not records[-1]:
        records.pop()
    while records and not records[0]:
        records.pop(0)
    if not records or not any(cell.strip() for cell in records[0]):
        raise CsvRejected("The file has no header row.")
    header, body = tuple(records[0]), records[1:]
    if not body:
        raise CsvRejected("The file has a header but no rows.")
    if len(body) > MAX_ROWS:
        raise CsvRejected(f"The file has {len(body)} rows; the limit is {MAX_ROWS}.")
    rows = []
    for number, record in enumerate(body, start=2):
        if len(record) > len(header):
            raise CsvRejected(f"Line {number} has more cells than the header.")
        rows.append(tuple(record) + ("",) * (len(header) - len(record)))
    return Upload(header=header, rows=tuple(rows))


def lookup_key(cell: str) -> str | None:
    """The address to look up: stripped and lowercased, or `None` when the
    cell is blank or not an address (`INVALID_INPUT`, never queried)."""
    key = cell.strip().lower()
    return key if _ADDRESS.fullmatch(key) else None


def preview(upload: Upload, column: int) -> Preview:
    seen: dict[str, None] = {}
    valid = invalid = repeated = 0
    for row in upload.rows:
        key = lookup_key(row[column])
        if key is None:
            invalid += 1
            continue
        valid += 1
        if key in seen:
            repeated += 1
        seen[key] = None
    return Preview(rows=len(upload.rows), valid=valid, invalid=invalid, repeated=repeated, keys=tuple(seen))


def result_header(header: Sequence[str]) -> tuple[str, ...]:
    """The input's header, then the result columns, each prefixed until
    it collides with no column already in the output (case-insensitive)."""
    taken = {name.strip().lower() for name in header}
    added = []
    for name in RESULT_COLUMNS:
        while name.lower() in taken:
            name = COLLISION_PREFIX + name
        taken.add(name.lower())
        added.append(name)
    return (*header, *added)


def safe_cell(value: str) -> str:
    return "'" + value if value.startswith(_FORMULA_START) else value


def write(upload: Upload, results: Sequence[Sequence[str]]) -> str:
    """The result CSV: every input row in order with its result cells
    (one sequence per row, in `RESULT_COLUMNS` order), every cell made
    safe to open in a spreadsheet."""
    if len(results) != len(upload.rows) or any(len(r) != len(RESULT_COLUMNS) for r in results):
        raise ValueError("one result of len(RESULT_COLUMNS) cells per input row")
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow([safe_cell(name) for name in result_header(upload.header)])
    for row, result in zip(upload.rows, results, strict=True):
        writer.writerow([safe_cell(cell) for cell in (*row, *result)])
    return out.getvalue()
