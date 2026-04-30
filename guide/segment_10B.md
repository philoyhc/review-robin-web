# Segment 10B Implementation Plan — Display-fields picker + operator preview

**Status:** Stub — decisions locked, slice breakdown still to be drafted.
Second of two PR-sized blocks for Segment 10. See
`guide/segment_10_instrument_builder_mvp_plan.md` §14 for the
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
  route.

---

## Decisions locked for 10B

### D1 — Source columns + naming

The display-field picker exposes seven sources, two source types:

- `source_type="reviewee"` with `source_field ∈ {"tag_1", "tag_2",
  "tag_3", "profile_link"}` — the **actual** column names on
  `reviewees`, not the parent plan's "tag1 / photo_link" shorthand.
- `source_type="pair_context"` with `source_field ∈ {"1", "2", "3"}`
  — the slot key into `Assignment.context["pair_context_<slot>"]`.

`assignment_context_*` is deliberately excluded (preserves the
reviewer-facing / logic-engaging distinction; see ARCHITECTURE.md
"Pair-level vs assignment-level context").

### D2 — Backfill migration scope

Single Alembic revision. For every existing instrument, write three
`InstrumentDisplayField` rows for `pair_context_1/2/3`
(`source_type="pair_context"`, `source_field="1"|"2"|"3"`,
`visible=true`, `order=0..2`, `label=NULL`) **unconditionally** —
including instruments that already carry display-field rows. Picks
option (b) from the open question: destructive-but-consistent.

`ensure_default_instrument` updates to seed the same three rows on
every newly created instrument.

No new columns on `instrument_display_fields` — the existing schema
(`label`, `source_type`, `source_field`, `order`, `visible`) is
already sufficient.

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
- **Identity column** (D4) is not represented as a row in either form.

This keeps the required-toggle warning (10A D6), the delete-confirm
cascade (10A §7.4), and the immutable `field_key` rule (10A §7.1)
intact, while giving the operator one place to interleave order and
flip visibility across both kinds.

### D4 — Reviewee identity column is fixed

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

### D6 — Default labels are inferred

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

### D7 — Bulk-save semantics

`POST /operator/sessions/{id}/instruments/{instrument_id}/fields/save`
(shared form for display + response field order/visibility).

- Form payload: an ordered list of rows. Each row carries
  `kind=display|response`, `id`, `order`, `visible` (display only),
  `label` (display only).
- Server-side: rows the operator removed from the form simply
  disappear from the payload. **In 10B, the bulk-save handler does
  NOT delete missing rows** — deletion goes through the row-level
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

### D8 — Preview row population

`GET /operator/sessions/{id}/preview` renders the reviewer surface
template with **three rows**:

- If the session has at least three assignments, use the first three
  by `Assignment.id` ascending.
- If 1–2 assignments exist, use those plus enough synthetic rows to
  reach three.
- If zero assignments exist, render three synthetic rows.

Synthetic row shape: reviewee name `"Sample Reviewee 1"` /
`"Sample Reviewee 2"` / `"Sample Reviewee 3"`, email
`"sample1@example.edu"` etc., display-field cells filled with
plausible placeholder values per source (`"Sample tag value"` for
reviewee tags, `"Sample pair context"` for pair contexts,
`"https://example.edu/sample-profile"` for `profile_link`), response
cells empty.

### D9 — Preview gating

`GET /operator/sessions/{id}/preview` is operator-only (gated on
`require_session_operator`) and works in **any** session status
(`draft` / `validated` / `ready`).

- **Bypasses** the reviewer-surface deadline / acceptance gate.
- All inputs render disabled (`disabled` attribute on every input,
  textarea, select).
- No save / submit / clear forms reachable on the preview surface.
- Renders a "Preview — not visible to reviewers" banner at the top.

### D10 — Validated → draft invalidation + locked-when-ready

Same pattern as 10A's response-field mutations:

- All display-field mutations (add / edit / delete) and the bulk
  fields-save POST flow through `_invalidate_if_validated` so a
  `validated` session flips back to `draft` with dedicated
  `session.invalidated` audit.
- All display-field structural mutations + the bulk save are gated
  on the existing `_can_edit_instrument` helper from 10A and return
  HTTP 409 when `session.status == "ready"`.
- The preview route does **not** invalidate (read-only).

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

### D12 — `spec/target_operator_map.md` update

Lands in a **separate PR** after 10B merges. 10B ships
implementation + tests; the spec rewrite is a docs-only follow-on
that re-frames the `/instruments` page to reflect both 10A's
response-field builder and 10B's display-field picker. Splitting
keeps 10B's diff focused.

### D13 — Reorder UX in the bulk form

Numeric `<input type="number">` for `order` + Save button. **No
JavaScript.** Matches AGENTS.md's "no frontend framework" guidance
and stays consistent with the rest of the operator UI.

(If you want a drag-handle interaction post-10B, that's a styling
polish PR — out of scope here.)

---

## Audit events added in 10B

- `instrument.display_field_added`
- `instrument.display_field_updated`
- `instrument.display_field_deleted`
- `instrument.display_fields_saved` (bulk save with diff per D11)

`instrument.fields_reordered` (existing in 10A) is reused when
the bulk fields-save POST reorders response fields; its
`old_order` / `new_order` lists stay scoped to response-field
keys only. A future cleanup could fold display + response order
into one event; out of scope for 10B.

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
- Drag-handle reorder UX → out of scope; numeric inputs ship in 10B
  per D13.
- `spec/target_operator_map.md` rewrite → separate post-10B PR per D12.

---

## To draft next

This stub locks the decisions. The implementation slice breakdown
(parallel to `segment_10A.md` Slices 1–5: migration → service layer
→ routes → templates → tests with ~10–12 cases per §14.3) is **not
yet drafted** and is the next deliverable on this branch.
