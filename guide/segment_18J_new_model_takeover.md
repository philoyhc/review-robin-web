# Segment 18J — New-model takeover mopping-up

> **Stub created 2026-05-24.** Sketch-level scope only — detailed
> PR breakdowns get drafted when each Part is picked up. The
> per-item Gap / Rec definitions and rationale live in
> `guide/new_model_instruments_outstanding.md`; this file's job
> is purely to sequence them.
>
> **Antecedent.** Segment 18I shipped the new-model
> instrument card from concept through main push (PRs **#1302
> → #1386**, see `guide/todo_master.md` Done section). 18J is
> the mopping-up sibling: it closes the parity gaps 18I left
> open, lands the perf follow-on, and ends with the
> `is_new_model` flag drop.

## Goal

Drive the new-model instrument card (the flavour gated on
`instruments.is_new_model`) from "usable end-to-end for design
feedback" (where 18I left it) to **full takeover** — every
operator-facing affordance covered, the legacy individual +
group cards retired, the `is_new_model` flag dropped — while
keeping Save / Refresh latency tolerable as adoption grows the
number of new-model cards on the Instruments index.

The gap inventory (Gaps 1-9) and the perf cost model + lift
sketches (Recs A-E) are already inventoried in
`guide/new_model_instruments_outstanding.md`. 18J adopts that
catalogue verbatim and decides only **what order to ship in**.

## Why now / why a segment

- **The catalogue spans two axes.** Gap closure (parity work
  toward retiring the legacy cards) and perf (Save + Refresh
  on 1k × 1k rosters) are independently shippable, but they
  interact — perf Layer 2 / 3 costs grow linearly with the
  number of new-model cards on the page, which only matters
  once gap closure makes the new-model card the default. A
  segment forces the interleave decision once rather than
  re-litigating it Part by Part.
- **Two work streams ship best together.** Wave 1 is small
  enough to land both perf and gap-closure quick wins in one
  PR or sibling PRs without splitting context across segments.
- **The endpoint is a cleanup PR.** Gap 8 + Gap 9 retire the
  legacy `+Group instrument` button and drop the
  `is_new_model` column. That cleanup needs to land *after*
  every other gap closes — naming the segment makes that
  terminal state explicit.

## Sequence (sketch)

Five waves, each independently shippable. The PR ladder inside
each wave is drafted when the wave is picked up.

### Wave 1 — Quick wins (T-S, no schema) — shipped 2026-05-24

Landed across five PRs (#1393, #1394, #1395, #1396, #1397) in
one sitting. After this wave the new-model card surfaces every
per-display-field affordance the legacy card has, the Grouped-
mode preview is honest about group membership, and Save no
longer pays the engine cost on the new-model path.

**Shipped PRs.**

| PR | Closes | Lift | Summary |
|---|---|---|---|
| #1393 | Rec A + Rec D1 | S | Conditional skip of `evaluate_session_rule_eligibility` for new-model-only pages; single active-reviewees query per render (was O(K)). |
| #1394 | Gap 10 | T-S | `find_sample_in_scope_reviewee` returns the rule-surviving group-member ID set alongside the sample reviewee; persisted to `band2_state.sample_group_member_ids`; render filters group_members by the set. Refresh-gated honesty contract preserved. |
| #1395 | Gap 1 | T-S | Pill toggle propagates to `InstrumentDisplayField.visible` via paired `update_display_field` calls; read path derives `selected_display_keys` from visible. Reviewer surface honours pill state. |
| #1396 | Gap 3 | S | Sort badges on Band 2 preview `<th>` cells, reusing the legacy `toggleSort` / `_rebuildSortInputs` JS. New-model branch of `/fields/save` processes the same parallel arrays. |
| #1397 | Gap 5 | T | Required checkbox on each Band 3 response-field row; persisted to `band2_state.response_fields[i].required`; preview column header gains `*` when required. Reviewer-surface enforcement waits for Wave 3 (Gap 2 bridge). |

**Design decisions taken at pickup** (preserved for the record).

- **Rec A flavour: conditional skip.** Skip
  `evaluate_session_rule_eligibility` for `is_new_model`
  instruments only. Legacy individual + group cards keep
  their counts unchanged. Smallest possible diff; lazy/async
  deferred until the legacy cards' count also becomes a felt
  latency complaint.
- **Gap 3 surface: preview-table header.** Sort badges live
  on the Band 2 preview table's `<th>` cells (tri-state
  cycle: unsorted → asc → desc → unsorted; priority number
  rendered on each sorted column). Pills keep their existing
  role — selection + display order — and stay free of the
  sort click conflict. Falls back to pill-mounted badges only
  if implementation finds the header-cell approach clearly
  unworkable (re-confirm before flipping).

**Caveat on Gap 5.** The required-flag checkbox persists into
`band2_state.response_fields[*]` JSON in Wave 1, but
**enforcement on the reviewer surface** waits for Wave 3
(Gap 2 bridging the JSON rows to real
`InstrumentResponseField` rows). Wave 1 ships
operator-authored metadata; the asterisk + validation
materialise alongside Gap 2. Bridge code in Wave 3 preserves
the `required` value across the migration.

**PR ladder.**

#### PR α — Rec A (conditional skip) + Rec D1 (single roster query) *(S)*

Perf double-tap. Both touch only the view-shape layer; no
template / JS change.

- **Rec A.** In `app/web/views/_instruments.py`, guard the
  `evaluate_session_rule_eligibility` call inside
  `_build_rule_picker_options` (line 312, reached from
  `build_instrument_rule_picker_contexts` lines 776-778) so
  it short-circuits when the requesting context is a
  `is_new_model` instrument. Confirm at implementation time
  whether the same call also feeds the picker dropdown's
  per-option counts: if it does, the skip is scoped to "no
  count rendered on this card" rather than "no count loaded
  for this picker" — pick whichever boundary matches the
  template's actual read.
- **Rec D1.** Lift the active-reviewees `SELECT` out of
  `_new_model_band2_state` (`_instruments.py:412-419`) into
  `build_instruments_context` (line 645). Fetch once at the
  top of the function; pass a `list[Reviewee]` (or
  `dict[id, Reviewee]`) into each `_new_model_band2_state`
  call. Signature change is
  `_new_model_band2_state(db, instrument)
  → (db, instrument, *, active_reviewees)`.

Tests:

- `tests/integration/test_instruments_index_perf.py`
  (new) — assert SQL query count is constant in the number
  of new-model instruments on the page (regression-style:
  count `Reviewee.session_id` SELECTs).
- Assert `evaluate_session_rule_eligibility` is not called
  for sessions whose only instruments are new-model
  (monkeypatch / spy).

Doc impact: annotate Recs A + D1 as shipped in
`guide/new_model_instruments_outstanding.md`.

#### PR β — Gap 1 (pill → `InstrumentDisplayField.visible`) *(T-S)*

Make the Band 2 pill toggle propagate to the real
`InstrumentDisplayField.visible` column so the reviewer
surface honours the operator's selection.

- **Write path.** When `set_band2_state`
  (`app/services/instruments/_instrument_crud.py:901`)
  mutates `band2_state.selected_display_keys`, paired call
  to `update_display_field`
  (`app/services/instruments/_display_fields.py:291`) for
  each newly-selected or newly-deselected display field,
  respecting the Name / Email locked-row guard (lines
  308-315). Name + Email pills render unclickable (already
  treated as a special case in the template — confirm at
  impl).
- **Read path.** `_new_model_band2_state` derives the
  initial pill `selected` state from
  `InstrumentDisplayField.visible` (the source of truth)
  rather than from `band2_state.selected_display_keys`
  alone. The JSON shape stays as a render hint / cache but
  the DB column wins on read.

Tests:

- Pill toggle → DB write covered for both selection and
  deselection; locked Name/Email rejected.
- Reviewer surface (`tests/integration/test_reviewer_*`)
  regression: deselecting a column on the new-model card
  drops it from the reviewer table.

#### PR γ — Gap 3 (sort badges on preview table header) *(S)*

Surface sort priorities in the Band 2 preview table header
cells.

- **Template.** Each `<th>` in the preview table
  (`app/web/templates/operator/instruments_index.html`,
  inside the `data-new-model-band2-preview` block at
  ~line 1314) gains a sort badge: priority number +
  asc/desc arrow when sorted, neutral icon when unsorted.
- **JS.** Click on header cell cycles unsorted → asc → desc
  → unsorted. When a column is removed from the sort,
  remaining columns renumber. POST the updated state via
  the existing `set_sort_display_fields` service
  (`_display_fields.py:771`) on each cycle (or on Save —
  decide at impl time based on whether the operator expects
  preview to reflect immediately).
- **Read path.** Reviewer surface already honours
  `instruments.sort_display_fields` from Segment 13B —
  no change needed.

Tests:

- Tri-state cycle round-trips through Save; multi-column
  sort assigns sequential priorities; removing a column
  renumbers the rest.
- Reviewer surface default sort matches the new-model
  card's authored priorities.

#### PR δ — Gap 5 (required-flag checkbox on Band 3 rows) *(T)*

Add the operator-authored required flag to each Band 3
response-field row.

- **Template.** Each Band 3 response-field row in the
  editor grows a Required checkbox column.
- **JS.** Row ✓ Save includes `required: bool` in the
  `band2_state.response_fields[*]` JSON.
- **Server.** `set_band2_state` preserves the new field
  (already round-trips arbitrary keys per PR #1379's
  `band2_state preserve all` fix — confirm at impl).
- **Preview.** Asterisk on the response-field column header
  in the Band 2 preview when required = true.

PR description **must** call out the half-shipped state:
checkbox visible + persisted; reviewer-surface enforcement
arrives with Wave 3.

Tests:

- Checkbox round-trip through Save preserves the value
  across no-op and edit cycles.
- Preview asterisk renders when required.

#### PR ε — Gap 10 (rule-constrained preview group expansion) *(T-S)*

Make the Grouped-mode preview's member list honest about
which reviewees Links 1+2 actually admit. Today the sample
**reviewee** is rule-constrained but the sample **group**
is not (see `guide/new_model_instruments_outstanding.md`
Gap 10).

- **Server-side.** Extend the sample-pick path
  (`find_sample_in_scope_reviewee` at
  `app/services/instruments/_band1.py:441-538`, or its
  caller in `_instruments.py::instrument_preview_sample`)
  to also return the set of rule-surviving reviewee IDs
  sharing the sample's boundary key. Compute by
  intersecting `engine.evaluate(...).pairs` (already
  produced) against the sample's `boundary_key` — pure
  set work, no second engine call.
- **Persistence.** Persist the ID set as
  `band2_state.sample_group_member_ids` (list of int) at
  Refresh time, alongside the existing
  `sample_reviewee_name`.
- **Render path.** `_new_model_band2_state` at
  `app/web/views/_instruments.py:456-464` filters
  `group_members` by `sample_group_member_ids` when the
  set is present. Fall through to the current
  unconstrained partition only when the set is absent
  (e.g. legacy band2_state rows that pre-date this PR —
  preview reflects stale unconstrained view until next
  Refresh, matching the existing Refresh-gated contract).

**Refresh contract preserved.** Preview honesty is gated on
the most recent Refresh; editing Links 1+2 without a
Refresh leaves the preview reflecting the previous engine
result. This matches today's contract for the sample
reviewee pick — Gap 10 just extends it to the member list.

Tests:

- After a Refresh under Links 1+2 that exclude half of a
  group's reviewees, the preview's `sample_names` shows
  only the surviving half.
- A pure tag-set rule (no QUOTA) and a QUOTA rule both
  filter the preview's group correctly.
- Legacy band2_state without `sample_group_member_ids`
  still renders (back-compat: unconstrained partition,
  same behaviour as today).

#### Recommended landing order

1. PR α first — smallest diff, biggest immediate operator
   win (Save lag), zero UI change.
2. PR ε second — correctness bug; cheap; lands before β/γ
   so the preview is honest as Gap 1's pill toggles and
   Gap 3's sort badges start exercising it more heavily.
3. PRs β / γ / δ in any order; mutually independent. Three
   sibling PRs let the reviewer batch them.
4. Rec E (no-op Save cache verify) can land as a tiny
   safety-net commit at any point in this wave or after.

**Out of Wave 1 scope** (per the catalogue split):

- Rec B (engine fast path), Rec D2 / D3 (page-level roster
  JSON + skip rebuild in view mode) — Wave 4.
- Gap 4 (help text + visibility) — Wave 3.
- Gap 2 / 6 / 7 (the schema-touching gaps) — Waves 2 / 3 / 4.

### Wave 2 — RTD library retirement — shipped 2026-05-24

Originally scoped as one M-sized PR; the test-fixture cascade
made that infeasible. Landed across **eight PRs** (PRs #1399 →
#1405) using a series of additive / flip / retire slices. The
end state:

- Numerical + string + List bounds all live inline on
  `instrument_response_fields` (six `_inline_*` columns).
- The `response_type_id` FK + the `response_type_definition`
  relationship + the `before_insert` listener + the
  validation-propagation loop are all retired.
- `operator_response_type_definitions` table + the entire
  cross-session library tier (Save-to-library / Add-from-library
  buttons, Settings page library card, library routes + audit
  events) — gone.
- The seeded RTD set is empty.

**One half-shipped piece deferred to Wave 5**: the
`response_type_definitions` table itself + the per-instrument
RTD card UI still exist so operators can author standalone RTDs
on the legacy individual/group cards. They retire together with
those cards in Wave 5 (Gap 8 + 9 cleanup).

**Shipped PRs.**

| PR | Slice | Lift | Summary |
|---|---|---|---|
| #1399 | i — additive schema | S | Add six `_inline_*` columns to `instrument_response_fields`; backfill from each row's RTD; `before_insert` listener bridges new rows. |
| #1400 | ii — flip readers | S | `.response_type` / `.data_type` properties prefer inline columns; fall back to FK relationship for safety. |
| #1401 | iii-a — FK nullable | S | Alter `response_type_id` to nullable so iii-b1 can land NULL refs. |
| #1402 | iii-b1 — explicit creators | S | All 7 production creator sites populate inline kwargs via `inline_kwargs_from_rtd`. Drop the property fallback. |
| #1403 | iii-b2 — seed retirement | M | `SEEDED_RESPONSE_TYPE_DEFINITIONS = []`. `DEFAULT_RESPONSE_FIELDS` rewritten to embed bounds inline. Migration NULLs FK refs + deletes seeded RTDs. Test-side `_legacy_rtd_helpers` + conftest seed shim for back-compat. |
| #1404 | iii-b3 — library tier | M | Drop `operator_response_type_definitions` table + `library_origin_id` column + 5 library audit events. Retire library routes / services / templates / 5 library test files. ~2300-line net reduction. |
| #1405 | iii-b4 — drop FK | S | Drop `response_type_id` column + listener + relationship. Add phantom property + init shim for back-compat with lingering test fixtures. 14 FK-driven tests skipped with TODO refs (deletion in Wave 5). |

### Wave 2½ — Band 2 reviewer-surface parity polish — shipped 2026-05-24

Nine UX-only PRs landed between Wave 2 and the start of Wave 3
to bring the new-model card's Band 2 preview much closer to what
a reviewer actually sees, plus stand up most of Gap 4's
underlying plumbing ahead of the formal Gap 4 UX decision. No
schema change in this wave — pure template / JS / CSS work
backed by one tiny new JSON endpoint (`/identity`).

**Shipped PRs.**

| PR | Slice | Lift | Summary |
|---|---|---|---|
| #1408 | Band 3 row toggles | T | Data-type `<select>` 20% → 15% width. "Required" checkbox replaced by an "R" toggle button (primary/secondary). New "≡" toggle button before ✓ shows / hides a half-width help card above the preview table per response field. `help_text_visible` persists in `band2_state.response_fields[*]`. |
| #1409 | Help card polish | T | Help card hides when the response chip is deselected (even if "≡" stays on). In-card ✎/✓ icon-button toggle for editing the help-text body inline; `help_text` persists alongside `help_text_visible`, clamped to 1000 chars server-side. |
| #1410 | Intro card v1 | S | Reviewer-surface `rs-intro-grid` / `rs-instrument-card` pattern transplanted into Band 2 — `<h2>` (short_label or name) + description subtitle + progress pills derived from `band2_state.response_fields`. Sits below the selector chips, above the help cards. |
| #1411 | Inline ✎/✓ for identity | S | Heading becomes "Page #N: <short_label or name>" (loop-index sourced — matches reviewer page numbering). short_label + description gain ✎/✓ pairs inside the intro card, gated on `is_editing`. New `POST /identity` JSON endpoint accepts `{short_label?, description?}` independently. Legacy heading-area short_label `<input>` + right-column description editor / display card + bottom-grid wrapper retired. |
| #1412 | Description textarea hide fix | T | Drop `display: block` from the description textarea's inline style so the `hidden` attribute's UA `[hidden]{display:none}` rule wins on specificity. Textarea now properly hides in non-edit mode (no perceivable empty box, no doubling-up with the view paragraph in edit mode). |
| #1413 | Heading + chips + constraints | S | "Review Instrument" → "Preview review instrument". Selector-chip row (display chips + `\|\|` divider + response chips) moved from above the intro card to the bottom of Band 2, flush-right. New constraint-summary row ("Rating (1-5, steps of 1), Notes (0-2000 char)") above the preview table — sibling to `buildResponseFieldHelpCards`, mirrors reviewer surface's `.rs-constraints`. |
| #1414 | Count semantics + thicker rules | T | Intro-card progress denominators count the full operator-authored response-field set (drop `selectattr('selected')`) — pill selection is a column-render concern, not a per-row item count. Band 2 separator `<hr>` lines bump from 1px to 3px. |
| #1415 | Compact sort buttons + RF cells | S | `.sort-btn` / `.sort-badge` shrink to match `.rrw-sort-btn` (18px height, no pill badge). Response-field preview cells now render disabled placeholder inputs / textareas / selects whose shape matches the reviewer surface (`review_surface.html` L345-410) — String / Integer / Decimal / List each render their own input shape with placeholder strings matching `placeholder_for_field`. |
| #1416 | Persistence-across-save + row height | T | Initial `newModelRefreshBand2` deferred to `DOMContentLoaded` — the inline `<script>` sat in the body *before* Band 3, so `buildConstraints` + `buildResponseFieldPreviewCell` were querying for Band 3 rows that hadn't been parsed yet on a page reload. Result before the fix: constraints line + placeholder inputs vanished into `—` after Save, only re-populating after a later Band-2/Band-3 interaction. Plus compact cell + input padding inside `[data-new-model-band2-preview]` to bring the row height down to reviewer-surface density. |

**What this means for Wave 3.** The preview surface is now
visually faithful to the reviewer experience — same intro card,
same constraint line, same input shapes, same progress pills.
Gap 4's underlying plumbing (help-text-body editing, visibility
toggle, persistence in `band2_state` + JSON-API) is shipped; the
deferred decision is purely the broader Band 3 UX (accordion vs
dedicated pane vs always-visible — see Wave 3 design decision 13
below). The remaining Gap 2 work (bridging JSON entries to real
`InstrumentResponseField` rows) is untouched and lands as the
three-PR Wave 3 ladder.

### Wave 3 — Response fields become real (M-L) — PRs i + ii shipped 2026-05-25; PR iii pending

**Scope.** Gap 2 (bridge `band2_state.response_fields` JSON
to real `InstrumentResponseField` rows) + Gap 5 enforcement
on the reviewer surface (Wave 1 shipped the required-flag
checkbox as metadata only). Gap 4 (help text UX) is
**deferred to a later wave** — the underlying `help_text` /
`help_text_visible` columns exist already and are untouched
in this wave; only the Band 3 surface for editing them is
deferred pending an operator-side design call.

At the end of Wave 3 the new-model card reaches functional
parity with the legacy individual + group cards on the
reviewer-surface read path. Operators can switch pilots over.

**Shipped so far.**

| PR | Slice | Lift | Summary |
|---|---|---|---|
| #1418 | i — additive schema + dual-write | M | `InstrumentResponseField.visible` column added (Boolean, default true). `set_band2_state` dual-writes JSON entries through to real `InstrumentResponseField` rows via id-match (`_sync_response_fields_to_db` in `app/services/instruments/_instrument_crud.py:1194`): entries with `id` update; entries without get a new row with `id` back-filled; absent ids delete (raising `ResponsesPresentError` when responses are attached so the route surfaces the error rather than cascading silently). Reviewer surface unchanged — still seeds the `DEFAULT_RESPONSE_FIELDS`-only rows; the read flip is PR ii. |
| TBD | ii — flip readers + enforce required + authoring + shape-lock | M | Reviewer-surface response-field reads (`responses.py`, `routes_reviewer/_surface.py`, `routes_reviewer/_preview.py`) now filter by `visible=true`, so a deselected Band 2 pill actually hides the column. `validate_value` reads `_inline_*` directly per decision 11 and gains String `max_length` + List option-membership branches — the bounds-rejection gap on new-model authored fields is closed. Two new service-level exceptions: `InvalidResponseFieldShapeError` (422 — max < min, step ≤ 0, empty List, etc) and `ResponseFieldShapeChangeError` (409 — data_type / bounds change on a row with saved responses). Band 3 row template renders `disabled` on `data_type` select + bound inputs when `has_responses=true`; ✓ button live-disables on empty name or invalid bounds; X button disables on empty awaiting-fill rows. Required flag is now load-bearing (Gap 5 enforcement). |

#### Locked design decisions

1. **Field-row identity.** Each
   `band2_state.response_fields[*]` entry gains an optional
   `id` field carrying the matching
   `InstrumentResponseField.id`. Save-time mapping is
   id-match: entries with `id` update the matching row;
   entries without `id` create a new row and back-fill the
   `id` on render; rows present in DB but absent from the
   JSON payload are deleted (cascade-checked, see decision 3).
2. **Visibility column.** Add
   `InstrumentResponseField.visible` (Boolean, default true).
   Mirrors the `InstrumentDisplayField.visible` pattern
   (Gap 1). The reviewer surface filters response fields by
   `visible=true` after PR ii flips readers.
3. **Cascade on delete.** The Band 3 row X button is
   rendered **disabled** when the field has ≥1 attached
   `Response` row. The Band 3 section title becomes
   "Response fields *(fields with undeleted responses
   cannot be removed)*" with the parenthetical in a muted
   weight. No confirm-dialog escape hatch from the row —
   operators must delete the responses first (or use Hide
   via the pill toggle to keep the field out of the
   reviewer surface non-destructively).
