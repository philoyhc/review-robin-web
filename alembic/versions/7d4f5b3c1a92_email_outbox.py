"""segment 9.2: email_outbox table

Revision ID: 7d4f5b3c1a92
Revises: 3c1b9f2a4e51
Create Date: 2026-04-29 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7d4f5b3c1a92"
down_revision: Union[str, Sequence[str], None] = "3c1b9f2a4e51"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "email_outbox",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=True),
        sa.Column("invitation_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("to_email", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["invitation_id"], ["invitations.id"]),
        sa.ForeignKeyConstraint(["reviewer_id"], ["reviewers.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("email_outbox", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_email_outbox_session_id"), ["session_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_email_outbox_reviewer_id"), ["reviewer_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_email_outbox_invitation_id"),
            ["invitation_id"],
            unique=False,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("email_outbox", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_email_outbox_invitation_id"))
        batch_op.drop_index(batch_op.f("ix_email_outbox_reviewer_id"))
        batch_op.drop_index(batch_op.f("ix_email_outbox_session_id"))
    op.drop_table("email_outbox")
