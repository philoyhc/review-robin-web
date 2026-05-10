# Segment 12A-3 — Export / import updates for 15D

**Status:** Planning. Sized 2026-05-10; refreshed against
the post-15D codebase 2026-05-10. **Last in the locked
sequence 13E → 12C → 15D → 12A-3.** Subsumes the
previously-planned 12A-2 (Settings CSV import) — see
"Relationship to 12A-2" below.

This segment evolves the export / import system to match
15D's post-revamp shape. **Export refresh lands first**
(PRs 1 + 2), then the importer-side work (PRs 3 + 4) lights
up Settings round-trip through Quick Setup. The targeted
Extract Data card becomes a **session-portability bundle**
(everything an operator needs to fully set up a fresh
session from scratch) plus a separate **analysis**
download.

**Target layout** (Extract Data card, 2-column grid;
locked in PR 2):

```
Reviewers           |  Session settings
Reviewees           |  Responses
Relationships       |  Zip all  (greyed out — deferred)
```

Left column = per-entity rosters (operator-uploaded
porting inputs). Right column = session-level outputs
(settings, downstream-analysis, future bundle).

Mapped to the porting-vs-analysis split:

```
Setup (round-trip):  Reviewers · Reviewees · Relationships · Session settings
Analysis only:       Responses
```

The pre-12A-3 Assignments tile is dropped from Extract
Data — assignments are derived (rule-based engine + roster
+ relationships), not an input to a new session, so the
download has no place in a porting bundle. (Operators who
want to inspect current pairings stay on the Operations
Assignments page, where the preview table already shows
the live state.)

## Goal

Bring the export / import surface into alignment with the
post-15D world:

- **Round-trip the new Relationships table.** Add a
  per-entity export + Extract Data tile for the
  `relationships` table that 15D wired. The underlying
  `parse_relationship_csv` importer service +
  `relationships.imported` audit event + per-entity
  Manage page upload form were already shipped by 15D —
  this segment builds the
  export route + UI surfaces on top of the existing
  service.
