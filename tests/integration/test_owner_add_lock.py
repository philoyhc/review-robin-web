"""Owner adds and revokes serialize on the user row (Codex on #3037).

An owner row's foreign-key check takes only ``FOR KEY SHARE`` on the
user, which passes the lock a revoke holds, so an owner add that read
``is_operator`` unlocked could commit beside a revoke that counted no
owned sessions: a non-operator owner. Every path that writes an owner
row now re-reads the user ``FOR SHARE`` first
(``session_owners.lock_owner_eligible``): ``add_owner``, and the creator
on Create, Duplicate and Rehydrate; and the single-row revoke takes the
batch's lock before it counts.

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
    """Order matters: counted before the lock, a revoke would wait on an
    add's ``FOR SHARE`` and then commit anyway, the add uncounted."""
    actor = _seed(db, "admin@example.edu", is_operator=True, is_sys_admin=True)
    bob = _seed(db, "bob@example.edu", is_operator=True)
    steps: list[str] = []
    real_lock = users_service._batch_lock
    real_count = users_service._guard_not_owner

    def lock(action: str, ids: list[int]):
        steps.append(f"lock {action} {ids == [bob.id]}")
        return real_lock(action, ids)

    def count(db: Session, target: User) -> None:
        steps.append("count")
        real_count(db, target)

    monkeypatch.setattr(users_service, "_batch_lock", lock)
    monkeypatch.setattr(users_service, "_guard_not_owner", count)
    users_service.revoke(db, actor=actor, target=bob)
    assert steps == ["lock revoke True", "count"]
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


def test_create_skips_a_staged_owner_revoked_since_the_check(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Revoked between the form's check and the owner write: the lock
    refuses them, the owners staged after them still land, and Create
    lands on the new session, not a 500."""
    bob = _seed(db, "bob@example.edu", is_operator=True)
    carl = _seed(db, "carl@example.edu", is_operator=True)
    real = session_owners.lock_owner_eligible
    monkeypatch.setattr(
        session_owners,
        "lock_owner_eligible",
        lambda db, user: False if user.id == bob.id else real(db, user),
    )
    response = client.post(
        "/operator/sessions",
        data={
            "name": "S",
            "code": "lock-staged",
            "owners": ["bob@example.edu", "carl@example.edu"],
        },
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
    assert sorted(owners) == sorted([review_session.created_by_user_id, carl.id])


# --- The conflict itself, on Postgres ----------------------------------------
#
# Each test holds one side's lock open in a transaction, as that side does
# between its check and its commit, and drives the other side through its
# real service function with a short ``lock_timeout``: the timeout is the
# proof that it waited.


@pytest.fixture
def pg_seed(engine: Engine):
    if engine.dialect.name != "postgresql":
        pytest.skip("row locks need Postgres (the ci-postgres job)")
    token = uuid.uuid4().hex[:8]
    with Session(engine) as setup:
        admin = User(
            email=f"lock-{token}-admin@example.edu", is_operator=True, is_sys_admin=True
        )
        bob = User(email=f"lock-{token}-bob@example.edu", is_operator=True)
        setup.add_all([admin, bob])
        setup.flush()
        review_session = ReviewSession(
            name="Lock", code=f"lock-{token}", created_by_user_id=admin.id
        )
        setup.add(review_session)
        setup.flush()
        setup.add(
            SessionOperator(
                session_id=review_session.id, user_id=admin.id, role="owner"
            )
        )
        setup.commit()
        ids = (admin.id, bob.id, review_session.id)
    yield ids
    with Session(engine) as cleanup:
        user_ids = list(ids[:2])
        cleanup.execute(
            text("DELETE FROM audit_events WHERE actor_user_id = ANY(:ids)"),
            {"ids": user_ids},
        )
        cleanup.execute(
            text("DELETE FROM session_operators WHERE session_id = :sid"),
            {"sid": ids[2]},
        )
        cleanup.execute(text("DELETE FROM sessions WHERE id = :sid"), {"sid": ids[2]})
        cleanup.execute(
            text("DELETE FROM users WHERE id = ANY(:ids)"), {"ids": user_ids}
        )
        cleanup.commit()


def _short_wait(session: Session) -> None:
    session.execute(text("SET LOCAL lock_timeout = '300ms'"))


@pytest.mark.parametrize("path", ["single", "bulk"])
def test_an_owner_add_holds_off_a_revoke(
    engine: Engine, pg_seed, path: str
) -> None:
    admin_id, bob_id, _ = pg_seed
    with Session(engine) as adding, Session(engine) as revoking:
        assert session_owners.lock_owner_eligible(adding, adding.get(User, bob_id))
        _short_wait(revoking)
        actor = revoking.get(User, admin_id)
        with pytest.raises(OperationalError, match="lock timeout") as waited:
            if path == "single":
                users_service.revoke(
                    revoking, actor=actor, target=revoking.get(User, bob_id)
                )
            else:
                users_service.apply_batch(
                    revoking, actor=actor, action="revoke", user_ids=[bob_id]
                )
        # The revoke's own row lock is what waited, not its later UPDATE:
        # counted before the lock, the count would miss the add.
        assert "FOR NO KEY UPDATE" in str(waited.value.statement)


def test_a_revoke_holds_off_an_owner_add(engine: Engine, pg_seed) -> None:
    admin_id, bob_id, session_id = pg_seed
    with Session(engine) as revoking, Session(engine) as adding:
        revoking.execute(users_service._batch_lock("revoke", [bob_id]))
        _short_wait(adding)
        with pytest.raises(OperationalError, match="lock timeout"):
            session_owners.add_owner(
                adding,
                review_session=adding.get(ReviewSession, session_id),
                actor=adding.get(User, admin_id),
                target=adding.get(User, bob_id),
            )
