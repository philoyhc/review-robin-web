"""A18: migration ``e2a7c4f9b130`` sets a stored reviewer summary to off.

The reviewer's "Responses released" cell lost ``summarized`` (findings
A18). The migration clears every stored ``peer_reviewer``
``after_release`` pair whose granularity is ``aggregated`` and touches
nothing else: not the reviewer's Raw cell, not a reviewee's or an
observer's summary. Built on its own in-memory SQLite engine, like
``test_19t13_branch_mode_column``; Postgres runs the same UPDATE through
``ci-postgres``'s ``upgrade head``.
"""

from __future__ import annotations

from alembic import command
from sqlalchemy import create_engine, text

from .test_19r2_reconcile_cache_columns import _alembic_config

REVISION = "e2a7c4f9b130"
PREVIOUS = "d81f3c6a2e47"

_ROWS = [
    # (id, audience, after_release_granularity, after_release_identification)
    (1, "peer_reviewer", "aggregated", "deidentified"),
    (2, "peer_reviewer", "row", "identified"),
    (3, "reviewee", "aggregated", "deidentified"),
    (4, "observer", "aggregated", "deidentified"),
]


def test_only_the_reviewers_released_summary_is_cleared() -> None:
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
            for row_id, audience, granularity, identification in _ROWS:
                connection.execute(
                    text(
                        "INSERT INTO instrument_view_policies "
                        "(id, instrument_id, audience, "
                        "after_release_granularity, "
                        "after_release_identification, "
                        "created_at, updated_at) VALUES "
                        "(:id, :inst, :aud, :g, :i, "
                        "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                    ),
                    {
                        "id": row_id,
                        "inst": row_id,
                        "aud": audience,
                        "g": granularity,
                        "i": identification,
                    },
                )
            connection.commit()

            command.upgrade(cfg, REVISION)
            connection.commit()
            after = {
                row.id: (row.after_release_granularity, row.after_release_identification)
                for row in connection.execute(
                    text(
                        "SELECT id, after_release_granularity, "
                        "after_release_identification "
                        "FROM instrument_view_policies"
                    )
                )
            }
            assert after == {
                1: (None, None),
                2: ("row", "identified"),
                3: ("aggregated", "deidentified"),
                4: ("aggregated", "deidentified"),
            }
    finally:
        eng.dispose()
