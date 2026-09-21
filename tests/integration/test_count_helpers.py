"""The count helpers count instead of fetching (19R Item 1 rung 1).

Five helpers answered *how many rows* with
``len(db.execute(select(Model.id)).all())`` — every id on the wire for
one integer, which `guide/app_responsiveness.md` measured at 1.17 s of
the Setup reviewers page's 2.4 s on a 200,000-row session.

Each test compares the helper against **the shape it replaced**, rather
than against a hand-counted number: an oracle that cannot drift as the
fixture grows, and the only form that can catch a conversion which
quietly changed the predicate rather than the aggregate. For
``count_pairs`` — the one conversion with joins under it — the oracle is
``list_pairs`` with the same filters, which is an independent
implementation rather than a restatement of the same SQL.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    Observer,
    Relationship,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services import csv_imports, relationships as relationships_service
from app.services.assignments import _coverage


def _old_count(db: Session, model, session_id: int) -> int:
    """The literal shape the helpers used before this rung."""
    stmt = select(model.id).where(model.session_id == session_id)
    return len(db.execute(stmt).all())


def _populate(db: Session, session: ReviewSession, *, reviewers: int) -> None:
    """A second session's worth of rows, so a helper that loses its
    ``session_id`` predicate counts too many instead of the same."""
    instrument = Instrument(
        session_id=session.id, name="Other", order=0, session_seq=1
    )
    db.add(instrument)
    db.flush()
    for n in range(reviewers):
        reviewer = Reviewer(
            session_id=session.id,
            name=f"Other {n}",
            email=f"other{n}@example.edu",
            status="active",
        )
        reviewee = Reviewee(
            session_id=session.id,
            name=f"Other {n}",
            email_or_identifier=f"othere{n}@example.edu",
            status="active",
        )
        db.add(Observer(
            session_id=session.id,
            email=f"othero{n}@example.edu",
            status="active",
        ))
        db.add_all([reviewer, reviewee])
        db.flush()
        db.add(Relationship(
            session_id=session.id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
            status="active",
        ))
        db.add(Assignment(
            session_id=session.id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
            instrument_id=instrument.id,
            include=True,
            created_by_mode="rule_based",
        ))
    db.flush()


@pytest.fixture
def decoy(db: Session) -> ReviewSession:
    """A populated neighbour. Every count below is scoped to one
    session; without a second one in the table, dropping that scope
    would change no answer and the assertions would prove nothing."""
    user = User(email="d@example.edu", display_name="D")
    db.add(user)
    db.flush()
    other = ReviewSession(
        name="Decoy", code="CNT9", status="draft", created_by_user_id=user.id
    )
    db.add(other)
    db.flush()
    _populate(db, other, reviewers=5)
    return other


@pytest.fixture
def seeded(db: Session, decoy: ReviewSession) -> ReviewSession:
    """Two instruments, three reviewers, two reviewees, and a pair set
    with one inactive row so the ``status`` filter has something to cut.
    """
    user = User(email="c@example.edu", display_name="C")
    db.add(user)
    db.flush()
    session = ReviewSession(
        name="Counts", code="CNT1", status="draft", created_by_user_id=user.id
    )
    db.add(session)
    db.flush()

    reviewers = [
        Reviewer(
            session_id=session.id,
            name=name,
            email=f"{name.lower()}@example.edu",
            status="active",
        )
        for name in ("Ana", "Bo", "Cy")
    ]
    reviewees = [
        Reviewee(
            session_id=session.id,
            name=name,
            email_or_identifier=f"{name.lower()}@example.edu",
            status="active",
        )
        for name in ("Dev", "Eli")
    ]
    instruments = [
        Instrument(session_id=session.id, name=f"I{n}", order=n, session_seq=n + 1)
        for n in range(2)
    ]
    observers = [
        Observer(
            session_id=session.id, email=f"obs{n}@example.edu", status="active"
        )
        for n in range(4)
    ]
    db.add_all([*reviewers, *reviewees, *instruments, *observers])
    db.flush()

    db.add_all(
        [
            Relationship(
                session_id=session.id,
                reviewer_id=reviewers[0].id,
                reviewee_id=reviewees[0].id,
                status="active",
            ),
            Relationship(
                session_id=session.id,
                reviewer_id=reviewers[1].id,
                reviewee_id=reviewees[1].id,
                status="active",
            ),
        ]
    )
    for index, reviewer in enumerate(reviewers):
        for instrument in instruments:
            db.add(
                Assignment(
                    session_id=session.id,
                    reviewer_id=reviewer.id,
                    reviewee_id=reviewees[index % len(reviewees)].id,
                    instrument_id=instrument.id,
                    include=index != 2,
                    created_by_mode="rule_based",
                )
            )
    db.flush()
    return session


def test_roster_counts_match_the_shape_they_replaced(
    db: Session, seeded: ReviewSession, decoy: ReviewSession
) -> None:
    for model in (Reviewer, Reviewee, Observer):
        assert csv_imports._count(db, model, seeded.id) == _old_count(
            db, model, seeded.id
        )
    assert csv_imports._count(db, Reviewer, seeded.id) == 3
    assert csv_imports._count(db, Observer, seeded.id) == 4
    # The decoy's rows are not in any of them.
    assert csv_imports._count(db, Reviewer, decoy.id) == 5


def test_assignment_and_relationship_counts_match(
    db: Session, seeded: ReviewSession
) -> None:
    assert csv_imports._count_assignments(db, seeded.id) == _old_count(
        db, Assignment, seeded.id
    )
    assert relationships_service.existing_count(db, seeded.id) == _old_count(
        db, Relationship, seeded.id
    )
    assert _coverage.existing_count(db, seeded.id) == _old_count(
        db, Assignment, seeded.id
    )


def test_existing_count_still_scopes_to_one_instrument(
    db: Session, seeded: ReviewSession
) -> None:
    instruments = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == seeded.id)
        ).scalars()
    )
    per_instrument = [
        _coverage.existing_count(db, seeded.id, instrument_id=instrument.id)
        for instrument in instruments
    ]
    # The scoped counts partition the unscoped one — an aggregate that
    # dropped the `instrument_id` predicate would return the total twice.
    assert sum(per_instrument) == _coverage.existing_count(db, seeded.id)
    assert per_instrument == [3, 3]


@pytest.mark.parametrize(
    "filters",
    [
        {},
        {"status": "active"},
        {"status": "inactive"},
        {"search": "Ana"},
        {"search": "Ana", "search_by": "reviewer"},
        {"search": "Ana", "search_by": "reviewee"},
        {"search": "Dev", "search_by": "reviewee"},
        {"search": "nobody-by-this-name"},
    ],
)
def test_count_pairs_agrees_with_the_rows_it_counts(
    db: Session, seeded: ReviewSession, filters: dict[str, str]
) -> None:
    """``count_pairs`` against ``list_pairs`` — the same filters, an
    independent implementation, and the join-carrying conversion."""
    counted = _coverage.count_pairs(db, seeded.id, **filters)
    listed = _coverage.list_pairs(db, seeded.id, limit=1000, **filters)
    assert counted == len(listed)


def test_count_pairs_sees_the_search_narrow(
    db: Session, seeded: ReviewSession
) -> None:
    """The same hazard as the status guard below, on the search path:
    two of the parametrised cases above are ``0 == 0``, and a
    ``_apply_pair_search`` that matched *nothing* would satisfy every
    one of them. Pin a search that must narrow without emptying."""
    everything = _coverage.count_pairs(db, seeded.id)
    ana = _coverage.count_pairs(db, seeded.id, search="Ana")
    # Ana reviews one reviewee, on both instruments.
    assert ana == 2
    assert 0 < ana < everything


def test_count_pairs_sees_the_status_split(
    db: Session, seeded: ReviewSession
) -> None:
    """A guard the parametrised comparison cannot give: both sides could
    agree on zero if the filter silently matched nothing."""
    active = _coverage.count_pairs(db, seeded.id, status="active")
    inactive = _coverage.count_pairs(db, seeded.id, status="inactive")
    assert (active, inactive) == (4, 2)
    assert active + inactive == _coverage.count_pairs(db, seeded.id)


def test_every_count_is_zero_on_an_empty_session(
    db: Session, decoy: ReviewSession
) -> None:
    """With a populated neighbour in the table, "zero" is a claim about
    the scope rather than about the database being empty."""
    user = User(email="e@example.edu", display_name="E")
    db.add(user)
    db.flush()
    empty = ReviewSession(
        name="Empty", code="CNT0", status="draft", created_by_user_id=user.id
    )
    db.add(empty)
    db.flush()

    assert csv_imports._count(db, Reviewer, empty.id) == 0
    assert csv_imports._count(db, Reviewee, empty.id) == 0
    assert csv_imports._count(db, Observer, empty.id) == 0
    assert csv_imports._count_assignments(db, empty.id) == 0
    assert relationships_service.existing_count(db, empty.id) == 0
    assert _coverage.existing_count(db, empty.id) == 0
    assert _coverage.count_pairs(db, empty.id) == 0