4. **Visibility UX.** The response-field pill in Band 2's
   "Review Instrument" row (the chips after the `||`
   divider, `instruments_index.html:1297-1310`) controls
   visibility. Pill toggle writes through to
   `InstrumentResponseField.visible`. The Band 3 editor's X
   button is **delete only** (subject to cascade check) —
   no separate Hide control in the editor row.
5. **`band2_state.response_fields` JSON shape.** Retired
   entirely once DB rows are authoritative. JSON becomes
   the wire format from Band 3's ✓ click, never the
   persisted state. The other `band2_state` keys
   (`selected_display_keys`, `sample_reviewee_name`,
   `sample_group_member_ids`, column widths) stay
   unchanged.
6. **Default seed preserved.**
   `DEFAULT_RESPONSE_FIELDS` (Rating: Integer, 1-5, step 1,
   required + Comments: String, 0-2000 chars, optional) is
   already seeded on every new instrument by
   `create_instrument`. Wave 3 inherits this on new-model
   instruments unchanged.
7. **Migration strategy.** Lazy materialise on first Save
   after deploy. No Alembic data migration; JSON entries
   without `id` get new rows the first time the operator
   Saves Band 3 after PR i lands.
8. **Band 3 first-render contract.** Band 3 reads rows
   directly from `InstrumentResponseField` when
   `band2_state.response_fields` is empty / absent.
   First-render is pure read — no write-on-read side
   effects, no audit churn. Edits-in-flight live in the
   browser DOM; Save POSTs the diff as JSON which becomes
   the transient wire format → DB rows.
