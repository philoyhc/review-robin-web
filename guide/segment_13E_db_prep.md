# Segment 13E — DB prep for the 12C / 15D block

**Status:** Planning. Sized 2026-05-10. **First in the
locked sequence 13E → 12C → 15D → 12A-3** (the next
big-picture block of operator-facing work). Mirrors the
13D pattern: every migration lands inert, additive, and
no-backfill so the feature segments downstream are pure
service / UI work.

> **Why "13E" rather than "13D-2".** 13D shipped as a
> standalone schema-prep segment. This is a separate
> schema-prep effort that follows the same playbook for
> a different downstream block (12C / 15D vs. 13D's
> 13B / 13C / 15A / 15B / 15C). Treating it as the
> next standalone segment in the 13-family (`13E`) is
> cleaner than overloading the `-N` suffix convention
> which elsewhere means "sub-parts of one umbrella
> effort" (12A-1 / 12A-2; 13A-1 / 13A-2).

**Sizing:** 2 PRs (one per migration).
**Depends on:** 13D (#697 → #702, shipped 2026-05-09).
**Unblocks:** 12C-1's bulk Include toggle (needs
`sessions.self_reviews_active`); 15D's Relationships page
+ generation-path read of pair-context (needs the new
`relationships` table).

## Goal

Pre-position the additive schema 12C and 15D need so each
of those segments is pure service / UI / template work.
Same shape as the original 13D's "every column nullable
or DEFAULT-shaped, every new table starts empty, no
service code reads or writes the new shape until its
owning feature segment lights it up."

The original 13D shipped 7 inert migrations. This wave
adds **2 more** to cover the 12C / 15D block:

| New schema | Owning segment | Shape |
|---|---|---|
| `sessions.self_reviews_active` | 12C-1 | Additive boolean column, `NOT NULL DEFAULT TRUE` (existing rows backfill to TRUE via server default). |
| `relationships` table | 15D | New table, FK to sessions / reviewers / reviewees, with 3 free-form tag slots + status enum. Empty on every deployment running the migration. |

Net effect once both ship: 12C-1 PR 1 stops needing a
schema step; 15D's Relationships service code can be
written immediately when its turn comes without waiting
on a table-creation migration.

## PR sequence (2 PRs, locked 2026-05-10)

PRs are independent and parallel-shippable.

### PR 1 — Add `sessions.self_reviews_active` column

- Migration `op.add_column("sessions", sa.Column(
  "self_reviews_active", sa.Boolean(), nullable=False,
  server_default=sa.true()))`. Existing rows backfill to
  `TRUE` via the server default — no Python-side update
  step.
- SQLAlchemy model: add `self_reviews_active: Mapped[bool]
  = mapped_column(Boolean, default=True, nullable=False,
  server_default=sa.true())` to
  `app/db/models/review_session.py`.
- Lands inert — no service or web code reads or writes
  the column until 12C-1 PR 1 wires the generation
  paths and 12C-1 PR 3 wires the bulk-toggle write.
- Tests:
  - Migration round-trip on SQLite + Postgres
    (autogenerate-clean against the model).
  - Existing-session default verified `TRUE` post-upgrade.
  - Inert audit at PR-close time: `grep -rn
    "self_reviews_active" app/services app/web` returns
    only the model definition.

### PR 2 — Create `relationships` table

- New table:

  ```python
  class Relationship(Base, TimestampMixin):
      __tablename__ = "relationships"
      id: Mapped[int] = mapped_column(primary_key=True)
      session_id: Mapped[int] = mapped_column(
          ForeignKey("sessions.id", ondelete="CASCADE"),
          nullable=False,
      )
      reviewer_id: Mapped[int] = mapped_column(
          ForeignKey("reviewers.id", ondelete="CASCADE"),
          nullable=False,
      )
      reviewee_id: Mapped[int] = mapped_column(
          ForeignKey("reviewees.id", ondelete="CASCADE"),
          nullable=False,
      )
      tag_1: Mapped[str | None] = mapped_column(String(255))
      tag_2: Mapped[str | None] = mapped_column(String(255))
      tag_3: Mapped[str | None] = mapped_column(String(255))
      status: Mapped[str] = mapped_column(
          String(32), default="active", nullable=False,
          server_default="active",
      )

      __table_args__ = (
          UniqueConstraint(
              "session_id", "reviewer_id", "reviewee_id",
              name="uq_relationships_session_reviewer_reviewee",
          ),
      )
  ```

