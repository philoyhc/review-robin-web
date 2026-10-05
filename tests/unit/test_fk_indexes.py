"""Every foreign-key column in the ORM metadata is indexed.

Pins ``docs/database.md`` "Indexes": every ``ForeignKey`` column
declares ``index=True``. A primary-key or ``unique=True`` column is
already indexed, so it passes too. Findings H2 / Hc4 found three
``data_shapes`` FKs that broke the rule unnoticed.
"""

from __future__ import annotations

import app.db.models  # noqa: F401 — registers every model on Base.metadata
from app.db.base import Base


def test_every_foreign_key_column_is_indexed() -> None:
    unindexed = sorted(
        f"{table.name}.{fk.parent.name}"
        for table in Base.metadata.sorted_tables
        for fk in table.foreign_keys
        if not (fk.parent.index or fk.parent.unique or fk.parent.primary_key)
    )
    assert unindexed == [], (
        "ForeignKey columns without index=True (docs/database.md "
        f"'Indexes'): {unindexed}"
    )
