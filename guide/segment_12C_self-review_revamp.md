# Segment 12C — Self-review revamp + Quick Setup upload semantics + chrome reorder

**Status:** Planning. **Codebase-check revision
2026-05-10** narrows 12C-1 from 5 PRs to **3 PRs**:
the bulk Include toggle (was PR 3) and the
ad-hoc-toggle-drop on the Rule Based card (was PR 4)
both defer to 15D PR 6, where the Operations
Assignments page is built. See the updated PR
sequence below + the "Forward-looking — 15D
alignment" matrix.

**Holistic-sequence revision 2026-05-10**: locked
sequence is **13E → 12C → 15D → 12A-3**. Under the
new sequence, 12C-2 + 12C-3 are **deferred / folded
into 15D** (15D fast-tracked); 12C ships **only
Sub-segment 12C-1** (now 3 PRs — schema lifted to
13E PR 1; bulk-toggle + ad-hoc-toggle-drop folded
into 15D PR 6). See "Forward-looking — 15D
alignment" below for the detailed map.

**Sub-segment 12C-1 (Part 1) — sized 2026-05-10
(narrowed to 3 PRs); ready to start once 13E PR 1
ships.** Schema (`sessions.self_reviews_active`)
lifted to 13E PR 1; 12C-1 PR 1 is now generation-path
wiring only (manual-CSV save path skipped — 15D
removes the operator-facing path entirely; dev-only
path doesn't need the self-review default).
Audit-event-name question settled 2026-05-10 (compact
form). Bulk Include toggle (was PR 3) and ad-hoc-toggle
drop (was PR 4) deferred to 15D PR 6.

**Sub-segment 12C-2 (Part 2) — DEFERRED 2026-05-10.**
The Quick Setup slot 3 retirement and Assignments-page
manual upload work is folded into 15D, where the
Quick Setup card is restructured anyway and manual
assignments retire entirely. See "Part 2 — DEFERRED"
section below for what was previously planned and how
15D absorbs it. The "Settings importer wipes
assignments explicitly" lock (was 12C-2 PR 2) is folded
into **12A-3 PR 1**.

**Sub-segment 12C-3 (Part 3) — DEFERRED 2026-05-10.**
The Setup-row chrome reorder (Instruments before
Assignments) is folded into 15D, which restructures
the chrome anyway (Assignments leaves the Setup row
entirely, becomes an Operations-row tab). See "Part 3
— DEFERRED" section below.

This doc covers **the self-review revamp** (Part 1, the
single sub-segment that ships from 12C). Parts 2 + 3 are
deferred / folded into 15D under the holistic-sequence
revision (2026-05-10) — kept here as historical record
+ "what was planned, where it went" pointers:

- **Part 1 — Two-layer self-review model (Sub-segment
  12C-1).** Replace today's scattered ad-hoc
  `exclude_self_review` toggles with a clean
  RuleSet-as-generator + Include-as-activator split.
  **Ships from 12C.**
- **Part 2 — Quick Setup upload semantics (Sub-segment
  12C-2).** *Deferred — folded into 15D + 12A-3.*
- **Part 3 — Chrome reorder: Instruments before
  Assignments (Sub-segment 12C-3).** *Deferred — 15D
  restructures the chrome anyway.*

The two parts share the same surfaces but answer different
questions; expect them to land as separate PR sequences.

---

## Forward-looking — 15D alignment (revised 2026-05-10)

Under the **locked sequence 13E → 12C → 15D → 12A-3**,
15D is fast-tracked and most of 12C's previously-planned
"interim" work is folded into 15D. Net effect: 12C ships
the self-review revamp (Sub-segment 12C-1, 5 PRs) and
nothing else. 12C-2 + 12C-3 are explicitly deferred —
their would-be intermediate states would be replaced by
15D's restructure within a single segment cycle, so the
intermediate work isn't worth the churn.

Per-PR map of what 12C ships vs. what 15D absorbs
(updated under the 2026-05-10 codebase-check
revision):

| 12C-1 piece (in original 5-PR sketch) | Status under the new sequence |
|---|---|
| `sessions.self_reviews_active` schema | **Lifted to 13E PR 1.** 12C-1 PR 1 is now generation-path wiring only. |
| Generation-path wiring for the self-review default (was PR 1; now PR 1) | **Ships from 12C.** Wires `generate_full_matrix` and the rule-based engine; manual-CSV save path skipped (15D removes the operator-facing path; dev-only path doesn't need the default). Inherited unchanged by 15D. |
| Rule Builder `exclude_self_reviews` checkbox (was PR 2; now PR 2) | **Ships from 12C.** Inherited unchanged by 15D. |
| Bulk Include toggle on Setup Assignments page (was PR 3) | **Deferred to 15D PR 6.** Folded into the Operations Assignments page build. Avoids a Setup-page intermediate that 15D relocates within days. Same route + audit event + flip-logic spec carries over. |
| Drop ad-hoc toggle on Rule Based card + validation copy refresh (was PR 4) | **Deferred to 15D PR 6.** Folded into the chrome restructure (the Rule Based card itself relocates with the page). |
| Full-matrix dead-code cleanup (was PR 5; now PR 3) | **Ships from 12C.** Inherited unchanged by 15D. Standalone route + `AssignmentMode.full_matrix` enum + Quick Setup legacy fallback all retire. `generate_full_matrix` itself stays (the seeded full-matrix RuleSet uses it via the rules engine). |

| 12C-2 piece | Where it goes |
|---|---|
| Quick Setup slot 3 retirement (was 12C-2 PR 1) | **Folded into 15D.** 15D restructures the Quick Setup card anyway (re-introduces slot 3 with Relationships content); doing slot retirement separately would mean Quick Setup goes 4 → 3 → 4 across two segments. Skip the intermediate hop. |
| Settings importer wipes assignments + instruments (was 12C-2 PR 2) | **Folded into 12A-3 PR 1.** The Settings importer doesn't exist until 12A-3 (which absorbs 12A-2's Settings-importer work), so adding the wipe step there is the natural home. |
| Manual upload via Assignments page Option A (was 12C-2 PR 3) | **Removed by 15D.** 15D retires manual upload entirely (Assignments table becomes always derived; manual rows give way to the Relationships table). No interim Option A behaviour ships from 12C. |

| 12C-3 piece | Where it goes |
|---|---|
| Setup-row chrome reorder (Instruments before Assignments) | **Folded into 15D.** 15D moves Assignments off the Setup row entirely; the Setup-row swap is moot post-15D. The status pills + Setup card row-list reorders also fold into 15D's restructure. |

**Specifically not pre-positioned by 12C** (lands fresh
with 15D):

- The new `relationships` table + per-entity importer
  (importer ships in 12A-3, table in 13E) +
  Relationships Setup page.
- Drop `Assignment.context` JSON column.
- Rule grammar additions (`pair_context.tag_N` matchers
  / filters / quotas).
- Operations Assignments page (replaces Setup
  Assignments).
- "Super buttons" multi-step shortcut actions.

---

## Part 1 — Two-layer self-review model (Sub-segment 12C-1)

### Goal

Replace today's three scattered ad-hoc `exclude_self_review`
toggles with a clean two-layer model:

1. **The RuleSet decides what gets generated.** A RuleSet's
   `exclude_self_reviews` flag is the only place an operator
   says "don't put self-review pairs into the assignments
   table at all". Edited in the **Rule Builder** as an
   explicit, first-class control.
2. **The Assignments page decides what's active.** Once
   self-review rows exist (because the RuleSet didn't filter
   them, or a manual CSV uploaded them), the operator
   bulk-flips their `Assignment.include` flag from a single
   on/off toggle on the Assignments page. **Persistent** —
   the operator's intent survives regeneration via a new
   session-level boolean column.

The two layers don't overlap: the RuleSet flag controls
**generation** (rows present or absent); the bulk toggle +
its persistence column control **activation** of rows that
exist.

### Targeted behaviors (locked 2026-05-09)

1. **Remove `exclude_self_review` as an ad-hoc generation
   toggle from every Assignments-upload surface.** Drop the
   form input from:
   - **Quick Setup** (slot 3, on both **Create New Session**
     and **Session Home**).
   - **Assignments page** (the toggle that today sits
     alongside the Generate button on the Rule Based card).

   The two surfaces share the slot-3 control vocabulary, so
   the form-field removal is one change applied to both
   contexts.
2. **Surface `exclude_self_reviews` in the Rule Builder.**
   The flag already lives on `RuleSetRevision` — promote it
   into the Rule Builder UI as a first-class checkbox.
   **Layout:** between the rule-list editor (the
   `+ MATCH / + FILTER / + QUOTA / + COMPOSITE` row) and the
   `Save` / `Cancel` action row at the bottom of the card.
   That keeps the rule-tree authoring above + the action
   row below, and slots the RuleSet-wide flag at the
   logical boundary between them. Remove the equivalent
   check from every other operator surface.
3. **Add a bulk Include toggle for self-reviews on the
   Assignments page.** A single on/off control that flips
   `Assignment.include` for every self-review row in the
   session at once **and** persists the operator's intent
   on `sessions.self_reviews_active` so it survives
   regeneration. **Layout:** just above the Assignments
   preview table — a header row showing toggle state +
   live count (e.g. "Self-reviews: ON (3 active, 0
   deactivated)" / "Self-reviews: OFF (0 active, 3
   deactivated)"). Per-row Include checkboxes (already
   present on the assignments table) keep their per-row
   role; the new toggle is a bulk shortcut whose state
   the row-level checkbox can override.

