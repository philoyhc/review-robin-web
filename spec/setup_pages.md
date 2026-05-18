# Setup Pages — UI spec

Per-session **Setup Pages** are the per-entity import + edit
surfaces reachable from the chrome's Setup row:

| Page | URL | Template |
|---|---|---|
| Reviewers | `/operator/sessions/{id}/reviewers` | `session_reviewers.html` |
| Reviewees | `/operator/sessions/{id}/reviewees` | `session_reviewees.html` |
| Relationships | `/operator/sessions/{id}/relationships` | `session_relationships.html` |
| Instruments | `/operator/sessions/{id}/instruments` | `instruments_index.html` |
| Email Template | `/operator/sessions/{id}/setupinvite` | `session_setupinvite.html` |

Each Setup Page follows the same shell (chrome + Setup row +
status strip + a body of cards). The Reviewers, Reviewees, and
Relationships pages additionally render a **preview table** of the
session's current rows that all share a common visibility-toggle
pattern; this spec covers that shared pattern alongside the
per-page idiosyncrasies.

**Assignments retired from Setup row in Segment 15D PR 6a.** The
page moved to the Operations row and is no longer a per-entity
Setup primitive — pair-level context (formerly the
`PairContext1/2/3` / `AssignmentContext1/2/3` JSON columns) lives
on the first-class `relationships` table now, and the Operations
Assignments page is the materialised-derivative surface where the
operator runs the rule engine. See `spec/operator_ui_concept.md`
§5 and `spec/rule_based_assignment.md` §7.1 for the post-15D
Operations Assignments page contract.

For the cross-page chrome contract (two-row navigation, status
strip, lock cards, principles P1–P4), see
[`spec/operator_ui_concept.md`](operator_ui_concept.md). For the
Quick Setup card on Session Home that bulk-uploads into the same
import paths these pages expose, see
[`spec/quick_setup_card_spec.md`](quick_setup_card_spec.md).

## Shared body shape

Every Setup Page renders, top-to-bottom:

1. **Chrome** (`session-nav-card` partial — two-row top nav with the
   Setup row highlighted).
2. **Status strip** (`session_setup_status_row` partial) — counts
   pills per entity.
3. **"Fields with data" pill row** — badge per CSV column that has
   at least one populated value (`reviewer_fields_with_data` /
   `reviewee_fields_with_data` in `app/services/assignments.py`;
   `relationships.fields_with_data` in
   `app/services/relationships.py`). Drives operator awareness of
   which optional fields the latest import populated.
4. **Lifecycle gate cards** (when the session is Activated): a
   `card lock` carrying "The {entity} cannot be modified while the
   session is ongoing. Revert the session to draft if you wish to
   modify anything." with an inline Revert form. Sits **above**
   the friendly-label editor so the yellow card immediately
   follows the status info card — the same status-info-then-
   yellow-lock pattern the Instruments and Assignments pages use.
5. **Friendly-label editor (left) + Operator actions card
   (right)** — a half-width `bottom-grid` pair.
   - The **friendly-label editor** (Segment 15A Slice 3) is the
     inline editor card via
     `operator/partials/_field_labels_editor.html`. Reviewers +
     Relationships render a 3-cell row; Reviewees a 2-row stacked
     grid (identity + tags, 6 cells). Save + Cancel pair in
     Secondary style, both starting `disabled` until the form is
     dirty (inline JS toggles via an initial-value snapshot).
     POST handlers in
     `app/web/routes_operator/_setup_rosters.py` upsert / clear
     via `app/services/field_labels.py`.
   - The **Operator actions card** (Segment 15F) is the per-row
     authoring surface — search / status filter strip + a
     selection-driven button row (Edit · Inactivate · Activate ·
     Add new row). See "Operator actions card" below.
   - Both are gated by `is_ready`: when the session is Activated
     the friendly-label inputs render `disabled`, the
     Save/Cancel pair is suppressed, and the operator-actions
     button row renders inert; the lifecycle-gate card above
     carries the "revert to draft" prompt for that state.
