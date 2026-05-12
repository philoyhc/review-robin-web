"""Tests for Segment 15C Slice 2 — auto-copy operator library
entries (RTDs + Personal RuleSets) into the per-session tables
at session-create time.

Pins:

1. No-op when the operator's library is empty (the typical
   pre-15C-Slice-5 state).
2. Personal RuleSet → `session_rule_sets` row with
   `library_origin_id` set and the current revision snapshotted.
3. Operator RTD → `response_type_definitions` row with
   `library_origin_id` set, `is_seeded=False`.
4. Name collision with a seed (RuleSet "Full Matrix" / RTD
   "Long_text"): seed wins, library entry skipped.
5. Idempotency: re-running on a session that already has the
   copies is a no-op.
6. Scoping: another operator's library entries aren't copied.
7. Audit emission: `*.materialised_from_library` events fire
   exactly when their tier inserts rows.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEvent,
    OperatorResponseTypeDefinition,
    ResponseTypeDefinition,
    ReviewSession,
    RuleSet,
    RuleSetRevision,
    SessionRuleSet,
    User,
)
from app.schemas.sessions import SessionCreate
from app.services.library_materialise import materialise_operator_libraries
from app.services.sessions import create_session


def _seed_user(db: Session, *, email: str) -> User:
    user = User(email=email, is_operator=True)
    db.add(user)
    db.flush()
    return user


def _seed_library_rule_set(
    db: Session,
    *,
    owner: User,
    name: str,
    rules_json: list[dict] | None = None,
    combinator: str = "ALL_OF",
    exclude_self_reviews: bool = True,
    seed: int | None = 42,
) -> RuleSet:
    rs = RuleSet(
        name=name,
        description=f"Library entry {name}",
        scope="personal",
        owner_user_id=owner.id,
        is_seed=False,
    )
    db.add(rs)
    db.flush()
    revision = RuleSetRevision(
        rule_set_id=rs.id,
        revision_no=1,
        combinator=combinator,
        exclude_self_reviews=exclude_self_reviews,
        seed=seed,
        rules_json=rules_json or [],
        created_at=datetime.now(timezone.utc),
        created_by_user_id=owner.id,
    )
    db.add(revision)
    db.flush()
    rs.current_revision_id = revision.id
    db.flush()
    return rs


def _seed_library_rtd(
    db: Session, *, owner: User, response_type: str, data_type: str = "Integer"
) -> OperatorResponseTypeDefinition:
    rtd = OperatorResponseTypeDefinition(
        owner_user_id=owner.id,
        response_type=response_type,
        data_type=data_type,
        min=0.0,
        max=10.0,
        step=1.0,
        list_csv=None,
    )
    db.add(rtd)
    db.flush()
    return rtd


def _create_session(
    db: Session, *, user: User, code: str
) -> ReviewSession:
    payload = SessionCreate(name=f"Test {code}", code=code)
    return create_session(db, user=user, payload=payload)


def _audit_events(
    db: Session, *, session_id: int, event_type: str
) -> list[AuditEvent]:
    return list(
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.session_id == session_id)
            .where(AuditEvent.event_type == event_type)
        ).scalars()
    )


# --- Helpers themselves -----------------------------------------------------


def test_materialise_with_empty_library_is_a_noop(db: Session) -> None:
    user = _seed_user(db, email="empty@example.edu")
    review_session = _create_session(db, user=user, code="lib-empty")

    library_rule_sets = list(
        db.execute(
            select(SessionRuleSet).where(
                SessionRuleSet.session_id == review_session.id,
                SessionRuleSet.library_origin_id.is_not(None),
            )
        ).scalars()
    )
    assert library_rule_sets == []

    library_rtds = list(
        db.execute(
            select(ResponseTypeDefinition).where(
                ResponseTypeDefinition.session_id == review_session.id,
                ResponseTypeDefinition.library_origin_id.is_not(None),
            )
        ).scalars()
    )
    assert library_rtds == []

    assert (
        _audit_events(
            db,
            session_id=review_session.id,
            event_type="session_rule_sets.materialised_from_library",
        )
        == []
    )
    assert (
        _audit_events(
            db,
            session_id=review_session.id,
            event_type="response_type_definitions.materialised_from_library",
        )
        == []
    )


# --- RuleSet copy ----------------------------------------------------------


def test_personal_rule_set_copied_with_library_origin(db: Session) -> None:
    user = _seed_user(db, email="rs@example.edu")
    library_rs = _seed_library_rule_set(
        db,
        owner=user,
        name="My Custom Rule",
        combinator="ANY_OF",
        exclude_self_reviews=False,
        seed=7,
    )
    review_session = _create_session(db, user=user, code="lib-rs")

    rows = list(
        db.execute(
            select(SessionRuleSet)
            .where(SessionRuleSet.session_id == review_session.id)
            .where(SessionRuleSet.library_origin_id == library_rs.id)
        ).scalars()
    )
    assert len(rows) == 1
    copy = rows[0]
    assert copy.name == "My Custom Rule"
    assert copy.combinator == "ANY_OF"
    assert copy.exclude_self_reviews is False
    assert copy.seed == 7
    assert copy.rules_json == []

    events = _audit_events(
        db,
        session_id=review_session.id,
        event_type="session_rule_sets.materialised_from_library",
    )
    assert len(events) == 1
    assert events[0].detail["counts"]["materialised"] == 1


def test_rule_set_name_collides_with_seed_library_skipped(
    db: Session,
) -> None:
    user = _seed_user(db, email="collide@example.edu")
    library_rs = _seed_library_rule_set(
        db, owner=user, name="Full Matrix"
    )
    review_session = _create_session(db, user=user, code="lib-rs-collide")

    rows = list(
        db.execute(
            select(SessionRuleSet)
            .where(SessionRuleSet.session_id == review_session.id)
            .where(SessionRuleSet.name == "Full Matrix")
        ).scalars()
    )
    assert len(rows) == 1
    assert rows[0].library_origin_id is None  # seed won

    # The library RuleSet still exists; just wasn't copied into this
    # session because the seed already claimed the name.
    assert (
        db.execute(
            select(RuleSet).where(RuleSet.id == library_rs.id)
        ).scalar_one()
        is not None
    )


def test_rule_set_without_current_revision_is_skipped(db: Session) -> None:
    """Library RuleSets whose current_revision_id is NULL (a rare
    historical / mid-edit state) are skipped rather than raising.
    Mirrors load_rule_set's tolerance for missing revisions."""
    user = _seed_user(db, email="norev@example.edu")
    rs = RuleSet(
        name="No Revision",
        description="",
        scope="personal",
        owner_user_id=user.id,
        is_seed=False,
    )
    db.add(rs)
    db.flush()  # current_revision_id stays NULL

    review_session = _create_session(db, user=user, code="lib-norev")

    rows = list(
        db.execute(
            select(SessionRuleSet)
            .where(SessionRuleSet.session_id == review_session.id)
            .where(SessionRuleSet.name == "No Revision")
        ).scalars()
    )
    assert rows == []


