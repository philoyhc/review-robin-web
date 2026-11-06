"""The in-app clock's pass (segment 14E rung 1): what it picks, what it
fires, and that each crossing is recorded once whichever trigger (clock
or page view) reaches it first."""

from __future__ import annotations

import threading
from collections.abc import Callable
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Instrument, ReviewSession
from app.services import scheduled_events
from app.services import session_lifecycle as lifecycle
from app.services.scheduled_events import _clock

from ._lookups import detail_of
from .test_scheduled_activation import _make_validated_session

NOW = datetime.now(UTC)


def _factory(db: Session) -> Callable[[], nullcontext[Session]]:
    """The pass opens database sessions; the test's own stands in."""
    return lambda: nullcontext(db)


def _events(db: Session, rs: ReviewSession, event_type: str) -> list[AuditEvent]:
    return list(
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.session_id == rs.id, AuditEvent.event_type == event_type)
            .order_by(AuditEvent.id)
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
    released.status = lifecycle.SessionStatus.expired.value
    released.responses_release_at = NOW - timedelta(minutes=1)
    open_release = _make_validated_session(db, "clock-open-release")
    open_release.responses_release_at = NOW - timedelta(minutes=1)
    old_release = _make_validated_session(db, "clock-old-release")
    old_release.responses_release_at = NOW - timedelta(days=3)
    archived = _make_validated_session(db, "clock-archived")
    archived.scheduled_activate_at = NOW - timedelta(minutes=1)
    archived.status = lifecycle.SessionStatus.archived.value
    db.commit()

    ids = set(_clock.due_session_ids(db, now=NOW))
    assert {due_start.id, past_end.id, released.id} <= ids
    assert not {later.id, old_release.id, archived.id, open_release.id} & ids


def test_the_pass_activates_a_session_whose_start_has_passed(db: Session) -> None:
    rs = _make_validated_session(db, "clock-activate")
    rs.scheduled_activate_at = NOW - timedelta(minutes=1)
    db.commit()

    assert _clock.run_pass(_factory(db), now=NOW) >= 1

    db.refresh(rs)
    assert lifecycle.is_ready(rs)
    activated = _events(db, rs, "session.activated")
    assert detail_of(activated[-1])["context"]["fired_by"] == "clock"
    assert detail_of(activated[-1])["context"]["trigger"] == "scheduled"


def test_the_deadline_closes_once_with_the_counts_at_that_moment(db: Session) -> None:
    rs = _ready_past_deadline(db, "clock-deadline")

    _clock.run_pass(_factory(db), now=NOW)

    open_left = (
        db.execute(
            select(Instrument).where(
                Instrument.session_id == rs.id, Instrument.accepting_responses.is_(True)
            )
        )
        .scalars()
        .all()
    )
    assert open_left == []
    reached = _events(db, rs, "session.deadline_reached")
    assert len(reached) == 1
    assert detail_of(reached[0])["context"]["fired_by"] == "clock"
    assert set(detail_of(reached[0])["counts"]) == {"submitted", "assigned"}
    # End closes the session (author, 2026-11-04): ready → expired, no actor.
    db.refresh(rs)
    assert lifecycle.is_expired(rs)
    expired = _events(db, rs, "session.expired")
    assert len(expired) == 1
    assert expired[0].actor_user_id is None
    assert detail_of(expired[0])["reason"] == "deadline"
    assert detail_of(expired[0])["context"]["fired_by"] == "clock"

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
    assert "fired_by" not in detail_of(reached[0])["context"]


def test_the_release_window_is_stamped_once_per_crossing(db: Session) -> None:
    rs = _make_validated_session(db, "clock-release")
    rs.status = lifecycle.SessionStatus.expired.value
    rs.responses_release_at = NOW - timedelta(hours=2)
    rs.responses_release_until = NOW - timedelta(minutes=5)
    db.commit()

    _clock.run_pass(_factory(db), now=NOW)
    scheduled_events.observe_scheduled_events(db, rs, now=NOW)  # a page view after

    opened = _events(db, rs, "session.release_window_opened")
    ended = _events(db, rs, "session.release_window_ended")
    assert len(opened) == 1 and len(ended) == 1
    release_at = rs.responses_release_at
    assert release_at is not None
    assert (
        detail_of(opened[0])["context"]["release_at"]
        == release_at.replace(tzinfo=release_at.tzinfo or UTC).isoformat()
    )
    assert detail_of(ended[0])["context"]["fired_by"] == "clock"

    # A moved end is a new crossing.
    rs.responses_release_until = NOW - timedelta(minutes=1)
    db.commit()
    _clock.run_pass(_factory(db), now=NOW)
    assert len(_events(db, rs, "session.release_window_ended")) == 2


