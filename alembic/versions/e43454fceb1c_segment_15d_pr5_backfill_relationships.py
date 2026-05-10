"""segment 15d pr5: backfill assignment.context.pair_context_* into relationships

Pure-DML migration. For every session with non-empty
``Assignment.context.pair_context_1/2/3`` values, lifts each distinct
``(session_id, reviewer_id, reviewee_id)`` pair into a row on the
``relationships`` table (created inert in 13E PR 2). Audit row
``relationships.migrated_from_assignment_context`` fires once per
session with ``counts.scanned`` / ``counts.migrated`` /
``counts.skipped``.

**Idempotent** — pairs that already have a relationships row in
the session are skipped (the unique constraint
``uq_relationships_session_reviewer_reviewee`` is enforced and the
explicit dedupe keeps the audit count honest). Re-running the
migration on a deployment that already ran it is a clean no-op
beyond the per-session zero-count audit emission, which the
migration suppresses when no new rows actually move.

Multiple Assignment fanout rows exist per ``(reviewer, reviewee)``
pair (one per instrument); their ``context`` dicts should be
identical (``replace_assignments`` writes the same value to every
fanout) but legacy data may disagree. Dedupe by pair, keeping
the first non-null value per tag slot.

Uses raw SQL via ``op.get_bind()`` (no app imports) so the
migration replays safely on fresh DBs after PR 6b drops the
``Assignment.context`` column. Production deploys this migration
once before PR 6b; future fresh DBs run against an empty
assignments table → no-op.

Revision ID: e43454fceb1c
Revises: e3ba5737e841
Create Date: 2026-05-10

"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e43454fceb1c"
down_revision: Union[str, Sequence[str], None] = "e3ba5737e841"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Probe for the ``assignments.context`` column. PR 6b drops it
    # later in the chain; on fresh DBs that include PR 6b, this
    # migration runs against a schema that no longer has the
    # column. Treat that as a clean no-op.
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("assignments")}
    if "context" not in columns:
        return

    # Walk the assignments table once. Group by
    # ``(session_id, reviewer_id, reviewee_id)``; capture the first
    # non-null tag slot per pair.
    rows = bind.execute(
        sa.text(
            "SELECT session_id, reviewer_id, reviewee_id, context "
            "FROM assignments "
            "WHERE context IS NOT NULL"
        )
    ).fetchall()

    pair_tags: dict[
        tuple[int, int, int], dict[str, str | None]
    ] = {}
    for row in rows:
        session_id, reviewer_id, reviewee_id, context = row
        ctx = _coerce_context(context)
        tag_1 = _coerce_tag(ctx.get("pair_context_1"))
        tag_2 = _coerce_tag(ctx.get("pair_context_2"))
        tag_3 = _coerce_tag(ctx.get("pair_context_3"))
        if tag_1 is None and tag_2 is None and tag_3 is None:
            continue
        key = (session_id, reviewer_id, reviewee_id)
        existing = pair_tags.get(key)
        if existing is None:
            pair_tags[key] = {
                "tag_1": tag_1,
                "tag_2": tag_2,
                "tag_3": tag_3,
            }
            continue
        for slot, value in (
            ("tag_1", tag_1),
            ("tag_2", tag_2),
            ("tag_3", tag_3),
        ):
            if existing[slot] is None and value is not None:
                existing[slot] = value

    # Skip pairs that already have a relationships row.
    existing_relationships = {
        (s, r, e)
        for s, r, e in bind.execute(
            sa.text(
                "SELECT session_id, reviewer_id, reviewee_id "
                "FROM relationships"
            )
        ).fetchall()
    }

    # Group migrated rows by session for the per-session audit emit.
    by_session: dict[int, dict[str, int]] = {}

    now = datetime.now(timezone.utc)
    for (session_id, reviewer_id, reviewee_id), tags in pair_tags.items():
        counts = by_session.setdefault(
            session_id, {"scanned": 0, "migrated": 0, "skipped": 0}
        )
        counts["scanned"] += 1
        if (session_id, reviewer_id, reviewee_id) in existing_relationships:
            counts["skipped"] += 1
            continue
        bind.execute(
            sa.text(
                "INSERT INTO relationships "
                "(session_id, reviewer_id, reviewee_id, tag_1, tag_2, "
                "tag_3, status, created_at, updated_at) "
                "VALUES (:session_id, :reviewer_id, :reviewee_id, "
                ":tag_1, :tag_2, :tag_3, 'active', :now, :now)"
            ),
            {
                "session_id": session_id,
                "reviewer_id": reviewer_id,
                "reviewee_id": reviewee_id,
                "tag_1": tags["tag_1"],
                "tag_2": tags["tag_2"],
                "tag_3": tags["tag_3"],
                "now": now,
            },
        )
        counts["migrated"] += 1

    # One audit row per session that actually scanned a pair. Sessions
    # with zero pair_context data don't emit, so the migration is
    # silent on the long tail of pre-15D sessions that never used
    # pair_context.
    for session_id, counts in by_session.items():
        # Pull the session row for the canonical detail envelope.
        session_row = bind.execute(
            sa.text(
                "SELECT code, created_by_user_id "
                "FROM sessions WHERE id = :id"
            ),
            {"id": session_id},
        ).fetchone()
        if session_row is None:
            continue
        session_code, created_by_user_id = session_row
        detail = {
            "session_id": session_id,
            "session_code": session_code,
            "counts": counts,
        }
        bind.execute(
            sa.text(
                "INSERT INTO audit_events "
                "(event_type, severity, summary, actor_user_id, "
                "session_id, detail, correlation_id, created_at) "
                "VALUES (:event_type, 'info', :summary, :actor_user_id, "
                ":session_id, :detail, :correlation_id, :now)"
            ),
            {
                "event_type": "relationships.migrated_from_assignment_context",
                "summary": (
                    f"Migrated {counts['migrated']} relationships from "
                    f"assignment context (skipped {counts['skipped']})"
                ),
                "actor_user_id": created_by_user_id,
                "session_id": session_id,
                "detail": json.dumps(detail),
                "correlation_id": str(uuid.uuid4()),
                "now": now,
            },
        )


def downgrade() -> None:
    # No-op: the backfill is one-way data movement and re-running the
    # migration is idempotent. There's no clean inverse — operators
    # can't tell which rows came from the backfill vs. user typing
    # without the assignment_context_* keys, which retire alongside
    # in PR 6b.
    pass


def _coerce_context(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, (str, bytes, bytearray)):
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _coerce_tag(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None