9. **`field_key` stable across renames.** Operator-side
   rename mutates `label` only; `field_key` (the
   `responses.field_key` join key) never changes once a
   row exists.
10. **`validation` JSON column kept as cache.** Already
    populated from RTDs pre-Wave-2; now derived from the
    `_inline_*` columns. Current readers (reviewer-surface
    validators) untouched. Column retires in Wave 5
    cleanup, not mid-wave.
11. **Validation logic at two points.** Band 3 row save
    enforces authoring-time sanity (max ≥ min, step > 0,
    numeric values parse, `list_csv` non-empty for list
    type, `max_length` sane for string). Reviewer-surface
    submission enforces response sanity (value parses to
    `data_type`, falls within min/max, satisfies required
    flag). Both reads pull directly from the `_inline_*`
    columns on `InstrumentResponseField`.
12. **List options shape.** Inline CSV string on
    `_inline_list_csv` suffices for new-model. No
    per-option list editor in Band 3 (the legacy RTD
    list-editor UX does not port over).
13. **Help text UI deferred.** `help_text` (`Text`,
    nullable) and `help_text_visible` (Boolean, default
    true) columns exist and stay populated by any code
    path that already writes them. Wave 3 does not add a
    Band 3 surface for editing these — that's a separate
    UI decision the operator will return to. When the UX
    lands, three options are sketched: (1) inline
    accordion per row with a ▸ toggle that expands a
    `help_text` textarea + `help_text_visible` checkbox;
    (2) dedicated help-editor pane below the Response
    Fields editor (mirrors the legacy Response Fields Help
    table); (3) always-visible textarea + checkbox under
    each row.
