"""AD2C: the timeline, its gates and outcomes, and Candidates

Revision ID: ad2c1process
Revises: ad2b1exercisesettings
Create Date: 2026-11-22

An exercise's timeline in the database (segment AD2C,
`applydesk/guide/archive/segment_AD2C_process.md`): `stage` (with the form's
window and state on the stage holding it), `gate` and its `gate_field`,
`gate_result` and `gate_source` rows, `outcome` and its `outcome_value`,
`outcome_weight` and `outcome_release` rows, each gate
and outcome keyed per exercise (ruling 37); `candidate`, the Candidates
list (ruling 77); and `exercise.process_revision`, 0 until Process is
first saved. New tables only: no existing row changes.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ad2c1process"
down_revision: str | Sequence[str] | None = "ad2b1exercisesettings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidate",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("exercise_id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("via", sa.String(length=8), nullable=False),
        sa.Column("added_by_id", sa.Integer(), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["added_by_id"], ["person.id"], name="fk_candidate_added_by"),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercise.id"], name="fk_candidate_exercise"),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"], name="fk_candidate_person"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exercise_id", "person_id", name="uq_candidate_pair"),
    )
    with op.batch_alter_table("candidate", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_candidate_exercise_id"), ["exercise_id"], unique=False)

    op.create_table(
        "stage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("exercise_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=16), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("shown", sa.Boolean(), nullable=False),
        sa.Column("holds_form", sa.Boolean(), nullable=False),
        sa.Column("holds_candidates", sa.Boolean(), nullable=False),
        sa.Column("form_opens_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("form_closes_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("form_state", sa.String(length=8), nullable=True),
        sa.Column("form_opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("form_closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercise.id"], name="fk_stage_exercise"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exercise_id", "key", name="uq_stage_key"),
    )
    with op.batch_alter_table("stage", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_stage_exercise_id"), ["exercise_id"], unique=False)

    op.create_table(
        "gate",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("exercise_id", sa.Integer(), nullable=False),
        sa.Column("stage_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=16), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("via", sa.String(length=16), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("confidential", sa.Boolean(), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("total_min", sa.Integer(), nullable=True),
        sa.Column("total_max", sa.Integer(), nullable=True),
        sa.Column("review_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rule", sa.JSON(), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercise.id"], name="fk_gate_exercise"),
        sa.ForeignKeyConstraint(["stage_id"], ["stage.id"], name="fk_gate_stage"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exercise_id", "key", name="uq_gate_key"),
    )
    with op.batch_alter_table("gate", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_gate_exercise_id"), ["exercise_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_gate_stage_id"), ["stage_id"], unique=False)

    op.create_table(
        "outcome",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("exercise_id", sa.Integer(), nullable=False),
        sa.Column("stage_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=16), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rule", sa.JSON(), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercise.id"], name="fk_outcome_exercise"),
        sa.ForeignKeyConstraint(["stage_id"], ["stage.id"], name="fk_outcome_stage"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exercise_id", "key", name="uq_outcome_key"),
    )
    with op.batch_alter_table("outcome", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_outcome_exercise_id"), ["exercise_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_outcome_stage_id"), ["stage_id"], unique=False)

    op.create_table(
        "gate_field",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("gate_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=16), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("min", sa.String(length=32), nullable=False),
        sa.Column("max", sa.String(length=32), nullable=False),
        sa.Column("step", sa.String(length=32), nullable=False),
        sa.Column("options", sa.Text(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("help", sa.Text(), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["gate_id"], ["gate.id"], name="fk_gate_field_gate"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gate_id", "key", name="uq_gate_field_key"),
    )
    with op.batch_alter_table("gate_field", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_gate_field_gate_id"), ["gate_id"], unique=False)

    op.create_table(
        "gate_source",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("gate_id", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("ref", sa.String(length=200), nullable=False),
        sa.Column("min", sa.Integer(), nullable=False),
        sa.Column("max", sa.Integer(), nullable=False),
        sa.Column("all_members", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["gate_id"], ["gate.id"], name="fk_gate_source_gate"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("gate_source", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_gate_source_gate_id"), ["gate_id"], unique=False)

    op.create_table(
        "outcome_release",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("outcome_id", sa.Integer(), nullable=False),
        sa.Column("audience", sa.String(length=16), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_by_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["outcome_id"], ["outcome.id"], name="fk_outcome_release_outcome"),
        sa.ForeignKeyConstraint(["released_by_id"], ["person.id"], name="fk_outcome_release_by"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("outcome_id", "audience", name="uq_outcome_release_pair"),
    )
    with op.batch_alter_table("outcome_release", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_outcome_release_outcome_id"), ["outcome_id"], unique=False
        )

    op.create_table(
        "outcome_value",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("outcome_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=16), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("advances", sa.Boolean(), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["outcome_id"], ["outcome.id"], name="fk_outcome_value_outcome"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("outcome_id", "key", name="uq_outcome_value_key"),
    )
    with op.batch_alter_table("outcome_value", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_outcome_value_outcome_id"), ["outcome_id"], unique=False
        )

    op.create_table(
        "outcome_weight",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("outcome_id", sa.Integer(), nullable=False),
        sa.Column("gate_id", sa.Integer(), nullable=False),
        sa.Column("result_key", sa.String(length=16), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["gate_id"], ["gate.id"], name="fk_outcome_weight_gate"),
        sa.ForeignKeyConstraint(["outcome_id"], ["outcome.id"], name="fk_outcome_weight_outcome"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("outcome_id", "gate_id", "result_key", name="uq_outcome_weight_pair"),
    )
    with op.batch_alter_table("outcome_weight", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_outcome_weight_outcome_id"), ["outcome_id"], unique=False
        )

    op.create_table(
        "gate_result",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("gate_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=16), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("field_id", sa.Integer(), nullable=True),
        sa.Column("derive", sa.String(length=16), nullable=False),
        sa.Column("value", sa.String(length=200), nullable=False),
        sa.Column("at_least", sa.Integer(), nullable=False),
        sa.Column("ignore_zero", sa.Boolean(), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["field_id"], ["gate_field.id"], name="fk_gate_result_field"),
        sa.ForeignKeyConstraint(["gate_id"], ["gate.id"], name="fk_gate_result_gate"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gate_id", "key", name="uq_gate_result_key"),
    )
    with op.batch_alter_table("gate_result", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_gate_result_gate_id"), ["gate_id"], unique=False)

    with op.batch_alter_table("exercise", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("process_revision", sa.Integer(), server_default="0", nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("exercise", schema=None) as batch_op:
        batch_op.drop_column("process_revision")

    with op.batch_alter_table("gate_result", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_gate_result_gate_id"))

    op.drop_table("gate_result")
    with op.batch_alter_table("outcome_weight", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_outcome_weight_outcome_id"))

    op.drop_table("outcome_weight")
    with op.batch_alter_table("outcome_value", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_outcome_value_outcome_id"))

    op.drop_table("outcome_value")
    with op.batch_alter_table("outcome_release", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_outcome_release_outcome_id"))

    op.drop_table("outcome_release")
    with op.batch_alter_table("gate_source", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_gate_source_gate_id"))

    op.drop_table("gate_source")
    with op.batch_alter_table("gate_field", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_gate_field_gate_id"))

    op.drop_table("gate_field")
    with op.batch_alter_table("outcome", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_outcome_stage_id"))
        batch_op.drop_index(batch_op.f("ix_outcome_exercise_id"))

    op.drop_table("outcome")
    with op.batch_alter_table("gate", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_gate_stage_id"))
        batch_op.drop_index(batch_op.f("ix_gate_exercise_id"))

    op.drop_table("gate")
    with op.batch_alter_table("stage", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_stage_exercise_id"))

    op.drop_table("stage")
    with op.batch_alter_table("candidate", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_candidate_exercise_id"))

    op.drop_table("candidate")
