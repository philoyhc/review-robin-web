# Segment 12C — Self-review revamp + Quick Setup upload semantics

**Status:** Planning. **Sub-segment 12C-1 (Part 1) — sized
2026-05-09; ready to start.** Sub-segment 12C-2 (Part 2)
remains open — priority order between overlapping Quick Setup
slots still TBD.

This doc covers **two related-but-distinct concerns** that
both touch the Assignments slot of Quick Setup:

- **Part 1 — Two-layer self-review model (Sub-segment
  12C-1).** Replace today's scattered ad-hoc
  `exclude_self_review` toggles with a clean
  RuleSet-as-generator + Include-as-activator split.
- **Part 2 — Quick Setup upload semantics (Sub-segment
  12C-2 — TBD).** Pin the wipe-and-replace contract for
  every Quick Setup slot, and resolve the priority order
  between slot 3 (assignments) and slot 4 (settings) when
  they disagree on RuleSet selection.

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

## Part 2 — Quick Setup upload semantics (Sub-segment 12C-2 — TBD)

### Replace-not-merge contract

Quick Setup is the all-at-once retemplating surface. **Every
slot is wipe-and-replace**: an upload replaces whatever was
previously in that slot's table. There is no "merge with
existing" mode. Operators who want partial updates use the
Manage pages instead.

| Slot | Upload | Replaces |
|---|---|---|
| 1 | Reviewers CSV | All `reviewers` rows on the session |
| 2 | Reviewees CSV | All `reviewees` rows on the session |
| 3 | Manual assignments CSV **or** RuleSet from the dropdown | All `assignments` rows on the session (manual CSV writes the new rows verbatim; RuleSet selection regenerates against the just-saved roster) |
| 4 | Settings CSV (12A-2 target) | All instruments + display fields + response fields + per-session RTDs + per-session RuleSets + field-label overrides + email-template overrides |

This already matches today's behaviour for slots 1-3 (11J's
Quick Setup chain wipes-and-replaces) and the 12A-2 plan for
slot 4 (the importer is wipe-and-replace for everything it
owns; see "Idempotency model" in
`guide/segment_12A-2_import.md`). Part 2's job is to write
the contract down explicitly so the next ambiguity that
crops up has a single authoritative answer.

### Conflict matrix — slot 3 vs slot 4

Slot 4 (Settings CSV) carries per-instrument
`rule_set_name` references and per-session
`session_rule_sets[N]` definitions; slot 3 (Assignments)
carries either an explicit assignment-row file or a single
session-level RuleSet pick from the dropdown. The two slots
can disagree about which RuleSet powers a given
instrument's rule-based generation, or about whether the
assignment table should be populated from a manual CSV
versus by re-running the engine.

The four shapes the operator can submit:

| Slot 3 | Slot 4 | Conflict? |
|---|---|---|
| Manual CSV | (any) | **Yes if slot 4 has `rule_set_name` references** — the operator says "use these specific rows" *and* "this instrument is rule-based". |
| RuleSet dropdown | Settings CSV with matching `rule_set_name` | **No conflict** — both nominate the same RuleSet (resolved by name). |
| RuleSet dropdown | Settings CSV with **different** `rule_set_name` | **Yes** — two RuleSet selections at different scopes (session-level dropdown vs. per-instrument). |
| (empty) | Settings CSV | **No conflict** — chain stops at "assignments not generated yet"; operator runs Generate from the Assignments page after the session loads. |
| (empty) | (empty) | **No conflict** — neither slot contributes; today's behaviour. |
| Manual CSV / dropdown | (empty) | **No conflict** — slot 3 alone, today's behaviour. |

### Question to resolve — priority order

When slot 3 and slot 4 disagree, which wins? Two candidates,
both internally consistent:

- **Option A — Slot 3 wins (the explicit assignment-time
  choice).** The operator's most-recent action is the
  slot 3 upload / dropdown; slot 4 contributes the
  structural config (instruments, fields, RTDs) but its
  `rule_set_name` references are inert when slot 3
  contradicts them. Simpler mental model: *"what I
  selected in slot 3 is what runs"*.
- **Option B — Slot 4 wins for per-instrument
  selection, slot 3 only fills in the gaps.** The Settings
  CSV is explicitly per-instrument; the slot 3 dropdown
  is only meaningful when no per-instrument
  `rule_set_name` exists. Closer to the long-term 15B
  world where per-instrument selection is first-class
  and the session-level dropdown becomes a "default for
  new instruments" affordance.

Option A is cheaper to reason about today; Option B is
more aligned with the per-instrument direction that 15B is
heading toward. **TBD.** Resolve before the Part 2 PR
sequence is sized — the chosen priority drives the slot-4
importer's apply step (does it skip `rule_set_name` rows
when slot 3 contradicts? does it overwrite slot 3's
selection? does it raise on conflict?).

### Validation impact

Whichever priority wins, the validation rule needs to agree.
Today's `assignments.no_mode` warning fires when no
`assignment_mode` is set; under the new conflict matrix,
it should fire when the resolved priority chain produced no
assignments. **No new validation row needed** — just confirm
the rule reads against the resolved state, not against the
slot inputs.

### PR sequence (Part 2)

> Draft — depends on the priority resolution above.
>
> 1. **Pin the contract.** Refactor the Quick Setup chain to
>    surface a single
>    `resolve_assignments_decision(slot_3, slot_4) ->
>    AssignmentDecision` helper that encodes the priority
>    order. Pure function; tested in isolation.
> 2. **Wire slot 4 (12A-2 importer) to the resolver.**
>    Coordinates with 12A-2 PR 1 — the importer's apply step
>    consults the resolver before applying `rule_set_name`
>    references.
> 3. **UX cue on conflict.** When the operator's slot 3 +
>    slot 4 inputs disagree, surface a banner-warning during
>    the Quick Setup submit confirmation that names the
>    resolution ("slot 3 manual CSV will be used; slot 4's
>    rule_set_name references on instruments are
>    preserved as metadata for future Generate runs"). Same
>    pattern as 11J's slot-scoped warnings.

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

- Audit event name shape — `assignments.self_reviews_active_set`
  carries the resulting boolean in
  `counts.flipped` + the column value, which is the most
  compact form. Alternative split into
  `assignments.self_reviews_activated` /
  `..._deactivated` would read more naturally in the
  audit log but doubles the event-type registrations.
  Settle on the single-event shape unless review on
  PR 3 surfaces a reason to split.

### Part 2 (Sub-segment 12C-2)

- **Priority order between slot 3 and slot 4** — Option A
  (slot 3 wins) vs. Option B (slot 4 per-instrument
  wins, slot 3 fills gaps). Settle before the Part 2 PR
  sequence is sized.
- Should the conflict be **rejected at upload time** with
  an error banner ("your slot 3 + slot 4 inputs
  disagree on RuleSet selection — pick one") rather than
  resolved silently with a warning? Trades operator
  friction against silent surprise; depends on how often
  the conflict naturally arises.
