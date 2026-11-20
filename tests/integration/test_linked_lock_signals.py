"""Every reader of a linked application's lock honours it, and each is named.

A linked application's lock (`app/services/linked_apps.py` ``Lock``) is
enforced where it was written: the routes refuse, and the page that serves
them says so (`tests/integration/test_linked_sessions.py`).

The 2026-11-20 assessment found a gap beside that. The lobby's Due pill read
the due prompts without the email lock, while the Workflow card, which
checked the lock itself, showed nothing
(`guide/findings_2026-11-20_assessment.md` D1). The corpus sweep found the
auto-send captions promising sends the trigger skips
(`guide/findings_2026-11-20_corpus.md` B3). The two were one miss: a signal
computed from a locked thing, outside the gate that holds the lock.

This file therefore holds two checks:

- **Completeness, derived from the code.** For each lock, every module in
  `app/` outside the route layer that reads it (``Lock.<NAME>``) must be
  named in ``READERS``, with either a signal checked here or the test that
  already covers it. A new reader of a lock fails until someone says where
  it is tested. A pointer is checked to resolve to a test, not for what
  that test asserts.
- **The signals checked here.** These are the readers no other test
  covered. Each must:
  - fire on a native session;
  - fall silent under a profile that takes that lock alone;
  - still fire under a profile taking every lock but that one, so the
    silence is that lock's and no other's.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.config import settings
from app.db.models import Reviewer, ReviewSession, User
from app.services import due_actions, invitations, linked_apps, sessions
from app.services import session_lifecycle as lifecycle
from app.services.linked_apps import LinkedProfile, Lock
from app.web import views
from app.web.views import _workflow_card

from .test_invitations import _ready_session
from .test_responses_received_queued import _answer_and_submit
from .test_responses_received_queued import _ready_session as _submittable_session

REPO = Path(__file__).resolve().parents[2]


@dataclass
class Ctx:
    client: TestClient
    db: Session
    mp: pytest.MonkeyPatch
    make_client: Callable[[AuthenticatedUser], TestClient]


@dataclass(frozen=True)
class Signal:
    """A derived signal: how to make it fire on a native session, and
    whether it fires."""

    name: str
    arrange: Callable[[Ctx], ReviewSession]
    fires: Callable[[Session, ReviewSession], bool]


# ── arrangements ─────────────────────────────────────────────────────


def _due_invites(ctx: Ctx) -> ReviewSession:
    """A ready session with an invite offset passed and scheduled email
    off: a prompt is due by hand (14F rung 5b)."""
    ctx.mp.setattr(settings, "scheduled_send", False)
    rs = _ready_session(ctx.client, ctx.db, code="lock-due")
    rs.scheduled_activate_at = datetime.now(UTC) + timedelta(hours=1)
    rs.invite_offsets = ["-P1D"]
    ctx.db.commit()
    return rs


def _auto_send(ctx: Ctx) -> ReviewSession:
    """A ready session with invite and reminder offsets still to fire and
    scheduled email on: the captions promise a send."""
    ctx.mp.setattr(settings, "scheduled_send", True)
    rs = _ready_session(ctx.client, ctx.db, code="lock-auto")
    now = datetime.now(UTC)
    rs.scheduled_activate_at = now + timedelta(days=2)
    rs.invite_offsets = ["-P1D"]
    rs.deadline = now + timedelta(days=5)
    rs.reminder_offsets = ["-P1D"]
    ctx.db.commit()
    return rs


def _activate_pending(ctx: Ctx) -> ReviewSession:
    """A prepared session whose Start would fire invite offsets: activating
    by hand would cancel them, so Activate asks first."""
    rs = _auto_send(ctx)
    rs.status = lifecycle.SessionStatus.validated.value
    ctx.db.commit()
    return rs


def _submitted(ctx: Ctx) -> ReviewSession:
    """A ready session whose reviewer has submitted: the confirmation
    queues."""
    rs = _submittable_session(ctx.client, ctx.db, "lock-received")
    rae = AuthenticatedUser(
        principal_id="rae-oid", email="rae@example.edu", name="Rae", provider="aad"
    )
    assert _answer_and_submit(ctx.make_client(rae), ctx.db, rs) == 303
    return rs


def _queues_confirmation(db: Session, rs: ReviewSession) -> bool:
    reviewer = db.scalars(select(Reviewer).where(Reviewer.session_id == rs.id)).one()
    user = db.scalars(select(User).where(User.email == "rae@example.edu")).one()
    queued = invitations.queue_responses_received(
        db, review_session=rs, reviewer=reviewer, user=user
    )
    return queued is not None


def _release_reached(ctx: Ctx) -> ReviewSession:
    """An expired session past its release anchor: the window is open."""
    rs = _ready_session(ctx.client, ctx.db, code="lock-release")
    rs.status = lifecycle.SessionStatus.expired.value
    rs.responses_release_at = datetime.now(UTC) - timedelta(hours=1)
    ctx.db.commit()
    return rs


def _draft(ctx: Ctx) -> ReviewSession:
    ctx.client.post("/operator/sessions", data={"name": "Lock draft", "code": "lock-draft"})
    return ctx.db.scalars(select(ReviewSession).where(ReviewSession.code == "lock-draft")).one()


def _turns_on_observers(db: Session, rs: ReviewSession) -> bool:
    """A roster upload turns the Observers toggle on, unless locked."""
    rs.observers_enabled = False
    user = db.scalars(select(User)).first()
    assert user is not None
    changes = sessions.turn_on_populated_features(
        db, rs, populated=["observers"], before={}, user=user, reason="lock-test"
    )
    return "observers_enabled" in changes


# ── the signals checked here ─────────────────────────────────────────

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
        Signal(
            "the responses-received confirmation",
            _submitted,
            _queues_confirmation,
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
    Lock.OBSERVERS: (
        Signal(
            "a roster upload turning Observers on",
            _draft,
            _turns_on_observers,
        ),
    ),
}

# ── every reader outside the route layer, and where it is tested ─────

_LINKED = "tests/integration/test_linked_sessions.py::"
_SCHEDULE = "tests/integration/test_linked_email_schedule.py::"
READERS: dict[Lock, dict[str, str]] = {
    Lock.EMAIL: {
        "app/services/due_actions.py": "signal: the due prompts",
        "app/services/invitations.py": "signal: the responses-received confirmation",
        "app/services/scheduled_events/_invites.py": (
            _SCHEDULE + "test_the_schedule_sends_no_email_for_apply_desk"
        ),
        "app/services/scheduled_events/_reminders.py": (
            _SCHEDULE + "test_the_schedule_sends_no_email_for_apply_desk"
        ),
        "app/web/views/_workflow_card.py": "signal: the auto-send invites caption",
    },
    Lock.RELEASE: {
        "app/services/session_config_io/_apply_parse.py": (
            _LINKED + "test_a_settings_import_refuses_release_values_and_observers"
        ),
        "app/services/session_lifecycle.py": "signal: the response release window",
        "app/services/validation/_rosters.py": (
            _LINKED + "test_validate_raises_no_unreachable_results_warning"
        ),
        "app/web/views/_instruments.py": _LINKED + "test_the_visibility_card_names_the_application",
        "app/web/views/_workflow_card.py": _LINKED + "test_the_workflow_card_offers_no_release",
    },
    Lock.OBSERVERS: {
        "app/services/handoffs.py": _LINKED + "test_a_linked_handoff_refuses_an_observers_file",
        "app/services/session_config_io/_apply_parse.py": (
            _LINKED + "test_a_settings_import_refuses_release_values_and_observers"
        ),
        "app/services/sessions.py": "signal: a roster upload turning Observers on",
        "app/web/views/_quick_setup.py": _LINKED + "test_quick_setup_offers_and_takes_no_observers",
    },
    Lock.INSTRUMENT_STRUCTURE: {
        "app/services/handoffs.py": (
            _LINKED + "test_the_create_fixes_the_rule_and_the_display_default"
        ),
        "app/services/instruments/_display_fields.py": (
            _LINKED + "test_prepare_seeds_no_relationship_tag_display_field"
        ),
        "app/services/instruments/_instrument_crud.py": (
            _LINKED + "test_the_page_seeds_no_display_field_back"
        ),
        "app/services/linked_settings.py": (
            "tests/integration/test_handoff_update.py::"
            "test_a_resend_writes_the_instruments_owned_rows"
        ),
    },
    Lock.ROSTERS: {
        "app/web/views/_linked_rosters.py": "signal: the roster pages' editability",
    },
    # Read only by routes and their gates, tested where they serve.
    Lock.SESSION_DETAILS: {},
    Lock.QUICK_SETUP: {},
    Lock.SETTINGS_IMPORT: {},
    Lock.INVITATION_SEND: {},
}


def _is_route_layer(rel: str) -> bool:
    """The gates: routing modules and their dependencies, tested where they
    serve (`tests/integration/test_linked_sessions.py`)."""
    return "/routes_" in rel or rel == "app/web/deps.py"


def _readers(lock: Lock) -> set[str]:
    pattern = re.compile(rf"\bLock\.{lock.name}\b")
    found: set[str] = set()
    for path in (REPO / "app").rglob("*.py"):
        rel = path.relative_to(REPO).as_posix()
        if rel == "app/services/linked_apps.py" or _is_route_layer(rel):
            continue
        if pattern.search(path.read_text()):
            found.add(rel)
    return found


CASES = [(lock, signal) for lock, signals in SIGNALS.items() for signal in signals]


def _link(monkeypatch: pytest.MonkeyPatch, rs: ReviewSession, locks: frozenset[Lock]) -> None:
    """Link ``rs`` to a profile taking exactly ``locks``."""
    profile = LinkedProfile("probe", "Probe", "Probe", locks=locks)
    monkeypatch.setitem(linked_apps.LINKED_APPS, "probe", profile)
    rs.linked_app = "probe"


@pytest.mark.parametrize(
    ("lock", "signal"), CASES, ids=[f"{lock.value}: {signal.name}" for lock, signal in CASES]
)
def test_a_signal_honours_its_lock_and_only_its_lock(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    make_client: Callable[[AuthenticatedUser], TestClient],
    lock: Lock,
    signal: Signal,
) -> None:
    rs = signal.arrange(Ctx(client, db, monkeypatch, make_client))
    assert signal.fires(db, rs), f"{signal.name} should fire on a native session"
    _link(monkeypatch, rs, frozenset({lock}))
    assert not signal.fires(db, rs), f"{signal.name} ignores the {lock.value} lock"
    _link(monkeypatch, rs, frozenset(Lock) - {lock})
    assert signal.fires(db, rs), f"{signal.name} answers to a lock other than {lock.value}"


@pytest.mark.parametrize("lock", list(Lock), ids=[lock.value for lock in Lock])
def test_every_reader_of_a_lock_is_named_with_where_it_is_tested(lock: Lock) -> None:
    """The readers come from the code, so a new one fails here until it is
    named, with a signal above or the test that covers it."""
    assert lock in READERS, f"{lock.value} has no READERS entry"
    named = READERS[lock]
    found = _readers(lock)
    assert set(named) == found, (
        f"{lock.value}: unnamed readers {sorted(found - set(named))}, "
        f"named but no longer reading {sorted(set(named) - found)}"
    )
    signals = {signal.name for signal in SIGNALS.get(lock, ())}
    for module, where in named.items():
        if where.startswith("signal: "):
            assert where.removeprefix("signal: ") in signals, (module, where)
            continue
        test_file, _, test_name = where.partition("::")
        source = (REPO / test_file).read_text()
        assert re.search(rf"^def {re.escape(test_name)}\(", source, re.M), (module, where)
