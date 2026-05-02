"""Bump Long_text/Short_text seeded RTD max to 2000/100

The Slice 4a seed (rev `8b3c1d4e5f7a`) set ``Long_text`` and
``Short_text`` to character-count maxes of 200 and 50
respectively. Both are too tight in practice — operator review
of seeded sessions on the dev slot 2026-05-02 settled on 2000
(Long_text) and 100 (Short_text).

Updates the seeded RTD rows on every existing session, plus
refreshes the ``validation`` JSON blocks on every dependent
``instrument_response_fields`` row so existing reviewer-surface
inputs honour the new caps. Only seeded rows are touched
(operator-defined RTDs with the same names are not possible —
``response_type`` is unique per session and seeded rows are
``is_seeded = TRUE``).

Down-migration restores the old caps.

Revision ID: a1b2c3d4e5f6
Revises: 8b3c1d4e5f7a
Create Date: 2026-05-02 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "8b3c1d4e5f7a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_BUMPS: list[dict] = [
    # name,        old_max, new_max
    {"name": "Long_text",  "old_max": 200, "new_max": 2000},
    {"name": "Short_text", "old_max": 50,  "new_max": 100},
]


def _retarget(
    rtd_table: sa.Table,
    rf_table: sa.Table,
    bind: sa.engine.Connection,
    old_max: int,
    new_max: int,
    name: str,
) -> None:
    # Bump the RTD row's ``max`` only when it's still at the
    # default (operators may have tweaked it via the RTD edit UI;
    # leave those alone).
    bind.execute(
        rtd_table.update()
        .where(rtd_table.c.response_type == name)
        .where(rtd_table.c.is_seeded.is_(True))
        .where(rtd_table.c.min == 0)
        .where(rtd_table.c.max == old_max)
        .values(max=new_max)
    )
    # Refresh dependent ``validation`` blocks on every
    # ``instrument_response_fields`` row pointing at any seeded
    # row of this name. (RF.validation is derived from the RTD —
    # operators don't edit it directly — so a blanket update is
    # safe.)
    rtd_ids = bind.execute(
        sa.select(rtd_table.c.id)
        .where(rtd_table.c.response_type == name)
        .where(rtd_table.c.is_seeded.is_(True))
    ).scalars().all()
    if rtd_ids:
        bind.execute(
            rf_table.update()
            .where(rf_table.c.response_type_id.in_(rtd_ids))
            .values(validation={"min_length": 0, "max_length": new_max})
        )


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
        _retarget(
            rtd_table,
            rf_table,
            bind,
            old_max=bump["old_max"],
            new_max=bump["new_max"],
            name=bump["name"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    rtd_table = sa.Table(
        "response_type_definitions", metadata, autoload_with=bind
    )
    rf_table = sa.Table(
        "instrument_response_fields", metadata, autoload_with=bind
    )
    for bump in _BUMPS:
        _retarget(
            rtd_table,
            rf_table,
            bind,
            old_max=bump["new_max"],
            new_max=bump["old_max"],
            name=bump["name"],
        )
