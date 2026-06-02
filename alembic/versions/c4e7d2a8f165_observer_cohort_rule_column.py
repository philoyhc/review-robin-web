"""observers: add cohort_rule JSON column

Backs the Cohort match rule editor on the Observers Setup
page. Stores the editor's payload as
``CohortRuleSet.model_dump()`` JSON; ``NULL`` means the
operator hasn't authored a cohort rule for this observer yet.

Schema decision in ``guide/observers.md`` "Match-axis schema
— decided (2026-06-02)". Validation lives in
``app/schemas/observer_cohort_rule.py``.

Revision ID: c4e7d2a8f165
Revises: b8f4c2a91d35
Create Date: 2026-06-02
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c4e7d2a8f165"
down_revision: Union[str, Sequence[str], None] = "b8f4c2a91d35"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("observers", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("cohort_rule", sa.JSON(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("observers", schema=None) as batch_op:
        batch_op.drop_column("cohort_rule")
