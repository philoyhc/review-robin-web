"""Owner adds and revokes serialize on the user row (Codex on #3037).

An owner row's foreign-key check takes only ``FOR KEY SHARE`` on the
user, which passes the lock a revoke holds, so an owner add that read
``is_operator`` unlocked could commit beside a revoke that counted no
owned sessions: a non-operator owner. Every path that writes an owner
row now re-reads the user ``FOR SHARE`` first
(``session_owners.lock_owner_eligible``), and the single-row revoke
takes the batch's lock before it counts.

SQLite ignores row locks, so the conflict itself is shown on Postgres
only (the ``ci-postgres`` job); the rest runs everywhere.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, text, update
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, SessionOperator, User
from app.services import session_owners
from app.services import users as users_service


def _seed(db: Session, email: str, **flags: bool) -> User:
    user = User(email=email, **flags)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _stale_revoke(db: Session, user: User) -> None:
    """Clear the flag in the table but not on the loaded object, as a
    revoke committed by another request leaves it."""
    db.execute(
        update(User)
        .where(User.id == user.id)
        .values(is_operator=False)
        .execution_options(synchronize_session=False)
    )
    db.commit()
    assert user.is_operator  # the object still says operator


def test_the_lock_is_for_share_and_rereads_the_row() -> None:
    statement = session_owners._eligibility_lock(1)
    assert str(statement.compile(dialect=postgresql.dialect())).rstrip().endswith(
        "FOR SHARE"
    )
    assert statement.get_execution_options()["populate_existing"] is True


def test_add_owner_refuses_a_target_revoked_since_it_was_loaded(
    db: Session, client: TestClient
) -> None:
    client.post("/operator/sessions", data={"name": "S", "code": "lock-add"})
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "lock-add")
    ).scalar_one()
    actor = db.get(User, review_session.created_by_user_id)
    bob = _seed(db, "bob@example.edu", is_operator=True)
    _stale_revoke(db, bob)
    with pytest.raises(session_owners.OwnerOperationError) as refused:
        session_owners.add_owner(
            db, review_session=review_session, actor=actor, target=bob
        )
    assert refused.value.code == "not_in_workspace"
    assert db.execute(
        select(SessionOperator).where(SessionOperator.user_id == bob.id)
    ).first() is None


def test_single_row_revoke_takes_the_batch_lock_before_counting(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    actor = _seed(db, "admin@example.edu", is_operator=True, is_sys_admin=True)
    bob = _seed(db, "bob@example.edu", is_operator=True)
    calls: list[tuple[str, list[int]]] = []
    real = users_service._batch_lock

    def spy(action: str, ids: list[int]):
        calls.append((action, ids))
        return real(action, ids)

    monkeypatch.setattr(users_service, "_batch_lock", spy)
    users_service.revoke(db, actor=actor, target=bob)
    assert calls == [("revoke", [bob.id])]
    assert not bob.is_operator


def test_create_bounces_a_creator_revoked_since_the_gate(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(session_owners, "lock_owner_eligible", lambda db, user: False)
    response = client.post(
        "/operator/sessions",
        data={"name": "S", "code": "lock-create"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith("/me")
    assert db.execute(
        select(ReviewSession).where(ReviewSession.code == "lock-create")
    ).first() is None


def test_duplicate_bounces_a_creator_revoked_since_the_gate(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.post("/operator/sessions", data={"name": "S", "code": "lock-clone"})
    source = db.execute(
        select(ReviewSession).where(ReviewSession.code == "lock-clone")
    ).scalar_one()
    monkeypatch.setattr(session_owners, "lock_owner_eligible", lambda db, user: False)
    response = client.post(
        f"/operator/sessions/{source.id}/clone",
        data={"mode": "config"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith("/me")
    assert db.execute(select(ReviewSession)).scalars().all() == [source]


def test_create_keeps_the_session_when_a_staged_owner_was_revoked(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Revoked between the form's check and the owner write: the lock
    refuses them, and Create lands on the new session, not a 500."""
    bob = _seed(db, "bob@example.edu", is_operator=True)
    real = session_owners.lock_owner_eligible
    monkeypatch.setattr(
        session_owners,
        "lock_owner_eligible",
        lambda db, user: False if user.id == bob.id else real(db, user),
    )
    response = client.post(
        "/operator/sessions",
        data={"name": "S", "code": "lock-staged", "owners": ["bob@example.edu"]},
        follow_redirects=False,
    )
    assert response.status_code == 303
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "lock-staged")
    ).scalar_one()
    owners = db.execute(
        select(SessionOperator.user_id).where(
            SessionOperator.session_id == review_session.id
        )
    ).scalars().all()
    assert owners == [review_session.created_by_user_id]


# --- The conflict itself, on Postgres ----------------------------------------


@pytest.fixture
def pg_users(engine: Engine):
    if engine.dialect.name != "postgresql":
        pytest.skip("row locks need Postgres (the ci-postgres job)")
    token = uuid.uuid4().hex[:8]
    with Session(engine) as setup:
        admin = User(
            email=f"lock-{token}-admin@example.edu", is_operator=True, is_sys_admin=True
        )
        bob = User(email=f"lock-{token}-bob@example.edu", is_operator=True)
        setup.add_all([admin, bob])
        setup.commit()
        ids = (admin.id, bob.id)
    yield ids
    with Session(engine) as cleanup:
        cleanup.execute(
            text("DELETE FROM audit_events WHERE actor_user_id = ANY(:ids)"),
            {"ids": list(ids)},
        )
        cleanup.execute(
            text("DELETE FROM users WHERE id = ANY(:ids)"), {"ids": list(ids)}
        )
        cleanup.commit()


def _short_wait(session: Session) -> None:
    session.execute(text("SET LOCAL lock_timeout = '300ms'"))


def test_an_owner_add_holds_off_a_revoke(engine: Engine, pg_users) -> None:
    admin_id, bob_id = pg_users
    with Session(engine) as adding, Session(engine) as revoking:
        assert session_owners.lock_owner_eligible(adding, adding.get(User, bob_id))
        _short_wait(revoking)
        with pytest.raises(OperationalError, match="lock timeout"):
            users_service.apply_batch(
                revoking,
                actor=revoking.get(User, admin_id),
                action="revoke",
                user_ids=[bob_id],
            )


def test_a_revoke_holds_off_an_owner_add(engine: Engine, pg_users) -> None:
    _, bob_id = pg_users
    with Session(engine) as revoking, Session(engine) as adding:
        revoking.execute(users_service._batch_lock("revoke", [bob_id]))
        _short_wait(adding)
        with pytest.raises(OperationalError, match="lock timeout"):
            session_owners.lock_owner_eligible(adding, adding.get(User, bob_id))