### Decisions (locked 2026-05-09)

- **Toggle UX = bulk on/off, persistent.** A single switch
  that flips every self-review row's `Assignment.include`
  flag at once **and** records the operator's intent on a
  new session-level column. Not a filter view; not
  per-row.
- **One new schema column —
  `sessions.self_reviews_active BOOLEAN NOT NULL DEFAULT
  TRUE`.**
  - Persists the operator's last bulk-toggle decision so
    intent survives regeneration. Without it, regenerating
    the assignments table (e.g. roster changed, RuleSet
    swapped) would silently re-activate self-reviews
    because every new row defaults to `include=true`.
  - Read by the generation paths
    (`generate_full_matrix`, the rule-based engine,
    manual-CSV save) when creating self-review rows: new
    self-review rows get `include = sessions.self_reviews_active`.
  - Written by the bulk toggle's POST handler; same
    handler updates every existing self-review row's
    `include` to match in a single UPDATE.
  - Per-row checkbox flips don't write the column —
    individual overrides stay at the row level. Mixed
    state ("toggle is ON, row 7 is individually OFF")
    is supported; the toggle's banner copy makes the mix
    visible.
  - Defaults to `TRUE` on existing sessions (no
    behavioural change at migration time).
- **Full-matrix is fully absorbed into the RuleSet system.**
  At the UI level, full-matrix has already become "the
  full-matrix seeded RuleSet" picked from Quick Setup
  slot 3's dropdown. This sub-segment removes any
  **remaining standalone affordance** — most importantly
  the `POST /operator/sessions/{id}/assignments/full-matrix`
  route in `_assignments.py` and the
  `AssignmentMode.full_matrix` enum value, if no other
  surface still depends on either. (Spike to confirm:
  Quick Setup's legacy `rule="full_matrix"` payload
  fall-through in `_quick_setup.py:573-586` may be the
  only caller; if so, drop the fallback together with
  the route.)
