"""U4: the photo proof of concept's table

Revision ID: u4a1photopoc01
Revises:
Create Date: 2026-11-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "u4a1photopoc01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "photo_poc_photos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(16), nullable=False),
        sa.Column("uploaded_by", sa.String(320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_type", sa.String(32), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.UniqueConstraint("public_id", name="uq_photo_poc_photos_public_id"),
    )


def downgrade() -> None:
    op.drop_table("photo_poc_photos")
