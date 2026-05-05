"""Segment 11E PR 4: per-operator SMTP settings on users

Adds the seven columns the operator Settings page (per
``guide/segment_11E_email_template_editor.md`` PR 4) populates
when an operator configures their Outlook / Office 365 SMTP
credentials. Storage is per-user because Segment 11E adopts the
"send-as-me" identity model — the operator who hits Send in
Manage Invitations (Segment 11C PR F) sends from their own
mailbox.

Columns:
* ``smtp_host`` (String(255), nullable) — SMTP server hostname.
* ``smtp_port`` (Integer, nullable) — typically 587 (STARTTLS) /
  465 (SSL).
* ``smtp_username`` (String(320), nullable) — usually equals the
  ``From`` email.
* ``smtp_password_encrypted`` (LargeBinary, nullable) —
  ``cryptography.fernet`` ciphertext keyed off the
  ``SMTP_ENCRYPTION_KEY`` env var; the plaintext is never
  persisted.
* ``smtp_from_display_name`` (String(255), nullable) — optional;
  falls back to ``smtp_username`` when blank.
* ``smtp_encryption`` (String(16), nullable) — ``"starttls"`` /
  ``"ssl"``.
* ``smtp_transport`` (String(16), nullable, default ``"smtp"``) —
  reserved for the future Microsoft Graph backend swap. Today
  the only legal value is ``"smtp"``; service-layer enforces.

Revision ID: a1b2c3d4e5f7
Revises: f7a8b9c0d1e2
Create Date: 2026-05-05 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, Sequence[str], None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("smtp_host", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "users", sa.Column("smtp_port", sa.Integer(), nullable=True)
    )
    op.add_column(
        "users",
        sa.Column("smtp_username", sa.String(length=320), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("smtp_password_encrypted", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("smtp_from_display_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("smtp_encryption", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "smtp_transport",
            sa.String(length=16),
            nullable=True,
            server_default="smtp",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "smtp_transport")
    op.drop_column("users", "smtp_encryption")
    op.drop_column("users", "smtp_from_display_name")
    op.drop_column("users", "smtp_password_encrypted")
    op.drop_column("users", "smtp_username")
    op.drop_column("users", "smtp_port")
    op.drop_column("users", "smtp_host")
