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
from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)
from app.services import session_lifecycle as lifecycle
from ._instrument_states import add_group_instrument
from ._validated import validate_session


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


def _generate_full_matrix(client: TestClient, db: Session, session_id: int) -> None:
    pin_full_matrix_on_all_instruments(db, session_id)
    response = generate_via_page_button(client, session_id)
    assert response.status_code == 303, response.text


def _build_ready_session(
    client: TestClient, db: Session, code: str = "ready-1"
) -> ReviewSession:
    session = _create_session(client, db, code=code)
    _populate_rosters(client, session.id)
    _generate_full_matrix(client, db, session.id)
    validate_session(session)
    client.get(f"/operator/sessions/{session.id}/assignments")
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
    assert instrument.deadline_closed_at is None


def test_activate_blocks_when_errors_exist(client: TestClient, db: Session) -> None:
    session = _create_session(client, db, code="empty-session")
    response = client.post(
        f"/operator/sessions/{session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    # audit R2 — activation failure bounces to the Session Home flash
    # (super_status=failed) rather than an error page. Stays draft.
    assert response.status_code == 303
    assert "super_status=failed" in response.headers["location"]
    db.refresh(session)
    assert session.status == "draft"


def test_activate_requires_acknowledge_when_warnings_present(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="warn-1")
    _populate_rosters(client, session.id)
    # Skip _generate_full_matrix so the assignment_mode-is-None warning fires.
    validate_session(session)
    client.get(f"/operator/sessions/{session.id}/assignments")
    db.refresh(session)
    assert session.status == "validated"

    no_ack = client.post(
        f"/operator/sessions/{session.id}/activate",
        follow_redirects=False,
    )
    # audit R2 — unacknowledged warnings bounce to the flash, not an
    # error page. The session stays validated.
    assert no_ack.status_code == 303
    assert "super_status=failed" in no_ack.headers["location"]
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
    assert audit.detail["context"]["override_warnings"] is False


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
    assert audit.detail["counts"]["responses_at_revert"] == 1


def test_each_mutating_endpoint_returns_409_while_ready(
    client: TestClient, db: Session
) -> None:
    session = _build_ready_session(client, db, code="locked-1")
    sid = session.id

    targets: list[tuple[str, dict, dict]] = [
        (f"/operator/sessions/{sid}/config", {"name": "x", "code": "x", "description": ""}, {}),
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
            f"/operator/sessions/{sid}/assignments/generate",
            {
                "confirm_replace": "true",
            },
            {},
        ),
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
    _generate_full_matrix(operator, db, session.id)
    # explicitly NOT activated

    rae = AuthenticatedUser(
        principal_id="rae-oid", email="rae@example.edu", name="Rae", provider="aad"
    )
    rae_client = make_client(rae)
    response = rae_client.post(
        f"/me/sessions/{session.id}/1/save",
        data={},
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_no_per_instrument_open_or_close(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Accepting is session-wide (author's ruling, 2026-10-01): Activate
    opens every instrument and the deadline, Close session or Revert closes them
    all. The per-instrument Open / Close buttons and their routes are
    gone, so an operator cannot leave one instrument closed while
    another accepts."""
    operator = make_client(alice)
    session = _build_ready_session(operator, db, code="no-per-instr")
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == session.id)
    ).scalar_one()

    page = operator.get(f"/operator/sessions/{session.id}/instruments")
    assert page.status_code == 200
    assert "Close this instrument" not in page.text
    assert "Open this Instrument" not in page.text
    for action in ("open", "close"):
        response = operator.post(
            f"/operator/sessions/{session.id}/instruments/{instrument.id}/{action}",
            follow_redirects=False,
        )
        assert response.status_code in (404, 405), action
    db.refresh(instrument)
    assert instrument.accepting_responses is True


def test_a_live_session_left_split_by_the_retired_close_heals(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The upgrade state: an Activated session, before its deadline, whose
    operator closed one instrument with the retired per-instrument Close.
    Nothing can reopen it from the UI now, and the session-wide gate
    would refuse every reviewer write, so the deadline observer reopens
    it on the reviewer's next request and records why."""
    operator = make_client(alice)
    session = _build_ready_session(operator, db, code="split-heal")
    session.deadline = datetime.now(timezone.utc) + timedelta(days=1)
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == session.id)
    ).scalar_one()
    instrument.accepting_responses = False  # what the retired Close left
    db.commit()

    rae = AuthenticatedUser(
        principal_id="rae-oid", email="rae@example.edu", name="Rae", provider="aad"
    )
    response = make_client(rae).post(
        f"/me/sessions/{session.id}/1/save",
        data={},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    db.refresh(instrument)
    assert instrument.accepting_responses is True
    healed = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "instrument.opened",
            AuditEvent.session_id == session.id,
        )
    ).scalars().all()
    assert len(healed) == 1
    assert healed[0].detail["reason"] == "session_wide"


def test_the_heal_leaves_a_session_past_its_deadline_closed(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    session = _build_ready_session(operator, db, code="split-past")
    session.deadline = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    lifecycle.observe_deadline(db, session)
    lifecycle.observe_deadline(db, session)  # a second pass reopens nothing
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == session.id)
    ).scalar_one()
    assert instrument.accepting_responses is False


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
        f"/me/sessions/{session.id}/1/save",
        data={},
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_past_the_deadline_a_ready_session_still_shows_the_reviewer_their_values(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """While the session is ``ready`` the reviewer is inside the
    ``while_ongoing`` window, whose ``peer_reviewer`` cell is Raw by
    rule, so once the deadline closes the instruments their own saved
    values stay readable (read-only). The visibility policy decides
    (G10, 2026-10-01)."""
    operator = make_client(alice)
    session = _build_ready_session(operator, db, code="visibility")
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == session.id)
    ).scalar_one()

    rae = AuthenticatedUser(
        principal_id="rae-oid", email="rae@example.edu", name="Rae", provider="aad"
    )
    rae_client = make_client(rae)
    rae_client.post(
        f"/me/sessions/{session.id}/1/save",
        data={
            f"response[{assignment.id}][rating]": "4",
            f"response[{assignment.id}][comments]": "secret-comment",
        },
        follow_redirects=False,
    )

    # Pass the deadline: the reviewer's next GET runs the deadline
    # observer, which closes every instrument.
    session.deadline = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    page = rae_client.get(f"/me/sessions/{session.id}")
    assert page.status_code == 200
    assert "no longer accepting responses" in page.text.lower()
    assert "secret-comment" in page.text
    assert "remain visible below" in page.text


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
    rae_client.get(f"/me/sessions/{session.id}")
    rae_client.get(f"/me/sessions/{session.id}")
    rae_client.get(f"/me/sessions/{session.id}")

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


