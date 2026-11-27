"""AD2K: Populate Dossiers' entries

Revision ID: ad2k1entries
Revises: ad2f1dossiers
Create Date: 2026-11-26

Ruling 83 (segment AD2K, `applydesk/guide/archive/segment_AD2K_populate_dossiers.md`):
each Candidates row is an entry, one dossier each, so a person may hold
several (``uq_candidate_pair`` dropped, an optional ``title``), up to the
exercise's ``dossiers_per_person``; and a dossier populated first may later
gain an application, so its source is a candidate or an application, or both.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ad2k1entries"
down_revision: str | Sequence[str] | None = "ad2f1dossiers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ONE = "(application_id IS NULL) <> (candidate_id IS NULL)"
_ANY = "application_id IS NOT NULL OR candidate_id IS NOT NULL"


def upgrade() -> None:
    with op.batch_alter_table("candidate", schema=None) as batch_op:
        batch_op.drop_constraint("uq_candidate_pair", type_="unique")
        batch_op.add_column(
            sa.Column("title", sa.String(length=300), nullable=False, server_default="")
        )
        batch_op.create_index("ix_candidate_person", ["exercise_id", "person_id"], unique=False)
    with op.batch_alter_table("exercise", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("dossiers_per_person", sa.Integer(), nullable=False, server_default="1")
        )
    with op.batch_alter_table("dossier", schema=None) as batch_op:
        batch_op.drop_constraint("ck_dossier_one_source", type_="check")
        batch_op.create_check_constraint("ck_dossier_a_source", _ANY)


def downgrade() -> None:
    # A dossier with both sources, or a person listed twice, cannot go back:
    # the older shape refuses them, as it should.
    with op.batch_alter_table("dossier", schema=None) as batch_op:
        batch_op.drop_constraint("ck_dossier_a_source", type_="check")
        batch_op.create_check_constraint("ck_dossier_one_source", _ONE)
    with op.batch_alter_table("exercise", schema=None) as batch_op:
        batch_op.drop_column("dossiers_per_person")
    with op.batch_alter_table("candidate", schema=None) as batch_op:
        batch_op.drop_index("ix_candidate_person")
        batch_op.drop_column("title")
        batch_op.create_unique_constraint("uq_candidate_pair", ["exercise_id", "person_id"])
