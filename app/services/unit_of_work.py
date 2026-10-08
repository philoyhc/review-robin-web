"""One commit for a request that calls several committing services.

Services here commit at their own edge (the package convention), which
is right for a route that calls one of them. A caller that applies
several in sequence and must be all-or-nothing wraps them in
:func:`single_commit`; inside it, :func:`commit` only flushes, so a
refusal part-way through can roll the whole unit back. The caller makes
the one real commit itself — the Instrument card's Save route (findings
A16) — or opens :func:`atomic`, which commits and rolls back for it:
the reviewer, reviewee and relationship imports, the label editor, the
instrument identity and Band 2 routes, Session Home's config save,
Generate (``assignments.replace_assignments``) and Purge and archive,
which hold the session lock from their gate to that commit (findings
Bc4). :func:`after_commit` defers a side effect — a log line saying work
was done — to that commit, and drops it if the unit rolls back.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

_DEFER_KEY = "unit_of_work.defer_commit"
_AFTER_KEY = "unit_of_work.after_commit"


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
            db.info.pop(_AFTER_KEY, None)
        raise


def commit(db: Session) -> None:
    """``db.commit()``, or ``db.flush()`` inside :func:`single_commit`.

    A real commit runs the :func:`after_commit` callbacks queued in the
    unit it closes; a failed one drops them."""
    if db.info.get(_DEFER_KEY, False):
        db.flush()
        return
    try:
        db.commit()
    except BaseException:
        db.info.pop(_AFTER_KEY, None)
        raise
    for fn in db.info.pop(_AFTER_KEY, []):
        fn()


def after_commit(db: Session, fn: Callable[[], None]) -> None:
    """Run ``fn`` once the work so far is committed: now, outside a unit;
    after the unit's real commit inside one, and never if the unit rolls
    back. For a side effect that must not report work the unit then
    discards — a "purged" or "imported" log line."""
    if db.info.get(_DEFER_KEY, False):
        db.info.setdefault(_AFTER_KEY, []).append(fn)
    else:
        fn()


__all__ = ["after_commit", "atomic", "commit", "single_commit"]
