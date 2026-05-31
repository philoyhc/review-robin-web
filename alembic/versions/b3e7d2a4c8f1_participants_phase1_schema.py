"""participants phase 1: schema prep

Ships all the inert additive schema the participant-model arc
needs, ahead of the slices that light it up. Per
``guide/participant_model_prep.md`` Phase 1 (✔ rows S1, S2, S7,
S8, S9, S11) and ``guide/participant_model_upgrade.md`` §§3.1,
3.3, 3.8, 3.9, and 6.

What lands:

- ``observers`` — new per-session participant roster (§3.1).
  Single ``tag_1`` column; mirrors the ``reviewers`` shape so
  the importer / Setup-page table / sort primitive extend with
  no new patterns. UNIQUE (session_id, email).
- ``instrument_view_policies`` — new per-instrument visibility
  grant table (§3.3). Up to three rows per instrument — one
  per audience. UNIQUE (instrument_id, audience). Service
  layer enforces the per-audience values and the
  ``observer_tag``-only-for-observer-audience rule (no DB
  CHECK constraint).
- ``sessions.relationships_enabled`` /
  ``sessions.observers_enabled`` (§3.8) — Boolean per-session
  toggles for the two optional Setup tabs. Both default
  ``FALSE``; existing sessions backfill to ``FALSE`` because
  no extant sessions populate Relationships today (operator
  call). The Setup-nav conditional render + lock-on-data
  behaviour wires in Phase 3.
- ``reviewees.results_acknowledged_at`` (§6) — nullable
  timestamp the reviewee surface stamps when the reviewee
  acknowledges their results. NULL until acknowledged. Per §6
  the leaning is "column on reviewees, not a separate
  ``result_acknowledgements`` table".
- ``reviewers.profile_link`` (§3.9) — mirrors
  ``reviewees.profile_link``. Closes the Reviewer / Reviewee
  parity gap §3.7 implicitly assumed. The ~12-file surface
  mirror is a separate Phase 3 slice (W11); this migration
  just adds the column.

Everything ships INERT. No service module reads or writes any
of these columns / tables until its owning slice ships.

The §3.5 audit-event registrations land alongside this
migration in the same PR (``app/services/audit.py``
``EVENT_SCHEMAS``); they are pure code additions and don't
need a migration.

Revision ID: b3e7d2a4c8f1
Revises: d8e4c3a1b5f6
Create Date: 2026-05-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b3e7d2a4c8f1"
down_revision: Union[str, Sequence[str], None] = "d8e4c3a1b5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # New table — observers.
    op.create_table(
        "observers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("tag_1", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id", "email", name="uq_observer_session_email"
        ),
    )
    with op.batch_alter_table("observers", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_observers_email"), ["email"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_observers_session_id"), ["session_id"], unique=False
        )

    # New table — instrument_view_policies.
    op.create_table(
        "instrument_view_policies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("audience", sa.String(length=16), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("granularity", sa.String(length=16), nullable=False),
        sa.Column("identification", sa.String(length=16), nullable=False),
        sa.Column("observer_tag", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "instrument_id",
            "audience",
            name="uq_view_policy_instrument_audience",
        ),
    )
    with op.batch_alter_table(
        "instrument_view_policies", schema=None
    ) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_instrument_view_policies_instrument_id"),
            ["instrument_id"],
            unique=False,
        )

    # New columns — sessions.relationships_enabled,
    # sessions.observers_enabled.
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "relationships_enabled",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "observers_enabled",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
            )
        )

    # New column — reviewees.results_acknowledged_at.
    with op.batch_alter_table("reviewees", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "results_acknowledged_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )

    # New column — reviewers.profile_link.
    with op.batch_alter_table("reviewers", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("profile_link", sa.String(length=2000), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("reviewers", schema=None) as batch_op:
        batch_op.drop_column("profile_link")

    with op.batch_alter_table("reviewees", schema=None) as batch_op:
        batch_op.drop_column("results_acknowledged_at")

    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_column("observers_enabled")
        batch_op.drop_column("relationships_enabled")

    with op.batch_alter_table(
        "instrument_view_policies", schema=None
    ) as batch_op:
        batch_op.drop_index(
            batch_op.f("ix_instrument_view_policies_instrument_id")
        )
    op.drop_table("instrument_view_policies")

    with op.batch_alter_table("observers", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_observers_session_id"))
        batch_op.drop_index(batch_op.f("ix_observers_email"))
    op.drop_table("observers")
