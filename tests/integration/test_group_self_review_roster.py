"""Group self-review membership follows the roster (findings B7).

On a group-scoped instrument a Link rule can filter the reviewer's own
``(R, R)`` row out of the fan-out while keeping a group-mate. Generate
already decided membership from the roster, so the group stayed a
self-review group for ``include`` and the exclusion. The stored
``Assignment.is_self_review`` column decided it from the written rows,
so the same group read as an ordinary review: ``FALSE`` in the
responses CSV, counted as a peer review by the "exclude self" data
shapes, and out of reach of the per-instrument toggle. The author ruled
2026-10-03 that the column follows the roster too.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    AuditEvent,
    Instrument,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionRuleSet,
    User,
)
from app.services import assignments
from app.services import reviewees as reviewees_service
from app.services.instruments import ensure_default_instrument

_LINK_KEEPS_OTHER_ONLY = [
    {
        "id": "link2",
        "kind": "COMPOSITE",
        "enabled": True,
        "op": "AND",
        "rules": [
            {
                "id": "link2-r0",
                "kind": "MATCH",
                "enabled": True,
                "predicate": {
                    "field": "reviewee.tag2",
                    "operator": "equals",
                    "operand": "OTHER",
                    "case_sensitive": False,
                },
            }
        ],
    }
]


def _seed(
    db: Session, *, self_reviews_active: bool, with_own_row: bool = True
) -> tuple[User, ReviewSession, Instrument]:
    """Sam and Zoe share TeamA (tag_1); the instrument groups by
    tag_1. The rule keeps only tag_2 == OTHER, so Sam's own reviewee
    row (tag_2 == SELF) is filtered out and Zoe's survives. The rule
    set's own exclusion is off."""
    user = User(email="op-b7@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="B7",
        code="b7",
        created_by_user_id=user.id,
        self_reviews_active=self_reviews_active,
    )
    db.add(review_session)
    db.flush()
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Sam",
            email="sam@example.edu",
        )
    )
    if with_own_row:
        db.add(
            Reviewee(
                session_id=review_session.id,
                name="Sam",
                email_or_identifier="Sam@Example.edu",
                tag_1="TeamA",
                tag_2="SELF",
            )
        )
    db.add_all(
        [
            Reviewee(
                session_id=review_session.id,
                name="Zoe",
                email_or_identifier="zoe@example.edu",
                tag_1="TeamA",
                tag_2="OTHER",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Kit",
                email_or_identifier="kit@example.edu",
                tag_1="TeamB",
                tag_2="OTHER",
            ),
        ]
    )
    db.flush()
    instrument = ensure_default_instrument(db, review_session)
    rule_set = SessionRuleSet(
        session_id=review_session.id,
        name="Link",
        description="",
        combinator="ALL_OF",
        exclude_self_reviews=False,
        seed=None,
        rules_json=_LINK_KEEPS_OTHER_ONLY,
    )
    db.add(rule_set)
    db.flush()
    instrument.rule_set_id = rule_set.id
    instrument.group_kind = "r1"
    db.flush()
    return user, review_session, instrument


def _rows_by_reviewee(db: Session, instrument: Instrument) -> dict[str, Assignment]:
    rows = db.execute(
        select(Assignment, Reviewee)
        .join(Reviewee, Reviewee.id == Assignment.reviewee_id)
        .where(Assignment.instrument_id == instrument.id)
    ).all()
    return {reviewee.name: assignment for assignment, reviewee in rows}


def test_own_group_is_flagged_when_the_self_row_is_filtered(db: Session) -> None:
    user, review_session, instrument = _seed(db, self_reviews_active=True)
    assignments.replace_assignments(
        db, review_session=review_session, user=user, correlation_id="b7"
    )
    rows = _rows_by_reviewee(db, instrument)
    assert "Sam" not in rows, "the Link rule should filter Sam's own row"
    assert rows["Zoe"].is_self_review is True, (
        "Sam is on TeamA's roster, so reviewing TeamA through Zoe is a "
        "self-review even though his own row was filtered out"
    )
    assert rows["Kit"].is_self_review is False


def test_flag_and_include_agree_when_self_reviews_are_off(db: Session) -> None:
    """With self-reviews off, Generate writes the row ``include=False``;
    the flag now says why, and the instrument toggle can reach it."""
    user, review_session, instrument = _seed(db, self_reviews_active=False)
    assignments.replace_assignments(
        db, review_session=review_session, user=user, correlation_id="b7"
    )
    zoe = _rows_by_reviewee(db, instrument)["Zoe"]
    assert zoe.include is False
    assert zoe.is_self_review is True

    assignments.set_instrument_self_reviews_active(
        db,
        review_session=review_session,
        instrument_id=instrument.id,
        user=user,
        active=True,
        correlation_id="b7-toggle",
    )
    db.refresh(zoe)
    assert zoe.include is True, (
        "the per-instrument toggle reads the flag; before B7 it skipped "
        "this row and left it off with no control to turn it back on"
    )


def test_moving_the_reviewer_to_another_team_moves_the_flag(
    db: Session,
) -> None:
    """Editing Sam's own reviewee row moves his membership without a
    regenerate: TeamA stops being his group and TeamB becomes it."""
    user, review_session, instrument = _seed(db, self_reviews_active=True)
    assignments.replace_assignments(
        db, review_session=review_session, user=user, correlation_id="b7"
    )
    sam_own = db.execute(
        select(Reviewee).where(Reviewee.name == "Sam")
    ).scalar_one()
    reviewees_service.update_reviewee(
        db, reviewee=sam_own, tag_1="TeamB", user=user
    )
    rows = _rows_by_reviewee(db, instrument)
    assert rows["Zoe"].is_self_review is False
    assert rows["Kit"].is_self_review is True


