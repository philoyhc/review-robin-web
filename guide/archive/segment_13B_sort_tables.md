# Segment 13B — Sortable tables (reviewer surface + operator surface)

> **Archived 2026-05-12.** Part 1 (PRs **#867 / #868 / #869**)
> + Part 2 (PRs **#873 → #878**, including refinement #878)
> all shipped 2026-05-12 — 9 PRs total + the diagnostic
> Instrument column (#870) on the path. PR F (per-instrument
> Assignments after 15B) carved out to 15B Slice 4c. Plan
> stays here as historical context; the canonical user-facing
> contract lives in `spec/sort_by_reviewee.md` and the per-PR
> Done entries live in `guide/todo_master.md`. The
> `spec/sort_by_reviewee.md` "Implementation pointers" section
> maps the shipped landmarks in the codebase.

Implementation plan for clickable column sort across the
reviewer surface AND the operator setup tables. Part 1 (3 PRs,
shipped 2026-05-12) is the reviewer-surface story laid on top
of the canonical functional spec at
[`spec/sort_by_reviewee.md`](../../spec/sort_by_reviewee.md).
Part 2 (5 PRs + refinement, shipped 2026-05-12) lifts the same
primitive into the operator surface — Reviewers, Reviewees,
Relationships, and Operations Assignments — with cookie-backed
per-(session, table) persistence so the sort survives reloads
on the same browser.

> **Renamed 2026-05-07** from `segment_13B_instrument_enhance.md`.
> **Scope extended 2026-05-12** from "sort by reviewee" to the
> broader "clickable sort across every interesting tabular
> surface" once the reviewer-surface primitive shipped and the
> operator follow-on became the obvious next step. Section titles
> below name the source spec where each surface is documented;
> this plan owns the sequencing + persistence wiring.
> **Renamed again 2026-05-12** from `segment_13B_sort_by_reviewee.md`
> to `segment_13B_sort_tables.md` so the filename matches the
> widened scope; cross-references in `spec/`, `guide/`, and
> `docs/` updated in the same commit.

## Status

**Part 1 shipped 2026-05-12** (3 PRs **#867 / #868 / #869**) —
operator-default sort spec stored on `Instrument.sort_display_fields`,
tri-state Sort column on the per-instrument Display Fields
card, reviewer-side live override on the response-table column
headers.

**Part 2 shipped 2026-05-12** (5 PRs **#873 / #874 / #875 /
#876 / #877**, plus refinement PR **#878**). Lifts the
reviewer-surface sort primitive into a site-wide
`base.html` script, adds cookie-backed persistence so the
sort survives reloads on the same browser, and rolls the
same affordance into the four operator-surface tables
(Reviewers / Reviewees / Relationships / Operations
Assignments). PR #878 refined the click target to a small
`↕` button next to each column label so the sort affordance
is discoverable on first paint.

**Part 2 PR F (per-instrument Assignments after 15B) carved
out to 15B Slice 4c** — see
`guide/archive/segment_15B_per_instrument_assignments.md`.

Refreshed 2026-05-12 against the as-shipped 13D scaffolding.
**Schema already in place** since Segment 13D PR 5
(`instruments.sort_display_fields` JSON column, NULL by
default), so PR 1 of this plan no longer needs to author the
migration. Settings CSV import/export round-trips the column
already (`app/services/session_config_io.py` lines 330-331 +
1020-1021), so the porting story is also covered.

**No 13F schema work needed for Part 2.** Cookie persistence
is per-(operator browser, session, table); no DB column
required. If pilot feedback later wants cross-browser
persistence ("my sort followed me to my laptop"), a
`users.ui_sort_preferences` JSON column would be its own small
migration carved out of 13F at that time — not committed in
this plan.

Sized as **3 PRs** in dependency order:

1. **PR 1 — Reviewer-surface read path + service writer
   (sort spec consumption + validator).** Schema column
   already exists; the work here is:
   - Update the column's docstring to match the canonical
     spec shape (currently drifted — says `source_type` /
     `source_field` / `direction`, should say
     `display_field_id` / `dir`).
   - New service helper
     `instruments.set_sort_display_fields(db, *, instrument,
     fields, user, correlation_id)` with the validator
     (length ≤ 3, IDs belong to this instrument, no
     duplicates, `dir ∈ {"asc", "desc"}`), lifecycle-
     invalidation hook, and emit of the new
     `instrument.sort_fields_updated` audit event.
   - Register `instrument.sort_fields_updated` in
     `EVENT_SCHEMAS`.
   - Reviewer-surface render adapter reads
     `instrument.sort_display_fields or []` and passes a sort
     spec into the row-ordering helper.
   - New pure-function helper
     `views.order_assignments_by_sort_spec(rows, sort_spec)`
     ordering assignment-shaped row tuples by the spec's keys
     (cascade by list order; NULLs sort last regardless of
     direction per spec §"NULL handling"; unknown-id entries
     skip with a fallback to insertion order per
     spec §"Render-time defense").
   - Tests pin: NULL/empty render unchanged (insertion order);
     single-key asc/desc; cascade; NULL handling; unknown-id
     defense; service validator rejects each documented
     invalid input; audit event fires on diff; no emit on
     no-op save; lifecycle-invalidates.
2. **PR 2 — Operator UI: tri-state Sort column.** Adds the
   "Sort" column to the per-instrument Display Fields table
   (only — no equivalent on Response Fields, per the spec).
   Click-to-promote + click-to-reverse + click-to-demote, max
   3 keys, display fields only. Save passes the operator's
   `[(display_field_id, dir), ...]` list into PR 1's
   `set_sort_display_fields` service writer.
3. **PR 3 — Reviewer-side live override.** Clickable column
   headers on the reviewer surface (display + response
   columns). Live-only persistence (no localStorage, no
   per-reviewer server state). Refresh returns to the operator
   default. Header arrows reflect the live sort state.

Sequencing rationale:

- PR 1 ships infrastructure end-to-end: validator + service
  writer + reviewer-surface render-path consumer + audit
  event. No operator UI yet — the column populates only
  through Settings CSV import or direct DB edits during PR 1,
  but the render path is ready to honour whatever value lands
  in the column.
- PR 2 is the operator-facing PR. Once it lands, sessions
  whose operators configure sort get a deliberate default
  order.
- PR 3 lights up the reviewer-side override on top of PR 2's
  default. Independent of PR 2 in code (a separate column-
  header set), but PR 2 ships first because the operator
  default is the load-bearing experience.

Each PR ships independently on top of `main`. PR 1 + PR 2 can
fold if the validator + render path is small and the operator
UI is ready; PR 3 is its own PR.

## Relationship to Segment 13A and 13C

13A, 13B, and 13C are siblings — independent of each other,
shippable in any order. Together they cover the original
"Segment 13 — rule-based assignment + sort UX" framing in the
master workplan, plus the group-scoped enhancement that surfaced
later.

- **13A** — rule-based assignment generation (Advanced mode +
  seed library + editor + retire Full Matrix card). Plan at
  [`archive/segment_13A_rulebased_assignment_builder.md`](archive/segment_13A_rulebased_assignment_builder.md).
- **13B** (this segment) — sort by reviewee.
- **13C** — group-scoped instruments + duplicate-instrument
  button. Plan at
  [`segment_13C_enhanced_instrument.md`](segment_13C_enhanced_instrument.md).

The three segments touch different surfaces:

- 13A — assignments page; new `RuleSet` schema.
- 13B — instrument card's Display Fields table + reviewer-
  surface table headers; new `Instrument.sort_display_fields`
  JSON column.
- 13C — instrument card's action-row buttons; new
  `Instrument.group_kind` column + `Assignment.context` keys
  (no `Response` schema change).

No cross-dependencies in either direction.

## Schema

**Already shipped.** Segment 13D PR 5 (#701, 2026-05-09)
added the JSON column on `Instrument`:

```python
sort_display_fields: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
```

Documented value shape (from `spec/sort_by_reviewee.md`):

```json
[
  {"display_field_id": 7, "dir": "asc"},
  {"display_field_id": 12, "dir": "desc"}
]
```

`NULL` and `[]` both mean "no operator-configured sort"
(insertion order — today's behaviour). Up to 3 entries.
PR 1's service-layer validator on save enforces:

- Length ≤ 3.
- Each `display_field_id` belongs to **this instrument's**
  display fields (cross-instrument display-field IDs rejected).
- No duplicate `display_field_id` within the list.
- `dir` ∈ `{"asc", "desc"}`.

> **Docstring drift to fix in PR 1.** The column docstring in
> `app/db/models/instrument.py` was written against an earlier
> design (`source_type` / `source_field` / `direction` keys).
> The canonical shape is `display_field_id` / `dir` per the
> functional spec; PR 1 updates the docstring.

CSV round-trip already covered: `session_config_io.py`
serialises the column as the `Instruments.sort_display_fields`
key in Settings CSV (lines 330-331 export, 1020-1021 import).
No additional porting work needed in 13B.

## Audit event

`instrument.sort_fields_updated` — emitted by PR 2's save path
when `sort_display_fields` changes. Detail follows the canonical
envelope from Segment 11K (the audit-event detail schema shipped
2026-05-07):

```python
audit.changes(
    {"sort_display_fields": [before, after]},
    session=review_session,
)
```

PR 2 registers the event_type in `audit_service.EVENT_SCHEMAS`
per the 11K convention.

## Out of scope

- **Sort by computed values** (cross-table joins, response
  aggregates) — not covered by the spec.
- **Cross-instrument session-wide sort** — each instrument has
  its own sort.
- **More than 3 sort keys** — keep the cognitive load low.
- **Persisted reviewer overrides** — live-only by spec.
- **An "apply sort to every instrument" bulk control** — not
  in the first cut.

## PR-by-PR sketch

### PR 1 — Reviewer-surface read path + service writer

Schema column already in place since 13D PR 5. Round-trip
tests already pin NULL / empty / populated persistence at
`tests/integration/test_instrument_sort_display_fields_schema.py`.
This PR adds the consumer (render path) + writer (service
validator) so the column stops being inert.

- **Docstring fix.** Update `Instrument.sort_display_fields`
  docstring to match the canonical
  `{"display_field_id": N, "dir": "asc|desc"}` shape (drifted
  from a prior design pass — calls out
  `source_type` / `source_field` / `direction` today).
- **Service writer.** New
  `instruments.set_sort_display_fields(db, *, instrument,
  fields, user, correlation_id)` in
  `app/services/instruments/_instrument_crud.py` (or a sibling
  module if scope fits cleaner — decide at scoping):
  - Accepts `fields: list[tuple[int, str]]` (display_field_id,
    dir) pairs.
  - Validator: length ≤ 3, each id ∈ this instrument's
    display fields, no duplicates, `dir ∈ {"asc", "desc"}`.
  - Idempotent: returns early on no-op (same fields). PR 1
    tests pin "no emit on no-op save."
  - Lifecycle-invalidation hook (per
    `invalidate_if_validated` convention).
  - Emits `instrument.sort_fields_updated` audit event with
    canonical envelope:
    `audit.changes({"sort_display_fields": [before, after]},
    session=review_session)`.
- **Audit registration.** New event_type
  `instrument.sort_fields_updated` in
  `audit.EVENT_SCHEMAS` (`_IDENTITY | {"changes"}`).
- **Reviewer-surface render-path consumer.** Wherever the
  per-instrument render adapter loops rows
  (`app/web/views/_responses.py` or the analogous reviewer-
  side helper), thread the sort spec from
  `instrument.sort_display_fields or []` through the row
  ordering. PR 1 confirms the threading on a fixture; PR 2's
  operator UI provides the live operator-set values.
- **Row-ordering helper.** New pure function
  `views.order_assignments_by_sort_spec(rows, sort_spec)` in
  `app/web/views/_audit_log.py`'s sibling module (TBD at
  scoping — likely `app/web/views/_reviewer_surface.py` if
  it exists, otherwise a new `_sort.py`):
  - Cascade by list order (first entry primary, second
    secondary, etc.).
  - NULLs sort last regardless of direction
    (per spec §"NULL handling").
  - Unknown-id entries (referenced display field no longer
    exists) skip with a fallback to the next-priority slot,
    then insertion order
    (per spec §"Render-time defense").
- **Tests.**
  - **Unit (helper).** NULL/empty input → unchanged order;
    single-key asc/desc; multi-key cascade; NULL value
    handling regardless of direction; unknown-id entry
    skipped + falls to next slot.
  - **Unit (service writer).** Validator rejects each
    documented invalid input (length 4, duplicate id,
    cross-instrument id, unknown dir); audit event fires on
    diff; no emit on no-op save; lifecycle-invalidates when
    the session was previously validated.
  - **Integration (reviewer surface).** When
    `sort_display_fields` is `NULL` or `[]`, row order is
    unchanged from today (insertion order). When populated,
    rows render in the spec's order.

### PR 2 — Operator UI: tri-state Sort column

- New "Sort" column on the per-instrument Display Fields table
  (`spec/instruments.md` Section B). Display fields only —
  Response Fields rows do not get a Sort cell (per spec
  §"Scope on the operator side").
- Click semantics per spec §"Operator UI: tri-state Sort
  column": unsorted → asc → desc → unsorted; clicking a sorted
  column promotes / demotes within the cascade order (max 3).
- Operator state lives in `[(display_field_id, dir), ...]` —
  serialised in a hidden form field and submitted with the
  bulk-save round-trip the card already uses.
- Save route passes the parsed list straight into PR 1's
  `instruments.set_sort_display_fields` service writer (which
  owns the validator + lifecycle hook + audit emission).
  Validation errors bubble up as banner errors on the page.
- Tests:
  - Tri-state click cycle + promote/demote/swap.
  - Route layer surfaces the service writer's validation
    errors as banners (rejection cases pin against the PR 1
    error codes / messages).
  - Reviewer-surface integration test confirms a configured
    sort propagates into the rendered row order via PR 1's
    render-path consumer.

### PR 3 — Reviewer-side live override

- Clickable column headers on the reviewer-surface table —
  display columns + response columns (per spec §"Reviewer UI:
  clickable column headers, live-only override"). Tri-state
  cycle, multi-key cascade with shift-click (or click-twice
  semantics if shift-click is awkward — pick at implementation
  time).
- Live-only: state lives in JS memory; refresh returns to
  operator default. No localStorage, no server-side per-
  reviewer state, no audit event (per spec §"Persistence: live
  only").
- Header arrows reflect the live state; the operator default
  arrows render server-side, the live overrides take effect on
  the first click.
- Tests:
  - JS unit test (or DOM-rendered integration) on cycle +
    cascade.
  - Server-side render unchanged when no override is in play
    (regression for PR 2's persistence contract).

---

## Part 2 — Operator-surface rollout + cookie persistence

PRs 4-8. Lifts the reviewer-surface sort primitive (the inline
JS in `review_surface.html` + the `<th data-sort-key>` /
`<td data-sort-value>` annotation contract) into a reusable
client-side module, then applies it to each operator setup /
operations table that today renders an inert HTML table:

- **Reviewers Setup page** (`/operator/sessions/{id}/reviewers`).
- **Reviewees Setup page** (`/operator/sessions/{id}/reviewees`).
- **Relationships Setup page** (`/operator/sessions/{id}/relationships`).
- **Operations Assignments page**
  (`/operator/sessions/{id}/assignments`).

Audit log is **intentionally out of scope** — filtering +
search in the in-app viewer (16C PRs 1-3) already cover the
"find specific events" use case that sort would otherwise
serve. Lifting sort onto the audit log surface stays a "ship
if pilot feedback asks" item.

### PR 4 — Shared client-side sort primitive (~250 LOC)

**Goal.** Extract the inline JS in `review_surface.html`
(`rsSortHeaderClick`, `_rsApplySort`, `_rsRefreshSortBadges`,
`_rsCompareValues`) into a reusable script that any page can
opt into without re-implementing the cycle / cascade /
null-last / numeric-compare logic.

**Ships.**

- Move the JS into `app/web/templates/base.html` as a single
  inline `<script>` (no JS build pipeline, no asset module
  per project conventions). Naming flips from `rs*` to
  generic `rrwSort*`.
- Selector contract: any `<table data-rrw-sortable="{key}">`
  with `<th class="rrw-sortable" data-sort-key="...">` headers
  and `<td data-sort-value="...">` cells binds automatically
  on page load.
- Optional `data-sort-type` per header (e.g. `"Integer"`,
  `"Decimal"`, default string) for numeric vs locale-string
  compare.
- Reviewer surface re-binds to the shared script — no
  behaviour change. The `data-rs-sortable-table` attribute
  renames to `data-rrw-sortable` (cookie keys carry the
  surface as a prefix; see PR 5).
- New `app/web/views/_sort.py` already houses the pure-
  Python sort helper from PR 1; PR 4 doesn't touch it. The
  JS lives separately (it's a presentation primitive).

**Tests.**

- Reviewer-surface tests already cover the JS-bound markup;
  PR 4 should not regress them. Add one targeted test
  asserting the renamed `data-rrw-sortable` attribute lands
  on the per-instrument tables.
- Snapshot the shared script's presence in `base.html` so
  future template-only PRs don't accidentally regress the
  primitive into per-page duplicates.

### PR 5 — Cookie persistence (~200 LOC)

**Ships.**

- Per-(session, table) cookies — naming convention
  `rrw-sort-{surface}-{session_id}[-{instrument_id}]`
  (e.g. `rrw-sort-reviewers-17`,
  `rrw-sort-reviewer-surface-17-3`).
- Cookie scope: `Path=/operator/sessions/{id}` or
  `/reviewer/sessions/{id}`, `SameSite=Lax`, NOT
  `HttpOnly` (the JS reads them).
- Cookie value: JSON-encoded `[{"key": "...", "dir":
  "asc|desc"}, ...]` in cascade order. Same shape as the
  operator-default `Instrument.sort_display_fields` so the
  reviewer surface can degrade to the operator default
  cleanly.
- **JS:** write on every state change; read on
  `DOMContentLoaded` (before binding so the initial
  badges + row order are correct).
- **SSR:** the route layer reads the cookie at render time
  and threads the parsed spec into the template's render
  loop, so the initial HTML lands in the cookie-saved
  order. Avoids the "flicker" where rows briefly render in
  default order before the JS re-sorts. Reuses PR 1's
  `views.order_rows_by_sort_spec` helper on the server
  side.
- Cookie size: cap at ~256 bytes total per cookie
  (3 keys × ~30 char key + dir = comfortably under). If
  the operator hammers a long-key column (e.g.
  `display:99999`), the JS truncates to 3 keys before
  encoding.

**Reviewer surface picks up persistence automatically** —
the existing `rrwSortHeaderClick` handler from PR 4 just
gets cookie I/O added to it.

**Tests.**

- Cookie I/O round-trips on the reviewer surface
  (integration: set state → assert cookie set on response →
  GET again → assert sort badges seeded + row order
  matches).
- Malformed cookie (manual tamper) is silently ignored —
  initial render falls back to operator default.
- Cookie scope is `/{surface}/sessions/{id}` so leaking
  across sessions can't happen.

### PR 6 — Reviewers + Reviewees Setup tables (~300 LOC)

**Ships.**

- Annotate both Setup page templates with the
  `data-rrw-sortable` table marker + `rrw-sortable` th
  classes + `data-sort-key` / `data-sort-value`
  attributes.
- Sortable columns: identity (name + email_or_identifier),
  Tag1 / Tag2 / Tag3 columns when populated, Active /
  Inactive status, any other operator-facing cells worth
  sorting.
- Cookie keys: `rrw-sort-reviewers-{session_id}` and
  `rrw-sort-reviewees-{session_id}`.
- Both Setup tables share the row shape pattern (status
  pill column on the right, identity on the left, tags in
  between); one PR for both since the diff is repetitive.

**Tests.**

- Each table renders the sort scaffolding (markers +
  classes + data attributes).
- Cookie round-trip: set state via cookie, hit GET, assert
  rows render in the cookie order.

### PR 7 — Relationships Setup table (~150 LOC)

**Ships.**

- Same treatment for the Relationships page table
  (`/operator/sessions/{id}/relationships`).
- Sortable columns: Reviewer identity, Reviewee identity,
  Tag1 / Tag2 / Tag3 (when populated), status pill.
- Cookie key: `rrw-sort-relationships-{session_id}`.

**Tests.**

- Scaffolding + cookie round-trip, as PR 6.

### PR 8 — Operations Assignments table (~150 LOC)

**Ships.**

- Sort headers on the per-pair Operations Assignments
  table at `/operator/sessions/{id}/assignments`. The
  diagnostic Instrument column from PR #870 (2026-05-12)
  is sortable too.
- Sortable columns: Reviewer, Tag columns (reviewer +
  reviewee + pair), Reviewee, Include pill, Instrument.
- Cookie key: `rrw-sort-assignments-{session_id}`.
- The existing per-column visibility toggle (localStorage-
  backed `assignment-col-toggle`) keeps doing its job —
  sort and visibility are orthogonal.

**Tests.**

- Scaffolding + cookie round-trip, as PR 6.

### Post-MVP — PR F (per-instrument Assignments after 15B)

**Defer to 15B's plan.** 15B introduces per-instrument
assignment tables; that surface should get the sort
facility too, but the work lives in 15B since it's coupled
to the new surface. Flag in 15B's PR ladder.

---

## Doc impact

**Part 1 (shipped 2026-05-12).**

- `guide/todo_master.md` — Done entry for Part 1.
- `spec/sort_by_reviewee.md` — implementation-pointers
  section can tick off as Part 1 shipped; the
  "Persistence: live only" line on the reviewer side
  flips with Part 2 PR 5 (cookies are still per-browser
  / per-device, but the JS-memory-only framing relaxes
  once cookies are in).

**Part 2 (per PR).**

- Update `spec/operator_ui_concept.md` to describe the
  sort facility on operator setup tables (new "Sortable
  columns" subsection? — decide at PR 4 scoping).
- Update `spec/setup_pages.md` to note sort affordance on
  Reviewers / Reviewees / Relationships tables.
- Update `spec/sessions_overview.md` if the lobby gets
  the same treatment in a future slice (out of Part 2's
  scope — flag if pilot wants it).
- `spec/settings_inventory.md` — new browser-local UI
  state row for the cookie family
  `rrw-sort-{surface}-{session_id}[-{instrument_id}]`.
- `guide/todo_master.md` — Done entry per PR; final
  archive of this file once PR 8 ships.
- `spec/sort_by_reviewee.md` — Part 2's cookie
  persistence flips the reviewer-side "Persistence: live
  only" line (cookies are still per-browser, but no
  longer JS-memory-only).
