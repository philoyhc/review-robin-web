"""Tests for Segment 15C Slice 3 — RTD card library actions.

Three flows under test:

1. **Save to library.** Operator hits the per-row Save-to-library
   button on a non-seeded session RTD. A new
   ``operator_response_type_definitions`` row appears, the session
   RTD's ``library_origin_id`` points at it, and two audit events
   fire (one workspace-scoped, one session-scoped).

2. **Add from library.** Operator picks a library RTD from the
   picker and submits. A new ``response_type_definitions`` row
   appears with ``library_origin_id`` set; one session-scoped audit
   event fires.

3. **Picker visibility.** The "Add from library" card only renders
   when the operator has library entries not already on the
   session.

Plus refusal paths: seeded rows can't save to library;
name-collision in the library returns the operator to the page
with an inline error.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEvent,
    OperatorResponseTypeDefinition,
    ResponseTypeDefinition,
    ReviewSession,
)
from app.services.instruments import add_response_type_definition


def _make_session(
    client: TestClient, db: Session, *, code: str = "lib-test"
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Lib Test", "code": code},
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


# --- Save to library -------------------------------------------------------


def test_save_to_library_creates_library_row_and_links_session_row(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="s2l-1")
    user = review_session.created_by_user
    rtd = add_response_type_definition(
        db,
        review_session=review_session,
        response_type="MyType",
        data_type="Integer",
        min=0,
        max=10,
        step=1,
        list_csv=None,
        actor=user,
    )
    db.commit()

    response = client.post(
        f"/operator/sessions/{review_session.id}/response-types/{rtd.id}/save-to-library",
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    db.expire_all()
    library_row = db.execute(
        select(OperatorResponseTypeDefinition).where(
            OperatorResponseTypeDefinition.owner_user_id == user.id,
            OperatorResponseTypeDefinition.response_type == "MyType",
        )
    ).scalar_one()
    assert library_row.data_type == "Integer"
    assert library_row.min == 0
    assert library_row.max == 10
    assert library_row.step == 1

    session_row = db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.id == rtd.id
        )
    ).scalar_one()
    assert session_row.library_origin_id == library_row.id

    library_events = _audit_events(db, event_type="operator_rtd.created")
    assert len(library_events) >= 1
    session_events = _audit_events(
        db,
        event_type="response_type_definitions.saved_to_library",
        session_id=review_session.id,
    )
    assert len(session_events) == 1
    assert session_events[0].detail["refs"]["operator_rtd_id"] == library_row.id


def test_save_to_library_refuses_seeded_row(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="s2l-2")
    seeded = db.execute(
        select(ResponseTypeDefinition)
        .where(ResponseTypeDefinition.session_id == review_session.id)
        .where(ResponseTypeDefinition.is_seeded.is_(True))
        .limit(1)
    ).scalar_one()
    response = client.post(
        f"/operator/sessions/{review_session.id}/response-types/{seeded.id}/save-to-library",
        follow_redirects=False,
    )
    assert response.status_code == 409, response.text


def test_save_to_library_name_collision_returns_inline_error(
    client: TestClient, db: Session
) -> None:
    """Operator already has a library RTD named ``MyDup``; saving a
    same-named session RTD must redirect back with rtd_error rather
    than 500-ing on the unique-constraint exception."""
    review_session = _make_session(client, db, code="s2l-3")
    user = review_session.created_by_user
    # Pre-seed a library entry with the same name.
    db.add(
        OperatorResponseTypeDefinition(
            owner_user_id=user.id,
            response_type="MyDup",
            data_type="Integer",
            min=0,
            max=5,
            step=1,
            list_csv=None,
        )
    )
    db.commit()
    rtd = add_response_type_definition(
        db,
        review_session=review_session,
        response_type="MyDup",
        data_type="Integer",
        min=0,
        max=5,
        step=1,
        list_csv=None,
        actor=user,
    )
    db.commit()

    response = client.post(
        f"/operator/sessions/{review_session.id}/response-types/{rtd.id}/save-to-library",
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert "rtd_error" in response.headers["location"]


# --- Add from library ------------------------------------------------------


def test_add_from_library_creates_session_row_with_origin(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="afl-1")
    user = review_session.created_by_user
    library_row = OperatorResponseTypeDefinition(
        owner_user_id=user.id,
        response_type="LibType",
        data_type="Decimal",
        min=0.5,
        max=4.0,
        step=0.5,
        list_csv=None,
    )
    db.add(library_row)
    db.commit()

    response = client.post(
        f"/operator/sessions/{review_session.id}/response-types/add-from-library",
        data={"operator_rtd_id": library_row.id},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    session_row = db.execute(
        select(ResponseTypeDefinition)
        .where(ResponseTypeDefinition.session_id == review_session.id)
        .where(ResponseTypeDefinition.response_type == "LibType")
    ).scalar_one()
    assert session_row.library_origin_id == library_row.id
    assert session_row.is_seeded is False
    assert session_row.data_type == "Decimal"
    assert session_row.step == 0.5

    events = _audit_events(
        db,
        event_type="response_type_definitions.added_from_library",
        session_id=review_session.id,
    )
    assert len(events) == 1


def test_add_from_library_404_on_other_operators_entry(
    client: TestClient, db: Session
) -> None:
    """An operator can't add another operator's library RTD even
    by guessing the id — the lookup filters by owner_user_id."""
    from app.db.models import User

    review_session = _make_session(client, db, code="afl-2")
    bob = User(email="bob-rtd-15c@example.edu", is_operator=True)
    db.add(bob)
    db.flush()
    bob_lib = OperatorResponseTypeDefinition(
        owner_user_id=bob.id,
        response_type="BobsType",
        data_type="Integer",
        min=0,
        max=10,
        step=1,
        list_csv=None,
    )
    db.add(bob_lib)
    db.commit()

    response = client.post(
        f"/operator/sessions/{review_session.id}/response-types/add-from-library",
        data={"operator_rtd_id": bob_lib.id},
        follow_redirects=False,
    )
    assert response.status_code == 404


def test_add_from_library_name_collision_returns_inline_error(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="afl-3")
    user = review_session.created_by_user
    library_row = OperatorResponseTypeDefinition(
        owner_user_id=user.id,
        response_type="Long_text",  # collides with seeded RTD
        data_type="String",
        min=0,
        max=2000,
        step=None,
        list_csv=None,
    )
    db.add(library_row)
    db.commit()

    response = client.post(
        f"/operator/sessions/{review_session.id}/response-types/add-from-library",
        data={"operator_rtd_id": library_row.id},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "rtd_error" in response.headers["location"]


# --- Picker visibility -----------------------------------------------------


def test_picker_hidden_when_library_is_empty(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="pick-1")
    response = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    )
    assert response.status_code == 200
    assert "Add from library" not in response.text


def test_picker_visible_when_library_has_unused_entries(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="pick-2")
    user = review_session.created_by_user
    db.add(
        OperatorResponseTypeDefinition(
            owner_user_id=user.id,
            response_type="UnusedLibEntry",
            data_type="Integer",
            min=0,
            max=10,
            step=1,
            list_csv=None,
        )
    )
    db.commit()

    response = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    )
    assert response.status_code == 200
    assert "Add from library" in response.text
    assert "UnusedLibEntry" in response.text


def test_in_library_badge_renders_when_origin_set(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="badge-1")
    user = review_session.created_by_user
    library_row = OperatorResponseTypeDefinition(
        owner_user_id=user.id,
        response_type="BadgedType",
        data_type="Integer",
        min=0,
        max=10,
        step=1,
        list_csv=None,
    )
    db.add(library_row)
    db.commit()
    client.post(
        f"/operator/sessions/{review_session.id}/response-types/add-from-library",
        data={"operator_rtd_id": library_row.id},
        follow_redirects=False,
    )

    response = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    )
    assert response.status_code == 200
    # The "in library" pill renders next to BadgedType.
    assert "BadgedType" in response.text
    assert "in library" in response.text
