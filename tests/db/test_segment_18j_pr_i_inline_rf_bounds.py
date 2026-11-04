"""Regression tests for the Segment 18J Wave 2 PR i migration that
adds the inline bound columns to ``instrument_response_fields`` and
backfills them from each row's pointed-at RTD."""

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


def test_pr_i_migration_backfills_inline_bounds_from_rtd() -> None:
    """Stand up the pre-PR-i schema, insert a few RTD-pointed
    InstrumentResponseField rows, then run the PR-i migration and
    assert each row's inline columns now mirror its RTD."""
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
    )
    try:
        with eng.connect() as connection:
            cfg = _alembic_config(connection)
            # Step to the revision immediately before PR i.
            command.upgrade(cfg, "e7c2b4d9a3f1")
            connection.commit()

            # Minimal seed for an InstrumentResponseField row + its
            # RTD. ``InstrumentResponseField`` requires
            # instrument → session → user.
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
                    "VALUES ('S', 'pre18j', 'draft', :uid)"
                ),
                {"uid": user_id},
            )
            session_id = connection.execute(
                text("SELECT id FROM sessions WHERE code = 'pre18j'")
            ).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO instruments "
                    '(session_id, name, "order", accepting_responses, '
                    "responses_visible_when_closed) "
                    "VALUES (:sid, 'I1', 0, 0, 0)"
                ),
                {"sid": session_id},
            )
            instrument_id = connection.execute(
                text("SELECT id FROM instruments WHERE session_id = :sid"),
                {"sid": session_id},
            ).scalar_one()

            # Three RTDs: numeric (1-5 integer), string (short),
            # and list (yes/no).
            connection.execute(
                text(
                    "INSERT INTO response_type_definitions "
                    "(session_id, response_type, data_type, "
                    "min, max, step, list_csv, is_seeded, seed_order) "
                    "VALUES "
                    "(:sid, '1-to-5int', 'Integer', 1, 5, 1, NULL, 0, 0), "
                    "(:sid, 'Short_text', 'String', NULL, 80, NULL, NULL, 0, 0), "
                    "(:sid, 'Yes_no', 'List', NULL, NULL, NULL, 'Yes,No', 0, 0)"
                ),
                {"sid": session_id},
            )
            rtd_ids = {
                r[0]: r[1]
                for r in connection.execute(
                    text(
                        "SELECT response_type, id FROM response_type_definitions "
                        "WHERE session_id = :sid"
                    ),
                    {"sid": session_id},
                ).fetchall()
            }

            for key, rtd_name in (
                ("rating", "1-to-5int"),
                ("notes", "Short_text"),
                ("yes_no", "Yes_no"),
            ):
                connection.execute(
                    text(
                        "INSERT INTO instrument_response_fields "
                        '(instrument_id, field_key, label, response_type_id, '
                        'required, "order") '
                        "VALUES (:iid, :key, :label, :rtd, 0, 0)"
                    ),
                    {
                        "iid": instrument_id,
                        "key": key,
                        "label": key.title(),
                        "rtd": rtd_ids[rtd_name],
                    },
                )
            connection.commit()

            # Upgrade through PR i.
            command.upgrade(cfg, "f9c2d8a4b7e1")
            connection.commit()

            rows = connection.execute(
                text(
                    "SELECT field_key, data_type, response_type, "
                    "min, max, step, list_csv "
                    "FROM instrument_response_fields "
                    "WHERE instrument_id = :iid "
                    "ORDER BY field_key"
                ),
                {"iid": instrument_id},
            ).fetchall()

        by_key = {r[0]: r for r in rows}
        # Numeric row: bounds inlined as floats; list_csv NULL.
        assert by_key["rating"][1] == "Integer"
        assert by_key["rating"][2] == "1-to-5int"
        assert by_key["rating"][3] == 1.0
        assert by_key["rating"][4] == 5.0
        assert by_key["rating"][5] == 1.0
        assert by_key["rating"][6] is None
        # String row: max carries char-length cap; min/step NULL;
        # list_csv NULL.
        assert by_key["notes"][1] == "String"
        assert by_key["notes"][2] == "Short_text"
        assert by_key["notes"][3] is None
        assert by_key["notes"][4] == 80.0
        assert by_key["notes"][5] is None
        assert by_key["notes"][6] is None
        # List row: list_csv carries options; numeric bounds NULL.
        assert by_key["yes_no"][1] == "List"
        assert by_key["yes_no"][2] == "Yes_no"
        assert by_key["yes_no"][3] is None
        assert by_key["yes_no"][4] is None
        assert by_key["yes_no"][5] is None
        assert by_key["yes_no"][6] == "Yes,No"
    finally:
        eng.dispose()
