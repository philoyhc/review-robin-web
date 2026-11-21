"""AD2W: when a person first signed in

Revision ID: ad2w1firstsignin
Revises: ad2a3onepending
Create Date: 2026-11-21

Workspace users' *First sign-in* column (segment AD2W). `bound_at` is not
it: a person picked from the directory is bound without signing in, and
their later sign-in finds them by object ID and records nothing. The new
column is set at a person's first sign-in. Existing rows take the time of
their own sign-in binding: the audit event that names them and whose actor
is themselves.
"""

from __future__ import annotations

import json
from typing import Any

import sqlalchemy as sa
from alembic import op

revision = "ad2w1firstsignin"
down_revision = "ad2a3onepending"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("person", sa.Column("first_signed_in_at", sa.DateTime(timezone=True)))
    # A person's own sign-in binding: a person.created or person.bound
    # event whose actor is the person it names (an administrator's pick of
    # someone else names them as actor and the other as refs; Codex on
    # #4121). Read in Python, so the JSON detail reads the same on SQLite
    # and Postgres.
    bind = op.get_bind()
    first: dict[int, object] = {}
    rows = bind.execute(
        sa.text(
            "SELECT actor_id, at, detail FROM audit_event"
            " WHERE event_type IN ('person.created', 'person.bound') AND actor_id IS NOT NULL"
            " ORDER BY at"
        )
    )
    for actor_id, at, raw in rows:
        detail: dict[str, Any] = json.loads(raw) if isinstance(raw, str) else (raw or {})
        refs: dict[str, Any] = detail.get("refs") or {}
        if refs.get("person_id") == actor_id and actor_id not in first:
            first[actor_id] = at
    for person_id, at in first.items():
        bind.execute(
            sa.text("UPDATE person SET first_signed_in_at = :at WHERE id = :id"),
            {"at": at, "id": person_id},
        )


def downgrade() -> None:
    with op.batch_alter_table("person") as batch:
        batch.drop_column("first_signed_in_at")