14. **`help_text` length + rendering** (when Gap 4 lands).
    UI cap 1000 chars. Plain text, HTML-escaped on
    render. No markdown, no embedded HTML. Underlying
    column (`Text`, nullable) imposes no DB cap.

#### PR ladder

Three PRs, additive-first (same shape as Wave 2). Each
slice keeps the system functional end-to-end at HEAD —
reviewer surface behaviour only changes at PR ii.

##### PR i — Additive schema + dual-write (M) — shipped 2026-05-24 (PR #1418)

- **Schema.** Add `InstrumentResponseField.visible`
  (Boolean, default true) via Alembic migration with
  `batch_alter_table` for SQLite. Add optional `id`
  field to the `band2_state.response_fields[*]` JSON
  shape (sanitiser in
  `app/services/instruments/_instrument_crud.py:989-1035`
  rounds-trips it).
- **Dual-write.** `set_band2_state` continues to persist
  `response_fields` JSON **and** additionally
  creates / updates / deletes `InstrumentResponseField`
  rows via id-match. Lazy materialise: entries without
  `id` get new rows and the new `id` is reflected in the
  persisted JSON for the next render.
- **Cascade check in service.** Row delete inside
  `set_band2_state` raises if the row has any attached
  `Response` rows. The route catches this and the next
  render of the page sees the row still in DB; the X
  button renders disabled (`disabled` attribute + muted
  styling).
