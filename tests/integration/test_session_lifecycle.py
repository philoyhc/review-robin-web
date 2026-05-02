from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import (
    Assignment,
    AuditEvent,
    Instrument,
    Response,
    ReviewSession,
)
from app.services import session_lifecycle as lifecycle


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _create_session(client: TestClient, db: Session, code: str = "spring-2026") -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring Reviews", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _populate_rosters(client: TestClient, session_id: int) -> None:
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


def _generate_full_matrix(client: TestClient, session_id: int) -> None:
    response = client.post(
        f"/operator/sessions/{session_id}/assignments/full-matrix",
        data={"exclude_self_review": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text


def _build_ready_session(
    client: TestClient, db: Session, code: str = "ready-1"
) -> ReviewSession:
    session = _create_session(client, db, code=code)
    _populate_rosters(client, session.id)
    _generate_full_matrix(client, session.id)
    client.get(f"/operator/sessions/{session.id}?validated=1")
    response = client.post(
        f"/operator/sessions/{session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.refresh(session)
    return session


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_default_instrument_starts_closed(client: TestClient, db: Session) -> None:
    session = _create_session(client, db)
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == session.id)
    ).scalar_one()
    assert instrument.accepting_responses is False
    assert instrument.responses_visible_when_closed is False
    assert instrument.deadline_closed_at is None


def test_activate_blocks_when_errors_exist(client: TestClient, db: Session) -> None:
    session = _create_session(client, db, code="empty-session")
    response = client.post(
        f"/operator/sessions/{session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 400
    db.refresh(session)
    assert session.status == "draft"


def test_activate_requires_acknowledge_when_warnings_present(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="warn-1")
    _populate_rosters(client, session.id)
    # Skip _generate_full_matrix so the assignment_mode-is-None warning fires.
    client.get(f"/operator/sessions/{session.id}?validated=1")
    db.refresh(session)
    assert session.status == "validated"

    no_ack = client.post(
        f"/operator/sessions/{session.id}/activate",
        follow_redirects=False,
    )
    assert no_ack.status_code == 400
    db.refresh(session)
    assert session.status == "validated"

    with_ack = client.post(
        f"/operator/sessions/{session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    assert with_ack.status_code == 303, with_ack.text
    db.refresh(session)
    assert session.status == "ready"


def test_activate_opens_all_instruments_and_writes_audit(
    client: TestClient, db: Session
) -> None:
    session = _build_ready_session(client, db, code="ready-instr")
    instruments = db.execute(
        select(Instrument).where(Instrument.session_id == session.id)
    ).scalars().all()
    assert all(i.accepting_responses for i in instruments)
    audit = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.activated",
            AuditEvent.session_id == session.id,
        )
    ).scalar_one()
    assert audit.detail is not None
    assert audit.detail["override_warnings"] is False


def test_revert_requires_confirm_and_preserves_responses(
    client: TestClient, db: Session
) -> None:
    session = _build_ready_session(client, db, code="revert-1")
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == session.id)
    ).scalar_one()
    db.add(
        Response(
            assignment_id=assignment.id,
            response_field_id=db.execute(
                select(Instrument)
                .where(Instrument.session_id == session.id)
            )
            .scalar_one()
            .response_fields[0]
            .id,
            value="3",
            submitted_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    no_confirm = client.post(
        f"/operator/sessions/{session.id}/revert",
        follow_redirects=False,
    )
    assert no_confirm.status_code == 400

    confirmed = client.post(
        f"/operator/sessions/{session.id}/revert",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert confirmed.status_code == 303

    db.refresh(session)
    assert session.status == "draft"
    instruments = db.execute(
        select(Instrument).where(Instrument.session_id == session.id)
    ).scalars().all()
    assert all(not i.accepting_responses for i in instruments)
    response_row = db.execute(
        select(Response).where(Response.assignment_id == assignment.id)
    ).scalar_one()
    assert response_row.value == "3"
    assert response_row.submitted_at is not None
    audit = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.reverted_to_draft",
            AuditEvent.session_id == session.id,
        )
    ).scalar_one()
    assert audit.detail is not None
    assert audit.detail["response_count_at_revert"] == 1


def test_each_mutating_endpoint_returns_409_while_ready(
    client: TestClient, db: Session
) -> None:
    session = _build_ready_session(client, db, code="locked-1")
    sid = session.id

    targets: list[tuple[str, dict, dict]] = [
        (f"/operator/sessions/{sid}/edit", {"name": "x", "code": "x", "description": ""}, {}),
        (f"/operator/sessions/{sid}/delete", {"confirm": "true"}, {}),
        (
            f"/operator/sessions/{sid}/reviewers/import",
            {"confirm_replace": "true"},
            {"file": ("r.csv", b"ReviewerName,ReviewerEmail\nA,a@x.com\n", "text/csv")},
        ),
        (f"/operator/sessions/{sid}/reviewers/delete-all", {"confirm": "true"}, {}),
        (
            f"/operator/sessions/{sid}/reviewees/import",
            {"confirm_replace": "true"},
            {"file": ("e.csv", b"RevieweeName,RevieweeEmail\nC,c@x.com\n", "text/csv")},
        ),
        (f"/operator/sessions/{sid}/reviewees/delete-all", {"confirm": "true"}, {}),
        (
            f"/operator/sessions/{sid}/assignments/full-matrix",
            {"confirm_replace": "true"},
            {},
        ),
        (
            f"/operator/sessions/{sid}/assignments/manual/import",
            {"confirm_replace": "true"},
            {
                "file": (
                    "m.csv",
                    b"ReviewerEmail,RevieweeEmail\nrae@example.edu,carol@example.edu\n",
                    "text/csv",
                )
            },
        ),
        (f"/operator/sessions/{sid}/assignments/delete-all", {"confirm": "true"}, {}),
    ]
    for url, data, files in targets:
        response = client.post(url, data=data, files=files or None, follow_redirects=False)
        assert response.status_code == 409, f"{url} -> {response.status_code}"

    db.refresh(session)
    assert session.status == "ready"


def test_response_loss_ack_required_after_revert(
    client: TestClient, db: Session
) -> None:
    session = _build_ready_session(client, db, code="ack-1")
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == session.id)
    ).scalar_one()
    field = (
        db.execute(select(Instrument).where(Instrument.session_id == session.id))
        .scalar_one()
        .response_fields[0]
    )
    db.add(Response(assignment_id=assignment.id, response_field_id=field.id, value="4"))
    db.commit()

    client.post(
        f"/operator/sessions/{session.id}/revert",
        data={"confirm": "true"},
        follow_redirects=False,
    )

    no_ack = client.post(
        f"/operator/sessions/{session.id}/reviewers/delete-all",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert no_ack.status_code == 400

    with_ack = client.post(
        f"/operator/sessions/{session.id}/reviewers/delete-all",
        data={"confirm": "true", "acknowledge_response_loss": "true"},
        follow_redirects=False,
    )
    assert with_ack.status_code == 303


def test_reviewer_save_403_when_session_draft(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    session = _create_session(operator, db, code="draft-rev")
    _populate_rosters(operator, session.id)
    _generate_full_matrix(operator, session.id)
    # explicitly NOT activated

    rae = AuthenticatedUser(
        principal_id="rae-oid", email="rae@example.edu", name="Rae", provider="aad"
    )
    rae_client = make_client(rae)
    response = rae_client.post(
        f"/reviewer/sessions/{session.id}/save",
        data={},
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_reviewer_save_403_when_instrument_closed_manually(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    session = _build_ready_session(operator, db, code="manual-close")
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == session.id)
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{session.id}/instruments/{instrument.id}/close",
        follow_redirects=False,
    )

    rae = AuthenticatedUser(
        principal_id="rae-oid", email="rae@example.edu", name="Rae", provider="aad"
    )
    rae_client = make_client(rae)
    response = rae_client.post(
        f"/reviewer/sessions/{session.id}/save",
        data={},
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_reviewer_save_403_when_deadline_passed(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    session = _build_ready_session(operator, db, code="deadline-1")
    session.deadline = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    rae = AuthenticatedUser(
        principal_id="rae-oid", email="rae@example.edu", name="Rae", provider="aad"
    )
    rae_client = make_client(rae)
    response = rae_client.post(
        f"/reviewer/sessions/{session.id}/save",
        data={},
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_reviewer_surface_hides_values_when_closed_and_invisible(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    session = _build_ready_session(operator, db, code="visibility")
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == session.id)
    ).scalar_one()
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == session.id)
    ).scalar_one()

    # Reviewer saves a draft while still accepting.
    rae = AuthenticatedUser(
        principal_id="rae-oid", email="rae@example.edu", name="Rae", provider="aad"
    )
    rae_client = make_client(rae)
    rae_client.post(
        f"/reviewer/sessions/{session.id}/save",
        data={
            f"response[{assignment.id}][rating]": "4",
            f"response[{assignment.id}][comments]": "secret-comment",
        },
        follow_redirects=False,
    )

    # Close the instrument directly via the service so we don't have to
    # juggle TestClient identity overrides mid-test.
    user = db.execute(select(__import__("app.db.models", fromlist=["User"]).User)).scalars().first()
    lifecycle.close_instrument(
        db,
        instrument=instrument,
        review_session=session,
        user=user,
        reason="manual",
    )

    page = rae_client.get(f"/reviewer/sessions/{session.id}")
    assert page.status_code == 200
    assert "secret-comment" not in page.text
    assert "no longer accepting responses" in page.text.lower()

    lifecycle.set_responses_visible_when_closed(
        db,
        instrument=instrument,
        review_session=session,
        user=user,
        visible=True,
    )
    page = rae_client.get(f"/reviewer/sessions/{session.id}")
    assert "secret-comment" in page.text


def test_lazy_deadline_close_fires_once(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    session = _build_ready_session(operator, db, code="lazy-close")
    session.deadline = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    rae = AuthenticatedUser(
        principal_id="rae-oid", email="rae@example.edu", name="Rae", provider="aad"
    )
    rae_client = make_client(rae)
    rae_client.get(f"/reviewer/sessions/{session.id}")
    rae_client.get(f"/reviewer/sessions/{session.id}")
    rae_client.get(f"/reviewer/sessions/{session.id}")

    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == session.id)
    ).scalar_one()
    assert instrument.accepting_responses is False
    assert instrument.deadline_closed_at is not None

    deadline_events = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "instrument.closed",
            AuditEvent.session_id == session.id,
        )
    ).scalars().all()
    deadline_only = [e for e in deadline_events if (e.detail or {}).get("reason") == "deadline"]
    assert len(deadline_only) == 1


def test_instrument_close_open_visibility_audits(
    client: TestClient, db: Session
) -> None:
    session = _build_ready_session(client, db, code="instr-audit")
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == session.id)
    ).scalar_one()

    client.post(
        f"/operator/sessions/{session.id}/instruments/{instrument.id}/close",
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{session.id}/instruments/{instrument.id}/open",
        follow_redirects=False,
    )

    closed = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "instrument.closed",
            AuditEvent.session_id == session.id,
        )
    ).scalars().all()
    opened = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "instrument.opened",
            AuditEvent.session_id == session.id,
        )
    ).scalars().all()
    manual_close = [e for e in closed if (e.detail or {}).get("reason") == "manual"]
    assert len(manual_close) == 1
    assert len(opened) == 1
