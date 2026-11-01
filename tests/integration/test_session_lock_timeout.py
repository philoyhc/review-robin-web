"""The session-lock bound (author, 2026-11-01; `docs/database.md`): a request waiting for another's
session lock gives up after ``LOCK_TIMEOUT_MS`` with the 409 page.

The wait itself needs two Postgres connections, so those tests run in the
``ci-postgres`` job (``TEST_DATABASE_URL``) and skip on SQLite, which never
blocks. The 409 page is checked on any database.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete, text
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.services import session_guard
from app.services.session_guard import BUSY_MESSAGE, SessionBusy, lock_session
from app.web.error_handlers import register_error_handlers


@pytest.fixture
def committed_session(engine: Engine) -> Iterator[int]:
    """A session row committed where a second connection can see it."""
    if engine.dialect.name != "postgresql":
        pytest.skip("the lock wait needs Postgres; SQLite never blocks")
    tag = uuid.uuid4().hex[:8]
    with Session(engine) as setup:
        user = User(email=f"lock-{tag}@example.edu", display_name="Lock Test")
        setup.add(user)
        setup.flush()
        review_session = ReviewSession(name="Lock", code=f"lock-{tag}", created_by_user_id=user.id)
        setup.add(review_session)
        setup.commit()
        session_id, user_id = review_session.id, user.id
    yield session_id
    with Session(engine) as cleanup:
        cleanup.execute(delete(ReviewSession).where(ReviewSession.id == session_id))
        cleanup.execute(delete(User).where(User.id == user_id))
        cleanup.commit()


def _lock_timeout(db: Session) -> str:
    return db.execute(text("SHOW lock_timeout")).scalar_one()


def test_a_held_lock_turns_a_waiter_away_within_the_bound(
    engine: Engine, committed_session: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(session_guard, "LOCK_TIMEOUT_MS", 300)
    with Session(engine) as holder, Session(engine) as waiter:
        lock_session(holder, holder.get(ReviewSession, committed_session))
        before = _lock_timeout(waiter)
        started = time.monotonic()
        with pytest.raises(SessionBusy) as raised:
            lock_session(waiter, waiter.get(ReviewSession, committed_session))
        waited = time.monotonic() - started
        assert 0.25 <= waited < 3.0
        assert str(raised.value) == BUSY_MESSAGE
        # The waiter's transaction is still usable, and waits as before.
        assert _lock_timeout(waiter) == before
        assert waiter.execute(text("SELECT 1")).scalar_one() == 1
        holder.rollback()
        # Released, the same waiter takes the lock.
        assert lock_session(waiter, waiter.get(ReviewSession, committed_session)).id == committed_session
        assert _lock_timeout(waiter) == before
        waiter.rollback()


def test_an_uncontended_lock_leaves_the_timeout_as_it_was(engine: Engine, committed_session: int) -> None:
    with Session(engine) as db:
        before = _lock_timeout(db)
        lock_session(db, db.get(ReviewSession, committed_session))
        assert _lock_timeout(db) == before
        db.rollback()


def test_a_timeout_the_transaction_set_itself_is_put_back(engine: Engine, committed_session: int) -> None:
    """Not merely back to the server's default: whatever applied before."""
    with Session(engine) as db:
        db.execute(text("SET LOCAL lock_timeout = '2s'"))
        lock_session(db, db.get(ReviewSession, committed_session))
        assert _lock_timeout(db) == "2s"
        db.rollback()


def test_a_busy_session_renders_the_409_page() -> None:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/busy")
    def busy() -> None:
        raise SessionBusy()

    reply = TestClient(app).get("/busy")
    assert reply.status_code == 409
    assert "Someone else is changing this session" in reply.text
