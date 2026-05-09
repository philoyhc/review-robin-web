# Segment 13D — DB prep for 15A / 15B (and 13B / 13C ride-along)

**Status:** Plan (2026-05-09).
**Sizing:** 1 small segment, **3-4 PRs** (one per migration).
**Depends on:** none.
**Unblocks:** 15A, 15B, and (if the ride-along columns land here)
13B PR 1 and 13C PR 1 become pure render-path work.

---

## Goal

Pre-position every additive, nullable, no-backfill schema change
that downstream feature segments need, so that those feature
segments are pure service / UI / template work. Net effect: a
shorter, safer feature segment per downstream plan, plus one
schema-only segment with predictable test surface.

The migrations land **inert** — every column is nullable, every
new table starts empty, and no service code reads or writes the
new shape until its owning feature segment lights it up. This
mirrors how Segment 11C Part 2 pre-positioned the seven `email_outbox`
audit-log columns ahead of Segment 14-1 Part A.

---

## Scope sweep (verified 2026-05-09)

Scanned every non-archive plan under `guide/segment_*.md`. Schema
needs that show up:

| Source | Change | Why ride along here |
|---|---|---|
| **15A** — Pervasive friendly labels | New table `session_field_labels` | Required by 15A. Pure additive; defaults read from code. |
| **15B** — Per-instrument assignments | `instruments.rule_set_id` nullable FK | Required by 15B (per-instrument RuleSet selection). One column add. |
| **13B** — Sort by reviewee | `instruments.sort_display_fields` JSON | 13B's own PR 1 is a schema-only PR ("infrastructure-only: schema + read path"). Lifting it here merges it with the rest of the schema work. |
| **13C** — Enhanced instrument | `instruments.group_kind` String(32) NULL | 13C's own PR 1 is a schema + render-path PR. The column-add half lifts here cleanly; the render adapter stays in 13C. |
| 12A — Export and import | none | Pure CSV read/write; no new schema. |
| 12B — Audit retention | none | Operates on existing `audit_events` + `responses`. |
| 14-1 — Email send activation | none | All schema already shipped in 11C Part 2 (Migration `c4f6a8b0d2e5`). |
| 14 — Production hardening | type migrations only | JSON → JSONB, String(36) → native UUID. Postgres-specific, not "additive nullable" — stays in 14. |
| 15B Slice 7 — `AssignmentContext1-3` | Three nullable columns on `assignments` | **Out of 13D scope by design.** AssignmentContext is logic-bearing (e.g. "this assignment is for Award X category"), not display-only like PairContext, and most use cases are derivable from existing reviewer + reviewee tags evaluated through the rule engine. If it ever lands, the schema + rule-engine integration + CSV column + UI plumbing all live together in `segment_15B_per_instrument_assignments.md` Slice 7 — not as a pre-positioned column here. |

---

## PRs

### PR 1 — `session_field_labels` table (15A prep)

**Why.** 15A's resolver consults this table to render operator-
overridden labels for tags + pair-context. Detail in
`segment_15A_friendly_labels.md` Slice 1.

**Change.**

```python
class SessionFieldLabel(Base):
    __tablename__ = "session_field_labels"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "source_type", "source_field",
            name="uq_session_field_label",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_field: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
```

**Inert.** No service module reads it; the existing
`_DEFAULT_DISPLAY_LABELS` dict in
`app/services/instruments/_display_fields.py` keeps its current
behaviour. 15A Slice 1 introduces the resolver that consults the
table.

**Tests.** `tests/integration/test_session_field_label_schema.py`
— round-trip insert / unique-constraint enforcement / cascade-on-
session-delete on both SQLite and the `ci-postgres` job.

### PR 2 — `instruments.rule_set_id` nullable FK (15B prep)

**Why.** 15B's per-instrument RuleSet selection. Each instrument
points at the RuleSet currently in effect for it; RuleSets remain
authored and owned at the user-library level (`scope ∈
{seed, personal}`, `owner_user_id`) — they are *applied* per
instrument via this pointer. Detail in
`segment_15B_per_instrument_assignments.md` Slice 2.

**FK direction rationale (locked 2026-05-09).** This column lives
on `instruments`, not `rule_sets`. RuleSets are operator-authored
content visible across all of an operator's sessions; instruments
are session-scoped containers that *select* a RuleSet to apply.
Putting the pointer on `instruments` means:

- Deleting an instrument disposes of its pointer cleanly without
  touching the RuleSet itself (matches the precedent set by
  `assignments` / `instrument_display_fields` /
  `instrument_response_fields` cascading off the instrument row,
  but **without** that cascade reaching back to the user-authored
  RuleSet).
- Deleting a RuleSet (operator removes from their library): the
  `ON DELETE SET NULL` on this FK clears the pointer on every
  instrument that referenced it. The instrument falls back to "no
  rule selected" until the operator picks one — never silently
  inherits a different rule.
- Resetting an instrument's assignments (a 15B UX action) is just
  a separate `UPDATE … SET rule_set_id = NULL` on the instrument
  row. No DELETE cascade involved at all; the RuleSet is never
  at risk.

**Change.**

