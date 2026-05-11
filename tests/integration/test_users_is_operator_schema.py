"""Schema-level coverage for the Segment 13F PR 2 ``users.is_operator`` column.

Round-trips the new column. The column is inert today — no
service module reads ``is_operator``.

The column sits inert until Segment 16A PR 1 wires
``require_operator`` (the gate on every operator route under
the Option C strict-allowlist access model) and the
``OPERATOR_EMAILS`` env-var bootstrap on first-sign-in.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User


def test_users_is_operator_defaults_to_false(db: Session) -> None:
    user = User(email="default@example.edu", display_name="Default")
    db.add(user)
    db.flush()

    reread = db.execute(select(User).where(User.id == user.id)).scalar_one()
    assert reread.is_operator is False


def test_users_is_operator_round_trips_true(db: Session) -> None:
    user = User(
        email="op@example.edu",
        display_name="Op",
        is_operator=True,
    )
    db.add(user)
    db.flush()

    reread = db.execute(select(User).where(User.id == user.id)).scalar_one()
    assert reread.is_operator is True


def test_users_is_operator_flip_persists(db: Session) -> None:
    user = User(email="flip@example.edu", display_name="Flip")
    db.add(user)
    db.flush()
    assert user.is_operator is False

    user.is_operator = True
    db.flush()
    db.expire(user)
    assert user.is_operator is True

    user.is_operator = False
    db.flush()
    db.expire(user)
    assert user.is_operator is False


def test_users_is_operator_independent_of_is_sys_admin(db: Session) -> None:
    """The two flags are independent at the column level — sys-admin
    *implying* operator is enforced at the read-path predicate
    (16A PR 1's ``require_operator``), not at the column level.
    Today both columns can hold any (False, False) / (False, True)
    / (True, False) / (True, True) combination."""

    sysadmin_only = User(
        email="sysadmin-only@example.edu",
        display_name="Sysadmin Only",
        is_sys_admin=True,
        is_operator=False,
    )
    operator_only = User(
        email="operator-only@example.edu",
        display_name="Operator Only",
        is_sys_admin=False,
        is_operator=True,
    )
    both = User(
        email="both@example.edu",
        display_name="Both",
        is_sys_admin=True,
        is_operator=True,
    )
    db.add_all([sysadmin_only, operator_only, both])
    db.flush()

    for user in (sysadmin_only, operator_only, both):
        db.expire(user)

    assert (sysadmin_only.is_sys_admin, sysadmin_only.is_operator) == (True, False)
    assert (operator_only.is_sys_admin, operator_only.is_operator) == (False, True)
    assert (both.is_sys_admin, both.is_operator) == (True, True)
