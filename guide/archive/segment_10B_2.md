# Segment 10B-2 Implementation Plan — Operator display-field builder

**Status:** Plan drafted — decisions locked, slice breakdown below.
Second of three PR-sized blocks for Segment 10B (display-fields picker
+ operator preview). See `guide/segment_10B.md` for the umbrella stub
that breaks 10B into 10B-1 / 10B-2 / 10B-3, and
`guide/archive/segment_10_instrument_builder_mvp_plan.md` §14 for the
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
reviewer-facing / logic-engaging distinction; see `spec/architecture.md`
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

## Implementation slices

### Slice 1 — Service-layer helpers for display fields

New module-level additions to `app/services/instruments.py` mirroring
10A's response-field helper set:

- `_VALID_DISPLAY_SOURCES: set[tuple[str, str]]` — the seven D6 source
  pairs, used as the picker allowlist. Re-derived from
  `_DEFAULT_DISPLAY_LABELS.keys()` (already in the module from
  10B-1) so the truth-source stays in one place.
- `class DisplaySourceError(ValueError)` — raised for unknown source
  pairs and duplicate `(source_type, source_field)` on the same
  instrument; route layer translates to HTTP 400.
- `_ordered_display_fields(db, instrument) -> list[InstrumentDisplayField]`
  — mirror of `_ordered_fields`; orders by `(order, id)`.
- `_repack_display_orders(fields)` — mirror of `_repack_orders`.
- `add_display_field(db, *, instrument, source_type, source_field,
  label, visible, actor) -> InstrumentDisplayField`:
  - validate `(source_type, source_field) in _VALID_DISPLAY_SOURCES`
    (else `DisplaySourceError`);
  - reject duplicate `(source_type, source_field)` on the instrument
    (else `DisplaySourceError`);
  - normalise `label` via `.strip()`; allow empty (the D6 helper
    fills in the inferred fallback at render time);
  - assign `order = max(existing) + 1` then repack to `0..N-1`;
  - audit `instrument.display_field_added`.