def test_a_crossing_older_than_a_day_is_not_backfilled(db: Session) -> None:
    rs = _make_validated_session(db, "clock-backfill")
    rs.status = lifecycle.SessionStatus.expired.value
    rs.responses_release_at = NOW - timedelta(days=2)
    db.commit()
    scheduled_events.observe_scheduled_events(db, rs, now=NOW)
    assert _events(db, rs, "session.release_window_opened") == []


def test_the_window_is_not_stamped_on_a_session_that_has_not_ended(db: Session) -> None:
    """The window opens only on an expired session: a Release-from that
    passes while it is still open stamps nothing, and is stamped once the
    operator ends it."""
    rs = _make_validated_session(db, "clock-not-ended")
    rs.responses_release_at = NOW - timedelta(minutes=10)
    db.commit()
    _clock.run_pass(_factory(db), now=NOW)
    assert _events(db, rs, "session.release_window_opened") == []
    rs.status = lifecycle.SessionStatus.expired.value
    db.commit()
    _clock.run_pass(_factory(db), now=NOW)
    assert len(_events(db, rs, "session.release_window_opened")) == 1


def test_sending_on_the_clock_holds_activation_for_its_invites(db: Session) -> None:
    """With sending on, the clock has no invite-URL builder, so it leaves
    a session with invite offsets to a page view that can send them,
    rather than activating it and clearing the Start they resolve on."""
    rs = _make_validated_session(db, "clock-hold")
    rs.scheduled_activate_at = NOW - timedelta(minutes=1)
    rs.invite_offsets = ["-P1D"]
    db.commit()
    _clock.run_pass(_factory(db), now=NOW)
    db.refresh(rs)
    assert not lifecycle.is_ready(rs)
    assert rs.scheduled_activate_at is not None


def test_a_recent_activation_retry_waits_for_its_spacing(db: Session) -> None:
    from app.services import audit

    rs = _make_validated_session(db, "clock-retry")
    rs.scheduled_activate_at = NOW - timedelta(minutes=1)
    audit.write_event(
        db,
        event_type="session.scheduled_activation_retry",
        summary="retry",
        session=rs,
        reason="boom",
        context={"attempt": 1},
    )
    db.commit()
    # The retry's row is stamped with the real time, so measure from it.
    now = datetime.now(UTC)
    assert rs.id not in _clock.due_session_ids(db, now=now)
    later = now + _clock.RETRY_SPACING + timedelta(minutes=1)
    assert rs.id in _clock.due_session_ids(db, now=later)


def test_the_retry_spacing_holds_back_only_the_start(db: Session) -> None:
    """A recent activation retry never hides a deadline due on the same
    session (Codex, #3579)."""
    from app.services import audit

    rs = _ready_past_deadline(db, "clock-retry-deadline")
    audit.write_event(
        db,
        event_type="session.scheduled_activation_retry",
        summary="retry",
        session=rs,
        reason="boom",
        context={"attempt": 1},
    )
    db.commit()
    assert rs.id in _clock.due_session_ids(db, now=datetime.now(UTC))


def test_a_pass_another_process_holds_is_skipped(db: Session) -> None:
    """Postgres only: with the advisory lock held elsewhere, the pass
    skips. (SQLite takes no lock.)"""
    from sqlalchemy import text

    engine = db.get_bind().engine
    if engine.dialect.name != "postgresql":
        pytest.skip("the advisory lock needs Postgres (the ci-postgres job)")
    with engine.connect() as holder:
        holder.execute(text("SELECT pg_advisory_lock(:k)"), {"k": _clock.LOCK_KEY})
        try:
            factory = lambda: Session(bind=engine)  # noqa: E731
            before = _clock.clock_status()
            assert _clock.run_pass(factory, now=NOW) == -1
            after = _clock.clock_status()
            # Counted as held elsewhere, and not as a pass (22G Item 1).
            assert after.held_elsewhere == before.held_elsewhere + 1
            assert after.passes == before.passes
        finally:
            holder.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _clock.LOCK_KEY})


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

    calls: list[threading.Event | None] = []

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
    assert calls[0] is not None
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


