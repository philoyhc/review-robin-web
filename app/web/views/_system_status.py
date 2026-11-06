"""System Status tab view shapes (segment 22G Item 1): the Admin page's
read-only report of what the host does in the background. Each card's
values arrive as display strings, plus the instants the template formats
in the viewer's zone."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

from app.services.scheduled_events import ClockStatus
from app.services.system_status import Instance


@dataclasses.dataclass(frozen=True)
class ClockCard:
    """The Clock card. ``state`` is ``on`` / ``off`` / ``stopped``:
    off is the setting (``SCHEDULER_INTERVAL_SECONDS`` 0), stopped is a
    loop that should run and is not."""

    state: str
    state_label: str
    interval_label: str
    since: datetime
    uptime_label: str
    last_pass_at: datetime | None
    last_pass_label: str
    last_failure_at: datetime | None
    last_failure_label: str
    failures: int
    skips_label: str


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def duration_label(span: timedelta) -> str:
    """A short span for a person: ``0.4 s``, ``12 s``, ``3 min``,
    ``2 h 5 min``, ``4 d 3 h``."""
    seconds = max(span.total_seconds(), 0.0)
    if seconds < 10:
        return f"{seconds:.1f} s"
    if seconds < 60:
        return f"{int(seconds)} s"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes} min"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours} h {minutes} min" if minutes else f"{hours} h"
    days, hours = divmod(hours, 24)
    return f"{days} d {hours} h" if hours else f"{days} d"


def clock_card(
    status: ClockStatus, *, interval_setting: float, now: datetime | None = None
) -> ClockCard:
    """``now`` dates the uptime: the time since ``status.since``, when
    this process loaded the clock, which is this instance's start."""
    if interval_setting <= 0:
        state, state_label = "off", "Off (SCHEDULER_INTERVAL_SECONDS is 0)"
    elif status.running:
        state, state_label = "on", "On"
    else:
        state, state_label = "stopped", "Not running, though the setting turns it on"
    interval = status.interval_seconds if status.running else interval_setting
    interval_label = (
        f"Every {duration_label(timedelta(seconds=interval))}" if interval and interval > 0 else "—"
    )
    if status.last_pass_started is None or status.last_pass_finished is None:
        last_pass_label = "None yet"
    else:
        took = duration_label(status.last_pass_finished - status.last_pass_started)
        visited = _plural(status.last_pass_visited or 0, "session")
        last_pass_label = f"Took {took}, visited {visited}"
    return ClockCard(
        state=state,
        state_label=state_label,
        interval_label=interval_label,
        since=status.since,
        uptime_label=duration_label((now or datetime.now(UTC)) - status.since),
        last_pass_at=status.last_pass_started,
        last_pass_label=last_pass_label,
        last_failure_at=status.last_failure_at,
        last_failure_label=status.last_failure_type or "None",
        failures=status.failures,
        skips_label=(
            f"{_plural(status.busy_sessions, 'session')} busy, "
            f"{_plural(status.held_elsewhere, 'pass')} held by another process"
        ),
    )


@dataclasses.dataclass(frozen=True)
class InstanceCard:
    """The Sending and This instance cards. ``schema_state`` is
    ``current`` / ``differs`` / ``unrecorded``: a database at another
    revision may be behind this code or ahead of it, and the app cannot
    tell which: the running app has no migration scripts to read
    (findings N6)."""

    scheduled_send_label: str
    version: str
    dialect: str
    schema_state: str
    schema_label: str


def instance_card(instance: Instance, *, scheduled_send: bool) -> InstanceCard:
    if instance.schema_current:
        state, label = "current", f"Current ({instance.schema_head})"
    elif instance.schema_revision:
        state = "differs"
        label = f"At {instance.schema_revision}; this code expects {instance.schema_head}"
    else:
        state = "unrecorded"
        label = f"No revision recorded; this code expects {instance.schema_head}"
    return InstanceCard(
        scheduled_send_label=(
            "On: scheduled invites and reminders fire on time"
            if scheduled_send
            else "Off (RRW_SCHEDULED_SEND): scheduled invites and reminders do not fire"
        ),
        version=instance.version,
        dialect=instance.dialect,
        schema_state=state,
        schema_label=label,
    )
