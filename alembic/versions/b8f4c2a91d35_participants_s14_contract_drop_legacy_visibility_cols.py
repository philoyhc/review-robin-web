"""participants S14 contract: drop legacy visibility columns

Contract step for the Band 3 editor redesign — drops the
single-mode ``enabled`` / ``granularity`` / ``identification`` /
``visible_when`` quadruple now that the per-window pair columns
(``while_ongoing_*`` / ``after_release_*``) from
``a7e3b1d92c64`` carry the operator's intent end-to-end.

PR B/C (#1730) flipped the service + route + view + template
over to the per-window columns and stopped reading the legacy
ones; the service kept mirror-writing them so a rolled-back
deploy stayed safe. With this PR landing the service stops the
mirror writes and the columns disappear.

What lands:

- drop ``instrument_view_policies.enabled``
- drop ``instrument_view_policies.granularity``
- drop ``instrument_view_policies.identification``
- drop ``instrument_view_policies.visible_when``

Downgrade re-adds the columns (NULL for the String ones,
``false`` for ``enabled``) and best-effort backfills from the
per-window pairs: ``enabled`` true iff either window is set;
``granularity`` / ``identification`` from the while_ongoing
pair when present else the after_release pair;
``visible_when`` is ``"throughout"`` when both windows are set,
``"while_ongoing"`` / ``"after_release"`` for the single-window
case, else NULL.

Revision ID: b8f4c2a91d35
Revises: a7e3b1d92c64
Create Date: 2026-06-01
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b8f4c2a91d35"
down_revision: Union[str, Sequence[str], None] = "a7e3b1d92c64"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instrument_view_policies") as batch_op:
        batch_op.drop_column("visible_when")
        batch_op.drop_column("identification")
        batch_op.drop_column("granularity")
        batch_op.drop_column("enabled")


def downgrade() -> None:
    with op.batch_alter_table("instrument_view_policies") as batch_op:
        batch_op.add_column(
            sa.Column(
                "enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "granularity",
                sa.String(length=16),
                nullable=False,
                server_default="row",
            )
        )
        batch_op.add_column(
            sa.Column(
                "identification",
                sa.String(length=16),
                nullable=False,
                server_default="identified",
            )
        )
        batch_op.add_column(
            sa.Column(
                "visible_when",
                sa.String(length=16),
                nullable=True,
            )
        )

    # Best-effort backfill from the per-window pairs.
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, while_ongoing_granularity, "
            "while_ongoing_identification, after_release_granularity, "
            "after_release_identification FROM instrument_view_policies"
        )
    ).fetchall()
    for row in rows:
        while_on = row.while_ongoing_granularity is not None
        after_on = row.after_release_granularity is not None
        if not while_on and not after_on:
            continue
        if while_on:
            granularity = row.while_ongoing_granularity
            identification = row.while_ongoing_identification
        else:
            granularity = row.after_release_granularity
            identification = row.after_release_identification
        if while_on and after_on:
            visible_when = "throughout"
        elif while_on:
            visible_when = "while_ongoing"
        else:
            visible_when = "after_release"
        bind.execute(
            sa.text(
                "UPDATE instrument_view_policies SET enabled = TRUE, "
                "granularity = :g, identification = :i, "
                "visible_when = :w WHERE id = :id"
            ),
            {
                "id": row.id,
                "g": granularity,
                "i": identification,
                "w": visible_when,
            },
        )

    with op.batch_alter_table("instrument_view_policies") as batch_op:
        batch_op.alter_column("granularity", server_default=None)
        batch_op.alter_column("identification", server_default=None)
        batch_op.alter_column("enabled", server_default=None)
