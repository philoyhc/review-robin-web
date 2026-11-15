"""Segment 23E: ``sessions.linked_app`` (revision ``d4e7a2c9f1b3``)
leaves every existing session native and drops cleanly.

Built on its own in-memory SQLite engine, as
``test_20m_instruments_display_layout``; Postgres runs the same migration
through ``ci-postgres``'s ``upgrade head`` and round-trip.
"""

from __future__ import annotations

from alembic import command
from sqlalchemy import create_engine, inspect, text

from .test_19r2_reconcile_cache_columns import _alembic_config

REVISION = "d4e7a2c9f1b3"
PREVIOUS = "c3f8a1d6e2b7"


def test_existing_sessions_stay_native_and_the_column_drops_again() -> None:
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
            connection.execute(
                text("INSERT INTO users (email, display_name) VALUES ('op@example.edu', 'O')")
            )
            uid = connection.execute(text("SELECT id FROM users")).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO sessions "
                    "(name, code, status, created_by_user_id, public_id, form_key) "
                    "VALUES ('S', 'e23', 'draft', :uid, 'abcdefghjk', :key)"
                ),
                {"uid": uid, "key": "0" * 64},
            )
            connection.commit()

            command.upgrade(cfg, REVISION)
            connection.commit()
            column = {c["name"]: c for c in inspect(connection).get_columns("sessions")}[
                "linked_app"
            ]
            assert column["nullable"] is True
            assert connection.execute(text("SELECT linked_app FROM sessions")).scalar_one() is None

            command.downgrade(cfg, PREVIOUS)
            connection.commit()
            names = {c["name"] for c in inspect(connection).get_columns("sessions")}
            assert "linked_app" not in names
    finally:
        eng.dispose()
