"""19R Item 2 rung 1: the four ``instruments`` reconcile-cache columns.

Rung 1 lands the migration with no reader and no writer, so there is no
behaviour to assert yet — what there is to assert is the shape the later
rungs will depend on, and that it survives both directions of the chain.

**This runs against SQLite in every environment**, including the
``ci-postgres`` job, because it builds its own in-memory engine rather
than taking the ambient one: stepping a shared database up and down the
chain underneath a parallel test run is not something a test may do.
Postgres sees these columns through that job's own
``downgrade base + upgrade head``, which proves the DDL applies but
exercises no value. So the value assertions below are SQLite's, and the
one thing SQLite cannot check — that a 67-character stamp fits — is
covered instead by asserting the *declared* width, which SQLite records
faithfully even though it does not enforce it.

19R's own Item 1 is the reminder for the rest: a check with no negative
case proves less than it looks like it proves. So the columns are
asserted absent before the upgrade, written and read back after it, and
asserted absent again after the downgrade.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.db.models.instrument import Instrument

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The revision this rung adds, and the one it chains onto.
REVISION = "d8c31f7a6b40"
PREVIOUS = "b7d4f2a9c153"

CACHE_COLUMNS = {
    "cached_reconcile_stamp",
    "cached_reconcile_stale",
    "cached_reconcile_eligible",
    "cached_reconcile_self_reviews_excluded",
}


def _alembic_config(connection) -> Config:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    cfg.attributes["connection"] = connection
    return cfg


def _instrument_columns(connection) -> dict[str, dict]:
    return {c["name"]: c for c in inspect(connection).get_columns("instruments")}


def _seed_instrument(connection, *, code: str) -> int:
    """A session with one instrument, by raw SQL — the ORM models the
    head revision, and this test stands at two different ones.

    ``session_seq`` is supplied explicitly: it is NOT NULL with a
    Python-side default (19Q Item 6), which a raw insert does not get.
    """
    connection.execute(
        text(
            "INSERT INTO users (email, display_name) VALUES (:e, 'O')"
        ),
        {"e": f"op-{code}@example.edu"},
    )
    uid = connection.execute(
        text("SELECT id FROM users WHERE email = :e"),
        {"e": f"op-{code}@example.edu"},
    ).scalar_one()
    connection.execute(
        text(
            "INSERT INTO sessions (name, code, status, created_by_user_id) "
            "VALUES ('S', :code, 'draft', :uid)"
        ),
        {"code": code, "uid": uid},
    )
    sid = connection.execute(
        text("SELECT id FROM sessions WHERE code = :code"), {"code": code}
    ).scalar_one()
    connection.execute(
        text(
            "INSERT INTO instruments "
            '(session_id, name, "order", session_seq, '
            "accepting_responses, responses_visible_when_closed) "
            "VALUES (:sid, 'I', 0, 1, 0, 0)"
        ),
        {"sid": sid},
    )
    return connection.execute(
        text("SELECT id FROM instruments WHERE session_id = :sid"),
        {"sid": sid},
    ).scalar_one()


def test_rung_1_adds_four_nullable_cache_columns_and_drops_them_again() -> None:
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
            before = _instrument_columns(connection)
            # The negative case: without it, an upgrade that added
            # nothing would still pass the assertions below.
            assert CACHE_COLUMNS & set(before) == set()
            # The neighbouring cache the design copies is already here,
            # so "column absent" above is about these four and not
            # about standing at the wrong revision.
            assert "cached_group_pair_stamp" in before

            command.upgrade(cfg, REVISION)
            connection.commit()
            after = _instrument_columns(connection)
            assert CACHE_COLUMNS <= set(after)
            for name in CACHE_COLUMNS:
                assert after[name]["nullable"] is True, name

            # The stamp is wider than the ``String(64)`` beside it
            # because it carries a version prefix ahead of a sha256
            # hex digest. SQLite does not *enforce* a VARCHAR length,
            # but it does record the declared one, so this catches a
            # migration that declared 64 — which Postgres would then
            # reject a real stamp against.
            assert after["cached_reconcile_stamp"]["type"].length == 80
            assert after["cached_group_pair_stamp"]["type"].length == 64
            # ...and the ORM has to agree with the migration, or the
            # two disagree only where there is no SQLite test session
            # to notice: production.
            assert (
                Instrument.__table__.c.cached_reconcile_stamp.type.length
                == after["cached_reconcile_stamp"]["type"].length
            )

            instrument_id = _seed_instrument(connection, code="19r2-up")
            # Inert after the migration: the rung lands no writer.
            row = connection.execute(
                text(
                    "SELECT cached_reconcile_stamp, cached_reconcile_stale, "
                    "cached_reconcile_eligible, "
                    "cached_reconcile_self_reviews_excluded "
                    "FROM instruments WHERE id = :iid"
                ),
                {"iid": instrument_id},
            ).one()
            assert list(row) == [None, None, None, None]

            # And each column actually holds what rung 3 will put in it.
            connection.execute(
                text(
                    "UPDATE instruments SET "
                    "cached_reconcile_stamp = :stamp, "
                    "cached_reconcile_stale = :stale, "
                    "cached_reconcile_eligible = :eligible, "
                    "cached_reconcile_self_reviews_excluded = :excluded "
                    "WHERE id = :iid"
                ),
                {
                    # A version prefix plus a sha256 hex digest: 67
                    # characters, the shape rung 2 will produce.
                    "stamp": "v1:" + "a" * 64,
                    "stale": True,
                    "eligible": 1234,
                    "excluded": 7,
                    "iid": instrument_id,
                },
            )
            written = connection.execute(
                text(
                    "SELECT cached_reconcile_stamp, cached_reconcile_stale, "
                    "cached_reconcile_eligible, "
                    "cached_reconcile_self_reviews_excluded "
                    "FROM instruments WHERE id = :iid"
                ),
                {"iid": instrument_id},
            ).one()
            assert written[0] == "v1:" + "a" * 64
            assert bool(written[1]) is True
            assert written[2] == 1234
            assert written[3] == 7

            command.downgrade(cfg, PREVIOUS)
            connection.commit()
            rolled_back = _instrument_columns(connection)
            assert CACHE_COLUMNS & set(rolled_back) == set()
            # The downgrade drops these four and nothing else.
            assert "cached_group_pair_stamp" in rolled_back
    finally:
        eng.dispose()