def _no_factory() -> Session:
    """For a stubbed pass, which opens no database session."""
    raise AssertionError("the stubbed pass opened a session")


def test_a_failing_pass_does_not_stop_the_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio
    import threading

    stop = threading.Event()
    calls: list[int] = []

    def flaky(factory, *, now=None, stop=None):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")
        assert stop is not None
        stop.set()
        return 0

    monkeypatch.setattr(_clock, "run_pass", flaky)
    asyncio.run(_clock.run_forever(_no_factory, interval=0.01, stop=stop))
    assert len(calls) == 2


def test_the_ongoing_window_ends_at_end_itself(db: Session) -> None:
    """Visibility exists only while ongoing and in the release window: a
    session still ``ready`` past End (the clock has not run yet, or End
    passed before End closed sessions) is not ongoing."""
    rs = _make_validated_session(db, "clock-ongoing")
    rs.status = lifecycle.SessionStatus.ready.value
    rs.deadline = NOW + timedelta(minutes=5)
    db.commit()
    assert lifecycle.is_ongoing(rs, now=NOW)
    assert not lifecycle.is_ongoing(rs, now=NOW + timedelta(minutes=6))
    rs.deadline = None
    assert lifecycle.is_ongoing(rs, now=NOW + timedelta(days=30))


def test_with_no_end_release_from_closes_the_session_and_opens_the_window(
    db: Session,
) -> None:
    """With no End set, Release responses from ends the review (author,
    2026-11-04): the session closes and the window opens in one pass."""
    rs = _make_validated_session(db, "clock-release-close")
    rs.status = lifecycle.SessionStatus.ready.value
    rs.deadline = None
    rs.responses_release_at = NOW - timedelta(minutes=1)
    db.commit()
    assert not lifecycle.is_ongoing(rs, now=NOW)
    assert lifecycle.review_end(rs) is not None

    _clock.run_pass(_factory(db), now=NOW)

    db.refresh(rs)
    assert lifecycle.is_expired(rs)
    expired = _events(db, rs, "session.expired")
    assert len(expired) == 1
    assert detail_of(expired[0])["reason"] == "release"
    assert detail_of(expired[0])["context"]["fired_by"] == "clock"
    assert "release_at" in detail_of(expired[0])["context"]
    assert _events(db, rs, "session.deadline_reached") == []
    assert len(_events(db, rs, "session.release_window_opened")) == 1
    _clock.run_pass(_factory(db), now=NOW)
    assert len(_events(db, rs, "session.expired")) == 1


def test_with_an_end_release_from_does_not_close_the_session(db: Session) -> None:
    rs = _make_validated_session(db, "clock-release-end")
    rs.status = lifecycle.SessionStatus.ready.value
    rs.deadline = NOW + timedelta(hours=1)
    rs.responses_release_at = NOW - timedelta(minutes=1)
    db.commit()
    assert lifecycle.observe_deadline(db, rs, now=NOW) == 0
    db.refresh(rs)
    assert lifecycle.is_ready(rs)


def test_an_old_release_from_with_no_end_closes_too(db: Session) -> None:
    """No age limit, as for End: a session whose Release from passed long
    ago, with no End, closes rather than staying open with its visibility
    shut (round-2 cold read, #3582)."""
    rs = _make_validated_session(db, "clock-release-old")
    rs.status = lifecycle.SessionStatus.ready.value
    rs.deadline = None
    rs.responses_release_at = NOW - timedelta(days=3)
    db.commit()
    assert rs.id in _clock.due_session_ids(db, now=NOW)
    _clock.run_pass(_factory(db), now=NOW)
    db.refresh(rs)
    assert lifecycle.is_expired(rs)


def test_with_no_end_release_from_stops_saves_at_once(db: Session) -> None:
    """The accept gate follows the review's end: past Release from, with
    no End, nothing is accepted even before any close has run."""
    rs = _make_validated_session(db, "clock-release-gate")
    rs.status = lifecycle.SessionStatus.ready.value
    rs.deadline = None
    rs.responses_release_at = NOW - timedelta(minutes=1)
    db.commit()
    assert lifecycle.deadline_has_passed(rs, now=NOW)
    assert not lifecycle.recall_allowed(rs, now=NOW)


