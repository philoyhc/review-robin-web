"""Segment 19Y Item 1: ``instruments.intro_layout`` (revision
``c4e9a2f7b1d3``) gives every existing instrument the default
``layout_1`` and drops cleanly.

Built on its own in-memory SQLite engine, like
``test_e3_instrument_self_reviews_active``; Postgres runs the same
migration through ``ci-postgres``'s ``upgrade head`` and round-trip.
"""

from __future__ import annotations

from alembic import command
from sqlalchemy import create_engine, inspect, text

from .test_19r2_reconcile_cache_columns import _alembic_config

REVISION = "c4e9a2f7b1d3"
PREVIOUS = "e8b3c1d4f6a2"


def test_existing_instruments_take_layout_1_and_the_column_drops_again() -> None:
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
                    "VALUES ('S', 'y19', 'draft', :uid, 'abcdefghjk', :key)"
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
            column = {
                c["name"]: c
                for c in inspect(connection).get_columns("instruments")
            }["intro_layout"]
            assert column["nullable"] is False
            assert connection.execute(
                text("SELECT intro_layout FROM instruments")
            ).scalar_one() == "layout_1"

            command.downgrade(cfg, PREVIOUS)
            connection.commit()
            assert "intro_layout" not in {
                c["name"] for c in inspect(connection).get_columns("instruments")
            }
    finally:
        eng.dispose()
