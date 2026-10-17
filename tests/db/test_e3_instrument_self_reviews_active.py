"""Findings E3: ``instruments.self_reviews_active`` (revision
``f3a7c1e9d5b2``) is backfilled from each instrument's session.

Built on its own in-memory SQLite engine, like
``test_19t13_branch_mode_column``; Postgres runs the same migration
through ``ci-postgres``'s ``upgrade head`` and round-trip.
"""

from __future__ import annotations

from alembic import command
from sqlalchemy import create_engine, inspect, text

from .test_19r2_reconcile_cache_columns import _alembic_config

REVISION = "f3a7c1e9d5b2"
PREVIOUS = "e5c1a9d3b7f2"


def _seed(connection, *, code: str, active: bool) -> int:
    """A session with the given flag and one instrument, by raw SQL —
    the ORM models the head revision, not ``PREVIOUS``."""
    connection.execute(
        text("INSERT INTO users (email, display_name) VALUES (:e, 'O')"),
        {"e": f"op-{code}@example.edu"},
    )
    uid = connection.execute(
        text("SELECT id FROM users WHERE email = :e"),
        {"e": f"op-{code}@example.edu"},
    ).scalar_one()
    connection.execute(
        text(
            "INSERT INTO sessions "
            "(name, code, status, created_by_user_id, self_reviews_active) "
            "VALUES ('S', :code, 'draft', :uid, :active)"
        ),
        {"code": code, "uid": uid, "active": active},
    )
    sid = connection.execute(
        text("SELECT id FROM sessions WHERE code = :code"), {"code": code}
    ).scalar_one()
    connection.execute(
        text(
            "INSERT INTO instruments "
            '(session_id, name, "order", session_seq, accepting_responses) '
            "VALUES (:sid, 'I', 0, 1, 0)"
        ),
        {"sid": sid},
    )
    return connection.execute(
        text("SELECT id FROM instruments WHERE session_id = :sid"),
        {"sid": sid},
    ).scalar_one()


def test_the_column_is_backfilled_from_the_session_and_dropped_again() -> None:
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
    )
    try:
        with eng.connect() as connection:
            cfg = _alembic_config(connection)
            command.upgrade(cfg, PREVIOUS)
            connection.commit()
            on = _seed(connection, code="e3-on", active=True)
            off = _seed(connection, code="e3-off", active=False)
            connection.commit()

            command.upgrade(cfg, REVISION)
            connection.commit()
            column = {
                c["name"]: c
                for c in inspect(connection).get_columns("instruments")
            }["self_reviews_active"]
            assert column["nullable"] is False
            flags = dict(
                connection.execute(
                    text("SELECT id, self_reviews_active FROM instruments")
                ).all()
            )
            assert {k: bool(v) for k, v in flags.items()} == {
                on: True,
                off: False,
            }

            command.downgrade(cfg, PREVIOUS)
            connection.commit()
            assert "self_reviews_active" not in {
                c["name"] for c in inspect(connection).get_columns("instruments")
            }
    finally:
        eng.dispose()
