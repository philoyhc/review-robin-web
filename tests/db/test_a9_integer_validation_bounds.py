"""A9: migration ``4cc450a87931`` re-derives truncated Integer bounds.

An Integer field's ``validation`` block cast bounds with ``int``, so a
non-whole bound the whole-bounds exemption kept in the ``min`` / ``max``
/ ``step`` columns showed truncated on the reviewer surface. Only those
bounds are rewritten; whole bounds, other types and other keys stay.
Built on its own in-memory SQLite engine, like
``test_a17_normalize_view_policy_cells``; Postgres runs the same
migration through ``ci-postgres``'s ``upgrade head``.
"""

from __future__ import annotations

import json

from alembic import command
from sqlalchemy import create_engine, text

from .test_19r2_reconcile_cache_columns import _alembic_config

REVISION = "4cc450a87931"
PREVIOUS = "e2503d04df0d"

# id: (data_type, min, max, step, stored block) -> expected block
_CASES = {
    1: (("Integer", 0.5, 10.0, None, {"min": 0, "max": 10}), {"min": 0.5, "max": 10}),
    2: (("Integer", 0.0, 10.0, 1.0, {"min": 0, "max": 10, "step": 1}), {"min": 0, "max": 10, "step": 1}),
    3: (("Integer", 1.0, 7.5, 2.5, {"min": 1, "max": 7, "step": 2}), {"min": 1, "max": 7.5, "step": 2.5}),
    4: (("Decimal", 0.5, 1.5, 0.25, {"min": 0.5, "max": 1.5, "step": 0.25}), {"min": 0.5, "max": 1.5, "step": 0.25}),
    5: (("Integer", 0.5, None, None, None), {"min": 0.5}),
}


def test_non_whole_integer_bounds_take_the_column_value() -> None:
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
            for row_id, ((data_type, lo, hi, step, block), _) in _CASES.items():
                connection.execute(
                    text(
                        "INSERT INTO instrument_response_fields "
                        '(id, instrument_id, field_key, label, required, "order", '
                        "help_text_visible, visible, data_type, min, max, step, "
                        "validation) VALUES (:id, 1, :key, 'L', 0, :id, 1, 1, "
                        ":dt, :lo, :hi, :step, :block)"
                    ),
                    {
                        "id": row_id,
                        "key": f"f{row_id}",
                        "dt": data_type,
                        "lo": lo,
                        "hi": hi,
                        "step": step,
                        "block": json.dumps(block) if block is not None else None,
                    },
                )
            connection.commit()

            command.upgrade(cfg, REVISION)
            connection.commit()

            stored = {
                row_id: json.loads(block) if block is not None else None
                for row_id, block in connection.execute(
                    text("SELECT id, validation FROM instrument_response_fields")
                )
            }
            assert stored == {row_id: expected for row_id, (_, expected) in _CASES.items()}
    finally:
        eng.dispose()
