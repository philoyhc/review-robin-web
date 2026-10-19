"""Held uploads — segment 19W.

An upload refused with a question (a missing replace tick, a
group-clear count, the Settings import's deletion count) holds the
files of that submit here, so the operator ticks and submits again
without choosing them again (``guide/segment_19W_held_uploads.md``).

Modeled on :mod:`app.services.rehydrate_stash`: Postgres-backed so the
ask and its answer may land on different instances, opaque random
tokens, a short TTL swept opportunistically. Unlike a stash, a hold is
scoped to a session as well as an operator, and keeps one row per slot
under a shared token, so one slot can be replaced on its own.

A hold is a convenience, never a trust boundary: the caller parses the
held bytes again on every submit, exactly as it would a fresh upload.
Nothing here writes an audit event; a hold saves nothing.
"""
from __future__ import annotations

import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import HeldUpload, User
from app.services.csv_imports import MAX_BYTES

#: How long a held file stays usable: one operator answering one ask.
#: The same hour as ``rehydrate_stash.STASH_TTL``.
HOLD_TTL = timedelta(hours=1)

#: A file larger than this is not held; the ask still shows and the file
#: is chosen again. The roster cap, which the Settings slot lacks.
MAX_HELD_BYTES = MAX_BYTES

_TOKEN_BYTES = 32


@dataclass(frozen=True)
class HeldFile:
    filename: str
    content: bytes


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware_utc(value: datetime) -> datetime:
    """SQLite drops tzinfo on write; treat a naive value as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _expired(row: HeldUpload) -> bool:
    return _now() - _as_aware_utc(row.created_at) > HOLD_TTL


def _rows(
    db: Session, *, token: str, user: User, session_id: int
) -> list[HeldUpload]:
    return list(
        db.execute(
            select(HeldUpload).where(
                HeldUpload.token == token,
                HeldUpload.operator_user_id == user.id,
                HeldUpload.session_id == session_id,
            )
        ).scalars()
    )


def hold(
    db: Session,
    *,
    user: User,
    session_id: int,
    files: Mapping[str, HeldFile],
    token: str | None = None,
) -> str | None:
    """Hold ``files`` (slot → file) and return their token.

    With ``token``, the files join that hold, each replacing any file the
    hold already has for its slot (a skipped file still drops the old
    one); a token that is not this operator's and this session's starts
    a new hold instead. A file over :data:`MAX_HELD_BYTES`, or an empty
    one, is skipped. Returns ``None`` when nothing ends up held. Sweeps
    expired holds first. :func:`take` says what the hold now holds.
    """
    sweep(db)
    keep = {
        slot: held
        for slot, held in files.items()
        if 0 < len(held.content) <= MAX_HELD_BYTES
    }
    if token is not None and not _rows(
        db, token=token, user=user, session_id=session_id
    ):
        token = None
    if token is not None:
        # Every slot this call brings drops what the hold had for it,
        # kept or not: a file too large to hold must not leave the one it
        # replaced to be sent again in its place.
        db.execute(
            delete(HeldUpload).where(
                HeldUpload.token == token, HeldUpload.slot.in_(list(files))
            )
        )
        db.flush()
    if not keep:
        return token if token is not None and _rows(
            db, token=token, user=user, session_id=session_id
        ) else None
    if token is None:
        token = secrets.token_urlsafe(_TOKEN_BYTES)
    for slot, held in keep.items():
        db.add(
            HeldUpload(
                token=token,
                slot=slot,
                operator_user_id=user.id,
                session_id=session_id,
                filename=held.filename[:255] or "upload.csv",
                content=held.content,
            )
        )
    db.flush()
    return token


def take(
    db: Session, *, token: str, user: User, session_id: int
) -> dict[str, HeldFile]:
    """The files held under ``token`` for this operator and session, by
    slot. Another operator's or another session's token, an unknown one
    and an expired hold all read as empty; expired rows are deleted on
    the way out. Taking does not end the hold: :func:`discard` does."""
    held: dict[str, HeldFile] = {}
    stale = False
    for row in _rows(db, token=token, user=user, session_id=session_id):
        if _expired(row):
            db.delete(row)
            stale = True
            continue
        held[row.slot] = HeldFile(filename=row.filename, content=row.content)
    if stale:
        db.flush()
    return held


def discard(db: Session, *, token: str, user: User, session_id: int) -> int:
    """End the hold: delete its rows. Returns how many went; a token
    that is not this operator's and this session's deletes nothing."""
    rows = _rows(db, token=token, user=user, session_id=session_id)
    for row in rows:
        db.delete(row)
    if rows:
        db.flush()
    return len(rows)


def sweep(db: Session) -> int:
    """Delete every expired hold. Returns the count. Called by
    :func:`hold`, so no scheduler is needed. Compared in Python, as
    ``rehydrate_stash.sweep`` does: SQLite hands back naive datetimes,
    and the table holds at most a few rows per operator at a time."""
    cutoff = _now() - HOLD_TTL
    stale = [
        row_id
        for row_id, created_at in db.execute(
            select(HeldUpload.id, HeldUpload.created_at)
        )
        if _as_aware_utc(created_at) < cutoff
    ]
    if stale:
        db.execute(delete(HeldUpload).where(HeldUpload.id.in_(stale)))
        db.flush()
    return len(stale)
