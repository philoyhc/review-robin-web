# Segment 12A-3 — Export / import updates for 15D

**Status:** Planning. Sized 2026-05-10. **Last in the
locked sequence 13D-1 → 12C → 15D → 12A-3.** Subsumes the
previously-planned 12A-2 (Settings CSV import) — see
"Relationship to 12A-2" below.

This segment evolves the export / import system to match
15D's post-revamp shape: ships the Settings importer
(absorbed from 12A-2), adds Relationships per-entity
export + import (parallel to rosters), and adjusts the
manual assignments CSV around 15D's "always derived"
model.

## Goal

Bring the export / import surface into alignment with the
post-15D world:

- **Round-trip the new Relationships table.** Add a
  per-entity export + per-entity import for the
  `relationships` table that 15D wires. Same shape /
  flow as today's reviewer + reviewee per-entity
  imports.
- **Ship the Settings CSV importer** (the 12A-2 work,
  absorbed). Quick Setup slot for Settings graduates
  to live (was 12A-2 PR 2's job).
- **Update the assignments CSV** to download-only
  semantics post-15D. Manual upload via the Assignments
  page retires (handled in 15D); the export track keeps
  the CSV for reference / debugging / one-time
  analytical export from the Operations Assignments
  page.
- **No new schema.** All schema for this round lands
  in 13D-1 + 15D; 12A-3 is pure CSV-format / importer /
  route work.

## Relationship to 12A-2

The originally-planned **12A-2 (Settings CSV import)** is
**absorbed into 12A-3**. Reasoning: the 15D revamp
changes the Quick Setup slot layout (slot 3 rotates from
manual-assignments to relationships), so the Settings
importer's "graduate slot 4 to slot 3 / new layout" work
overlaps with the Relationships slot work. Easier to
ship them together.

The **`guide/segment_12A-2_import.md` plan stays as
historical reference** — its contract (3-column Settings
CSV, wipe-and-replace, lifecycle gate) carries over
verbatim to 12A-3 PR 1. Read 12A-2 for the
contract / inclusion model / fallback rules; read 12A-3
for the PR-by-PR delivery.

## Scope

### Settings importer (absorbed from 12A-2)

- New service module `app/services/session_config_io.py`
  gains an `apply_session_config(db, session, rows) ->
  ApplyResult` function (mirroring the existing
  `serialize_session_config` from 12A-1 PR 1). Two-phase
  parse + apply per the 12A-2 plan's "Idempotency model"
  section.
- New route `POST /operator/sessions/{id}/import-config`
  with the lifecycle gate (`status in {"draft",
  "validated"}`).
- Audit event `session.settings_imported` registered in
  `EVENT_SCHEMAS` per 11K's strict-mode gate.
- Settings importer's wipe-and-replace step **explicitly
  wipes the assignments table** before wiping
  instruments (per the 12C-2 PR 2 lock that's now folded
  into 12A-3 — the cascade ordering is deterministic
  and the operator's mental model "Settings upload
  wipes instruments + assignments" matches the
  implementation).

### Relationships per-entity export + import

Mirrors the per-entity flows for reviewers + reviewees
(12A-1 PR 2 shipped the rosters):

- **Export:** `app/services/extracts/relationships_extract.py`
  with `serialize_relationships(session) -> Iterable[Row]`.
  6-column wide CSV:

  ```
  ReviewerEmail,RevieweeEmail,PairContextTag1,PairContextTag2,PairContextTag3,Status
  ```

  Header pinned in unit tests; ordering deterministic
  (`(reviewer.email, reviewee.email_or_identifier)`).
  Filename `{code}_relationships.csv`. New audit event
  `session.relationships_extracted` (mirrors
  `session.reviewers_extracted` etc.).

- **Import:** `parse_relationship_csv` in
  `app/services/csv_imports.py` (or a sibling
  `app/services/relationships.py` module — slot during
  PR scoping). Same wipe-and-replace per-row upsert
  pattern as `parse_reviewer_csv` /
  `parse_reviewee_csv`. Resolves `ReviewerEmail` against
  the session's reviewers; resolves `RevieweeEmail`
  against the session's reviewees; rejects rows that
  reference unknown identifiers. Uniqueness enforced
  by the 13D-1 PR 2 unique constraint.

- **Manage page:** new `/operator/sessions/{id}/relationships`
  upload form mirrors today's reviewer / reviewee
  upload pages.

### Quick Setup integration (Settings + Relationships slots)

15D restructures Quick Setup to 4 slots:

```
Slot 1: Reviewers
Slot 2: Reviewees
Slot 3: Relationships  (new in 15D)
Slot 4: Settings       (live in 12A-3)
```

12A-3 graduates the Settings slot to live (was 12A-2
PR 2). The Relationships slot itself is wired by 15D;
12A-3 just consumes the Relationships per-entity
importer for slot 3's apply step (per 15D's Quick
Setup chain ordering).

### Assignments CSV: download-only

Post-15D the assignments table is system-derived. The
existing per-entity assignments CSV (12A-1 PR 3)
remains for **download-only**: operator clicks
"Download Assignments CSV" on the Operations
Assignments page to get a snapshot of the current
state for reference / debugging / external analysis.
**No matching importer** — manual row authoring
retires in 15D.

12A-3 keeps the export route + audit event; removes
any matching upload route / form that 12C-2 PR 3
might have shipped (per the original 12C plan). If
12C-2 PR 3 was deferred to 15D / 12A-3 (per the
holistic-sequence revision), there's nothing to
remove — this is a no-op for that path.