6. **Preview table card** — Reviewers / Reviewees / Relationships.
   Always renders when the entity is non-empty (or when Add mode
   is active), regardless of lifecycle state. A **leftmost
   checkbox column** drives the operator-actions selection (a
   header select-all checkbox toggles every visible row). Column
   headers render the resolved friendly label via
   `operator/partials/_field_label_header.html`; when an override
   is set, the canonical name appears as `.field-label-canonical`
   muted subtext below the friendly label and the sort `↕`
   button. While a row is being edited (`?edit_id=`) or a blank
   Add row is active (`?add=1`), that row's cells render as
   inputs / pickers — see "Per-row Edit / Add / bulk actions".
7. **Body grid** — Upload + Danger Zone cards. Hidden when the
   session is Activated *or* while a row is being edited / added.
   Placed **after** the preview table so the operator's eye lands
   on the data they're managing first; the upload-CSV +
   delete-all destructive actions sit below the table as a
   deliberate de-prioritised cluster. CSV upload stays the
   bulk-create path; the Operator actions card covers single-row
   authoring.

## Preview tables (shared toggle pattern)

The Reviewers, Reviewees, and Relationships preview tables share
a **column-visibility chip row** that lets the operator hide
optional columns. The pattern (Segment 18E Part 1):

- A `Show columns:` chip row sits in the top "Fields with data"
  card, directly below the `Fields with data:` line. Each chip is
  a `<button class="col-chip" data-col-toggle="<slot>">` carrying
  the column's **friendly label** (the operator-set field label,
  falling back to the default — same label the header renders).
- Optional tag / context columns always render in the DOM (so
  empty columns can be revealed). Clicking a chip toggles
  per-column visibility via a CSS class on the table (e.g.
  `col-hidden-tag-1` → `display: none` for cells with class
  `tag-col-1`). The chip flips between filled (`is-selected`,
  column shown) and outline (column hidden), with `aria-pressed`
  tracking the state.
- Each chip defaults to **selected iff that column has at least
  one populated value** in the current preview rows.
- **Empty columns render the chip disabled** (`disabled
  aria-disabled="true" title="No data in this column"`, struck
  through). The operator can't toggle an empty column on, and
  stored "show" preferences carried over from a load when the
  column had data are ignored — the chip stays unselected and the
  column stays hidden until the next import populates it.
- The Reviewees row also carries a chip for the **profile-link
  column** (`data-col-toggle="profile"`, cells `class="profile-col"`).
  That column is server-rendered only when some row has a link, so
  its chip never reaches the disabled state.
- Operator choice persists per browser via `localStorage` under a
  per-page key:
  - Reviewers preview: `rrw-reviewer-tag-visibility`.
  - Reviewees preview: `rrw-reviewee-tag-visibility`.
  - Relationships preview: `rrw-relationship-tag-visibility`.
- Stored choice wins over the data-driven default for live chips.
  Stored "hide" keeps a populated column hidden; stored "show"
  reveals an explicitly-toggled-on column on next load. Disabled
  chips ignore storage entirely (see above).
- The inline JS targets `.col-chip` and early-returns on
  `chip.disabled` so listeners aren't bound and storage isn't
  applied.

The pattern is intentionally not extracted into a Jinja macro —
each page's column shape differs enough (Reviewees adds the
profile-link chip) that the inline JS + scoped `<style>` block per
template is more legible than a macro with a sprawling parameter
list.

## Sortable headers (shared affordance)

All three preview tables — Reviewers, Reviewees, Relationships
— **opt into the shared sort primitive** that
`spec/sort_by_reviewee.md` documents. Each table:

- Carries a `<table data-rrw-sortable="rrw-sort-{surface}-{session_id}">`
  marker. Surface tokens: `reviewers` / `reviewees` /
  `relationships`.
- Wraps its data rows in `<tbody class="rrw-rows">`.
- Renders every sortable header with `class="rrw-sortable"` +
  `data-sort-key="..."` + a child `<button class="rrw-sort-btn">`
  carrying the `↕` / `1↑` / `2↓` badge.

Cookie persistence is per-(browser, session, table) — see
`spec/settings_inventory.md` §7 for the cookie shape. Sort state
survives reloads on the same browser; clearing all cookies
returns to insertion order. The route layer reads the cookie at
render time so the initial HTML lands sorted (no JS-reorder
flicker on first paint).

