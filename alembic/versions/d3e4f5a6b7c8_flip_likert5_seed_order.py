"""Flip seeded Likert5 list_csv to positive-first order

The seeded `Likert5` RTD shipped with `Strongly Disagree, Disagree,
Neutral, Agree, Strongly Agree` (negative-first), inconsistent with
the other seeded List RTDs (`Yes_no` is positive-first; `Grade` is
A+ → F). Flip to `Strongly Agree, Agree, Neutral, Disagree, Strongly
Disagree` so the catalog reads consistently top-to-bottom.

Existing reviewer responses are unaffected — values are stored as
text (`"Agree"`, `"Strongly Disagree"`) and the `choices` list still
carries the same strings. The dropdown re-renders in the new order.

Match scope: only seeded rows whose `list_csv` is exactly the
original string. Operator-edited rows (or rows already manually
flipped) are left alone. Dependent `instrument_response_fields.validation`
JSON blocks are refreshed for every RF row pointing at one of the
flipped RTDs.

Revision ID: d3e4f5a6b7c8
Revises: e1c8f4d57a92
Create Date: 2026-05-05 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "e1c8f4d57a92"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_OLD_CSV = "Strongly Disagree, Disagree, Neutral, Agree, Strongly Agree"
_NEW_CSV = "Strongly Agree, Agree, Neutral, Disagree, Strongly Disagree"
_NEW_CHOICES = [
    "Strongly Agree",
    "Agree",
    "Neutral",
    "Disagree",
    "Strongly Disagree",
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

    # Pick up the seeded Likert5 rows that still carry the original CSV.
    # Operator-edited rows (different list_csv) are left untouched.
    target_ids = bind.execute(
        sa.select(rtd_table.c.id)
        .where(rtd_table.c.response_type == "Likert5")
        .where(rtd_table.c.is_seeded == sa.true())
        .where(rtd_table.c.list_csv == _OLD_CSV)
    ).scalars().all()
    if not target_ids:
        return

    bind.execute(
        rtd_table.update()
        .where(rtd_table.c.id.in_(target_ids))
        .values(list_csv=_NEW_CSV)
    )
    bind.execute(
        rf_table.update()
        .where(rf_table.c.response_type_id.in_(target_ids))
        .values(validation={"choices": _NEW_CHOICES})
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

    target_ids = bind.execute(
        sa.select(rtd_table.c.id)
        .where(rtd_table.c.response_type == "Likert5")
        .where(rtd_table.c.is_seeded == sa.true())
        .where(rtd_table.c.list_csv == _NEW_CSV)
    ).scalars().all()
    if not target_ids:
        return

    bind.execute(
        rtd_table.update()
        .where(rtd_table.c.id.in_(target_ids))
        .values(list_csv=_OLD_CSV)
    )
    bind.execute(
        rf_table.update()
        .where(rf_table.c.response_type_id.in_(target_ids))
        .values(validation={"choices": list(reversed(_NEW_CHOICES))})
    )
