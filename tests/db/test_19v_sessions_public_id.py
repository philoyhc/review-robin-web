"""19V Item 1: ``sessions.public_id`` (revision ``a9d4f2c7e1b8``) is
backfilled with a distinct random value per session, made ``NOT NULL``
with a unique index, and dropped again on downgrade.

Built on its own in-memory SQLite engine, like
``test_e3_instrument_self_reviews_active``; Postgres runs the same
migration through ``ci-postgres``'s ``upgrade head`` and round-trip.
"""

from __future__ import annotations

from alembic import command
from sqlalchemy import create_engine, inspect, text

from app.db.models.review_session import PUBLIC_ID_ALPHABET, PUBLIC_ID_LENGTH

from .test_19r2_reconcile_cache_columns import _alembic_config

REVISION = "a9d4f2c7e1b8"
PREVIOUS = "f3a7c1e9d5b2"


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
            "INSERT INTO sessions (name, code, status, created_by_user_id) "
            "VALUES ('S', :code, 'draft', :uid)"
        ),
        {"code": code, "uid": uid},
    )


def test_existing_sessions_get_distinct_public_ids_and_lose_them_on_downgrade() -> None:
    eng = create_engine(
        "sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, future=True
    )
    try:
        with eng.connect() as connection:
            cfg = _alembic_config(connection)
            command.upgrade(cfg, PREVIOUS)
            connection.commit()
            for code in ("v1", "v2", "v3"):
                _seed(connection, code)
            connection.commit()

            command.upgrade(cfg, REVISION)
            connection.commit()
            column = {c["name"]: c for c in inspect(connection).get_columns("sessions")}[
                "public_id"
            ]
            assert column["nullable"] is False
            index = {i["name"]: i for i in inspect(connection).get_indexes("sessions")}[
                "ix_sessions_public_id"
            ]
            assert index["unique"]
            ids = [r[0] for r in connection.execute(text("SELECT public_id FROM sessions"))]
            assert len(ids) == 3 and len(set(ids)) == 3
            for value in ids:
                assert len(value) == PUBLIC_ID_LENGTH
                assert set(value) <= set(PUBLIC_ID_ALPHABET)

            command.downgrade(cfg, PREVIOUS)
            connection.commit()
            assert "public_id" not in {
                c["name"] for c in inspect(connection).get_columns("sessions")
            }
    finally:
        eng.dispose()