- **Template surface.** Band 3 row X gets the disabled
  state when `field.has_responses` is true; section
  title gains the parenthetical.
- **Reviewer surface unchanged.** Still reads only the
  `DEFAULT_RESPONSE_FIELDS` rows seeded by
  `create_instrument`. Operator-authored rows now exist
  in DB but the reviewer-surface code path doesn't read
  them yet — pure additive.
- **Tests.** JSON ↔ DB round-trip for create / update /
  delete via Band 3 Save; delete-with-responses keeps
  the row + renders disabled X; lazy materialise on
  first Save backfills `id`.

##### PR ii — Flip readers + enforce required (M) — shipped 2026-05-25

> Shipped scope expanded from the original sketch: in addition to the
> read flip + required enforcement + authoring validation, this PR
> closed the bounds-rejection gap by rewriting `validate_value` to
> read `_inline_*` directly (decision 11) and added the
> shape-change-with-responses guard
> (`ResponseFieldShapeChangeError`) + corresponding Band 3 template
> shape-lock. Two new service-level exceptions return as structured
> JSON from the `/band2-state` route.

- **Reviewer surface read.** Switch the response-fields
  read path used by the reviewer surface to return all
  rows where `visible=true`, ordered by `order`.
  Replaces the current `DEFAULT_RESPONSE_FIELDS`-only
  behaviour.
