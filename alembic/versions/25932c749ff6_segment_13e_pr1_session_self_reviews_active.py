"""segment 13e pr1: sessions.self_reviews_active

Adds the per-session activator flag for the post-12C self-review
model. Existing rows backfill to ``TRUE`` via the server default —
no Python-side update step.

Lands inert — no service or web code reads or writes the column
until 12C-1 PR 1 wires the generation paths and 12C-1 PR 3 wires
the bulk-toggle write. See ``guide/segment_13E_db_prep.md`` PR 1
for the schema rationale and ``guide/segment_12C_self-review_revamp.md``
for the consumer.

Revision ID: 25932c749ff6
Revises: 7c2b94f1a5e3
Create Date: 2026-05-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "25932c749ff6"
down_revision: Union[str, Sequence[str], None] = "7c2b94f1a5e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("sessions") as batch:
        batch.add_column(
            sa.Column(
                "self_reviews_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("sessions") as batch:
        batch.drop_column("self_reviews_active")