- `update_display_field(db, *, field, label, visible, actor)
  -> tuple[InstrumentDisplayField, dict[str, list[Any]]]`:
  - diff `label` (strip-on-read) and `visible`;
  - audit `instrument.display_field_updated` with
    `detail.changes = {key: [old, new], …}` when non-empty.
  - `(source_type, source_field)` are immutable post-create
    (mirrors 10A's immutable `field_key`); the form does not
    expose them.
- `delete_display_field(db, *, field, actor) -> None`:
  - snapshot the field config, delete, repack remaining display
    fields to `0..N-1`, audit `instrument.display_field_deleted`
    with `detail.snapshot`. No cascade-confirm flow — display fields
    have no per-row dependent data (unlike `Response` rows on
    response fields).
- `bulk_save_fields(db, *, instrument, rows, actor) -> dict`:
  - `rows` payload shape (validated at the route layer): a list of
    `{"kind": "display"|"response", "id": int, "order": int,
    "visible": bool | None, "label": str | None}` where `visible`
    and `label` are populated only when `kind == "display"`.
  - Apply per D7: load both tables, intersect each `kind` group
    against the IDs the operator submitted (rows missing from the
    payload are left as-is — deletion goes through the row-level
    Delete POST, not bulk save), repack `order` to `0..N-1`
    **separately per table** in submission order, persist `visible`
    + `label` on display rows.
  - Diff bookkeeping: collect a `display_changes` list of
    `{"source_type", "source_field", "changes": {...}}` for any
    display row whose `label`, `visible`, or `order` changed; track a
    `response_order_changed` boolean for the `instrument.fields_reordered`
    re-emit.
  - Audit emit:
    - When `response_order_changed`: emit `instrument.fields_reordered`
      (existing 10A event) with `detail.old_order` /
      `detail.new_order` lists of `field_key`. Scope stays
      response-field-only; display order is not folded into this
      event.
    - When `display_changes` is non-empty: emit
      `instrument.display_fields_saved` with the diff shape from D11.
      `detail.added` and `detail.removed` are **always empty lists**
      in 10B-2 (adds + deletes are row-level per D7); only
      `detail.updated` carries entries.
  - Return value: a small summary dict
    `{"display_changed": bool, "response_order_changed": bool}`
    so the route can shape its redirect (e.g. for a `?saved=1`
    flag if useful — out of scope for the slice plan to over-spec).

All helpers go on the `_can_edit_instrument` predicate at the route
layer, not inside the service (matches 10A's split: services raise
typed errors, routes translate to HTTP). No `_invalidate_if_validated`
calls inside the service — that's also a route-layer concern.

### Slice 2 — Routes for display fields + bulk save

In `app/web/routes_operator.py`:

- New helper `_require_display_field_in_instrument(dfid, instrument,
  db)` mirroring `_require_response_field_in_instrument`.
- New POSTs (all gated on `_require_instrument_editable` + flow
  through `_invalidate_if_validated` per D10):

| Verb / path | Service call | Redirect |
|---|---|---|
| `POST .../display-fields` | `add_display_field` | `/instruments` (303); `DisplaySourceError` → re-render with `?display_source_error=<code>` query (mirrors 10A's `field_key_error` pattern). |
| `POST .../display-fields/{dfid}/edit` | `update_display_field` | `/instruments` (303). |
| `POST .../display-fields/{dfid}/delete` | `delete_display_field` | `/instruments` (303). |
| `POST .../fields/save` | `bulk_save_fields` | `/instruments` (303). On payload-shape errors (e.g. unparseable `order`), HTTP 400 + inline error on the redirect; ignore unknown row IDs defensively per D7. |

- Form input shapes (locked here so the template + tests can be
  written against a stable contract):
  - **Add display field**: `source_type` (select; values
    `reviewee` / `pair_context`), `source_field` (select; populated
    by the template from the seven allowed pairs minus what the
    instrument already has), `label` (text, optional), `visible`
    (checkbox, default checked).
  - **Edit display field**: `label` (text, optional), `visible`
    (checkbox). The form does not expose `(source_type,
    source_field)` since they are immutable; the route re-loads
    them from the DB row.
  - **Delete display field**: no form fields (single submit button).
  - **Bulk fields-save**: a list of rows where each row carries
    hidden `kind` (`display` | `response`), hidden `id`, an `order`
    `<input type="number">`, and — display rows only — a `visible`
    checkbox plus a `label` text input. The list is rendered server-
    side in the operator's chosen interleave (the template feeds
    today's stored merged sort; operator changes `order` numerics
    to interleave). Form names follow Starlette's repeated-key
    convention: `kind`, `id`, `order`, `visible`, `label` repeated
    once per row, parsed by the route via
    `request.form().getlist(...)`.

- `instruments_index` GET extends its template context with:
  - `instrument.display_fields` ordered list (already on the model
    via the existing relationship; no additional eager-load needed
    today since 10B-1's renderer is the only hot path that would
    care).
  - For each instrument, a `merged_field_rows` list pre-computed
    server-side with the "display before response" merged sort
    (mirrors the 10B-1 renderer rule). The bulk form renders this
    list in order; operator interleaves by changing `order` values.
    Each entry: `{"kind", "id", "order", "label", "visible",
    "response_field"}` for response rows or
    `{"kind", "id", "order", "label", "visible", "display_field"}`
    for display rows.
  - `available_display_sources: list[tuple[str, str]]` — the seven
    allowed source pairs minus those already on the instrument,
    used to populate the Add picker's `source_field` options.
  - `display_source_error: str | None` from a new `Query()` param
    matching the existing `field_key_error` plumbing.

- The legacy `instrument_detail` 303 (10A D12) keeps redirecting
  to `/instruments`; no new top-level routes to add.

### Slice 3 — Template + CSS

Edit `app/web/templates/operator/instruments_index.html`:

- **Display fields table per instrument** rendered above the
  existing "Response fields" table (since display fields default to
  rendering left of response fields per D5). Columns:
  - System pair (`<code>{{ source_type }}.{{ source_field }}</code>`).
  - Label (operator-typed value verbatim; muted "(Tag 1)" / "(Pair
    context 1)" hint underneath when the stored label is empty,
    pulled from the D6 `_DEFAULT_DISPLAY_LABELS`).
  - Visible (yes / no).
  - Order (numeric).
  - Actions: inline Edit (`<details>` toggle wrapping the edit
    form, mirrors 10A's response-field row), Delete (POST form,
    single button — no cascade-confirm since display fields carry
    no dependent data).
  Empty-state row: "No display fields. Reviewers will see only the
  reviewee identity column and response fields." (Should be
  unreachable today because 10B-1's `ensure_default_instrument`
  seeds three rows — but render the row defensively for the
  multi-instrument future.)
- **"Add display field" form** below the display table:
  - `<select name="source_type">` with options `reviewee` and
    `pair_context`.
  - `<select name="source_field">` populated server-side from
    `available_display_sources` filtered by the chosen source type.
    Since there's no JS, the picker is rendered as one combined
    `<select>` with options like
    `<option value="reviewee:tag_1">reviewee.tag_1 — Tag 1</option>`
    and the route parses the colon-delimited value back into
    `(source_type, source_field)`. This avoids JS-driven cascading
    selects and stays consistent with the rest of the operator UI.
  - `<input name="label">` (optional).
  - `<input type="checkbox" name="visible" value="true" checked>`.
  - Submit button `Add display field`.
  - All inputs gated on `{% if not can_edit %}disabled{% endif %}`.
