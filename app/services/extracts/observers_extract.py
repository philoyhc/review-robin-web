"""Observers extract — sibling of ``relationships_extract``.

Streams the session's ``observers`` rows as a CSV whose column
shape matches ``csv_imports.parse_observer_csv`` (``ObserverEmail``
required; ``ObserverName`` / ``ObserverTag1`` optional), so the
file round-trips with the Observers Setup-page Upload card and the
Quick Setup card's observers slot without conversion.

Closes the Extract Setup leg of L2 from
``guide/participant_model_remainder.md``.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Observer, ReviewSession

__all__ = ["HEADER", "serialize_observers"]


HEADER: tuple[str, ...] = (
    "ObserverEmail",
    "ObserverName",
    "ObserverTag1",
    "Status",
)


def serialize_observers(
    db: Session, review_session: ReviewSession
) -> Iterable[tuple[str, ...]]:
    """Yield CSV rows for ``review_session``'s observers.

    First yield is ``HEADER``; subsequent yields are one tuple
    per observer row in (status="active" first, then email) order
    — same active-first sort the Reviewers / Reviewees / Relationships
    extracts use.
    """

    yield HEADER
    rows = db.execute(
        select(Observer)
        .where(Observer.session_id == review_session.id)
        .order_by(
            (Observer.status != "active").asc(),
            Observer.email,
        )
    ).scalars().all()
    for observer in rows:
        yield (
            observer.email,
            observer.display_name or "",
            observer.tag_1 or "",
            observer.status,
        )
