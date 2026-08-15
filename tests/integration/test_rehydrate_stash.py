"""18P PR G2 — the rehydrate stash service (put / get / delete / sweep).

Operator-scoped, TTL-bounded, Postgres-backed hand-off between the
rehydrate Validate and Commit requests.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import RehydrateStash, User
from app.services import rehydrate_stash


def _user(db: Session, email: str) -> User:
    user = User(email=email, display_name=email.split("@", 1)[0])
    db.add(user)
    db.flush()
    return user


def _age(db: Session, token: str, *, hours: float) -> None:
    row = db.execute(
        select(RehydrateStash).where(RehydrateStash.token == token)
    ).scalar_one()
    row.created_at = datetime.now(timezone.utc) - timedelta(hours=hours)
    db.flush()


def test_put_get_round_trip(db: Session) -> None:
    user = _user(db, "op@e.edu")
    token = rehydrate_stash.put(db, payload=b"hello world", user=user)
    assert rehydrate_stash.get(db, token=token, user=user) == b"hello world"


def test_unknown_token_returns_none(db: Session) -> None:
    user = _user(db, "op@e.edu")
    assert rehydrate_stash.get(db, token="nope", user=user) is None


def test_foreign_operator_rejected(db: Session) -> None:
    owner = _user(db, "owner@e.edu")
    other = _user(db, "other@e.edu")
    token = rehydrate_stash.put(db, payload=b"x", user=owner)
    assert rehydrate_stash.get(db, token=token, user=other) is None
    # Still readable by the owner.
    assert rehydrate_stash.get(db, token=token, user=owner) == b"x"


def test_expired_token_rejected_and_deleted(db: Session) -> None:
    user = _user(db, "op@e.edu")
    token = rehydrate_stash.put(db, payload=b"x", user=user)
    _age(db, token, hours=2)  # past the 1h TTL
    assert rehydrate_stash.get(db, token=token, user=user) is None
    # The expired row is dropped on the way out.
    assert (
        db.execute(
            select(RehydrateStash).where(RehydrateStash.token == token)
        ).scalar_one_or_none()
        is None
    )


def test_delete(db: Session) -> None:
    user = _user(db, "op@e.edu")
    token = rehydrate_stash.put(db, payload=b"x", user=user)
    rehydrate_stash.delete(db, token=token)
    assert rehydrate_stash.get(db, token=token, user=user) is None


def test_sweep_removes_expired_only(db: Session) -> None:
    user = _user(db, "op@e.edu")
    fresh = rehydrate_stash.put(db, payload=b"fresh", user=user)
    old = rehydrate_stash.put(db, payload=b"old", user=user)
    _age(db, old, hours=2)

    assert rehydrate_stash.sweep(db) == 1
    assert rehydrate_stash.get(db, token=fresh, user=user) == b"fresh"
    assert rehydrate_stash.get(db, token=old, user=user) is None
