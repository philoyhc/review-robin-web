from __future__ import annotations

import json
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


def _seed_minimal_session(connection, *, code: str) -> tuple[int, int]:
    connection.execute(
        text(
            "INSERT INTO users (email, display_name) "
            "VALUES (:email, 'Op') "
            "ON CONFLICT(email) DO NOTHING"
        ),
        {"email": f"op-{code}@example.edu"},
    )
    user_id = connection.execute(
        text("SELECT id FROM users WHERE email = :email"),
        {"email": f"op-{code}@example.edu"},
    ).scalar_one()
    connection.execute(
        text(
            "INSERT INTO sessions "
            "(name, code, status, created_by_user_id) "
            "VALUES ('S', :code, 'draft', :uid)"
        ),
        {"code": code, "uid": user_id},
    )
    session_id = connection.execute(
        text("SELECT id FROM sessions WHERE code = :code"),
        {"code": code},
    ).scalar_one()
    connection.execute(
        text(
            "INSERT INTO instruments "
            "(session_id, name, \"order\", accepting_responses, "
            "responses_visible_when_closed) "
            "VALUES (:sid, 'Default', 0, 0, 0)"
        ),
        {"sid": session_id},
    )
    instrument_id = connection.execute(
        text("SELECT id FROM instruments WHERE session_id = :sid"),
        {"sid": session_id},
    ).scalar_one()
    # Pre-c2143bd329c7 seed: every instrument has three pair_context rows.
    for slot, order in (("1", 0), ("2", 1), ("3", 2)):
        connection.execute(
            text(
                "INSERT INTO instrument_display_fields "
                "(instrument_id, source_type, source_field, label, \"order\", visible) "
                "VALUES (:iid, 'pair_context', :sf, '', :ord, 1)"
            ),
            {"iid": instrument_id, "sf": slot, "ord": order},
        )
    return session_id, instrument_id


def _seed_reviewer_and_reviewee(connection, *, session_id: int) -> tuple[int, int]:
    connection.execute(
        text(
            "INSERT INTO reviewers (session_id, name, email, status) "
            "VALUES (:sid, 'R', :email, 'active')"
        ),
        {"sid": session_id, "email": f"r-{session_id}@example.edu"},
    )
    reviewer_id = connection.execute(
        text(
            "SELECT id FROM reviewers WHERE session_id = :sid"
        ),
        {"sid": session_id},
    ).scalar_one()
    connection.execute(
        text(
            "INSERT INTO reviewees "
            "(session_id, name, email_or_identifier, status) "
            "VALUES (:sid, 'E', :ident, 'active')"
        ),
        {"sid": session_id, "ident": f"e-{session_id}@example.edu"},
    )
    reviewee_id = connection.execute(
        text(
            "SELECT id FROM reviewees WHERE session_id = :sid"
        ),
        {"sid": session_id},
    ).scalar_one()
    return reviewer_id, reviewee_id


def test_drop_unpopulated_pair_context_keeps_populated_slots() -> None:
    """Pair-context display rows whose slot has data in any of the
    session's assignments are preserved (with operator-typed labels).
    Rows whose slot is empty are dropped."""
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
    )
    try:
        with eng.connect() as connection:
            cfg = _alembic_config(connection)
            command.upgrade(cfg, "c2143bd329c7")
            connection.commit()

            session_id, instrument_id = _seed_minimal_session(
                connection, code="keep-populated"
            )
            reviewer_id, reviewee_id = _seed_reviewer_and_reviewee(
                connection, session_id=session_id
            )

            connection.execute(
                text(
                    "INSERT INTO assignments "
                    "(session_id, reviewer_id, reviewee_id, instrument_id, "
                    'include, context, created_by_mode) '
                    "VALUES (:sid, :rev, :rev2, :inst, 1, :ctx, 'manual')"
                ),
                {
                    "sid": session_id,
                    "rev": reviewer_id,
                    "rev2": reviewee_id,
                    "inst": instrument_id,
                    "ctx": json.dumps(
                        {"pair_context_1": "morning", "pair_context_3": "cohortA"}
                    ),
                },
            )
            connection.execute(
                text(
                    "UPDATE instrument_display_fields SET label = 'P1' "
                    "WHERE instrument_id = :iid AND source_field = '1'"
                ),
                {"iid": instrument_id},
            )
            connection.commit()

            command.upgrade(cfg, "head")
            connection.commit()

            rows = connection.execute(
                text(
                    "SELECT source_type, source_field, label, \"order\" "
                    "FROM instrument_display_fields "
                    "WHERE instrument_id = :iid "
                    "ORDER BY \"order\""
                ),
                {"iid": instrument_id},
            ).fetchall()
            # The follow-up migration ``543aa71cd452`` inserts the locked
            # Name + Email rows at orders 0/1 and shifts existing rows by
            # 2, so the surviving pair_context rows end up at orders 2/3.
            assert [tuple(r) for r in rows] == [
                ("reviewee", "name", "", 0),
                ("reviewee", "email_or_identifier", "", 1),
                ("pair_context", "1", "P1", 2),
                ("pair_context", "3", "", 3),
            ]
    finally:
        eng.dispose()


def test_drop_unpopulated_pair_context_drops_all_when_no_assignments() -> None:
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
    )
    try:
        with eng.connect() as connection:
            cfg = _alembic_config(connection)
            command.upgrade(cfg, "c2143bd329c7")
            connection.commit()

            session_id, instrument_id = _seed_minimal_session(
                connection, code="no-asgn"
            )
            connection.commit()

            command.upgrade(cfg, "head")
            connection.commit()

            rows = connection.execute(
                text(
                    "SELECT source_type, source_field "
                    "FROM instrument_display_fields "
                    "WHERE instrument_id = :iid "
                    "ORDER BY \"order\""
                ),
                {"iid": instrument_id},
            ).fetchall()
            # The drop-pair_context migration removes all three slots
            # (no assignments populated them); the follow-up
            # ``543aa71cd452`` then inserts the locked Name + Email rows.
            assert [tuple(r) for r in rows] == [
                ("reviewee", "name"),
                ("reviewee", "email_or_identifier"),
            ]
    finally:
        eng.dispose()


def test_drop_unpopulated_pair_context_preserves_reviewee_rows() -> None:
    """Non-pair_context display fields are not affected by this migration."""
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
    )
    try:
        with eng.connect() as connection:
            cfg = _alembic_config(connection)
            command.upgrade(cfg, "c2143bd329c7")
            connection.commit()

            session_id, instrument_id = _seed_minimal_session(
                connection, code="keep-rev"
            )
            connection.execute(
                text(
                    "INSERT INTO instrument_display_fields "
                    '(instrument_id, source_type, source_field, label, "order", visible) '
                    "VALUES (:iid, 'reviewee', 'tag_1', 'Cohort', 5, 1)"
                ),
                {"iid": instrument_id},
            )
            connection.commit()

            command.upgrade(cfg, "head")
            connection.commit()

            rows = connection.execute(
                text(
                    "SELECT source_type, source_field, label "
                    "FROM instrument_display_fields "
                    "WHERE instrument_id = :iid "
                    "ORDER BY \"order\""
                ),
                {"iid": instrument_id},
            ).fetchall()
            # ``543aa71cd452`` follows: locked rows seed at 0/1, the
            # operator-typed tag_1 row keeps its label and is shifted up.
            assert [tuple(r) for r in rows] == [
                ("reviewee", "name", ""),
                ("reviewee", "email_or_identifier", ""),
                ("reviewee", "tag_1", "Cohort"),
            ]
    finally:
        eng.dispose()
