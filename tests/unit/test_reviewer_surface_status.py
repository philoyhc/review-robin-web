"""Findings R7 (author's ruling 2026-10-17): the reviewer surface's
per-page and session pills follow the dashboard's answers-based rule.

A row with no answer is not started even when nothing is required;
``complete`` needs an answer and every required field filled;
``submitted`` needs every saved answer stamped, so an unsubmitted change
after Submit holds it off, and a blank all-optional row does not.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.web.routes_reviewer._surface._status import (
    PageStatus,
    _page_status_for_group,
    _session_status,
)

_AT = datetime(2026, 10, 17, tzinfo=timezone.utc)


def _row(
    *,
    answers: int = 0,
    unsubmitted: int = 0,
    complete: bool = True,
    shown: bool = True,
) -> dict:
    """A built surface row: ``answers`` saved, ``unsubmitted`` of them
    without a stamp, required fields ``complete`` or not."""
    stamped = answers - unsubmitted
    return {
        "answer_count": answers,
        "unsubmitted_count": unsubmitted,
        "is_complete": complete,
        "submitted_at": _AT if stamped else None,
        "cells": [{"value": "x" if shown else ""} for _ in range(answers)],
    }


def test_blank_all_optional_rows_are_not_started() -> None:
    # Nothing required, so every row is "complete" by its required
    # fields; with no answer the page is still not started.
    assert _page_status_for_group([_row(), _row()]) == "not_started"


def test_complete_needs_an_answer_and_every_required_field() -> None:
    assert _page_status_for_group([_row(answers=1, unsubmitted=1)]) == "complete"
    assert (
        _page_status_for_group([_row(answers=1, unsubmitted=1, complete=False)])
        == "in_progress"
    )
    # One answered row and one blank all-optional row is complete.
    assert (
        _page_status_for_group([_row(answers=1, unsubmitted=1), _row()])
        == "complete"
    )


def test_submitted_ignores_a_blank_all_optional_row() -> None:
    assert _page_status_for_group([_row(answers=2), _row()]) == "submitted"


def test_unsubmitted_answer_after_submit_is_not_submitted() -> None:
    # A new or changed answer (findings R1) beside stamped ones: complete
    # while every required field is filled, in progress once one isn't.
    assert _page_status_for_group([_row(answers=2, unsubmitted=1)]) == "complete"
    assert (
        _page_status_for_group([_row(answers=2, unsubmitted=1, complete=False)])
        == "in_progress"
    )


def test_hidden_values_read_saved_rows_for_submitted() -> None:
    # A value the reviewer may not read back is not shown, but a
    # submitted page still reads submitted; one short of it reads as not
    # started, as the spec has it.
    assert _page_status_for_group([_row(answers=1, shown=False)]) == "submitted"
    assert (
        _page_status_for_group(
            [_row(answers=1, complete=False, shown=False)]
        )
        == "not_started"
    )


def _pages(*states: str) -> list[PageStatus]:
    return [PageStatus(position=i, label=f"#{i}", state=s) for i, s in enumerate(states, 1)]


def test_session_submitted_beside_a_blank_optional_page() -> None:
    rows = [_row(answers=1), _row()]
    assert _session_status(_pages("submitted", "not_started"), rows) == "submitted"


def test_session_saved_when_anything_is_unsubmitted() -> None:
    rows = [_row(answers=1), _row(answers=1, unsubmitted=1)]
    assert _session_status(_pages("submitted", "in_progress"), rows) == "saved"


def test_session_saved_when_a_required_field_is_missing() -> None:
    rows = [_row(answers=1), _row(complete=False)]
    assert _session_status(_pages("submitted", "not_started"), rows) == "saved"


def test_session_draft_and_none() -> None:
    assert _session_status(_pages("not_started"), [_row()]) == "draft"
    assert _session_status([], []) is None
