"""``sessions.payload_changes_session`` / ``deadline_box_unedited``
(findings B2, 2026-10-05).

The lobby expander saves tags and, on an editable session, Name / Code /
Deadline. ``update_session`` demotes a ``validated`` session, so the
route calls it only when something changed — which has to survive a
naive-vs-aware deadline (a parsed form value against Postgres's
``timestamptz``), a minute-precision box re-submitting a stored
deadline that has seconds, and a deadline in the repeated hour after a
DST fall-back, whose wall-clock text parses to the hour's first instant.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.db.models import ReviewSession
from app.services import sessions

AWARE = datetime(2031, 3, 4, 23, 59, 59, tzinfo=timezone.utc)
NAIVE_SAME = datetime(2031, 3, 4, 23, 59, 59)


def _session() -> ReviewSession:
    return ReviewSession(
        name="N",
        code="c",
        deadline=AWARE,
        relationships_enabled=False,
        observers_enabled=False,
    )


def test_a_naive_and_an_aware_deadline_for_the_same_instant_are_unchanged() -> None:
    payload = sessions.edit_payload(_session(), deadline=NAIVE_SAME)
    assert sessions.payload_changes_session(_session(), payload) is False


def test_a_renamed_session_is_changed() -> None:
    payload = sessions.edit_payload(_session(), name="Other")
    assert sessions.payload_changes_session(_session(), payload) is True


def test_the_seeded_box_with_seconds_stored_is_unedited() -> None:
    assert sessions.deadline_box_unedited(AWARE, "2031-03-04T23:59", "UTC")


def test_another_minute_is_an_edit() -> None:
    assert not sessions.deadline_box_unedited(AWARE, "2031-03-04T23:58", "UTC")


def test_clearing_or_setting_a_deadline_is_an_edit() -> None:
    assert not sessions.deadline_box_unedited(AWARE, "", "UTC")
    assert not sessions.deadline_box_unedited(None, "2031-03-04T23:59", "UTC")
    assert sessions.deadline_box_unedited(None, "", "UTC")


def test_the_second_pass_of_a_repeated_dst_hour_is_unedited() -> None:
    # 06:30 UTC on 2026-11-01 is 01:30 EST, the second 01:30 in New York;
    # parsing "01:30" back would land on 05:30 UTC, the first (Codex, #2832).
    stored = datetime(2026, 11, 1, 6, 30, tzinfo=timezone.utc)
    assert sessions.deadline_box_unedited(
        stored, "2026-11-01T01:30", "America/New_York"
    )
