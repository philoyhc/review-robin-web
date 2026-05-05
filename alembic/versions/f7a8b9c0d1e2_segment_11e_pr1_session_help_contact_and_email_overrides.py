"""Segment 11E PR 1: review_sessions.help_contact + email_template_overrides

Adds the two columns the operator-editable email template editor
(per ``guide/archive/segment_11E_email_template_editor.md``) and the
``{{help_contact}}`` merge field both consume:

* ``help_contact`` (String(320), nullable) — operational help contact
  for "I have questions about the review process." Surfaced in the
  session create / edit form, on the reviewer surface as a small
  "Questions? Contact X" line, and as the ``$help_contact`` merge
  field at template render time.
* ``email_template_overrides`` (JSON, nullable) — operator overrides
  keyed by ``{invitation_subject, invitation_body, invitation_cc,
  invitation_bcc, reminder_subject, reminder_body, reminder_cc,
  reminder_bcc}``. Defaults live in code; ``NULL`` / missing keys
  fall through to defaults. No new table — 1:1 with sessions, no
  separate lifecycle.

Revision ID: f7a8b9c0d1e2
Revises: d3e4f5a6b7c8
Create Date: 2026-05-05 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("help_contact", sa.String(length=320), nullable=True),
    )
    op.add_column(
        "sessions",
        sa.Column("email_template_overrides", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sessions", "email_template_overrides")
    op.drop_column("sessions", "help_contact")