Sortable columns per table:

- **Reviewers:** `name`, `email`, `tag_1` / `tag_2` / `tag_3`,
  `status`, `updated_at`.
- **Reviewees:** `name`, `email_or_identifier`, `tag_1` /
  `tag_2` / `tag_3`, `status`, `updated_at`. (The Photo column
  stays non-sortable — it renders a link, not a comparable
  value.)
- **Relationships:** `reviewer` / `reviewee` (both sort on the
  resolved member **name** — the prominent identity text since
  Segment 15F), `tag_1` / `tag_2` / `tag_3`, `status`,
  `updated_at`.

The right-end **Updated** column shows each row's `updated_at`
timestamp (`%Y-%m-%d %H:%M`); sorting it descending surfaces the
most recently added / edited rows. Freshly inserted rows carry
`updated_at == created_at`; a per-row edit bumps it. The
server-rendered Add / Edit rows show `—` in this cell (no
committed value yet).

Sortable affordance and visibility-toggle affordance are
orthogonal — toggling a column's visibility doesn't affect its
sort state, and a sort spec referencing a hidden column still
applies (the column data is still present in the DOM).

## Operator actions card (Segment 15F)

The right half of the `bottom-grid` pair (friendly-label editor
on the left). It is the per-row authoring surface — operators no
longer round-trip a CSV bulk-replace to fix one name, retire one
person, or add one row. Top-to-bottom:

