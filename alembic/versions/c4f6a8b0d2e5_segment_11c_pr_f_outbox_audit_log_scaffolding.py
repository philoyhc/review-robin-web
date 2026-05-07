"""Segment 11C PR F: email_outbox audit-log scaffolding

Adds the seven nullable audit-log columns the spec's
``email_infra_options.md`` "Future-target additions" table calls
out: ``error_message``, ``from_address``, ``backend``,
``backend_message_id``, ``delivered_at``, ``payload_hash``,
``correlation_id`` (the last is indexed because the Segment 14-1
dispatch helper looks rows up by it on idempotent retry).

Pure additive — all columns nullable, no defaults beyond column
defaults, no backfill. The columns sit inert until Segment 14-1
Part A wires the actual transport dispatch against this stable
schema. Today's enqueue paths continue to write only ``status``
(``queued`` / ``sent``), ``kind`` (``invitation`` / ``reminder``),
``cc_emails``, ``bcc_emails``, and the existing baseline columns.

Revision ID: c4f6a8b0d2e5
Revises: b3d5e7f9a1c4
Create Date: 2026-05-07 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4f6a8b0d2e5"
down_revision: Union[str, Sequence[str], None] = "b3d5e7f9a1c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("email_outbox", schema=None) as batch_op:
        batch_op.add_column(sa.Column("error_message", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("from_address", sa.String(length=320), nullable=True)
        )
        batch_op.add_column(sa.Column("backend", sa.String(length=32), nullable=True))
        batch_op.add_column(
            sa.Column("backend_message_id", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("payload_hash", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(
            sa.Column("correlation_id", sa.String(length=128), nullable=True)
        )
        batch_op.create_index(
            batch_op.f("ix_email_outbox_correlation_id"),
            ["correlation_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("email_outbox", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_email_outbox_correlation_id"))
        batch_op.drop_column("correlation_id")
        batch_op.drop_column("payload_hash")
        batch_op.drop_column("delivered_at")
        batch_op.drop_column("backend_message_id")
        batch_op.drop_column("backend")
        batch_op.drop_column("from_address")
        batch_op.drop_column("error_message")