- The friendly name on the chrome / UI is **Relationships**
  (per 15D's locked naming); the schema-level identifier
  is also `relationships` here for symmetry. The
  `pair_context` schema-level identifier (already used
  for display fields' `source_type` enum) stays where it
  is — the new table doesn't replace that vocabulary,
  it complements it. Joins from display fields'
  `pair_context.tag_N` source go through this table
  post-15D instead of through `Assignment.context`.
- Cascade on session / reviewer / reviewee delete keeps
  the table consistent without trigger logic.
- `status` is operator-typed enum (`active` / `inactive`)
  — inactive rows are ignored by 15D's generation
  consumption.
- Lands inert — no service or web code reads or writes
  the table until 15D wires the per-entity importer +
  generation consumption.
- Tests:
  - Migration round-trip on SQLite + Postgres.
  - Empty table on every deployment running the
    migration (verified via `count == 0` post-upgrade).
  - Unique constraint enforced (insert two rows with
    same `(session_id, reviewer_id, reviewee_id)` →
    IntegrityError).
  - Cascade behaviour verified — deleting a reviewer
    removes related `relationships` rows; same for
    reviewee + session.
  - Inert audit at PR-close time: `grep -rn
    "Relationship\|relationships" app/services app/web`
    returns only the model definition.

## Out of scope

- **Drop `Assignment.context` JSON column.** Destructive
  migration; lives in 15D itself (paired with the
  backfill step that lifts `Assignment.context.pair_context_*`
  values into the new `relationships` table).
- **Rule-schema additions.** 15D's `pair_context.tag_N`
  matcher / filter / quota grammar is a JSON-schema change
  in `app/schemas/rules.py`, not a DB schema change. Lives
  in 15D.
- **Per-entity importer / Settings page surface.** Lives
  in 15D (Relationships page) and 12A-3 (export /
  import).
- **Backfill.** No-backfill is the 13D pattern; the
  table starts empty on every deployment. 15D handles
  the one-time backfill from `Assignment.context.pair_context_*`
  in its own migration.

## Test impact

Mirrors the 13D test surface:

- Per-PR migration round-trip (SQLite + Postgres).
- Per-PR existing-state preservation (no rows mutated
  outside the new column / table).
- Per-PR inert audit at PR-close time.
- One extra test in `tests/unit/test_models.py` (or the
  per-model file) per new model that exercises the
  shape: the model imports, instantiates, and round-trips
  through a flushed transaction.

## Doc impact

- `docs/status.md` gains one timeline entry per PR.
- `guide/todo_master.md`:
  - Move Segment 13E from **Upcoming** to **Done** under
    "Segment 13" once both PRs land.
  - The Upcoming entry was added by the planning round
    that locked the 13E → 12C → 15D → 12A-3 sequence
    on 2026-05-10.
- `spec/architecture.md` — extend the "Database tables"
  enumeration to cover `relationships`.
- `spec/settings_inventory.md` — extend §10 (CSV
  coverage) once 12A-3 ships the per-entity export +
  import; not in 13E's scope to update yet.

## Related context

- **Segment 13D** (shipped 2026-05-09;
  `guide/archive/segment_13D_db_prep.md`). 7 PRs, every
  migration inert. This 13E doc mirrors the same
  schema-prep pattern; differences are scope (only 2
  PRs here) + downstream consumers (12C / 15D vs.
  13D's 13B / 13C / 15A / 15B / 15C).
- **Segment 12C — Self-review revamp**
  (`guide/segment_12C_self-review_revamp.md`). 12C-1 PR 1
  consumes `sessions.self_reviews_active` (this segment's
  PR 1) for generation-path wiring; 12C-1 PR 3 writes it
  via the bulk Include toggle.
- **Segment 15D — Assignments revamp**
  (`guide/segment_15D_assignments_revamp.md`). 15D's
  Relationships page + per-entity importer + generation
  consumption all read / write the `relationships`
  table (this segment's PR 2).
- **Segment 12A-3 — Export / import updates for
  15D** (`guide/segment_12A-3_export_import_updates.md`).
  Adds Relationships per-entity export + import once
  the table is wired by 15D.
