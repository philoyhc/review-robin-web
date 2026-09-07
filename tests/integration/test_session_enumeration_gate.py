"""Segment 19F PR 1 — session ids are not enumerable through a gate.

The property under test is **indistinguishability**: for each of the
four session-scoped gates, a signed-in caller who holds no role on an
existing session must get back exactly what they get for a session id
that does not exist. Same status, same body.

Before 19F the two differed — 404 for "no such session", 403 with a
role-naming ``detail`` for "the session exists but you are not on it" —
so any signed-in person could enumerate session ids, and count them, by
reading status codes. Content never leaked; existence did.

Each test probes **both** sides rather than asserting 404 twice, because
a gate that answered 404 for a real session and 500 for a missing one
would pass a one-sided check while still telling the two apart.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession

# An id far past anything the per-test database allocates.
MISSING_SESSION_ID = 987654


def _make_session(client: TestClient, db: Session, *, code: str) -> ReviewSession:
    """Alice creates a session; she is its sole SessionOperator."""
    response = client.post(
        "/operator/sessions",
        data={"name": "Cohort A", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


@pytest.mark.parametrize(
    ("gate", "path"),
    [
        ("require_session_operator", "/operator/sessions/{id}"),
        ("require_reviewer_in_session", "/me/sessions/{id}/1"),
        ("require_reviewee_in_session", "/me/sessions/{id}/results"),
        ("require_observer_in_session", "/me/sessions/{id}/collation"),
    ],
)
def test_a_session_you_hold_no_role_on_is_indistinguishable_from_no_session(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    gate: str,
    path: str,
) -> None:
    """Bob is signed in and on the workspace operator allowlist, but he
    holds no role on Alice's session: no SessionOperator row, and no
    reviewer / reviewee / observer roster row.

    The operator route is included deliberately. Decision 5 does not
    stop at the participant boundary — an operator who does not own
    session *n* could enumerate other operators' sessions by exactly the
    same means.
    """
    review_session = _make_session(db=db, client=client, code=f"enum-{gate[8:14]}")
    bob_client = make_client(bob)

    existing = bob_client.get(
        path.format(id=review_session.id), follow_redirects=False
    )
    missing = bob_client.get(
        path.format(id=MISSING_SESSION_ID), follow_redirects=False
    )

    assert existing.status_code == 404, gate
    assert existing.status_code == missing.status_code, gate
    # Body too: a `detail` naming the role would answer the question the
    # status code is refusing to answer.
    assert existing.text == missing.text, gate


def test_no_refusal_body_names_a_role_or_a_session(
    db: Session, client: TestClient, make_client, bob
) -> None:
    """The retired ``detail`` strings read "You are not an active
    reviewer/reviewee/observer in this session" and "You do not have
    access to this session" — each of which confirms the session exists.
    """
    review_session = _make_session(db=db, client=client, code="enum-body")
    bob_client = make_client(bob)
    for path in (
        f"/operator/sessions/{review_session.id}",
        f"/me/sessions/{review_session.id}/1",
        f"/me/sessions/{review_session.id}/results",
        f"/me/sessions/{review_session.id}/collation",
    ):
        body = bob_client.get(path, follow_redirects=False).text
        assert "not an active" not in body, path
        assert "do not have access" not in body, path
        assert "this session" not in body, path


def test_only_require_sys_admin_still_answers_403() -> None:
    """The Definition-of-done grep, as an assertion.

    ``require_operator`` (303 to ``/me``) and ``require_sys_admin``
    (403) are deliberately out of scope: neither takes a session id, so
    neither discloses anything about one. If a session-scoped gate ever
    regains a 403, this fails.
    """
    source = (
        __import__("pathlib").Path("app/web/deps.py").read_text()
    )
    assert source.count("HTTP_403_FORBIDDEN") == 1
    before, _, after = source.partition("HTTP_403_FORBIDDEN")
    assert "def require_sys_admin(" in before
    assert "def require_session_operator(" not in before
