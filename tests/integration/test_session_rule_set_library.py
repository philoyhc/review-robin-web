"""Tests for Segment 15C Slice 4a — session-tier RuleSet writes +
cross-tier promote / demote.

This slice ships the **service** module
:mod:`app.services.rules.session_library` and the two new routes
``rule-based-editor/save-to-library`` and
``rule-based-editor/add-from-library`` while leaving the Rule
Builder picker / editor / Save handlers untouched. The picker
source flip itself lands in Slice 4b.

Tests pin:

1. Save-to-library copies a SessionRuleSet into ``operator_rule_sets``
   with a fresh revision, sets ``library_origin_id``, and emits
   ``rule_set.created`` + ``session_rule_sets.saved_to_library``.
2. Save-to-library refuses on library name collision.
3. Save-to-library is idempotent when ``library_origin_id`` already
   points at an extant library row.
4. Add-from-library copies a library RuleSet's current revision into
   ``session_rule_sets`` with ``library_origin_id`` set; emits
   ``session_rule_sets.added_from_library``.
5. Add-from-library refuses on cross-operator id (404).
6. Add-from-library refuses on session-name collision (303 with
   ``error=name_collision``).
7. Session-tier name-collision helpers correctly scope to
   ``(session_id, name)`` (`name_taken_in_session`).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEvent,
    ReviewSession,
    RuleSet,
    RuleSetRevision,
    SessionRuleSet,
    User,
)
from app.services.rules import session_library


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Lib", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _audit_events(
    db: Session, *, event_type: str, session_id: int | None = None
) -> list[AuditEvent]:
    stmt = select(AuditEvent).where(AuditEvent.event_type == event_type)
    if session_id is not None:
        stmt = stmt.where(AuditEvent.session_id == session_id)
    return list(db.execute(stmt).scalars())


def _add_library_rule_set(
    db: Session, *, owner: User, name: str, rules_json: list[dict] | None = None
) -> RuleSet:
    rs = RuleSet(
        name=name,
        description=f"library {name}",
        scope="personal",
        owner_user_id=owner.id,
        is_seed=False,
    )
    db.add(rs)
    db.flush()
    revision = RuleSetRevision(
        rule_set_id=rs.id,
        revision_no=1,
        combinator="ALL_OF",
        exclude_self_reviews=True,
        seed=None,
        rules_json=rules_json or [],
        created_at=datetime.now(timezone.utc),
        created_by_user_id=owner.id,
    )
    db.add(revision)
    db.flush()
    rs.current_revision_id = revision.id
    db.flush()
    return rs


def _seed_session_rule_set(
    db: Session,
    *,
    review_session: ReviewSession,
    name: str,
    library_origin_id: int | None = None,
) -> SessionRuleSet:
    row = SessionRuleSet(
        session_id=review_session.id,
        name=name,
        description="local",
        combinator="ALL_OF",
        exclude_self_reviews=True,
        seed=None,
        rules_json=[],
        library_origin_id=library_origin_id,
    )
    db.add(row)
    db.flush()
    return row


# --- Save to library --------------------------------------------------------


def test_save_to_library_creates_library_row_links_session_row(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="lib-rs-1")
    user = review_session.created_by_user
    row = _seed_session_rule_set(
        db, review_session=review_session, name="MyAuthoredRule"
    )
    db.commit()

    response = client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based-editor/save-to-library",
        data={"rule_set_id": row.id},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    db.expire_all()
    library_row = db.execute(
        select(RuleSet).where(
            RuleSet.owner_user_id == user.id,
            RuleSet.name == "MyAuthoredRule",
        )
    ).scalar_one()
    revision = db.execute(
        select(RuleSetRevision).where(
            RuleSetRevision.id == library_row.current_revision_id
        )
    ).scalar_one()
    assert revision.combinator == "ALL_OF"
    assert revision.rules_json == []

    session_row = db.execute(
        select(SessionRuleSet).where(SessionRuleSet.id == row.id)
    ).scalar_one()
    assert session_row.library_origin_id == library_row.id

    workspace_events = _audit_events(
        db, event_type="rule_set.created"
    )
    session_events = _audit_events(
        db,
        event_type="session_rule_sets.saved_to_library",
        session_id=review_session.id,
    )
    assert len(workspace_events) >= 1
    assert len(session_events) == 1
    assert (
        session_events[0].detail["refs"]["rule_set_id"]
        == library_row.id
    )


def test_save_to_library_name_collision_returns_inline_error(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="lib-rs-2")
    user = review_session.created_by_user
    _add_library_rule_set(db, owner=user, name="Dup")
    row = _seed_session_rule_set(
        db, review_session=review_session, name="Dup"
    )
    db.commit()

    response = client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based-editor/save-to-library",
        data={"rule_set_id": row.id},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "error=name_collision" in response.headers["location"]


def test_save_to_library_idempotent_when_origin_extant(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="lib-rs-3")
    user = review_session.created_by_user
    library_row = _add_library_rule_set(db, owner=user, name="Already")
    row = _seed_session_rule_set(
        db,
        review_session=review_session,
        name="Already",
        library_origin_id=library_row.id,
    )
    db.commit()

    # Direct service call to assert idempotency without a route round
    # trip (the route's collision check would short-circuit first).
    returned = session_library.save_to_library(
        db, session_rule_set=row, actor=user, correlation_id="c"
    )
    db.commit()
    assert returned.id == library_row.id

    library_rows = list(
        db.execute(
            select(RuleSet).where(
                RuleSet.owner_user_id == user.id,
                RuleSet.name == "Already",
            )
        ).scalars()
    )
    assert len(library_rows) == 1


# --- Add from library -------------------------------------------------------


def test_add_from_library_copies_revision_snapshot(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="lib-rs-4")
    user = review_session.created_by_user
    library_row = _add_library_rule_set(
        db, owner=user, name="FromLib", rules_json=[{"id": "r1"}]
    )
    db.commit()

    response = client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based-editor/add-from-library",
        data={"library_rule_set_id": library_row.id},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    session_row = db.execute(
        select(SessionRuleSet)
        .where(SessionRuleSet.session_id == review_session.id)
        .where(SessionRuleSet.name == "FromLib")
    ).scalar_one()
    assert session_row.library_origin_id == library_row.id
    assert session_row.combinator == "ALL_OF"
    assert session_row.rules_json == [{"id": "r1"}]

    events = _audit_events(
        db,
        event_type="session_rule_sets.added_from_library",
        session_id=review_session.id,
    )
    assert len(events) == 1


def test_add_from_library_404_on_cross_operator_id(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="lib-rs-5")
    bob = User(email="bob-rs-15c@example.edu", is_operator=True)
    db.add(bob)
    db.flush()
    library_row = _add_library_rule_set(db, owner=bob, name="BobRule")
    db.commit()

    response = client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based-editor/add-from-library",
        data={"library_rule_set_id": library_row.id},
        follow_redirects=False,
    )
    assert response.status_code == 404


def test_add_from_library_session_name_collision_returns_inline_error(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="lib-rs-6")
    user = review_session.created_by_user
    library_row = _add_library_rule_set(db, owner=user, name="Already")
    # Plant a session row with the same name first.
    _seed_session_rule_set(
        db, review_session=review_session, name="Already"
    )
    db.commit()

    response = client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based-editor/add-from-library",
        data={"library_rule_set_id": library_row.id},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "error=name_collision" in response.headers["location"]


# --- Service-tier helpers ---------------------------------------------------


def test_name_taken_in_session_scoped_correctly(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="lib-rs-7")
    _seed_session_rule_set(
        db, review_session=review_session, name="ThisOne"
    )
    db.commit()

    assert session_library.name_taken_in_session(
        db,
        session_id=review_session.id,
        candidate_name="ThisOne",
        exclude_id=None,
    )
    assert not session_library.name_taken_in_session(
        db,
        session_id=review_session.id,
        candidate_name="ThatOne",
        exclude_id=None,
    )


def test_list_library_rule_sets_not_in_session_filters_correctly(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="lib-rs-8")
    user = review_session.created_by_user
    _add_library_rule_set(db, owner=user, name="UnusedLib")
    in_session_lib = _add_library_rule_set(db, owner=user, name="UsedLib")
    _seed_session_rule_set(
        db,
        review_session=review_session,
        name="UsedLib",
        library_origin_id=in_session_lib.id,
    )
    db.commit()

    available = session_library.list_library_rule_sets_not_in_session(
        db, owner_user=user, session_id=review_session.id
    )
    available_names = [row.name for row in available]
    assert "UnusedLib" in available_names
    assert "UsedLib" not in available_names