- **Validation rule kept; copy refreshed.**
  `count_self_reviews_in_assignments` (and the
  `assignments.self_reviews_present` validation row that
  cites it) stays. Screen text updates to make clear that
  these are **self-review pairs that exist in the
  assignments table**, which can be turned on / off via
  the bulk Include toggle if the operator wants. No
  behavioural change to the predicate; just a copy
  refresh.

### Implementation pointers

- **Migration** — `alembic revision -m "12C-1 add
  sessions.self_reviews_active"`. Single `op.add_column`
  with `server_default=sa.true()` so existing rows backfill
  to `TRUE` without a Python-side update step. SQLite +
  Postgres dialects round-trip naturally; mirrors the
  `op.add_column` shape used by 13D PR 5 (`instruments.sort_display_fields`)
  and 13D PR 6 (`instruments.group_kind`).
- **Generation-path wiring.**
  - `generate_full_matrix(reviewers, reviewees)` — used
    today by the seeded full-matrix RuleSet's engine
    evaluation. Add a `self_reviews_active: bool`
    parameter (or read directly from the session inside
    the caller); when constructing the pair tuples, set
    `include = self_reviews_active` for any pair where
    `is_self_review(reviewer, reviewee)` returns `True`.
  - Rule-based engine in `app/services/rules/engine.py` —
    same pattern when it materialises self-review pairs
    that survived the RuleSet's `exclude_self_reviews`
    filter.
  - Manual-CSV save in `app/services/csv_imports.py`
    (or wherever `parse_manual_csv` writes
    `Assignment.include`) — when the CSV row is a
    self-review pair (predicate-driven), AND the
    operator-typed `IncludeAssignment` cell is empty /
    default, fall back to
    `sessions.self_reviews_active`. When the cell is
    explicitly typed, the operator's per-row choice
    wins.
- **Rule Builder UI.** The `exclude_self_reviews` flag
  lives on `RuleSetRevision.exclude_self_reviews` and
  travels through the Rule Builder's edit / preview /
  save flow today as a hidden form value. Surface it as
  a labelled checkbox between the Rules + buttons row
  and the Save / Cancel row. The rules-JSON serializer
  (`_rule_based_editor_js.html`) already round-trips
  the flag; just need a visible control + matching
  adapter slot in `views/_rule_builder.py`. Copy:
  *"Exclude self-review pairs (reviewer reviews
  themselves)"* with a tooltip / hint line clarifying
  this only affects what gets **generated**.
- **Bulk Include toggle on the Assignments page.**
  - Renders just above the Assignments preview table
    in a small header row.
  - Visual: state pill + live counts + the toggle
    control. E.g.
    `Self-reviews: ON (3 active, 0 deactivated)
    [toggle]`. When the row-level data is mixed
    (toggle says ON but one row is individually OFF),
    the deactivated count surfaces it.
  - Hidden / disabled when no self-review rows exist
    in the assignments table — no behaviour to toggle.
  - Action POSTs to a new route — e.g.
    `POST /operator/sessions/{id}/assignments/self-reviews/active`
    with body `{"active": true|false}`. Single
    transaction: write `sessions.self_reviews_active`,
    then UPDATE every self-review row's `include` to
    match. Audit event
    `assignments.self_reviews_active_set` registered
    in `EVENT_SCHEMAS` per 11K's strict-mode gate;
    detail carries `counts.flipped` + the resulting
    boolean.
