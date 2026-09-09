"""Selection-driven roster delete — Segment 19I Item 2 PR 2.

The service half: `delete_selected` on each of the four roster
services, all of them thin callers of `roster_bulk.bulk_delete`.
Nothing calls them yet — the route lands in PR 3 — so these are the
only exercise this code gets.

Two claims here are load-bearing beyond "it deletes":

- **The cascade is inherited, not reimplemented.** Deleting a reviewer
  takes its assignments and their responses through the ORM's
  `delete-orphan`, exactly as `delete_all_reviewers` does.
- **Observers and Relationships carry no cascade at all**, which is
  what answers the item's open question about whether Relationships
  needs a response-loss gate. Asserted from behaviour rather than read
  off the model file.
"""
from __future__ import annotations

import datetime as _dt

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    AuditEvent,
    Instrument,
    InstrumentResponseField,
    Observer,
    Relationship,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services import observers as observers_service
from app.services import relationships as relationships_service
from app.services import reviewees as reviewees_service
from app.services import reviewers as reviewers_service
from app.services import roster_bulk


def _session(db: Session, *, code: str) -> tuple[ReviewSession, User]:
    user = User(email=f"op-{code}@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="Spring", code=code, created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    return review_session, user


def _reviewers(db: Session, s: ReviewSession, n: int) -> list[Reviewer]:
    rows = [
        Reviewer(session_id=s.id, name=f"R{i}", email=f"r{i}-{s.code}@example.edu")
        for i in range(n)
    ]
    db.add_all(rows)
    db.flush()
    return rows


def _reviewees(db: Session, s: ReviewSession, n: int) -> list[Reviewee]:
    rows = [
        Reviewee(
            session_id=s.id,
            name=f"E{i}",
            email_or_identifier=f"e{i}-{s.code}@example.edu",
        )
        for i in range(n)
    ]
    db.add_all(rows)
    db.flush()
    return rows


def _assignment_with_responses(
    db: Session,
    s: ReviewSession,
    *,
    reviewer: Reviewer,
    reviewee: Reviewee,
    responses: int,
) -> Assignment:
    instrument = Instrument(
        session_id=s.id, name=f"I-{reviewer.id}-{reviewee.id}", order=0
    )
    db.add(instrument)
    db.flush()
    # One field per response: `responses` is unique on
    # (assignment_id, response_field_id), so N answers means N fields.
    fields = [
        InstrumentResponseField(
            instrument_id=instrument.id,
            field_key=f"rating_{i}",
            label=f"Rating {i}",
            _inline_data_type="Integer",
            _inline_response_type="Likert5",
            order=i,
        )
        for i in range(responses)
    ]
    db.add_all(fields)
    assignment = Assignment(
        session_id=s.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        instrument_id=instrument.id,
        include=True,
        created_by_mode="manual",
    )
    db.add(assignment)
    db.flush()
    for i, field in enumerate(fields):
        db.add(
            Response(
                assignment_id=assignment.id,
                response_field_id=field.id,
                value=str(i),
                saved_at=_dt.datetime(2026, 9, 9, tzinfo=_dt.timezone.utc),
                version=1,
            )
        )
    db.flush()
    return assignment


# ── The basic act ──────────────────────────────────────────────────────


def test_only_the_selected_rows_go(db: Session) -> None:
    s, user = _session(db, code="bd-basic")
    rows = _reviewers(db, s, 4)
    db.commit()

    deleted, _a, _r = reviewers_service.delete_selected(
        db,
        review_session=s,
        reviewer_ids=[rows[0].id, rows[2].id],
        user=user,
    )

    assert deleted == 2
    left = db.execute(
        select(Reviewer.name).where(Reviewer.session_id == s.id)
    ).scalars()
    assert sorted(left) == ["R1", "R3"]


def test_an_empty_selection_is_a_no_op(db: Session) -> None:
    s, user = _session(db, code="bd-empty")
    _reviewers(db, s, 2)
    db.commit()

    assert reviewers_service.delete_selected(
        db, review_session=s, reviewer_ids=[], user=user
    ) == (0, 0, 0)
    assert db.execute(
        select(Reviewer).where(Reviewer.session_id == s.id)
    ).scalars().all()


def test_an_id_from_another_session_is_refused_and_nothing_is_deleted(
    db: Session,
) -> None:
    """`bulk_set_status` raises rather than skipping, and a delete has
    the stronger case for it: a silently skipped id is a row the
    operator asked to remove that is still there, unremarked."""
    mine, user = _session(db, code="bd-mine")
    theirs, _ = _session(db, code="bd-theirs")
    ours = _reviewers(db, mine, 2)
    stranger = _reviewers(db, theirs, 1)[0]
    db.commit()

    with pytest.raises(reviewers_service.ReviewerOperationError) as excinfo:
        reviewers_service.delete_selected(
            db,
            review_session=mine,
            reviewer_ids=[ours[0].id, stranger.id],
            user=user,
        )

    assert excinfo.value.code == "not_in_session"
    # No rollback here on purpose: the refusal happens *before* any
    # `db.delete`, so an intact roster is the claim. Rolling back
    # first would make the assertion true whatever the code did.
    assert len(
        db.execute(select(Reviewer).where(Reviewer.session_id == mine.id))
        .scalars()
        .all()
    ) == 2, "the valid id in the same call must not have been deleted"


# ── The cascade ────────────────────────────────────────────────────────


def test_deleting_a_reviewer_takes_its_assignments_and_responses(
    db: Session,
) -> None:
    s, user = _session(db, code="bd-cascade")
    reviewer, spared = _reviewers(db, s, 2)
    reviewee = _reviewees(db, s, 1)[0]
    doomed = _assignment_with_responses(
        db, s, reviewer=reviewer, reviewee=reviewee, responses=3
    )
    kept = _assignment_with_responses(
        db, s, reviewer=spared, reviewee=reviewee, responses=2
    )
    db.commit()

    deleted, assignments, responses = reviewers_service.delete_selected(
        db, review_session=s, reviewer_ids=[reviewer.id], user=user
    )

    assert (deleted, assignments, responses) == (1, 1, 3)
    remaining = db.execute(select(Assignment.id)).scalars().all()
    assert remaining == [kept.id], "only the spared reviewer's assignment"
    assert (
        db.execute(
            select(Response).where(Response.assignment_id == doomed.id)
        ).scalars().all()
        == []
    )
    assert (
        len(
            db.execute(
                select(Response).where(Response.assignment_id == kept.id)
            ).scalars().all()
        )
        == 2
    )


def test_the_counts_are_for_the_selected_rows_not_the_session(
    db: Session,
) -> None:
    """`delete_all` can only say how many assignments the session has;
    this knows which rows are going. The session has 3 assignments and
    5 responses; deleting one reviewer must report 1 and 3."""
    s, user = _session(db, code="bd-exact")
    reviewer, other = _reviewers(db, s, 2)
    a, b = _reviewees(db, s, 2)
    _assignment_with_responses(db, s, reviewer=reviewer, reviewee=a, responses=3)
    _assignment_with_responses(db, s, reviewer=other, reviewee=a, responses=1)
    _assignment_with_responses(db, s, reviewer=other, reviewee=b, responses=1)
    db.commit()

    _d, assignments, responses = reviewers_service.delete_selected(
        db, review_session=s, reviewer_ids=[reviewer.id], user=user
    )

    assert (assignments, responses) == (1, 3)


def test_deleting_a_reviewee_cascades_the_same_way(db: Session) -> None:
    s, user = _session(db, code="bd-reviewee")
    reviewer = _reviewers(db, s, 1)[0]
    reviewee = _reviewees(db, s, 1)[0]
    _assignment_with_responses(
        db, s, reviewer=reviewer, reviewee=reviewee, responses=2
    )
    db.commit()

    assert reviewees_service.delete_selected(
        db, review_session=s, reviewee_ids=[reviewee.id], user=user
    ) == (1, 1, 2)
    assert db.execute(select(Assignment)).scalars().all() == []


def test_observers_and_relationships_destroy_no_responses(
    db: Session,
) -> None:
    """This is what answers the item's open question: a relationship
    row is pair context, and nothing references it or an observer, so
    neither delete can lose a response. The gate PR 3 puts on
    Reviewers / Reviewees is therefore not needed on these two."""
    s, user = _session(db, code="bd-noresp")
    reviewer = _reviewers(db, s, 1)[0]
    reviewee = _reviewees(db, s, 1)[0]
    kept = _assignment_with_responses(
        db, s, reviewer=reviewer, reviewee=reviewee, responses=4
    )
    observer = Observer(
        session_id=s.id, email="o@example.edu", display_name="Obs"
    )
    pair = Relationship(
        session_id=s.id, reviewer_id=reviewer.id, reviewee_id=reviewee.id
    )
    db.add_all([observer, pair])
    db.commit()

    assert observers_service.delete_selected(
        db, review_session=s, observer_ids=[observer.id], user=user
    ) == (1, 0, 0)
    assert relationships_service.delete_selected(
        db, review_session=s, relationship_ids=[pair.id], user=user
    ) == (1, 0, 0)

    # The assignment and every response it carries are untouched.
    assert db.execute(select(Assignment.id)).scalars().all() == [kept.id]
    assert (
        len(db.execute(select(Response)).scalars().all()) == 4
    ), "a pair-context delete must not reach a response"


def test_cascade_counts_reports_nothing_for_unreferenced_models(
    db: Session,
) -> None:
    """The helper directly, since a wrong `(0, 0)` here would make the
    confirmation understate what a delete costs."""
    s, _user = _session(db, code="bd-counts")
    reviewer = _reviewers(db, s, 1)[0]
    reviewee = _reviewees(db, s, 1)[0]
    _assignment_with_responses(
        db, s, reviewer=reviewer, reviewee=reviewee, responses=2
    )
    db.commit()

    assert roster_bulk.cascade_counts(
        db, model=Reviewer, ids=[reviewer.id]
    ) == (1, 2)
    assert roster_bulk.cascade_counts(
        db, model=Observer, ids=[1, 2, 3]
    ) == (0, 0)
    assert roster_bulk.cascade_counts(
        db, model=Relationship, ids=[1]
    ) == (0, 0)
    assert roster_bulk.cascade_counts(db, model=Reviewer, ids=[]) == (0, 0)


# ── Audit + lifecycle ──────────────────────────────────────────────────


def test_one_audit_event_carries_the_three_counts(db: Session) -> None:
    """**Two** rows deleted, deliberately: with one row, "one event
    per call" and "one event per row" are the same number, and the
    assertion pins nothing."""
    s, user = _session(db, code="bd-audit")
    first, second = _reviewers(db, s, 2)
    reviewee = _reviewees(db, s, 1)[0]
    _assignment_with_responses(
        db, s, reviewer=first, reviewee=reviewee, responses=2
    )
    _assignment_with_responses(
        db, s, reviewer=second, reviewee=reviewee, responses=3
    )
    db.commit()

    reviewers_service.delete_selected(
        db, review_session=s, reviewer_ids=[first.id, second.id], user=user
    )

    events = [
        e
        for e in db.execute(
            select(AuditEvent).where(AuditEvent.session_id == s.id)
        ).scalars()
        if e.event_type == "reviewer.bulk_deleted"
    ]
    assert len(events) == 1, "one event per call, not one per row"
    assert events[0].detail["counts"] == {
        "deleted": 2,
        "cascaded_assignments": 2,
        "cascaded_responses": 5,
    }, "counts are summed across the selection, not the last row's"


@pytest.mark.parametrize(
    "service, kwarg, event_type",
    [
        (reviewers_service, "reviewer_ids", "reviewer.bulk_deleted"),
        (reviewees_service, "reviewee_ids", "reviewee.bulk_deleted"),
        (observers_service, "observer_ids", "observer.bulk_deleted"),
        (relationships_service, "relationship_ids", "relationship.bulk_deleted"),
    ],
)
def test_every_roster_service_emits_its_registered_event(
    db: Session, service, kwarg: str, event_type: str
) -> None:
    """Strict-mode audit validation runs in tests, so an unregistered
    `event_type` fails on write rather than here — this pins that all
    four emit, and emit their own."""
    s, user = _session(db, code=f"bd-ev-{kwarg}")
    reviewer = _reviewers(db, s, 1)[0]
    reviewee = _reviewees(db, s, 1)[0]
    row = {
        "reviewer_ids": reviewer,
        "reviewee_ids": reviewee,
        "observer_ids": Observer(
            session_id=s.id, email="o@example.edu", display_name="O"
        ),
        "relationship_ids": Relationship(
            session_id=s.id, reviewer_id=reviewer.id, reviewee_id=reviewee.id
        ),
    }[kwarg]
    if kwarg in ("observer_ids", "relationship_ids"):
        db.add(row)
    db.commit()

    service.delete_selected(
        db, review_session=s, user=user, **{kwarg: [row.id]}
    )

    kinds = [
        e.event_type
        for e in db.execute(
            select(AuditEvent).where(AuditEvent.session_id == s.id)
        ).scalars()
    ]
    assert event_type in kinds


def test_a_validated_session_is_invalidated(db: Session) -> None:
    s, user = _session(db, code="bd-lifecycle")
    rows = _reviewers(db, s, 2)
    s.status = "validated"
    db.commit()

    reviewers_service.delete_selected(
        db, review_session=s, reviewer_ids=[rows[0].id], user=user
    )

    db.refresh(s)
    assert s.status == "draft"