def test_adding_the_reviewers_own_row_flags_existing_rows(
    db: Session,
) -> None:
    """A reviewee added after Generate that shares the reviewer's email
    puts him in a group; the rows already written are flagged."""
    user, review_session, instrument = _seed(
        db, self_reviews_active=True, with_own_row=False
    )
    assignments.replace_assignments(
        db, review_session=review_session, user=user, correlation_id="b7"
    )
    assert _rows_by_reviewee(db, instrument)["Zoe"].is_self_review is False
    reviewees_service.create_reviewee(
        db,
        review_session=review_session,
        name="Sam",
        email_or_identifier="sam@example.edu",
        tag_1="TeamA",
        tag_2="SELF",
        user=user,
    )
    assert _rows_by_reviewee(db, instrument)["Zoe"].is_self_review is True


def test_deleting_the_reviewers_own_row_clears_the_flag(
    db: Session,
) -> None:
    user, review_session, instrument = _seed(db, self_reviews_active=True)
    assignments.replace_assignments(
        db, review_session=review_session, user=user, correlation_id="b7"
    )
    sam_own = db.execute(
        select(Reviewee).where(Reviewee.name == "Sam")
    ).scalar_one()
    reviewees_service.delete_selected(
        db, review_session=review_session, reviewee_ids=[sam_own.id], user=user
    )
    assert _rows_by_reviewee(db, instrument)["Zoe"].is_self_review is False


def test_a_row_that_stops_being_a_self_review_is_included_again(
    db: Session,
) -> None:
    """Codex on #2765: with self-reviews off, Zoe's row is written
    ``include=False`` as a self-review. Deleting Sam's own reviewee row
    makes it an ordinary review, which must come back on: the toggle
    reads the flag and could no longer reach it."""
    user, review_session, instrument = _seed(db, self_reviews_active=False)
    assignments.replace_assignments(
        db, review_session=review_session, user=user, correlation_id="b7"
    )
    assert _rows_by_reviewee(db, instrument)["Zoe"].include is False
    sam_own = db.execute(
        select(Reviewee).where(Reviewee.name == "Sam")
    ).scalar_one()
    reviewees_service.delete_selected(
        db, review_session=review_session, reviewee_ids=[sam_own.id], user=user
    )
    zoe = _rows_by_reviewee(db, instrument)["Zoe"]
    assert zoe.is_self_review is False
    assert zoe.include is True


def test_a_row_that_becomes_a_self_review_follows_the_session_setting(
    db: Session,
) -> None:
    """The inverse: adding Sam's own row after Generate makes Zoe's row
    a self-review, so with self-reviews off it is excluded, as Generate
    would have written it."""
    user, review_session, instrument = _seed(
        db, self_reviews_active=False, with_own_row=False
    )
    assignments.replace_assignments(
        db, review_session=review_session, user=user, correlation_id="b7"
    )
    assert _rows_by_reviewee(db, instrument)["Zoe"].include is True
    reviewees_service.create_reviewee(
        db,
        review_session=review_session,
        name="Sam",
        email_or_identifier="sam@example.edu",
        tag_1="TeamA",
        tag_2="SELF",
        user=user,
    )
    zoe = _rows_by_reviewee(db, instrument)["Zoe"]
    assert zoe.is_self_review is True
    assert zoe.include is False


def test_an_inactive_side_keeps_a_reclassified_row_off(db: Session) -> None:
    """Findings B2: a row with an inactive reviewer or reviewee is never
    assigned work, so stopping being a self-review does not switch it
    back on."""
    user, review_session, instrument = _seed(db, self_reviews_active=False)
    assignments.replace_assignments(
        db, review_session=review_session, user=user, correlation_id="b7"
    )
    zoe_e = db.execute(
        select(Reviewee).where(Reviewee.name == "Zoe")
    ).scalar_one()
    reviewees_service.update_reviewee(
        db, reviewee=zoe_e, status="inactive", user=user
    )
    sam_own = db.execute(
        select(Reviewee).where(Reviewee.name == "Sam")
    ).scalar_one()
    reviewees_service.delete_selected(
        db, review_session=review_session, reviewee_ids=[sam_own.id], user=user
    )
    zoe = _rows_by_reviewee(db, instrument)["Zoe"]
    assert zoe.is_self_review is False
    assert zoe.include is False


def test_an_include_change_is_audited(db: Session) -> None:
    user, review_session, instrument = _seed(db, self_reviews_active=False)
    assignments.replace_assignments(
        db, review_session=review_session, user=user, correlation_id="b7"
    )
    sam_own = db.execute(
        select(Reviewee).where(Reviewee.name == "Sam")
    ).scalar_one()
    reviewees_service.delete_selected(
        db, review_session=review_session, reviewee_ids=[sam_own.id], user=user
    )
    events = db.execute(
        select(AuditEvent).where(
            AuditEvent.session_id == review_session.id,
            AuditEvent.event_type == "assignments.include_reconciled",
        )
    ).scalars().all()
    assert len(events) == 1
    assert events[0].detail["counts"]["include_changed"] == 1

