"""segment_18J wave 2 PR iii-b3 — retire the operator RTD library tier

After iii-b2 the seeded RTD set is empty and numerical / string
fields hold bounds inline; the only thing keeping the
``operator_response_type_definitions`` table alive was the
cross-session library workflow (Save-to-library / Add-from-library
buttons on the per-session RTD card + the Settings page library
management).

iii-b3 retires that workflow:

1. NULL ``response_type_definitions.library_origin_id`` on every
   row (the FK column itself drops in step 2). This unwires the
   provenance pointer so cross-tier audit context becomes
   inert; the per-session RTD's own data is unchanged.
2. Drop the ``library_origin_id`` column from
   ``response_type_definitions`` via batch alter (also drops the
   FK).
3. Drop the ``operator_response_type_definitions`` table entirely.

The per-session ``response_type_definitions`` table survives —
operator-authored List RTDs still use it. iii-b4 drops the table
itself + the ``response_type_id`` FK from
``instrument_response_fields``.

Revision ID: d4e1c8b5f372
Revises: c5e2d7a3f81b
Create Date: 2026-05-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e1c8b5f372"
down_revision: Union[str, Sequence[str], None] = "c5e2d7a3f81b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    # 1. NULL all provenance refs (defensive — the column drops
    #    next, but if a downgrade attempt re-creates the column it
    #    won't try to restore stale ids).
    bind.execute(
        sa.text(
            "UPDATE response_type_definitions SET library_origin_id = NULL"
        )
    )
    # 2. Drop the column (which also drops its FK + index).
    with op.batch_alter_table(
        "response_type_definitions", schema=None
    ) as batch_op:
        batch_op.drop_index(
            "ix_response_type_definitions_library_origin_id"
        )
        batch_op.drop_column("library_origin_id")
    # 3. Drop the operator-library table entirely.
    op.drop_table("operator_response_type_definitions")


def downgrade() -> None:
    op.create_table(
        "operator_response_type_definitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "owner_user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("response_type", sa.String(length=64), nullable=False),
        sa.Column("data_type", sa.String(length=16), nullable=False),
        sa.Column("min", sa.Float(), nullable=True),
        sa.Column("max", sa.Float(), nullable=True),
        sa.Column("step", sa.Float(), nullable=True),
        sa.Column("list_csv", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "owner_user_id", "response_type",
            name="uq_operator_rtd_owner_name",
        ),
    )
    with op.batch_alter_table(
        "response_type_definitions", schema=None
    ) as batch_op:
        batch_op.add_column(
            sa.Column("library_origin_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_response_type_definitions_library_origin_id",
            "operator_response_type_definitions",
            ["library_origin_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_response_type_definitions_library_origin_id",
            ["library_origin_id"],
        )