def test_lazy_deadline_close_audit_carries_correlation_id(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """observe_deadline's audit row carries the request's correlation_id.

    Regression for unfinished_business.md #10: the deadline lazy-close
    audit was emitted with correlation_id=None, leaving "which request
    tripped the close?" undebuggable. Now correlation_id is threaded
    through from each observe_deadline caller (operator instruments
    GET, reviewer surface GET, reviewer pre-write check).
    """
    operator = make_client(alice)
    session = _build_ready_session(operator, db, code="lazy-close-cid")
    session.deadline = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    rae = AuthenticatedUser(
        principal_id="rae-oid", email="rae@example.edu", name="Rae", provider="aad"
    )
    rae_client = make_client(rae)
    rae_client.get(f"/me/sessions/{session.id}")

    deadline_events = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "instrument.closed",
            AuditEvent.session_id == session.id,
        )
    ).scalars().all()
    deadline_only = [
        e for e in deadline_events if (e.detail or {}).get("reason") == "deadline"
    ]
    assert len(deadline_only) == 1
    assert deadline_only[0].correlation_id is not None
    assert deadline_only[0].correlation_id != ""


# --------------------------------------------------------------------------- #
# Segment 13C — group-scoped instrument rule-required gate
# --------------------------------------------------------------------------- #


def _add_group_instrument(db: Session, session_id: int) -> Instrument:
    add_group_instrument(db, db.get(ReviewSession, session_id))
    return db.execute(
        select(Instrument)
        .where(Instrument.session_id == session_id)
        .where(Instrument.group_kind.is_not(None))
    ).scalar_one()


def test_activation_opens_a_group_instrument(
    client: TestClient, db: Session
) -> None:
    """Activation opens a group-scoped instrument like any other."""
    session = _create_session(client, db, code="grp-rule")
    group = _add_group_instrument(db, session.id)
    _populate_rosters(client, session.id)
    _generate_full_matrix(client, db, session.id)
    validate_session(session)
    client.get(f"/operator/sessions/{session.id}/assignments")
    activate = client.post(
        f"/operator/sessions/{session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    assert activate.status_code == 303, activate.text
    db.refresh(group)
    assert group.rule_set_id is not None  # Full Matrix pinned by the helper
    # Activation opens it with every other instrument; there is no
    # per-instrument open.
    assert group.accepting_responses is True
