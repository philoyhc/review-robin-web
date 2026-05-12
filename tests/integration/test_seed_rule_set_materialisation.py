"""Tests for Segment 15C Slice 1 — workspace-seed materialisation
into ``session_rule_sets`` at session-create time.

Pins three behaviours:

1. ``create_session`` populates ``session_rule_sets`` with one
   row per ``SEEDED_RULE_SETS`` entry.
2. The materialised rows carry the same shape as the in-memory
   ``RuleSetSchema`` definitions (combinator, exclude_self_reviews,
   seed, rules_json round-trip).
3. ``materialise_seed_rule_sets`` is idempotent — re-running on a
   session that already has the seeds is a no-op and skips rows
   the operator may have edited locally.

Audit emission (``session_rule_sets.materialised_from_seed``) is
also pinned: one event fires per session-create call that
inserted rows.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession, SessionRuleSet
from app.services.rules.seeds import (
    SEEDED_RULE_SETS,
    _rules_json_payload,
    materialise_seed_rule_sets,
)


def _make_session(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Test", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed_rows_for(db: Session, session_id: int) -> list[SessionRuleSet]:
    return list(
        db.execute(
            select(SessionRuleSet)
            .where(SessionRuleSet.session_id == session_id)
            .order_by(SessionRuleSet.id)
        ).scalars()
    )


def test_create_session_materialises_every_seed_rule_set(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="seed-mat-1")

    rows = _seed_rows_for(db, review_session.id)
    assert [row.name for row in rows] == [
        schema.name for schema in SEEDED_RULE_SETS
    ]
    assert all(row.library_origin_id is None for row in rows), (
        "seed copies do not reference the operator library"
    )


def test_materialised_seed_rows_carry_full_schema_shape(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="seed-mat-2")

    rows = {
        row.name: row
        for row in _seed_rows_for(db, review_session.id)
    }
    for schema in SEEDED_RULE_SETS:
        row = rows[schema.name]
        assert row.description == (schema.description or "")
        assert row.combinator == schema.combinator.value
        assert row.exclude_self_reviews == schema.options.excludeSelfReviews
        assert row.seed == schema.options.seed
        assert row.rules_json == _rules_json_payload(schema)


def test_materialise_seed_rule_sets_is_idempotent(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="seed-mat-3")
    rows_first = _seed_rows_for(db, review_session.id)
    first_ids = [row.id for row in rows_first]
    assert len(first_ids) == len(SEEDED_RULE_SETS)

    # Edit the description on one materialised row — the idempotent
    # re-run must leave the edit in place rather than overwriting.
    rows_first[0].description = "operator-edited"
    db.flush()

    materialise_seed_rule_sets(db, review_session)
    db.flush()

    rows_second = _seed_rows_for(db, review_session.id)
    assert [row.id for row in rows_second] == first_ids
    edited = next(
        row for row in rows_second if row.id == rows_first[0].id
    )
    assert edited.description == "operator-edited"


def test_create_session_emits_materialised_from_seed_audit_event(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="seed-mat-4")

    events = list(
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.session_id == review_session.id)
            .where(
                AuditEvent.event_type
                == "session_rule_sets.materialised_from_seed"
            )
        ).scalars()
    )
    assert len(events) == 1
    detail = events[0].detail
    assert detail["counts"]["materialised"] == len(SEEDED_RULE_SETS)


def test_materialise_does_not_re_emit_audit_event_on_idempotent_run(
    client: TestClient, db: Session
) -> None:
    """The audit event fires only when rows are actually inserted.
    A subsequent idempotent call (which inserts nothing) does not
    re-emit the event — that's the caller's contract in
    ``create_session`` (audit emission is conditional on the
    returned dict being newly-populated)."""

    review_session = _make_session(client, db, code="seed-mat-5")
    materialise_seed_rule_sets(db, review_session)
    db.flush()

    events = list(
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.session_id == review_session.id)
            .where(
                AuditEvent.event_type
                == "session_rule_sets.materialised_from_seed"
            )
        ).scalars()
    )
    # Only the one emitted by ``create_session`` itself; the explicit
    # re-call doesn't fire any audit because the helper doesn't emit
    # — the caller is responsible.
    assert len(events) == 1
