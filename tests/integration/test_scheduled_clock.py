"""The in-app clock's pass (segment 14E rung 1): what it picks, what it
fires, and that each crossing is recorded once whichever trigger (clock
or page view) reaches it first."""

from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Instrument, ReviewSession
from app.services import scheduled_events
from app.services import session_lifecycle as lifecycle
from app.services.scheduled_events import _clock

from .test_scheduled_activation import _make_validated_session

NOW = datetime.now(timezone.utc)


def _factory(db: Session):
    """The pass opens database sessions; the test's own stands in."""
    return lambda: nullcontext(db)


def _events(db: Session, rs: ReviewSession, event_type: str) -> list[AuditEvent]:
    return list(
        db.execute(
            select(AuditEvent).where(
                AuditEvent.session_id == rs.id, AuditEvent.event_type == event_type
            ).order_by(AuditEvent.id)
        ).scalars()
    )


def _ready_past_deadline(db: Session, code: str) -> ReviewSession:
    rs = _make_validated_session(db, code)
    rs.scheduled_activate_at = NOW - timedelta(hours=1)
    db.commit()
    scheduled_events.observe_scheduled_events(db, rs, now=NOW - timedelta(minutes=30))
    rs.deadline = NOW - timedelta(minutes=5)
    db.commit()
    assert lifecycle.is_ready(rs)
    return rs


def test_the_pass_picks_only_sessions_with_a_step_due(db: Session) -> None:
    due_start = _make_validated_session(db, "clock-due-start")
    due_start.scheduled_activate_at = NOW - timedelta(minutes=1)
    later = _make_validated_session(db, "clock-later")
    later.scheduled_activate_at = NOW + timedelta(days=1)
    past_end = _ready_past_deadline(db, "clock-past-end")
    released = _make_validated_session(db, "clock-released")
    released.responses_release_at = NOW - timedelta(minutes=1)
    old_release = _make_validated_session(db, "clock-old-release")
    old_release.responses_release_at = NOW - timedelta(days=3)
    archived = _make_validated_session(db, "clock-archived")
    archived.scheduled_activate_at = NOW - timedelta(minutes=1)
    archived.status = lifecycle.SessionStatus.archived.value
    db.commit()

    ids = set(_clock.due_session_ids(db, now=NOW))
    assert {due_start.id, past_end.id, released.id} <= ids
    assert not {later.id, old_release.id, archived.id} & ids


def test_the_pass_activates_a_session_whose_start_has_passed(db: Session) -> None:
    rs = _make_validated_session(db, "clock-activate")
    rs.scheduled_activate_at = NOW - timedelta(minutes=1)
    db.commit()

    assert _clock.run_pass(_factory(db), now=NOW) >= 1

    db.refresh(rs)
    assert lifecycle.is_ready(rs)
    activated = _events(db, rs, "session.activated")
    assert activated[-1].detail["context"]["fired_by"] == "clock"
    assert activated[-1].detail["context"]["trigger"] == "scheduled"


def test_the_deadline_closes_once_with_the_counts_at_that_moment(db: Session) -> None:
    rs = _ready_past_deadline(db, "clock-deadline")

    _clock.run_pass(_factory(db), now=NOW)

    open_left = db.execute(
        select(Instrument).where(
            Instrument.session_id == rs.id, Instrument.accepting_responses.is_(True)
        )
    ).scalars().all()
    assert open_left == []
    reached = _events(db, rs, "session.deadline_reached")
    assert len(reached) == 1
    assert reached[0].detail["context"]["fired_by"] == "clock"
    assert set(reached[0].detail["counts"]) == {"submitted", "assigned"}

    # A later page view, and a second pass, record nothing more.
    lifecycle.observe_deadline(db, rs, now=NOW)
    _clock.run_pass(_factory(db), now=NOW)
    assert len(_events(db, rs, "session.deadline_reached")) == 1


def test_a_page_view_first_records_the_deadline_without_fired_by(db: Session) -> None:
    rs = _ready_past_deadline(db, "clock-page-first")
    lifecycle.observe_deadline(db, rs, now=NOW)
    _clock.run_pass(_factory(db), now=NOW)
    reached = _events(db, rs, "session.deadline_reached")
    assert len(reached) == 1
    assert "fired_by" not in reached[0].detail["context"]


