"""session lifecycle 9.1: instrument acceptance + visibility + deadline_closed_at

Revision ID: 3c1b9f2a4e51
Revises: a6ce41175175
Create Date: 2026-04-29 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3c1b9f2a4e51"
down_revision: str | Sequence[str] | None = "a6ce41175175"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("instruments", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "accepting_responses",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column(
                "responses_visible_when_closed",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column(
                "deadline_closed_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("instruments", schema=None) as batch_op:
        batch_op.drop_column("deadline_closed_at")
        batch_op.drop_column("responses_visible_when_closed")
        batch_op.drop_column("accepting_responses")
