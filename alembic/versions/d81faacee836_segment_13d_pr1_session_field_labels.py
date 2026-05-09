"""segment 13d pr1: session_field_labels

Adds the per-session friendly-label override table that backs
Segment 15A's resolver. Each row overrides the default display
label for one ``(source_type, source_field)`` pair within one
session.

Lands inert — no service module reads or writes the table until
15A Slice 1 introduces ``app/services/field_labels.py``. See
``guide/segment_15A_friendly_labels.md`` Slice 1 for the
end-to-end design and ``guide/segment_13D_db_prep.md`` PR 1 for
the schema rationale.

Revision ID: d81faacee836
Revises: 3213fb59371b
Create Date: 2026-05-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d81faacee836"
down_revision: Union[str, Sequence[str], None] = "3213fb59371b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "session_field_labels",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_field", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.UniqueConstraint(
            "session_id",
            "source_type",
            "source_field",
            name="uq_session_field_label",
        ),
    )


def downgrade() -> None:
    op.drop_table("session_field_labels")
