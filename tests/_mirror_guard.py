"""The symmetric-review mirror, checked at every commit the suite makes
(segment 20F rung 3).

Under ``sessions.symmetric_review`` the Reviewees roster is a copy of the
Reviewers roster, kept only because every writer of reviewers calls
``symmetric_review.sync_reviewees_from_reviewers`` before it commits. A new
writer that forgets leaves no failing test of its own. This guard closes
that: the integration ``db`` fixture runs ``mirror_problems`` after every
commit, on the test's own connection, and fails the test at teardown if a
symmetric session's mirror was ever out of step at a commit. A writer the
suite exercises therefore cannot skip the sync unnoticed.

A test that puts a mirror out of step on purpose (Validate's
``reviewees.mirror_drift`` tests) marks itself ``mirror_drift_expected``.
"""

from __future__ import annotations

from sqlalchemy import Connection, select

from app.db.models import Reviewee, Reviewer, ReviewSession
from app.services.symmetric_review import MIRRORED_FIELDS


def mirror_problems(connection: Connection) -> list[str]:
    """Every symmetric session's mirror faults, as one line each; empty
    when every mirror is in step. The same faults Validate's
    ``reviewees.mirror_drift`` reports."""
    session_ids = list(
        connection.execute(
            select(ReviewSession.id).where(ReviewSession.symmetric_review.is_(True))
        ).scalars()
    )
    if not session_ids:
        return []
    reviewer_cols = [Reviewer.__table__.c[name] for _, name in MIRRORED_FIELDS]
    reviewee_cols = [Reviewee.__table__.c[name] for name, _ in MIRRORED_FIELDS]
    problems: list[str] = []
    for session_id in session_ids:
        reviewers = {
            row[0]: tuple(row[1:])
            for row in connection.execute(
                select(Reviewer.id, *reviewer_cols).where(Reviewer.session_id == session_id)
            )
        }
        linked: dict[int, list[tuple]] = {}
        for row in connection.execute(
            select(Reviewee.id, Reviewee.mirrors_reviewer_id, *reviewee_cols).where(
                Reviewee.session_id == session_id
            )
        ):
            fields = tuple(row)
            reviewee_id, link, values = fields[0], fields[1], fields[2:]
            if link not in reviewers:
                problems.append(f"session {session_id}: reviewee {reviewee_id} mirrors no reviewer")
            else:
                linked.setdefault(link, []).append(values)
        for reviewer_id, values in reviewers.items():
            mirrors = linked.get(reviewer_id, [])
            if len(mirrors) != 1:
                problems.append(
                    f"session {session_id}: reviewer {reviewer_id} has {len(mirrors)} mirrors"
                )
            elif mirrors[0] != values:
                problems.append(
                    f"session {session_id}: reviewer {reviewer_id}'s mirror differs"
                )
    return problems
