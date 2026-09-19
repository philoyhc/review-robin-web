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

from app.db.models import ReviewSession

from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


def _create_session(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _populate(client: TestClient, db: Session, session_id: int, *, reviewer_email: str) -> None:
    client.post(
        f"/operator/sessions/{session_id}/reviewers/import",
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
    pin_full_matrix_on_all_instruments(db, session_id)
    generate_via_page_button(client, session_id)