### Manual assignments importer retirement

The legacy `parse_manual_csv` / `replace_assignments`
flow (today's behaviour pre-15D) is removed by 15D.
12A-3 doesn't ship anything new here; called out for
completeness so the export / import surface
inventory is accurate.

## PR sequence (4 PRs, locked 2026-05-10)

PRs 1 + 2 are independent; PR 3 depends on PR 1
(Settings importer must exist before its slot can
graduate to live); PR 4 is independent dead-code
cleanup.

### PR 1 — Settings importer + route

Exact 12A-2 PR 1 scope, absorbed:

- `apply_session_config(db, session, rows) ->
  ApplyResult` in `app/services/session_config_io.py`.
- `POST /operator/sessions/{id}/import-config` route.
- `session.settings_imported` audit event in
  `EVENT_SCHEMAS`.
- Settings importer's wipe-and-replace step explicitly
  wipes the assignments table before instruments
  (folded from 12C-2 PR 2).
- Round-trip integration test:
  `serialize_session_config(A) → file →
  apply_session_config(B) → serialize_session_config(B)
  matches A` (modulo the `name` / `code` fallback
  rule).

### PR 2 — Relationships per-entity export + import

- `serialize_relationships(session)` extract +
  `/export/relationships.csv` route.
- `parse_relationship_csv` importer + `/relationships`
  Manage page upload.
- `session.relationships_extracted` +
  `relationships.imported` audit events.
- Tests: round-trip (export → import → export
  byte-stable); FK rejection for unknown reviewer /
  reviewee identifiers; unique-constraint enforcement;
  status enum validation.

### PR 3 — Quick Setup Settings + Relationships slot graduation

- Settings slot (slot 4 in 15D's layout) graduates to
  live, pointing at PR 1's import-config route.
- Relationships slot (slot 3 in 15D's layout) graduates
  to live, pointing at PR 2's importer.
- View-shape adapter `views.build_quick_setup_context`
  flips both slots' `is_wired=True`.
- Tests: Quick Setup card renders 4 live slots in both
  Create New Session + Session Home contexts; submit-all
  chain runs reviewers → reviewees → relationships →
  settings; per-slot error banners surface in the right
  slot.

### PR 4 — Assignments-CSV download-only cleanup

- Confirms the assignments extract route stays live
  (download remains useful as a reference snapshot).
- Verifies any legacy upload form / route on the
  Operations Assignments page is retired (should
  already be done by 15D — this PR is a sweep).
- Updates `spec/settings_inventory.md` §10's CSV
  coverage matrix to reflect the post-15D state.
- Tests: download route still works; no upload route
  responds to POST.

## Out of scope

- **Schema changes.** All in 13D-1 (`sessions.self_reviews_active`,
  `relationships` table) or 15D (drop
  `Assignment.context`).
- **Generation-path consumption of relationships.**
  15D wires it into `generate_full_matrix` + the
  rule-based engine + manual-CSV save (pre-15D paths).
- **Rule grammar extensions.** 15D adds
  `pair_context.tag_N` matchers / filters / quotas
  to `app/schemas/rules.py`.
- **Operations Assignments page UI.** Lives in 15D;
  12A-3 just confirms the download route still works
  on that page.
- **Zip bundle export.** Deferred follow-on of the
  12A-1 export track; orthogonal to 15D.

## Test impact

- Round-trip integration tests for both Settings CSV
  (PR 1) and Relationships CSV (PR 2). Pin the
  contract that the export and import halves stay in
  lockstep on each format.
- Quick Setup chain tests (PR 3) — 4 live slots,
  submit-all chain ordering, per-slot error
  surfacing.
- Spec sweep (PR 4) — `spec/settings_inventory.md`
  §10 + `spec/operator_ui_concept.md` enumerations of
  per-entity CSVs.

## Doc impact

- `docs/status.md` gains one timeline entry per PR.
- `guide/todo_master.md`:
  - Move Segment 12A-3 from **Upcoming** to **Done**
    under "Segment 12" once all 4 PRs land.
  - The 12A-2 entry retires from Upcoming when the
    holistic-sequence revision lands; replaced by
    12A-3.
- `spec/settings_inventory.md` — §10 (CSV coverage)
  rewrites to reflect the post-15D Relationships
  per-entity flow + assignments download-only state.
- `guide/archive/segment_12A-1_export.md` — appendix update
  noting the new Relationships extract; same
  per-entity export pattern.
- `guide/segment_12A-2_import.md` — kept as
  historical reference; status block updated to
  point at 12A-3 as the actual delivery vehicle.

## Related context

- **Segment 12A-1** (export, shipped 2026-05-09;
  `guide/archive/segment_12A-1_export.md`) — the per-entity
  CSV pattern this segment extends.
- **Segment 12A-2** (Settings CSV import, planned
  but absorbed into this segment;
  `guide/segment_12A-2_import.md`) — the contract
  this segment's PR 1 ships.
- **Segment 13D-1** (DB prep, second pass;
  `guide/segment_13D-1_db_prep.md`) — the
  `relationships` table this segment's PR 2 reads
  / writes.
- **Segment 12C** (self-review revamp;
  `guide/segment_12C_self-review_revamp.md`) — 12C-2
  PR 2's "Settings importer wipes assignments
  explicitly" lock is folded into this segment's
  PR 1.
- **Segment 15D** (assignments revamp;
  `guide/segment_15D_assignments_revamp.md`) — wires
  the Relationships table that this segment's PR 2
  exports / imports; defines the post-15D Quick Setup
  layout that this segment's PR 3 graduates.
