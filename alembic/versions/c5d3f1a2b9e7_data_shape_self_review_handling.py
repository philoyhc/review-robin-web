"""self-review handling chip PR B — data_shapes.self_review_handling

Adds the per-shape Self-review handling chip state column to
``data_shapes``. Three valid values:

* ``include_self`` — fold self-review responses into the
  aggregates (today's behaviour; new default for backfill).
* ``exclude_self`` — drop ``is_self_review=True`` rows from the
  pool.
* ``both`` — emit two aggregate-column blocks side by side
  (one ``_self``, one ``_noself``).

See ``guide/extract_data.md`` § *Self-review handling in
summarizing extracts*. Validation is enforced at the
application layer (``app/services/data_shapes.py``
``VALID_SELF_REVIEW_HANDLING``); the DB ``CHECK`` constraint
is skipped here because SQLite + Postgres handle string
``CHECK`` enforcement differently and the application gate
already rejects unknown strings on save.

Revision ID: c5d3f1a2b9e7
Revises: b4e8c2a9d1f6
Create Date: 2026-05-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c5d3f1a2b9e7"
down_revision: Union[str, Sequence[str], None] = "b4e8c2a9d1f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("data_shapes") as batch:
        batch.add_column(
            sa.Column(
                "self_review_handling",
                sa.String(length=16),
                nullable=False,
                server_default="include_self",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("data_shapes") as batch:
        batch.drop_column("self_review_handling")
