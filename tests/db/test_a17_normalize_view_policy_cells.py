"""A17: migration ``14db60023e88`` normalizes cells the per-cell rule refuses.

Rows backfilled by ``a7e3b1d92c64`` predate the rule and made the
Instrument card's Save 422 and a Settings re-import refuse. Each illegal
cell is rewritten to the nearest legal one, never wider than it granted;
legal cells are untouched. Built on its own in-memory SQLite engine, like
``test_a18_reviewer_released_summary_off``; Postgres runs the same
migration through ``ci-postgres``'s ``upgrade head``.
"""

from __future__ import annotations

from alembic import command
from sqlalchemy import create_engine, text

from app.services.visibility_policies import valid_modes_for_cell

from .test_19r2_reconcile_cache_columns import _alembic_config

REVISION = "14db60023e88"
PREVIOUS = "a2d16ffeb59a"

RAW = ("row", "identified")
ANON = ("row", "deidentified")
SUMM = ("aggregated", "deidentified")
OFF = (None, None)
INCOHERENT = ("aggregated", "identified")
HALF = ("row", None)

# id: (audience, while_ongoing pair, after_release pair) -> expected
_CASES = {
    1: (("peer_reviewer", OFF, OFF), (RAW, OFF)),
    2: (("peer_reviewer", ANON, ANON), (RAW, OFF)),
    3: (("peer_reviewer", RAW, RAW), (RAW, RAW)),
    4: (("reviewee", RAW, RAW), (OFF, RAW)),
    5: (("reviewee", OFF, INCOHERENT), (OFF, OFF)),
    6: (("observer", RAW, RAW), (SUMM, RAW)),
    7: (("observer", ANON, HALF), (SUMM, OFF)),
    8: (("observer", SUMM, SUMM), (SUMM, SUMM)),
    9: (("observer", INCOHERENT, ANON), (OFF, ANON)),
}

_MODE = {RAW: "raw", ANON: "anonymized", SUMM: "summarized", OFF: None}


def test_illegal_cells_take_the_nearest_legal_value() -> None:
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
            for row_id, ((audience, wo, ar), _) in _CASES.items():
                connection.execute(
                    text(
                        "INSERT INTO instrument_view_policies "
                        "(id, instrument_id, audience, "
                        "while_ongoing_granularity, while_ongoing_identification, "
                        "after_release_granularity, after_release_identification, "
                        "created_at, updated_at) VALUES "
                        "(:id, :inst, :aud, :wg, :wi, :ag, :ai, "
                        "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                    ),
                    {
                        "id": row_id,
                        "inst": row_id,
                        "aud": audience,
                        "wg": wo[0],
                        "wi": wo[1],
                        "ag": ar[0],
                        "ai": ar[1],
                    },
                )
            connection.commit()

            command.upgrade(cfg, REVISION)
            connection.commit()
            after = {
                row.id: (
                    (row.while_ongoing_granularity, row.while_ongoing_identification),
                    (row.after_release_granularity, row.after_release_identification),
                )
                for row in connection.execute(
                    text(
                        "SELECT id, while_ongoing_granularity, "
                        "while_ongoing_identification, after_release_granularity, "
                        "after_release_identification FROM instrument_view_policies"
                    )
                )
            }
            assert after == {i: expected for i, (_, expected) in _CASES.items()}

            # Every result is legal under the service's rule, so the
            # card's Save and a Settings re-import accept it.
            for row_id, ((audience, _, _), (wo, ar)) in _CASES.items():
                assert _MODE[wo] in valid_modes_for_cell(audience, "while_ongoing")
                assert _MODE[ar] in valid_modes_for_cell(audience, "after_release")
    finally:
        eng.dispose()