# --- RTD copy --------------------------------------------------------------


def test_operator_rtd_copied_with_library_origin(db: Session) -> None:
    user = _seed_user(db, email="rtd@example.edu")
    library_rtd = _seed_library_rtd(
        db, owner=user, response_type="MyCustomGrade", data_type="Integer"
    )
    review_session = _create_session(db, user=user, code="lib-rtd")

    rows = list(
        db.execute(
            select(ResponseTypeDefinition)
            .where(ResponseTypeDefinition.session_id == review_session.id)
            .where(ResponseTypeDefinition.library_origin_id == library_rtd.id)
        ).scalars()
    )
    assert len(rows) == 1
    copy = rows[0]
    assert copy.response_type == "MyCustomGrade"
    assert copy.data_type == "Integer"
    assert copy.min == 0.0
    assert copy.max == 10.0
    assert copy.step == 1.0
    assert copy.is_seeded is False

    events = _audit_events(
        db,
        session_id=review_session.id,
        event_type="response_type_definitions.materialised_from_library",
    )
    assert len(events) == 1
    assert events[0].detail["counts"]["materialised"] == 1


def test_rtd_name_collides_with_seed_library_skipped(db: Session) -> None:
    user = _seed_user(db, email="rtd-collide@example.edu")
    _seed_library_rtd(db, owner=user, response_type="Long_text")
    review_session = _create_session(db, user=user, code="lib-rtd-collide")

    rows = list(
        db.execute(
            select(ResponseTypeDefinition)
            .where(ResponseTypeDefinition.session_id == review_session.id)
            .where(ResponseTypeDefinition.response_type == "Long_text")
        ).scalars()
    )
    assert len(rows) == 1
    assert rows[0].is_seeded is True
    assert rows[0].library_origin_id is None  # seed won


