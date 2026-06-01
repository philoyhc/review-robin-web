"""participants S14: add per-window visibility-mode columns

Expand step for the Band 3 editor redesign — splits the single
``visible_when`` + ``granularity`` + ``identification`` triple
into two per-window pairs so the editor's column axis can be
the window ("Session ongoing" / "Responses released") instead
of the mode.

What lands:

- ``instrument_view_policies.while_ongoing_granularity``
  (String(16), NULL)
- ``instrument_view_policies.while_ongoing_identification``
  (String(16), NULL)
- ``instrument_view_policies.after_release_granularity``
  (String(16), NULL)
- ``instrument_view_policies.after_release_identification``
  (String(16), NULL)

Each pair encodes the audience's mode in that window;
``NULL ≡ off in this window``. The pair (``aggregated``,
``identified``) is reserved-incoherent and rejected by the
service.

Backfill from existing rows based on the old quadruple
(``enabled``, ``granularity``, ``identification``,
``visible_when``):

- ``enabled = FALSE`` → both pairs stay NULL.
- ``enabled = TRUE`` AND ``visible_when = 'while_ongoing'`` →
  only the ``while_ongoing_*`` pair set.
- ``enabled = TRUE`` AND ``visible_when = 'after_release'`` →
  only the ``after_release_*`` pair set.
- ``enabled = TRUE`` AND ``visible_when = 'throughout'`` →
  both pairs set to the same mode.
- ``enabled = TRUE`` AND ``visible_when IS NULL`` OR
  ``'always'`` → treat as ``throughout`` for back-compat (the
  ``always`` value was reserved for operator forward-
  compatibility and didn't ship through the editor).

**Old columns are NOT dropped** in this migration — this is
the additive half of an expand → migrate → contract
sequence. The service mirror-writes both old and new so the
new columns track the operator's intent from this slice on;
the editor / route / template swap to read-from-new comes in
the follow-on PR, and the old-column drop comes after that.

Revision ID: a7e3b1d92c64
Revises: f4a92b3c6d18
Create Date: 2026-06-01
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a7e3b1d92c64"
down_revision: Union[str, Sequence[str], None] = "f4a92b3c6d18"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instrument_view_policies") as batch_op:
        batch_op.add_column(
            sa.Column(
                "while_ongoing_granularity",
                sa.String(length=16),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "while_ongoing_identification",
                sa.String(length=16),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "after_release_granularity",
                sa.String(length=16),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "after_release_identification",
                sa.String(length=16),
                nullable=True,
            )
        )

    # Backfill the new pair columns from existing rows.
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, enabled, granularity, identification, "
            "visible_when FROM instrument_view_policies"
        )
    ).fetchall()
    for row in rows:
        if not row.enabled:
            continue
        # Default the absent window to throughout when the
        # operator's intent is "viewable, but the window value is
        # missing / reserved-always"; the editor never wrote
        # ``always`` and a NULL ``visible_when`` is the inert
        # pre-W15 default that the resolver would have skipped
        # anyway. Map both to "throughout" so the row's intent
        # carries forward unambiguously.
        when = row.visible_when or "throughout"
        if when == "always":
            when = "throughout"
        sets_while = when in ("while_ongoing", "throughout")
        sets_after = when in ("after_release", "throughout")
        params = {
            "id": row.id,
            "wg": row.granularity if sets_while else None,
            "wi": row.identification if sets_while else None,
            "ag": row.granularity if sets_after else None,
            "ai": row.identification if sets_after else None,
        }
        bind.execute(
            sa.text(
                "UPDATE instrument_view_policies SET "
                "while_ongoing_granularity = :wg, "
                "while_ongoing_identification = :wi, "
                "after_release_granularity = :ag, "
                "after_release_identification = :ai "
                "WHERE id = :id"
            ),
            params,
        )


def downgrade() -> None:
    with op.batch_alter_table("instrument_view_policies") as batch_op:
        batch_op.drop_column("after_release_identification")
        batch_op.drop_column("after_release_granularity")
        batch_op.drop_column("while_ongoing_identification")
        batch_op.drop_column("while_ongoing_granularity")
