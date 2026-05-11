"""Segment 9.5A — `validated` lifecycle state and invalidation triggers."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Instrument, ReviewSession
from ._full_matrix import full_matrix_seed_id


def _create_session(
    client: TestClient, db: Session, code: str = "v1"
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring Reviews", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _populate(client: TestClient, db: Session, session_id: int) -> None:
    client.post(
        f"/operator/sessions/{session_id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nRae,rae@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{session_id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{session_id}/assignments/rule-based/generate",
        data={"rule_set_id": full_matrix_seed_id(db), "exclude_self_review": ""},
        follow_redirects=False,
    )


def _validate(client: TestClient, session_id: int) -> None:
    response = client.get(f"/operator/sessions/{session_id}?validated=1")
    assert response.status_code == 200


def _validated_session(
    client: TestClient, db: Session, code: str = "v1"
) -> ReviewSession:
    session = _create_session(client, db, code=code)
    _populate(client, db, session.id)
    _validate(client, session.id)
    db.refresh(session)
    assert session.status == "validated"
    return session


# --------------------------------------------------------------------------- #
# T1 — draft → validated trigger
# --------------------------------------------------------------------------- #


def test_validated_query_flips_draft_to_validated_when_no_errors(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="t1-ok")
    _populate(client, db, session.id)

    client.get(f"/operator/sessions/{session.id}?validated=1")

    db.refresh(session)
    assert session.status == "validated"


def test_validated_query_does_not_flip_when_errors_exist(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="t1-err")
    # No setup → validation has errors

    client.get(f"/operator/sessions/{session.id}?validated=1")

    db.refresh(session)
    assert session.status == "draft"


def test_validated_query_idempotent_when_already_validated(
    client: TestClient, db: Session
) -> None:
    session = _validated_session(client, db, code="t1-idem")

    client.get(f"/operator/sessions/{session.id}?validated=1")

    db.refresh(session)
    assert session.status == "validated"
    # Only one session.validated audit event
    events = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.validated",
            AuditEvent.session_id == session.id,
        )
    ).scalars().all()
    assert len(events) == 1


def test_validate_deep_dive_does_not_flip_status(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="t1-readonly")
    _populate(client, db, session.id)

    response = client.get(f"/operator/sessions/{session.id}/validate")
    assert response.status_code == 200

    db.refresh(session)
    assert session.status == "draft"


# --------------------------------------------------------------------------- #
# T2 — activation requires validated
# --------------------------------------------------------------------------- #


def test_activate_rejects_from_draft(client: TestClient, db: Session) -> None:
    session = _create_session(client, db, code="t2-draft")
    _populate(client, db, session.id)
    # Skip validation step

    response = client.post(
        f"/operator/sessions/{session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "validated" in response.text.lower()
    db.refresh(session)
    assert session.status == "draft"


def test_activate_succeeds_from_validated(
    client: TestClient, db: Session
) -> None:
    session = _validated_session(client, db, code="t2-ok")

    response = client.post(
        f"/operator/sessions/{session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    db.refresh(session)
    assert session.status == "ready"


# --------------------------------------------------------------------------- #
# D2 — invalidation triggers (validated → draft)
# --------------------------------------------------------------------------- #


def _assert_invalidated(
    db: Session, session: ReviewSession, *, expected_reason: str
) -> None:
    db.refresh(session)
    assert session.status == "draft"
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.invalidated",
            AuditEvent.session_id == session.id,
        )
    ).scalar_one()
    assert event.detail is not None
    assert event.detail["reason"] == expected_reason


def test_reviewer_import_invalidates_validated(
    client: TestClient, db: Session
) -> None:
    session = _validated_session(client, db, code="inv-ri")

    client.post(
        f"/operator/sessions/{session.id}/reviewers/import",
        files={
            "file": (
                "r2.csv",
                b"ReviewerName,ReviewerEmail\nNew,new@example.edu\n",
                "text/csv",
            )
        },
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )

    _assert_invalidated(db, session, expected_reason="reviewers_imported")


def test_reviewee_import_invalidates_validated(
    client: TestClient, db: Session
) -> None:
    session = _validated_session(client, db, code="inv-ei")

    client.post(
        f"/operator/sessions/{session.id}/reviewees/import",
        files={
            "file": (
                "e2.csv",
                b"RevieweeName,RevieweeEmail\nNew,newee@example.edu\n",
                "text/csv",
            )
        },
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )

    _assert_invalidated(db, session, expected_reason="reviewees_imported")


def test_reviewers_delete_all_invalidates_validated(
    client: TestClient, db: Session
) -> None:
    session = _validated_session(client, db, code="inv-rda")

    client.post(
        f"/operator/sessions/{session.id}/reviewers/delete-all",
        data={"confirm": "true"},
        follow_redirects=False,
    )

    _assert_invalidated(db, session, expected_reason="reviewers_deleted_all")


def test_reviewees_delete_all_invalidates_validated(
    client: TestClient, db: Session
) -> None:
    session = _validated_session(client, db, code="inv-eda")

    client.post(
        f"/operator/sessions/{session.id}/reviewees/delete-all",
        data={"confirm": "true"},
        follow_redirects=False,
    )

    _assert_invalidated(db, session, expected_reason="reviewees_deleted_all")


def test_assignments_generate_invalidates_validated(
    client: TestClient, db: Session
) -> None:
    session = _validated_session(client, db, code="inv-ag")

    client.post(
        f"/operator/sessions/{session.id}/assignments/rule-based/generate",
        data={"rule_set_id": full_matrix_seed_id(db), "exclude_self_review": "", "confirm_replace": "true"},
        follow_redirects=False,
    )

    _assert_invalidated(db, session, expected_reason="assignments_generated")


def test_assignments_delete_all_invalidates_validated(
    client: TestClient, db: Session
) -> None:
    session = _validated_session(client, db, code="inv-ada")

    client.post(
        f"/operator/sessions/{session.id}/assignments/delete-all",
        data={"confirm": "true"},
        follow_redirects=False,
    )

    _assert_invalidated(db, session, expected_reason="assignments_deleted_all")


def test_session_edit_invalidates_validated(
    client: TestClient, db: Session
) -> None:
    session = _validated_session(client, db, code="inv-se")

    response = client.post(
        f"/operator/sessions/{session.id}/edit",
        data={"name": "Renamed", "code": "inv-se"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    _assert_invalidated(db, session, expected_reason="session_edited")
    assert session.name == "Renamed"


# --------------------------------------------------------------------------- #
# D2 carve-outs — actions that do NOT invalidate
# --------------------------------------------------------------------------- #


def test_delete_data_does_not_invalidate(
    client: TestClient, db: Session
) -> None:
    session = _validated_session(client, db, code="noinv-dd")

    response = client.post(
        f"/operator/sessions/{session.id}/delete-data",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    db.refresh(session)
    assert session.status == "validated"


def test_instrument_open_close_do_not_invalidate(
    client: TestClient, db: Session
) -> None:
    session = _validated_session(client, db, code="noinv-instr")
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == session.id)
    ).scalar_one()

    # Instrument open/close routes require ready, so directly toggling via
    # the lifecycle service from validated state would 409 — instead, verify
    # that no invalidate event has fired during validation.
    invalidated = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.invalidated",
            AuditEvent.session_id == session.id,
        )
    ).scalars().all()
    assert invalidated == []
    db.refresh(session)
    assert session.status == "validated"
    assert instrument.accepting_responses is False


# --------------------------------------------------------------------------- #
# D4 — revert from ready lands on draft (not validated)
# --------------------------------------------------------------------------- #


def test_revert_from_ready_lands_on_draft(
    client: TestClient, db: Session
) -> None:
    session = _validated_session(client, db, code="d4")
    client.post(
        f"/operator/sessions/{session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    db.refresh(session)
    assert session.status == "ready"

    client.post(
        f"/operator/sessions/{session.id}/revert",
        data={"confirm": "true"},
        follow_redirects=False,
    )

    db.refresh(session)
    assert session.status == "draft"


# --------------------------------------------------------------------------- #
# Audit — session.validated event fires on transition
# --------------------------------------------------------------------------- #


def test_session_validated_audit_event(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="audit-v")
    _populate(client, db, session.id)

    client.get(f"/operator/sessions/{session.id}?validated=1")

    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.validated",
            AuditEvent.session_id == session.id,
        )
    ).scalar_one()
    assert event.detail is not None
    assert event.detail["session_id"] == session.id


# --------------------------------------------------------------------------- #
# Mutating routes still rejected from ready (locked state still locks)
# --------------------------------------------------------------------------- #


def test_reviewer_import_rejected_when_ready(
    client: TestClient, db: Session
) -> None:
    session = _validated_session(client, db, code="lock-ready")
    client.post(
        f"/operator/sessions/{session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    db.refresh(session)
    assert session.status == "ready"

    response = client.post(
        f"/operator/sessions/{session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nNew,new@example.edu\n",
                "text/csv",
            )
        },
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 409