- **Drop ad-hoc toggles.**
  - Quick Setup slot 3 form-data field
    `exclude_self_review` (string flag) is read by
    `_quick_setup.py` and passed into
    `generate_full_matrix` / the rule-based engine.
    Drop the form field on the template + the
    handler-side fallback that defaults it on; rely
    entirely on the RuleSet's own flag.
  - Assignments page Rule Based card carries an
    `exclude_self_review` checkbox alongside the
    Generate button. Drop it; the Rule Builder is now
    the only edit surface for the flag.
- **Full-matrix cleanup.** Spike to confirm no live
  caller hits `POST /assignments/full-matrix` outside
  the Quick Setup legacy fallback. If clean, delete the
  route, the `assignments_full_matrix` handler, the
  `AssignmentMode.full_matrix` enum value, and the
  legacy `rule="full_matrix"` fallback in
  `_quick_setup.py`. `generate_full_matrix` itself stays
  (the seeded full-matrix RuleSet's engine evaluation
  ultimately produces the same Cartesian product, but
  via the rules engine).
- **Validation copy.** Find the validation-row template
  text (likely in `app/services/validation.py`'s message
  catalogue or a Jinja template under
  `templates/operator/`) and update the message string +
  any inline link / banner copy that says "exclude" to
  say something like "self-review pairs are present —
  use the bulk toggle on the Assignments page to
  deactivate if needed".

### Out of scope

- **Per-row Include UX changes.** The per-row Include
  checkboxes on the Assignments table stay exactly as
  they are today. Per-row flips don't write the
  session-level column; mixed states are supported.
- **Schema changes beyond the one new column.**
  `RuleSetRevision.exclude_self_reviews`,
  `Assignment.include`, and
  `count_self_reviews_in_assignments` all already
  exist.
- **Settings / manual-assignments CSV format.** The
  Settings CSV already exports
  `session_rule_sets[N].exclude_self_reviews`; the
  manual-assignments CSV already exports per-row
  `IncludeAssignment`. The new
  `sessions.self_reviews_active` column is **not**
  added to the Settings CSV — operator intent on a
  porting-target session lands at the default `TRUE`
  and the operator re-toggles if needed; this avoids
  carrying a UI-state preference across the porting
  boundary. Reconfirm on PR 1 review.
- **Validation predicate change.**
  `count_self_reviews_in_assignments` keeps counting
  every self-review row regardless of `include` value;
  the operator's mental model is "rows present in the
  table", not "rows currently active". The copy is
  what carries the new framing.
- **Self-review export column.** The Responses CSV's
  `SelfReview` column (12A-1 PR 4a) is a derived flag
  for analyst convenience — orthogonal to the
  generation / activation question this part answers.

### PR sequence (3 PRs, locked 2026-05-10)

Two PRs from the original 5-PR sketch are deferred and
folded into 15D under the 2026-05-10 codebase-check
revision: the bulk Include toggle (was PR 3) and the
ad-hoc-toggle drop on the Rule Based card (was PR 4).
Both surfaces relocate when 15D moves the Assignments
page from Setup to Operations, so building them on
today's Setup-page home only to relocate days later
isn't worth the churn. They land alongside the full
Operations Assignments page implementation in **15D
PR 6** (where the page is rebuilt anyway). The
remaining 3 PRs ship from 12C — independent of each
other and parallel-shippable.

1. **PR 1 — Generation-path wiring.** *Schema lifted to
   13E PR 1 under the 2026-05-10 holistic-sequence
   revision.* Wires `generate_full_matrix` and the
   rule-based engine to consult
   `sessions.self_reviews_active` when creating
   self-review rows (new self-review rows get
   `include = sessions.self_reviews_active`).
   *Manual-CSV save path skipped under the 2026-05-10
   codebase-check revision* — 15D removes the
   operator-facing manual upload entirely (route stays
   as a dev-only feature; dev test data doesn't need
   the self-review default applied). No UI yet — the
   column is universally `TRUE` on existing sessions,
   so behaviour is unchanged. Depends on 13E PR 1
   having shipped. Tests: each generation path picks
   up the column when it's `FALSE`; existing-session
   default behaviour preserved when it's `TRUE`.
2. **PR 2 — Rule Builder surfaces
   `exclude_self_reviews`.** Adds the labelled checkbox
   between the rule-list editor and the Save / Cancel
   row. View-shape adapter slot in
   `views/_rule_builder.py`; round-trip already
   plumbed. Tests: checkbox renders; toggling it
   round-trips through the save flow; the saved
   RuleSet revision carries the flag.
3. **PR 3 — Full-matrix dead-code cleanup.** *(was
   PR 5 in the original sketch; renumbered after the
   PR 3 + PR 4 deferrals.)* Removes the standalone
   `POST /assignments/full-matrix` route, the
   `assignments_full_matrix` handler, the
   `AssignmentMode.full_matrix` enum value, and the
   legacy `rule="full_matrix"` fallback in
   `_quick_setup.py`. `generate_full_matrix` stays
   (the seeded full-matrix RuleSet uses it via the
   rules engine). Tests: any test exercising the
   standalone route is migrated to the seeded
   full-matrix RuleSet path (mirrors how 11J's
   Quick Setup tests already use the dropdown);
   enum-value test gate flagged if a stray reference
   survives.

