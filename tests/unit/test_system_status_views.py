"""System Status's Clock card (segment 22G Item 1): the labels a
ClockStatus becomes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.services.scheduled_events import ClockStatus
from app.web.views import clock_card, duration_label

SINCE = datetime(2026, 11, 5, 1, 0, tzinfo=UTC)


def test_off_by_the_setting() -> None:
    card = clock_card(ClockStatus(since=SINCE), interval_setting=0)
    assert card.state == "off"
    assert "SCHEDULER_INTERVAL_SECONDS is 0" in card.state_label
    assert card.interval_label == "—"


def test_on_and_never_passed() -> None:
    status = ClockStatus(since=SINCE, running=True, interval_seconds=120)
    card = clock_card(status, interval_setting=120)
    assert (card.state, card.state_label) == ("on", "On")
    assert card.interval_label == "Every 2 min"
    assert card.last_pass_at is None
    assert card.last_pass_label == "None yet"
    assert card.last_failure_label == "None"


def test_set_on_but_not_running_is_stopped() -> None:
    card = clock_card(ClockStatus(since=SINCE), interval_setting=120)
    assert card.state == "stopped"
    assert card.interval_label == "Every 2 min"


def test_a_pass_and_a_failure() -> None:
    started = SINCE + timedelta(minutes=2)
    status = ClockStatus(
        since=SINCE,
        running=True,
        interval_seconds=120,
        passes=3,
        last_pass_started=started,
        last_pass_finished=started + timedelta(milliseconds=400),
        last_pass_visited=1,
        busy_sessions=2,
        held_elsewhere=1,
        failures=1,
        last_failure_at=started,
        last_failure_type="RuntimeError",
    )
    card = clock_card(status, interval_setting=120, now=SINCE + timedelta(hours=3))
    assert card.uptime_label == "3 h"
    assert card.last_pass_at == started
    assert card.last_pass_label == "Took 0.4 s, visited 1 session"
    assert card.last_failure_label == "RuntimeError"
    assert card.skips_label == "2 sessions busy, 1 pass held by another process"


def test_duration_label() -> None:
    assert duration_label(timedelta(seconds=0.42)) == "0.4 s"
    assert duration_label(timedelta(seconds=42)) == "42 s"
    assert duration_label(timedelta(minutes=3, seconds=5)) == "3 min"
    assert duration_label(timedelta(hours=2)) == "2 h"
    assert duration_label(timedelta(hours=2, minutes=5)) == "2 h 5 min"
    assert duration_label(timedelta(days=4, hours=3)) == "4 d 3 h"
    assert duration_label(timedelta(seconds=-1)) == "0.0 s"
