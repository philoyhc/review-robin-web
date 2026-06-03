"""Participant tokens extract — operator-side deanonymization key.

Streams a CSV mapping every Reviewer + Reviewee in the session to
their per-session opaque token (the same token the Anonymized
``by_instrument`` CSV swaps in for names + emails on the observer
collation surface). Lets the operator reverse a token they
received as a support question without re-implementing the hash
chain.

The token is computed per-row via
``app.services.participant_tokens.ParticipantTokenizer`` — the
same chain the observer-side Anonymized output uses, so a token
in the extract is byte-identical to the one in any Anonymized
download for the same session.

Use case: an observer hands the operator a token from an
Anonymized CSV ("which row is ``R-a3f8b2c1``?"); the operator
downloads ``participant_tokens.csv`` and Ctrl-Fs the token to
get back name + email.

The CSV is **not round-trip compatible** with any importer — it's
a one-way reference. Sibling ``reviewers.csv`` /
``reviewees.csv`` keep their importer-compatible column shapes.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Reviewee, Reviewer, ReviewSession
from app.services.participant_tokens import ParticipantTokenizer

__all__ = ["HEADER", "serialize_participant_tokens"]


HEADER: tuple[str, ...] = ("Role", "Name", "Email", "Token")


def serialize_participant_tokens(
    db: Session, review_session: ReviewSession
) -> Iterable[tuple[str, ...]]:
    """Yield CSV rows for ``review_session``'s participant tokens.

    First yield is ``HEADER``; subsequent yields are one row per
    Reviewer + Reviewee, reviewers first, each block sorted by
    ``(status="active" first, name, email)`` so re-export of the
    same session is byte-stable and the active rows lead the
    block.
    """
    yield HEADER

    tokenizer = ParticipantTokenizer(review_session)

    reviewer_rows = (
        db.execute(
            select(Reviewer)
            .where(Reviewer.session_id == review_session.id)
            .order_by(
                (Reviewer.status != "active").asc(),
                Reviewer.name,
                Reviewer.email,
            )
        )
        .scalars()
        .all()
    )
    for reviewer in reviewer_rows:
        yield (
            "Reviewer",
            reviewer.name,
            reviewer.email,
            tokenizer.token("reviewer", reviewer.id),
        )

    reviewee_rows = (
        db.execute(
            select(Reviewee)
            .where(Reviewee.session_id == review_session.id)
            .order_by(
                (Reviewee.status != "active").asc(),
                Reviewee.name,
                Reviewee.email_or_identifier,
            )
        )
        .scalars()
        .all()
    )
    for reviewee in reviewee_rows:
        yield (
            "Reviewee",
            reviewee.name,
            reviewee.email_or_identifier,
            tokenizer.token("reviewee", reviewee.id),
        )
