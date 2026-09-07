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

from app.config import settings
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


def test_the_only_403s_left_are_the_two_that_are_meant_to_be() -> None:
    """The Definition-of-done grep, as an assertion.

    Exactly two ``403``s survive in ``deps.py``, and this pins both so a
    third cannot creep back into a session-scoped gate unnoticed:

    * ``require_sys_admin`` — out of scope from the start. It takes no
      session id, so it discloses nothing about one.
    * ``require_session_operator``'s **sys-admin exemption** (author,
      2026-09-07) — a sys-admin who is not an owner of an existing
      session gets the legible refusal, because
      ``/operator/sys-admin/sessions`` already names every session to
      them and links to this very route.

    ``require_operator`` keeps its 303 and appears in neither count.
    """
    source = (
        __import__("pathlib").Path("app/web/deps.py").read_text()
    )
    assert source.count("status.HTTP_403_FORBIDDEN") == 2
    # And they are in the two functions named above — not, say, both in
    # a participant gate.
    first, _, rest = source.partition("status.HTTP_403_FORBIDDEN")
    assert "def require_sys_admin(" in first
    assert "def require_session_operator(" not in first
    second, _, _tail = rest.partition("status.HTTP_403_FORBIDDEN")
    assert "def require_session_operator(" in second
    assert "def require_reviewer_in_session(" not in second


def test_the_sys_admin_exemption_does_not_invent_sessions(
    db: Session, client: TestClient, make_client, bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The exemption is gated on the session actually existing.

    Without that check it would be a worse leak than the one 19F closed:
    a sys-admin probing ids would get "you are not an owner of this
    session" for ids that have never existed, turning a refusal into a
    confirmation. An existing session they do not own answers 403; an
    absent id answers 404.
    """
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="enum-sysadmin")
    bob_client = make_client(bob)

    existing = bob_client.get(
        f"/operator/sessions/{review_session.id}", follow_redirects=False
    )
    assert existing.status_code == 403

    missing = bob_client.get(
        f"/operator/sessions/{MISSING_SESSION_ID}", follow_redirects=False
    )
    assert missing.status_code == 404