```python
# app/db/models/instrument.py
rule_set_id: Mapped[int | None] = mapped_column(
    ForeignKey("rule_sets.id", ondelete="SET NULL"),
    index=True, nullable=True,
)
```

Plus an Alembic `op.add_column` migration. NULL = "no rule
currently selected for this instrument" (initial state for every
existing instrument); non-NULL = "this is the RuleSet that
generated the current assignments for this instrument" (15B Slice
2 onwards).

**Inert.** No service code reads or writes the new column;
`app/services/rules/library.py` and
`app/services/rules/engine.py` continue passing `rule_set_id`
through the URL / form parameters as today, and
`assignments.replace_assignments` continues to fan one set of
generated pairs across every instrument. 15B Slice 2 starts
persisting the choice into this column.

**Tests.** `tests/integration/test_instrument_rule_set_id_schema.py`
— insert with NULL (initial state) + non-NULL (selected state);
`SET NULL` behaviour when the referenced `rule_sets` row is
deleted; `instrument_id` cascade deletes the pointer column with
the row, RuleSet untouched.

### PR 3 — `instruments.sort_display_fields` JSON column (13B ride-along)

**Why.** 13B PR 1 already specs this as a schema-only PR
("infrastructure-only … the column sits dormant, it's a `NULL`
column without any operator able to break it"). Lifting it here
merges it with the other schema-only work and lets 13B PR 1 collapse
into 13B's render-path slice.

**Change.**

```python
# app/db/models/instrument.py
sort_display_fields: Mapped[list[dict] | None] = mapped_column(JSON)
```

Plus the Alembic `op.add_column`.

**Inert.** No service code reads it. The reviewer-surface render
keeps its current sort policy (instrument order, then reviewee
order). 13B's render-path PR (was PR 2) becomes "PR 1" of the
shrunk segment.

**Tests.** `test_instrument_sort_display_fields_schema.py` —
round-trip a small `[{"source_type": "...", "source_field": "...",
"direction": "asc"}]` list; default NULL.

**Optional.** If we want to keep 13B as a self-contained ladder,
skip this PR and let 13B own its own schema. Recommend folding —
the schema move is genuinely uncoupled from the UI work.

### PR 4 — `instruments.group_kind` column (13C ride-along)

**Why.** 13C PR 1 specs the `group_kind String(32) | NULL` column
+ render-path edits. The column add is independent of the render
path; lifting it here makes 13C's PR 1 pure render work.

**Change.**

```python
# app/db/models/instrument.py
group_kind: Mapped[str | None] = mapped_column(String(32))
```

Plus the Alembic `op.add_column`.

**Inert.** No service code reads it; reviewer-surface render
behaviour unchanged. 13C PR 1 reads it via the new render adapter.

**Tests.** `test_instrument_group_kind_schema.py` — round-trip
with NULL default; round-trip with `"by_team"` / `"by_role"` /
whatever value-set 13C settles on.

**Optional.** Same call as PR 3 — keep 13C self-contained, or
fold the schema work here. Recommend fold.

---

## Sequencing

PRs 1 → 4 are independent of each other. Land in any order; even
land in parallel if multiple sessions are open. PR 1 + PR 2 are
non-optional (15A and 15B genuinely depend on them); PR 3 + PR 4
are recommended fold-ins but the corresponding feature segments
can carry their own schema if preferred — flag the decision before
PR 3 / PR 4 open.

---

## Risks + open questions

- **All migrations are additive + nullable + no backfill** — same
  shape as the 11C Part 2 outbox column scaffolding. The
  `ci-postgres` job round-trips every migration on a real Postgres
  16 service container; SQLite parity is exercised by the local
  pytest suite.
- **Inert is enforceable.** `grep` audits at PR-close time:
  `grep -rn "session_field_labels\|sort_display_fields\|group_kind\|rule_set_id" app/services/ app/web/` should return zero **new** hits in the service layer (the existing `rule_set_id` URL/form param wiring stays untouched). Schema-only test files are fine.
- **13B / 13C call to fold or not** — see "Optional" notes on PRs
  3 / 4. If the feature plan owners want to keep the slice self-
  contained, drop those PRs from this segment and 13D becomes a
  2-PR pure-prep segment.

---

## Critical files

- New per PR:
  - PR 1: `app/db/models/session_field_label.py` + Alembic migration
  - PR 2: Alembic migration; one column add to `app/db/models/instrument.py`
  - PR 3: Alembic migration; one column add to `app/db/models/instrument.py`
  - PR 4: Alembic migration; one column add to `app/db/models/instrument.py`
- Touched: `app/db/models/__init__.py` (re-export the new
  `SessionFieldLabel` class).

---

## Verification

- `pytest -q` green on SQLite + `ci-postgres` after each PR.
- `ruff check .` green.
- `alembic upgrade head` clean on both dialects (the `ci-postgres`
  job already does this — no extra wiring needed).
- `alembic downgrade -1` reversible per migration (manual smoke
  during PR review).
- Schema-only tests per PR (above).
- Inert audit: zero `app/services/` or `app/web/` references to
  the new columns / table after each PR's diff lands.
