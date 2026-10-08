"""One commit for a request that calls several committing services.

Services here commit at their own edge (the package convention), which
is right for a route that calls one of them. A caller that applies
several in sequence and must be all-or-nothing wraps them in
:func:`single_commit`; inside it, :func:`commit` only flushes, so a
refusal part-way through can roll the whole unit back. The caller makes
the one real commit itself — the Instrument card's Save route (findings
A16) — or opens :func:`atomic`, which commits and rolls back for it:
the reviewer, reviewee and relationship imports, the label editor and
Generate (``assignments.replace_assignments``), which hold the session
lock from their gate to that commit (findings Bc4).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

_DEFER_KEY = "unit_of_work.defer_commit"


@contextmanager
def single_commit(db: Session) -> Iterator[None]:
    """While open, :func:`commit` on ``db`` flushes instead of committing."""
    previous = db.info.get(_DEFER_KEY, False)
    db.info[_DEFER_KEY] = True
    try:
        yield
    finally:
        db.info[_DEFER_KEY] = previous


@contextmanager
def atomic(db: Session) -> Iterator[None]:
    """One all-or-nothing unit that commits on its own when outermost.

    :func:`single_commit` around the body, then :func:`commit` — a real
    commit, or a flush inside a caller's own :func:`single_commit`, so
    the caller still owns its unit. If the body or that commit raises,
    the outermost unit rolls back, so a refusal leaves no flushed
    half-write behind for a later commit to pick up; a nested one
    leaves that to the unit that owns it."""
    outermost = not db.info.get(_DEFER_KEY, False)
    try:
        with single_commit(db):
            yield
        commit(db)
    except BaseException:
        if outermost:
            db.rollback()
        raise


def commit(db: Session) -> None:
    """``db.commit()``, or ``db.flush()`` inside :func:`single_commit`."""
    if db.info.get(_DEFER_KEY, False):
        db.flush()
    else:
        db.commit()


__all__ = ["atomic", "commit", "single_commit"]
