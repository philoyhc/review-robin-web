"""The responses-received confirmation is queued on a successful submit.

Author's ruling, 2026-10-02 (G4): when the session's "send on submit"
toggle is on, a reviewer's successful submit writes a
``responses_received`` outbox row. It is work in progress awaiting
Azure: the row stays ``queued`` because no transport exists yet."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import (
    Assignment,
    AuditEvent,
    EmailOutbox,
    InstrumentResponseField,
    Response,
    ReviewSession,
    User,
)
from app.services import audit, email_templates

from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


@pytest.fixture
def rae() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae Reviewer",
        provider="aad",
    )


def _ready_session(
    client: TestClient, db: Session, code: str, name: str | None = None
) -> ReviewSession:
    client.post(
        "/operator/sessions",
        data={"name": name or code.title(), "code": code},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
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
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(client, review_session.id)
    client.post(
        f"/operator/sessions/{review_session.id}/workflow/prepare",
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/workflow/activate",
        follow_redirects=False,
    )
    db.refresh(review_session)
    assert review_session.status == "ready"
    return review_session


def _answer_and_submit(
    rae_client: TestClient, db: Session, review_session: ReviewSession
) -> int:
    data: dict[str, str] = {}
    for assignment in db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalars():
        data[f"response[{assignment.id}][rating]"] = "5"
        data[f"response[{assignment.id}][comments]"] = "fine"
    rae_client.post(
        f"/me/sessions/{review_session.id}/1/save",
        data=data,
        follow_redirects=False,
    )
    return rae_client.post(
        f"/me/sessions/{review_session.id}/submit", follow_redirects=False
    ).status_code


def _received_rows(db: Session, session_id: int) -> list[EmailOutbox]:
    return list(
        db.execute(
            select(EmailOutbox).where(
                EmailOutbox.session_id == session_id,
                EmailOutbox.kind == "responses_received",
            )
        ).scalars()
    )


def test_a_submit_queues_the_confirmation(
    client: TestClient, db: Session, rae: AuthenticatedUser, make_client
) -> None:
    review_session = _ready_session(client, db, "received-on")

    assert _answer_and_submit(make_client(rae), db, review_session) == 303

    rows = _received_rows(db, review_session.id)
    assert len(rows) == 1
    row = rows[0]
    assert row.to_email == "rae@example.edu"
    assert row.status == "queued"
    assert row.sent_at is None
    assert review_session.name in row.subject
    assert "(not yet submitted)" not in row.body
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "responses_received.queued",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    assert event.detail["refs"]["outbox_id"] == row.id
    rae_user = db.execute(
        select(User).where(User.email == "rae@example.edu")
    ).scalar_one()
    assert event.actor_user_id == rae_user.id


def test_a_second_submit_refreshes_the_one_queued_row(
    client: TestClient, db: Session, rae: AuthenticatedUser, make_client
) -> None:
    """A double-clicked Submit (or a recall and resubmit) leaves one
    pending confirmation, not two."""
    review_session = _ready_session(client, db, "received-twice")
    rae_client = make_client(rae)

    assert _answer_and_submit(rae_client, db, review_session) == 303
    assert (
        rae_client.post(
            f"/me/sessions/{review_session.id}/submit", follow_redirects=False
        ).status_code
        == 303
    )

    assert len(_received_rows(db, review_session.id)) == 1
    contexts = [
        e.detail["context"]["refreshed"]
        for e in db.execute(
            select(AuditEvent)
            .where(
                AuditEvent.event_type == "responses_received.queued",
                AuditEvent.session_id == review_session.id,
            )
            .order_by(AuditEvent.id)
        ).scalars()
    ]
    assert contexts == [False, True]


def test_a_long_session_name_keeps_the_subject_within_its_column(
    client: TestClient, db: Session, rae: AuthenticatedUser, make_client
) -> None:
    review_session = _ready_session(
        client, db, "received-long", name="n" * 255
    )

    assert _answer_and_submit(make_client(rae), db, review_session) == 303

    (row,) = _received_rows(db, review_session.id)
    assert len(row.subject) == 255


def test_a_queue_failure_does_not_fail_the_submit(
    client: TestClient,
    db: Session,
    rae: AuthenticatedUser,
    make_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The submit has committed before the queue runs; a database error
    while queueing is logged and rolled back, not shown to the reviewer."""
    review_session = _ready_session(client, db, "received-fails")

    def _boom(*args: object, **kwargs: object) -> tuple[str, str]:
        raise OperationalError("render", {}, Exception("db down"))

    monkeypatch.setattr(email_templates, "render_responses_received", _boom)

    assert _answer_and_submit(make_client(rae), db, review_session) == 303

    assert _received_rows(db, review_session.id) == []
    submitted = db.execute(
        select(Response)
        .join(Assignment, Response.assignment_id == Assignment.id)
        .where(
            Assignment.session_id == review_session.id,
            Response.submitted_at.is_not(None),
        )
    ).scalars().all()
    assert submitted


def test_toggle_off_queues_nothing(
    client: TestClient, db: Session, rae: AuthenticatedUser, make_client
) -> None:
    review_session = _ready_session(client, db, "received-off")
    email_templates.set_responses_received_enabled(review_session, False)
    db.commit()

    assert _answer_and_submit(make_client(rae), db, review_session) == 303

    assert _received_rows(db, review_session.id) == []


def test_a_blocked_submit_queues_nothing(
    client: TestClient, db: Session, rae: AuthenticatedUser, make_client
) -> None:
    review_session = _ready_session(client, db, "received-blocked")

    response = make_client(rae).post(
        f"/me/sessions/{review_session.id}/submit", follow_redirects=False
    )

    assert response.status_code == 400
    assert _received_rows(db, review_session.id) == []


def test_a_failure_after_the_write_leaves_no_row(
    client: TestClient,
    db: Session,
    rae: AuthenticatedUser,
    make_client,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failure once the outbox row is flushed rolls the row back too,
    and is logged."""
    review_session = _ready_session(client, db, "received-late-fail")

    real_write_event = audit.write_event

    def _boom_on_queue(*args: object, **kwargs: object) -> object:
        if kwargs.get("event_type") == "responses_received.queued":
            raise OperationalError("audit", {}, Exception("db down"))
        return real_write_event(*args, **kwargs)

    monkeypatch.setattr(audit, "write_event", _boom_on_queue)

    assert _answer_and_submit(make_client(rae), db, review_session) == 303

    assert _received_rows(db, review_session.id) == []
    assert "queueing the responses-received email failed" in caplog.text


def test_a_submit_that_recorded_nothing_queues_nothing(
    client: TestClient, db: Session, rae: AuthenticatedUser, make_client
) -> None:
    """With every field optional and nothing answered, the submit
    succeeds but stamps no response, so there is nothing to confirm."""
    review_session = _ready_session(client, db, "received-empty")
    for field in db.execute(select(InstrumentResponseField)).scalars():
        field.required = False
    db.commit()

    response = make_client(rae).post(
        f"/me/sessions/{review_session.id}/submit", follow_redirects=False
    )

    assert response.status_code == 303
    assert _received_rows(db, review_session.id) == []
