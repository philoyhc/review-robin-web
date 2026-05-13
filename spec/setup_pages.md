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
5. **Friendly-label editor** (Segment 15A Slice 3) — inline
   editor card via `operator/partials/_field_labels_editor.html`.
   Reviewers + Relationships render a 3-cell row; Reviewees a
   2-row stacked grid (identity + tags, 6 cells). Save + Cancel
   pair in Secondary style at the bottom, both starting
   `disabled` until the form is dirty (inline JS toggles via an
   initial-value snapshot). Gated by `is_ready`: when the
   session is Activated, inputs render `disabled` and the
   Save/Cancel pair is suppressed; the lifecycle-gate card above
   carries the "revert to draft" prompt for that state. POST
   handlers in
   `app/web/routes_operator/_setup_rosters.py` upsert / clear via
   `app/services/field_labels.py`.
6. **Preview table card** — Reviewers / Reviewees / Relationships.
   Always renders when the entity is non-empty, regardless of
   lifecycle state. Column headers render the resolved friendly
   label via `operator/partials/_field_label_header.html`; when
   an override is set, the canonical name appears as
   `.field-label-canonical` muted subtext below the friendly
   label and the sort `↕` button.
7. **Body grid** — Upload + Danger Zone cards. Hidden when the
   session is Activated. Placed **after** the preview table so
   the operator's eye lands on the data they're managing first;
   the upload-CSV + delete-all destructive actions sit below the
   table as a deliberate de-prioritised cluster.

## Preview tables (shared toggle pattern)

The Reviewers, Reviewees, and Relationships preview tables share
a **visibility-toggle row** that lets the operator hide optional
columns. The pattern:

- Optional tag / context columns always render in the DOM (so
  empty columns can be revealed by ticking).
- A right-flushed checkbox row above the table toggles per-column
  visibility via a CSS class on the table (e.g.
  `tag-hidden-1` → `display: none` for cells with class
  `tag-col-1`).
- Each toggle defaults to **ticked iff that column has at least
  one populated value** in the current preview rows.
- **Empty columns render the toggle disabled** (`disabled
  aria-disabled="true" title="No data in this column"`). The
  operator can't tick an empty column on, and stored "show"
  preferences carried over from a load when the column had data
  are ignored — the toggle stays unticked and the column stays
  hidden until the next import populates it.
- Operator choice persists per browser via `localStorage` under a
  per-page key:
  - Reviewers preview: `rrw-reviewer-tag-visibility`.
  - Reviewees preview: `rrw-reviewee-tag-visibility`.
  - Relationships preview: `rrw-relationship-tag-visibility`.
- Stored choice wins over the data-driven default for live
  toggles. Stored "hide" keeps a populated column hidden;
  stored "show" reveals an explicitly-toggled-on column on next
  load. Disabled toggles ignore storage entirely (see above).
- The toggle inputs carry `data-tag-toggle="<slot>"` /
  `data-col-toggle="<slot>"` for the inline JS to target. The JS
  early-returns on `cb.disabled` so listeners aren't bound and
  storage isn't applied.

The pattern is intentionally not extracted into a Jinja macro —
each page's column shape differs enough (Reviewers has 3 toggles,
Reviewees has 3, Relationships has 3) that the inline JS +
scoped `<style>` block per template is more legible than a macro
with a sprawling parameter list.

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
  `status`.
- **Reviewees:** `name`, `email_or_identifier`, `tag_1` /
  `tag_2` / `tag_3`, `status`. (The Photo column stays
  non-sortable — it renders a link, not a comparable value.)
- **Relationships:** `reviewer` (sorts on reviewer email),
  `reviewee` (sorts on `email_or_identifier`),
  `tag_1` / `tag_2` / `tag_3`, `status`.

