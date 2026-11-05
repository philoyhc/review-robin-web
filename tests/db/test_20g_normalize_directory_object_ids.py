"""Segment 20G rung 4: revision ``e4b2c7a91d36`` stores every roster
row's ``directory_object_id`` and every ``users.external_principal_id``
stripped and lower-cased, a whitespace-only value as NULL, and its
downgrade is a no-op.

Built on its own in-memory SQLite engine, like
``test_19y_instruments_intro_layout``; Postgres runs the same migration
through ``ci-postgres``'s ``upgrade head`` and round-trip.
"""

from __future__ import annotations

from alembic import command
from sqlalchemy import create_engine, text

from .test_19r2_reconcile_cache_columns import _alembic_config

REVISION = "e4b2c7a91d36"
PREVIOUS = "c3e9a1f7d2b4"
MIXED = " 1A2B3C4D-AAAA-4BBB-8CCC-DDDDEEEEFFFF "
NORMAL = "1a2b3c4d-aaaa-4bbb-8ccc-ddddeeeeffff"


def test_stored_ids_are_normalized_and_the_downgrade_keeps_them() -> None:
    eng = create_engine(
        "sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, future=True
    )
    try:
        with eng.connect() as connection:
            cfg = _alembic_config(connection)
            command.upgrade(cfg, PREVIOUS)
            connection.commit()
            # By raw SQL: the ORM models the head revision, not PREVIOUS.
            connection.execute(
                text(
                    "INSERT INTO users (email, display_name, external_principal_id) "
                    "VALUES ('a@example.edu', 'A', :mixed), ('b@example.edu', 'B', '  '), "
                    "('c@example.edu', 'C', NULL)"
                ),
                {"mixed": MIXED},
            )
            uid = connection.execute(
                text("SELECT id FROM users WHERE email = 'a@example.edu'")
            ).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO sessions "
                    "(name, code, status, created_by_user_id, public_id, form_key) "
                    "VALUES ('S', 'g20', 'draft', :uid, 'abcdefghjk', :key)"
                ),
                {"uid": uid, "key": "0" * 64},
            )
            sid = connection.execute(text("SELECT id FROM sessions")).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO reviewers (session_id, name, email, status, directory_object_id) "
                    "VALUES (:sid, 'R', 'r@example.edu', 'active', :mixed)"
                ),
                {"sid": sid, "mixed": MIXED},
            )
            connection.execute(
                text(
                    "INSERT INTO reviewees "
                    "(session_id, name, email_or_identifier, status, directory_object_id) "
                    "VALUES (:sid, 'E', 'e@example.edu', 'active', :mixed)"
                ),
                {"sid": sid, "mixed": MIXED},
            )
            connection.execute(
                text(
                    "INSERT INTO observers "
                    "(session_id, email, display_name, status, directory_object_id) "
                    "VALUES (:sid, 'o@example.edu', 'O', 'active', :mixed)"
                ),
                {"sid": sid, "mixed": MIXED},
            )
            connection.commit()

            command.upgrade(cfg, REVISION)
            connection.commit()
            for table in ("reviewers", "reviewees", "observers"):
                assert (
                    connection.execute(
                        text(f"SELECT directory_object_id FROM {table}")
                    ).scalar_one()
                    == NORMAL
                )
            principals = dict(
                connection.execute(text("SELECT email, external_principal_id FROM users")).all()
            )
            assert principals == {
                "a@example.edu": NORMAL,
                "b@example.edu": None,
                "c@example.edu": None,
            }

            command.downgrade(cfg, PREVIOUS)
            connection.commit()
            assert (
                connection.execute(text("SELECT directory_object_id FROM reviewers")).scalar_one()
                == NORMAL
            )
    finally:
        eng.dispose()
