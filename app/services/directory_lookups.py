"""Directory answers kept for an upload's countdown — segment 20H Item 6.

The roster Upload card's script looks the file's addresses up in batches
before it posts the file, so the page can count down what is left
(``guide/segment_20H_walkthrough_19Z_followups.md`` Item 6). Each answer
the server fetched from Graph is kept here for :data:`CACHE_TTL`; the
upload then reads those (`csv_imports.directory_check`'s ``known``) and
asks Graph only for the rest.

Only the server's own fetches are kept: the page never posts an outcome,
so nothing it sends can bind a row to an account. Only answers are kept
(`directory_accounts.ANSWERED`); a failed lookup is asked again at the
upload, as 20G ruled. Modeled on :mod:`app.services.held_uploads`:
Postgres-backed, scoped to an operator and a session, swept
opportunistically. Nothing here writes an audit event; a cached answer
saves nothing until an import does, which audits as before.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from cordware.graph import DirectoryUser, Outcome

from app.db.models import DirectoryLookup, User
from app.services import directory_accounts

#: How long a fetched answer stands in for a lookup (author, 2026-11-03):
#: long enough to look a large file up and upload it, short enough that
#: a directory change since is seen at the next upload.
CACHE_TTL = timedelta(minutes=15)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fresh(row: DirectoryLookup, now: datetime) -> bool:
    """SQLite drops tzinfo on write; a naive value is UTC."""
    fetched = row.fetched_at
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=timezone.utc)
    return now - fetched <= CACHE_TTL


def _outcome(row: DirectoryLookup) -> Outcome:
    user = None
    if row.account_id is not None:
        user = DirectoryUser(
            id=row.account_id,
            display_name=row.display_name or "",
            mail=row.mail,
            user_principal_name=row.upn or "",
        )
    return Outcome(row.status, row.match_type, user=user, note=row.note)


def _rows(db: Session, *, user: User, session_id: int, keys: list[str]) -> list[DirectoryLookup]:
    if not keys:
        return []
    return list(
        db.execute(
            select(DirectoryLookup).where(
                DirectoryLookup.operator_user_id == user.id,
                DirectoryLookup.session_id == session_id,
                DirectoryLookup.key.in_(keys),
            )
        ).scalars()
    )


def recall(
    db: Session, *, user: User, session_id: int, keys: Iterable[str]
) -> dict[str, Outcome]:
    """The fresh answers kept for ``keys``, this operator's and this
    session's; a stale one reads as absent."""
    now = _now()
    return {
        row.key: _outcome(row)
        for row in _rows(db, user=user, session_id=session_id, keys=list(dict.fromkeys(keys)))
        if _fresh(row, now)
    }


def known_for(
    db: Session, *, user: User, session_id: int, addresses: Iterable[str | None]
) -> dict[str, Outcome]:
    """:func:`recall` for a roster's addresses as written: what an
    upload hands its directory check as ``known``."""
    keys = (directory_accounts.key(a) for a in addresses)
    return recall(db, user=user, session_id=session_id, keys=[k for k in keys if k])


def remember(
    db: Session, *, user: User, session_id: int, outcomes: Mapping[str, Outcome]
) -> int:
    """Keep each answer in ``outcomes``, replacing what was kept for its
    key; a failed lookup is not kept. Returns how many were kept."""
    answered = {
        k: o for k, o in outcomes.items() if o.status in directory_accounts.ANSWERED
    }
    if not answered:
        return 0
    db.execute(
        delete(DirectoryLookup).where(
            DirectoryLookup.operator_user_id == user.id,
            DirectoryLookup.session_id == session_id,
            DirectoryLookup.key.in_(list(answered)),
        )
    )
    for k, o in answered.items():
        account = o.user
        db.add(
            DirectoryLookup(
                operator_user_id=user.id,
                session_id=session_id,
                key=k,
                status=o.status,
                match_type=o.match_type,
                note=o.note[:255],
                account_id=account.id if account else None,
                display_name=account.display_name if account else None,
                mail=account.mail if account else None,
                upn=account.user_principal_name if account else None,
            )
        )
    db.flush()
    return len(answered)


def sweep(db: Session) -> int:
    """Delete every stale answer. Returns the count. Called once an
    upload's countdown starts (the keys request), so no scheduler is
    needed. Compared in Python, as ``held_uploads.sweep`` is: SQLite
    hands back naive datetimes."""
    now = _now()
    stale = [
        row_id
        for row_id, fetched_at in db.execute(
            select(DirectoryLookup.id, DirectoryLookup.fetched_at)
        )
        if now - (fetched_at if fetched_at.tzinfo else fetched_at.replace(tzinfo=timezone.utc))
        > CACHE_TTL
    ]
    if stale:
        db.execute(delete(DirectoryLookup).where(DirectoryLookup.id.in_(stale)))
        db.flush()
    return len(stale)
