"""19T Item 13 rung 2: ``instrument_response_fields.branch_mode``.

Rung 2 lands the column with no write path, so what there is to assert
is its shape and that it survives both directions of the chain. Like
``test_19r2_reconcile_cache_columns``, this builds its own in-memory
SQLite engine; Postgres sees the column through ``ci-postgres``'s own
``downgrade base + upgrade head``.
"""

from __future__ import annotations

from alembic import command
from sqlalchemy import create_engine, inspect

from app.db.models import InstrumentResponseField

from .test_19r2_reconcile_cache_columns import _alembic_config

REVISION = "c4e9a1d27b58"
PREVIOUS = "63b1bb107eb0"


def _columns(connection) -> dict[str, dict]:
    return {
        c["name"]: c
        for c in inspect(connection).get_columns("instrument_response_fields")
    }


def test_rung_2_adds_a_nullable_branch_mode_and_drops_it_again() -> None:
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
            before = _columns(connection)
            # Standing at the branching revision, without the mode.
            assert "branch_op" in before and "branch_mode" not in before

            command.upgrade(cfg, REVISION)
            connection.commit()
            column = _columns(connection)["branch_mode"]
            assert column["nullable"] is True
            assert str(column["type"]) == "VARCHAR(8)"
            # The ORM agrees with the migration.
            assert InstrumentResponseField.__table__.c.branch_mode.type.length == 8

            command.downgrade(cfg, PREVIOUS)
            connection.commit()
            assert "branch_mode" not in _columns(connection)
    finally:
        eng.dispose()