- **Ship the Settings CSV importer** (the 12A-2 work,
  absorbed). Quick Setup slot for Settings graduates
  to live (was 12A-2 PR 2's job).
- **Drop the Assignments tile from Extract Data.**
  Post-15D the assignments table is system-derived —
  there is no porting use case (no matching importer,
  never was a round-trip target post-15D) and the
  legacy debugging / analytical use case is better
  served by the live preview table on the Operations
  Assignments page. The underlying export route +
  service code retire too.
- **No new schema.** All schema for this round lands
  in 13E + 15D; 12A-3 is pure CSV-format / importer /
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

## Codebase-check notes (2026-05-10)

What 15D already shipped that 12A-3 builds on:

- **`relationships` table** wired end-to-end:
  per-entity Manage page (`/operator/sessions/{id}/relationships`)
  + upload form + `parse_relationship_csv` importer
  service + `relationships.imported` audit event +
  `pair_context_lookup` consumption in
  `app/services/rules/engine.py`. 12A-3 PR 2 only adds
  the **export half** — there is no need to also ship
  an importer.
- **Manual-CSV assignment authoring retired.** 15D PR 6a
  removed the upload form on the Operations Assignments
  page; `assignment_mode == "manual"` survives only as
  a dev-diagnostic surface for legacy data.
- **`Assignment.context` JSON dropped.** Pair-context
  tags now live exclusively in `relationships.tag_*`.
  The pre-15D assignments-CSV column ordering (which
  carried `Pair*Tag*` columns sourced from
  `Assignment.context`) is no longer applicable — but
  since the Assignments tile retires entirely in
  PR 4, no CSV-shape rewrite is needed.

What's still pre-12A-3:

- Extract Data card has 5 tiles + bundle: Reviewers /
  Reviewees / **Assignments** / Responses / Session
  settings (+ inert Zip all). After 12A-3: Reviewers /
  Reviewees / **Relationships** / Responses / Session
  settings (+ inert Zip all). Net: same row count,
  Assignments swaps for Relationships.
- No Settings CSV importer; the Quick Setup Settings
  slot is inert pending PR 1 + PR 3.

## Scope

### Settings importer (absorbed from 12A-2)

- New `apply_session_config(db, session, rows) ->
  ApplyResult` function in
  `app/services/session_config_io.py` (mirroring the
  existing `serialize_session_config` from 12A-1 PR 1).
  Two-phase parse + apply per the 12A-2 plan's
  "Idempotency model" section.
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

### Relationships per-entity export

The importer half is already shipped by 15D PR 1 — see
codebase-check notes above. 12A-3 only adds the export
half + UI tile:

- **Export service:** `app/services/extracts/relationships_extract.py`
  with `serialize_relationships(session) -> Iterable[Row]`.
  6-column wide CSV:

  ```
  ReviewerEmail,RevieweeEmail,PairContextTag1,PairContextTag2,PairContextTag3,Status
  ```

  Header pinned in unit tests; ordering deterministic
  (`(reviewer.email, reviewee.email_or_identifier)`).
  Filename `{code}_relationships.csv`.

- **Audit event:** `session.relationships_extracted`
  registered in `EVENT_SCHEMAS` (mirror of
  `session.reviewers_extracted` etc.).

- **Route:** `GET /operator/sessions/{id}/export/relationships.csv`
  in `app/web/routes_operator/_extracts.py` (mirror of
  the reviewers / reviewees / responses / settings
  routes).

- **Extract Data tile:** new "Relationships" row in
  `app/web/views/_extract_data.py`. PR 1 inserts the
  row after Reviewees in the current DOM order;
  PR 2 finalises the row order to the target left/right
  column layout when Assignments retires. Count display
  conditionally suppresses if 0 (mirrors the existing
  rosters' display rule).

### Quick Setup integration (Settings + Relationships slots)

15D restructures Quick Setup to 4 slots:

```
Slot 1: Reviewers
Slot 2: Reviewees
Slot 3: Relationships  (live in 15D)
Slot 4: Settings       (graduates in 12A-3)
```

12A-3 graduates the Settings slot to live (was 12A-2
PR 2). The Relationships slot itself is already wired
by 15D; 12A-3 confirms the submit-all chain ordering
runs reviewers → reviewees → relationships → settings.

### Assignments CSV: dropped from Extract Data

Post-15D the assignments table is system-derived —
operator inputs (roster + relationships + RuleSet
selection) determine it deterministically. There is
no porting use case (assignments are output, not input)
and no analytical use case the live preview on
Operations Assignments doesn't already serve.

12A-3 PR 2 retires the surface end-to-end:

- Drop the **Extract Data tile** (`key="assignments"`
  row in `app/web/views/_extract_data.py`).
- Drop the **export route**
  (`GET /operator/sessions/{id}/export/assignments.csv`
  in `_extracts.py`).
- Drop the **extract service**
  (`app/services/extracts/assignments_extract.py`).
- Drop the `session.assignments_extracted` audit-event
  registration in `EVENT_SCHEMAS`.
- Drop the related tests
  (`tests/.../test_assignments_extract.py`).
- Drop the assignment-mode-aware count display +
  tile-suppression logic.

**Keep** the seeded-RuleSet audit-log fallback in
`app/services/session_config_io.py` (added in 12A-1 PR 1a).
That fallback is load-bearing for the **Settings CSV**
export's `instruments[N].rule_set_name` capture —
`Instrument.rule_set_id` is universally NULL pre-15B, so
the audit-log fallback is the only way to round-trip
which RuleSet was used. It retires properly when 15B
wires `Instrument.rule_set_id` for real, not in 12A-3.

## PR sequence (4 PRs, re-sequenced 2026-05-10)

**Export refresh first, then importer work.** The
export-side PRs (1 + 2) bring Extract Data into
alignment with the post-15D session model — adding
Relationships and retiring Assignments — before the
importer-side PRs (3 + 4) light up Settings round-trip
through Quick Setup.

PRs 1 + 2 + 3 are independent; PR 4 depends on PR 3
(Settings importer must exist before its slot can
graduate to live).

### PR 1 — Relationships export + Extract Data tile

Net-additive — gives operators the new capability
immediately.

- `serialize_relationships(session)` extract service in
  `app/services/extracts/relationships_extract.py` +
  `session.relationships_extracted` audit event in
  `EVENT_SCHEMAS`.
- `GET /operator/sessions/{id}/export/relationships.csv`
  route in `_extracts.py`.
- New "Relationships" tile in the Extract Data card
  (between Reviewees and Responses) via
  `app/web/views/_extract_data.py`.
- Sweep `session_config_io.py` for any orphan code that
  references the dropped `Assignment.context.pair_context_*`
  shape (15D dropped the column; this is a confirmation
  pass, not new work).
- Tests: round-trip (export → import via 15D's already-
  shipped `parse_relationship_csv` → export byte-stable);
  export route auth + filename + audit emission with row
  count; Extract Data card tile renders + downloads.

### PR 2 — Assignments-CSV retirement sweep

Cleanup pass + final layout lock.

- Drop the Extract Data tile (`key="assignments"` row
  in `_extract_data.py`).
- Drop the `/export/assignments.csv` route in
  `_extracts.py`.
- Drop `app/services/extracts/assignments_extract.py`.
- Drop `session.assignments_extracted` from
  `EVENT_SCHEMAS`.
- Drop the assignment-mode-aware count display +
  tile-suppression logic.
- Drop related test files
  (`tests/.../test_assignments_extract.py`).
- **Keep** the seeded-RuleSet audit-log fallback in
  `session_config_io.py` — it's load-bearing for
  Settings CSV export's `rule_set_name` capture
  (see "Assignments CSV: dropped from Extract Data"
  above).
- **Reorder** the row list in `_extract_data.py` to
  the target layout (left/right columns; the
  `extract-data-grid` CSS already wraps row-major in
  a 2-column grid):

  ```
  Reviewers           |  Session settings
  Reviewees           |  Responses
  Relationships       |  Zip all  (inert)
  ```

  DOM order: Reviewers, Session settings, Reviewees,
  Responses, Relationships, Zip all.
- Update `README.md` — Extract Data blurb shifts from
  "five live CSV downloads (Settings, Reviewers,
  Reviewees, Manual Assignments, Responses)" to
  "five live CSV downloads (Settings, Reviewers,
  Reviewees, Relationships, Responses)".
