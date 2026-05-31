"""Reviewers extract — Segment 12A-1 PR 2.

Streams the session's reviewer roster as a CSV whose column shape
matches the existing reviewer importer
(``app.services.csv_imports.parse_reviewer_csv``), so the file
round-trips with the upload flow on the Reviewers Manage page
and the Quick Setup card without conversion.

The ``PhotoLink`` column maps to ``Reviewer.profile_link``,
mirroring ``reviewees_extract.PhotoLink`` per participant-model
upgrade §3.9 (Reviewer / Reviewee parity).

Both ``status="active"`` and ``status="inactive"`` rows are
included — the importer treats inactive rows as inactive on the
next session anyway, so excluding them would lose state on the
round-trip.

Plan: ``guide/segment_12A-1_export.md`` PR 2.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Reviewer, ReviewSession

__all__ = ["HEADER", "serialize_reviewers"]


# Header tuple matching the importer's required + optional columns
# (csv_imports.parse_reviewer_csv:167 / 238-240). Pinned here so a
# rename on either side fails loud in a contract test.
HEADER: tuple[str, ...] = (
    "ReviewerName",
    "ReviewerEmail",
    "ReviewerTag1",
    "ReviewerTag2",
    "ReviewerTag3",
    "PhotoLink",
)


def serialize_reviewers(
    db: Session, review_session: ReviewSession
) -> Iterable[tuple[str, ...]]:
    """Yield CSV rows for ``review_session``'s reviewers.

    First yield is ``HEADER``; subsequent yields are one tuple per
    reviewer in ``(status="active" first, then name, then email)``
    order — deterministic so re-export of the same session is
    byte-stable, and active rows lead so the file reads top-to-
    bottom as the operator expects.
    """

    yield HEADER
    rows = (
        db.execute(
            select(Reviewer)
            .where(Reviewer.session_id == review_session.id)
            .order_by(
                # ``"active" < "inactive"`` lexicographically, so ASC
                # already puts active rows first. Pinning explicitly
                # in case a future status value disrupts the lex
                # order.
                (Reviewer.status != "active").asc(),
                Reviewer.name,
                Reviewer.email,
            )
        )
        .scalars()
        .all()
    )
    for reviewer in rows:
        yield (
            reviewer.name,
            reviewer.email,
            reviewer.tag_1 or "",
            reviewer.tag_2 or "",
            reviewer.tag_3 or "",
            reviewer.profile_link or "",
        )
