"""self-review consolidation PR 1 — Assignment.is_self_review

Adds a boolean ``is_self_review`` column to ``assignments``,
backfilled per-session via the canonical whole-group rule
documented in ``spec/assignments.md`` § *Self-review policy*.
The column is the new single source of truth for "is this
assignment row a self-review"; subsequent PRs in the
``guide/self_review_consolidate.md`` slice wire the write +
read sites.

Backfill rule (self-contained — no imports from ``app.services``):

* **Individual-scoped instrument** (``group_kind IS NULL``): a
  row is self-review iff its reviewer's email matches the
  reviewee's identifier (case-insensitive, and only if the
  reviewee identifier contains ``@``).
* **Group-scoped instrument**: the whole-group rule — a group
  is a self-review group iff its reviewer is themselves a
  member of it (the ``(R, R)`` pair exists in the group's
  member-assignments). When the rule fires, *every* assignment
  in that group flips to ``TRUE``.

The migration reads the minimum columns it needs directly via
``op.get_bind()`` so the rule stays pinned to the data the
column captures at write-time, even if the service layer
later moves around.

Revision ID: b4e8c2a9d1f6
Revises: 683e99cca6b7
Create Date: 2026-05-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b4e8c2a9d1f6"
down_revision: Union[str, Sequence[str], None] = "683e99cca6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Group-kind encoding mirrors
# ``app.services.instruments._instrument_crud`` (Segment 13C).
# Replicated here so the migration is self-contained.
_GROUP_KIND_SENTINEL = "both"
_GROUP_BOUNDARY_SOURCE_BY_CODE: dict[str, tuple[str, str]] = {
    "r1": ("reviewee", "tag_1"),
    "r2": ("reviewee", "tag_2"),
    "r3": ("reviewee", "tag_3"),
    "p1": ("pair_context", "1"),
    "p2": ("pair_context", "2"),
    "p3": ("pair_context", "3"),
}


def _decode_group_kind(group_kind: str | None) -> list[tuple[str, str]]:
    """Decode ``group_kind`` into ``(source_type, source_field)`` pairs.
    ``None`` → not a group instrument; ``"both"`` → group instrument
    with no boundary tag (single global group)."""
    if group_kind is None:
        return []  # Not a group instrument.
    pairs: list[tuple[str, str]] = []
    for code in group_kind.split(","):
        code = code.strip()
        if code == _GROUP_KIND_SENTINEL or not code:
            continue
        source = _GROUP_BOUNDARY_SOURCE_BY_CODE.get(code)
        if source is not None:
            pairs.append(source)
    return pairs


def _is_pair_self_review(
    reviewer_email: str, reviewee_identifier: str
) -> bool:
    if "@" not in reviewee_identifier:
        return False
    return reviewer_email.casefold() == reviewee_identifier.casefold()


def _classify_session(bind, session_id: int) -> set[int]:
    """Return the set of ``assignment.id`` rows in this session that
    are self-reviews per the canonical rule."""
    rows = bind.execute(
        sa.text(
            """
            SELECT
                a.id            AS assignment_id,
                a.reviewer_id   AS reviewer_id,
                a.reviewee_id   AS reviewee_id,
                a.instrument_id AS instrument_id,
                r.email         AS reviewer_email,
                ree.email_or_identifier AS reviewee_identifier,
                ree.tag_1       AS reviewee_tag_1,
                ree.tag_2       AS reviewee_tag_2,
                ree.tag_3       AS reviewee_tag_3,
                i.group_kind    AS group_kind
            FROM assignments a
            JOIN reviewers   r   ON r.id   = a.reviewer_id
            JOIN reviewees   ree ON ree.id = a.reviewee_id
            JOIN instruments i   ON i.id   = a.instrument_id
            WHERE a.session_id = :sid
            """
        ),
        {"sid": session_id},
    ).mappings().all()

    if not rows:
        return set()

    # Active relationships keyed by (reviewer_id, reviewee_id) — only
    # consulted when at least one group-scoped instrument with a
    # pair-context boundary exists in this session.
    needs_relationships = any(
        any(src == "pair_context" for src, _ in _decode_group_kind(row["group_kind"]))
        for row in rows
        if row["group_kind"] is not None
    )
    relationship_tags: dict[tuple[int, int], tuple[str | None, str | None, str | None]] = {}
    if needs_relationships:
        rel_rows = bind.execute(
            sa.text(
                """
                SELECT reviewer_id, reviewee_id, tag_1, tag_2, tag_3
                FROM relationships
                WHERE session_id = :sid AND status = 'active'
                """
            ),
            {"sid": session_id},
        ).mappings().all()
        for r in rel_rows:
            relationship_tags[(r["reviewer_id"], r["reviewee_id"])] = (
                r["tag_1"],
                r["tag_2"],
                r["tag_3"],
            )

    # Group key for each (reviewer, reviewee) on a group-scoped
    # instrument; absent for individual-scoped instruments.
    group_key_by_assignment: dict[int, tuple[str, ...]] = {}
    for row in rows:
        boundary = _decode_group_kind(row["group_kind"])
        if row["group_kind"] is None:
            continue  # Individual instrument — no key.
        key: list[str] = []
        for source_type, source_field in boundary:
            if source_type == "reviewee":
                raw = row[f"reviewee_{source_field}"]
            else:  # pair_context
                idx = int(source_field) - 1  # "1"|"2"|"3" → 0|1|2
                rel = relationship_tags.get(
                    (row["reviewer_id"], row["reviewee_id"])
                )
                raw = rel[idx] if rel is not None else None
            key.append((raw or "").strip())
        group_key_by_assignment[row["assignment_id"]] = tuple(key)

    # First pass: identify (instrument, reviewer) → group-key for
    # groups where R is themselves a member.
    self_group_key: dict[tuple[int, int], tuple[str, ...]] = {}
    for row in rows:
        aid = row["assignment_id"]
        if aid in group_key_by_assignment and _is_pair_self_review(
            row["reviewer_email"], row["reviewee_identifier"]
        ):
            self_group_key[(row["instrument_id"], row["reviewer_id"])] = (
                group_key_by_assignment[aid]
            )

    # Second pass: flag self-review rows per the rule.
    flagged: set[int] = set()
    for row in rows:
        aid = row["assignment_id"]
        group_key = group_key_by_assignment.get(aid)
        if group_key is None:
            # Individual instrument: per-row pair test.
            if _is_pair_self_review(
                row["reviewer_email"], row["reviewee_identifier"]
            ):
                flagged.add(aid)
        else:
            # Group instrument: whole-group rule.
            if (
                self_group_key.get(
                    (row["instrument_id"], row["reviewer_id"])
                )
                == group_key
            ):
                flagged.add(aid)
    return flagged


def upgrade() -> None:
    # Add the column; ``server_default=false`` populates every
    # existing row with ``FALSE``. Backfill below flips
    # self-review rows to ``TRUE``.
    with op.batch_alter_table("assignments") as batch:
        batch.add_column(
            sa.Column(
                "is_self_review",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    bind = op.get_bind()
    session_ids = [
        row[0]
        for row in bind.execute(
            sa.text("SELECT DISTINCT session_id FROM assignments")
        ).fetchall()
    ]
    for session_id in session_ids:
        flagged = _classify_session(bind, session_id)
        if not flagged:
            continue
        # Update in batches so the IN clause doesn't get unbounded.
        ids = sorted(flagged)
        batch_size = 500
        for i in range(0, len(ids), batch_size):
            chunk = ids[i : i + batch_size]
            bind.execute(
                sa.text(
                    "UPDATE assignments SET is_self_review = :v "
                    "WHERE id IN :ids"
                ).bindparams(sa.bindparam("ids", expanding=True)),
                {"v": True, "ids": chunk},
            )


def downgrade() -> None:
    with op.batch_alter_table("assignments") as batch:
        batch.drop_column("is_self_review")
