"""Drop instruments.responses_visible_when_closed (findings B21)

The flag once chose whether a closed instrument's responses showed on
the reviewer surface. The per-instrument visibility policy took that
over (findings G10, 2026-10-01), the Instruments page's toggle had
already retired, and only the settings CSV, Replicate and an unused
route still touched the column. The author retired it on 2026-10-03
(`guide/findings_2026-10-01_corpus.md` B21).

The downgrade restores the column NOT NULL with a false default: the
dropped values are not recoverable, and nothing read them.

Revision ID: a2d16ffeb59a
Revises: e2a7c4f9b130
Create Date: 2026-10-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a2d16ffeb59a"
down_revision: Union[str, Sequence[str], None] = "e2a7c4f9b130"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instruments") as batch:
        batch.drop_column("responses_visible_when_closed")


def downgrade() -> None:
    with op.batch_alter_table("instruments") as batch:
        batch.add_column(
            sa.Column(
                "responses_visible_when_closed",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
