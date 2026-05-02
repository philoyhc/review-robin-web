"""Force Long_text/Short_text seeded RTD max to 2000/100 (idempotent)

`a1b2c3d4e5f6` was conditional on the rows being at their
exact default values (`min == 0` and `max == 200/50`). On
Postgres that conditional comparison may not have matched if
the stored Float values differ from int literals by epsilon, or
if a session's seed values drifted before the bump shipped.
This follow-up unconditionally sets seeded `Long_text` and
`Short_text` rows to the new maxes, and refreshes dependent
RF validation blocks. If `a1b2c3d4e5f6` already updated them,
this is a no-op.

Down-migration is a no-op (the previous migration's downgrade
handles the revert path).

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-02 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_BUMPS: list[dict] = [
    {"name": "Long_text",  "new_max": 2000},
    {"name": "Short_text", "new_max": 100},
]


def upgrade() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    rtd_table = sa.Table(
        "response_type_definitions", metadata, autoload_with=bind
    )
    rf_table = sa.Table(
        "instrument_response_fields", metadata, autoload_with=bind
    )

    for bump in _BUMPS:
        # Force-update the seeded RTD rows to the new max.
        bind.execute(
            rtd_table.update()
            .where(rtd_table.c.response_type == bump["name"])
            .where(rtd_table.c.is_seeded == sa.true())
            .values(max=bump["new_max"])
        )
        # Refresh dependent RF validation JSON blocks for any RF
        # row pointing at any seeded row of this name.
        rtd_ids = bind.execute(
            sa.select(rtd_table.c.id)
            .where(rtd_table.c.response_type == bump["name"])
            .where(rtd_table.c.is_seeded == sa.true())
        ).scalars().all()
        if rtd_ids:
            bind.execute(
                rf_table.update()
                .where(rf_table.c.response_type_id.in_(rtd_ids))
                .values(
                    validation={
                        "min_length": 0,
                        "max_length": bump["new_max"],
                    }
                )
            )


def downgrade() -> None:
    # No-op — the previous migration's downgrade reverts to the
    # old defaults.
    pass