- Update `spec/settings_inventory.md` §10 — flip the
  Relationships row from "Pending 12A-3" to "✅ All";
  retire the assignments-CSV row from the coverage
  table.

After PR 1 + PR 2, the Extract Data card matches the
target layout above. The full 4-CSV porting bundle is
downloadable from the left column; the analysis-only
Responses CSV + future bundle live in the right
column.

### PR 3 — Settings importer + route

Exact 12A-2 PR 1 scope, absorbed:

- `apply_session_config(db, session, rows) ->
  ApplyResult` in `app/services/session_config_io.py`.
- `POST /operator/sessions/{id}/import-config` route
  with the lifecycle gate (`status in {"draft",
  "validated"}`); invalidates `validated → draft` via
  `lifecycle.invalidate_if_validated`.
- `session.settings_imported` audit event in
  `EVENT_SCHEMAS` per 11K's strict-mode gate.
- Settings importer's wipe-and-replace step explicitly
  wipes the assignments table before instruments
  (folded from 12C-2 PR 2).
- **No standalone Manage page.** The importer is
  reachable only via Quick Setup slot 4 (graduated in
  PR 4) — Settings is structurally different from
  rosters and isn't naturally browseable.
- Round-trip integration test:
  `serialize_session_config(A) → file →
  apply_session_config(B) → serialize_session_config(B)
  matches A` (modulo the `name` / `code` fallback
  rule).

### PR 4 — Quick Setup Settings slot graduation

