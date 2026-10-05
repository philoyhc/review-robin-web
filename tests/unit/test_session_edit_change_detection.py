"""``sessions.payload_changes_session`` / ``keep_stored_if_same_minute``
(findings B2, 2026-10-05).

The lobby expander saves tags and, on an editable session, Name / Code /
Deadline. ``update_session`` demotes a ``validated`` session, so the
route calls it only when something changed — which has to survive a
naive-vs-aware deadline (a parsed form value against Postgres's
``timestamptz``) and a minute-precision box re-submitting a stored
deadline that has seconds.
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


def test_the_same_minute_keeps_the_stored_value() -> None:
    submitted = datetime(2031, 3, 4, 23, 59)
    assert sessions.keep_stored_if_same_minute(AWARE, submitted) is AWARE


def test_another_minute_is_an_edit() -> None:
    submitted = datetime(2031, 3, 4, 23, 58)
    assert sessions.keep_stored_if_same_minute(AWARE, submitted) is submitted


def test_clearing_or_setting_a_deadline_is_passed_through() -> None:
    assert sessions.keep_stored_if_same_minute(AWARE, None) is None
    assert sessions.keep_stored_if_same_minute(None, NAIVE_SAME) is NAIVE_SAME
