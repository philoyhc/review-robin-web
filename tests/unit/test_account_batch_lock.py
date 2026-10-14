"""The Accounts batch's row lock, compiled for Postgres
(guide/admin_pages_refine.md Item 2).

SQLite drops ``FOR UPDATE`` altogether, so no integration test can see
which lock ``users.apply_batch`` takes. Every action but Delete takes
``FOR NO KEY UPDATE``, the mode ``session_guard`` takes on its session
row, which an audit row's foreign-key check (``FOR KEY SHARE`` on its
actor) doesn't wait on, so a bulk Remove from all sessions can't
deadlock against a concurrent owner removal by a selected user. Delete
removes the rows and needs the full ``FOR UPDATE``.
"""

from __future__ import annotations

import pytest
from sqlalchemy.dialects import postgresql

from app.services.users import BATCH_ACTIONS, _batch_lock


def _sql(action: str) -> str:
    return str(_batch_lock(action, [1, 2]).compile(dialect=postgresql.dialect()))


@pytest.mark.parametrize("action", [a for a in BATCH_ACTIONS if a != "delete"])
def test_every_action_but_delete_takes_no_key_update(action: str) -> None:
    assert _sql(action).rstrip().endswith("FOR NO KEY UPDATE")


def test_delete_takes_the_full_lock() -> None:
    sql = _sql("delete").rstrip()
    assert sql.endswith("FOR UPDATE") and "NO KEY" not in sql


@pytest.mark.parametrize("action", ["demote", "delete"])
def test_an_action_that_can_lower_the_admin_count_locks_every_admin(
    action: str,
) -> None:
    assert "users.is_sys_admin IS true" in _sql(action)


@pytest.mark.parametrize(
    "action", [a for a in BATCH_ACTIONS if a not in ("demote", "delete")]
)
def test_others_lock_the_selection_only(action: str) -> None:
    assert "is_sys_admin IS true" not in _sql(action)
    assert "ORDER BY users.id" in _sql(action)


def test_the_locked_rows_are_reread() -> None:
    """A guard never judges a copy loaded earlier in the request."""
    assert _batch_lock("revoke", [1]).get_execution_options()["populate_existing"]
