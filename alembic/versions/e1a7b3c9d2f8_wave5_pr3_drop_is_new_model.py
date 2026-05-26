"""Wave 5 PR 5.3 — drop instruments.is_new_model

Drops the ``is_new_model`` discriminator column from
``instruments``. After this migration, every instrument is
implicitly a (former) new-model instrument: the legacy individual
+ group cards retired in PR 5.3's template collapse, and the
service / view / route layers no longer branch on
``is_new_model``. Schema-wise this is a single column drop.

Data preservation: every existing instrument row keeps its
identity / sort spec / rule_set_id / response fields / display
fields — only the discriminator column drops. Legacy rows
(pre-PR-5.3 ``is_new_model=False``) and new-model rows
(``is_new_model=True``) are now indistinguishable, which is
exactly the point.

Revision ID: e1a7b3c9d2f8
Revises: d8f4a92c1e6b
Create Date: 2026-05-26
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e1a7b3c9d2f8"
down_revision: Union[str, Sequence[str], None] = "d8f4a92c1e6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instruments", schema=None) as batch_op:
        batch_op.drop_column("is_new_model")


def downgrade() -> None:
    # Restore the column with the legacy default (``False``). The
    # original is_new_model=True flags are not recoverable — every
    # row resurrects as ``False``.
    with op.batch_alter_table("instruments", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_new_model",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
