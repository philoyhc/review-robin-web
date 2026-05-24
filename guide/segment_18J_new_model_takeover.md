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

### Wave 1 — Quick wins (T-S, no schema) — picked up 2026-05-24

Land first; small diffs that cure the most visible operator
pain today. After this wave the new-model card surfaces every
per-display-field affordance the legacy card has, the Grouped-
mode preview is honest about group membership, and Save no
longer pays the engine cost on the new-model path.

**Design decisions taken at pickup.**

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

### Wave 2 — RTD library retirement (M, schema delta)

- **Gap 6** — inline numerical + string bounds onto
  `instrument_response_fields`; keep List-type RTDs as a
  per-session catalogue; retire
  `operator_response_type_definitions`. Lands **before**
  Wave 3 so Gap 2 doesn't have to author the per-instrument-
  RTD bloat workaround.

### Wave 3 — Response fields become real (M-L)

- **Gap 2** — `band2_state.response_fields` JSON entries
  become real `InstrumentResponseField` rows. Cheap now
  because Wave 2 inlined the bounds.
- **Gap 4** — response-field help text + visibility. Rides
  along since `InstrumentResponseField.help_text` /
  `.help_text_visible` exist once Gap 2 closes.

At the end of Wave 3 the new-model card has full parity with
the legacy individual + group cards. Operators can switch
their pilots over.

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
