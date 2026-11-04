"""19V Item 2: ``sessions.form_key`` (revision ``c4e8b2f6a1d9``) is
backfilled with a distinct random secret per session, made ``NOT NULL``,
and dropped again on downgrade.

Built on its own in-memory SQLite engine, like
``test_19v_sessions_public_id``; Postgres runs the same migration through
``ci-postgres``'s ``upgrade head`` and round-trip.
"""

from __future__ import annotations

from alembic import command
from sqlalchemy import create_engine, inspect, text

from .test_19r2_reconcile_cache_columns import _alembic_config

REVISION = "c4e8b2f6a1d9"
PREVIOUS = "a9d4f2c7e1b8"


def _seed(connection, code: str) -> None:
    """A session by raw SQL: the ORM models the head revision."""
    connection.execute(
        text("INSERT INTO users (email, display_name) VALUES (:e, 'O')"),
        {"e": f"op-{code}@example.edu"},
    )
    uid = connection.execute(
        text("SELECT id FROM users WHERE email = :e"), {"e": f"op-{code}@example.edu"}
    ).scalar_one()
    connection.execute(
        text(
            "INSERT INTO sessions (name, code, status, created_by_user_id, public_id) "
            "VALUES ('S', :code, 'draft', :uid, :code)"
        ),
        {"code": code, "uid": uid},
    )


def test_existing_sessions_get_distinct_form_keys_and_lose_them_on_downgrade() -> None:
    eng = create_engine(
        "sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, future=True
    )
    try:
        with eng.connect() as connection:
            cfg = _alembic_config(connection)
            command.upgrade(cfg, PREVIOUS)
            connection.commit()
            for code in ("k1", "k2", "k3"):
                _seed(connection, code)
            connection.commit()

            command.upgrade(cfg, REVISION)
            connection.commit()
            column = {c["name"]: c for c in inspect(connection).get_columns("sessions")}[
                "form_key"
            ]
            assert column["nullable"] is False
            keys = [r[0] for r in connection.execute(text("SELECT form_key FROM sessions"))]
            assert len(keys) == 3 and len(set(keys)) == 3
            assert all(len(k) == 64 and int(k, 16) >= 0 for k in keys)

            command.downgrade(cfg, PREVIOUS)
            connection.commit()
            assert "form_key" not in {
                c["name"] for c in inspect(connection).get_columns("sessions")
            }
    finally:
        eng.dispose()
