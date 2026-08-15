"""Rehydrate stash service — Segment 18P PR G2.

Holds an uploaded extract file set (as one opaque blob) between the
rehydrate **Validate** request (which stashes it) and the **Rehydrate**
commit request (which loads it). Postgres-backed so the hand-off
survives App Service scale-out; operator-scoped and TTL-bounded so a
token is only usable by the operator who created it, briefly.

The caller decides what ``payload`` is (a re-zipped bundle of the
resolved files); this module just stores / fetches / expires it.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import RehydrateStash, User

# How long a stashed set stays usable between Validate and Commit. Short
# on purpose — it only needs to bridge one operator's click-through.
STASH_TTL = timedelta(hours=1)

_TOKEN_BYTES = 32


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware_utc(value: datetime) -> datetime:
    """SQLite drops tzinfo on write, so a fetched ``created_at`` can be
    naive. Treat naive values as UTC for age comparison."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def put(db: Session, *, payload: bytes, user: User) -> str:
    """Stash ``payload`` for ``user`` and return its opaque token."""
    token = secrets.token_urlsafe(_TOKEN_BYTES)
    db.add(
        RehydrateStash(
            token=token,
            operator_user_id=user.id,
            payload=payload,
        )
    )
    db.flush()
    return token


def get(db: Session, *, token: str, user: User) -> bytes | None:
    """Return the stashed payload for ``token`` — or ``None`` if it's
    unknown, belongs to a different operator, or has expired (an
    expired row is deleted on the way out)."""
    row = db.execute(
        select(RehydrateStash).where(RehydrateStash.token == token)
    ).scalar_one_or_none()
    if row is None:
        return None
    if row.operator_user_id != user.id:
        return None
    if _now() - _as_aware_utc(row.created_at) > STASH_TTL:
        db.delete(row)
        db.flush()
        return None
    return row.payload


def delete(db: Session, *, token: str) -> None:
    """Drop a stash by token (called after a successful commit).
    No-op when the token is unknown."""
    row = db.execute(
        select(RehydrateStash).where(RehydrateStash.token == token)
    ).scalar_one_or_none()
    if row is not None:
        db.delete(row)
        db.flush()


def sweep(db: Session) -> int:
    """Delete every stash older than the TTL. Returns the count.
    Done in Python (the table is tiny and transient) to stay
    dialect-agnostic. Safe to call opportunistically."""
    cutoff = _now() - STASH_TTL
    rows = db.execute(select(RehydrateStash)).scalars().all()
    deleted = 0
    for row in rows:
        if _as_aware_utc(row.created_at) < cutoff:
            db.delete(row)
            deleted += 1
    if deleted:
        db.flush()
    return deleted
