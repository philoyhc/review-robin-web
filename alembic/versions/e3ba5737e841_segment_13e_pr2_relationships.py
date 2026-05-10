"""segment 13e pr2: relationships table

Creates the per-pair attributes table that 15D's "Relationships"
page reads / writes. Replaces the pre-15D ``Assignment.context``
JSON column as the home for ``pair_context_*`` tag values; lifts
the join out of the assignments table so per-pair attributes
exist whether or not a rule has materialised an assignment.

Lands inert — no service or web code reads or writes the table
until 15D PR 1 introduces ``app/services/relationships.py`` (the
per-entity importer + serializer) and 15D PR 4 wires the
generation-path consumption.

See ``guide/segment_13E_db_prep.md`` PR 2 for the schema
rationale and ``guide/segment_15D_assignments_revamp.md`` for the
end-to-end design.

Revision ID: e3ba5737e841
Revises: 25932c749ff6
Create Date: 2026-05-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e3ba5737e841"
down_revision: Union[str, Sequence[str], None] = "25932c749ff6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "relationships",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "reviewer_id",
            sa.Integer(),
            sa.ForeignKey("reviewers.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "reviewee_id",
            sa.Integer(),
            sa.ForeignKey("reviewees.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("tag_1", sa.String(length=255), nullable=True),
        sa.Column("tag_2", sa.String(length=255), nullable=True),
        sa.Column("tag_3", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="active",
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
        sa.UniqueConstraint(
            "session_id",
            "reviewer_id",
            "reviewee_id",
            name="uq_relationships_session_reviewer_reviewee",
        ),
    )


def downgrade() -> None:
    op.drop_table("relationships")
