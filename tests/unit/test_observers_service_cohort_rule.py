"""Unit tests for ``app.services.observers.set_cohort_rule``.

Exercises the per-observer cohort-rule writer service: validation,
multi-observer fan-out, no-op on empty ids, error paths for
unknown observers and invalid payloads, and the
``observer.cohort_rule_assigned`` audit event.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Observer, ReviewSession, User
from app.services import observers as observers_service


def _session_with_user(db: Session, *, code: str) -> tuple[ReviewSession, User]:
    user = User(email=f"{code}@example.org", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name=f"Sess-{code}",
        code=code,
        created_by_user_id=user.id,
        assignment_mode="manual",
    )
    db.add(review_session)
    db.flush()
    return review_session, user


def _add_observer(
    db: Session, *, review_session: ReviewSession, email: str
) -> Observer:
    observer = Observer(session_id=review_session.id, email=email)
    db.add(observer)
    db.flush()
    return observer


def test_set_cohort_rule_persists_validated_payload(db: Session) -> None:
    session, user = _session_with_user(db, code="cohort-persist")
    obs = _add_observer(db, review_session=session, email="a@example.org")
    payload = {
        "combinator": "AND",
        "rules": [
            {
                "field": "reviewer.tag1",
                "op": "IS THE SAME AS",
                "operand_tag": "observer.email",
                "operand_value": "",
            }
        ],
    }

    returned = observers_service.set_cohort_rule(
        db,
        review_session=session,
        observer_ids=[obs.id],
        payload=payload,
        user=user,
    )

    assert returned == payload
    db.expire_all()
    refetched = db.get(Observer, obs.id)
    assert refetched is not None
    assert refetched.cohort_rule == payload


def test_set_cohort_rule_fans_out_across_multiple_observers(
    db: Session,
) -> None:
    session, user = _session_with_user(db, code="cohort-fanout")
    o1 = _add_observer(db, review_session=session, email="a@example.org")
    o2 = _add_observer(db, review_session=session, email="b@example.org")
    o3 = _add_observer(db, review_session=session, email="c@example.org")
    payload = {
        "combinator": "OR",
        "rules": [
            {
                "field": "reviewee.tag1",
                "op": "IS",
                "operand_tag": "",
                "operand_value": "math",
            }
        ],
    }

    observers_service.set_cohort_rule(
        db,
        review_session=session,
        observer_ids=[o1.id, o2.id, o3.id],
        payload=payload,
        user=user,
    )

    db.expire_all()
    for oid in (o1.id, o2.id, o3.id):
        refetched = db.get(Observer, oid)
        assert refetched is not None
        assert refetched.cohort_rule == payload


def test_set_cohort_rule_none_clears_existing(db: Session) -> None:
    session, user = _session_with_user(db, code="cohort-clear")
    obs = _add_observer(db, review_session=session, email="x@example.org")
    obs.cohort_rule = {
        "combinator": "AND",
        "rules": [
            {
                "field": "reviewer.tag1",
                "op": "IS",
                "operand_tag": "",
                "operand_value": "old",
            }
        ],
    }
    db.commit()

    returned = observers_service.set_cohort_rule(
        db,
        review_session=session,
        observer_ids=[obs.id],
        payload=None,
        user=user,
    )

    assert returned is None
    db.expire_all()
    refetched = db.get(Observer, obs.id)
    assert refetched is not None
    assert refetched.cohort_rule is None


def test_set_cohort_rule_empty_ids_noops(db: Session) -> None:
    session, user = _session_with_user(db, code="cohort-noop")
    obs = _add_observer(db, review_session=session, email="x@example.org")
    obs.cohort_rule = {"combinator": "AND", "rules": []}
    db.commit()

    returned = observers_service.set_cohort_rule(
        db,
        review_session=session,
        observer_ids=[],
        payload={
            "combinator": "OR",
            "rules": [],
        },
        user=user,
    )

    assert returned is None
    db.expire_all()
    refetched = db.get(Observer, obs.id)
    assert refetched is not None
    assert refetched.cohort_rule == {"combinator": "AND", "rules": []}


def test_set_cohort_rule_rejects_invalid_payload(db: Session) -> None:
    session, user = _session_with_user(db, code="cohort-invalid")
    obs = _add_observer(db, review_session=session, email="x@example.org")

    with pytest.raises(observers_service.ObserverOperationError) as exc:
        observers_service.set_cohort_rule(
            db,
            review_session=session,
            observer_ids=[obs.id],
            payload={
                "combinator": "AND",
                "rules": [
                    {
                        "field": "reviewer.tag9",  # not in vocabulary
                        "op": "IS",
                        "operand_tag": "",
                        "operand_value": "x",
                    }
                ],
            },
            user=user,
        )
    assert exc.value.code == "invalid_cohort_rule"

    # Database untouched.
    db.expire_all()
    refetched = db.get(Observer, obs.id)
    assert refetched is not None
    assert refetched.cohort_rule is None


def test_set_cohort_rule_rejects_ids_from_other_session(db: Session) -> None:
    session_a, user = _session_with_user(db, code="cohort-cross-a")
    session_b, _ = _session_with_user(db, code="cohort-cross-b")
    obs_a = _add_observer(db, review_session=session_a, email="a@example.org")
    obs_b = _add_observer(db, review_session=session_b, email="b@example.org")

    with pytest.raises(observers_service.ObserverOperationError) as exc:
        observers_service.set_cohort_rule(
            db,
            review_session=session_a,
            observer_ids=[obs_a.id, obs_b.id],
            payload={"combinator": "AND", "rules": []},
            user=user,
        )
    assert exc.value.code == "not_in_session"


def test_set_cohort_rule_emits_audit_event(db: Session) -> None:
    session, user = _session_with_user(db, code="cohort-audit")
    o1 = _add_observer(db, review_session=session, email="a@example.org")
    o2 = _add_observer(db, review_session=session, email="b@example.org")
    payload = {"combinator": "AND", "rules": []}

    observers_service.set_cohort_rule(
        db,
        review_session=session,
        observer_ids=[o1.id, o2.id],
        payload=payload,
        user=user,
    )

    events = list(
        db.execute(
            select(AuditEvent).where(
                AuditEvent.session_id == session.id,
                AuditEvent.event_type == "observer.cohort_rule_assigned",
            )
        ).scalars()
    )
    assert len(events) == 1
    detail = events[0].detail
    assert detail["snapshot"]["observer_ids"] == sorted([o1.id, o2.id])
    assert detail["snapshot"]["cohort_rule"] == payload
    assert detail["refs"]["observer_count"] == 2
