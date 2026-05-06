"""Segment 11C PR 2: email_outbox.cc_emails / bcc_emails

Adds CC / BCC storage to the email outbox so the queue path can
carry the per-session CC / BCC override values that the
Segment 11E PR 1 ``email_template_overrides`` JSON
(``invitation_cc`` / ``invitation_bcc`` / ``reminder_cc`` /
``reminder_bcc``) already lets operators define.

Both columns are ``Text`` with a comma-separated list convention
(matching the editor's input shape). They land unused at send
time until Segment 11C Part 2 (PR F) wires the transport dispatch;
storing them now keeps the queue path shape-stable across the
cutover.

Revision ID: b3d5e7f9a1c4
Revises: a1b2c3d4e5f7
Create Date: 2026-05-06 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3d5e7f9a1c4"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "email_outbox",
        sa.Column("cc_emails", sa.Text(), nullable=True),
    )
    op.add_column(
        "email_outbox",
        sa.Column("bcc_emails", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("email_outbox", "bcc_emails")
    op.drop_column("email_outbox", "cc_emails")
