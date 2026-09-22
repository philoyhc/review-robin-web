"""Unit coverage for Segment 19S Item 3 rung 1 — the assignment
insert is a bulk Core statement, and the rows it writes are visible
to the self-review passes that run after it.

The insert half of ``_materialise_one_instrument`` built one
``Assignment`` object per pair; the delete half three lines above it
has been bulk Core since PR #1065. A Core insert leaves **no identity-
map entries**, so everything downstream must see the rows through the
flush rather than through the unit of work. Two passes run right after
it inside the same transaction:

- ``recompute_self_review_classification``, which sets
  ``is_self_review`` — a row invisible to it keeps the column's
  Python-side ``default=False``;
- ``verify_self_review_classification``, which raises
  ``AssertionError`` in a test env on any divergence.

These tests pin that visibility as a property of the write, so the
switch to Core is made under coverage rather than ahead of it. They
read the stored column through a **column-tuple select** rather than
through an entity: the ``db`` fixture builds its session with
``expire_on_commit=False``, so an entity attribute can answer from the
identity map and never reach the row the insert actually wrote.
"""
from __future__ import annotations

from sqlalchemy import Engine, event, select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionRuleSet,
    User,
)
from app.services import assignments
from app.services.assignments._self_review import (
    verify_self_review_classification,
)
from app.services.instruments import ensure_default_instrument


def _seed(db: Session) -> tuple[User, ReviewSession]:
    """Two reviewers x two reviewees under a Full-Matrix rule, one of
    whose four pairs is a self-review (Alice reviews Alice)."""
    user = User(email="op@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="Spring",
        code="bulk-insert",
        created_by_user_id=user.id,
        self_reviews_active=True,
    )
    db.add(review_session)
    db.flush()
    db.add_all(
        [
            Reviewer(
                session_id=review_session.id,
                name="Alice",
                email="alice@example.edu",
            ),
            Reviewer(
                session_id=review_session.id,
                name="Bob",
                email="bob@example.edu",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Alice",
                email_or_identifier="alice@example.edu",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Carol",
                email_or_identifier="carol@example.edu",
            ),
        ]
    )
    db.flush()
    full_matrix = SessionRuleSet(
        session_id=review_session.id,
        name="Full Matrix",
        description="",
        combinator="ALL_OF",
        exclude_self_reviews=False,
        seed=None,
        rules_json=[],
    )
    db.add(full_matrix)
    db.flush()
    instrument = ensure_default_instrument(db, review_session)
    instrument.rule_set_id = full_matrix.id
    db.flush()
    return user, review_session


def _stored_flags(db: Session, session_id: int) -> dict[int, bool]:
    """``{assignment id: stored is_self_review}`` read as column
    tuples, so the values come from the row rather than from any
    entity the unit of work happens to be holding."""
    return {
        row_id: bool(flag)
        for row_id, flag in db.execute(
            select(Assignment.id, Assignment.is_self_review).where(
                Assignment.session_id == session_id
            )
        ).all()
    }


def test_inserted_rows_are_visible_to_the_self_review_passes(
    db: Session,
) -> None:
    """Every pair the diff inserts is visible, through the flush, to
    the recompute that runs one line later: the self-review pair's
    stored flag reads ``True`` and no row is left in drift.

    This is the property the Core insert has to preserve. Mutation
    check (19S Item 3, ``docs/unenforced_conventions.md`` 1.8): moving
    ``recompute_self_review_classification`` above the insert in
    ``_materialise_one_instrument`` leaves the new row at the column's
    ``default=False`` and fails the flag assertion below.
    """
    user, review_session = _seed(db)

    assignments.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        correlation_id="corr-visible",
    )

    flags = _stored_flags(db, review_session.id)
    assert len(flags) == 4, "every reviewer x reviewee pair got a row"
    assert sorted(flags.values()) == [False, False, False, True], (
        "the recompute saw the freshly inserted rows and flagged "
        "Alice-reviews-Alice"
    )
    assert verify_self_review_classification(
        db, session_id=review_session.id
    ) == []


def test_regenerate_with_nothing_to_insert_issues_no_insert(
    db: Session, engine: Engine
) -> None:
    """An empty ``diff.to_insert`` issues no insert statement.

    A Core ``insert()`` handed an empty list of parameter dicts is an
    error on some dialects rather than a no-op, so the guard in front
    of it is load-bearing in a way the ``for`` loop it replaces was
    not.
    """
    user, review_session = _seed(db)
    assignments.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        correlation_id="corr-first",
    )

    statements: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def _record(conn, cursor, statement, parameters, context, many):  # type: ignore[no-untyped-def]
        statements.append(statement)

    try:
        assignments.replace_assignments(
            db,
            review_session=review_session,
            user=user,
            correlation_id="corr-second",
        )
    finally:
        event.remove(engine, "before_cursor_execute", _record)

    assert statements, "the second regenerate did run statements"
    assert not [
        s
        for s in statements
        if "INSERT INTO assignments" in s.replace("\n", " ")
    ], "a no-op reconcile writes no assignment rows"


def test_core_inserted_row_starts_false_then_is_recomputed(
    db: Session,
) -> None:
    """``is_self_review`` is omitted at the insert site, so the row
    lands on the column's Python-side ``default=False`` and the
    recompute is what raises it.

    Pinned because the two Core insert forms differ here: passing a
    list of dicts as executemany parameters applies Python-side column
    defaults, and a row written without them would violate the
    column's ``nullable=False``. Asserted by regenerating with the
    self-review pair excluded, so the three rows the rule does emit
    are ones the recompute has no reason to raise.
    """
    user, review_session = _seed(db)

    assignments.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        correlation_id="corr-no-self",
        override_exclude_self_reviews=True,
    )

    flags = _stored_flags(db, review_session.id)
    assert len(flags) == 3, "the self-review pair is excluded by the rule"
    assert set(flags.values()) == {False}, (
        "every row carries the column default, written rather than NULL"
    )
