"""segment 13d pr0: rename rule_sets -> operator_rule_sets

The library / per-session-copy split (Segment 15C) introduces
``session_rule_sets`` for per-session copies. Renaming the existing
``rule_sets`` table to ``operator_rule_sets`` first lets the two
tiers sit side-by-side under symmetric names — and lets the new
table from 13D PR 2 reference the harmonised name from birth.

SQL only — the Python class identifier ``RuleSet`` (and its
siblings ``RuleSetRevision`` / ``RuleSetSchema`` / etc.) keep
their names. Just retags ``__tablename__`` and the FK string in
``rule_set_revisions.rule_set_id``.

See ``guide/segment_13D_db_prep.md`` PR 0 for rationale.

Revision ID: 3213fb59371b
Revises: c5e9a8f3d4b1
Create Date: 2026-05-09

"""
from typing import Sequence, Union

from alembic import op

revision: str = "3213fb59371b"
down_revision: Union[str, Sequence[str], None] = "c5e9a8f3d4b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("rule_sets", "operator_rule_sets")


def downgrade() -> None:
    op.rename_table("operator_rule_sets", "rule_sets")
