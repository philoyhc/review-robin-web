"""One commit for a request that calls several committing services.

Services here commit at their own edge (the package convention), which
is right for a route that calls one of them. A route that applies
several in sequence and must be all-or-nothing — the Instrument card's
Save (findings A16) — wraps them in :func:`single_commit`; inside it,
:func:`commit` only flushes, so a refusal part-way through can roll the
whole request back. The route makes the one real ``db.commit()`` itself.
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


def commit(db: Session) -> None:
    """``db.commit()``, or ``db.flush()`` inside :func:`single_commit`."""
    if db.info.get(_DEFER_KEY, False):
        db.flush()
    else:
        db.commit()


__all__ = ["commit", "single_commit"]
