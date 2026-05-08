# Setup Pages — UI spec

Per-session **Setup Pages** are the per-entity import + edit
surfaces reachable from the chrome's Setup row:

| Page | URL | Template |
|---|---|---|
| Reviewers | `/operator/sessions/{id}/reviewers` | `session_reviewers.html` |
| Reviewees | `/operator/sessions/{id}/reviewees` | `session_reviewees.html` |
| Assignments | `/operator/sessions/{id}/assignments` | `session_assignments.html` |
| Instruments | `/operator/sessions/{id}/instruments` | `session_instruments.html` |
| Settings | `/operator/sessions/{id}/edit` | `session_edit.html` |

Each Setup Page follows the same shell (chrome + Setup row +
status strip + a body of cards). The Reviewers, Reviewees, and
Assignments pages additionally render a **preview table** of the
session's current rows that all share a common visibility-toggle
pattern; this spec covers that shared pattern alongside the
per-page idiosyncrasies.

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
   `reviewee_fields_with_data` / `assignment_fields_with_data` in
   `app/services/assignments.py`). Drives operator awareness of
   which optional fields the latest import populated.
4. **Lifecycle gate cards** (when the session is Activated): a
   `card lock` carrying "The {entity} cannot be modified while the
   session is ongoing. Revert the session to draft if you wish to
   modify anything." with an inline Revert form.
5. **Body grid** — Upload + Danger Zone cards (and on the
   Assignments page, the Rule Based card too). Hidden when the
   session is Activated; only the lock card and the preview table
   render in that state.
6. **Preview table card** — Reviewers / Reviewees / Assignments
   only. Always renders when the entity is non-empty, regardless
   of lifecycle state.

## Preview tables (shared toggle pattern)

The Reviewers, Reviewees, and Assignments preview tables share a
**visibility-toggle row** that lets the operator hide optional
columns. The pattern:

- Optional tag / context columns always render in the DOM (so
  empty columns can be revealed by ticking).
- A right-flushed checkbox row above the table toggles per-column
  visibility via a CSS class on the table (e.g.
  `tag-hidden-1` → `display: none` for cells with class
  `tag-col-1`).
- Each toggle defaults to **ticked iff that column has at least
  one populated value** in the current preview rows.
- Operator choice persists per browser via `localStorage` under a
  per-page key:
  - Reviewers preview: `rrw-reviewer-tag-visibility`.
  - Reviewees preview: `rrw-reviewee-tag-visibility`.
  - Assignments preview: `rrw-assignment-col-visibility`.
- Stored choice wins over the data-driven default. Stored "show"
  reveals an empty column on next load; stored "hide" keeps a
  populated column hidden.
- The toggle inputs carry `data-tag-toggle="<slot>"` /
  `data-col-toggle="<slot>"` for the inline JS to target.

The pattern is intentionally not extracted into a Jinja macro —
each page's column shape differs enough (Reviewers has 3 toggles,
Reviewees has 3, Assignments has 12 grouped) that the inline JS
+ scoped `<style>` block per template is more legible than a
macro with a sprawling parameter list.

## Reviewers page (`session_reviewers.html`)

### Body grid (when not Activated)

Two-column `bottom-grid`:

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

## Assignments page (`session_assignments.html`)

### Body grid (when not Activated)

Two columns:

- **Left:** `Rule Based Assignment` card (`partials/_rule_based_card.html`).
  RuleSet dropdown + "Generate" submit, plus an inline link to
  the Rule Builder page. The card stays at its natural height —
  no alignment with the right column's bottom.
- **Right:**
  - `Upload Manual Assignment` card (top). Required CSV columns
    `ReviewerEmail`, `RevieweeEmail`; optional `IncludeAssignment`,
    `PairContext1/2/3`, `AssignmentContext1/2/3`. Carries an
    `Exclude self-review` checkbox (default `checked`) and a
    confirm-replace checkbox when the session already has
    assignments.
  - `Danger Zone` card (just below Upload), only rendered when at
    least one assignment exists.

The `.bottom-grid` wrapper uses `align-items: start`, so the right
column doesn't stretch to match the (typically taller) Rule Based
card.

### Preview table — "Current pairs"

15 columns total, in canonical left-to-right order:

| # | Column | Toggle slot | Header label |
|---|---|---|---|
| 1 | Reviewer (`name · email`) | — | `Reviewer` |
| 2 | Reviewer Tag1 | `rt1` | `Tag1` |
| 3 | Reviewer Tag2 | `rt2` | `Tag2` |
| 4 | Reviewer Tag3 | `rt3` | `Tag3` |
| 5 | Reviewee (`name · email`) | — | `Reviewee` |
| 6 | Reviewee Tag1 | `et1` | `Tag1` |
| 7 | Reviewee Tag2 | `et2` | `Tag2` |
| 8 | Reviewee Tag3 | `et3` | `Tag3` |
| 9 | Pair context 1 | `p1` | `Pair1` |
| 10 | Pair context 2 | `p2` | `Pair2` |
| 11 | Pair context 3 | `p3` | `Pair3` |
| 12 | Assignment context 1 | `a1` | `Assign1` |
| 13 | Assignment context 2 | `a2` | `Assign2` |
| 14 | Assignment context 3 | `a3` | `Assign3` |
| 15 | Include | — | `Include` (renders `yes` / `no`) |

The Reviewer and Reviewee identity cells render the name and email
on the same line separated by a middle dot (`Alice · alice@example.edu`),
with the email wrapped in `<code>`. The 12 toggleable columns
(Reviewer Tag1..3, Reviewee Tag1..3, Pair1..3, Assign1..3) are
grouped into four right-flushed clusters in the toggle row, each
prefixed with a muted group label (`Reviewer:`, `Reviewee:`,
`Pair:`, `Assignment:`).

## Out of scope for these pages

- **Per-record inline editing.** Setup pages today are import +
  preview only; per-record editing is deferred. The Edit buttons
  on Reviewers / Reviewees pages render disabled with a
  "Inline editing — coming soon" tooltip.
- **Cross-entity validation.** Surfaced via the dedicated Validate
  page; not rendered inline on these pages.
- **Sort or filter on preview tables.** Reviewer-side sort is
  Segment 13B's concern (see `spec/sort_by_reviewee.md`); operator
  preview rows render in primary-key order today.

## Implementation pointers

- The shared visibility-toggle pattern lives inline per template
  (HTML structure + `<style>` + `<script>`). Each page picks its
  own `STORAGE_KEY` and CSS class names so they don't collide.
- Per-entity row counts and "fields with data" pill labels come
  from the helpers in `app/services/assignments.py`
  (`reviewer_fields_with_data`, `reviewee_fields_with_data`,
  `assignment_fields_with_data`) — keep them in sync with any
  new optional column added to the model + CSV importer.
- Lifecycle gating is the existing pattern: a `card lock` at the
  top of the body when `is_ready`, and the Upload + Danger Zone
  cards conditionally rendered behind `{% if not is_ready %}`. The
  preview table renders unconditionally so the operator can read
  the current rows even while the session is Activated.