- Settings slot (slot 4 in 15D's layout) graduates to
  live, pointing at PR 3's import-config route.
- View-shape adapter `views.build_quick_setup_context`
  flips slot 4's `is_wired=True`.
- Tests: Quick Setup card renders 4 live slots in both
  Create New Session + Session Home contexts; submit-all
  chain runs reviewers → reviewees → relationships →
  settings; per-slot error banners surface in the right
  slot. (Relationships slot is already live from 15D —
  this PR just adds the Settings slot to the chain.)

## Out of scope

- **Schema changes.** All in 13E (`sessions.self_reviews_active`,
  `relationships` table) or 15D (drop
  `Assignment.context`).
- **Generation-path consumption of relationships.**
  15D wires it into the rule-based engine via
  `pair_context_lookup`.
- **Rule grammar extensions.** 15D adds
  `pair_context.tag_N` matchers / filters / quotas
  to `app/schemas/rules.py`.
- **Operations Assignments page UI.** Lives in 15D;
  12A-3 doesn't touch it.
- **Zip bundle export.** Deferred follow-on of the
  12A-1 export track; orthogonal to 15D. The
  inert Zip all row stays inert.

## Test impact

- Relationships CSV round-trip integration test
  (PR 1) — export → import via 15D's already-shipped
  `parse_relationship_csv` → export byte-stable.
- Assignments-CSV removal sweep (PR 2) — confirm no
  route responds, no extract service exists, no
  audit-event registration remains, Extract Data card
  renders 5 tiles in the new order (Reviewers ·
  Reviewees · Relationships · Responses · Session
  settings).
- Settings CSV round-trip integration test (PR 3) —
  pin the contract that the export and import halves
  stay in lockstep on the 3-column `field,value,
  data_type` shape.
- Quick Setup chain tests (PR 4) — 4 live slots,
  submit-all chain ordering, per-slot error
  surfacing.

## Doc impact

- `docs/status.md` gains one timeline entry per PR.
- `guide/todo_master.md`:
  - Move Segment 12A-3 from **Upcoming** to **Done**
    under "Segment 12" once all 4 PRs land.
  - The 12A-2 entry stays in the
    "Historical-reference entries" subsection per the
    Post-Segment 15 todo_master refresh.
- `spec/settings_inventory.md` — §10 (CSV coverage)
  rewrites to reflect the post-12A-3 4-CSV porting
  bundle + 1 analysis download. The pending
  Relationships row (added in the post-15D refresh)
  flips from "Pending 12A-3" to "✅ All" in PR 1; the
  assignments-CSV row retires in PR 2.
- `README.md` — Extract Data blurb updated in PR 2
  (when the Assignments tile retires and Relationships
  is in place).
- `guide/archive/segment_12A-1_export.md` — appendix
  update noting the new Relationships extract +
  retired Assignments extract; same per-entity export
  pattern.
- `guide/segment_12A-2_import.md` — kept as
  historical reference; status block already points at
  12A-3 as the actual delivery vehicle (added in
  Post-Segment 15 refresh).

## Related context

- **Segment 12A-1** (export, shipped 2026-05-09;
  `guide/archive/segment_12A-1_export.md`) — the per-entity
  CSV pattern this segment extends + the Assignments
  CSV that this segment retires.
- **Segment 12A-2** (Settings CSV import, planned
  but absorbed into this segment;
  `guide/segment_12A-2_import.md`) — the contract
  this segment's PR 1 ships.
- **Segment 13E** (DB prep for the 12C / 15D block;
  `guide/archive/segment_13E_db_prep.md`) — the
  `relationships` table this segment's PR 2 reads.
- **Segment 12C** (self-review revamp;
  `guide/archive/segment_12C_self-review_revamp.md`) — 12C-2
  PR 2's "Settings importer wipes assignments
  explicitly" lock is folded into this segment's
  PR 1.
- **Segment 15D** (assignments revamp;
  `guide/archive/segment_15D_assignments_revamp.md`) — wired
  the Relationships table that this segment's PR 2
  exports; defines the post-15D Quick Setup layout
  that this segment's PR 3 graduates.
