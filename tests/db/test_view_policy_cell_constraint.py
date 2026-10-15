"""``ck_view_policy_cell``: the database refuses a visibility cell the
per-cell rule refuses (``guide/archive/visibility_cell_constraint.md``, author 2026-10-15).

The rule lives twice — ``visibility_policies._PER_CELL_VALID_MODES`` for
the validators, the CHECK for the database — so these tests insert every
audience × pair × pair combination and require the database to accept
exactly what the Python rule accepts, on the schema the ORM builds and
on the one migration ``e5c1a9d3b7f2`` builds. Postgres runs the same
migration both ways through ``ci-postgres``.
"""

from __future__ import annotations

import itertools
import logging
import logging.config

import pytest
from alembic import command
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from app.db.base import Base
from app.services.visibility_policies import (
    VisibilityPolicyError,
    decode_mode,
    valid_modes_for_cell,
)

from .test_19r2_reconcile_cache_columns import _alembic_config

REVISION = "e5c1a9d3b7f2"
PREVIOUS = "c4a8e2f6d1b3"

RAW = ("row", "identified")
ANON = ("row", "deidentified")
SUMM = ("aggregated", "deidentified")
OFF = (None, None)
PAIRS = [
    OFF, RAW, ANON, SUMM,
    ("aggregated", "identified"),  # reserved-incoherent
    ("row", None), (None, "identified"),  # half-set
    ("bogus", "identified"),
]
AUDIENCES = ["peer_reviewer", "reviewee", "observer", "nobody"]

_INSERT = text(
    "INSERT INTO instrument_view_policies "
    "(id, instrument_id, audience, "
    "while_ongoing_granularity, while_ongoing_identification, "
    "after_release_granularity, after_release_identification, "
    "created_at, updated_at) VALUES "
    "(:id, :id, :aud, :wg, :wi, :ag, :ai, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
)


def _python_allows(audience: str, ongoing: tuple, released: tuple) -> bool:
    if audience not in {"peer_reviewer", "reviewee", "observer"}:
        return False
    for window, pair in (("while_ongoing", ongoing), ("after_release", released)):
        if pair == OFF:
            mode = None
        elif None in pair:
            return False
        else:
            try:
                mode = decode_mode(*pair)
            except VisibilityPolicyError:
                return False
        if mode not in valid_modes_for_cell(audience, window):
            return False
    return True


def _params(row_id: int, audience: str, ongoing: tuple, released: tuple) -> dict:
    return {
        "id": row_id, "aud": audience,
        "wg": ongoing[0], "wi": ongoing[1], "ag": released[0], "ai": released[1],
    }


def _assert_database_agrees(engine) -> int:
    accepted = 0
    combos = itertools.product(AUDIENCES, PAIRS, PAIRS)
    for row_id, (audience, ongoing, released) in enumerate(combos, start=1):
        with engine.connect() as connection:
            try:
                connection.execute(_INSERT, _params(row_id, audience, ongoing, released))
                connection.commit()
                stored = True
            except IntegrityError:
                connection.rollback()
                stored = False
        assert stored == _python_allows(audience, ongoing, released), (
            audience, ongoing, released,
        )
        accepted += stored
    return accepted


def _memory_engine():
    return create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
    )


def test_the_model_constraint_accepts_exactly_what_the_rule_allows() -> None:
    engine = _memory_engine()
    try:
        Base.metadata.create_all(engine)
        # Legal combinations: reviewer 1×2, reviewee 1×4, observer 2×4.
        assert _assert_database_agrees(engine) == 14
    finally:
        engine.dispose()


def test_the_migration_normalizes_constrains_and_downgrades(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    # env.py's fileConfig replaces the root logger's handlers, caplog's
    # among them, so the log line below would go unseen.
    monkeypatch.setattr(logging.config, "fileConfig", lambda *a, **k: None)
    engine = _memory_engine()
    try:
        with engine.connect() as connection:
            cfg = _alembic_config(connection)
            command.upgrade(cfg, PREVIOUS)
            connection.commit()
            # Illegal rows the earlier normalization would also fix.
            for row_id, (audience, ongoing, released) in {
                1: ("peer_reviewer", OFF, ANON),
                2: ("observer", RAW, ("row", None)),
                3: ("reviewee", ANON, SUMM),
            }.items():
                connection.execute(_INSERT, _params(row_id, audience, ongoing, released))
            connection.commit()

            with caplog.at_level("INFO", logger="alembic.runtime.migration"):
                command.upgrade(cfg, REVISION)
            connection.commit()
            # guide/post_azure_todo_checklist.md item 1 reads this line.
            assert (
                "ck_view_policy_cell: normalized 3 instrument_view_policies "
                "row(s) before adding the constraint: ids [1, 2, 3]"
            ) in caplog.text
            after = {
                row.id: (
                    (row.while_ongoing_granularity, row.while_ongoing_identification),
                    (row.after_release_granularity, row.after_release_identification),
                )
                for row in connection.execute(text(
                    "SELECT id, while_ongoing_granularity, while_ongoing_identification, "
                    "after_release_granularity, after_release_identification "
                    "FROM instrument_view_policies"
                ))
            }
            assert after == {1: (RAW, OFF), 2: (SUMM, OFF), 3: (OFF, SUMM)}
            connection.execute(text("DELETE FROM instrument_view_policies"))
            connection.commit()

        assert _assert_database_agrees(engine) == 14

        with engine.connect() as connection:
            connection.execute(text("DELETE FROM instrument_view_policies"))
            connection.commit()
            command.downgrade(_alembic_config(connection), PREVIOUS)
            connection.commit()
            # The constraint is gone: an illegal cell stores again.
            connection.execute(_INSERT, _params(1, "observer", RAW, RAW))
            connection.commit()
    finally:
        engine.dispose()


def test_an_unknown_audience_stops_the_upgrade() -> None:
    engine = _memory_engine()
    try:
        with engine.connect() as connection:
            cfg = _alembic_config(connection)
            command.upgrade(cfg, PREVIOUS)
            connection.commit()
            connection.execute(_INSERT, _params(7, "nobody", OFF, OFF))
            connection.commit()
            with pytest.raises(RuntimeError, match=r"unknown audience.*ids \[7\]"):
                command.upgrade(cfg, REVISION)
    finally:
        engine.dispose()
