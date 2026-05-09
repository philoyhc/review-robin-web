"""segment 13d pr3: operator_response_type_definitions + library_origin_id

Two related changes packaged in one migration:

1. New ``operator_response_type_definitions`` table — operator-
   library tier for RTDs (mirror of ``operator_rule_sets`` on
   the RuleSet side, minus revisioning).
2. New ``response_type_definitions.library_origin_id`` column —
   provenance pointer back to the operator-library row a
   per-session RTD was copied from.

Lands inert — no service module reads or writes the new shape.
The existing seed materialisation
(``SEEDED_RESPONSE_TYPE_DEFINITIONS`` →
``ensure_default_response_type_definitions``) keeps its current
behaviour. Segment 15C wires the auto-copy-on-session-create +
Save-to-library / Add-from-library flows.

See ``guide/segment_13D_db_prep.md`` PR 3 for the schema
rationale and ``guide/segment_15C_operator_libraries.md`` for
the end-to-end design.

Revision ID: f6183d235e59
Revises: e216f472ac47
Create Date: 2026-05-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6183d235e59"
down_revision: Union[str, Sequence[str], None] = "e216f472ac47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "operator_response_type_definitions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "owner_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("response_type", sa.String(length=64), nullable=False),
        sa.Column("data_type", sa.String(length=16), nullable=False),
        sa.Column("min", sa.Float(), nullable=True),
        sa.Column("max", sa.Float(), nullable=True),
        sa.Column("step", sa.Float(), nullable=True),
        sa.Column("list_csv", sa.Text(), nullable=True),
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
        sa.UniqueConstraint(
            "owner_user_id",
            "response_type",
            name="uq_operator_rtd_owner_name",
        ),
    )

    # Add the column without an inline FK (anonymous constraints
    # break SQLite batch mode), then attach the FK + index in a
    # second batch — same shape as 8b3c1d4e5f7a's
    # `instrument_response_fields.response_type_id` add.
    with op.batch_alter_table("response_type_definitions") as batch:
        batch.add_column(
            sa.Column("library_origin_id", sa.Integer(), nullable=True)
        )
    with op.batch_alter_table("response_type_definitions") as batch:
        batch.create_foreign_key(
            "fk_response_type_definitions_library_origin_id",
            "operator_response_type_definitions",
            ["library_origin_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index(
            "ix_response_type_definitions_library_origin_id",
            ["library_origin_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("response_type_definitions") as batch:
        batch.drop_index("ix_response_type_definitions_library_origin_id")
        batch.drop_constraint(
            "fk_response_type_definitions_library_origin_id",
            type_="foreignkey",
        )
        batch.drop_column("library_origin_id")
    op.drop_table("operator_response_type_definitions")
