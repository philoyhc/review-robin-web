"""What a refused roster upload reports: the kinds of problem the file
has, each with how many rows have it.

``guide/quick_setup_update.md`` Item 3 (author, 2026-10-13). Quick
Setup's banner and the four Setup pages' upload cards (Reviewers,
Reviewees, Relationships, Observers) read the same lines from here, so
the two surfaces cannot disagree about one file. Neither lists rows: a
file with a hundred bad rows would print a hundred lines.

Validate is not a caller. It reports on the saved session, which a
refused file never reaches.
"""

from __future__ import annotations

from dataclasses import dataclass


def problem_kinds(issues: list) -> list[str]:
    """One line per kind of problem, with how many rows have it
    ("ReviewerEmail is blank (2 rows)"), in the order each kind first
    appears.

    Each blocking issue counts under its ``problem``; a file-level issue
    (no row) has none and stands under its own message, which names no
    row already. A row-level issue a parser left unlabeled falls back to
    its field, so it is still counted rather than lost."""

    rows: dict[str, int] = {}
    for issue in issues:
        if not issue.is_blocking:
            continue
        if issue.problem:
            label = issue.problem
        elif issue.row_number is None:
            label = issue.message
        else:
            label = f"{issue.field or 'A cell'} has a problem"
        rows.setdefault(label, 0)
        if issue.row_number is not None:
            rows[label] += 1
    return [
        f"{label} ({n} row{'' if n == 1 else 's'})" if n else label
        for label, n in rows.items()
    ]


@dataclass(frozen=True)
class UploadProblems:
    """The banner a Setup page's upload card shows for a refused file."""

    message: str
    lines: list[str]


def upload_problems(noun: str, issues: list | None) -> UploadProblems | None:
    """The upload card's banner for a refused file, or ``None`` when the
    file has no blocking problem (a plain render, or the
    replace-confirmation state, which re-renders with a clean file)."""

    lines = problem_kinds(issues or [])
    if not lines:
        return None
    return UploadProblems(
        message=f"Could not import {noun}. The file has these problems:",
        lines=lines,
    )