def test_validate_refuses_a_session_whose_end_has_passed(db: Session) -> None:
    """Activating would close it at once, so Validate stops it (an End,
    or with no End a Release from, already passed)."""
    from app.services.validation import validate_session_setup

    rs = _make_validated_session(db, "clock-end-passed")
    rs.status = "draft"
    rs.deadline = None
    rs.responses_release_at = NOW - timedelta(hours=2)
    db.commit()
    issues = validate_session_setup(db, rs)
    assert any("Release responses from has passed" in i.message for i in issues)


def test_a_session_whose_end_passed_earlier_still_closes(db: Session) -> None:
    """End closes the session even when its instruments were shut before
    End closed sessions (a reviewer's request past End, before 14E)."""
    rs = _ready_past_deadline(db, "clock-legacy-end")
    for instrument in db.execute(
        select(Instrument).where(Instrument.session_id == rs.id)
    ).scalars():
        instrument.accepting_responses = False
        instrument.deadline_closed_at = NOW - timedelta(minutes=4)
    db.commit()

    assert rs.id in _clock.due_session_ids(db, now=NOW)
    _clock.run_pass(_factory(db), now=NOW)
    db.refresh(rs)
    assert lifecycle.is_expired(rs)
    assert len(_events(db, rs, "session.expired")) == 1
    # And it records the crossing, from the clock (findings L4).
    [reached] = _events(db, rs, "session.deadline_reached")
    assert detail_of(reached)["context"]["fired_by"] == "clock"


def test_an_operator_page_view_past_end_closes_the_session(db: Session) -> None:
    """With the clock off, the scheduled pass an operator page runs closes
    a session past End too, not only a reviewer's request."""
    rs = _ready_past_deadline(db, "clock-op-view")
    scheduled_events.observe_scheduled_events(db, rs, now=NOW)
    db.refresh(rs)
    assert lifecycle.is_expired(rs)
    expired = _events(db, rs, "session.expired")
    assert len(expired) == 1 and "fired_by" not in detail_of(expired[0])["context"]


def test_no_end_release_before_start_is_refused_at_save() -> None:
    """With no End the release ends the review, so it cannot come before
    Start (round-3 read, #3582)."""
    from app.services.scheduled_events import ScheduledActivateError, validate_schedule_ordering

    with pytest.raises(ScheduledActivateError):
        validate_schedule_ordering(
            scheduled_activate_at=NOW + timedelta(days=2),
            deadline=None,
            responses_release_at=NOW + timedelta(days=1),
        )
    validate_schedule_ordering(
        scheduled_activate_at=NOW + timedelta(days=1),
        deadline=None,
        responses_release_at=NOW + timedelta(days=2),
    )


def test_validate_refuses_a_validated_session_whose_end_has_passed(db: Session) -> None:
    from app.services.validation import validate_session_setup

    rs = _make_validated_session(db, "clock-end-passed-v")
    rs.deadline = NOW - timedelta(minutes=5)
    db.commit()
    keys = [i.message for i in validate_session_setup(db, rs)]
    assert any("End has passed" in m for m in keys)


def test_a_release_close_names_the_instruments_release(db: Session) -> None:
    rs = _make_validated_session(db, "clock-release-instr")
    rs.status = lifecycle.SessionStatus.ready.value
    rs.deadline = None
    rs.responses_release_at = NOW - timedelta(minutes=1)
    for instrument in db.execute(
        select(Instrument).where(Instrument.session_id == rs.id)
    ).scalars():
        instrument.accepting_responses = True
    db.commit()
    lifecycle.observe_deadline(db, rs, now=NOW)
    closed = _events(db, rs, "instrument.closed")
    assert closed and all(detail_of(e)["reason"] == "release" for e in closed)


# --- segment 22G Item 1: what the clock last did ---


def test_a_pass_records_itself_in_the_clock_status(db: Session) -> None:
    rs = _make_validated_session(db, "clock-status-pass")
    rs.scheduled_activate_at = NOW - timedelta(minutes=1)
    db.commit()
    before = _clock.clock_status()
    visited = _clock.run_pass(_factory(db), now=NOW)
    after = _clock.clock_status()
    assert after.passes == before.passes + 1
    assert after.last_pass_visited == visited >= 1
    assert after.last_pass_started is not None and after.last_pass_finished is not None
    assert after.last_pass_started <= after.last_pass_finished


