# Segment 18J — New-model instruments takeover + perf

> **Stub created 2026-05-24.** Sketch-level scope only — detailed
> PR breakdowns get drafted when each Part is picked up. The
> per-item Gap / Rec definitions and rationale live in
> `guide/new_model_instruments_outstanding.md`; this file's job
> is purely to sequence them.

## Goal

Drive the new-model instrument card (the flavour gated on
`instruments.is_new_model`) to **full takeover** — every
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

### Wave 1 — Quick wins (T-S, no schema)

Land first; both halves are small diffs and cure the most
visible operator pain today.

- **Gaps 1, 3, 5** — pill → `InstrumentDisplayField.visible`
  (Gap 1, via `update_display_field` at
  `_display_fields.py:291`), sort priorities on Band 2 pills
  (Gap 3), required-flag checkbox on Band 3 rows (Gap 5).
  After this wave the new-model card surfaces every per-
  display-field affordance the legacy card has.
- **Rec A** — drop the per-instrument eligible-pair count
  from `build_instruments_context`. Save → redirect → render
  stops paying the engine cost on the new-model path.
- **Rec D1** — single roster query per render. Lift the
  reviewee SELECT out of `_new_model_band2_state`
  (`app/web/views/_instruments.py:412-419`) into
  `build_instruments_context`. `O(K)` → 1 query.

Recommend A + D1 together as a single PR; Gaps 1 / 3 / 5 as
one or three sibling PRs depending on review-load.

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