# --- Idempotency + scoping -------------------------------------------------


def test_materialise_is_idempotent(db: Session) -> None:
    user = _seed_user(db, email="idem@example.edu")
    _seed_library_rule_set(db, owner=user, name="Idem Rule")
    _seed_library_rtd(db, owner=user, response_type="IdemRtd")
    review_session = _create_session(db, user=user, code="lib-idem")

    rs_count_before = len(
        list(
            db.execute(
                select(SessionRuleSet).where(
                    SessionRuleSet.session_id == review_session.id
                )
            ).scalars()
        )
    )
    rtd_count_before = len(
        list(
            db.execute(
                select(ResponseTypeDefinition).where(
                    ResponseTypeDefinition.session_id == review_session.id
                )
            ).scalars()
        )
    )

    result = materialise_operator_libraries(
        db, review_session, owner_user=user
    )
    db.flush()

    rs_count_after = len(
        list(
            db.execute(
                select(SessionRuleSet).where(
                    SessionRuleSet.session_id == review_session.id
                )
            ).scalars()
        )
    )
    rtd_count_after = len(
        list(
            db.execute(
                select(ResponseTypeDefinition).where(
                    ResponseTypeDefinition.session_id == review_session.id
                )
            ).scalars()
        )
    )
    assert rs_count_after == rs_count_before
    assert rtd_count_after == rtd_count_before
    assert result.rtds_copied == 0
    assert result.rule_sets_copied == 0


def test_other_operators_library_not_copied(db: Session) -> None:
    alice = _seed_user(db, email="alice-15c@example.edu")
    bob = _seed_user(db, email="bob-15c@example.edu")
    _seed_library_rule_set(db, owner=bob, name="Bob's Rule")
    _seed_library_rtd(db, owner=bob, response_type="BobRtd")

    review_session = _create_session(db, user=alice, code="lib-scope")

    rows = list(
        db.execute(
            select(SessionRuleSet)
            .where(SessionRuleSet.session_id == review_session.id)
            .where(SessionRuleSet.name == "Bob's Rule")
        ).scalars()
    )
    assert rows == []

    rtds = list(
        db.execute(
            select(ResponseTypeDefinition)
            .where(ResponseTypeDefinition.session_id == review_session.id)
            .where(ResponseTypeDefinition.response_type == "BobRtd")
        ).scalars()
    )
    assert rtds == []


def test_soft_deleted_library_entries_skipped(db: Session) -> None:
    user = _seed_user(db, email="softdel@example.edu")
    rs = _seed_library_rule_set(db, owner=user, name="Soft Deleted")
    rs.deleted_at = datetime.now(timezone.utc)
    db.flush()

    review_session = _create_session(db, user=user, code="lib-softdel")

    rows = list(
        db.execute(
            select(SessionRuleSet)
            .where(SessionRuleSet.session_id == review_session.id)
            .where(SessionRuleSet.name == "Soft Deleted")
        ).scalars()
    )
    assert rows == []
