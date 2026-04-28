from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.schemas.assignments import AssignmentMode
from app.services import audit


def get_or_create_default_instrument(
    db: Session, review_session: ReviewSession
) -> Instrument:
    existing = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .order_by(Instrument.id)
    ).scalars().first()
    if existing is not None:
        return existing

    instrument = Instrument(
        session_id=review_session.id,
        name="Default",
        order=0,
    )
    db.add(instrument)
    db.flush()
    return instrument


def existing_count(db: Session, session_id: int) -> int:
    stmt = select(Assignment.id).where(Assignment.session_id == session_id)
    return len(db.execute(stmt).all())


def _is_self_review(reviewer: Reviewer, reviewee: Reviewee) -> bool:
    identifier = reviewee.email_or_identifier
    if "@" not in identifier:
        return False
    return reviewer.email.casefold() == identifier.casefold()


def generate_full_matrix(
    reviewers: Iterable[Reviewer],
    reviewees: Iterable[Reviewee],
    *,
    exclude_self_review: bool,
) -> tuple[list[tuple[Reviewer, Reviewee]], int]:
    """Return (pairs, excluded_self_count). Deterministic ordering by id."""
    sorted_reviewers = sorted(reviewers, key=lambda r: r.id)
    sorted_reviewees = sorted(reviewees, key=lambda r: r.id)
    pairs: list[tuple[Reviewer, Reviewee]] = []
    excluded = 0
    for reviewer in sorted_reviewers:
        for reviewee in sorted_reviewees:
            if exclude_self_review and _is_self_review(reviewer, reviewee):
                excluded += 1
                continue
            pairs.append((reviewer, reviewee))
    return pairs, excluded


def coverage_stats(
    reviewers: list[Reviewer],
    reviewees: list[Reviewee],
    pairs: list[tuple[Reviewer, Reviewee]],
) -> dict[str, Any]:
    reviewer_ids_with_pair = {r.id for r, _ in pairs}
    reviewee_ids_with_pair = {e.id for _, e in pairs}
    return {
        "total": len(pairs),
        "reviewers_total": len(reviewers),
        "reviewees_total": len(reviewees),
        "reviewers_covered": len(reviewer_ids_with_pair),
        "reviewees_covered": len(reviewee_ids_with_pair),
        "reviewers_uncovered": [
            r for r in reviewers if r.id not in reviewer_ids_with_pair
        ],
        "reviewees_uncovered": [
            r for r in reviewees if r.id not in reviewee_ids_with_pair
        ],
    }


def replace_assignments(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    pairs: list[tuple[Reviewer, Reviewee]],
    mode: AssignmentMode,
    correlation_id: str,
    excluded_self_count: int = 0,
    filename: str | None = None,
    contexts: list[dict[str, Any] | None] | None = None,
    includes: list[bool] | None = None,
) -> tuple[int, int]:
    """Replace all assignments for the session. Returns (replaced, new)."""
    if contexts is not None and len(contexts) != len(pairs):
        raise ValueError("contexts length must match pairs length")
    if includes is not None and len(includes) != len(pairs):
        raise ValueError("includes length must match pairs length")

    instrument = get_or_create_default_instrument(db, review_session)

    replaced = existing_count(db, review_session.id)
    db.execute(delete(Assignment).where(Assignment.session_id == review_session.id))

    for index, (reviewer, reviewee) in enumerate(pairs):
        db.add(
            Assignment(
                session_id=review_session.id,
                reviewer_id=reviewer.id,
                reviewee_id=reviewee.id,
                instrument_id=instrument.id,
                include=includes[index] if includes is not None else True,
                context=contexts[index] if contexts is not None else None,
                created_by_mode=mode.value,
            )
        )

    review_session.assignment_mode = mode.value
    db.flush()

    audit.write_event(
        db,
        event_type="assignments.generated",
        summary=(
            f"Generated {len(pairs)} assignments via {mode.value} "
            f"(replaced {replaced})"
        ),
        actor_user_id=user.id,
        session_id=review_session.id,
        detail={
            "mode": mode.value,
            "replaced_count": replaced,
            "new_count": len(pairs),
            "excluded_self_count": excluded_self_count,
            "filename": filename,
        },
        correlation_id=correlation_id,
    )

    db.commit()
    return replaced, len(pairs)


def list_reviewers(db: Session, session_id: int) -> list[Reviewer]:
    return list(
        db.execute(
            select(Reviewer).where(Reviewer.session_id == session_id)
        ).scalars()
    )


def list_reviewees(db: Session, session_id: int) -> list[Reviewee]:
    return list(
        db.execute(
            select(Reviewee).where(Reviewee.session_id == session_id)
        ).scalars()
    )
