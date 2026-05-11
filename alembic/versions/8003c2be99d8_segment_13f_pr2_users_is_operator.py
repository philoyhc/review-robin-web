"""segment 13f pr2: users.is_operator

Adds the workspace-level operator-allowlist Boolean flag to
``users``. This is the persisted source of truth for the
Option C strict-allowlist access model (locked 2026-05-11) —
only operators a sys-admin explicitly admits can use operator
routes.

Lands inert — no service module reads or writes the column
until Segment 16A PR 1's ``require_operator`` dependency lights
it up. After light-up, the read-path predicate is
``is_operator OR is_sys_admin`` (sys-admin implies operator).
Bootstrap source on first-sign-in is a new ``OPERATOR_EMAILS``
env var, mirroring the ``SYS_ADMIN_EMAILS`` pattern from
13F PR 1. After bootstrap, the persisted column is
authoritative — removing an email from the env var does NOT
auto-revoke; revocation goes through 16A PR 6's workspace UI.

See ``guide/segment_13F_more_db_prep.md`` PR 2 for the schema
rationale and ``guide/segment_16A_sys_admin_page.md`` PR 1 for
the light-up.

Revision ID: 8003c2be99d8
Revises: 779b90e4b397
Create Date: 2026-05-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "8003c2be99d8"
down_revision: Union[str, Sequence[str], None] = "779b90e4b397"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_operator",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("is_operator")
