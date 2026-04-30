from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[2]


def _alembic_config(connection) -> Config:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    cfg.attributes["connection"] = connection
    return cfg


def test_upgrade_replaces_pair_context_rows_and_seeds_three_per_instrument() -> None:
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
    )
    try:
        with eng.connect() as connection:
            cfg = _alembic_config(connection)
            command.upgrade(cfg, "4e8a2b9c3d11")
            connection.commit()
            connection.execute(
                text(
                    "INSERT INTO users (email, display_name) "
                    "VALUES ('op@example.edu', 'Op')"
                )
            )
            user_id = connection.execute(
                text("SELECT id FROM users WHERE email = 'op@example.edu'")
            ).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO sessions "
                    "(name, code, status, created_by_user_id) "
                    "VALUES ('S', 'pre', 'draft', :uid)"
                ),
                {"uid": user_id},
            )
            session_id = connection.execute(
                text("SELECT id FROM sessions WHERE code = 'pre'")
            ).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO instruments "
                    '(session_id, name, "order", accepting_responses, '
                    "responses_visible_when_closed) "
                    "VALUES (:sid, 'instrument_1', 0, 0, 0)"
                ),
                {"sid": session_id},
            )
            instrument_id = connection.execute(
                text("SELECT id FROM instruments WHERE session_id = :sid"),
                {"sid": session_id},
            ).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO instrument_display_fields "
                    '(instrument_id, source_type, source_field, label, "order", visible) '
                    "VALUES (:iid, 'pair_context', '1', 'Stale', 5, 1), "
                    "       (:iid, 'reviewee', 'tag_1', 'Cohort', 6, 1)"
                ),
                {"iid": instrument_id},
            )
            connection.commit()

            command.upgrade(cfg, "head")
            connection.commit()

            rows = connection.execute(
                text(
                    "SELECT source_type, source_field, label, \"order\", visible "
                    "FROM instrument_display_fields "
                    "WHERE instrument_id = :iid "
                    "ORDER BY \"order\""
                ),
                {"iid": instrument_id},
            ).fetchall()
        assert [tuple(r) for r in rows] == [
            ("pair_context", "1", "", 0, 1),
            ("pair_context", "2", "", 1, 1),
            ("pair_context", "3", "", 2, 1),
            ("reviewee", "tag_1", "Cohort", 6, 1),
        ]
    finally:
        eng.dispose()
