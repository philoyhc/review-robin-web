"""``reviewer_review_count_for_user`` — the reviewer chrome's
"My Reviews" count (findings Ac4).

The count renders on every reviewer-chrome page, so it must be one
scoped aggregate rather than a load of every active reviewer in the
workspace folded in Python. The matching rule is unchanged: active
rows only, email compared stripped and case-insensitively, across
every session.
"""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.db.models import Reviewer, ReviewSession, User
from app.web.routes_reviewer._shared import reviewer_review_count_for_user


def _seed(db: Session) -> User:
    operator = User(email="op-ac4@example.edu")
    db.add(operator)
    db.flush()
    first = ReviewSession(name="One", code="ac4-one", created_by_user_id=operator.id)
    second = ReviewSession(name="Two", code="ac4-two", created_by_user_id=operator.id)
    db.add_all([first, second])
    db.flush()
    db.add_all(
        [
            Reviewer(session_id=first.id, name="Rae", email="Rae@Example.edu"),
            Reviewer(session_id=second.id, name="Rae", email=" rae@example.edu "),
            Reviewer(
                session_id=second.id,
                name="Rae old",
                email="rae@example.edu",
                status="inactive",
            ),
            Reviewer(session_id=first.id, name="Bob", email="bob@example.edu"),
            Reviewer(session_id=first.id, name="Blank", email=""),
        ]
    )
    db.flush()
    return User(email="RAE@example.edu")


def test_counts_active_case_insensitive_matches_across_sessions(
    db: Session,
) -> None:
    viewer = _seed(db)
    assert reviewer_review_count_for_user(db, viewer) == 2
    assert reviewer_review_count_for_user(db, User(email="bob@example.edu")) == 1
    assert reviewer_review_count_for_user(db, User(email="nobody@example.edu")) == 0
    # An unidentifiable viewer matches nothing, not the blank-email row.
    assert reviewer_review_count_for_user(db, User(email="")) == 0


def test_is_one_aggregate_query_scoped_to_the_email(db: Session) -> None:
    """One ``COUNT`` with the email predicate in SQL — not a ``SELECT``
    of every active reviewer row."""
    viewer = _seed(db)
    statements: list[str] = []

    def _capture(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        statements.append(statement.lower())

    engine = db.get_bind().engine
    event.listen(engine, "before_cursor_execute", _capture)
    try:
        assert reviewer_review_count_for_user(db, viewer) == 2
    finally:
        event.remove(engine, "before_cursor_execute", _capture)

    (statement,) = [s for s in statements if "reviewers" in s]
    assert "count(" in statement
    assert "lower(" in statement