- **Shared "Field order & visibility" bulk form** below the existing
  Add-response-field form (so the per-instrument card flows: friendly
  description → display fields table + Add → response fields table +
  Add → bulk fields-save form). Renders one row per
  `merged_field_rows` entry with hidden `kind` + `id`, numeric
  `order`, visible checkbox (display rows only), and label text
  (display rows only). One Save button per instrument. Numeric
  inputs only — no JS reorder UX per D13.
- **Display-source error banner** rendered at the top of the affected
  per-instrument card when `display_source_error` is set on the
  query string, mirroring the 10A `field_key_error` banner pattern.

CSS: no new rules. The existing `.table-scroll`, `.pill`, `.muted`,
and `details` styles cover everything.

### Slice 4 — Tests

Aim for ~12–14 cases across one new unit file plus targeted additions
to existing files. Unit tests use the in-memory SQLite fixture; route
tests use the existing `client` fixture.

**Unit (`tests/unit/test_display_field_builder.py`)**

1. `add_display_field` rejects an unknown `(source_type,
   source_field)` pair with `DisplaySourceError`; no row written.
2. `add_display_field` rejects a duplicate `(source_type,
   source_field)` on the same instrument; first row preserved.
3. `add_display_field` for a fresh `reviewee.tag_1` row appends at
   end (`order = N`) then repacks `0..N-1`; audits
   `instrument.display_field_added` with the row's full state.
4. `update_display_field` records only changed keys in
   `detail.changes`; a no-op edit produces an empty `changes` dict
   and audits exactly one event (matches 10A's `update_response_field`
   behaviour for parity).
5. `update_display_field` round-trips the empty-string `label`
   (`""` → `""`) and the `display_field_label` helper (10B-1) still
   falls back to the inferred D6 string at render time.
6. `delete_display_field` snapshots the row, deletes, repacks
   remaining display orders to `0..N-1`, and audits
   `instrument.display_field_deleted` with the snapshot.
7. `bulk_save_fields` repacks orders separately per table: a
   payload that interleaves `[display(tag_1), response(rating),
   display(tag_2), response(comments)]` produces display orders
   `[0, 1]` and response orders `[0, 1]` even though the merged
   submission positions were 0/2 and 1/3.
8. `bulk_save_fields` emits exactly one
   `instrument.fields_reordered` event when response orders change,
   with `old_order` / `new_order` as `field_key` lists scoped to
   response fields only.
9. `bulk_save_fields` emits exactly one
   `instrument.display_fields_saved` event with `detail.updated`
   populated and `detail.added` / `detail.removed` empty when only
   display fields' label / visible / order change.
10. `bulk_save_fields` emits zero events when the payload is a no-op
    (no order changes, no visibility changes, no label changes).

**Integration (`tests/integration/test_display_field_routes.py`)**

11. `POST .../display-fields` with `source_type=reviewee` /
    `source_field=tag_1` adds a row visible on the next GET; locked-
    when-`ready` returns 409. From `validated`, the session flips to
    `draft` and a `session.invalidated` audit event is written.
12. `POST .../display-fields` with an unknown source pair (e.g.
    `source_type=reviewee` / `source_field=phone`) redirects to
    `/instruments?display_source_error=…` and the next GET renders
    the error banner.
13. `POST .../display-fields` with a duplicate source pair
    (`pair_context.1` is already seeded) redirects with the error
    banner; row count unchanged.
14. `POST .../display-fields/{dfid}/edit` updates label + visibility;
    next GET reflects both. Locked-when-`ready` returns 409.
15. `POST .../display-fields/{dfid}/delete` removes the row and
    repacks remaining orders. Locked-when-`ready` returns 409.
16. `POST .../fields/save` with an interleaved payload reorders both
    tables independently and persists display visibility / label
    overrides; the next reviewer-surface GET reflects the
    interleave on the headers + cells (regression-guard for the
    10B-1 renderer × 10B-2 form contract).

**Targeted updates to existing files**

- `tests/integration/test_session_lifecycle.py`: assert each new
  display-field POST flips `validated → draft` (D10), mirroring the
  existing 10A response-field assertions.
- `tests/integration/test_instrument_builder_routes.py`: extend
  the locked-when-`ready` block to cover the four new POSTs (409
  on each). Existing 10A redirect-target assertions unchanged.

