"""Backfill coverage for migration ``b4e8c2a9d1f6`` —
``Assignment.is_self_review``.

Seeds a session whose assignment population covers every arm of
the canonical rule (individual match + miss, group with R as
member, group with R not a member, group with `"both"` sentinel)
through raw SQL at the pre-migration schema, runs the upgrade,
and asserts every row's ``is_self_review`` value matches the
canonical classification.

The migration is self-contained — no ``app.services`` imports —
so this test exercises the migration's own classifier in
isolation.
"""
from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[2]

_PRE_MIGRATION = "683e99cca6b7"  # data_shapes — the rev before ours
_TARGET_MIGRATION = "b4e8c2a9d1f6"  # this slice's migration


def _alembic_config(connection) -> Config:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    cfg.attributes["connection"] = connection
    return cfg


def _seed_pre_migration(connection) -> dict[str, int]:
    """Seed the pre-migration schema with a population that
    covers every arm of the rule. Returns a dict of stable names →
    assignment ids so the assertions can read by intent."""
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
            "VALUES ('Spring', 'sr-bf', 'draft', :uid)"
        ),
        {"uid": user_id},
    )
    session_id = connection.execute(
        text("SELECT id FROM sessions WHERE code = 'sr-bf'")
    ).scalar_one()

    # Reviewers — Alice (will turn up on both sides of a self-pair)
    # and Bob (control).
    connection.execute(
        text(
            "INSERT INTO reviewers (session_id, name, email, status) "
            "VALUES (:sid, 'Alice', 'Alice@example.edu', 'active'), "
            "       (:sid, 'Bob',   'bob@example.edu',   'active')"
        ),
        {"sid": session_id},
    )
    reviewer_ids = dict(
        connection.execute(
            text(
                "SELECT name, id FROM reviewers WHERE session_id = :sid"
            ),
            {"sid": session_id},
        ).all()
    )

    # Reviewees: Alice (email matches reviewer Alice), Bob,
    # Carol (non-email identifier — never self-review).
    connection.execute(
        text(
            "INSERT INTO reviewees (session_id, name, email_or_identifier, "
            "    tag_1, status) "
            "VALUES (:sid, 'Alice', 'alice@example.edu', 'X', 'active'), "
            "       (:sid, 'Bob',   'bob@example.edu',   'X', 'active'), "
            "       (:sid, 'Carol', 'CarolID',           'Y', 'active'), "
            "       (:sid, 'Dan',   'dan@example.edu',   'Y', 'active')"
        ),
        {"sid": session_id},
    )
    reviewee_ids = dict(
        connection.execute(
            text(
                "SELECT name, id FROM reviewees WHERE session_id = :sid"
            ),
            {"sid": session_id},
        ).all()
    )

    # Instruments:
    #  * #1 individual-scoped (group_kind NULL) — straight pair test.
    #  * #2 group-scoped on tag_1 — Alice IS a member of group "X",
    #    so reviewing X is a self-review group. Group "Y" has no
    #    Alice → not a self-review group.
    #  * #3 group-scoped with the "both" sentinel — single global
    #    group, includes Alice → self-review.
    connection.execute(
        text(
            'INSERT INTO instruments (session_id, name, "order", group_kind) '
            "VALUES (:sid, 'Individual', 1, NULL), "
            "       (:sid, 'GroupOnTag1', 2, 'r1'), "
            "       (:sid, 'GroupBoth',   3, 'both')"
        ),
        {"sid": session_id},
    )
    instrument_ids = dict(
        connection.execute(
            text(
                "SELECT name, id FROM instruments WHERE session_id = :sid"
            ),
            {"sid": session_id},
        ).all()
    )

    ids: dict[str, int] = {}

    def insert_assignment(
        *,
        label: str,
        reviewer_name: str,
        reviewee_name: str,
        instrument_name: str,
    ) -> None:
        connection.execute(
            text(
                "INSERT INTO assignments "
                '(session_id, reviewer_id, reviewee_id, instrument_id, '
                '"include", created_by_mode) '
                "VALUES (:sid, :rid, :eid, :iid, 1, 'manual')"
            ),
            {
                "sid": session_id,
                "rid": reviewer_ids[reviewer_name],
                "eid": reviewee_ids[reviewee_name],
                "iid": instrument_ids[instrument_name],
            },
        )
        ids[label] = connection.execute(
            text(
                "SELECT id FROM assignments "
                "WHERE session_id = :sid AND reviewer_id = :rid "
                "AND reviewee_id = :eid AND instrument_id = :iid"
            ),
            {
                "sid": session_id,
                "rid": reviewer_ids[reviewer_name],
                "eid": reviewee_ids[reviewee_name],
                "iid": instrument_ids[instrument_name],
            },
        ).scalar_one()

    # Individual instrument cases.
    insert_assignment(
        label="ind_alice_self",
        reviewer_name="Alice",
        reviewee_name="Alice",  # email match → TRUE
        instrument_name="Individual",
    )
    insert_assignment(
        label="ind_alice_bob",
        reviewer_name="Alice",
        reviewee_name="Bob",  # email miss → FALSE
        instrument_name="Individual",
    )
    insert_assignment(
        label="ind_alice_carol_non_email",
        reviewer_name="Alice",
        reviewee_name="Carol",  # non-email identifier → FALSE
        instrument_name="Individual",
    )

    # Group-instrument on tag_1: Alice reviewing group "X"
    # (which contains Alice + Bob — both rows flip TRUE) and
    # group "Y" (Carol + Dan — both rows stay FALSE).
    insert_assignment(
        label="grp_x_alice_alice",
        reviewer_name="Alice",
        reviewee_name="Alice",
        instrument_name="GroupOnTag1",
    )
    insert_assignment(
        label="grp_x_alice_bob",
        reviewer_name="Alice",
        reviewee_name="Bob",
        instrument_name="GroupOnTag1",
    )
    insert_assignment(
        label="grp_y_alice_carol",
        reviewer_name="Alice",
        reviewee_name="Carol",
        instrument_name="GroupOnTag1",
    )
    insert_assignment(
        label="grp_y_alice_dan",
        reviewer_name="Alice",
        reviewee_name="Dan",
        instrument_name="GroupOnTag1",
    )

    # Group "both" sentinel: single global group; Alice is a
    # member; every row Alice reviews flips TRUE.
    insert_assignment(
        label="grp_both_alice_alice",
        reviewer_name="Alice",
        reviewee_name="Alice",
        instrument_name="GroupBoth",
    )
    insert_assignment(
        label="grp_both_alice_bob",
        reviewer_name="Alice",
        reviewee_name="Bob",
        instrument_name="GroupBoth",
    )
    insert_assignment(
        label="grp_both_alice_dan",
        reviewer_name="Alice",
        reviewee_name="Dan",
        instrument_name="GroupBoth",
    )

    # Bob reviewing both groups — never self-review (Bob is in
    # group "X" but only the reviewer-as-member rule applies,
    # so when Bob is the reviewer and reviews himself, that's
    # ALSO a self-review group).
    insert_assignment(
        label="grp_x_bob_self",
        reviewer_name="Bob",
        reviewee_name="Bob",
        instrument_name="GroupOnTag1",
    )
    insert_assignment(
        label="grp_x_bob_alice",
        reviewer_name="Bob",
        reviewee_name="Alice",
        instrument_name="GroupOnTag1",
    )

    return ids


