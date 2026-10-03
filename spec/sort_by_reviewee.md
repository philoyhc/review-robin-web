# Sort by Reviewee — functional spec

Two sorts on one data set: the **operator's default** row order for an
instrument's reviewer surface, and the **reviewer's live override** on
top of it. The shared `↕`-button primitive that carries the second is
`base.html`'s, not this feature's alone.

**The primitive is table-agnostic.** A new sortable table opts in with
template-and-route work only — the annotation contract plus the shared
JS — and nothing in this spec changes. The current adopter list is
under "Implementation pointers" below.

This file is the source of truth for the design: edits here propagate
to the implementation, not the other way around.

---

## Rationale

The reviewer surface renders one row per assignment per instrument. With no sort configured the row order is **implicit insertion order** — whatever the assignments service produced, which serves neither of the two needs the feature exists for:

- **Operator side:** "Sort by cohort, then by name" before the reviewer ever sees the form. A deliberate default that frames the work the way the operator wants the reviewer to encounter it.
- **Reviewer side:** "Let me sort by my own scores so I can see what I rated high." Live, working-flow ergonomics during the review.

Sort is **row sorting**, distinct from **Order** (column ordering on the same surface, via ▲/▼ buttons). The two are independent: the operator sets columns left-to-right via Order, and rows top-to-bottom via Sort.

---

## Scope: Display Fields only on the operator side

The operator's default sort is restricted to **Display Fields** — reviewee attributes that exist at form-render time (name, profile_link, tag_1/2/3, pair_context_1/2/3). **Email is not a key** (findings A29): it shares the identity column with the name, whose badge sorts by name, and a save drops a key naming it. Only the save drops one: a key already stored (nothing current writes one) still sorts the reviewer surface until the card is next saved, and Duplicate, Replicate and the Settings CSV carry it as they find it.

**Response Fields are excluded** from the operator-side sort. No response data exists when the form first renders, so sorting by it would produce empty-cell sorts that shuffle as the reviewer types — surprising and useless.

The reviewer-side override at view time spans **both display and response fields** — once the reviewer has data, sorting by their own ratings is natural.

---

## Operator UI: sort badges on the Band 2 preview headers

