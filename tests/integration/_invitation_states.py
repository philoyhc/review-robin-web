"""Shared session-setup helpers for the invitation lifecycle.

A ``_``-prefixed helper imported relatively, per the convention
`_full_matrix.py` sets and `_assignment_states.py` follows: a bare
`pytest` run puts nothing on `sys.path`, so an absolute
`from tests.…` import fails collection (Segment 19I Item 6 PR 2).

Lifted out of `test_invitations.py` at 19O Item 7 entry 14, when a
second module wanted them and imported them from that test module
instead — which works, but leaves one test file depending on another
test file's privates rather than on a declared interface.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.services import invitations

from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)
from ._public_id import public_id


def _create_session(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(select(ReviewSession).where(ReviewSession.code == code)).scalar_one()


def _populate(client: TestClient, db: Session, session_id: int, *, reviewer_email: str) -> None:
    client.post(
        f"/operator/sessions/{public_id(session_id)}/reviewers/import",
        files={
            "file": (
                "r.csv",
                f"ReviewerName,ReviewerEmail\nRae,{reviewer_email}\n".encode(),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{public_id(session_id)}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    pin_full_matrix_on_all_instruments(db, session_id)
    generate_via_page_button(client, session_id)


# --------------------------------------------------------------------------- #
# The bulk services, called directly
# --------------------------------------------------------------------------- #
#
# The bulk Send all and Remind incomplete routes refuse until 14G wires
# paced bulk dispatch, whatever ``RRW_BULK_SEND`` says (findings L2,
# ``tests/integration/test_bulk_send_off.py``). The services stay, for
# 14G; a test of what they do, or one that wants the state they leave
# (every invitation sent, the incomplete reminded), calls them here.


def _invite_url(token: str) -> str:
    return f"http://testserver/me/invite/{token}"


def _session_operator(db: Session, session: ReviewSession) -> User:
    user = db.get(User, session.created_by_user_id)
    assert user is not None
    return user


def bulk_send_all(db: Session, session: ReviewSession) -> int:
    """``invitations.send_all_invitations`` as the session's operator,
    as the bulk route did before findings L2; returns the count sent."""
    return invitations.send_all_invitations(
        db,
        review_session=session,
        user=_session_operator(db, session),
        build_invite_url=_invite_url,
    )


def bulk_remind_incomplete(db: Session, session: ReviewSession) -> invitations.ReminderBatchResult:
    """``invitations.send_reminders_to_incomplete`` as the session's
    operator, as the bulk route did before findings L2."""
    return invitations.send_reminders_to_incomplete(
        db,
        review_session=session,
        user=_session_operator(db, session),
        build_invite_url=_invite_url,
    )
