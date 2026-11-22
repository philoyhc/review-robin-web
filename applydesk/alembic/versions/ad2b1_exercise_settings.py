"""AD2B: an exercise's own settings, and its tags

Revision ID: ad2b1exercisesettings
Revises: ad2m2manyowners
Create Date: 2026-11-22

The `exercise` row takes its settings (segment AD2B,
`applydesk/guide/segment_AD2B_exercises.md`): name, code (one live
exercise per code, ignoring case), description, eligibility, blind, help
contact and timezone (NULL takes the operator settings' default), who
created it, archived and deleted, and a revision; `exercise_tag` its tags.
Existing rows take revision 0: no settings recorded, the pages keep the
sample's until the seed or a save records them.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ad2b1exercisesettings"
down_revision = "ad2m2manyowners"
branch_labels = None
depends_on = None

_LIVE = "code_key IS NOT NULL AND archived_at IS NULL AND deleted_at IS NULL"


def upgrade() -> None:
    with op.batch_alter_table("exercise") as batch:
        batch.add_column(sa.Column("name", sa.String(200)))
        batch.add_column(sa.Column("code", sa.String(40)))
        batch.add_column(sa.Column("code_key", sa.String(40)))
        batch.add_column(sa.Column("description", sa.Text()))
        batch.add_column(sa.Column("eligibility", sa.String(16)))
        batch.add_column(
            sa.Column("blind", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(sa.Column("help_contact", sa.String(320)))
        batch.add_column(sa.Column("timezone", sa.String(64)))
        batch.add_column(sa.Column("created_by_id", sa.Integer()))
        batch.add_column(sa.Column("archived_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("revision", sa.Integer(), nullable=False, server_default="0"))
        batch.create_foreign_key("fk_exercise_created_by", "person", ["created_by_id"], ["id"])
    op.create_index(
        "uq_exercise_live_code",
        "exercise",
        ["code_key"],
        unique=True,
        sqlite_where=sa.text(_LIVE),
        postgresql_where=sa.text(_LIVE),
    )
    op.create_table(
        "exercise_tag",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "exercise_id",
            sa.Integer(),
            sa.ForeignKey("exercise.id", name="fk_exercise_tag_exercise"),
            nullable=False,
        ),
        sa.Column("label", sa.String(40), nullable=False),
        sa.Column("label_key", sa.String(40), nullable=False),
        sa.UniqueConstraint("exercise_id", "label_key", name="uq_exercise_tag_label"),
    )
    op.create_index("ix_exercise_tag_exercise_id", "exercise_tag", ["exercise_id"])


def downgrade() -> None:
    op.drop_index("ix_exercise_tag_exercise_id", table_name="exercise_tag")
    op.drop_table("exercise_tag")
    op.drop_index("uq_exercise_live_code", table_name="exercise")
    with op.batch_alter_table("exercise") as batch:
        batch.drop_constraint("fk_exercise_created_by", type_="foreignkey")
        for column in (
            "revision",
            "deleted_at",
            "archived_at",
            "created_by_id",
            "timezone",
            "help_contact",
            "blind",
            "eligibility",
            "description",
            "code_key",
            "code",
            "name",
        ):
            batch.drop_column(column)
