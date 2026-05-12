"""session_rule_sets.is_seeded

Adds an ``is_seeded`` Boolean column to ``session_rule_sets`` so
seed-originated copies (materialised on session create from the
``SEEDED_RULE_SETS`` code constant) can be marked workspace-locked
the same way ``response_type_definitions.is_seeded`` locks the
ten baseline RTDs.

Backfill: any existing ``session_rule_sets`` row whose
``library_origin_id IS NULL`` and whose ``name`` matches one of
the workspace-shipped seed names gets ``is_seeded = TRUE``. Rows
that arrived via Save-As or via Add-from-library leave the
default ``FALSE``.

Behavioural light-up follows in the service layer: edit / rename /
delete / save-to-library all refuse on seeded rows. Operators
customise via Copy → Save-As (mirrors the RTD spec-lock model).

Revision ID: a4c8e91b2d6f
Revises: 8003c2be99d8
Create Date: 2026-05-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a4c8e91b2d6f"
down_revision: Union[str, Sequence[str], None] = "8003c2be99d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("session_rule_sets", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_seeded",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
            )
        )

    # Backfill: rows materialised via ``materialise_seed_rule_sets``
    # match by name (the workspace seed names) and have a NULL
    # ``library_origin_id`` (seeds bypass the operator library
    # tier). The names come from ``app.services.rules.seeds``;
    # inlining them keeps this migration self-contained and stable
    # against future renames of the seed constants.
    seed_names = (
        "Full Matrix",
        "Intra-group peer review",
        "Cross-group peer review",
        "Same group, different role",
        "Three reviewers per reviewee",
    )
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE session_rule_sets SET is_seeded = TRUE "
            "WHERE library_origin_id IS NULL "
            "AND name IN :names"
        ).bindparams(sa.bindparam("names", expanding=True)),
        {"names": list(seed_names)},
    )


def downgrade() -> None:
    with op.batch_alter_table("session_rule_sets", schema=None) as batch_op:
        batch_op.drop_column("is_seeded")
