# Segment 10B-2 Implementation Plan — Operator display-field builder

**Status:** Stub — decisions locked, slice breakdown still to be drafted.
Second of three PR-sized blocks for Segment 10B (display-fields picker
+ operator preview). See `guide/segment_10B.md` for the umbrella stub
that breaks 10B into 10B-1 / 10B-2 / 10B-3, and
`guide/segment_10_instrument_builder_mvp_plan.md` §14 for the
segment-level split. 10B-2 follows 10B-1 (data-driven render) and
precedes 10B-3 (preview).

- **10B-1 (shipped before this):** Alembic backfill, reviewer-surface
  refactor to render from `InstrumentDisplayField`, identity column,
  default-label inference. Behavior-preserving.
- **10B-2 (this doc):** display-field picker UI on the per-instrument
  card — row-level add / edit / delete POSTs, shared bulk "field
  order & visibility" form covering both display and response fields,
  invalidation + locked-when-ready gating, the four new audit events.
- **10B-3 (next):** `GET /operator/sessions/{id}/preview` with
  synthetic rows, disabled inputs, banner.

---

## 10B-2 outcome

One PR that ships:

- A display-field picker section on each per-instrument card on
  `/operator/sessions/{id}/instruments`, with sources limited to the
  seven defined in D1.
- Row-level POSTs for display fields:
  `POST .../display-fields` (add), `.../display-fields/{dfid}/edit`
  (edit label override + visibility), `.../display-fields/{dfid}/delete`.
- A shared instrument-level bulk form
  `POST .../fields/save` (one Save button per instrument) covering
  order + visibility + label across both display and response fields,
  per D3 / D5 / D7.
- `_invalidate_if_validated` + `_can_edit_instrument` gating wired
  through every new mutation per D10.
- Four new audit events per D11:
  `instrument.display_field_added`,
  `instrument.display_field_updated`,
  `instrument.display_field_deleted`,
  `instrument.display_fields_saved` (bulk diff).
- Reuse of the existing 10A `instrument.fields_reordered` event when
  the bulk save reorders response fields.

Reviewer surface unchanged from 10B-1 — the picker only writes data
that 10B-1's render layer already consumes. Preview route still not
present; that is 10B-3.

---

## Decisions locked for 10B-2

### D1 — Source columns + naming (picker UX)

The display-field picker exposes seven sources, two source types:

- `source_type="reviewee"` with `source_field ∈ {"tag_1", "tag_2",
  "tag_3", "profile_link"}` — the **actual** column names on
  `reviewees`, not the parent plan's "tag1 / photo_link" shorthand.
- `source_type="pair_context"` with `source_field ∈ {"1", "2", "3"}`
  — the slot key into `Assignment.context["pair_context_<slot>"]`.

`assignment_context_*` is deliberately excluded (preserves the
reviewer-facing / logic-engaging distinction; see ARCHITECTURE.md
"Pair-level vs assignment-level context").

10B-1 already seeded the three `pair_context` rows on every
instrument; the picker in 10B-2 lets the operator add the four
`reviewee` rows on demand and remove any of the seven.

### D3 — Builder UX shape (Option B)

Display fields and response fields share **one** instrument-level
"Field order & visibility" bulk form. Structural mutations stay
row-level.

- **Bulk form** (one Save button per instrument):
  - One row per field, **interleaved** display + response fields in
    operator-chosen order.
  - Per-row inputs: `order` (numeric), `visible` (checkbox), and for
    display-field rows only an optional `label` override.
  - Save action does a single transactional replace: repack `order` to
    `0..N-1` separately within each table (`instrument_display_fields`
    and `instrument_response_fields`), persist `visible` on display
    rows, persist any label override.
- **Structural mutations stay row-level (10A pattern unchanged):**
  - Add / Edit / Delete response-field POSTs from 10A keep their
    URLs and behavior (required-toggle banner, delete-confirm cascade,
    immutable `field_key`).
  - Display fields gain analogous row-level POSTs:
    `POST .../display-fields` (add), `.../display-fields/{dfid}/edit`
    (edit label override + visibility), `.../display-fields/{dfid}/delete`.
- **Identity column** (10B-1 D4) is not represented as a row in
  either form.

This keeps the required-toggle warning (10A D6), the delete-confirm
cascade (10A §7.4), and the immutable `field_key` rule (10A §7.1)
intact, while giving the operator one place to interleave order and
flip visibility across both kinds.

### D5 — Single ordering namespace across display + response

