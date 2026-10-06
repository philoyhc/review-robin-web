"""Re-derive truncated Integer bounds in the validation block (findings A9)

An Integer response field's ``validation`` block cast its Min, Max and
Step with ``int``, so a non-whole bound truncated on the way in. The
whole-bounds rule refuses such a bound on new input, but a field with
responses keeps the one it had in its ``min`` / ``max`` / ``step``
columns, and those are what the save path enforces. The reviewer surface
reads the block, so it showed (and anchored its client-side step check
on) a bound the server does not apply.

By the author's ruling (2026-10-06), Integer bounds print as entered:
the block now keeps a non-whole value. This rewrites each Integer row
whose column holds a non-whole bound so the block carries that value.
Whole bounds, and every other key in the block, are left as they are.

The downgrade is a no-op: the truncated values carry no information the
columns do not, and every value written is one the block now stores.

Revision ID: 4cc450a87931
Revises: e2503d04df0d
Create Date: 2026-10-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "4cc450a87931"
down_revision: Union[str, Sequence[str], None] = "e2503d04df0d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_fields = sa.table(
    "instrument_response_fields",
    sa.column("id", sa.Integer),
    sa.column("data_type", sa.String),
    sa.column("min", sa.Float),
    sa.column("max", sa.Float),
    sa.column("step", sa.Float),
    sa.column("validation", sa.JSON),
)


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.select(
            _fields.c.id,
            _fields.c.min,
            _fields.c.max,
            _fields.c.step,
            _fields.c.validation,
        ).where(_fields.c.data_type == "Integer")
    ).all()
    for row in rows:
        block = dict(row.validation or {})
        changed = False
        for key, value in (("min", row.min), ("max", row.max), ("step", row.step)):
            if value is None or float(value).is_integer():
                continue
            if block.get(key) != value:
                block[key] = float(value)
                changed = True
        if changed:
            bind.execute(
                _fields.update()
                .where(_fields.c.id == row.id)
                .values(validation=block)
            )


def downgrade() -> None:
    pass
