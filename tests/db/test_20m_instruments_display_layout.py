"""Segment 20M: ``instruments.display_layout`` (revision
``c3f8a1d6e2b7``) gives every existing instrument the default
``across`` and drops cleanly.

Built on its own in-memory SQLite engine, like
``test_e3_instrument_self_reviews_active``; Postgres runs the same
migration through ``ci-postgres``'s ``upgrade head`` and round-trip.
"""

from __future__ import annotations

from alembic import command
from sqlalchemy import create_engine, inspect, text

from .test_19r2_reconcile_cache_columns import _alembic_config

REVISION = "c3f8a1d6e2b7"
PREVIOUS = "b9e2d4f7a1c6"


def test_existing_instruments_take_across_and_the_column_drops_again() -> None:
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
            # By raw SQL: the ORM models the head revision, not PREVIOUS.
            connection.execute(
                text("INSERT INTO users (email, display_name) VALUES ('op@example.edu', 'O')")
            )
            uid = connection.execute(text("SELECT id FROM users")).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO sessions "
                    "(name, code, status, created_by_user_id, public_id, form_key) "
                    "VALUES ('S', 'm20', 'draft', :uid, 'abcdefghjk', :key)"
                ),
                {"uid": uid, "key": "0" * 64},
            )
            sid = connection.execute(text("SELECT id FROM sessions")).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO instruments "
                    '(session_id, name, "order", session_seq, accepting_responses) '
                    "VALUES (:sid, 'I', 0, 1, 0)"
                ),
                {"sid": sid},
            )
            connection.commit()

            command.upgrade(cfg, REVISION)
            connection.commit()
            column = {c["name"]: c for c in inspect(connection).get_columns("instruments")}[
                "display_layout"
            ]
            assert column["nullable"] is False
            assert (
                connection.execute(text("SELECT display_layout FROM instruments")).scalar_one()
                == "across"
            )

            command.downgrade(cfg, PREVIOUS)
            connection.commit()
            assert "display_layout" not in {
                c["name"] for c in inspect(connection).get_columns("instruments")
            }
    finally:
        eng.dispose()
