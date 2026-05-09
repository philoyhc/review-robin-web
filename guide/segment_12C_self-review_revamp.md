# Segment 12C — Self-review revamp

**Status:** Planning — scope locked 2026-05-09. PR sequence and
implementation pointers still being filled in; treat the
"Implementation pointers" and "PR sequence" sections as drafts.

## Goal

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
   on/off toggle on the Assignments page. No regeneration.

The two layers don't overlap: the RuleSet flag controls
**generation** (rows present or absent); the Include toggle
controls **activation** of rows that already exist. Nothing
about the underlying schema changes —
`RuleSetRevision.exclude_self_reviews` and
`Assignment.include` are both already there. This segment is
a UI re-routing exercise plus a small dead-code cleanup.

## Targeted behaviors (locked 2026-05-09)

1. **Remove `exclude_self_review` as an ad-hoc generation
   toggle.** Drop the form input from:
   - **Quick Setup** (slot 3 of the Quick Setup card on
     both Create New Session and Session Home).
   - **Assignments page** (the toggle that today sits
     alongside the Generate button on the Rule Based card).
2. **Surface `exclude_self_reviews` in the Rule Builder.**
   The flag already lives on `RuleSetRevision` — promote it
   into the Rule Builder UI as a first-class checkbox so an
   operator who wants self-reviews skipped at generation
   time encodes that decision **in the RuleSet itself**.
   Remove the equivalent check from every other operator
   surface.
3. **Add a bulk Include toggle for self-reviews on the
   Assignments page.** A single on/off control that flips
   `Assignment.include` for every self-review row in the
   session at once. Self-review rows still exist in the
   table whenever the RuleSet generated them or a manual
   CSV uploaded them; the toggle just decides whether they
   participate. Per-row Include checkboxes (already present
   on the assignments table, today) keep their per-row role;
   the new toggle is a bulk shortcut.

## Decisions (locked 2026-05-09)

- **Toggle UX = bulk on/off.** A single switch that flips
  every self-review row's `Assignment.include` flag at
  once. Not a filter view; not per-row. Per-row Include
  checkboxes stay as the override surface.
- **Full-matrix is fully absorbed into the RuleSet system.**
  At the UI level, full-matrix has already become "the
  full-matrix seeded RuleSet" picked from Quick Setup
  slot 3's dropdown. This segment removes any **remaining
  standalone affordance** — most importantly the
  `POST /operator/sessions/{id}/assignments/full-matrix`
  route in `_assignments.py` and the
  `AssignmentMode.full_matrix` enum value, if no other
  surface still depends on either. (Spike to confirm:
  Quick Setup's legacy `rule="full_matrix"` payload
  fall-through in `_quick_setup.py:573-586` may be the only
  caller; if so, drop the fallback together with the route.)
- **Validation rule kept; copy refreshed.**
  `count_self_reviews_in_assignments` (and the
  `assignments.self_reviews_present` validation row that
  cites it) stays. Screen text updates to make clear that
  these are **self-review pairs that exist in the
  assignments table**, which can be turned on / off via
  the bulk Include toggle if the operator wants. No
  behavioural change to the predicate; just a copy refresh
  on the validation row + any banner that mentions it.
- **No new schema.**
  - `RuleSetRevision.exclude_self_reviews` already exists
    (Rule Builder needs to expose it).
  - `Assignment.include` already exists (Assignments page
    needs the bulk toggle wired against it).
  - `count_self_reviews_in_assignments` already exists
    (validation rule needs the copy refresh).

## Implementation pointers

> Draft — flesh out as the PR sequence settles.

- **Rule Builder UI.** The flag lives on
  `RuleSetRevision.exclude_self_reviews` and travels
  through the Rule Builder's edit / preview / save flow
  today as a hidden form value. Surface it as a labelled
  checkbox in the Rule Builder's main editor card. The
  rules-JSON serializer (`_rule_based_editor_js.html`)
  already round-trips the flag; just need a visible
  control + matching adapter slot in `views/_rule_builder.py`.
- **Quick Setup.** The slot-3 form-data field
  `exclude_self_review` (string flag) is read by
  `_quick_setup.py` and passed into `generate_full_matrix`
  / the rule-based engine. Drop the form field on the
  template + the handler-side fallback that defaults it
  on; rely entirely on the RuleSet's own flag (the
  RuleSet picker in slot 3 already resolves to a
  `session_rule_sets` row).
- **Assignments page.** The Rule Based card today carries
  an `exclude_self_review` checkbox alongside the Generate
  button. Drop it; replace with the new bulk Include
  toggle that POSTs to a new route — e.g.
  `POST /operator/sessions/{id}/assignments/self-reviews/include`
  with body `{"include": true|false}` — that runs a
  single UPDATE against `Assignment` where the row is a
  self-review pair (predicate-driven, mirroring
  `count_self_reviews_in_assignments`). Audit event
  `assignments.self_reviews_include_toggled` registered
  in `EVENT_SCHEMAS` per 11K's strict-mode gate; detail
  carries `counts.flipped` + the resulting boolean.
- **Full-matrix cleanup.** Spike to confirm no live caller
  hits `POST /assignments/full-matrix` outside the
  Quick Setup legacy fallback. If clean, delete the route,
  the `assignments_full_matrix` handler, the
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
  use the bulk Include toggle on the Assignments page
  to deactivate if needed".

## Out of scope

- **Per-row Include UX changes.** The per-row Include
  checkboxes on the Assignments table stay exactly as
  they are today.
- **Schema changes.** No new columns / tables. The
  semantic shift rides on existing fields.
- **Settings / manual-assignments CSV format.** The
  Settings CSV already exports
  `session_rule_sets[N].exclude_self_reviews`; the
  manual-assignments CSV already exports per-row
  `IncludeAssignment`. Removing the ad-hoc UI toggle
  drops zero export columns. Round-trip with 12A-1
  unchanged.
- **Validation predicate change.**
  `count_self_reviews_in_assignments` keeps counting
  every self-review row regardless of `include` value;
  the operator's mental model is "rows present in the
  table", not "rows currently active". The copy is what
  carries the new framing.
- **Self-review export column.** The Responses CSV's
  `SelfReview` column (12A-1 PR 4a) is purely a
  derived flag for analyst convenience — orthogonal to
  the generation / activation question this segment
  answers.

## PR sequence

> Draft — sized once Implementation pointers firm up.
> Likely shape:
>
> 1. **Rule Builder surfaces `exclude_self_reviews`.**
>    Foundational — the only place to encode the
>    decision once the ad-hoc toggles are gone.
> 2. **Bulk Include toggle on Assignments page** + new
>    route + audit event.
> 3. **Drop ad-hoc toggles** from Quick Setup + the
>    Assignments page Rule Based card. Validation copy
>    refresh in the same PR (small, scoped).
> 4. **Full-matrix code cleanup** — remove the standalone
>    route + enum value + legacy Quick Setup fallback,
>    once the spike confirms no remaining callers.

## Related context

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

## Open questions

- Does the bulk Include toggle persist its **last state**
  per session as a UI cue (e.g. "self-reviews are off"
  banner) or is it strictly a one-shot action whose state
  is implicit in the row data? The latter is simpler;
  the former is a nicer cue. Settle on a sketch when PR 2
  scopes.
- Audit event name shape — `assignments.self_reviews_include_toggled`
  or split into
  `assignments.self_reviews_activated` /
  `..._deactivated`? Two events is more verbose but the
  audit log reads naturally; one event with the boolean
  in the detail is more compact. Defer to PR 2.
