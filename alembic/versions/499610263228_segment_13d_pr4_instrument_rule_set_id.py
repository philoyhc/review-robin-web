"""segment 13d pr4: instruments.rule_set_id

Adds the per-instrument RuleSet selection pointer for Segment 15B.
Each instrument points at the per-session ``session_rule_sets`` row
currently applied to it; NULL = "no RuleSet currently selected".

Targets the per-session copy table (``session_rule_sets``), not
the operator library (``operator_rule_sets``):

- Deleting an instrument disposes of the pointer cleanly — the
  session's RuleSet copy is untouched.
- Deleting a ``session_rule_sets`` row clears the pointer on
  every instrument that referenced it via SQL ``SET NULL``.
- Deleting from the operator library doesn't touch any
  instrument pointer — those target session copies, which
  survive library deletes via ``session_rule_sets.library_origin_id``
  ``SET NULL`` (added in 13D PR 2).

Lands inert — no service module reads or writes the column.
``assignments.replace_assignments`` continues to fan one set of
generated pairs across every instrument. 15B Slice 2 starts
persisting the choice into this column once 15C has populated
``session_rule_sets``.

See ``guide/segment_13D_db_prep.md`` PR 4 for the schema rationale,
``guide/segment_15B_per_instrument_assignments.md`` Slice 2 for
how the pointer gets used, and
``guide/segment_15C_operator_libraries.md`` for the library /
copy infrastructure.

Revision ID: 499610263228
Revises: f6183d235e59
Create Date: 2026-05-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "499610263228"
down_revision: Union[str, Sequence[str], None] = "f6183d235e59"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add the column without an inline FK (anonymous constraints
    # break SQLite batch mode), then attach the named FK + index in
    # a second batch — same shape as 8b3c1d4e5f7a (10D Slice 4a) and
    # f6183d235e59 (13D PR 3).
    with op.batch_alter_table("instruments") as batch:
        batch.add_column(
            sa.Column("rule_set_id", sa.Integer(), nullable=True)
        )
    with op.batch_alter_table("instruments") as batch:
        batch.create_foreign_key(
            "fk_instruments_rule_set_id",
            "session_rule_sets",
            ["rule_set_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("ix_instruments_rule_set_id", ["rule_set_id"])


def downgrade() -> None:
    with op.batch_alter_table("instruments") as batch:
        batch.drop_index("ix_instruments_rule_set_id")
        batch.drop_constraint("fk_instruments_rule_set_id", type_="foreignkey")
        batch.drop_column("rule_set_id")
