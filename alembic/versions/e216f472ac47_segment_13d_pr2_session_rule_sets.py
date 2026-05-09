"""segment 13d pr2: session_rule_sets

Adds the per-session snapshot table for RuleSet copies. Each row
carries a complete snapshot of the rule tree at copy / edit time
(no per-session revisions table — RTDs are minimalistic, the
same call applied here for symmetry).

Lands inert — no service module reads or writes the table until
Segment 15C wires the library / copy split. See
``guide/segment_13D_db_prep.md`` PR 2 for the schema rationale
and ``guide/segment_15C_operator_libraries.md`` for the
end-to-end design.

Revision ID: e216f472ac47
Revises: d81faacee836
Create Date: 2026-05-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e216f472ac47"
down_revision: Union[str, Sequence[str], None] = "d81faacee836"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "session_rule_sets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("combinator", sa.String(length=16), nullable=False),
        sa.Column("exclude_self_reviews", sa.Boolean(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("rules_json", sa.JSON(), nullable=False),
        sa.Column(
            "library_origin_id",
            sa.Integer(),
            sa.ForeignKey("operator_rule_sets.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("session_rule_sets")
