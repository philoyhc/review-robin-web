"""segment 13f pr4: users.is_sys_admin

Adds the workspace-level sys-admin Boolean flag to ``users``.

Lands inert — no service module reads or writes the column until
Segment 16A PR 1's ``require_sys_admin`` dependency lights it
up. Persisted source of truth for the sys-admin list; the
existing ``SYS_ADMIN_EMAILS`` env var becomes a one-shot
bootstrap on first-sign-in (16A PR 1 wires that read). After
bootstrap, the column is authoritative — removing an email from
the env var does NOT auto-demote that operator.

See ``guide/segment_13F_more_db_prep.md`` PR 4 for the schema
rationale and ``guide/segment_16A_sys_admin_page.md`` PR 1 for
the light-up.

Revision ID: 779b90e4b397
Revises: d92f4a710e88
Create Date: 2026-05-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "779b90e4b397"
down_revision: Union[str, Sequence[str], None] = "d92f4a710e88"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_sys_admin",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("is_sys_admin")
