# Segment 12C — Self-review revamp + Quick Setup upload semantics + chrome reorder

**Status:** Planning. **Sub-segment 12C-1 (Part 1) — sized
2026-05-09; ready to start; audit-event-name question
settled 2026-05-10 (compact form).** Sub-segment 12C-2
(Part 2) — slot-3 dropdown removal locked 2026-05-10;
**trending toward a more drastic simplification (remove
manual assignments from Quick Setup entirely; rule-based
becomes the default, manual is a post-creation override on
the Assignments page)** — pros / cons captured 2026-05-10.
Manual-CSV shape in a per-instrument world (Options A / B
/ C / D) still open. **Sub-segment 12C-3 (Part 3) —
locked 2026-05-10; ready to start.**

This doc covers **three related concerns** that all touch
the Assignments / Instruments cluster of the operator chrome:

- **Part 1 — Two-layer self-review model (Sub-segment
  12C-1).** Replace today's scattered ad-hoc
  `exclude_self_review` toggles with a clean
  RuleSet-as-generator + Include-as-activator split.
- **Part 2 — Quick Setup upload semantics (Sub-segment
  12C-2 — TBD).** Pin the wipe-and-replace contract for
  every Quick Setup slot, and resolve the priority order
  between slot 3 (assignments) and slot 4 (settings) when
  they disagree on RuleSet selection.
- **Part 3 — Chrome reorder: Instruments before
  Assignments (Sub-segment 12C-3).** Small UI move —
  swap the Instruments and Assignments tabs in the
  chrome's Setup nav row, and apply the same swap to the
  status pills + the Session Home Setup card so the
  "what's still left to set up?" reading order matches.

The two parts share the same surfaces but answer different
questions; expect them to land as separate PR sequences.

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

### PR sequence (5 PRs, locked 2026-05-09)

PRs 2 + 3 are independent of each other and of PR 1's
generation-path wiring (each touches a different surface);
parallel-shippable. PR 4 depends on PRs 1 + 2 + 3 shipping
(the new edit surfaces have to exist before the old ones
can be removed). PR 5 is independent dead-code cleanup.

1. **PR 1 — Schema + generation-path wiring.** Alembic
   migration adds `sessions.self_reviews_active BOOLEAN
   NOT NULL DEFAULT TRUE`. Wires `generate_full_matrix`,
   the rule-based engine, and the manual-CSV save path
   to consult the column when creating self-review rows
   (new self-review rows get `include = sessions.self_reviews_active`).
   No UI yet — the column is universally `TRUE` on
   existing sessions, so behaviour is unchanged. Tests:
   migration round-trips; each generation path picks up
   the column when it's `FALSE`; existing-session
   default is `TRUE`.
2. **PR 2 — Rule Builder surfaces
   `exclude_self_reviews`.** Adds the labelled checkbox
   between the rule-list editor and the Save / Cancel
   row. View-shape adapter slot in
   `views/_rule_builder.py`; round-trip already
   plumbed. Tests: checkbox renders; toggling it
   round-trips through the save flow; the saved
   RuleSet revision carries the flag.
3. **PR 3 — Bulk Include toggle on the Assignments
   page** + new route + audit event. Renders the
   header row above the preview table (toggle + state
   + counts); POSTs to
   `/assignments/self-reviews/active`; single
   transaction writes the column + updates every
   self-review row's `include` to match. New
   `assignments.self_reviews_active_set` event in
   `EVENT_SCHEMAS`. Tests: route auth; transition both
   directions; mixed-state row count surfaces in the
   header; audit emission with `counts.flipped` +
   resulting boolean.
4. **PR 4 — Drop ad-hoc toggles + validation copy
   refresh.** Removes the `exclude_self_review` form
   field from Quick Setup slot 3 (template +
   handler-side fallback) and from the Assignments
   page Rule Based card. Refreshes the
   `assignments.self_reviews_present` validation row
   message + any related banner copy to point at the
   new bulk toggle. Tests: previously-failing form-field
   assertions are deleted; validation row still fires +
   reads cleanly; integration smoke that the
   end-to-end Quick Setup chain still works.
