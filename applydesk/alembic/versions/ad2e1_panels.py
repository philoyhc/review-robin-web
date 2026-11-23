"""AD2E: panels, the Panels roster and memberships; a searchable name key

Revision ID: ad2e1panels
Revises: ad2c1process
Create Date: 2026-11-23

An exercise's panels in the database (segment AD2E,
`applydesk/guide/segment_AD2E_panels.md`): `panel`, keyed per exercise and
named uniquely among its live panels; `roster_entry`, a row per person on
the Panels table with their name and note; `panel_member`, an entry on a
panel; and `exercise.panels_revision`, 0 until Panels is first saved.
`person.display_name_key` is the casefolded name the people searches
match (AD-127), filled here for every person on record.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ad2e1panels"
down_revision: str | Sequence[str] | None = "ad2c1process"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "panel",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("exercise_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("name_key", sa.String(length=240), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercise.id"], name="fk_panel_exercise"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exercise_id", "key", name="uq_panel_key"),
    )
    with op.batch_alter_table("panel", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_panel_exercise_id"), ["exercise_id"], unique=False)
        batch_op.create_index(
            "uq_panel_live_name",
            ["exercise_id", "name_key"],
            unique=True,
            sqlite_where=sa.text("retired_at IS NULL"),
            postgresql_where=sa.text("retired_at IS NULL"),
        )

    op.create_table(
        "roster_entry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("exercise_id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercise.id"], name="fk_roster_entry_exercise"),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"], name="fk_roster_entry_person"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exercise_id", "person_id", name="uq_roster_entry_pair"),
    )
    with op.batch_alter_table("roster_entry", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_roster_entry_exercise_id"), ["exercise_id"], unique=False
        )

    op.create_table(
        "panel_member",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("panel_id", sa.Integer(), nullable=False),
        sa.Column("roster_entry_id", sa.Integer(), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["panel_id"], ["panel.id"], name="fk_panel_member_panel"),
        sa.ForeignKeyConstraint(
            ["roster_entry_id"], ["roster_entry.id"], name="fk_panel_member_entry"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("panel_id", "roster_entry_id", name="uq_panel_member_pair"),
    )
    with op.batch_alter_table("panel_member", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_panel_member_panel_id"), ["panel_id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_panel_member_roster_entry_id"), ["roster_entry_id"], unique=False
        )

    with op.batch_alter_table("exercise", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("panels_revision", sa.Integer(), server_default="0", nullable=False)
        )

    with op.batch_alter_table("person", schema=None) as batch_op:
        # Three times the name's width: casefolding lengthens some letters
        # ("ß" is "ss"), at most to three (Codex on #4169).
        batch_op.add_column(sa.Column("display_name_key", sa.String(length=765), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_person_display_name_key"), ["display_name_key"], unique=False
        )
    # Python's casefold, as the model's: neither database's lower() is it.
    person = sa.table(
        "person",
        sa.column("id", sa.Integer()),
        sa.column("display_name", sa.String()),
        sa.column("display_name_key", sa.String()),
    )
    conn = op.get_bind()
    named = conn.execute(
        sa.select(person.c.id, person.c.display_name).where(person.c.display_name.is_not(None))
    ).all()
    for person_id, name in named:
        conn.execute(
            sa.update(person)
            .where(person.c.id == person_id)
            .values(display_name_key=name.casefold() if name else None)
        )


def downgrade() -> None:
    with op.batch_alter_table("person", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_person_display_name_key"))
        batch_op.drop_column("display_name_key")

    with op.batch_alter_table("exercise", schema=None) as batch_op:
        batch_op.drop_column("panels_revision")

    with op.batch_alter_table("panel_member", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_panel_member_roster_entry_id"))
        batch_op.drop_index(batch_op.f("ix_panel_member_panel_id"))

    op.drop_table("panel_member")
    with op.batch_alter_table("roster_entry", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_roster_entry_exercise_id"))

    op.drop_table("roster_entry")
    with op.batch_alter_table("panel", schema=None) as batch_op:
        batch_op.drop_index(
            "uq_panel_live_name",
            sqlite_where=sa.text("retired_at IS NULL"),
            postgresql_where=sa.text("retired_at IS NULL"),
        )
        batch_op.drop_index(batch_op.f("ix_panel_exercise_id"))

    op.drop_table("panel")