def test_a_failing_session_and_a_busy_one_are_counted(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.session_guard import SessionBusy

    bad = _make_validated_session(db, "clock-status-bad")
    bad.scheduled_activate_at = NOW - timedelta(minutes=1)
    busy = _make_validated_session(db, "clock-status-busy")
    busy.scheduled_activate_at = NOW - timedelta(minutes=1)
    db.commit()

    def refuse(db_, session, **kwargs):
        if session.id == bad.id:
            raise RuntimeError("boom")
        if session.id == busy.id:
            raise SessionBusy()
        return True

    monkeypatch.setattr(scheduled_events, "observe_scheduled_events", refuse)
    before = _clock.clock_status()
    _clock.run_pass(_factory(db), now=NOW)
    after = _clock.clock_status()
    assert after.failures == before.failures + 1
    assert after.last_failure_type == "RuntimeError"
    assert after.last_failure_at is not None
    assert after.busy_sessions == before.busy_sessions + 1


def test_a_trigger_meeting_a_busy_session_counts_as_busy_not_visited(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real path (Codex, cordware #180): a trigger's ``SessionBusy``
    is caught inside the observer, which reports the pass cut short, so
    the clock counts the session busy rather than visited."""
    from app.services.session_guard import SessionBusy

    rs = _make_validated_session(db, "clock-status-busy-trigger")
    rs.scheduled_activate_at = NOW - timedelta(minutes=1)
    db.commit()

    def busy(*args, **kwargs):
        raise SessionBusy()

    monkeypatch.setattr(scheduled_events, "_observe_scheduled_activation", busy)
    before = _clock.clock_status()
    visited = _clock.run_pass(_factory(db), now=NOW)
    after = _clock.clock_status()
    assert visited == 0
    assert after.busy_sessions == before.busy_sessions + 1
    assert after.last_pass_visited == 0
    db.refresh(rs)
    assert not lifecycle.is_ready(rs)


def test_the_observer_reports_a_full_pass(db: Session) -> None:
    rs = _make_validated_session(db, "clock-observer-true")
    assert scheduled_events.observe_scheduled_events(db, rs, now=NOW) is True


def test_the_status_is_a_copy(db: Session) -> None:
    snapshot = _clock.clock_status()
    snapshot.passes += 100
    assert _clock.clock_status().passes != snapshot.passes


def test_the_loop_marks_itself_running_while_it_runs(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    import asyncio

    seen: list[bool] = []

    def fake_pass(factory, *, now=None, stop=None):
        seen.append(_clock.clock_status().running)
        assert stop is not None
        stop.set()
        return 0

    monkeypatch.setattr(_clock, "run_pass", fake_pass)
    stop = threading.Event()
    asyncio.run(_clock.run_forever(_factory(db), interval=0.01, stop=stop))
    assert seen == [True]
    after = _clock.clock_status()
    assert after.running is False
    assert after.interval_seconds == 0.01


def test_a_pass_that_raises_outright_is_a_failure(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    import asyncio

    stop = threading.Event()

    def broken_pass(factory, *, now=None, stop=stop):
        stop.set()
        raise LookupError("no database")

    monkeypatch.setattr(_clock, "run_pass", broken_pass)
    before = _clock.clock_status()
    asyncio.run(_clock.run_forever(_factory(db), interval=0.01, stop=stop))
    after = _clock.clock_status()
    assert after.failures == before.failures + 1
    assert after.last_failure_type == "LookupError"


def test_an_end_over_already_shut_instruments_still_records_the_deadline(db: Session) -> None:
    """Findings L4 (author, 2026-11-06): a legacy session whose
    instruments were already shut (the retired per-instrument Close, or
    an End that passed before End closed sessions) still writes its one
    `session.deadline_reached` when End closes it, so every crossing
    leaves the same record."""
    rs = _ready_past_deadline(db, "clock-already-shut")
    for instrument in db.execute(
        select(Instrument).where(Instrument.session_id == rs.id)
    ).scalars():
        instrument.accepting_responses = False
    db.commit()

    lifecycle.observe_deadline(db, rs, now=NOW)

    reached = _events(db, rs, "session.deadline_reached")
    assert len(reached) == 1
    assert set(detail_of(reached[0])["counts"]) == {"submitted", "assigned"}
    assert "fired_by" not in detail_of(reached[0])["context"]  # a page view
    db.refresh(rs)
    assert lifecycle.is_expired(rs)
    [expired] = _events(db, rs, "session.expired")
    assert detail_of(expired)["counts"]["closed_instruments"] == 0
    lifecycle.observe_deadline(db, rs, now=NOW)
    assert len(_events(db, rs, "session.deadline_reached")) == 1