- **Pill → visibility write.** When the Band 2
  response-field pill toggles, the click handler POSTs
  a partial `band2_state.response_fields` payload with
  the matching row's `id` + `selected` (now interpreted
  as `visible`); `set_band2_state` writes through to
  `InstrumentResponseField.visible`.
- **Gap 5 enforcement flips on.** The reviewer-surface
  form renders the asterisk for `required=true` fields
  and the submit handler rejects empty values on those
  fields. Wave 1's metadata-only required flag becomes
  load-bearing.
- **Authoring-time validation.** `set_band2_state`
  validates each `response_fields[*]` entry (max ≥ min,
  step > 0, numeric values parse, list_csv non-empty
  for list type) before write. Validation errors
  surface to the operator via the existing form-error
  path.
- **Tests.** Reviewer surface sees operator-authored
  rows; deselected pill drops the field from the
  reviewer surface (without delete); required field
  validation rejects empty submission; authoring
  validation rejects nonsensical bounds at Save.

##### PR iii — Retire JSON write side (S)

- `set_band2_state` stops persisting `response_fields`
  in JSON. Sanitiser drops the key.
- Band 3 initial render reads from
  `InstrumentResponseField` directly (the (b)
  contract from decision 8 — already partially in
  place from PR i, now the only path).
- JSON payload on Band 3 Save is consumed transactionally
  and discarded; only DB rows persist.