(Author's ruling, 2026-10-02, findings A22.) The operator sets the default
sort from the column headers of the per-instrument card's Band 2 preview
("Preview review instrument", `spec/instruments.md`), the table that mirrors
the reviewer surface. **No Sort column on the Display Fields table, no new
card, no separate sort-builder dialog.** Each controllable header carries a
badge button (`.sort-btn`) that reads `↕` while the column is not in the
spec and `N↑` / `N↓` while it is the Nth key.

Where the control lives:

- **Display-field columns** — each carries its own badge.
- **The Reviewee identity header** — its badge sets the Name field's key.
  Email shares that cell and has no control of its own, so the operator
  cannot sort by it. With Name not selected the header carries no control.
- **A group-scoped instrument** — only the Group header carries a badge
  (the `-1` key; see "Group-scoped instruments").
- **Response columns** — an inert `↕` only. Response Fields are excluded
  from the operator-side sort (see "Scope").

### Click semantics: per-column cycle with priority

A click acts on its own column and leaves the others where they are. It
**appends**; it does not replace the cascade, which is the reviewer-side
behavior (next section).

| State | Click |
|---|---|
| Unsorted (`↕`) | → ascending, at the next free priority. At three keys it is refused with an alert. |
| `N↑` | → `N↓`, same priority. |
| `N↓` | → unsorted. Every key numbered after it moves up one, so the numbers stay contiguous. |

The live state is the list of `(display_field_id, dir)` in priority order.
Each click rebuilds it into the hidden `sort_display_field_id` / `sort_dir`
inputs that ride the card's `dfsave-{id}` form, and the Save request carries
them as parallel arrays.

### Locked / unlocked

- **Locked (default):** no buttons. A column in the spec shows its badge as
  static text; every other sortable header shows the inert `↕`.
- **Unlocked (Edit):** the badges are buttons. A click marks the card dirty.
- **Save:** the card's consolidated Save persists the spec through
  `set_sort_display_fields` — emits the audit event and lifecycle-invalidates
  `validated → draft`. A rejected spec comes back as a save error on the card.
- **Cancel:** reloads the card from persisted state, discarding the unsaved
  sort with the other edits.

---

## Reviewer UI: header buttons, view-time override

The reviewer surface table renders with the operator's configured sort
applied. Each sortable header carries a `↕` button (`rrw-sort-btn`) that runs
the shared `rrwSortHeaderClick`. The reviewer's override is a cascade of at
most three keys (author's ruling, 2026-10-02, findings A23):

- **Plain click** on a column that is not sorted, or that is one of several
  sorted columns → the cascade becomes that column alone, ascending
  (**replace**, not append).
- **Plain click** on the sole sorted column → ascending, then descending,
  then cleared.
- **Shift-click** on an unsorted column → appended to the cascade,
  ascending. Ignored once the cascade holds three keys.
- **Shift-click** on a sorted column → ascending, then descending, then
  dropped from the cascade; the other keys keep their order.
- **No Reset control.** The way back to the operator default is to clear
  the cascade, which expires the cookie (below).

The operator default carries no badges on the reviewer surface; a badge
appears only for a key in the reviewer's own cascade.

The reviewer's override **spans both display and response columns**. Sort by display field is a read on existing reviewee data; sort by response field is a read on the reviewer's own response values (their `100int` rating, their `Yes_no` choice, etc.).

**Persistence: per-browser cookie.** The reviewer-side override
persists in a `rrw-sort-rs-{session_id}-{instrument_id}` cookie scoped
to `/me/sessions/{id}`. The cookie carries the canonical
`[{"key": "...", "dir": "asc|desc"}, ...]` shape, **percent-encoded**
(the browser primitive writes it via `encodeURIComponent`); the server
reads it at render time, `unquote()`-s the raw value before
`json.loads`, and threads the decoded spec through
`views.order_rows_by_sort_spec`. Clearing the sort writes an expired
cookie, returning the next render to the operator default. Cookie
scope is per-(browser, session, instrument) — different browsers /
devices / cleared cookies all return cleanly to the operator default.

**Who applies which key on load** (ruling A27). The server cannot
sort by response values, so the work splits by what the stored spec
holds:

- **A display-only spec is applied by the server** (`reviewee.name`,
  `reviewee.email_or_identifier`, `display:N`). It replaces the
  operator default rather than tie-breaking with it, so rows tied on
  every cookie key stay in insertion order. The page lands in it with
  no client reorder.
- **A spec holding any `response:N` key is applied by the on-load
  script.** The decoder returns no override for it, so the server
  renders the operator default. `_rrwHydrateFromCookies` in
  `base.html` then re-sorts the rows by the whole spec, display keys
  included, through `_rrwApplySort`: the routine a header click runs,
  comparing with `_rrwCompareValues` and firing `rrw:sorted`.
  Rows tied on every key keep the order the script found them in,
  which is the operator default. **A reload therefore shows exactly
  the order the click produced, ties and blank cells included, when
  that click was made on a page with no stored sort.** A click on such
  a page also finds the rows in the operator default.
- **Group instruments** are covered by the same script. The server
  ignores their cookie (see "Group-scoped instruments"), and a group
  table's only sortable headers are its response columns.
- **The exception is a display-only spec.** The server compares the
  way Python does: case first, digit runs as text, and ties left in
  insertion order. A click compares with `localeCompare`
  (`{numeric: true}`) and breaks ties by the order the page was in
  when the first sort ran on it — the operator default on a page with
  no stored sort. The
  two can differ on mixed-case or numbered values and on tied rows.
  This predates A27.
- **A click made over a stored display-only sort is a second
  exception.** That page is in the server's display-sorted order, and
  the click's first `_rrwApplySort` stamps `rrwOriginalIndex` from it,
  so ties break by the old display sort. The reload of the resulting
  response-key cookie breaks them by the operator default instead. For
  example, with an operator default of name descending, Charlie = 2,
  Alpha = Bravo = 4, and Delta and Echo unanswered: click Name,
  reload, click Rating. The click shows
  `Charlie, Alpha, Bravo, Delta, Echo`, and the reload that follows
  shows `Charlie, Bravo, Alpha, Echo, Delta`. Only the order of rows
  tied on every key differs; the design accepts this.
- On every load, `_rrwHydrateFromCookies` redraws the badges from the
  cookie, whichever of the two applied the spec.

**The `unquote()` is not optional, and a test cannot be trusted to
say so.** Starlette does not percent-decode cookie values, so without
it `json.loads` fails on the browser's own encoding and SSR falls back
to the operator default — silently, because the on-load script still draws
the badge from the cookie and, for a display-only spec, does not
re-sort. A cookie-decoding test must therefore write the value the
way the browser writes it; one that sets raw JSON exercises nothing.

**Persistence is safe because the sort is visible.** Every sortable
header carries a `rrw-sort-badge`: `↕` while the column is not in the
sort, and the column's priority number plus `↑` / `↓` while it is. A
sort persisted weeks ago therefore announces itself on the columns it
orders, rather than quietly reordering a page the reviewer took to be
unsorted.

---

## Storage

New JSON column on `Instrument`:

```python
sort_display_fields: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
```

Shape:

```json
[
  {"display_field_id": 5,  "dir": "asc"},
  {"display_field_id": 12, "dir": "asc"},
  {"display_field_id": 7,  "dir": "desc"}
]
```

- Up to 3 entries; service-enforced (DB doesn't enforce a length cap).
- `dir ∈ {"asc", "desc"}` — service validates.
- `display_field_id` references `instrument_display_fields(id)` — service drops an id that is not this instrument's (see "Cascade behaviour") or that names the reviewee email (see "Scope") — or is the `-1` Group sentinel, which is kept (see "Group-scoped instruments").
- Empty list `[]` or NULL → fall back to **implicit insertion order** (today's behaviour, zero change for existing sessions).

JSON over three explicit FK columns: simpler schema, easier to extend to 4+ slots later if it ever matters, and the FK-orphan risk is small (handled by render-time defense + auto-compact on next save). See "Cascade behaviour" below.

---

## Cascade behaviour

When a Display Field is deleted (cascade from instrument or per-row delete):

- **Render-time defense:** the reviewer-surface sort code skips any `sort_display_fields` entry whose `display_field_id` no longer exists. Render falls back to the next-priority slot, then to insertion order.
- **Auto-compact on next save:** when the operator next saves the instrument card, the service drops any stale references and re-numbers the remaining priorities to be contiguous. Audit event captures the cleanup as part of the same `instrument.sort_fields_updated` diff.

No explicit FK / cascade migration is needed. The defense is one if-statement at render and a service-side filter at save.

---

## Default state and migrations

- New column added via Alembic migration with a NULL default.
- Backfill is a no-op — every existing instrument starts with `sort_display_fields = NULL`, which renders as today's implicit insertion order.
- New instruments default to NULL.

Zero behaviour change for any existing session until an operator explicitly configures sort.

---

## Audit event

`instrument.sort_fields_updated`, emitted via the canonical
`audit.changes(...)` envelope (`spec/architecture.md` "Audit-event
detail schema") with a single before/after pair on
`sort_display_fields`:

```python
payload=audit.changes({"sort_display_fields": [old_value, normalised]})
```

`old_value` / `normalised` are the full pre- / post-save spec lists
(`[{"display_field_id": …, "dir": "asc|desc"}, …]`), so the audit row
carries the complete before/after snapshots and stands on its own
without a join to the previous event. The service skips the emit
entirely on a no-op save (when `old_value == normalised`).

---

## Lifecycle behaviour

Sort config edits **invalidate `validated → draft`** via `lifecycle.invalidate_if_validated()`, as every other instrument-mutating service does. Setting a sort doesn't change assignment data, but it changes the reviewer-facing form render, which the validation snapshot covers.

The instrument card's edit lock applies — whenever the session is **not editable** (`ready`, `expired` or `archived`) the sort badges render locked alongside the rest of the card, and the operator must leave that state to change them. Nothing in the badges reads the lifecycle directly: they are buttons only while the card is unlocked, and `editing_instrument_id` is forced to `None` whenever `can_edit` — `lifecycle.is_editable` — is false (`app/web/views/_instruments.py`), so the three non-editable states are covered by one predicate rather than by each badge's own guard. The way out is the state's own: Revert to draft from `ready` or `expired`, Unarchive from `archived` (`spec/lifecycle.md` §5).

Reviewer-side override is view-only and never invalidates anything.

---

## Multi-instrument sessions

Each instrument has its own `sort_display_fields` spec, independent of other instruments. A reviewer with assignments across two instruments sees each instrument's table sorted by that instrument's own configuration.

The Display Fields available to sort are scoped to the instrument's own display fields — the operator can't reference another instrument's display field as a sort key.

---

## Group-scoped instruments

A group-scoped instrument (`Instrument.group_kind` set; `spec/instruments.md`) renders one row per group rather than one per reviewee, and sorts differently on both sides:

- **Default order.** `_collapse_group_rows` (`app/web/routes_reviewer/_surface/_group_collapse.py`) emits the group rows in ascending order of their group key — the tuple of boundary tag values from `responses.group_keys`, or `()` when the instrument has no boundary tag. A group row carries no per-reviewee display cells or sort values, so display-field entries in the spec are not applied.
- **The `-1` key.** `GROUP_IDENTITY_SORT_KEY` (`-1`, in `app/services/instruments/_display_fields.py`) is a sentinel `display_field_id` for the composed Group cell, not an `instrument_display_fields` row. `set_sort_display_fields` keeps it where it would drop an unknown id, and `order_rows_by_sort_spec` exempts it from the known-id filter. The operator sets it from the sort badge on the Group header of Band 2's group preview. On a group instrument it is the only entry the reviewer surface reads (`app/web/routes_reviewer/_surface/_context.py`): `"dir": "desc"` reverses the default group-key order, `"asc"` keeps it. On a per-reviewee instrument it resolves to no value on every row and changes nothing.
- **No server-side reviewer override.** The Group header carries no `↕` button, and the server does not read the `rrw-sort-rs-{session_id}-{instrument_id}` cookie for a group instrument. Its response-column headers keep their `↕` buttons, so a reviewer can still reorder the group rows in the browser by their own answers, and the on-load script re-applies that order from the cookie on the next visit.

---

## Out of scope for the initial slice

- Sort by **Response Fields** on the operator side. Excluded by design (see "Scope" above).
- **Multi-column sort beyond 3.** Diminishing returns; the catalog can re-open the cap if a real session needs it.
- A separate **sort-builder card or dialog**. The design constraint is "no new card; the sort lives on the Band 2 preview's column headers."
- Sort by **computed values** (e.g., per-reviewer "completion %"). Display fields and response fields only.
- Sort **across instruments** (e.g., a session-wide sort applied to every instrument). Each instrument is independent by design.
- Mass operator UI for "apply this sort to every instrument" (could be added later as a bulk action).
- **Cross-browser persistence** of any sort (operator setup tables OR reviewer surface). Cookie-only; sort doesn't follow the user to a different device. Revisit only if pilot feedback specifically asks.

---

## Implementation pointers

Key landmarks in the codebase:

- **Schema:** `Instrument.sort_display_fields` JSON column.
- **Service:** `app/services/instruments/_display_fields.py
  ::set_sort_display_fields` with `SortSpecError` (codes
  `too_many` / `unknown_dir` / `duplicate_id` / `bad_id`; an id
  that is not this instrument's display field is dropped, per
  "Cascade behaviour", and so is the reviewee email's, per "Scope").
- **Audit event:** `instrument.sort_fields_updated` registered
  in `app/services/audit.py::EVENT_SCHEMAS`.
- **Read path:** `app/web/views/_sort.py
  ::order_rows_by_sort_spec` (pure-function reviewer-surface
  helper); generic `decode_cookie_sort_spec` +
  `apply_cookie_sort` for the operator-table cookies;
  `decode_cookie_sort_spec_for_reviewer_surface` for the
  reviewer surface. Both decoders `unquote()` the raw cookie
  value before `json.loads` (the browser writes it
  percent-encoded; Starlette does not percent-decode cookie
  values).
- **Operator template** (`instruments_index.html`): the
  Band 2 preview's headers carry `<button class="sort-btn">`
  badges (`sortBadgeHtml`); `toggleSort` cycles state into
  hidden `sort_display_field_id` / `sort_dir` form arrays.
  Save path: `instrument_consolidated_save` (and the no-JS
  `instrument_bulk_save_fields`) in
  `app/web/routes_operator/_instruments.py`.
- **Shared sort primitive:** `base.html` ships the
  `rrwSortHeaderClick` + `_rrwApplySort` + cookie-I/O JS;
  every sortable table gains a tiny `↕` button next to
  the column label (the click target) via the
  `rrw-sort-btn` class. Since 19O Item 4 the primitive also
  **removes any injected `.session-expander` panel** before it
  collects or stamps rows, and **dispatches `rrw:sorted`** on
  the table once the rows have landed, for pages that re-anchor
  a panel. Mechanism and the per-page migration state are in
  `spec/ui_elements.md` under `.session-row-selected`.
- **Reviewer template** (`review_surface.html`) +
  **operator tables** — Reviewers / Reviewees / Relationships
  (Setup), Assignments / Invitations / Responses (Operations), and
  the Sessions lobby and Archived sessions page
  (`app/web/routes_operator/_lobby.py`): each annotated with
  `<table data-rrw-sortable="...">`, `th.rrw-sortable`,
  `data-sort-key`, `data-sort-value` cells, and
  `<tbody class="rrw-rows">`.
- **Wrapper rows need a resolver.** The four rosters hand
  `apply_cookie_sort` rows whose sort keys are their own attributes,
  so a plain `getattr` suffices. Invitations and Responses do not:
  their rows are per-reviewer / per-reviewee **view wrappers**, so
  `_operations.py` passes a resolver that reaches through
  (`row.reviewer.name`, `row.reviewee.tag_1`) and derives the
  progress keys as a **completion percentage** rather than a raw
  count. `apply_cookie_sort` collapses `""` to `None` and sorts
  `None` last in both directions, matching the client comparator —
  so a row with nothing to do lands in the same place server-side
  and after a click.
- **Assignments is not in that group**, and must not be folded back
  into it: its sort translates to `ORDER BY` in
  `assignments.list_pairs` rather than running through
  `apply_cookie_sort`, so sorting composes with paging over the whole
  matching set instead of reordering one fetched page — see
  `spec/assignments.md` "Sorting the pair list".
- **Cookies:** `rrw-sort-{surface}-{session_id}[-{instrument_id}]`
  carrying the canonical
  `[{"key": "...", "dir": "asc|desc"}, ...]` shape,
  percent-encoded (`encodeURIComponent`) — the SSR decoders
  `unquote()` before parsing. The two session-list pages carry no
  session id: `rrw-sort-lobby` and `rrw-sort-archived`, which the
  primitive scopes to path `/` rather than to a session's path.
- **Tests:**
  - `tests/unit/test_order_rows_by_sort_spec.py` — the pure helper.
  - `tests/integration/test_set_sort_display_fields.py` — the
    service writer and its `SortSpecError` codes.
  - `tests/integration/test_instruments_sort_column.py` — the
    operator sort badges' save path.
  - `tests/integration/test_reviewer_surface_sort.py` +
    `tests/integration/test_reviewer_surface_sort_cookies.py` — the
    reviewer surface and its cookie.
  - `tests/integration/test_setup_tables_sort.py` — the four roster
    tables.
  - `tests/integration/test_assignments_sort.py` — Operations
    Assignments (the `ORDER BY` path).
  - `tests/integration/test_operations_sort.py` — Operations
    Invitations + Responses.

---

## Doc cross-references

- **`spec/operator_ui_concept.md`** — per-instrument Display Fields card layout, and the shared `rrw-sort` primitive's adopter list.
- **`spec/reviewer-surface.md`** — the review-surface table these sorts order.
- **`spec/quick_setup_card_spec.md`** — adjacent operator-card design pattern (single source of truth for an operator-side feature spec).
- **`guide/archive/segment_13B_sort_tables.md`** — the implementation plan, for the record of how this landed.
