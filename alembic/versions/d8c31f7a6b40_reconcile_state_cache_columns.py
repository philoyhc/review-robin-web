"""perf: instruments reconcile-state cache columns

Adds four nullable columns to ``instruments`` backing the lazy
persisted cache for the per-instrument staleness verdict —
``assignments.staleness_by_instrument``'s
``InstrumentReconcileState`` — which today runs the rules engine
once per instrument on every render of Assignments, Validate and
(on a ``validated`` session) the four pages carrying the workflow
card. The engine's floor at a 1,000 x 1,000 roster is 2.29 s per
instrument; ``guide/app_responsiveness.md`` has the measurement
and ``guide/segment_19R_optimization_and_bugfixes.md`` Item 2 the
design.

- ``cached_reconcile_stamp`` — a version-prefixed content hash of
  everything the verdict is derived from. On read, a mismatch
  means recompute.
- ``cached_reconcile_stale`` — the verdict.
- ``cached_reconcile_eligible`` — the pair fan-out the engine
  would produce now.
- ``cached_reconcile_self_reviews_excluded`` — pairs the
  self-review rule dropped in that dry run.

The three values ride with the stamp rather than a verdict alone
because the Assignments view renders all of them; a verdict-only
cache would leave the engine running on the page this exists to
fix.

Lands inert — all nullable, no backfill, and nothing reads or
writes them until 19R Item 2 rung 3. A NULL stamp is a cache miss,
which is the state every row is in after this migration.

Revision ID: d8c31f7a6b40
Revises: b7d4f2a9c153
Create Date: 2026-09-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d8c31f7a6b40"
down_revision: Union[str, Sequence[str], None] = "b7d4f2a9c153"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "instruments",
        sa.Column("cached_reconcile_stamp", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "instruments",
        sa.Column("cached_reconcile_stale", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "instruments",
        sa.Column("cached_reconcile_eligible", sa.Integer(), nullable=True),
    )
    op.add_column(
        "instruments",
        sa.Column(
            "cached_reconcile_self_reviews_excluded",
            sa.Integer(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("instruments", "cached_reconcile_self_reviews_excluded")
    op.drop_column("instruments", "cached_reconcile_eligible")
    op.drop_column("instruments", "cached_reconcile_stale")
    op.drop_column("instruments", "cached_reconcile_stamp")