Reviewer surface column order, left to right (already implemented by
the 10B-1 renderer; 10B-2 adds the operator controls to drive it):

1. Reviewee identity (always first; 10B-1 D4).
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

### D7 — Bulk-save semantics

`POST /operator/sessions/{id}/instruments/{instrument_id}/fields/save`
(shared form for display + response field order/visibility).

- Form payload: an ordered list of rows. Each row carries
  `kind=display|response`, `id`, `order`, `visible` (display only),
  `label` (display only).
- Server-side: rows the operator removed from the form simply
  disappear from the payload. **In 10B-2, the bulk-save handler
  does NOT delete missing rows** — deletion goes through the row-level
  Delete POSTs so the cascade-confirm flow still applies. Rows in
  the payload that are missing from the database are ignored
  (defensive).
- New rows have no `id` — but **adds also go through their row-level
  POSTs**, not through bulk save. The bulk form is order +
  visibility + label only; structural mutations stay row-level
  (D3).
- After save: repack order `0..N-1` separately per table; emit one
  `instrument.fields_reordered` event when any order changed (reuses
  the existing 10A audit type, extended to cover display fields too)
  and one `instrument.display_fields_saved` event when any display
  visibility / label changed (D11).

### D10 — Validated → draft invalidation + locked-when-ready

Same pattern as 10A's response-field mutations:

- All display-field mutations (add / edit / delete) and the bulk
  fields-save POST flow through `_invalidate_if_validated` so a
  `validated` session flips back to `draft` with dedicated
  `session.invalidated` audit.
- All display-field structural mutations + the bulk save are gated
  on the existing `_can_edit_instrument` helper from 10A and return
  HTTP 409 when `session.status == "ready"`.
- The preview route (10B-3) does **not** invalidate (read-only).

### D11 — `instrument.display_fields_saved` audit shape

Diff-shaped (mirrors 10A's `instrument.field_updated`):

```python
detail = {
    "instrument_id": ...,
    "session_id": ...,
    "added": [
        {"source_type": ..., "source_field": ..., "label": ...,
         "visible": ..., "order": ...},
        ...
    ],
    "removed": [{"source_type": ..., "source_field": ..., ...}, ...],
    "updated": [
        {
            "source_type": ..., "source_field": ...,
            "changes": {"label": [old, new], "visible": [old, new], ...},
        },
        ...
    ],
}
```

Single bulk event per save. Per-row Add / Edit / Delete POSTs
emit their own `instrument.display_field_added` /
`instrument.display_field_updated` / `instrument.display_field_deleted`
events with the same shape conventions as 10A's response-field
events.

### D13 — Reorder UX in the bulk form

Numeric `<input type="number">` for `order` + Save button. **No
JavaScript.** Matches AGENTS.md's "no frontend framework" guidance
and stays consistent with the rest of the operator UI.

(If you want a drag-handle interaction post-10B, that's a styling
polish PR — out of scope here.)

---

## Audit events added in 10B-2

- `instrument.display_field_added`
- `instrument.display_field_updated`
- `instrument.display_field_deleted`
- `instrument.display_fields_saved` (bulk save with diff per D11)

`instrument.fields_reordered` (existing in 10A) is reused when
the bulk fields-save POST reorders response fields; its
`old_order` / `new_order` lists stay scoped to response-field
keys only. A future cleanup could fold display + response order
into one event; out of scope for 10B-2.

---

## Out of scope for 10B-2 (explicitly deferred)

- Alembic backfill, `ensure_default_instrument` seeding,
  reviewer-surface refactor, identity column, default-label
  inference → already shipped in 10B-1 (prerequisite).
- `GET /operator/sessions/{id}/preview` route, synthetic-row
  helper, disabled-inputs render, banner → 10B-3.
- Multi-instrument operator UI (Add / Delete instrument buttons stay
  disabled per 9.4C / 10A) → Segment 13.
- Per-instrument applicability filtering on the reviewer dashboard
  → Segment 13.
- Operator-driven export of the configured surface → Segment 11.
- `assignment_context_*` as a display-field source — deliberately
  excluded per D1.
- Drag-handle reorder UX → out of scope; numeric inputs ship per D13.
- `spec/target_operator_map.md` rewrite → separate post-10B PR per
  10B D12.

---

## To draft next

This stub locks the decisions for 10B-2. The implementation slice
breakdown (parallel to `segment_10A.md` Slices 1–5: service layer
→ routes → templates → tests) is **not yet drafted** and is the
next deliverable on this branch.