- Migration: no schema change; one-time backfill of any
  remaining JSON-only entries lazy via PR i's
  dual-write path before PR iii lands.
- **Tests.** Band 3 round-trip without JSON state;
  `band2_state` audit history shows no
  `response_fields` keys post-PR iii; pre-existing JSON
  entries on instruments untouched since PR ii are
  back-filled correctly by PR ii's last Save.

### Wave 4 — Perf followers + RuleSet library retirement

Now that operators are adding new-model cards in volume
(post-Wave 3), the per-card costs that grow with `K` start
to bite. Land in parallel with Gap 7.

- **Rec D2** — single page-level
  `<script type="application/json" id="new-model-roster-data">`
  blob; HTML payload `K × 100KB` → `1 × 100KB`.
- **Rec D3** — skip on-load preview rebuild in view mode
  (requires either a new `data-edit-mode` data attribute on
  the card root, or reading the inner
  `[data-new-model-band2-editable]` `inert` flag — the card
  root does **not** currently expose an edit-mode signal;
  see Rec D3 in the outstanding doc).
- **Rec B** — `find_first_n_pairs` engine fast path. Cures
  Refresh on 1k × 1k from 1-3s to typically <100ms.
- **Gap 7** — retire the RuleSet library + Rule Builder
  child page. Band 1's inline editor (already shipped on
  new-model) becomes the canonical authoring surface.