def test_backfill_sets_is_self_review_correctly_for_every_arm() -> None:
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
    )
    try:
        with eng.connect() as connection:
            # Step to the pre-migration head, then seed.
            cfg = _alembic_config(connection)
            command.upgrade(cfg, _PRE_MIGRATION)
            connection.commit()
            ids = _seed_pre_migration(connection)
            connection.commit()

            # Apply the migration with the backfill.
            command.upgrade(cfg, _TARGET_MIGRATION)
            connection.commit()

            # Per-row assertions, by intent.
            def value(label: str) -> bool:
                raw = connection.execute(
                    text(
                        "SELECT is_self_review FROM assignments WHERE id = :id"
                    ),
                    {"id": ids[label]},
                ).scalar_one()
                # SQLite stores boolean as 0/1.
                return bool(raw)

            # Individual instrument — straight pair test.
            assert value("ind_alice_self") is True
            assert value("ind_alice_bob") is False
            assert value("ind_alice_carol_non_email") is False

            # Group on tag_1: Alice reviewing group X (self-group)
            # → every member-row flips, including Bob.
            assert value("grp_x_alice_alice") is True
            assert value("grp_x_alice_bob") is True
            # Alice reviewing group Y (not a member) → no flips.
            assert value("grp_y_alice_carol") is False
            assert value("grp_y_alice_dan") is False
            # Bob reviewing group X (Bob is a member) → both
            # rows flip, including the row about Alice.
            assert value("grp_x_bob_self") is True
            assert value("grp_x_bob_alice") is True

            # Group "both" sentinel — single global group; Alice is
            # a member; every row flips.
            assert value("grp_both_alice_alice") is True
            assert value("grp_both_alice_bob") is True
            assert value("grp_both_alice_dan") is True
    finally:
        eng.dispose()


def test_backfill_no_op_on_empty_session() -> None:
    """A session with no assignments shouldn't crash the migration."""
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
    )
    try:
        with eng.connect() as connection:
            cfg = _alembic_config(connection)
            command.upgrade(cfg, _PRE_MIGRATION)
            connection.commit()
            connection.execute(
                text(
                    "INSERT INTO users (email, display_name) "
                    "VALUES ('op@example.edu', 'Op')"
                )
            )
            user_id = connection.execute(
                text(
                    "SELECT id FROM users WHERE email = 'op@example.edu'"
                )
            ).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO sessions "
                    "(name, code, status, created_by_user_id) "
                    "VALUES ('Empty', 'empty', 'draft', :uid)"
                ),
                {"uid": user_id},
            )
            connection.commit()
            command.upgrade(cfg, _TARGET_MIGRATION)
            connection.commit()
            # Column exists, no rows to assert on.
            count = connection.execute(
                text("SELECT COUNT(*) FROM assignments")
            ).scalar_one()
            assert count == 0
    finally:
        eng.dispose()
