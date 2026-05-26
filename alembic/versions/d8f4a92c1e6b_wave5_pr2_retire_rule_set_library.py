"""Wave 5 PR 5.2 — retire RuleSet library tables + provenance + cache

Drops the operator-library tier entirely along with the
provenance + spec-lock + eligibility-cache scaffolding on
session_rule_sets:

  - Drop ``rule_set_revisions`` table (no longer written; Rule
    Builder retired in PR 5.1).
  - Drop ``operator_rule_sets`` table (cross-session library
    retired with Rule Builder; new sessions no longer auto-copy
    rows in).
  - Drop ``session_rule_sets.library_origin_id`` FK + index +
    column (provenance pointer back to the library row).
  - Drop ``session_rule_sets.is_seeded`` column (seeded RuleSets
    no longer materialised on session create; nothing distinguishes
    seed vs operator-authored anymore).
  - Drop ``session_rule_sets.cached_eligible_pair_count`` +
    ``cached_eligibility_stamp`` columns (the helper that wrote
    them retired with session_library in PR 5.1).

What remains on ``session_rule_sets``: ``id`` / ``session_id`` /
``name`` / ``description`` / ``combinator`` /
``exclude_self_reviews`` / ``seed`` / ``rules_json`` — the thin
authoring shape Band 1's inline editor writes to.

Data loss: pre-migration operator_rule_sets + rule_set_revisions
rows are deleted. session_rule_sets rows retain their core data
(id, name, rules_json, etc.); only the orphan-pointer columns
drop. Acceptable for beta — the user explicitly authorised the
aggressive cut.

Revision ID: d8f4a92c1e6b
Revises: c3a7e9d8b154
Create Date: 2026-05-26
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d8f4a92c1e6b"
down_revision: Union[str, Sequence[str], None] = "c3a7e9d8b154"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop session_rule_sets columns first so the operator_rule_sets
    # FK (via library_origin_id) drops cleanly. batch_alter_table
    # for SQLite compatibility. Drop the library_origin_id index
    # explicitly before the column itself — SQLite's batch
    # table-recreate path needs the index gone first.
    with op.batch_alter_table("session_rule_sets", schema=None) as batch_op:
        batch_op.drop_index("ix_session_rule_sets_library_origin_id")
        batch_op.drop_column("library_origin_id")
        batch_op.drop_column("is_seeded")
        batch_op.drop_column("cached_eligible_pair_count")
        batch_op.drop_column("cached_eligibility_stamp")

    # rule_set_revisions has a FK to operator_rule_sets; drop the
    # child table first.
    op.drop_table("rule_set_revisions")
    op.drop_table("operator_rule_sets")


def downgrade() -> None:
    # Re-create operator_rule_sets + rule_set_revisions with
    # their pre-PR-5.2 schema, and add the dropped columns back
    # to session_rule_sets with their original defaults. The
    # data is not restored — rolling back returns empty tables.
    op.create_table(
        "operator_rule_sets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "scope", sa.String(16), nullable=False, server_default="personal"
        ),
        sa.Column(
            "owner_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "is_seed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "current_revision_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "owner_user_id", "name", name="uq_operator_rule_set_owner_name"
        ),
    )
    op.create_index(
        "ix_operator_rule_sets_owner_user_id",
        "operator_rule_sets",
        ["owner_user_id"],
    )

    op.create_table(
        "rule_set_revisions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "rule_set_id",
            sa.Integer(),
            sa.ForeignKey("operator_rule_sets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("combinator", sa.String(16), nullable=False),
        sa.Column(
            "exclude_self_reviews",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("rules_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_rule_set_revisions_rule_set_id",
        "rule_set_revisions",
        ["rule_set_id"],
    )

    with op.batch_alter_table("session_rule_sets", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "library_origin_id",
                sa.Integer(),
                sa.ForeignKey("operator_rule_sets.id", ondelete="SET NULL"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "is_seeded",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "cached_eligible_pair_count",
                sa.Integer(),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "cached_eligibility_stamp",
                sa.String(64),
                nullable=True,
            )
        )
        batch_op.create_index(
            "ix_session_rule_sets_library_origin_id",
            ["library_origin_id"],
        )
