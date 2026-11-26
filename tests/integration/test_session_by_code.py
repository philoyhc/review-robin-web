"""A session's home named by its code (segment 23J rung 6,
`guide/segment_23J_linked_setup_first.md`): Apply Desk knows the code it
sent, so *Open in Review Robin* links by it. An operator of the session
is redirected home; anyone else, or an unknown code, gets the uniform
404."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, SessionOperator

from .test_handoffs import _bundle, _post


def _made(client: TestClient, db: Session) -> ReviewSession:
    assert _post(client, _bundle()).status_code == 201
    return db.scalars(select(ReviewSession)).one()


def test_an_operator_is_sent_home(client: TestClient, db: Session) -> None:
    review_session = _made(client, db)
    reply = client.get(f"/operator/sessions/by-code/{review_session.code}", follow_redirects=False)
    assert reply.status_code == 307
    assert reply.headers["location"].endswith(f"/operator/sessions/{review_session.public_id}")
    home = client.get(f"/operator/sessions/by-code/{review_session.code}")
    assert home.status_code == 200 and review_session.code in home.text


def test_an_unknown_code_is_not_found(client: TestClient, db: Session) -> None:
    _made(client, db)
    assert client.get("/operator/sessions/by-code/NO-SUCH-CODE").status_code == 404


def test_a_session_the_user_does_not_operate_is_not_found(client: TestClient, db: Session) -> None:
    """The same 404 as an unknown code, so the code of another operator's
    session tells nothing."""
    review_session = _made(client, db)
    for operator in db.scalars(
        select(SessionOperator).where(SessionOperator.session_id == review_session.id)
    ):
        db.delete(operator)
    db.commit()
    reply = client.get(f"/operator/sessions/by-code/{review_session.code}", follow_redirects=False)
    assert reply.status_code == 404


def _not_an_operator(db: Session, review_session: ReviewSession) -> None:
    for operator in db.scalars(
        select(SessionOperator).where(SessionOperator.session_id == review_session.id)
    ):
        db.delete(operator)
    db.commit()


def test_a_sys_admin_is_sent_on_to_the_adopt_door(client: TestClient, db: Session) -> None:
    """The cumulative read: as Session Home answers a sys-admin who is not
    an owner, legibly (`require_session_operator`), a session that exists
    is not hidden from them; an unknown code still is."""
    from app.db.models import User

    review_session = _made(client, db)
    _not_an_operator(db, review_session)
    for user in db.scalars(select(User)):
        user.is_sys_admin = True
    db.commit()
    reply = client.get(f"/operator/sessions/by-code/{review_session.code}", follow_redirects=False)
    assert reply.status_code == 307
    home = client.get(f"/operator/sessions/by-code/{review_session.code}")
    assert home.status_code == 403 and "Adopt it from" in home.text
    assert client.get("/operator/sessions/by-code/NO-SUCH-CODE").status_code == 404