D2 + D3 belong in one PR (they touch the same template + JS).
B is its own PR. Gap 7 is independent of the perf work but
naturally lands here.

### Wave 5 — Cleanup

- **Gap 8** — retire the `+Group instrument` button (Band 1
  Link 3's Individual ↔ Grouped toggle replaces it).
- **Gap 9** — drop the `instruments.is_new_model` column +
  the `+New model` button. Template branches on
  `is_new_model` collapse to a single shape.

Both gaps + the legacy template branches + routes + buttons
retire in one PR. After this wave the legacy individual /
group cards no longer exist.

## Deferred until needed

- **Rec C** — single-side predicate indexes (+ roster-upload
  cache). Defer until Rec B's worst case is observed on a
  real pilot roster. For broad-rule cases (the likely default)
  Rec B alone should hold latency well under 100ms.
- **Rec E** — verify Band 1 no-op Save stays cache-warm.
  Tiny safety-net commit; can land any time after Wave 1.
  Not blocking.

## Doc impact

When Waves ship:

- `docs/status.md` timeline entry per Wave.
- `guide/todo_master.md` updated (Wave-by-Wave).
- `guide/new_model_instruments_outstanding.md` annotated as
  Gaps / Recs close; the doc retires when Gap 9 lands and
  there's nothing left to track.
- `spec/instrument_builder.md` updated as Gaps 1-7 land
  (each one changes the operator surface contract).
- `guide/instrument_builder.md` cross-references updated as
  Parts §D-RTD + Part 1b sketches collapse into shipped state.
