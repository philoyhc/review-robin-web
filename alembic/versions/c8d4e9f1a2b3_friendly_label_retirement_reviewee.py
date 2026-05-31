"""friendly-label retirement: drop reviewee fixed-column overrides

Data-only migration. Drops any persisted ``session_field_labels``
rows for the three reviewee identity columns
(``name`` / ``email_or_identifier`` / ``profile_link``) so the
resolver returns the canonical default everywhere. The editor UI
+ slot allowlists are retired in the same PR; existing operator
overrides for these slots become inaccessible without this drop.

Per ``guide/participant_model_upgrade.md`` §3.7 — the rename
affordance was redundant for these columns and beta feedback
flagged it; "no data loss in any meaningful sense" because
operators were paying configuration cost for no signal.

Downgrade cannot restore the dropped overrides (we didn't snapshot
the deleted rows). Restoring is a no-op; the resolver would still
return the canonical defaults until an operator re-enters the
overrides through the (no-longer-rendered) editor surface.

Revision ID: c8d4e9f1a2b3
Revises: b3e7d2a4c8f1
Create Date: 2026-05-31

"""
from typing import Sequence, Union

from alembic import op


revision: str = "c8d4e9f1a2b3"
down_revision: Union[str, Sequence[str], None] = "b3e7d2a4c8f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM session_field_labels
         WHERE source_type = 'reviewee'
           AND source_field IN ('name', 'email_or_identifier', 'profile_link')
        """
    )


def downgrade() -> None:
    # Data drop is one-way — see migration docstring.
    pass
