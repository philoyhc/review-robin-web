"""segment 13a-2: uq_session_rule_set_session_name

Adds a unique constraint on ``session_rule_sets(session_id,
name)`` mirroring the parallel ``uq_rtd_session_name`` already
on ``response_type_definitions``. Pure DDL — the table is empty
on every deployment that has run 13D PR 2 (it lands inert; no
service module reads or writes it yet), so no data backfill /
pre-flight cleanup is needed.

The 12A-1 export contract leans on per-session name uniqueness
for the name-based ``instruments[N].rule_set_name`` reference;
this PR pins the invariant at the schema level so 12A-1, 15B,
and 15C can all rely on it. Service-layer enforcement (a
collision check at editor-save time mirroring
``_resolve_save_as_name`` for ``operator_rule_sets``) is
deferred to 15C Slice 4 where the editor is rerouted to save
into ``session_rule_sets``; this DB index is the safety net.

Revision ID: 7c2b94f1a5e3
Revises: 38b72f14662c
Create Date: 2026-05-09

"""
from typing import Sequence, Union

from alembic import op

revision: str = "7c2b94f1a5e3"
down_revision: Union[str, Sequence[str], None] = "38b72f14662c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Batch mode keeps SQLite happy (it has no ALTER for constraints
    # so Alembic copies the table); on Postgres the helper resolves
    # to the same plain ``ALTER TABLE … ADD CONSTRAINT`` ``op.create_unique_constraint``
    # would emit.
    with op.batch_alter_table("session_rule_sets") as batch_op:
        batch_op.create_unique_constraint(
            "uq_session_rule_set_session_name",
            ["session_id", "name"],
        )


def downgrade() -> None:
    with op.batch_alter_table("session_rule_sets") as batch_op:
        batch_op.drop_constraint(
            "uq_session_rule_set_session_name",
            type_="unique",
        )