Sortable affordance and visibility-toggle affordance are
orthogonal — toggling a column's visibility doesn't affect its
sort state, and a sort spec referencing a hidden column still
applies (the column data is still present in the DOM).

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
| 1 | Name | — | `reviewer.name` |
| 2 | Email | — | `<code>{{ reviewer.email }}</code>` |
| 3 | Tag1 | ✓ | `data-tag-toggle="1"` / `class="tag-col tag-col-1"` |
| 4 | Tag2 | ✓ | `data-tag-toggle="2"` / `class="tag-col tag-col-2"` |
| 5 | Tag3 | ✓ | `data-tag-toggle="3"` / `class="tag-col tag-col-3"` |
| 6 | Status | — | `reviewer.status` |

Toggle row sits right-flushed above the table (`Tag1`, `Tag2`,
`Tag3` checkboxes); see "Preview tables (shared toggle pattern)"
above for default-state and persistence rules.

## Reviewees page (`session_reviewees.html`)

### Body grid (when not Activated)

Same two-column shape as Reviewers — Upload card on the left,
Danger Zone on the right. CSV header copy lists `RevieweeName`,
`RevieweeEmail` required; `PhotoLink`, `RevieweeTag1..3` optional.

### Preview table

| # | Column | Toggle? | Notes |
|---|---|---|---|
| 1 | Name | — | `reviewee.name` |
| 2 | Email / Identifier | — | `<code>{{ reviewee.email_or_identifier }}</code>` |
| 3 | Photo | — | Conditional: rendered only when at least one reviewee has `profile_link`. Cell renders `<a href="…" target="_blank">link</a>`. |
| 4 | Tag1 | ✓ | Same toggle scheme as Reviewers |
| 5 | Tag2 | ✓ | |
| 6 | Tag3 | ✓ | |
| 7 | Status | — | `reviewee.status` |

The Photo column is *not* on a toggle — its presence is governed
solely by whether any reviewee has a populated `profile_link` in
the current preview rows. Position 3 sits between the identity
columns and the toggleable tag columns so the canonical column
order is consistent across reviewers / reviewees.

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

Single-line counts card above the body grid:

> Number of pairwise relationships: **{pill}** · Fields with data:
> {pill, pill, …}

Mirrors the Reviewers / Reviewees stats card shape (Segment 15
post-cleanup polish #762 unified the three pages on this
treatment). Fields-with-data labels come from
`relationships.fields_with_data(...)` in `app/services/relationships.py`.

### Preview table

| # | Column | Toggle? | Notes |
|---|---|---|---|
| 1 | Reviewer | — | `<a href=…>name</a> · <code>email</code>` |
| 2 | Reviewee | — | `<a href=…>name</a> · <code>email_or_identifier</code>` |
| 3 | Tag1 | ✓ | `data-tag-toggle="1"` / `class="tag-col tag-col-1"` |
| 4 | Tag2 | ✓ | `data-tag-toggle="2"` / `class="tag-col tag-col-2"` |
| 5 | Tag3 | ✓ | `data-tag-toggle="3"` / `class="tag-col tag-col-3"` |
| 6 | Status | — | `<span class="pill pill-info\|pill-empty">active\|inactive</span>` per the canonical pill treatment (post-15 cleanup polish #768) |

Toggle row sits right-flushed above the table (`Tag1`, `Tag2`,
`Tag3` checkboxes); same default-state and persistence rules as
Reviewers / Reviewees per the shared section above.

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

- **Per-record inline editing.** Setup pages today are import +
  preview only; per-record editing is deferred to Segment 15F
  (bundled with per-row Inactivate / Reactivate affordances).
  The Edit buttons on Reviewers / Reviewees / Relationships
  pages render disabled with an "Inline editing — coming soon"
  tooltip.
- **Cross-entity validation.** Surfaced via the dedicated Validate
  page; not rendered inline on these pages.
- **Filter on preview tables.** Out of scope for the initial
  slice. Operator-side **sort** lives in the shared rrw-sort
  primitive ("Sortable headers" section above; shipped 2026-05-12
  as Segment 13B Part 2). Default render order remains
  primary-key when no sort cookie is in play.
- **Assignments generation.** Moved to the Operations row in
  Segment 15D PR 6a — see `spec/operator_ui_concept.md` §5.

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
