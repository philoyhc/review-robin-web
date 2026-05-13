# Segment 13D — DB prep for the library / per-session-copy split (and 13B / 13C / 15A ride-along)

**Status:** Complete (2026-05-09). All 7 PRs landed (#696 → #702).
**Sizing:** 1 small segment, **7 PRs** (one per migration).
**Depends on:** none.
**Unblocks:** 15A, 15C (operator RTD/RuleSet libraries), 15B
(per-instrument assignments). 13B PR 1 and 13C PR 1 collapse into
pure render-path slices.

### Final layout

```
operator_rule_sets                       # PR 0: renamed from rule_sets
session_field_labels                     # PR 1: 15A friendly-label resolver
session_rule_sets                        # PR 2: per-session RuleSet copies
operator_response_type_definitions       # PR 3: operator RTD library
response_type_definitions.library_origin_id  # PR 3: provenance pointer
instruments.rule_set_id                  # PR 4: per-instrument selection
instruments.sort_display_fields          # PR 5: 13B sort spec (JSON)
instruments.group_kind                   # PR 6: 13C group flavour
```

Every migration shipped inert — no service or web code reads or
writes the new shape until its owning feature segment lights it
up. Inert audits at PR-close time confirmed zero hits in
`app/services/` + `app/web/` per PR.

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
mirrors how Segment 11C Part 2 pre-positioned the seven
`email_outbox` audit-log columns ahead of Segment 14-1 Part A.

---

## Table-name harmonisation (locked 2026-05-09)

The library / per-session-copy split (15C) is much easier to
reason about when both tiers carry tier-bearing prefixes. **PR 0**
of this segment renames the existing `rule_sets` table to
`operator_rule_sets` so the two libraries can sit side-by-side
under symmetric names.

| Concept | Operator library tier | Per-session copy tier |
|---|---|---|
| **RuleSets** | `operator_rule_sets` *(renamed in PR 0 from `rule_sets`)* | `session_rule_sets` *(new, PR 2)* |
| **RTDs**     | `operator_response_type_definitions` *(new, PR 3)* | `response_type_definitions` *(existing — kept)* |

One tail of asymmetry remains: the RTD per-session table doesn't
carry a `session_` prefix. Renaming it
(`response_type_definitions` → `session_response_type_definitions`)
is a larger sweep — the model class is referenced ~80x across
services, routes, views, tests — and the "per-session is the
default tier" assumption is already correct via context. Defer
the optional follow-on; the post-PR-0 RuleSet side is symmetric,
which is where the cognitive load was concentrated.

The Python class `RuleSet` (and siblings `RuleSetRevision` /
`RuleSetSchema` / `RuleSetOptions` / `RuleSetScope`) keep their
names — only the SQL `__tablename__` flips. ~243 occurrences
across `app/` + `tests/` reference the class identifier; renaming
those is mechanical but adds churn for marginal readability win
(see `Tier 2` analysis in PR conversation #694's follow-up).

---

## Scope sweep (verified 2026-05-09)

Scanned every non-archive plan under `guide/segment_*.md`. Schema
needs that show up:

| Source | Change | Why ride along here |
|---|---|---|
| **15C** — Operator RTD/RuleSet libraries | Rename existing table `rule_sets` → `operator_rule_sets` | Bedrock for the rest. Lets PR 2's `session_rule_sets` and PR 4's `instruments.rule_set_id` reference the harmonised name from birth. |
| **15A** — Pervasive friendly labels | New table `session_field_labels` | Required by 15A. Pure additive; defaults read from code. |
| **15C** — Operator RTD/RuleSet libraries | New table `session_rule_sets` (snapshot, no per-session revisions) | Required by 15C. Per-session copy of a RuleSet — what `instruments.rule_set_id` actually points at. |
| **15C** — Operator RTD/RuleSet libraries | New table `operator_response_type_definitions` | Required by 15C. Operator's library tier for RTDs (mirror of how `rule_sets` is the library tier today). |
| **15B** — Per-instrument assignments | `instruments.rule_set_id` nullable FK → `session_rule_sets` | Required by 15B (per-instrument selection). One column add. |
| **13B** — Sort by reviewee | `instruments.sort_display_fields` JSON | 13B's own PR 1 is a schema-only PR ("infrastructure-only: schema + read path"). Lifting it here merges it with the rest of the schema work. |
| **13C** — Enhanced instrument | `instruments.group_kind` String(32) NULL | 13C's own PR 1 is a schema + render-path PR. The column-add half lifts here cleanly; the render adapter stays in 13C. |
| 12A — Export and import | none | Pure CSV read/write; no new schema. |
| 12B — Audit retention | none | Operates on existing `audit_events` + `responses`. |
| 14-1 — Email send activation | none | All schema already shipped in 11C Part 2 (Migration `c4f6a8b0d2e5`). |
| 14 — Production hardening | type migrations only | JSON → JSONB, String(36) → native UUID. Postgres-specific, not "additive nullable" — stays in 14. |
| 15B Slice 7 — `AssignmentContext1-3` | Three nullable columns on `assignments` | **Out of 13D scope by design.** AssignmentContext is logic-bearing (e.g. "this assignment is for Award X category"), not display-only like PairContext. If it ever lands, the schema + rule-engine integration + CSV column + UI plumbing all live together in `guide/archive/segment_15B_per_instrument_assignments.md` Slice 7 — not as a pre-positioned column here. |

---

## PRs

### PR 0 — Rename `rule_sets` → `operator_rule_sets` (Tier 1 table-name harmonisation)

**Why first.** Bedrock for PR 2 (`session_rule_sets` — picks up
the symmetric name) and PR 4 (`instruments.rule_set_id` — gets to
target `operator_rule_sets.id` from birth, no fix-up migration
needed). Landing the rename last would force a follow-on FK
constraint rename on every table this segment introduces.

**Scope.** SQL only — the Python class `RuleSet` and its siblings
(`RuleSetRevision` / `RuleSetSchema` / `RuleSetOptions` /
`RuleSetScope`) keep their names. Just retag what table the class
maps to.

**Change.**

```python
# app/db/models/rule_set.py
class RuleSet(Base, TimestampMixin):
    __tablename__ = "operator_rule_sets"   # was: "rule_sets"
    # … no other changes …
```

```python
# app/db/models/rule_set.py (same file — RuleSetRevision class)
rule_set_id: Mapped[int] = mapped_column(
    ForeignKey("operator_rule_sets.id", ondelete="CASCADE"),
    # was: ForeignKey("rule_sets.id", ondelete="CASCADE")
    nullable=False, index=True,
)
```

**Migration sketch.**

```python
def upgrade() -> None:
    op.rename_table("rule_sets", "operator_rule_sets")
    # SQLite drops + recreates the FK during rename_table; Postgres
    # keeps the constraint but ties it to the renamed table. The
    # constraint name itself doesn't need an explicit rename for
    # SQLAlchemy to find it (it's resolved by tablename + column
    # set), but rename for tidiness on Postgres:
    with op.batch_alter_table("rule_set_revisions") as batch_op:
        batch_op.drop_constraint(
            "fk_rule_set_revisions_rule_set_id", type_="foreignkey"
        )
        batch_op.create_foreign_key(
            "fk_rule_set_revisions_rule_set_id_operator",
            "operator_rule_sets", ["rule_set_id"], ["id"],
            ondelete="CASCADE",
        )

def downgrade() -> None:
    # Symmetric reverse.
    op.rename_table("operator_rule_sets", "rule_sets")
    with op.batch_alter_table("rule_set_revisions") as batch_op:
        batch_op.drop_constraint(
            "fk_rule_set_revisions_rule_set_id_operator",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "fk_rule_set_revisions_rule_set_id",
            "rule_sets", ["rule_set_id"], ["id"],
            ondelete="CASCADE",
        )
```

(Verify constraint names against `c5e9a8f3d4b1`'s autogenerated
output before authoring — Alembic constraint naming may differ
from the sketch above.)

**Inert.** Class identifier `RuleSet` is unchanged; all 243+
service / route / view / test references keep working without
edit. Tests pass green on first try because they exercise the
class, not the table-name string.

**Sweep.** Doc references in `guide/`, `spec/`, etc. update
mechanically (`s/\brule_sets\b table/operator_rule_sets table/`).
~9 non-archive files; archive entries left as historical record.

**Tests.** `tests/integration/test_rule_set_rename_schema.py` —
asserts the table is reachable under the new name (round-trip
insert + query) and that the FK from `rule_set_revisions` still
cascades correctly.

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

### PR 2 — `session_rule_sets` table (15C prep)

**Why.** Post-PR-0, `operator_rule_sets` is the operator library
tier (visible across all of an operator's sessions). Per-session
**copies** need their own table so each session can carry a
complete, portable, independently-edited snapshot of the RuleSets
it uses. 15C populates these rows via "Add from library" / "Save
to library" actions; 15B's `instruments.rule_set_id` (PR 4 below)
points into this table, not into `operator_rule_sets`.

**Sketch shape.**

```python
class SessionRuleSet(Base, TimestampMixin):
    __tablename__ = "session_rule_sets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Snapshot of the rule tree at copy / edit time; no per-session
    # revisions table. (RTDs are similarly minimalistic per the
    # 2026-05-09 design call.) Operator preserving history is an
    # explicit "Save to library" action that creates a new revision
    # in rule_set_revisions on the library side.
    combinator: Mapped[str] = mapped_column(String(16), nullable=False)
    exclude_self_reviews: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rules_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False
    )
    # Provenance only — survives library-RuleSet deletion via SET NULL.
    library_origin_id: Mapped[int | None] = mapped_column(
        ForeignKey("operator_rule_sets.id", ondelete="SET NULL"),
        index=True, nullable=True,
    )
```

**Inert.** No service code reads or writes the new table. The
existing Rule Builder + assignments-generation pipeline stays
pointed at `operator_rule_sets` (via the `RuleSet` class) until
15C reroutes it.

**Tests.** `tests/integration/test_session_rule_set_schema.py` —
round-trip insert with NULL + non-NULL `library_origin_id`;
`SET NULL` behaviour when the referenced `operator_rule_sets`
row is deleted; CASCADE on `sessions.id`.

### PR 3 — `operator_response_type_definitions` table (15C prep)

**Why.** Today's `response_type_definitions` is per-session.
Operator-library RTDs need their own table so an operator can
author "1-7 Likert" once and have it auto-copy into every new
session they create. Mirror of the post-PR-0 `operator_rule_sets`
shape on the RuleSet side (just minus revisioning, since RTDs
are minimalistic per the 2026-05-09 design call).

**Sketch shape.**

```python
class OperatorResponseTypeDefinition(Base, TimestampMixin):
    __tablename__ = "operator_response_type_definitions"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id", "response_type",
            name="uq_operator_rtd_owner_name",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    response_type: Mapped[str] = mapped_column(String(64), nullable=False)
    data_type: Mapped[str] = mapped_column(String(16), nullable=False)
    min: Mapped[float | None] = mapped_column(Float, nullable=True)
    max: Mapped[float | None] = mapped_column(Float, nullable=True)
    step: Mapped[float | None] = mapped_column(Float, nullable=True)
    list_csv: Mapped[str | None] = mapped_column(Text, nullable=True)
```

The existing per-session `response_type_definitions` row gains a
nullable `library_origin_id` FK back to this table — provenance
only, `SET NULL` on library-RTD delete. (Schema for that
column-add lives in the same PR for one cohesive migration.)

**Inert.** No service code reads or writes the new table or the
new provenance column. The existing seed materialisation
(`SEEDED_RESPONSE_TYPE_DEFINITIONS` → `ensure_default_response_type_definitions`)
keeps its current behaviour. 15C wires up the
auto-copy-on-session-create + Save-to-library / Add-from-library
flows.

**Tests.** `tests/integration/test_operator_rtd_schema.py` —
round-trip insert; unique-constraint enforcement on
`(owner_user_id, response_type)`; cascade on user delete;
provenance-pointer behaviour on
`response_type_definitions.library_origin_id`.

### PR 4 — `instruments.rule_set_id` nullable FK → `session_rule_sets` (15B prep)

**Why.** 15B's per-instrument RuleSet selection. Each instrument
points at its session's copy of the chosen RuleSet (not at the
operator-library row). Detail in
`guide/archive/segment_15B_per_instrument_assignments.md` Slice 2.

**FK direction rationale.** This column lives on `instruments`,
not on `session_rule_sets`. Instrument-scoped containers point at
the rule they apply, not vice versa — same reasoning as the
deliberate flip in this segment's earlier draft (RuleSets are
content, not derived data). The pointer targets the **per-session
copy** so that:

- Deleting an instrument disposes of its pointer cleanly without
  touching the session's RuleSet copy. If other instruments in
  the session apply the same RuleSet, they keep their pointers.
- Deleting a `session_rule_sets` row (operator removes it from
  the session) clears the pointer on every instrument that
  referenced it via SQL `SET NULL`. Instrument falls back to "no
  rule selected" until the operator picks one — never silently
  inherits a different rule.
- Deleting from the operator library (`operator_rule_sets`) does
  **not** touch any instrument pointer — those point at session
  copies, which survive library deletes (the library-origin FK
  is `SET NULL` per PR 2).
- Resetting an instrument's assignments is just an `UPDATE …
  SET rule_set_id = NULL`. No `DELETE` cascade involved at all.

**Change.**

```python
# app/db/models/instrument.py
rule_set_id: Mapped[int | None] = mapped_column(
    ForeignKey("session_rule_sets.id", ondelete="SET NULL"),
    index=True, nullable=True,
)
```

Plus an Alembic `op.add_column` migration. NULL = "no rule
currently selected for this instrument" (initial state for every
existing instrument).

**Inert.** No service code reads or writes the column.
`assignments.replace_assignments` continues to fan one set of
generated pairs across every instrument. 15B Slice 2 starts
persisting the choice into this column once 15C has populated
`session_rule_sets`.

**Tests.** `tests/integration/test_instrument_rule_set_id_schema.py`
— insert with NULL + non-NULL; `SET NULL` behaviour when the
referenced `session_rule_sets` row is deleted; instrument cascade
deletes the pointer with the row, session_rule_set untouched.

### PR 5 — `instruments.sort_display_fields` JSON column (13B ride-along)

**Why.** 13B PR 1 already specs this as a schema-only PR
("infrastructure-only … the column sits dormant, it's a `NULL`
column without any operator able to break it"). Lifting it here
merges it with the other schema-only work and lets 13B PR 1
collapse into 13B's render-path slice.

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

**Optional.** If 13B's plan owner prefers a self-contained ladder,
drop this PR and let 13B own its own schema. Recommend folding —
the schema move is genuinely uncoupled from the UI work.

### PR 6 — `instruments.group_kind` column (13C ride-along)

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

**Optional.** Same call as PR 5 — keep 13C self-contained or
fold the schema work here. Recommend fold.

---

## Sequencing

PR ordering matters for:

- **PR 0** lands first — bedrock. PR 2 and PR 4 can then reference
  `operator_rule_sets` from birth instead of writing the old name
  and patching it later.
- **PR 4** depends on PR 2's `session_rule_sets` table existing.
- **PR 3** packages two related changes (new
  `operator_response_type_definitions` table + provenance column on
  the existing `response_type_definitions`) into one migration.

Recommended order:

0. **PR 0** — Rename `rule_sets` → `operator_rule_sets` (Tier 1).
1. **PR 1** — `session_field_labels` table.
2. **PR 2** — `session_rule_sets` table.
3. **PR 3** — `operator_response_type_definitions` table + the
   `response_type_definitions.library_origin_id` provenance
   column.
4. **PR 4** — `instruments.rule_set_id` (depends on PR 2).
5. **PR 5** — `instruments.sort_display_fields` JSON column.
6. **PR 6** — `instruments.group_kind` column.

Optional fold-out: PR 5 and PR 6 can defer to their owning
segments if 13B / 13C plan owners prefer self-contained ladders;
13D becomes a 5-PR segment in that case.

---

## Risks + open questions

- **PR 0 is the only non-additive migration.** It renames an
  existing table — `op.rename_table` is well-supported by both
  SQLite and Postgres but is the highest-risk change in this
  segment (constraint names, downgrade reversibility). Land it
  first and on its own to isolate the failure mode.
- **All other migrations are additive + nullable + no backfill** —
  same shape as the 11C Part 2 outbox column scaffolding. The
  `ci-postgres` job round-trips every migration on a real Postgres
  16 service container; SQLite parity is exercised by the local
  pytest suite.
- **Inert is enforceable.** `grep` audits at PR-close time:
  `grep -rn "session_field_labels\|session_rule_sets\|operator_response_type_definitions\|sort_display_fields\|group_kind" app/services/ app/web/`
  should return zero hits in the service layer. The existing
  `rule_set_id` form-param wiring stays — that's not a new column
  reference. PR 0's `operator_rule_sets` rename is also inert in
  the sense that no Python code outside the model file even
  references the table-name string.
- **13B / 13C call to fold or not** — see "Optional" notes on PRs
  5 / 6. If the feature plan owners want to keep the slice self-
  contained, drop those PRs from this segment and 13D becomes a
  5-PR segment.
- **Workspace-seed migration NOT in 13D.** The cleanup that moves
  `operator_rule_sets` rows with `scope=seed` out to a code
  constant (mirroring `SEEDED_RESPONSE_TYPE_DEFINITIONS`) is a
  service-layer change, not a schema-only change — it lives in
  15C.
- **RTD per-session table rename deferred.** The optional
  `response_type_definitions` → `session_response_type_definitions`
  rename for full symmetry isn't in PR 0; it would touch ~80
  service / route / view / test references through the
  `ResponseTypeDefinition` class. Worth doing if the asymmetry
  proves confusing in practice; not worth doing pre-emptively.

---

## Critical files

- New per PR:
  - PR 0: One `__tablename__` flip + one FK string update in `app/db/models/rule_set.py` + Alembic `rename_table` migration. ~9 doc-file `s/rule_sets/operator_rule_sets/` sweeps in `guide/` + `spec/`. No service / route / view / test edits (class identifier `RuleSet` unchanged).
  - PR 1: `app/db/models/session_field_label.py` + Alembic migration.
  - PR 2: `app/db/models/session_rule_set.py` + Alembic migration.
  - PR 3: `app/db/models/operator_response_type_definition.py` + one column add to `app/db/models/response_type_definition.py` + Alembic migration.
  - PR 4: One column add to `app/db/models/instrument.py` + Alembic migration.
  - PR 5: One column add to `app/db/models/instrument.py` + Alembic migration.
  - PR 6: One column add to `app/db/models/instrument.py` + Alembic migration.
- Touched: `app/db/models/__init__.py` (re-export the three new
  classes — `SessionFieldLabel`, `SessionRuleSet`,
  `OperatorResponseTypeDefinition`).

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
  the new tables / columns after each PR's diff lands.
