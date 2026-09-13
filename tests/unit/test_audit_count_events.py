"""``audit.count_events_for_session`` — the audit-log row count.

`NF-25`. The audit-log CSV route composed this count inline: two
branches assembling a `SELECT count()`, differing only in whether
to LEFT JOIN ``users``, both then calling ``audit._apply_filters``
— **a private helper of another module** — and executing the
result itself.

That made the route the only place the count's correctness was
expressed, while the set it was supposed to be counting is
defined by ``_apply_filters`` and paged by
``list_events_for_session``. These tests pin the property that
actually matters: **the count matches what the reader returns**,
under every filter shape including the actor filter that drove
the join branch.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.services import audit


def _session_with_events(db: Session, code: str) -> tuple[User, User, ReviewSession]:
    alice = User(email=f"alice-{code}@example.edu", display_name="Alice")
    bob = User(email=f"bob-{code}@example.edu", display_name="Bob")
    db.add_all([alice, bob])
    db.flush()
    review_session = ReviewSession(
        name=code.title(), code=code, created_by_user_id=alice.id
    )
    db.add(review_session)
    db.flush()
    for actor, event_type in (
        (alice, "session.tag_added"),
        (alice, "session.tag_added"),
        (alice, "session.tag_removed"),
        (bob, "session.tag_added"),
    ):
        audit.write_event(
            db,
            event_type=event_type,
            summary=f"{event_type} by {actor.email}",
            actor_user_id=actor.id,
            session=review_session,
            context={"tag": "t"},
        )
    db.flush()
    return alice, bob, review_session


def _reader_count(db: Session, review_session, filters) -> int:
    return len(
        audit.list_events_for_session(
            db, review_session, limit=1000, filters=filters
        )
    )


def test_unfiltered_count_matches_the_reader(db: Session) -> None:
    _, _, review_session = _session_with_events(db, "cnt-plain")
    filters = audit.AuditFilters()

    assert audit.count_events_for_session(
        db, review_session, filters=filters
    ) == _reader_count(db, review_session, filters)


def test_event_type_filter_counts_the_same_set_the_reader_pages(
    db: Session,
) -> None:
    _, _, review_session = _session_with_events(db, "cnt-type")
    filters = audit.AuditFilters(event_types=("session.tag_added",))

    counted = audit.count_events_for_session(
        db, review_session, filters=filters
    )
    assert counted == _reader_count(db, review_session, filters)
    assert counted == 3


def test_actor_filter_takes_the_join_branch_and_still_agrees(
    db: Session,
) -> None:
    """The branch the route split by hand. An actor filter needs
    the LEFT JOIN on ``users`` for a column to match against;
    everything else must not pay for it."""
    _, bob, review_session = _session_with_events(db, "cnt-actor")
    filters = audit.AuditFilters(actor_email=bob.email)

    counted = audit.count_events_for_session(
        db, review_session, filters=filters
    )
    assert counted == _reader_count(db, review_session, filters)
    assert counted == 1


def test_actor_filter_is_case_insensitive(db: Session) -> None:
    _, bob, review_session = _session_with_events(db, "cnt-case")
    filters = audit.AuditFilters(actor_email=bob.email.upper())

    assert (
        audit.count_events_for_session(db, review_session, filters=filters)
        == 1
    )


def test_count_is_scoped_to_its_own_session(db: Session) -> None:
    _, _, mine = _session_with_events(db, "cnt-mine")
    _session_with_events(db, "cnt-theirs")
    filters = audit.AuditFilters()

    assert audit.count_events_for_session(
        db, mine, filters=filters
    ) == _reader_count(db, mine, filters)


def test_none_filters_counts_everything(db: Session) -> None:
    """The route always passed a parsed filter set, but the
    signature admits ``None`` the way the reader's does."""
    _, _, review_session = _session_with_events(db, "cnt-none")

    assert (
        audit.count_events_for_session(db, review_session, filters=None)
        == _reader_count(db, review_session, None)
    )