5. **PR 5 — Full-matrix dead-code cleanup.** Removes
   the standalone
   `POST /assignments/full-matrix` route, the
   `assignments_full_matrix` handler, the
   `AssignmentMode.full_matrix` enum value, and the
   legacy `rule="full_matrix"` fallback in
   `_quick_setup.py`. `generate_full_matrix` stays.
   Tests: any test exercising the standalone route is
   migrated to the seeded full-matrix RuleSet path
   (mirrors how 11J's Quick Setup tests already use
   the dropdown); enum-value test gate flagged if a
   stray reference survives.

---

## Part 2 — Quick Setup upload semantics (Sub-segment 12C-2)

### Trending toward (2026-05-10): remove manual assignments from Quick Setup entirely

Beyond the slot-3-dropdown removal locked below, consider a
more **drastic** simplification — remove the slot-3 manual
CSV upload from Quick Setup too. Quick Setup's Assignments
slot goes away entirely; manual assignments live exclusively
on the Assignments page (today's Manage path).

**Direction.** Operators should assign by rules in the
default flow — it's the correct approach for larger sets of
reviewers and reviewees, and the per-instrument 15B model
already centres on RuleSets. Manual is then a *special
override* surfaced on the Assignments page, not a peer of
rule-based on the Quick Setup card.

**Pros:**

- Quick Setup card slims from 4 slots to 3 (Reviewers,
  Reviewees, Settings). One fewer decision at
  session-creation time.
- The slot-3 × slot-4 conflict matrix disappears
  entirely — no manual CSV in Quick Setup means no
  conflict between manual rows and the Settings CSV's
  per-instrument `rule_set_name` references. The
  resolver / banner-warning machinery sketched in
  Part 2's PR sequence isn't needed.
- The manual-CSV shape question (Options A / B / C / D
  below) moves off the Quick Setup chain entirely. The
  Assignments page becomes the only place a manual CSV
  is uploaded; its scope semantics still need pinning,
  but the answer is scoped to one upload path with no
  Settings-CSV cross-reference.
- Encourages the right pattern. Rule-based is the
  scale-friendly default; manual becomes a deliberate
  post-creation override rather than a same-card
  shortcut.
- Symmetric with the rule-based path under the
  dropdown-removal lock — rule-based without a Settings
  CSV already requires post-creation Generate on the
  Assignments page; manual now joins the same
  "post-creation decision" surface.
- Settings CSV (slot 4) becomes the only
  assignment-related Quick Setup input. Per-instrument
  `rule_set_name` references travel via Settings CSV;
  one source of truth.

**Cons:**

- Operator with a pre-built manual CSV (e.g. exported
  from another tool, or hand-curated for a small
  cohort) loses the one-click "create + populate"
  workflow. The new flow is two clicks: Create New
  Session → Quick Setup → click Create; then go to
  Assignments page → upload manual CSV.
- Partial round-trip break with 12A-1 / 12A-2. An
  operator who exported settings + manual assignments
  from session A can't re-upload both via Quick Setup
  on session B. Must Quick Setup the settings, then
  separately upload manual assignments via the
  Assignments page. *Counter:* 12A-1's per-entity files
  already round-trip with the existing per-entity
  import flows — Manage pages for rosters; Assignments
  page for manual. Quick Setup's manual slot was a
  convenience-bundling, not the canonical round-trip
  surface.
- Slightly more friction for very small sessions where
  rule-based feels overkill (e.g. "10 students, each
  reviews 3 others I picked manually"). The two-step
  workflow is acceptable — small cohorts aren't the
  optimisation target.

**Recommendation: trending YES.** The simplifications are
material (Part 2 collapses to a single Quick-Setup move +
a much narrower CSV-shape decision); the cons are
minor-friction trade-offs the operator can accept.

**If the drastic option lands**, Part 2's PR sequence
collapses to:

1. **Remove the slot-3 dropdown *and* the slot-3 manual
   CSV upload** from Quick Setup. Quick Setup card slims
   to 3 slots (Reviewers, Reviewees, Settings). The
   `quick_setup_submit_all` chain drops the assignments
   dispatch step (slot 3 retires); chain ends after
   slot 4's Settings CSV apply, so generation kicks off
   via the Settings CSV's per-instrument
   `rule_set_name` references (post-12A-2 PR 1) or via
   the operator's post-creation Generate / manual
   upload on the Assignments page.
2. **Pin the Assignments-page manual upload's scope
   semantics** (Options A / B / C / D below — the
   question is now scoped to one upload path, no
   cross-reference). Option D's Settings-CSV
   `instruments[N].mode` column may no longer be
   necessary if the conflict is resolved per-page
   rather than cross-slot; reconsider on resolution.
3. **UX cue on the Assignments page** when an operator
   uploads a manual CSV that covers an instrument
   whose `rule_set_id` is already set — banner-warning
   that flipping the instrument to manual mode will
   override the RuleSet selection. (Replaces the
   slot-3 × slot-4 cue from the original sketch.)

If the drastic option is rejected, Part 2 keeps the
existing slot-3-dropdown-only removal and the conflict
matrix below.

### Decision locked 2026-05-09: remove the RuleSet dropdown from Quick Setup slot 3

Slot 3 today supports two modes — a manual assignments file
upload **or** a session-level RuleSet pick from a dropdown.
**Drop the dropdown.** Slot 3 becomes manual-CSV-only.

**Why.** The dropdown picks one RuleSet for the whole
session. This worked when `assignment_mode` was session-level
(every instrument used the same generation path). In the 15B
direction, RuleSet selection becomes per-instrument
(`Instrument.rule_set_id`); a session-level dropdown can't
cleanly express that. The Settings CSV (slot 4) already
carries per-instrument `rule_set_name` references, so
dropping the dropdown leaves a single, per-instrument-scoped
path for encoding rule-based selection.

**Workflow consequence.** Operators who want rule-based
assignments via Quick Setup encode it in the Settings CSV
(slot 4). Operators who want a quick rule-based run without
writing a Settings CSV go to the Assignments page Rule Based
card after session creation (today's path). The dropdown's
"set up + assign in one click" shortcut retires; mixed-mode
sessions (some instruments manual, some rule-based) become
expressible in a single Quick Setup submission via the
manual CSV (slot 3) + per-instrument `rule_set_name` rows
(slot 4).

**Removal scope:** the dropdown UI on the Quick Setup card
template, the slot-3 handler-side dropdown branch in
`_quick_setup.py` (incl. the legacy `rule="full_matrix"` /
`rule="rule_based"` payload variants), the
`session_rule_set_id` form-data field, and the matching
view-shape adapter slot in `views/_quick_setup.py`. The
`generate_full_matrix` / rule-based engine entrypoints stay
— the Assignments page still calls them.

This is the **first move in Part 2.**

### Open question — shape of the manual assignments CSV in a per-instrument world

Once the dropdown is gone, slot 3 is the only manual path
and slot 4 is the only RuleSet path — both per-instrument-aware
in the 15B model. The remaining shape question: when an
operator uploads a manual CSV that covers only some
instruments, what happens to existing assignments for the
other instruments?

The CSV's column shape is already per-instrument-aware (12A-1
PR 3 export — `ReviewerEmail,RevieweeEmail,IncludeAssignment,Instrument`).
The unsettled question is the **import-time scope**.

| Option | Wipe scope | Pros | Cons |
|---|---|---|---|
| **A — Session-wide wipe** (today's shape, formalized) | Wipes all `Assignment` rows on the session, then writes the CSV's rows. Instruments not named in the CSV end up with zero rows. | Predictable; matches the wipe-and-replace contract for slots 1 + 2. | Surprising in mixed-mode setups — uploading manual rows for Instrument #1 silently empties Instruments #2 + #3, even if the operator intended to leave them on their RuleSets. |
| **B — Per-instrument-scoped wipe** | Wipes only those instruments named in the CSV's `Instrument` column. Instruments not named are left untouched. | Cleanest per-instrument model. Operator can update one instrument's assignments without affecting others. | "Wipe" semantics are now scoped — more subtle than slots 1/2's session-wide wipe. Documentation has to spell it out. |
| **C — Session-wide wipe with explicit scope directive** | Header-row metadata declares the CSV's scope. E.g. `# scope: session` (wipe all) vs `# scope: instruments=1,2` (wipe only those). | Explicit; the operator's intent is in the file. | Adds CSV-format complexity. No precedent in the other CSVs. |
| **D — Two-pass with per-instrument mode in Settings CSV** | Add `instruments[N].mode` (`manual` / `rule_based`) to the Settings CSV; manual CSV is per-instrument-scoped (Option B); on Quick Setup the importer cross-references the two — manual CSV must only cover instruments whose Settings-CSV mode is `manual`, otherwise raise a conflict. | Fully explicit per-instrument model; mixed mode coexists cleanly in one Quick Setup submission. | Requires a Settings-CSV format addition (12A-1 / 12A-2 coordination); requires an extra Settings-CSV column (`instruments[N].mode`). |

**Recommendation pending.** Option B is the smallest move
and preserves the current CSV format; Option D is the
long-term clean answer but requires Settings-CSV additions.
Option A is what we have today; Option C is a hybrid that
shifts complexity into the file.

Settle this before the Part 2 PR sequence is sized — the
chosen shape drives:

- Slot 3 importer's scope behaviour.
- Slot 3 vs slot 4 conflict resolution (when the manual CSV
  covers an instrument that the Settings CSV also points
  at via `rule_set_name`).
- Whether the Settings CSV gets a new
  `instruments[N].mode` column (Option D only) — would
  coordinate with 12A-1's export shape and 12A-2's import
  side.

### Replace-not-merge contract (post-dropdown-removal)

Quick Setup is the all-at-once retemplating surface. **Every
slot is wipe-and-replace**: an upload replaces whatever was
previously in that slot's table. There is no "merge with
existing" mode. Operators who want partial updates use the
Manage pages instead.

| Slot | Upload | Replaces |
|---|---|---|
| 1 | Reviewers CSV | All `reviewers` rows on the session |
| 2 | Reviewees CSV | All `reviewees` rows on the session |
| 3 | Manual assignments CSV (file only — dropdown retired) | All `assignments` rows on the session — **scope TBD pending the open shape question above (Option A vs B vs C vs D)** |
| 4 | Settings CSV (12A-2 target) | All instruments + display fields + response fields + per-session RTDs + per-session RuleSets + field-label overrides + email-template overrides |

This already matches today's behaviour for slots 1-2 (11J's
Quick Setup chain wipes-and-replaces) and the 12A-2 plan for
slot 4 (the importer is wipe-and-replace for everything it
owns; see "Idempotency model" in
`guide/segment_12A-2_import.md`). Slot 3's exact scope
follows from the open question.

### Conflict resolution — slot 3 vs slot 4 (deferred)

Pending the manual-CSV-shape decision above. The original
"Option A vs Option B priority order between slot-3
dropdown vs slot 4" question is **superseded** by the
per-instrument framing — the slot-3 dropdown is gone, and
per-instrument disagreement is the only remaining conflict
shape:

> *"Manual CSV (slot 3) has rows for Instrument #1.
> Settings CSV (slot 4) says
> `instruments[1].rule_set_name = 'Cross-cohort fanout'`.
> Which wins?"*

The shape decision drives the answer:

- **Option B / D** — manual CSV wins for any instrument it
  names (more specific). Settings CSV's `rule_set_name`
  for that instrument is preserved as metadata so a
  future Generate re-run could use it (post-15B's
  per-instrument FK). Other instruments stay on the
  Settings CSV's `rule_set_name` selection.
- **Option A** — manual CSV is session-wide-wipe; Settings
  CSV's per-instrument `rule_set_name` references are
  written into `instruments.rule_set_id` for future
  Generate, but the assignment rows themselves come from
  slot 3 only. Operator who wants to mix manual +
  rule-based in one Quick Setup submission can't — they
  pick one or use the Assignments page after.
- **Option C** — same as A or B depending on the header
  directive.

### Validation impact

Whichever shape wins, the validation rule needs to agree.
Today's `assignments.no_mode` warning fires when no
`assignment_mode` is set; in the per-instrument world,
the predicate likely shifts to "no assignments rows
present across any instrument" or similar. **No new
validation row needed** — confirm the rule reads against
the resolved state once the shape lands. (Note:
`assignment_mode` itself is a session-level field today;
15B's per-instrument direction makes it derived /
retired; that retirement is out of scope here.)

### PR sequence (Part 2 — TBD)

> Likely shape, pending the manual-CSV-shape decision:
>
> 1. **Remove the RuleSet dropdown from Quick Setup slot
>    3** (the locked decision above). Pure UI removal +
>    handler-side cleanup; no schema changes; mode-aware
>    payload variants retired. Tests: dropdown
>    disappears from both Create New Session + Session
>    Home contexts; existing manual-CSV upload path
>    still works; rule-based assignments now require
>    either Settings CSV (slot 4) or post-creation
>    Generate.
> 2. **Pin the manual-CSV shape** (Option A / B / C / D
>    — TBD). Migrates the slot 3 importer to the chosen
>    scope semantics; if Option D, coordinates with
>    12A-1 / 12A-2 to add `instruments[N].mode` to the
>    Settings CSV.
> 3. **Wire the slot 4 importer to the resolved
>    contract.** Coordinates with 12A-2 PR 1 — the
>    importer's apply step consults the resolver when
>    slot 3 + slot 4 disagree on a per-instrument basis.
> 4. **UX cue on conflict.** When the operator's slot 3
>    + slot 4 inputs disagree, surface a banner-warning
>    during the Quick Setup submit confirmation that
>    names the resolution ("manual rows for Instrument
>    #1 will override its `rule_set_name` reference").
>    Same pattern as 11J's slot-scoped warnings.

---

## Part 3 — Chrome reorder: Instruments before Assignments (Sub-segment 12C-3)

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

- **Lock or reject the drastic option** — remove manual
  assignments from Quick Setup entirely (see "Trending
  toward" at the top of Part 2). Recommendation:
  **trending YES**. If accepted, the conflict matrix
  collapses and the manual-CSV-shape question (next
  item) is scoped to a single upload path. If
  rejected, Part 2 keeps the slot-3-dropdown-only
  removal + the conflict matrix.
- **Manual assignments CSV shape in a per-instrument
  world** — Option A (session-wide wipe), B
  (per-instrument-scoped wipe), C (explicit scope
  directive in the file), or D (per-instrument mode in
  the Settings CSV). Settle before the Part 2 PR
  sequence is sized; the answer drives the slot 3
  importer (or the Assignments-page importer if the
  drastic option lands), and — if Option D survives —
  whether the Settings CSV gets a new
  `instruments[N].mode` column. Note: if the drastic
  option lands, Option D's cross-slot rationale is
  weakened; reconsider then.
- Should a manual-CSV upload that conflicts with an
  existing per-instrument `rule_set_id` be **rejected
  at upload time** with an error banner ("manual rows
  for Instrument #1 conflict with its `rule_set_name`
  reference — pick one") rather than resolved silently
  with a warning? Trades operator friction against
  silent surprise; depends on how often the conflict
  naturally arises in practice. Applies whether the
  upload lives on Quick Setup slot 3 or on the
  Assignments page — the question is which side wins,
  not which slot the file came in through.
