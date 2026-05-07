"""segment 13a pr1: rule_sets + rule_set_revisions

Adds the two persistence tables for the RuleBased assignment library.
The rule tree itself lives as a JSON column inside ``rule_set_revisions``
rather than normalised — see
``guide/segment_13A_rulebased_assignment_builder.md`` §"DB shape" for
the rationale.

No engine, no UI, no operator-visible change — PR 1 is the persistence
layer that PR 2's pure-Python evaluator and PR 3's seed installer
build on.

Revision ID: 8d57b772ffc4
Revises: c4f6a8b0d2e5
Create Date: 2026-05-07 11:48:50.314450

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "8d57b772ffc4"
down_revision: Union[str, Sequence[str], None] = "c4f6a8b0d2e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rule_sets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False, index=True),
        sa.Column(
            "owner_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("is_seed", sa.Boolean(), nullable=False),
        sa.Column("current_revision_id", sa.Integer(), nullable=True),
        sa.Column(
            "deleted_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "rule_set_revisions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "rule_set_id",
            sa.Integer(),
            sa.ForeignKey("rule_sets.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("combinator", sa.String(length=16), nullable=False),
        sa.Column("exclude_self_reviews", sa.Boolean(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("rules_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.UniqueConstraint(
            "rule_set_id", "revision_no", name="uq_rule_set_revision_no"
        ),
    )

    # The forward FK from ``rule_sets.current_revision_id`` to
    # ``rule_set_revisions.id`` is added after both tables exist to
    # avoid the chicken-and-egg DDL ordering.
    with op.batch_alter_table("rule_sets") as batch:
        batch.create_foreign_key(
            "fk_rule_sets_current_revision_id",
            "rule_set_revisions",
            ["current_revision_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("rule_sets") as batch:
        batch.drop_constraint(
            "fk_rule_sets_current_revision_id", type_="foreignkey"
        )
    op.drop_table("rule_set_revisions")
    op.drop_table("rule_sets")
