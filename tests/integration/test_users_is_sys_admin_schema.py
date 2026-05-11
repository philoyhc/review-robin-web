"""Schema-level coverage for the Segment 13F PR 1 ``users.is_sys_admin`` column.

Round-trips the new column and pins the canonical
``SESSION_OPERATOR_ROLES`` value-set. Both changes are inert
today — no service module reads ``is_sys_admin`` and no code
path writes a ``role`` other than ``"owner"``.

The column sits inert until Segment 16A PRs 1-2 wire the
bootstrap read + the ``require_sys_admin`` dependency; the
value-set constant sits inert until Segment 16B PR 1 starts
policing role writes.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, SessionOperator, User
from app.db.models.session_operator import SESSION_OPERATOR_ROLES


def test_users_is_sys_admin_defaults_to_false(db: Session) -> None:
    user = User(email="default@example.edu", display_name="Default")
    db.add(user)
    db.flush()

    reread = db.execute(select(User).where(User.id == user.id)).scalar_one()
    assert reread.is_sys_admin is False


def test_users_is_sys_admin_round_trips_true(db: Session) -> None:
    user = User(
        email="admin@example.edu",
        display_name="Admin",
        is_sys_admin=True,
    )
    db.add(user)
    db.flush()

    reread = db.execute(select(User).where(User.id == user.id)).scalar_one()
    assert reread.is_sys_admin is True


def test_users_is_sys_admin_flip_persists(db: Session) -> None:
    user = User(email="flip@example.edu", display_name="Flip")
    db.add(user)
    db.flush()
    assert user.is_sys_admin is False

    user.is_sys_admin = True
    db.flush()
    db.expire(user)
    assert user.is_sys_admin is True

    user.is_sys_admin = False
    db.flush()
    db.expire(user)
    assert user.is_sys_admin is False


def test_session_operator_role_default_is_owner(db: Session) -> None:
    """The Python-side default flipped from "operator" to "owner"
    in Segment 13F PR 1 to match the only value any code actually
    writes (``sessions.create_session`` writes the creator as
    ``role="owner"`` at create-time)."""

    creator = User(email="creator@example.edu", display_name="Creator")
    db.add(creator)
    db.flush()

    session = ReviewSession(name="S", code="S001", created_by_user_id=creator.id)
    db.add(session)
    db.flush()

    # Don't pass role explicitly — let the model default fire.
    op_row = SessionOperator(session_id=session.id, user_id=creator.id)
    db.add(op_row)
    db.flush()

    reread = db.execute(
        select(SessionOperator).where(SessionOperator.id == op_row.id)
    ).scalar_one()
    assert reread.role == "owner"


def test_session_operator_roles_value_set() -> None:
    """The locked value-set constant. Widening is a deliberate
    Python edit; today only "owner" is in active use,
    "manager" is reserved for the Segment 16B less-rights role."""

    assert SESSION_OPERATOR_ROLES == ("owner", "manager")
    assert "owner" in SESSION_OPERATOR_ROLES
    assert "manager" in SESSION_OPERATOR_ROLES
    # Today no other role values are blessed:
    assert "operator" not in SESSION_OPERATOR_ROLES
    assert "viewer" not in SESSION_OPERATOR_ROLES