---

## Docs to update at PR time

- `docs/status.md`:
  - Timeline row: `2026-04-NN | Segment 10B-2 shipped (operator
    display-field builder + shared field-order bulk form)`.
  - Segments-shipped row: `10B-2 | Per-instrument display-fields
    picker on /operator/sessions/{id}/instruments: Add (selects
    from the seven D6 sources minus those already on the
    instrument) / Edit (label override + visibility) / Delete
    (no cascade-confirm). New shared "Field order & visibility"
    bulk form covering both display + response fields, interleaved
    in operator-chosen order, repacked 0..N-1 per table on save.
    Four new audit events: instrument.display_field_added,
    instrument.display_field_updated, instrument.display_field_deleted,
    instrument.display_fields_saved (bulk diff). Reuses
    instrument.fields_reordered (10A) when bulk save reorders
    response fields. Display-field mutations invalidate
    validated → draft and 409 when status=ready (mirrors 10A).
    | <date>`.
  - Audit table: add the four new events.
  - "What's deliberately not yet there": remove the 10B-2 picker
    row; keep the 10B-3 preview row.
- `AGENTS.md`: bump "Current stage" to mention 10B-2 (display-field
  picker UI on the per-instrument card; shared field-order bulk form;
  four new audit events; invalidation + locked-when-ready gating
  matches 10A). Update "Not yet implemented" to call out 10B-3 only.
- `spec/target_operator_map.md`: deferred to post-10B per umbrella
  D12. **No edit in 10B-2.**
- `spec/operator_map.md` (as-is map): refresh the `/instruments`
  page section to reflect the new display-fields card + bulk form.
  (As-is map gets its update here rather than at the umbrella close
  because it'd otherwise be stale until 10B-3 lands; 10B-3 only
  adds a new route, doesn't change `/instruments`.)
- `README.md`: only if a tooling / dependency change ships in 10B-2
  (none expected — the slice plan is pure server-rendered HTML +
  service helpers, no JS / build-step changes).

---

## Risk notes

- **Wide template diff on `instruments_index.html`.** Slice 3 adds
  three new sections per per-instrument card (display table, Add
  display, bulk fields-save). The card already has friendly-
  description form, response-fields table, Add response, and the
  9.1 acceptance / visibility forms. Land Slices 1 + 2 first as a
  self-contained service + route diff (the routes can render today's
  template and the template ignores the new context keys); the
  template-only diff in Slice 3 is then easy to review against a
  stable contract.
- **Bulk form parsing depends on Starlette's repeated-key
  convention.** Each row's `kind`, `id`, `order`, `visible`, `label`
  share their input names across the form. The route reads them
  via `await request.form()` and `getlist(...)` per name, then
  zips by index. Index-zip is fragile if any input is omitted —
  e.g. unchecked `visible` checkboxes don't submit a value, so the
  zipped lists drift. Use a hidden `<input type="hidden"
  name="visible_present" value="1">` per display row to mark
  rows that should consult the checkbox state, or render explicit
  `<input type="hidden" name="visible" value="off">` ahead of the
  checkbox so an unchecked box still submits a value (sentinel
  pattern). Lock the sentinel pattern at implementation time and
  document it in the route docstring.
- **`(source_type, source_field)` is immutable post-create.** The
  Edit form deliberately omits both fields. A future requirement
  to "change a row from `tag_1` to `tag_2`" would need to be
  modelled as Delete + Add. Today's allowlist (seven sources, no
  re-targetable display fields) makes this a non-issue;
  multi-instrument support (Segment 13) doesn't change it.
- **Shared bulk form vs row-level edit divergence.** The bulk form
  carries `label` and `visible` for display rows; the row-level
  Edit form carries the same. If an operator edits both tabs in
  parallel, the last-write-wins pattern applies (no optimistic
  locking, mirrors 10A). Document in the route docstring;
  acceptable for a single-operator session.
- **Response-field visibility is not in the bulk form.** Per D7,
  display rows carry `visible`; response rows carry only `order`.
  Response-field visibility today means `help_text_visible`, which
  has its own per-field toggle (10A). The bulk form deliberately
  does not subsume that toggle — it'd require a third response-row
  input column and inflate the form complexity. Lock here; revisit
  if the operator UX feels asymmetric in practice.
- **Audit-event count under no-op bulk saves.** Slice 4's test 10
  guards against accidentally emitting `instrument.fields_reordered`
  or `instrument.display_fields_saved` when nothing actually
  changed (e.g. operator clicks Save without touching a row).
  Verify both per-table change-detection paths early-return before
  `write_event`.
