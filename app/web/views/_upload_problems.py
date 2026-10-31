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


def problems_sentence(noun: str) -> str:
    """The sentence over the lines, on both surfaces."""

    return f"Could not import {noun}. The file has these problems:"


@dataclass(frozen=True)
class UploadProblems:
    """The banner a Setup page's upload card shows for an upload that
    did not happen: a refused file's kinds of problem, or one sentence
    with no lines (the missing replace tick, or the missing response-loss
    acknowledgment)."""

    message: str
    lines: list[str]


#: The sentence when a clean file would go onto a populated roster but
#: none of the replace, append or merge ticks was ticked (segment 19Z):
#: any one answers it. Quick Setup's twin names its Submit.
NEEDS_CONFIRM_SENTENCE = (
    "Tick replace, append or merge just above Upload, then upload again."
)


#: The sentence when more than one of the replace, append and merge
#: ticks arrives (no script on the page to untick the others, or a
#: direct POST): they ask for different things, so none is guessed
#: (segment 19Z).
BOTH_TICKS_SENTENCE = (
    "Tick only one of replace, append or merge, then upload again."
)


#: The sentence when a Reviewers or Reviewees replace would discard
#: saved responses but the request did not acknowledge it. The card
#: sends the acknowledgment beside the tick whenever it names
#: responses, so this is a tab loaded before the session had any (or a
#: direct POST). The re-rendered card names them; a second tick sends it.
NEEDS_RESPONSE_ACK_SENTENCE = (
    "This session now holds reviewer responses, which replacing this "
    "roster would discard. The replacement-confirmation box now names "
    "them: tick it, then upload again."
)


def upload_problems(
    noun: str,
    issues: list | None,
    *,
    missing_confirm: bool = False,
    missing_response_ack: bool = False,
    both_ticks: bool = False,
) -> UploadProblems | None:
    """The upload card's banner, or ``None`` on a plain render.

    A refused file lists its kinds of problem. A clean file onto a
    populated roster without the replace tick says so in one sentence:
    before this, that 400 re-rendered the page with nothing on it
    (``missing_confirm`` was passed and no template read it). A replace
    that would discard responses without the acknowledgment says so in
    one sentence too: before this, it was a full error page asking for an
    "acknowledge response loss" tick no page offers."""

    lines = problem_kinds(issues or [])
    if lines:
        return UploadProblems(message=problems_sentence(noun), lines=lines)
    if both_ticks:
        return UploadProblems(message=BOTH_TICKS_SENTENCE, lines=[])
    if missing_confirm:
        return UploadProblems(message=NEEDS_CONFIRM_SENTENCE, lines=[])
    if missing_response_ack:
        return UploadProblems(message=NEEDS_RESPONSE_ACK_SENTENCE, lines=[])
    return None
