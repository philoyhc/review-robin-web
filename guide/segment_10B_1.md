# Segment 10B-1 Implementation Plan — Data-driven reviewer-surface render

**Status:** Plan drafted — decisions locked, slice breakdown below.
First of three PR-sized blocks for Segment 10B (display-fields picker
+ operator preview). See `guide/segment_10B.md` for the umbrella stub
that breaks 10B into 10B-1 / 10B-2 / 10B-3, and
`guide/segment_10_instrument_builder_mvp_plan.md` §14 for the
segment-level split. 10B-1 follows 10A (shipped) and precedes 10B-2.

- **10B-1 (this doc):** Alembic backfill migration, `ensure_default_instrument`
  seeding three pair-context rows, reviewer-surface refactor to render
  from `InstrumentDisplayField` (replacing hard-coded `pair_context_*`),
  reviewee identity column wiring, default-label inference. **Ships
  behavior-preserving** — no operator UI yet.
- **10B-2 (next):** display-field picker UI on the per-instrument card
  (row-level add / edit / delete POSTs + shared bulk "field order &
  visibility" form), invalidation + locked-when-ready gating, the four
  new audit events.
- **10B-3 (last):** `GET /operator/sessions/{id}/preview` with synthetic
  rows, disabled inputs, banner.

---

## 10B-1 outcome

One PR that ships:

- One Alembic revision that backfills three `InstrumentDisplayField`
  rows per existing instrument (`pair_context_1/2/3`), and updates
  `ensure_default_instrument` to seed the same three rows on every
  newly created instrument.
- The reviewer surface (`reviewer/review_surface.html`) refactored to
  loop over each instrument's `InstrumentDisplayField` rows in their
  stored order, with the reviewee identity column always rendered as
  the fixed first column.
- A small label-inference helper used by the renderer when an
  `InstrumentDisplayField.label` is NULL or empty.

Behavior unchanged otherwise: no operator-facing UI for managing
display fields yet (10B-2), no preview route yet (10B-3). On every
existing session, reviewers see the same three columns in the same
order they see today; the change is purely how those columns are
sourced.

---

## Decisions locked for 10B-1

### D2 — Backfill migration scope

Single Alembic revision. For every existing instrument, write three
`InstrumentDisplayField` rows for `pair_context_1/2/3`
(`source_type="pair_context"`, `source_field="1"|"2"|"3"`,
`visible=true`, `order=0..2`, `label=NULL`) **unconditionally** —
including instruments that already carry display-field rows. Picks
option (b) from the original 10B open question:
destructive-but-consistent.

`ensure_default_instrument` updates to seed the same three rows on
every newly created instrument.

No new columns on `instrument_display_fields` — the existing schema
(`label`, `source_type`, `source_field`, `order`, `visible`) is
already sufficient.

### D4 — Reviewee identity column is fixed

Always-first column on the reviewer surface: reviewee `name`
(primary) with `email_or_identifier` beneath in smaller font, same
cell. **Mandatory.** Not represented by an `InstrumentDisplayField`
row, not toggleable, not reorderable. Renderer hard-codes this
column ahead of the display-field loop.

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

A small helper (e.g. `display_field_label(field)`) does the lookup.
Operator-typed labels are stored verbatim and round-tripped — the
helper only kicks in for NULL / empty.

The four `reviewee` sources are listed here so the helper covers them
end-to-end; only the three `pair_context` sources are seeded by the
backfill in 10B-1, the `reviewee` rows enter via the picker in 10B-2.

### D5 (partial) — Default ordering on a freshly seeded instrument

Display fields first, in slot order — `pair_context_1/2/3` at
`order=0..2`, then response fields at `order=0..N-1` (their existing
seed order). Reviewer-surface columns render left to right as:

1. Reviewee identity (always first; D4).
2. Visible display fields and response fields, **interleaved** by
   merged sort across `(table, order)` pairs.
3. Per-row submitted-status indicator (rightmost; today's behavior).

In 10B-1 there is no operator interleaving — display fields all sort
before response fields by construction (display `order=0..2`,
response `order=0..N-1`, table tiebreaker puts display first). The
bulk form that lets the operator interleave lands in 10B-2; the
renderer in 10B-1 already implements the merged-sort rule so 10B-2
adds zero render-side change.

### D6.1 — `profile_link` rendering

When `source_type="reviewee"` and `source_field="profile_link"`, the
cell renders as a plain `<a>` to the stored URL with the URL as link
text (no truncation, no icon). Empty / NULL values render as an
empty cell.

This is the only display-field source whose cell is not a plain text
escape; locking it in 10B-1 keeps the picker decision in 10B-2 from
having to revisit cell-level rendering.

---

## Audit events added in 10B-1

None. 10B-1 ships data-driven render only; mutations land in 10B-2.

The Alembic backfill itself does not emit application-level audit
events (consistent with prior backfill migrations in this codebase —
e.g. the `Instrument.description` provisioning).

---

## Out of scope for 10B-1 (explicitly deferred)

- Display-field picker UI on the per-instrument card → 10B-2.
- Row-level add / edit / delete POSTs for display fields → 10B-2.
- Shared bulk "field order & visibility" form → 10B-2.
- The four new audit events (`instrument.display_field_added` /
  `_updated` / `_deleted` / `instrument.display_fields_saved`) → 10B-2.
- `_invalidate_if_validated` + `_can_edit_instrument` gating on
  display-field mutations → 10B-2.
- `GET /operator/sessions/{id}/preview` route, synthetic-row helper,
  disabled-inputs render, banner → 10B-3.
- `assignment_context_*` as a display-field source — deliberately
  excluded per 10B D1 (umbrella stub).
- `spec/target_operator_map.md` rewrite → separate post-10B PR per
  10B D12.

---

## Implementation slices

### Slice 1 — Alembic backfill migration + `ensure_default_instrument` seeding

- New revision file under `alembic/versions/`, e.g.
  `<rev>_segment_10b1_display_field_backfill.py`. `down_revision =
  "4e8a2b9c3d11"` (Segment 10A's `help_text` revision; tip of `head`
  today). Pure-DML migration — **no DDL changes** per umbrella D2
  ("no new columns").
- `upgrade()` body, in two passes within a single transaction:
  1. `DELETE FROM instrument_display_fields WHERE source_type =
     'pair_context' AND source_field IN ('1', '2', '3')` — clears any
     existing pair-context seed rows so the re-seed is idempotent
     and consistent across instruments. Per umbrella D2:
     "unconditionally — including instruments that already carry
     display-field rows."
  2. `INSERT INTO instrument_display_fields (instrument_id,
     source_type, source_field, label, "order", visible)
     SELECT id, 'pair_context', s.slot, '', s.idx, true FROM
     instruments CROSS JOIN (VALUES ('1', 0), ('2', 1), ('3', 2))
     AS s(slot, idx)` — three rows per instrument in one statement.
     SQLite + Postgres both support this; verify locally with the
     existing `postgres-migration` smoke job pattern.
- `downgrade()` mirrors the upgrade's filter:
  `DELETE FROM instrument_display_fields WHERE source_type =
  'pair_context' AND source_field IN ('1', '2', '3')`. Operator-typed
  `reviewee` rows added later via 10B-2 are left intact.
- **Seed `label=''` rather than SQL NULL.** Sub-decision locked at
  implementation time: `instrument_display_fields.label` is
  currently `nullable=False` in the model. D6 already treats "NULL
  or empty" as equivalent for the inference helper, so empty string
  preserves the umbrella decision intent without an `ALTER COLUMN`
  change. Land a one-line clarification in `segment_10B.md`'s D2
  text in the same PR (`label=NULL` → `label='' (empty string;
  treated identically to NULL by the D6 inference helper)`) so docs
  and migration stay aligned.
- `app/services/instruments.py::ensure_default_instrument`: add a
  `_DEFAULT_DISPLAY_FIELDS` constant near the existing
  `DEFAULT_RESPONSE_FIELDS` and a `has_display_fields` probe
  mirroring today's `has_fields` block. When the probe returns
  False, insert three rows with `(source_type='pair_context',
  source_field='1'|'2'|'3', label='', order=0|1|2, visible=True)`.
  No audit event (mirrors today's response-field seed: silent
  bootstrap).
- Land Slices 1 + 2 atomically — the `postgres-migration` smoke job
  in PR CI exercises the upgrade against a real Postgres before any
  renderer reads the new rows.

### Slice 2 — Display-field helpers + label inference

New module-level additions to `app/services/instruments.py`:

- `_DEFAULT_DISPLAY_LABELS: dict[tuple[str, str], str]` — the seven
  `(source_type, source_field)` → inferred-label mappings from D6
  (umbrella). Module-level constant alongside `DEFAULT_RESPONSE_FIELDS`.
- `display_field_label(field: InstrumentDisplayField) -> str`:
  - When `field.label` (after `.strip()`) is non-empty, return it
    verbatim — no normalisation beyond strip-on-read so operators
    can store labels with intentional padding (matching today's
    `_instrument_label` helper that strips before render).
  - Else look up `_DEFAULT_DISPLAY_LABELS[(field.source_type,
    field.source_field)]`.
  - Defensive fallback for unknown source pairs:
    `f"{field.source_type}:{field.source_field}"`. The picker in
    10B-2 enforces the seven-source allowlist; the fallback keeps
    a malformed row from crashing the reviewer surface.
- `display_field_value(field: InstrumentDisplayField,
  assignment: Assignment) -> str | None`:
  - `("pair_context", "1"|"2"|"3")` →
    `(assignment.context or {}).get(f"pair_context_{field.source_field}")`.
  - `("reviewee", "tag_1"|"tag_2"|"tag_3"|"profile_link")` →
    `getattr(assignment.reviewee, field.source_field, None)`.
  - Returns `None` when the source is absent or the value is empty
    / falsy. Renderer handles `None` as an empty cell.
  - Defensive fallback for unknown source pairs: `None` (silent
    empty cell; pairs with the label fallback above).

Both helpers are pure functions over already-loaded ORM objects —
no DB access — so the renderer can call them in a tight per-row
loop without N+1 risk. Easy to unit-test in isolation.

No new service-layer mutations, no new audit events.

### Slice 3 — Reviewer-surface renderer refactor

In `app/web/routes_reviewer.py` (the `_render_session_surface` /
equivalent function that builds `instrument_groups`):

- Eager-load `Instrument.display_fields`. Add `selectinload(
  Instrument.display_fields)` to the existing `_instruments_for_session`
  query, **or** issue a single `select(InstrumentDisplayField)
  .where(instrument_id IN [...]).order_by(order, id)` and bucket by
  `instrument_id` into `display_fields_by_instrument`. Pick whichever
  matches the surrounding query style; both avoid the per-instrument
  N+1 risk noted below.
- **Drop** the per-row `pair_contexts = []` build (lines around
  `routes_reviewer.py:204-209`) and the `"pair_contexts": pair_contexts`
  key on the row dict.
- **Add** a per-row `display_cells: list[dict]` built from the
  instrument's **visible** display fields, in stored `order` ascending,
  shape:
  ```python
  display_cells.append({
      "field": display_field,
      "label": instruments_service.display_field_label(display_field),
      "value": instruments_service.display_field_value(
          display_field, assignment
      ),
      "is_profile_link": (
          display_field.source_type == "reviewee"
          and display_field.source_field == "profile_link"
      ),
  })
  ```
- **Add** `display_fields` (visible only, ordered) to each
  `instrument_groups[i]` dict so the template can render headers
  without peeking inside the first row's cells.
- **Default ordering rule (D5, render-side half).** Display fields
  render left of response fields by construction in 10B-1: display
  orders 0..2 from the seed, response orders 0..N-1 from today's
  builder. The template emits display headers first, then response
  headers — no merged-sort logic in 10B-1. The bulk-form interleave
  contract (10B-2) extends this with a `(table_priority, order)`
  composite-key sort; 10B-1 ships only the simpler "display before
  response" merge.
- View-shape helper: if `app/web/views.py` already factors out the
  reviewer-surface group builder, mirror the new `display_cells` /
  `display_fields` keys there. Today's logic is inlined in the route;
  introducing a new helper module is **out of scope** for 10B-1 (keep
  the diff focused).

### Slice 4 — Reviewer-surface template refactor

Edit `app/web/templates/reviewer/review_surface.html`:

- **Identity cell (D4)** keeps today's render: `<strong>{{
  row.assignment.reviewee.name }}</strong><br><code>{{
  row.assignment.reviewee.email_or_identifier }}</code>`. **Remove**
  the inline `{% if row.pair_contexts %}…<div>P{{ slot }}: {{ value
  }}</div>…{% endif %}` block at lines ~99-105.
- **Header row** — between today's `<th>Reviewee</th>` and the
  response-field header loop, insert:
  ```jinja
  {% for field in group.display_fields %}
    <th>{{ field.label }}</th>
  {% endfor %}
  ```
  where `group.display_fields` is the list of dicts populated in
  Slice 3, each carrying `label` (already inferred). The trailing
  `<th style="width: 1%;"></th>` for the submitted-status column
  stays unchanged.
- **Data row** — between the identity `<td>` and the response cells
  loop, insert:
  ```jinja
  {% for cell in row.display_cells %}
    <td>
      {% if cell.is_profile_link %}
        {% if cell.value %}<a href="{{ cell.value }}">{{ cell.value }}</a>{% endif %}
      {% else %}
        {{ cell.value or "" }}
      {% endif %}
    </td>
  {% endfor %}
  ```
  Jinja's autoescape handles HTML safety on plain text values; the
  `<a href>` rendering for `profile_link` matches D6.1 (URL-as-text,
  no truncation, no icon).
- No CSS changes. Display-field cells inherit the table's cell
  styling. Empty values render as empty cells (no placeholder
  glyph) — matches today's response-cell behaviour for empty
  drafts.
- Template stays no-JS, no `<script>`. `<input>`s exist only on
  response columns; display columns are static text / anchor cells.

### Slice 5 — Tests

Aim for ~10–11 cases across one new unit file, one new integration
file, and one migration test, plus targeted updates to the existing
reviewer-flow test. Unit tests use the in-memory SQLite fixture;
route tests use the existing `client` fixture.

**Unit (`tests/unit/test_display_fields.py`)**

1. `display_field_label` returns the operator-typed `label` (after
   `.strip()`) when non-empty: `"  Cohort  "` → `"Cohort"`, mirrors
   the strip-on-read pattern from `_instrument_label`.
2. `display_field_label` falls back to the inferred label for each
   of the seven `(source_type, source_field)` pairs from D6
   (parametrised: one assertion per pair).
3. `display_field_label` returns the defensive fallback
   `"<source_type>:<source_field>"` for an unknown pair —
   regression guard against future migration drift.
4. `display_field_value` for `("pair_context", "1"|"2"|"3")` reads
   `assignment.context["pair_context_<slot>"]` and returns `None`
   when the key is missing or the value is empty / falsy.
5. `display_field_value` for each of the four `("reviewee", "tag_1"
   |"tag_2"|"tag_3"|"profile_link")` pairs reads the matching column
   via `getattr` and returns `None` when the column is `None`.
6. `ensure_default_instrument` on a freshly created session seeds
   exactly three `InstrumentDisplayField` rows with `(source_type=
   "pair_context", source_field="1"|"2"|"3", visible=True,
   order=0|1|2, label="")`.
7. `ensure_default_instrument` is idempotent — a second call on the
   same session does not duplicate display-field rows.

**Integration (`tests/integration/test_reviewer_surface_display_fields.py`)**

8. Reviewer surface renders three pair-context columns sourced from
   the seeded display fields. Assert one `<th>Pair context 1</th>`
   header (and 2, 3) and the values from
   `assignment.context["pair_context_1/2/3"]` appear as cell content
   outside the identity cell.
9. Pair-context values **no longer appear inside the identity cell**:
   the historical `"P1: morning"` substring is **absent** while
   `"morning"` itself appears in its dedicated `<td>` to the right
   of the identity cell. (Pairs with the targeted update to
   `test_reviewer_response_flow.py` below.)
10. `profile_link` column rendering: insert an
    `InstrumentDisplayField` row with `source_type="reviewee"`,
    `source_field="profile_link"` directly via the ORM (the picker
    UI lands in 10B-2). Assert the surface renders `<a href="…">…</a>`
    when the reviewee's `profile_link` is set, and an empty cell
    when it's `None`.

**Migration (`tests/migration/test_segment_10b1_backfill.py` —
or the existing migration-test pattern in this repo)**

11. Stamp the schema at revision `4e8a2b9c3d11`, insert one
    `Instrument` plus two pre-existing `InstrumentDisplayField`
    rows that match the upgrade's filter (e.g. `(pair_context, "1")`
    with `label="Stale"`), run `alembic upgrade head`, and assert
    the post-state has exactly three pair-context rows under that
    instrument with the seeded shape — pre-existing rows under the
    filter were replaced ("destructive-but-consistent" per umbrella
    D2). Operator-typed `reviewee` rows (if present in the fixture)
    are left untouched.

**Targeted updates to existing tests**

- `tests/integration/test_reviewer_response_flow.py::
  test_surface_renders_pair_context_and_default_fields` — replace
  `assert "P1: morning" in response.text` with assertions against
  the new column shape: a `<th>Pair context 1</th>` header and a
  cell containing `"morning"` outside the identity cell. The
  `assert "panel-1" not in response.text` (assignment_context
  exclusion) stays. Grep `tests/` for any other `"P1:"` /
  `"pair_contexts"` literal-string assertions before merging.

---

## Docs to update at PR time

- `docs/status.md`:
  - Timeline row: `2026-04-NN | Segment 10B-1 shipped (data-driven
    reviewer-surface render + display-field backfill)`.
  - Segments-shipped row: `10B-1 | Backfill migration seeding
    pair_context_1/2/3 InstrumentDisplayField rows on every
    instrument; ensure_default_instrument seeds the same three rows
    on new sessions; reviewer surface renders display fields as
    separate columns instead of inline in the identity cell;
    default-label inference for the seven D6 sources | <date>`.
  - Audit table: no change (10B-1 adds no audit events).
  - "What's deliberately not yet there": replace the existing
    "Display-fields picker / preview (10B)" row with two rows for
    the still-pending sub-PRs (10B-2 picker, 10B-3 preview).
- `AGENTS.md`: add a 10B-1 bullet to "Current stage" — ~3 lines on
  the backfill, `ensure_default_instrument` seeding, renderer
  refactor, and the fixed identity-column contract. Update
  "Not yet implemented" to call out 10B-2 and 10B-3 by name.
- `guide/segment_10B.md` (umbrella): clarify D2's `label=NULL` text
  to `label='' (empty string; treated identically to NULL by the D6
  inference helper)` per the Slice 1 sub-decision. One-line edit;
  ships in the same PR.
- `spec/target_operator_map.md`: deferred to post-10B per umbrella
  D12. **No edit in 10B-1.**
- `spec/operator_map.md` (as-is map): no change — 10B-1 doesn't
  touch the operator surface.
- `README.md`: only if a tooling / dependency change ships in 10B-1
  (none expected).

---

## Risk notes

- **Migration is destructive within its filter.** D2's
  "unconditionally" clause means `upgrade()` deletes every
  pre-existing `(source_type='pair_context', source_field IN
  ('1','2','3'))` row before re-seeding. `downgrade()` only removes
  rows the upgrade inserted, so a downgrade-then-upgrade cycle
  round-trips losslessly for the seeded shape but does **not**
  restore prior operator-typed labels on those three slots. Today's
  codebase has no operator-facing path that writes display-field
  rows, so the destructive scope is bounded to the seed itself.
  Document this in the migration's docstring.
- **Existing tests rely on the inline "P1: …" shape.**
  `tests/integration/test_reviewer_response_flow.py::
  test_surface_renders_pair_context_and_default_fields` is the
  known case (Slice 5 covers the rewrite). `grep -rn "P1:\|pair_contexts" tests/`
  before merging to catch any stragglers in newer test files.
- **N+1 risk on `Instrument.display_fields`.** Without a
  `selectinload`, the renderer hits the DB once per instrument when
  accessing `.display_fields`. Today's reviewer surface targets one
  instrument per session, so the regression is one extra query, but
  multi-instrument support (Segment 13) will multiply the cost. Wire
  the eager load in Slice 3 even though today's blast radius is
  small.
- **Header row depends on `group.display_fields`, not first-row
  peek.** Today's template uses `{% set first_row = group.rows[0] %}`
  to drive response-field headers. After 10B-1, display-field
  headers source from `group.display_fields` directly so they
  render even on a hypothetical zero-row group; the response-field
  header still uses the first-row peek. Today's renderer only adds
  groups with at least one assignment, so the divergence is
  invisible — but if Segment 13 surfaces empty-group rendering, the
  response-header loop will need to source from the instrument's
  `response_fields` directly. Note for forward-compat; **no change
  in 10B-1**.
- **Empty-string vs NULL `label` divergence with the umbrella stub.**
  Slice 1 seeds `label=''`; `segment_10B.md` D2 currently reads
  `label=NULL`. Land the one-line umbrella clarification in the
  same PR so the docs and migration agree (called out in "Docs to
  update" above).
- **Wide-but-shallow template diff.** Slice 4's template change
  inserts two new loops (header + data) into an existing table that
  already has the `<th>Reviewee</th>` + response-field loops. Land
  Slices 1 + 2 + 3 first as a self-contained schema + service +
  view-shape change; the template-only diff in Slice 4 is then easy
  to review against a stable contract.
