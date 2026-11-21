"""AD2A: people, exercises, operators and audit

Revision ID: ad2a1foundations
Revises:
Create Date: 2026-11-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ad2a1foundations"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exercise",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("public_id", name="uq_exercise_public_id"),
    )
    op.create_table(
        "person",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=True),
        sa.Column("object_id", sa.String(64), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("email_key", sa.String(320), nullable=True),
        sa.Column("upn", sa.String(320), nullable=True),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("bound_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        # sa.false(), not text("0"): Postgres refuses an integer default on a
        # boolean column (CLAUDE.md, "Migration portability matters").
        sa.Column("may_operate", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("admitted_by_id", sa.Integer(), nullable=True),
        sa.Column("admitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["admitted_by_id"], ["person.id"], name="fk_person_admitted_by"),
        sa.UniqueConstraint("tenant_id", "object_id", name="uq_person_tenant_object"),
    )
    op.create_index("ix_person_email_key", "person", ["email_key"])
    op.create_table(
        "audit_event",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("exercise_id", sa.Integer(), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["person.id"], name="fk_audit_event_actor"),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercise.id"], name="fk_audit_event_exercise"),
    )
    op.create_index("ix_audit_event_event_type", "audit_event", ["event_type"])
    op.create_index("ix_audit_event_exercise_id", "audit_event", ["exercise_id"])
    op.create_table(
        "exercise_operator",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exercise_id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("is_owner", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("added_by_id", sa.Integer(), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["exercise_id"], ["exercise.id"], name="fk_exercise_operator_exercise"
        ),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"], name="fk_exercise_operator_person"),
        sa.ForeignKeyConstraint(
            ["added_by_id"], ["person.id"], name="fk_exercise_operator_added_by"
        ),
        sa.UniqueConstraint("exercise_id", "person_id", name="uq_exercise_operator_pair"),
    )


def downgrade() -> None:
    # Children first, so no foreign key is left pointing at a dropped table.
    op.drop_table("exercise_operator")
    op.drop_index("ix_audit_event_exercise_id", table_name="audit_event")
    op.drop_index("ix_audit_event_event_type", table_name="audit_event")
    op.drop_table("audit_event")
    op.drop_index("ix_person_email_key", table_name="person")
    op.drop_table("person")
    op.drop_table("exercise")