1. **Search + filter strip.** A search box (name / email
   typeahead, backed by a `<datalist>` of the unfiltered
   roster's distinct values) plus, on Reviewers / Reviewees, a
   **Status** filter (`all` / `active` / `inactive`). Relationships
   substitutes a **Search by** dropdown (Reviewer / Reviewee —
   picks which side of the pair the search box matches) since a
   relationship has no single status-vs-roster distinction worth
   a filter. Apply submits a GET; a Clear link resets it.
2. **Selection-driven button row** — **Edit**, **Inactivate**,
   **Activate**, **Add new row**, plus a selected-count pill.
   Buttons enable / disable from the checkbox selection (see
   below). The row greys out (`is-locked`) while a row is being
   edited / added; a focused **Save / Cancel** pair renders
   below a divider in that state.

The list is **capped at 200 rows** (lifted to **500** when a
search or status filter is applied) — the cap is applied after
sort, so the visible window matches the operator's chosen order.
A "Showing N of M" hint renders when the cap or filter trims the
list.

## Per-row Edit / Add / bulk actions (Segment 15F)

**Selection.** The leftmost checkbox column is the sole selection
mechanism — rows carry no per-row action buttons. Button state:

| Selection | Edit | Inactivate / Activate | Add new row |
|---|---|---|---|
| 0 rows | disabled | disabled | enabled |
| 1 row | enabled | enabled | disabled |
| ≥2 rows | disabled | enabled | disabled |

**Edit** (`?edit_id=<id>`) and **Add** (`?add=1`) are
server-rendered states — no client-side DOM surgery. The target
row's cells render as `<input>` / `<select>`; Add prepends a
blank row at the top of the table. The Operator actions card
swaps its filter strip + button row for the focused Save /
Cancel pair. Editing a row's **status** to `inactive` /
`active` is the inactivate / reactivate path — there is no
separate per-row toggle. **Inactivate** / **Activate** flip the
`status` of every checkbox-selected row in one POST (reversible,
so no confirm checkbox).

After an Edit or a bulk action the redirect **preserves the row
selection** (`?selected=` query params re-check those rows) and
the **active search / status filter** (so the operator lands
back on the same filtered view, not the unfiltered list). CSV
bulk upload stays as the bulk-create path.

**Relationships pickers.** The Relationships Edit / Add rows
choose reviewer + reviewee via **name-or-email search-box
pickers** — a text `<input>` backed by a `<datalist>` of
`"Name (handle)"` options (inactive members suffixed
`— inactive`), not a native `<select>`. This scales past
1,000-row rosters; the submitted label resolves back to a roster
id server-side. Add is disabled with a hint when either roster
is empty — a pairwise relationship needs both sides.

Mutating service modules: `app/services/reviewers.py` /
`reviewees.py` and the per-row mutators on `relationships.py`.
Audit events: `reviewer.created` / `.updated` /
`.bulk_inactivated` / `.bulk_reactivated` and the parallel
`reviewee.*` / `relationship.*` families.

## Reviewers page (`session_reviewers.html`)

### Body grid (after the preview table, when not Activated)

Two-column `bottom-grid` placed **below** the preview table so
the operator's eye lands on the data first; the upload + delete-
all destructive actions cluster as a deliberate de-prioritised
section beneath:

- **Left:** `Upload Reviewers` card. Required CSV columns
  `ReviewerName`, `ReviewerEmail`; optional `ReviewerTag1..3`. POSTs
  to `/operator/sessions/{id}/reviewers/import`. When existing rows
  are present, surfaces a "Yes, replace the existing N reviewers
  (and delete K assignments)" confirm checkbox.
- **Right:** `Danger Zone` card with "Delete all reviewers". Only
  rendered when at least one reviewer exists.

### Preview table

| # | Column | Toggle? | Notes |
|---|---|---|---|
| 0 | (select) | — | Leftmost checkbox column — per-row select + header select-all; drives the Operator actions card |
| 1 | Name | — | `reviewer.name` |
| 2 | Email | — | `<code>{{ reviewer.email }}</code>` |
| 3 | Tag1 | ✓ | `data-col-toggle="tag-1"` / `class="tag-col tag-col-1"` |
| 4 | Tag2 | ✓ | `data-col-toggle="tag-2"` / `class="tag-col tag-col-2"` |
| 5 | Tag3 | ✓ | `data-col-toggle="tag-3"` / `class="tag-col tag-col-3"` |
| 6 | Status | — | `reviewer.status` |
| 7 | Updated | — | `reviewer.updated_at` (`%Y-%m-%d %H:%M`) |

The `Show columns:` chip row sits in the top "Fields with data"
card; see "Preview tables (shared toggle pattern)" above for
default-state and persistence rules.

## Reviewees page (`session_reviewees.html`)

### Body grid (when not Activated)

Same two-column shape as Reviewers — Upload card on the left,
Danger Zone on the right. CSV header copy lists `RevieweeName`,
`RevieweeEmail` required; `PhotoLink`, `RevieweeTag1..3` optional.

### Preview table

| # | Column | Toggle? | Notes |
|---|---|---|---|
| 0 | (select) | — | Leftmost checkbox column — per-row select + header select-all; drives the Operator actions card |
| 1 | Name | — | `reviewee.name` |
| 2 | Email / Identifier | — | `<code>{{ reviewee.email_or_identifier }}</code>` |
| 3 | Photo | ✓ | Conditional: rendered only when at least one reviewee has `profile_link`. Cell renders `<a href="…" target="_blank">link</a>`. `data-col-toggle="profile"` / `class="profile-col"` |
| 4 | Tag1 | ✓ | `data-col-toggle="tag-1"` / `class="tag-col tag-col-1"` |
| 5 | Tag2 | ✓ | `data-col-toggle="tag-2"` / `class="tag-col tag-col-2"` |
| 6 | Tag3 | ✓ | `data-col-toggle="tag-3"` / `class="tag-col tag-col-3"` |
| 7 | Status | — | `reviewee.status` |
| 8 | Updated | — | `reviewee.updated_at` (`%Y-%m-%d %H:%M`) |

Whether the Photo column renders at all is governed by whether any
reviewee has a populated `profile_link` in the current preview
rows; when it renders, its `Show columns:` chip can hide / show it
like the tag columns. Position 3 sits between the identity columns
and the toggleable tag columns so the canonical column order is
consistent across reviewers / reviewees.

## Relationships page (`session_relationships.html`)

The home for **pair-level context** — the `relationships` table
seeded in Segment 13E PR 2 and lit up by this Setup page in
Segment 15D PR 2. One row per `(reviewer, reviewee)` pair within
a session, carrying three `tag_N` slots consumed by the rule
engine via the `pair_context.tag1` / `pair_context.tag2` /
`pair_context.tag3` predicate field names (15D PR 3 / PR 4)
plus a per-row `active` / `inactive` status.

### Body grid (when not Activated)

Same two-column shape as Reviewers / Reviewees — Upload card on
the left, Danger Zone on the right. CSV header copy lists
`ReviewerEmail`, `RevieweeEmail` required; `PairContextTag1..3`,
`Status` (`active` / `inactive`) optional. Defaults to `active`
when `Status` is omitted. POSTs to
`/operator/sessions/{id}/relationships/import` via
`save_relationships(...)`.

### Stats card

Single-line "Fields with data" card above the body grid:

> Fields with data: {pill, pill, …}

Mirrors the Reviewers / Reviewees stats card shape exactly — the
per-entity row count is **not** repeated here, since the chrome
status strip already carries it. Fields-with-data labels come
from `relationships.fields_with_data(...)` in
`app/services/relationships.py`.

### Preview table

| # | Column | Toggle? | Notes |
|---|---|---|---|
| 0 | (select) | — | Leftmost checkbox column — per-row select + header select-all; drives the Operator actions card |
| 1 | Reviewer | — | Resolved **name** stacked above `<code>email</code>`; sorts on name |
| 2 | Reviewee | — | Resolved **name** stacked above `<code>email_or_identifier</code>`; sorts on name |
| 3 | Tag1 | ✓ | `data-col-toggle="tag-1"` / `class="tag-col tag-col-1"` |
| 4 | Tag2 | ✓ | `data-col-toggle="tag-2"` / `class="tag-col tag-col-2"` |
| 5 | Tag3 | ✓ | `data-col-toggle="tag-3"` / `class="tag-col tag-col-3"` |
| 6 | Status | — | `<span class="pill pill-info\|pill-empty">active\|inactive</span>` per the canonical pill treatment (post-15 cleanup polish #768) |
| 7 | Updated | — | `relationship.updated_at` (`%Y-%m-%d %H:%M`) |

The `Show columns:` chip row sits in the top "Fields with data"
card; same default-state and persistence rules as Reviewers /
Reviewees per the shared section above.

The Status column is *not* toggleable — every relationship has a
status by design, and the pill treatment makes the value visually
distinct without needing an explicit hide affordance.

### Round-trip with the Relationships extract

The CSV column shape here is the inverse of
`app/services/extracts/relationships_extract.py` (8-column wide
CSV: `ReviewerEmail`, `RevieweeEmail`, `PairContextTag1..3`,
`Status` — same six columns the importer accepts). Round-trip is
byte-stable on the export's own output. The Extract Data card on
Session Home carries the corresponding Download button.

## Out of scope for these pages

- **Per-row hard Delete.** Inactivate-via-edit covers the
  single-row retire case; the Danger Zone Delete-all flow covers
  the bulk-clear case. A per-row Delete is a separate ask if it
  surfaces in pilot feedback.
- **Cross-entity validation.** Surfaced via the dedicated Validate
  page; not rendered inline on these pages.
- **Paging.** The 200-row (500-when-filtered) cap + the search /
  status filter cover the long-list case; there is no pager.
- **Assignments generation.** Moved to the Operations row in
  Segment 15D PR 6a — see `spec/operator_ui_concept.md` §5.

Per-row inline Edit / Add / bulk inactivate-reactivate and the
search / status filter strip — previously listed here as
deferred — **shipped in Segment 15F** (2026-05-15); see
"Operator actions card" and "Per-row Edit / Add / bulk actions"
above.

## Implementation pointers

- The shared visibility-toggle pattern lives inline per template
  (HTML structure + `<style>` + `<script>`). Each page picks its
  own `STORAGE_KEY` and CSS class names so they don't collide.
- Per-entity row counts and "fields with data" pill labels come
  from the helpers in `app/services/assignments.py`
  (`reviewer_fields_with_data`, `reviewee_fields_with_data`) and
  `app/services/relationships.py`
  (`fields_with_data`) — keep them in sync with any new optional
  column added to the model + CSV importer.
- Lifecycle gating is the existing pattern: a `card lock` at the
  top of the body when `is_ready`, and the Upload + Danger Zone
  cards conditionally rendered behind `{% if not is_ready %}`. The
  preview table renders unconditionally so the operator can read
  the current rows even while the session is Activated.
