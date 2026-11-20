"""Every signal derived from a locked thing honours the lock.

A linked application's lock (`app/services/linked_apps.py` ``Lock``) is
enforced where it was written: the routes refuse, and the page that serves
them says so (`tests/integration/test_linked_sessions.py`). What those
tests did not reach is a signal *computed from* the locked thing somewhere
else. The 2026-11-20 assessment found the lobby's Due pill lit on a session
whose application takes the email lock while the Workflow card, which read
the lock, showed nothing (`guide/findings_2026-11-20_assessment.md` D1), and
the corpus sweep found the auto-send captions promising sends the trigger
skips (`guide/findings_2026-11-20_corpus.md` B3). The two were one miss.

So this walks a table, keyed by the ``Lock`` enum: for each lock, every
derived signal, a setup that makes it fire on a native session, and the
reading. Each signal must fire natively, fall silent under a profile that
takes that lock alone, and still fire under a profile that takes every lock
but that one, so the silence is the lock's and no other's. A lock with no
derived signal says why, and a lock added to the enum without an entry fails
here, which is when its signals are easiest to name.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import ReviewSession
from app.services import due_actions, linked_apps
from app.services import session_lifecycle as lifecycle
from app.services.linked_apps import LinkedProfile, Lock
from app.web import views
from app.web.views import _workflow_card

from .test_invitations import _ready_session


@dataclass(frozen=True)
class Signal:
    """One derived signal: how to make it fire on a native session, and
    whether it fires."""

    name: str
    arrange: Callable[[TestClient, Session, pytest.MonkeyPatch], ReviewSession]
    fires: Callable[[Session, ReviewSession], bool]


def _due_invites(client: TestClient, db: Session, mp: pytest.MonkeyPatch) -> ReviewSession:
    """A ready session with an invite offset passed, scheduled email off:
    a prompt is due by hand (14F rung 5b)."""
    mp.setattr(settings, "scheduled_send", False)
    rs = _ready_session(client, db, code="lock-due")
    rs.scheduled_activate_at = datetime.now(UTC) + timedelta(hours=1)
    rs.invite_offsets = ["-P1D"]
    db.commit()
    return rs


def _auto_send(client: TestClient, db: Session, mp: pytest.MonkeyPatch) -> ReviewSession:
    """A ready session with invite and reminder offsets still to fire,
    scheduled email on: the captions promise a send."""
    mp.setattr(settings, "scheduled_send", True)
    rs = _ready_session(client, db, code="lock-auto")
    now = datetime.now(UTC)
    rs.scheduled_activate_at = now + timedelta(days=2)
    rs.invite_offsets = ["-P1D"]
    rs.deadline = now + timedelta(days=5)
    rs.reminder_offsets = ["-P1D"]
    db.commit()
    return rs


def _activate_pending(client: TestClient, db: Session, mp: pytest.MonkeyPatch) -> ReviewSession:
    """A prepared session whose Start would fire invite offsets: activating
    by hand would cancel them, so Activate asks first."""
    rs = _auto_send(client, db, mp)
    rs.status = lifecycle.SessionStatus.validated.value
    db.commit()
    return rs


def _release_reached(client: TestClient, db: Session, mp: pytest.MonkeyPatch) -> ReviewSession:
    """An expired session past its release anchor: the window is open."""
    rs = _ready_session(client, db, code="lock-release")
    rs.status = lifecycle.SessionStatus.expired.value
    rs.responses_release_at = datetime.now(UTC) - timedelta(hours=1)
    db.commit()
    return rs


def _draft(client: TestClient, db: Session, mp: pytest.MonkeyPatch) -> ReviewSession:
    response = client.post("/operator/sessions", data={"name": "Lock draft", "code": "lock-draft"})
    assert response.status_code in (200, 303), response.text
    return db.execute(select(ReviewSession).where(ReviewSession.code == "lock-draft")).scalar_one()


#: Every lock's derived signals. The routes and the page each lock gates
#: are tested in `tests/integration/test_linked_sessions.py`; these are the
#: signals read from the same thing elsewhere.
SIGNALS: dict[Lock, tuple[Signal, ...]] = {
    Lock.EMAIL: (
        Signal(
            "the due prompts",
            _due_invites,
            lambda db, rs: bool(due_actions.due_actions(db, rs)),
        ),
        Signal(
            "the Workflow card's due lines",
            _due_invites,
            lambda db, rs: bool(_workflow_card.build_due_lines(db, rs)),
        ),
        Signal(
            "the lobby's Due pill",
            _due_invites,
            lambda db, rs: rs.public_id in views.lobby_due_session_ids(db, [rs]),
        ),
        Signal(
            "the auto-send invites caption",
            _auto_send,
            lambda db, rs: _workflow_card.build_auto_send_invites_caption(db, rs) is not None,
        ),
        Signal(
            "the auto-send reminders caption",
            _auto_send,
            lambda db, rs: _workflow_card.build_auto_send_reminders_caption(db, rs) is not None,
        ),
        Signal(
            "Activate's warning that it cancels auto-sends",
            _activate_pending,
            lambda db, rs: _workflow_card.build_manual_activate_cancellation(rs) is not None,
        ),
    ),
    Lock.RELEASE: (
        Signal(
            "the response release window",
            _release_reached,
            lambda db, rs: lifecycle.is_response_release_window_open(rs),
        ),
    ),
    Lock.ROSTERS: (
        Signal(
            "the roster pages' editability",
            _draft,
            lambda db, rs: views.rosters_editable(rs),
        ),
    ),
}

#: Locks with no derived signal: what each gates is a route and the page it
#: serves, and nothing elsewhere computes from it.
ROUTE_ONLY: dict[Lock, str] = {
    Lock.OBSERVERS: "the Observers routes, Quick Setup's observer fields and the details card",
    Lock.SESSION_DETAILS: "the details card and the lobby's edit",
    Lock.QUICK_SETUP: "Quick Setup's routes",
    Lock.SETTINGS_IMPORT: "the Settings import route",
    Lock.INVITATION_SEND: "the per-row Send routes and the Invitations page's note",
    Lock.INSTRUMENT_STRUCTURE: "the instrument structure routes and services",
}

CASES = [(lock, signal) for lock, signals in SIGNALS.items() for signal in signals]


def _link(monkeypatch: pytest.MonkeyPatch, rs: ReviewSession, locks: frozenset[Lock]) -> None:
    """Link ``rs`` to a profile taking exactly ``locks``."""
    profile = LinkedProfile("probe", "Probe", "Probe", locks=locks)
    monkeypatch.setitem(linked_apps.LINKED_APPS, "probe", profile)
    rs.linked_app = "probe"


@pytest.mark.parametrize(
    ("lock", "signal"), CASES, ids=[f"{lock.value}: {signal.name}" for lock, signal in CASES]
)
def test_a_derived_signal_honours_its_lock_and_only_its_lock(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    lock: Lock,
    signal: Signal,
) -> None:
    rs = signal.arrange(client, db, monkeypatch)
    assert signal.fires(db, rs), f"{signal.name} should fire on a native session"
    _link(monkeypatch, rs, frozenset({lock}))
    assert not signal.fires(db, rs), f"{signal.name} ignores the {lock.value} lock"
    _link(monkeypatch, rs, frozenset(Lock) - {lock})
    assert signal.fires(db, rs), f"{signal.name} answers to a lock other than {lock.value}"


def test_every_lock_names_its_derived_signals_or_says_it_has_none() -> None:
    """A lock added to the enum is named here, signals or reason."""
    assert set(SIGNALS) | set(ROUTE_ONLY) == set(Lock)
    assert not set(SIGNALS) & set(ROUTE_ONLY)
    assert all(SIGNALS.values())
