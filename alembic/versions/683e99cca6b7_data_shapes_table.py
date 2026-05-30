"""data_shapes: per-session library for operator-saved Data shaper shapes

New table backing the wiring slice of the Data shaper card on the
Extract data Operations tab. Each row is one saved shape; the
unique constraint on ``(session_id, name)`` prevents the operator
from saving two shapes with the same name on a session.

FK semantics CASCADE on every side
(``sessions`` / ``instruments`` / ``instrument_response_fields``)
so deleting any of the upstream rows drops the shape — the
operator re-authors against the new instrument set rather than
ending up with a silently-widened scope. ``created_by_user_id``
uses ``SET NULL`` because the shape itself should outlive a
deleted user.

See ``spec/extract_data.md`` "Wiring decisions (resolved
2026-05-29)" for the full contract.

Revision ID: 683e99cca6b7
Revises: e5c1a3b9d472
Create Date: 2026-05-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "683e99cca6b7"
down_revision: Union[str, Sequence[str], None] = "e5c1a3b9d472"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "data_shapes",
        sa.Column(
            "id", sa.Integer(), primary_key=True, autoincrement=True
        ),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("axis", sa.String(length=16), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=True),
        sa.Column("response_field_id", sa.Integer(), nullable=True),
        sa.Column("column_chip_slots", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["session_id"], ["sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instruments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["response_field_id"],
            ["instrument_response_fields.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint(
            "session_id", "name", name="uq_data_shape_session_name"
        ),
    )
    op.create_index(
        "ix_data_shapes_session_id", "data_shapes", ["session_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_data_shapes_session_id", table_name="data_shapes")
    op.drop_table("data_shapes")
