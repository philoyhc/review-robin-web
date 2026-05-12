"""Tests for Segment 15C Slice 5 — operator-library management on
the operator Settings page.

Pins:

1. GET renders both library cards (RTDs + RuleSets) with the
   operator's entries.
2. Empty-library cards render their empty-state message.
3. Each row shows the per-row session-copy count.
4. POST delete-rtd hard-deletes the library row and emits
   ``operator_rtd.deleted`` (workspace-scoped). Session copies
   survive with their ``library_origin_id`` cleared to NULL via
   the SET NULL cascade.
5. POST delete-rule-set soft-deletes (the library tier preserves
   revisions for historical audit refs). Session copies survive.
6. 404 on cross-operator id for both delete routes.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
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


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "S", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _make_library_rtd(
    db: Session, *, owner: User, name: str = "LibRtd"
) -> OperatorResponseTypeDefinition:
    rtd = OperatorResponseTypeDefinition(
        owner_user_id=owner.id,
        response_type=name,
        data_type="Integer",
        min=0.0,
        max=10.0,
        step=1.0,
        list_csv=None,
    )
    db.add(rtd)
    db.flush()
    return rtd


def _make_library_rule_set(
    db: Session, *, owner: User, name: str = "LibRule"
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
        rules_json=[],
        created_at=datetime.now(timezone.utc),
        created_by_user_id=owner.id,
    )
    db.add(revision)
    db.flush()
    rs.current_revision_id = revision.id
    db.flush()
    return rs


def _current_user(client: TestClient, db: Session) -> User:
    """Hit GET /settings once so get_or_create_user materialises the
    fake-auth user row, then return it."""
    client.get("/operator/settings")
    return db.execute(
        select(User).order_by(User.id.desc()).limit(1)
    ).scalar_one()


# --- GET render -------------------------------------------------------------


def test_settings_renders_empty_library_cards(
    client: TestClient, db: Session
) -> None:
    response = client.get("/operator/settings")
    assert response.status_code == 200
    body = response.text
    assert "Response Type Definitions (library)" in body
    assert "RuleSets (library)" in body
    # Empty-state messages render when no library entries exist.
    assert "No Response Type Definitions in your library yet" in body
    assert "No RuleSets in your library yet" in body


def test_settings_lists_library_entries(
    client: TestClient, db: Session
) -> None:
    user = _current_user(client, db)
    _make_library_rtd(db, owner=user, name="MyLibType")
    _make_library_rule_set(db, owner=user, name="MyLibRule")
    db.commit()

    body = client.get("/operator/settings").text
    assert "MyLibType" in body
    assert "MyLibRule" in body
    # Both rows render Delete buttons.
    assert (
        '/operator/settings/library/rtd/' in body
        and '/delete' in body
    )
    assert '/operator/settings/library/rule-set/' in body


def test_settings_shows_session_copy_count(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="sl-1")
    user = review_session.created_by_user
    library_rtd = _make_library_rtd(db, owner=user, name="Counted")
    # Plant a session copy referencing the library row.
    db.add(
        ResponseTypeDefinition(
            session_id=review_session.id,
            response_type="Counted",
            data_type="Integer",
            min=0.0,
            max=10.0,
            step=1.0,
            list_csv=None,
            is_seeded=False,
            seed_order=0,
            library_origin_id=library_rtd.id,
        )
    )
    db.commit()

    body = client.get("/operator/settings").text
    # The session-copy count cell renders the integer 1 in the row.
    assert "Counted" in body
    # Loose match — the count appears as ">1<" in a <td>.
    assert ">1<" in body


# --- Delete RTD -------------------------------------------------------------


def test_delete_library_rtd_succeeds_and_emits_audit(
    client: TestClient, db: Session
) -> None:
    user = _current_user(client, db)
    rtd = _make_library_rtd(db, owner=user, name="DelMe")
    db.commit()

    response = client.post(
        f"/operator/settings/library/rtd/{rtd.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/operator/settings"

    db.expire_all()
    assert (
        db.execute(
            select(OperatorResponseTypeDefinition).where(
                OperatorResponseTypeDefinition.id == rtd.id
            )
        ).scalar_one_or_none()
        is None
    )

    events = list(
        db.execute(
            select(AuditEvent).where(
                AuditEvent.event_type == "operator_rtd.deleted"
            )
        ).scalars()
    )
    assert len(events) == 1
    assert events[0].detail["snapshot"]["response_type"] == "DelMe"


def test_delete_library_rtd_preserves_session_copies(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="sl-2")
    user = review_session.created_by_user
    library_rtd = _make_library_rtd(db, owner=user, name="SurviveMe")
    session_rtd = ResponseTypeDefinition(
        session_id=review_session.id,
        response_type="SurviveMe",
        data_type="Integer",
        min=0.0,
        max=10.0,
        step=1.0,
        list_csv=None,
        is_seeded=False,
        seed_order=0,
        library_origin_id=library_rtd.id,
    )
    db.add(session_rtd)
    db.commit()
    session_rtd_id = session_rtd.id

    response = client.post(
        f"/operator/settings/library/rtd/{library_rtd.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303

    db.expire_all()
    surviving = db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.id == session_rtd_id
        )
    ).scalar_one()
    # Session copy survives; provenance pointer clears via SET NULL.
    assert surviving.response_type == "SurviveMe"
    assert surviving.library_origin_id is None


def test_delete_library_rtd_404_on_cross_operator(
    client: TestClient, db: Session
) -> None:
    other = User(email="other-rtd-15c@example.edu", is_operator=True)
    db.add(other)
    db.flush()
    rtd = _make_library_rtd(db, owner=other, name="NotMine")
    db.commit()

    response = client.post(
        f"/operator/settings/library/rtd/{rtd.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 404


# --- Delete RuleSet ---------------------------------------------------------


def test_delete_library_rule_set_soft_deletes_and_emits_audit(
    client: TestClient, db: Session
) -> None:
    user = _current_user(client, db)
    rs = _make_library_rule_set(db, owner=user, name="SoftDel")
    db.commit()

    response = client.post(
        f"/operator/settings/library/rule-set/{rs.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/operator/settings"

    db.expire_all()
    surviving = db.execute(
        select(RuleSet).where(RuleSet.id == rs.id)
    ).scalar_one()
    assert surviving.deleted_at is not None

    events = list(
        db.execute(
            select(AuditEvent).where(
                AuditEvent.event_type == "rule_set.deleted"
            )
        ).scalars()
    )
    assert len(events) >= 1


def test_delete_library_rule_set_preserves_session_copies(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="sl-3")
    user = review_session.created_by_user
    library_rs = _make_library_rule_set(db, owner=user, name="SurviveRS")
    session_copy = SessionRuleSet(
        session_id=review_session.id,
        name="SurviveRS",
        description="local copy",
        combinator="ALL_OF",
        exclude_self_reviews=True,
        seed=None,
        rules_json=[],
        library_origin_id=library_rs.id,
    )
    db.add(session_copy)
    db.commit()
    session_copy_id = session_copy.id

    response = client.post(
        f"/operator/settings/library/rule-set/{library_rs.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303

    db.expire_all()
    surviving = db.execute(
        select(SessionRuleSet).where(
            SessionRuleSet.id == session_copy_id
        )
    ).scalar_one()
    assert surviving.name == "SurviveRS"
    # Soft-delete on the library tier leaves the FK pointer intact —
    # the library row still exists with ``deleted_at`` set. Session
    # copies survive byte-identical. The SET NULL cascade only fires
    # when the library row is later hard-deleted (no UI for that in
    # 15C; future cleanup migration concern).
    assert surviving.library_origin_id == library_rs.id


def test_delete_library_rule_set_404_on_cross_operator(
    client: TestClient, db: Session
) -> None:
    other = User(email="other-rs-15c@example.edu", is_operator=True)
    db.add(other)
    db.flush()
    rs = _make_library_rule_set(db, owner=other, name="NotMineRS")
    db.commit()

    response = client.post(
        f"/operator/settings/library/rule-set/{rs.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 404


def test_delete_library_rule_set_404_on_seed(
    client: TestClient, db: Session
) -> None:
    """Seeds aren't owned by any operator; the lookup filters
    is_seed=False, so workspace seeds can't be deleted through the
    library-management surface."""
    _current_user(client, db)  # materialise the fake-auth user row
    seed = RuleSet(
        name="WorkspaceSeedSL",
        description="",
        scope="seed",
        owner_user_id=None,
        is_seed=True,
    )
    db.add(seed)
    db.commit()

    response = client.post(
        f"/operator/settings/library/rule-set/{seed.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 404
