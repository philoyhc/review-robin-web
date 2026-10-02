"""Retire the reviewer's "Anonymized summaries" released cell (findings A18)

The peer-reviewer audience's ``after_release`` cell accepted ``summarized``
(``aggregated`` + ``deidentified``), but no reviewer-facing summary view
was ever built: since #2723 such a grant hides the reviewer's answers like
an off cell does. The author retired the option on 2026-10-02
(`guide/findings_2026-10-01_corpus.md` A18), so the cell is Raw or off.

This sets every stored peer-reviewer ``after_release`` pair whose
granularity is ``aggregated`` to off: the retired summary, and the
reserved-incoherent ``aggregated`` + ``identified`` pair, which already
read as off. Since #2723 that is what the reviewer's read-back showed,
though the transparency card and the editor still labelled it. The downgrade is a no-op: the cleared
values are not recoverable, and off is a valid state before and after.

Revision ID: e2a7c4f9b130
Revises: d81f3c6a2e47
Create Date: 2026-10-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e2a7c4f9b130"
down_revision: Union[str, Sequence[str], None] = "d81f3c6a2e47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE instrument_view_policies "
            "SET after_release_granularity = NULL, "
            "after_release_identification = NULL "
            "WHERE audience = 'peer_reviewer' "
            "AND after_release_granularity = 'aggregated'"
        )
    )


def downgrade() -> None:
    pass
