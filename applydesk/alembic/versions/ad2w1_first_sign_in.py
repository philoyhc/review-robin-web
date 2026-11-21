"""AD2W: when a person first signed in

Revision ID: ad2w1firstsignin
Revises: ad2a3onepending
Create Date: 2026-11-21

Workspace users' *First sign-in* column (segment AD2W). `bound_at` is not
it: a person picked from the directory is bound without signing in, and
their later sign-in finds them by object ID and records nothing. The new
column is set at a person's first sign-in. Existing rows take the time of
their own sign-in binding, the audit event whose actor is themselves.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ad2w1firstsignin"
down_revision = "ad2a3onepending"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("person", sa.Column("first_signed_in_at", sa.DateTime(timezone=True)))
    op.execute(
        "UPDATE person SET first_signed_in_at = ("
        " SELECT MIN(audit_event.at) FROM audit_event"
        " WHERE audit_event.actor_id = person.id"
        " AND audit_event.event_type IN ('person.bound', 'person.created'))"
    )


def downgrade() -> None:
    with op.batch_alter_table("person") as batch:
        batch.drop_column("first_signed_in_at")
