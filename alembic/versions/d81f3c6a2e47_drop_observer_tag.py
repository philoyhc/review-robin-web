"""Drop instrument_view_policies.observer_tag (findings A19)

The column was meant to restrict an instrument's observer grant to
observers carrying a tag. No reader was ever built, no page showed it,
and only the settings CSV round-tripped it. An observer's cohort rule
decides who they see, so the author retired the tag on 2026-10-02
(`guide/findings_2026-10-01_corpus.md` A19). Instrument scoping inside
the cohort rule is a future feature, recorded in
`guide/deferred_consolidated.md`.

The downgrade restores the column empty: the dropped values are not
recoverable, and nothing read them.

Revision ID: d81f3c6a2e47
Revises: c4e9a1d27b58
Create Date: 2026-10-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d81f3c6a2e47"
down_revision: Union[str, Sequence[str], None] = "c4e9a1d27b58"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instrument_view_policies") as batch:
        batch.drop_column("observer_tag")


def downgrade() -> None:
    with op.batch_alter_table("instrument_view_policies") as batch:
        batch.add_column(
            sa.Column("observer_tag", sa.String(length=255), nullable=True)
        )
