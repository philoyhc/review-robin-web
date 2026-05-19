"""perf: instruments group-pair-count cache columns

Adds two nullable columns to ``instruments`` backing the lazy
persisted cache for the per-instrument "reviewer-group pairs"
count shown on a group-scoped instrument's rule card — the
rule-engine pass over the reviewer x reviewee space collapsed
by the instrument's group boundary, expensive at large roster
sizes:

- ``cached_group_pair_count`` — the last computed count.
- ``cached_group_pair_stamp`` — a content-hash of the inputs
  (reviewer / reviewee / relationship rows + the pinned rule
  definition + ``group_kind``) the count was computed from. On
  read, a stamp mismatch means the cache is stale and the count
  is recomputed.

Per-instrument rather than per-rule (cf. the
``session_rule_sets`` eligibility cache) because the count
depends on the instrument's boundary tags. Lands inert — both
nullable, no backfill; the first
``evaluate_instrument_group_pair_counts`` call after deploy
populates them, and a NULL count is treated as a cache miss.

Revision ID: c3a9f1d7b2e8
Revises: c5a9b7e3d1f0
Create Date: 2026-05-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c3a9f1d7b2e8"
down_revision: Union[str, Sequence[str], None] = "c5a9b7e3d1f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "instruments",
        sa.Column("cached_group_pair_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "instruments",
        sa.Column(
            "cached_group_pair_stamp", sa.String(length=64), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("instruments", "cached_group_pair_stamp")
    op.drop_column("instruments", "cached_group_pair_count")