### Deferred PRs (folded into 15D PR 6)

The following two PRs were sketched as part of 12C-1
in the original plan but defer to 15D under the
2026-05-10 codebase-check revision. The **work itself
ships** — just lands on the Operations Assignments
page (15D's home for it) instead of today's Setup
Assignments page (which 15D restructures).

- **(Was PR 3) Bulk Include toggle.** Header row
  above the assignments preview table (toggle +
  state + counts); POSTs to
  `/assignments/self-reviews/active`; single
  transaction writes
  `sessions.self_reviews_active` + updates every
  self-review row's `include` to match. New
  `assignments.self_reviews_active_set` event in
  `EVENT_SCHEMAS` with `counts.flipped` + the
  resulting boolean. Folded into **15D PR 6** —
  the Operations Assignments page builds the
  toggle into its surface from the start, no
  Setup-page intermediate.
- **(Was PR 4) Drop ad-hoc toggle on Rule Based
  card + validation copy refresh.** Removes the
  `exclude_self_review` form field from the
  Assignments page Rule Based card; refreshes the
  `assignments.self_reviews_present` validation row
  message + any related banner copy to point at
  the new bulk toggle. Folded into **15D PR 6**
  alongside the chrome restructure (the Rule
  Based card itself relocates with the page).

---

## Part 2 — Quick Setup upload semantics (Sub-segment 12C-2 — DEFERRED 2026-05-10)

> **DEFERRED under the holistic-sequence revision
> 2026-05-10.** Under the locked sequence
> 13E → 12C → 15D → 12A-3, this sub-segment's work
> would land + be replaced within a single segment
> cycle (15D restructures Quick Setup anyway, and
> retires manual assignments entirely). Keeping the
> intermediate state isn't worth the churn. Where the
> three would-be PRs land instead:
>
> - **PR 1 (Quick Setup slot 3 retirement)** → folded
>   into 15D, which restructures the Quick Setup card
>   from 4 → 3 → 4 slots in one shot (slot 3 retires
>   AND comes back as Relationships in the same
>   segment).
> - **PR 2 (Settings importer wipes assignments
>   explicitly)** → folded into 12A-3 PR 1, which
>   builds the Settings importer in the first place
>   (this PR was always a tightening of 12A-2's
>   importer; with 12A-2 absorbed into 12A-3, the
>   tightening lives there too).
> - **PR 3 (Manual upload via Assignments page,
>   Option A)** → not shipped at all. 15D removes the
>   manual upload entirely; landing Option A in 12C
>   would be wasted work.
>
> The locked Decisions + Workflow consequences +
> Replace-not-merge contract + Manual-upload-Option-A
> spec below are kept as **historical reference** —
> they describe the contract 12A-3 PR 1 implements (for
> the wipe-assignments step) and the no-manual-upload
> world 15D ships into. The PR sequence at the bottom
> of this Part is what was previously planned to ship
> from 12C; under the new sequence, none of those
> three PRs ship from 12C.

### Decisions locked 2026-05-10

Three locks settle Part 2's scope:

1. **Manual assignments removed from Quick Setup
   entirely** (the previously "trending YES" drastic
   option). Slot 3 retires; manual assignments live
   exclusively on the Assignments page. The Quick Setup
   card slims from 4 slots to 3 (Reviewers, Reviewees,
   Settings). Subsumes the earlier slot-3-dropdown-only
   removal — the entire slot goes, dropdown and file
   upload alike.
2. **Quick Setup uploads = strict wipe-and-replace.**
   Every upload wipes its target tables and replaces
   with the uploaded content; no merge mode. Reviewers
   upload wipes the reviewers list; reviewees upload
   wipes the reviewees list; **Settings upload wipes
   instruments + assignments before re-creating from
   the Settings CSV.** The Settings → assignments wipe
   is explicit (assignments cascade-delete via FK from
   instruments today; the Settings importer's
   wipe-and-replace step covers it deliberately).
3. **Manual assignments CSV shape locked at Option A
   (session-wide wipe).** The CSV's `Instrument` column
   makes it per-instrument-aware on the **row** level,
   but the import is session-wide-wipe at the **file**
   level. For a multi-instrument session, the manual CSV
   must include rows for every instrument the operator
   wants populated; instruments not represented in the
   CSV end up with no assignments. Acceptable trade-off
   since manual is being discouraged in favour of
   rule-based per-instrument.

These three locks together collapse the previously open
slot-3 × slot-4 conflict matrix entirely. Slot 3 is gone,
so cross-slot disagreement at upload time can't happen.
The only remaining question — manual upload via the
Assignments page colliding with an existing
per-instrument `rule_set_id` — moves to the Assignments
page itself, where it's a one-surface decision.

### Workflow consequences

**Rule-based-first default.** Operators set up sessions
with rosters + Settings (incl. per-instrument
`rule_set_name` references); generation kicks off
automatically via 12A-2 PR 1's chain step. Operators who
want rule-based without writing a Settings CSV go to the
Assignments page Rule Based card after session creation
(today's path). Either way, the workflow centres on the
RuleSet model.

**Manual = post-creation override.** Operators who need
manual assignments — small cohorts, hand-curated pairings,
imports from external tools — go to the Assignments page
after session creation and upload a manual CSV. The CSV
covers every instrument they want populated.

**Round-trip with 12A-1 / 12A-2.** An operator porting a
session uses Quick Setup for rosters + Settings (which
includes per-instrument `rule_set_name`). If the source
session was rule-based per-instrument, the destination
session regenerates assignments from the same RuleSets
on Generate. If the source had any manual instruments,
the operator uploads the manual assignments CSV via the
Assignments page after Quick Setup completes. Quick
Setup is no longer the canonical round-trip surface for
manual assignments; the per-entity importer on the
Assignments page is.

### Replace-not-merge contract (locked)

| Slot | Upload | Replaces (incl. cascades) |
|---|---|---|
| 1 | Reviewers CSV | All `reviewers` rows on the session. Cascade: any `Assignment` rows referencing wiped reviewers are also removed (FK). |
| 2 | Reviewees CSV | All `reviewees` rows on the session. Cascade: any `Assignment` rows referencing wiped reviewees are also removed (FK). |
| 3 | Settings CSV (12A-2 target — was slot 4 before the slot-3 retirement) | All instruments + display fields + response fields + per-session RTDs + per-session RuleSets + field-label overrides + email-template overrides. **Explicit cascade:** the importer wipes the assignments table before replacing instruments, so any `Assignment` rows tied to about-to-be-deleted instruments are gone before the FK cascade would fire. Round-trip clean. |

The chain order in `quick_setup_submit_all` becomes:
reviewers → reviewees → settings (was: reviewers →
reviewees → assignments). Generation no longer fires
during Quick Setup at all; if the Settings CSV's
per-instrument `rule_set_name` references are present,
12A-2 PR 1's chain consults them and runs Generate as
part of the Settings apply (or surfaces a "ready to
Generate" cue on Session Home so the operator clicks
once). If neither, Session Home's
`assignments.no_mode` validation row warns until the
operator either runs Generate or uploads manual
assignments.

### Manual upload via the Assignments page (Option A — locked)

The Assignments page is the only place a manual CSV is
uploaded. Shape:

- **Required columns** (matches 12A-1 PR 3 export):
  `ReviewerEmail`, `RevieweeEmail`, `IncludeAssignment`,
  `Instrument`. The `Instrument` column is required even
  on single-instrument sessions, for symmetry with the
  multi-instrument case and round-trip with the export.
- **Wipe scope:** session-wide. Upload wipes every
  `Assignment` row on the session, then writes the CSV's
  rows.
- **Coverage requirement:** in a multi-instrument session,
  the operator must include rows for every instrument
  they want populated. Instruments not represented in the
  CSV end up with zero assignments (and surface in the
  validation report as "no assignments for Instrument
  #N"). The importer doesn't block uploads with omitted
  instruments — operators may legitimately want some
  instruments empty — but the validation row makes the
  state visible.
- **Per-instrument mode flip:** when the manual CSV
  covers an instrument whose `Instrument.rule_set_id`
  is currently set (post-15B), the upload flips that
  instrument to manual mode for the assignment rows
  themselves but **preserves** `rule_set_id` as
  metadata so a future Generate re-run on that
  instrument can swap back to rule-based. Banner-warning
  on the Assignments page during the upload submit
  confirms the flip ("uploading manual rows for
  Instrument #1 will override its current
  `rule_set_name='Cross-cohort fanout'` selection;
  Generate on Instrument #1 to switch back").

The discouragement of manual assignments is intentional:
operators *can* manage manual assignments per-instrument
through the Assignments page, but rule-based via the
Settings CSV is the scale-friendly path and the default
for new sessions.

### Validation impact

Today's `assignments.no_mode` warning fires when no
`assignment_mode` is set. In the per-instrument world,
the predicate shifts to "any instrument has zero
assignments". **No new validation row needed** — the
existing row's predicate generalises naturally to the
per-instrument question. `assignment_mode` itself is a
session-level field today; 15B's per-instrument
direction makes it derived / retired — that retirement
is out of scope here.

### PR sequence (3 PRs, locked 2026-05-10)

Coordinates with 12A-2 PR 1 (Settings CSV importer);
PR 1 below depends on 12A-2 PR 1 having shipped.

1. **PR 1 — Retire Quick Setup slot 3.** Removes the
   manual CSV upload field, the RuleSet dropdown, the
   slot-3 handler-side branch in `_quick_setup.py`
   (incl. legacy `rule="full_matrix"` /
   `rule="rule_based"` payload variants), the
   `session_rule_set_id` form-data field, and the
   matching view-shape adapter slot in
   `views/_quick_setup.py`. Renumbers Settings to
   slot 3. The `quick_setup_submit_all` chain drops
   the assignments dispatch step; chain ends after
   Settings apply. Tests: Quick Setup card renders 3
   slots in both Create New Session + Session Home
   contexts; submit-all chain runs reviewers →
   reviewees → settings without the assignments
   step; existing tests that uploaded manual CSV via
   slot 3 are migrated to upload via the Assignments
   page after Quick Setup completes.
   *15D note: 15D re-introduces a slot 3 with
   different content (Relationships, not Assignments)
   — Quick Setup goes 4 → 3 → 4 across this segment
   and 15D. The interim 3-slot state is intentional;
   the slot frame is not preserved for re-use.*
2. **PR 2 — Settings importer wipes assignments
   explicitly.** 12A-2 PR 1 wires the Settings
   importer's wipe-and-replace; this PR adds the
   explicit assignments-table wipe step before the
   instruments wipe so the cascade ordering is
   deterministic and the operator's mental model
   ("Settings upload wipes instruments + assignments")
   matches the implementation. Tests: round-trip
   integration test (assignments wipe is observable
   via audit count on the Settings importer).
3. **PR 3 — Assignments-page manual upload: lock
   Option A + per-instrument mode-flip cue.** Pins
   the importer at Option A (session-wide wipe; cover
   all instruments); ensures the `Instrument` column
   is required; surfaces the banner-warning when the
   upload covers an instrument with a non-NULL
   `rule_set_id`. Tests: upload covers all
   instruments → all populated; upload omits an
   instrument → that instrument has zero assignments;
   upload covering an instrument with `rule_set_id`
   set surfaces the banner-warning + preserves
   `rule_set_id` post-upload.
   *15D note: 15D removes the manual upload entirely
   (Assignments table becomes always-derived; manual
   row authoring retires in favour of the
   Relationships table). This PR ships the cleaner
   intermediate behaviour — operators get
   wipe-and-replace + clear coverage semantics
   between 12C ship and 15D ship.*

---

## Part 3 — Chrome reorder: Instruments before Assignments (Sub-segment 12C-3 — DEFERRED 2026-05-10)

> **DEFERRED under the holistic-sequence revision
> 2026-05-10.** 15D moves Assignments off the Setup
> row entirely (it becomes an Operations-row tab), so
> the Setup-row Instruments-before-Assignments swap is
> moot post-15D. The status pills + Setup card row-list
> reorders also fold into 15D's broader restructure.
>
> The locked decision + targeted moves below are kept
> as historical reference — they describe the chrome
> shape that 15D rebuilds anyway. Under the new
> sequence, no PR ships from this Part.

### Decision locked 2026-05-10

In the chrome's Setup row, swap **Instruments** ahead of
**Assignments**. Apply the same swap to the chrome status
pills row and the Session Home Setup card so all three
"what's left to set up?" surfaces read in the same order.

**Why.** Instruments define *what* the operator asks
reviewers about; assignments define *who* reviews *whom*
per instrument. Instruments are conceptually upstream — the
operator typically builds the question schema before
deciding who answers it. The chrome ordering should match
that workflow.

### Targeted moves (locked 2026-05-10)

1. **Chrome nav (Setup tab strip).** Swap the two `<a
   class="nav-tab">` blocks in
   `app/web/templates/operator/partials/session_top_nav.html`
   so the Setup row reads:
   `Reviewers · Reviewees · Instruments · Assignments ·
   Email Template`. The `_setup_pages` list at the top of
   the partial keeps the same five entries; only the
   render order changes.
2. **Chrome status pills row.** Swap the
   `Assignments` + `Instruments` pill blocks in
   `app/web/templates/operator/partials/session_setup_status_row.html`
   (the Assignments block at lines 30-38 carries the
   `assignment_mode` annex; preserve it intact when
   moving). The underlying `SessionStatusPills` dataclass
   in `app/web/views/_setup.py` stays as-is — fields are
   accessed by attribute, not by position.
3. **Session Home Setup card.** Swap the `SetupRow(label="Assignments", …)`
   and `SetupRow(label="Instruments", …)` entries in
   `build_setup_rows`
   (`app/web/views/_setup.py:78-87`). The chrome change
   only feels consistent if this card flips too, since
   the operator sees both surfaces at once on Home.

The Operations row tabs (Validate / Previews / Invitations
/ Responses) and the Operations-row pills (Invitations /
Responses placeholders) are not in scope for this swap —
their order tracks the lifecycle, not the setup workflow.

### Implementation pointers

- Single small PR. Three template / view-shape edits +
  any test reorder. No schema; no new audit events; no
  copy changes (labels themselves stay).
- **Test impact.** Anywhere a test asserts the pre-flip
  order needs the matching reorder. Spot-check before
  sizing — likely a handful of integration tests under
  `tests/integration/` (e.g. tests that scan the chrome
  HTML for tab strings, or that assert
  `build_setup_rows` returns rows in a specific order).
  No unit-level pin on `SessionStatusPills` field order
  expected; if one exists, update it too.
- **Spec doc touch-ups.** Sweep
  `spec/operator_ui_concept.md` for any "Reviewers /
  Reviewees / Assignments / Instruments / Email
  Template" enumeration; flip to the new order so the
  spec stays the source of truth. Same sweep on
  `spec/setup_pages.md` and any segment doc that
  enumerates the Setup tabs (`spec/session_home.md`?).
- **No reflow / spacing concerns.** The two tabs are
  sibling links inside `.tab-strip-setup`; swapping
  them doesn't change the strip's width or layout
  behaviour.

### Out of scope

- **Reordering the Operations row tabs or pills.** The
  Operations row tracks lifecycle ordering
  (`Validate → Previews → Invitations → Responses`)
  and stays as-is.
- **Reordering Quick Setup card slots.** Slot 3
  (Assignments) follows slots 1 + 2 (Reviewers /
  Reviewees) per the existing card spec; instruments
  aren't a Quick Setup slot today, so there's nothing
  to move.
- **Renaming the tabs / labels.** Labels stay as-is;
  only the order changes.
- **Page-body content.** No changes to the Instruments
  page or Assignments page bodies — they keep their
  existing surfaces.

### PR sequence

> **Single PR.**
>
> 1. Swap Instruments ahead of Assignments in the chrome
>    nav partial, the chrome status pills partial, and
>    the Session Home Setup card's row list. Update
>    affected tests + spec-doc enumerations in the same
>    PR (small, scoped).

*15D note: 15D moves Assignments off the Setup row
entirely (becomes an Operations-row tab). The Setup-row
swap landed here is an interim improvement; post-15D the
Setup row will read `Reviewers · Reviewees ·
Relationships · Instruments · Email Template` (one tab
fewer) and the Operations row picks up the Assignments
tab. The Session Home Setup card row list is
restructured by 15D as part of the Setup-vs-Operations
split.*

---

## Related context (cross-cutting)

- 12A-1 PR 4a (#725, 2026-05-09) added the derived
  `SelfReview` column to the responses CSV. The canonical
  predicate lives in
  `is_self_review(reviewer, reviewee)`
  (`app/services/assignments.py`) — case-insensitive
  `reviewer.email` vs `reviewee.email_or_identifier`,
  `FALSE` for non-email reviewee identifiers.
- Existing self-review handling on assignment generation:
  `generate_full_matrix(..., exclude_self_review)` and
  the `exclude_self_review` toggle on the Assignments page;
  rule-based engine equivalent in
  `app/services/rules/engine.py` (separate
  `_is_self_review` helper, intentionally module-private).
- Counting helpers: `count_self_review_candidates`,
  `count_self_reviews_in_assignments` in
  `app/services/assignments.py`.
- Full-matrix code surfaces today (candidates for
  cleanup): `generate_full_matrix` in
  `app/services/assignments.py:440`;
  `POST /sessions/{id}/assignments/full-matrix` route
  in `app/web/routes_operator/_assignments.py:134-170`;
  `AssignmentMode.full_matrix` enum value; legacy
  `rule="full_matrix"` payload fallback in
  `app/web/routes_operator/_quick_setup.py:573-586`.
- 12A-2's wipe-and-replace import contract — single
  source of truth for slot 4 semantics; see
  `guide/segment_12A-2_import.md` "Idempotency model" +
  "Import flows".
- Quick Setup chain ordering — `quick_setup_submit_all`
  in `app/web/routes_operator/_quick_setup.py` already
  dispatches reviewers → reviewees → assignments per-slot;
  Part 2 settles the cross-slot conflict layer above
  that dispatch.
- Schema-only-PR precedents — 13A-2 (#711, single
  uniqueness constraint) and 13D PR 5 / PR 6 (additive
  nullable columns with `server_default`) both mirror
  the shape Part 1 PR 1 lands.
- **Segment 15D — Assignments revamp**
  (`guide/segment_15D_assignments_revamp.md`). Replaces
  today's Setup Assignments page with an Operations
  Assignments page; introduces a new Relationships
  table; assignments table becomes always derived;
  manual assignment-row authoring retires entirely.
  See "Forward-looking — 15D alignment" at the top of
  this doc for the per-PR map of what 15D inherits
  unchanged vs. what's transient.

## Open questions

### Part 1 (Sub-segment 12C-1)

_None — audit-event-name question settled 2026-05-10:
**compact form** locked. PR 3 ships
`assignments.self_reviews_active_set` with detail shape
`_IDENTITY | {"counts"}`, carrying the resulting boolean
+ `counts.flipped`. The activated / deactivated split was
considered and rejected — single event keeps
`EVENT_SCHEMAS` registration noise low and the audit log
reads cleanly with the boolean in detail._

### Part 2 (Sub-segment 12C-2)

_None — all Part 2 questions settled 2026-05-10:_

- _Drastic option locked: manual assignments removed
  from Quick Setup entirely._
- _Manual-CSV shape locked at Option A (session-wide
  wipe; operator covers all instruments). Options B / C /
  D considered and rejected — A's coverage requirement
  is the simplest model and is acceptable because manual
  is being discouraged in favour of rule-based
  per-instrument._
- _Per-instrument mode-flip on manual upload: surfaces
  as a banner-warning during the Assignments-page
  submit confirmation (preserves `rule_set_id` as
  metadata; doesn't reject the upload). Settles the
  "reject vs warn" question — warn._
