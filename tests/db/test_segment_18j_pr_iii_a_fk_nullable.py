"""Regression test for Segment 18J Wave 2 PR iii-a: makes
``instrument_response_fields.response_type_id`` nullable so iii-b
can land NULL refs on non-List fields before retiring the seeded
non-List RTDs."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

REPO_ROOT = Path(__file__).resolve().parents[2]


def _alembic_config(connection) -> Config:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    cfg.attributes["connection"] = connection
    return cfg


def test_pr_iii_a_makes_response_type_id_nullable() -> None:
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
    )
    try:
        with eng.connect() as connection:
            cfg = _alembic_config(connection)
            # Step to the revision immediately before iii-a.
            command.upgrade(cfg, "f9c2d8a4b7e1")
            connection.commit()

            inspector_before = inspect(connection)
            cols_before = {
                c["name"]: c
                for c in inspector_before.get_columns(
                    "instrument_response_fields"
                )
            }
            # Pre-iii-a: column is NOT NULL.
            assert cols_before["response_type_id"]["nullable"] is False

            command.upgrade(cfg, "b1e8f3c47d92")
            connection.commit()

            inspector_after = inspect(connection)
            cols_after = {
                c["name"]: c
                for c in inspector_after.get_columns(
                    "instrument_response_fields"
                )
            }
            assert cols_after["response_type_id"]["nullable"] is True

            # And the column can actually hold NULL — exercise the
            # write path with a minimal seed.
            connection.execute(
                text(
                    "INSERT INTO users (email, display_name) "
                    "VALUES ('o@x', 'O')"
                )
            )
            uid = connection.execute(
                text("SELECT id FROM users WHERE email = 'o@x'")
            ).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO sessions "
                    "(name, code, status, created_by_user_id) "
                    "VALUES ('S', 'iii-a', 'draft', :uid)"
                ),
                {"uid": uid},
            )
            sid = connection.execute(
                text("SELECT id FROM sessions WHERE code = 'iii-a'")
            ).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO instruments "
                    '(session_id, name, "order", accepting_responses, '
                    "responses_visible_when_closed) "
                    "VALUES (:sid, 'I', 0, 0, 0)"
                ),
                {"sid": sid},
            )
            iid = connection.execute(
                text("SELECT id FROM instruments WHERE session_id = :sid"),
                {"sid": sid},
            ).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO instrument_response_fields "
                    '(instrument_id, field_key, label, response_type_id, '
                    'required, "order") '
                    "VALUES (:iid, 'k', 'L', NULL, 0, 0)"
                ),
                {"iid": iid},
            )
            row = connection.execute(
                text(
                    "SELECT field_key, response_type_id "
                    "FROM instrument_response_fields "
                    "WHERE instrument_id = :iid"
                ),
                {"iid": iid},
            ).first()
            assert row is not None
            assert row[0] == "k"
            assert row[1] is None
    finally:
        eng.dispose()
