# Segment 10B Plan — Display-fields picker + operator preview (umbrella)

**Status:** Umbrella stub — split into three PR-sized sub-stubs.
Decisions for the segment as a whole are still locked here; per
sub-PR decisions live in `segment_10B_1.md` / `segment_10B_2.md` /
`segment_10B_3.md`. Second of two PR-sized blocks for Segment 10
at the segment level. See
`guide/archive/segment_10_instrument_builder_mvp_plan.md` §14 for the
segment-level split, and `guide/segment_10A.md` for the locked
decisions on the consolidated `/instruments` page that 10B extends.

- **10A (shipped):** consolidated `/operator/sessions/{id}/instruments`
  page, response-field builder (add / edit / delete / reorder + per-field
  help text + visibility), friendly description, bulk Open all / Close
  all, reviewer-surface loop-by-instrument refactor, body width 1400px.
- **10B (this doc):** display-fields picker on the per-instrument card,
  shared "field order & visibility" bulk form covering both display and
  response fields, reviewer-surface display-fields-driven render
  (replaces the hard-coded `pair_context_*` rendering), operator preview
  route. Split into three sub-PRs below.

---

## Sub-PR breakdown

10B as originally written is meaningfully larger than 10A in scope
(migration + reviewer-surface render swap + display-field CRUD +
bulk interleaved order/visibility form + preview route + four new
audit events). It is split into three PR-sized blocks:

- **10B-1 (data-driven render)** — `guide/segment_10B_1.md`.
  Backfill migration, `ensure_default_instrument` seeding the three
  pair-context rows, reviewer surface refactored to render from
  `InstrumentDisplayField` (replacing hard-coded `pair_context_*`),
  identity column (D4), default-label inference (D6). Ships
  behavior-preserving — no operator UI yet.
- **10B-2 (operator builder)** — `guide/segment_10B_2.md`.
  Row-level display-field add / edit / delete POSTs + shared bulk
  "field order & visibility" form (D3, D5, D7), invalidation +
  locked-when-ready gating (D10), the four new audit events (D11).
- **10B-3 (preview)** — `guide/segment_10B_3.md`.
  `GET /operator/sessions/{id}/preview` with synthetic rows,
  disabled inputs, banner (D8, D9).

