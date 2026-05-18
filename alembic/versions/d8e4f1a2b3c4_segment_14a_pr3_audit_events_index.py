"""segment 14a pr3: audit_events (session_id, created_at) index

Adds a composite B-tree index on ``audit_events (session_id,
created_at)``. The §5.5 index review walked every named query
path — sessions-for-operator, reviewers / reviewees by session,
assignments by reviewer / session, responses by assignment,
monitoring counts, export queries, audit events by session /
date — and found all of them already covered by an existing FK
or unique-constraint index *except* the audit-log paths. This is
the one genuine gap.

The index serves the per-session audit-log queries: the CSV
exporter walks ``WHERE session_id = ? ORDER BY created_at, id``,
and the in-app viewer's optional date-range filter layers
``created_at`` range predicates on top of the same ``session_id``
filter. The ``session_id`` prefix also covers the unfiltered
viewer query (which then keyset-paginates on the ``id`` primary
key).

Plain cross-dialect B-tree — no Postgres-specific index type;
those wait on the deferred type migrations per
``guide/deferred_infra.md``.

Revision ID: d8e4f1a2b3c4
Revises: c7d1e9f3a4b2
Create Date: 2026-05-18

"""
from typing import Sequence, Union

from alembic import op


revision: str = "d8e4f1a2b3c4"
down_revision: Union[str, Sequence[str], None] = "c7d1e9f3a4b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_audit_events_session_created",
        "audit_events",
        ["session_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_audit_events_session_created", table_name="audit_events"
    )