def test_the_release_window_is_stamped_once_per_crossing(db: Session) -> None:
    rs = _make_validated_session(db, "clock-release")
    rs.responses_release_at = NOW - timedelta(hours=2)
    rs.responses_release_until = NOW - timedelta(minutes=5)
    db.commit()

    _clock.run_pass(_factory(db), now=NOW)
    scheduled_events.observe_scheduled_events(db, rs, now=NOW)  # a page view after

    opened = _events(db, rs, "session.release_window_opened")
    ended = _events(db, rs, "session.release_window_ended")
    assert len(opened) == 1 and len(ended) == 1
    assert opened[0].detail["context"]["release_at"] == rs.responses_release_at.replace(
        tzinfo=rs.responses_release_at.tzinfo or timezone.utc
    ).isoformat()
    assert ended[0].detail["context"]["fired_by"] == "clock"

    # A moved end is a new crossing.
    rs.responses_release_until = NOW - timedelta(minutes=1)
    db.commit()
    _clock.run_pass(_factory(db), now=NOW)
    assert len(_events(db, rs, "session.release_window_ended")) == 2


def test_a_crossing_older_than_a_day_is_not_backfilled(db: Session) -> None:
    rs = _make_validated_session(db, "clock-backfill")
    rs.responses_release_at = NOW - timedelta(days=2)
    db.commit()
    scheduled_events.observe_scheduled_events(db, rs, now=NOW)
    assert _events(db, rs, "session.release_window_opened") == []


def test_one_failing_session_does_not_stop_the_pass(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = _make_validated_session(db, "clock-bad")
    bad.scheduled_activate_at = NOW - timedelta(minutes=1)
    good = _make_validated_session(db, "clock-good")
    good.scheduled_activate_at = NOW - timedelta(minutes=1)
    db.commit()
    real = scheduled_events.observe_scheduled_events

    def flaky(db_, session, **kwargs):
        if session.id == bad.id:
            raise RuntimeError("boom")
        return real(db_, session, **kwargs)

    monkeypatch.setattr(scheduled_events, "observe_scheduled_events", flaky)
    _clock.run_pass(_factory(db), now=NOW)
    db.refresh(good)
    assert lifecycle.is_ready(good)


def test_the_clock_sends_nothing(db: Session) -> None:
    """Even with sending on (the suite's setting), the clock passes no
    invite-URL builder, so no scheduled invite goes out."""
    rs = _make_validated_session(db, "clock-no-mail")
    rs.scheduled_activate_at = NOW + timedelta(hours=2)
    rs.invite_offsets = ["-P1D"]
    db.commit()
    _clock.run_pass(_factory(db), now=NOW)
    assert _events(db, rs, "session.scheduled_invites_fired") == []


# --- rung 2: the loop, started by RRW's lifespan ---


def test_a_set_stop_ends_the_pass_before_any_session(db: Session) -> None:
    import threading

    rs = _make_validated_session(db, "clock-stop")
    rs.scheduled_activate_at = NOW - timedelta(minutes=1)
    db.commit()
    stop = threading.Event()
    stop.set()
    assert _clock.run_pass(_factory(db), now=NOW, stop=stop) == 0
    db.refresh(rs)
    assert not lifecycle.is_ready(rs)


def test_the_lifespan_starts_the_loop_and_stops_it(monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    from fastapi.testclient import TestClient

    from app.config import settings
    from app.main import create_app

    calls: list[object] = []

    def fake_pass(factory, *, now=None, stop=None):
        calls.append(stop)
        return 0

    monkeypatch.setattr(settings, "scheduler_interval_seconds", 0.05)
    monkeypatch.setattr(_clock, "run_pass", fake_pass)
    with TestClient(create_app()):
        deadline = time.monotonic() + 5
        while not calls and time.monotonic() < deadline:
            time.sleep(0.02)
    assert calls, "the loop never ran a pass"
    assert calls[0].is_set()  # stopped on shutdown


def test_off_the_lifespan_starts_no_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    from fastapi.testclient import TestClient

    from app.config import settings
    from app.main import create_app

    calls: list[object] = []
    monkeypatch.setattr(settings, "scheduler_interval_seconds", 0)
    monkeypatch.setattr(_clock, "run_pass", lambda *a, **k: calls.append(1))
    with TestClient(create_app()):
        time.sleep(0.1)
    assert calls == []


def test_a_failing_pass_does_not_stop_the_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio
    import threading

    stop = threading.Event()
    calls: list[int] = []

    def flaky(factory, *, now=None, stop=None):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")
        stop.set()
        return 0

    monkeypatch.setattr(_clock, "run_pass", flaky)
    asyncio.run(_clock.run_forever(lambda: None, interval=0.01, stop=stop))
    assert len(calls) == 2
