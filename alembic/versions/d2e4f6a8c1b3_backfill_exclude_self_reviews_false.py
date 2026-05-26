"""Backfill session_rule_sets.exclude_self_reviews=False

PR #1452 (2026-05-26) flipped the per-instrument SessionRuleSet
default from ``exclude_self_reviews=True`` to ``False`` so the
per-instrument Self review toggle on the Assignments page is the
sole include / exclude surface. The fix only applied to fresh
materialisations — sessions whose SessionRuleSet was created
pre-fix kept the True value forever, and subsequent Band 1 saves
didn't reset it (the update path only wrote ``rules_json``).

Wave 5 PR 5.1 + 5.2 retired the RuleSet library tier, so every
remaining ``session_rule_sets`` row is auto-managed by Band 1
(via :func:`_create_band1_rule_set`). Backfill every existing
row to ``False`` so old sessions heal without operator action.
The companion service-side update (in ``_band1.py``) keeps the
column normalised on every subsequent save.

Revision ID: d2e4f6a8c1b3
Revises: c7d9e1f3b5a8
Create Date: 2026-05-26
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d2e4f6a8c1b3"
down_revision: Union[str, Sequence[str], None] = "c7d9e1f3b5a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE session_rule_sets SET exclude_self_reviews = "
            + ("FALSE" if op.get_bind().dialect.name != "sqlite" else "0")
            + " WHERE exclude_self_reviews IS NOT NULL"
        )
    )


def downgrade() -> None:
    # No-op — there's nothing to restore. The original True values
    # were not preserved; reverting would require an operator-side
    # policy decision that this migration deliberately retired.
    pass
