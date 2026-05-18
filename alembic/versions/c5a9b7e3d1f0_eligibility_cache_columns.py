"""perf: session_rule_sets eligibility-cache columns

Adds two nullable columns to ``session_rule_sets`` backing the
lazy persisted cache for the per-rule "eligible pairs" count —
the rule-engine pass over the reviewer × reviewee space, which
is expensive at large roster sizes:

- ``cached_eligible_pair_count`` — the last computed count.
- ``cached_eligibility_stamp`` — a content-hash of the inputs
  (reviewer / reviewee / relationship rows + the rule
  definition) the count was computed from. On read, a stamp
  mismatch means the cache is stale and the count is recomputed.

Lands inert — both nullable, no backfill. The first
``evaluate_session_rule_eligibility`` call after deploy
populates them; a NULL count is treated as a cache miss.

Revision ID: c5a9b7e3d1f0
Revises: d8e4f1a2b3c4
Create Date: 2026-05-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c5a9b7e3d1f0"
down_revision: Union[str, Sequence[str], None] = "d8e4f1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "session_rule_sets",
        sa.Column("cached_eligible_pair_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "session_rule_sets",
        sa.Column(
            "cached_eligibility_stamp", sa.String(length=64), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("session_rule_sets", "cached_eligibility_stamp")
    op.drop_column("session_rule_sets", "cached_eligible_pair_count")