10B-2 cannot land before 10B-1 (the picker writes into rows that
10B-1's renderer reads). 10B-3 can in principle land after 10B-1
alone, but is sequenced last so the preview demos the full builder.

---

## Decisions locked for 10B (segment-wide)

### D1 — Source columns + naming

The display-field picker exposes seven sources, two source types:

- `source_type="reviewee"` with `source_field ∈ {"tag_1", "tag_2",
  "tag_3", "profile_link"}` — the **actual** column names on
  `reviewees`, not the parent plan's "tag1 / photo_link" shorthand.
- `source_type="pair_context"` with `source_field ∈ {"1", "2", "3"}`
  — the slot key into `Assignment.context["pair_context_<slot>"]`.

`assignment_context_*` is deliberately excluded (preserves the
reviewer-facing / logic-engaging distinction; see `spec/architecture.md`
"Pair-level vs assignment-level context").

Lands across 10B-1 (default-label coverage of all seven sources;
seeded `pair_context` rows) and 10B-2 (picker UX exposing the four
`reviewee` sources for add).

### D2 — Backfill migration scope → 10B-1

Single Alembic revision. For every existing instrument, write three
`InstrumentDisplayField` rows for `pair_context_1/2/3`
(`source_type="pair_context"`, `source_field="1"|"2"|"3"`,
`visible=true`, `order=0..2`, `label=''` — empty string; treated
identically to NULL by the D6 inference helper) **unconditionally** —
including instruments that already carry display-field rows. Picks
option (b) from the open question: destructive-but-consistent.

(`instrument_display_fields.label` is `nullable=False` in the model;
seeding empty string preserves the umbrella decision intent without
an `ALTER COLUMN` change.)

`ensure_default_instrument` updates to seed the same three rows on
every newly created instrument.

No new columns on `instrument_display_fields` — the existing schema
(`label`, `source_type`, `source_field`, `order`, `visible`) is
already sufficient.

### D3 — Builder UX shape (Option B) → 10B-2

Display fields and response fields share **one** instrument-level
"Field order & visibility" bulk form. Structural mutations stay
row-level. See `segment_10B_2.md` D3 for the full form contract.

### D4 — Reviewee identity column is fixed → 10B-1

Always-first column on the reviewer surface: reviewee `name`
(primary) with `email_or_identifier` beneath in smaller font, same
cell. **Mandatory.** Not represented by an `InstrumentDisplayField`
row, not toggleable, not reorderable.

### D5 — Single ordering namespace across display + response

Reviewer surface column order, left to right:

1. Reviewee identity (always first; D4).
2. All visible display fields and response fields, **interleaved** in
   the operator-chosen order from the bulk form.
3. Per-row submitted-status indicator (rightmost; today's behavior).

Default ordering on a freshly seeded instrument: display fields
first (orders 0..2 from the backfill / `ensure_default_instrument`),
then response fields (orders 0..N-1 from the seed). The bulk form
lets the operator interleave, e.g. `tag_1 → Rating → tag_2 →
Comments`.

Internally, `order` is repacked `0..N-1` **per table** on save (not
across tables) — the merged ordering is computed at render time
from `(table, order)` pairs sorted by a stable composite key.

The render-side merged-sort lands in 10B-1; the operator interleave
controls land in 10B-2.

### D6 — Default labels are inferred → 10B-1

When a display field's `label` is NULL or empty, the reviewer
surface column header falls back to an inferred string:

| `source_type` | `source_field` | Inferred label |
|---|---|---|
| `reviewee` | `tag_1` | "Tag 1" |
| `reviewee` | `tag_2` | "Tag 2" |
| `reviewee` | `tag_3` | "Tag 3" |
| `reviewee` | `profile_link` | "Profile" |
| `pair_context` | `1` | "Pair context 1" |
| `pair_context` | `2` | "Pair context 2" |
| `pair_context` | `3` | "Pair context 3" |

No `_DEFAULT_LABEL_MAP` constant needed beyond a small helper.
Operator-typed labels are stored verbatim and round-tripped.

### D7 — Bulk-save semantics → 10B-2

`POST /operator/sessions/{id}/instruments/{instrument_id}/fields/save`
(shared form for display + response field order/visibility). See
`segment_10B_2.md` D7 for the full payload + handler contract.

### D8 — Preview row population → 10B-3

`GET /operator/sessions/{id}/preview` renders the reviewer surface
template with **three rows**: real assignments where possible,
synthetic placeholders to fill. Synthetic row shape uses
`"Sample Reviewee 1/2/3"`, `"sample1@example.edu"`, etc., with
plausible placeholder values per display-field source.

### D9 — Preview gating → 10B-3

Operator-only (`require_session_operator`); works in any status
(`draft` / `validated` / `ready`); bypasses deadline / acceptance
gates; all inputs disabled; no save / submit / clear forms; banner
"Preview — not visible to reviewers" at the top.

### D10 — Validated → draft invalidation + locked-when-ready → 10B-2

Same pattern as 10A's response-field mutations:

- All display-field mutations (add / edit / delete) and the bulk
  fields-save POST flow through `_invalidate_if_validated` so a
  `validated` session flips back to `draft` with dedicated
  `session.invalidated` audit.
- All display-field structural mutations + the bulk save are gated
  on the existing `_can_edit_instrument` helper from 10A and return
  HTTP 409 when `session.status == "ready"`.
- The preview route does **not** invalidate (read-only).

### D11 — `instrument.display_fields_saved` audit shape → 10B-2

Diff-shaped, mirrors 10A's `instrument.field_updated`. See
`segment_10B_2.md` D11 for the detail dict shape.

### D12 — `spec/target_operator_map.md` update → post-10B PR

Lands in a **separate PR** after 10B-3 merges. 10B's three sub-PRs
ship implementation + tests; the spec rewrite is a docs-only
follow-on that re-frames the `/instruments` page to reflect 10A's
response-field builder, 10B-2's display-field picker, and 10B-3's
preview route. Splitting keeps each sub-PR's diff focused.

### D13 — Reorder UX in the bulk form → 10B-2

Numeric `<input type="number">` for `order` + Save button. **No
JavaScript.** Matches AGENTS.md's "no frontend framework" guidance
and stays consistent with the rest of the operator UI.

(If you want a drag-handle interaction post-10B, that's a styling
polish PR — out of scope here.)

---

## Audit events added across 10B

Added in 10B-2:

- `instrument.display_field_added`
- `instrument.display_field_updated`
- `instrument.display_field_deleted`
- `instrument.display_fields_saved` (bulk save with diff per D11)

`instrument.fields_reordered` (existing in 10A) is reused when
10B-2's bulk fields-save POST reorders response fields; its
`old_order` / `new_order` lists stay scoped to response-field
keys only. A future cleanup could fold display + response order
into one event; out of scope for 10B.

10B-1 and 10B-3 add no audit events.

---

## Out of scope for 10B (explicitly deferred)

- Multi-instrument operator UI (Add / Delete instrument buttons stay
  disabled per 9.4C / 10A) → Segment 13.
- Per-instrument applicability filtering on the reviewer dashboard
  → Segment 13.
- Operator-driven export of the configured surface → Segment 11.
- Anonymous / shareable preview link — preview is operator-only and
  gated on `require_session_operator`.
- `assignment_context_*` as a display-field source — deliberately
  excluded per D1.
- Drag-handle reorder UX → out of scope; numeric inputs ship in
  10B-2 per D13.
- `spec/target_operator_map.md` rewrite → separate post-10B PR per D12.

---

## To draft next

This umbrella stub locks the segment-wide decisions and points to
three per-sub-PR stubs. The implementation slice breakdown for each
sub-PR (parallel to `segment_10A.md` Slices 1–5: migration → service
layer → routes → templates → tests) is **not yet drafted** in any
of `segment_10B_1.md` / `segment_10B_2.md` / `segment_10B_3.md`.
