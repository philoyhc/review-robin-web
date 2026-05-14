# Segment 15F — Enhanced Setup pages

**Status:** Sized 2026-05-14. Carved out 2026-05-10 from the original
`guide/archive/segment_15_operator_polish_and_documentation.md` once it
became clear the per-row Manage-page enhancements are a
distinct scope from the documentation pass (now Segment 20).

15F lives alongside the other 15-family extensions —
15A (friendly labels), 15B (per-instrument assignments),
15C (operator RTD / RuleSet libraries), 15E (Operations
Workflow Card), 16 (Sys Admin page) — as a focused per-row UX
improvement for the three Setup pages that operators iterate
on most.

## Goal

Bring per-row affordances to the Reviewers / Reviewees /
Relationships Manage pages so operators don't have to drop
to CSV upload + replace to fix a single name, demote one
person to inactive, or add a single new row. Four linked
surfaces:

1. **Inline edit** — operator clicks a row's **Edit** button,
   that row flips into edit mode (input fields replace text),
   Save / Cancel commit or roll back. No bulk CSV round-trip
   needed for single-row changes. Editing a row's status is the
   inactivate / reactivate path — no separate per-row toggle
   button.
2. **Bulk inactivate / reactivate** — leftmost checkbox column;
   action bar above the table when ≥1 row is selected
   (Inactivate selected / Reactivate selected). Reversible
   actions; no confirm-checkbox needed.
3. **Add new row** — a half-width "Add row" card to the right
   of the existing friendly-labels editor card (which becomes
   half-width on the left). Single-row authoring; CSV bulk
   upload stays as the bulk-create path.
4. **Find a row to act on** — a search + status filter strip
   above the table so operators don't scroll a 1500-row list
   looking for one name.

## Decisions locked (2026-05-14)

1. **Display.** Show-first-200 + server-side search + status
   filter. The cap lifts to 500 when a filter (search or
   status) is applied. Same pattern as the Invitations /
   Responses tables — the "Showing N of M" muted line tells
   the operator when they've hit the cap.

2. **Search + filter strip.** Reuse `app/web/views/_filters.py`
   (the Invitations / Responses helper). `<input list>` +
   `<datalist>` autocompleted from the unfiltered roster's
   distinct values, plus a Status `<select>` (`all` /
   `active` / `inactive`). `GET` form so URL state survives
   reload.

3. **Per-row Edit button** in an Actions column. Clicking it
   flips the row into edit mode (inputs replace text in-place
   for the editable cells); Save / Cancel buttons appear in
   that column. One row in edit mode at a time. Single-row
   edit is the dominant case; bulk-edit on free-text fields
   isn't useful.

4. **Status flip via inline edit, not a separate button.** The
   Status cell becomes a `<select>` (`active` / `inactive`)
   while the row is in edit mode. Removes the need for a
   per-row Inactivate / Reactivate button and keeps the row's
   action column thin (just Edit / Save / Cancel).

5. **Leftmost checkbox column for bulk-only actions.**
   Header checkbox selects-all-visible (i.e. all rendered
   rows on the current filtered page; doesn't reach hidden
   capped rows). Bulk-action bar above the table renders
   only when ≥1 row is selected — Inactivate selected /
   Reactivate selected. No bulk Edit, no bulk Delete.

6. **No per-row hard Delete.** Inline-edit covers the
   single-row inactivate use case; bulk inactivate via the
   checkbox column covers the cohort case. Hard delete stays
   on the **Danger Zone Delete-all** flow already shipped,
   plus "upload a new list" via CSV bulk-replace. Avoids
   accidental destruction of audit-pointed data and keeps the
   surface honest about which actions are reversible.

7. **Add-row card layout.** The friendly-labels editor card
   currently runs full-width above the table on each Setup
   page (Segment 15A Slice 3). 15F splits that into a
   `bottom-grid` row of two half-width cards: the existing
   labels editor stays on the **left**, a new Add-row card
   anchors the **right**. Add card carries the same inputs
   as the inline-edit row + an Add button; emits a single
   POST that creates one new row + 303s back.

8. **One row in edit mode at a time.** If the operator clicks
   Edit on a second row, the first row's pending edits prompt
   for save-or-discard (inline JS, no modal). Keeps the form
   state model simple and prevents losing unsaved changes
   silently.

9. **Lifecycle gate stays at `_require_editable`.** Every new
   mutation route (per-row edit / per-row add / bulk
   inactivate / bulk reactivate) wraps with the existing
   `_require_editable` helper and calls
   `lifecycle.invalidate_if_validated` from the service layer.
   Same pattern every other Setup-page mutation uses.

10. **Stack choice: vanilla JS, no AG Grid.** The shipped
    surfaces (Invitations / Responses tables, Instruments
    edit-lock, 13B sort affordance) prove the row-level
    edit + search + filter shape works on plain HTML +
    targeted progressive-enhancement JS. AG Grid is a
    separate question (Segment 17A) — 15F doesn't depend
    on it.

## Why one segment

The four items move together because they share:

- **The same three pages** (Reviewers / Reviewees /
  Relationships Manage pages, all under `/operator/sessions/{id}/…`).
- **The same row-state UX** — per-row Edit toggles one row into
  inputs; the Status cell in that row's edit form is the
  inactivate path. Bulk inactivate from the checkbox column is
  a thin variant of the same service-layer call. Add-row reuses
  the inline-edit row's input shape.
- **The same row-level conflict story** — when an operator
  edits a row that the rule engine is about to consume, the
  service layer needs to gate the write against lifecycle
  state. Solving the conflict story once for inline edit
  covers Inactivate, bulk inactivate, and Add too.

## Background

- **Inline-editable rows** — officially deferred from
  Segment 11 (originally 10E §2.5). The catalog entry
  flagged it needs a design pass before code; 15F is the
  design + implementation pass.
- **Operator Inactivate UI** — officially deferred from
  Segment 11 Tier 3 §2.4 on 2026-05-03. The Reviewer +
  Reviewee tables already filter on `status` defensively;
  the affordance to flip the column is missing. The
  relationships table picked up `status` in 15D PR 2 and
  has the same gap.
- **Codebase check 2026-05-14.** Inactivation is clean: every
  consumer-side path (`invitations.py:70`, `monitoring.py:72`,
  `assignments.py:131,414`, `routes_reviewer.py:55,154`,
  `deps.py:161`) filters on `Reviewer.status == "active"`,
  so inactivating a reviewer removes them from invitation
  generation, reminder sends, assignment generation, and
  reviewer-surface login without affecting historical Response
  / Invitation / Assignment rows. Hard delete is FK-safe in
  `draft` / `validated` (where Responses don't exist yet) but
  blocked by FK violation in `ready` — `_require_editable`
  already enforces the lifecycle precondition that makes hard
  delete safe; 15F still defers it per Decision 6.

## Scope

### Pages touched

- `/operator/sessions/{id}/reviewers` — `Reviewer` rows
  with `name` / `email` / `tag_1..3` / `status`.
- `/operator/sessions/{id}/reviewees` — `Reviewee` rows
  with `name` / `email_or_identifier` / `profile_link` /
  `tag_1..3` / `status`.
- `/operator/sessions/{id}/relationships` — `Relationship`
  rows with `reviewer` / `reviewee` (FKs, not editable
  inline) / `tag_1..3` / `status`.

### Inline-edit UX

- Edit affordance: per-row Edit button in the rightmost
  Actions column. Click → row's editable cells flip from text
  to `<input>` / `<select>` (Status becomes a `<select>`);
  Save + Cancel buttons replace the Edit button. Save POSTs
  the row, Cancel restores the snapshot. One row at a time.
- Validation: client-side immediate (matching the existing
  CSV importer's per-column rules — email shape, tag length,
  non-empty name); server-side authoritative.
- Save shape: per-row POST with the row id. The CSV importer
  stays for bulk-replace.
- Cross-table integrity: editing a reviewer's email after
  the rule engine has materialised assignments is fine —
  assignments key by row id, not email. Audit trail records
  the change via `reviewer.updated` / `reviewee.updated` /
  `relationship.updated` (canonical `changes` envelope per
  Segment 11K).

### Bulk selection + bulk actions

- Leftmost checkbox column. Header checkbox selects-all-visible.
- Bulk-action bar renders above the table when ≥1 row is
  selected; carries Inactivate selected + Reactivate selected.
  No bulk Edit, no bulk Delete.
- Audit events: `reviewer.status_changed_bulk` /
  `reviewee.status_changed_bulk` /
  `relationship.status_changed_bulk` with the canonical
  `set_changes` envelope (added = newly inactivated ids,
  removed = newly reactivated ids — or split into separate
  event types per the audit-emitter style, decide during PR
  scoping).

### Add-row affordance

- Half-width "Add row" card to the right of the friendly-labels
  editor card (which moves from full-width to half-width left).
- Inputs match the inline-edit row's shape — name / email /
  tags (Reviewers); name / identifier / profile-link / tags
  (Reviewees); reviewer-select / reviewee-select / tags
  (Relationships). Status defaults to `active`; the operator
  can flip it to `inactive` via subsequent inline edit.
- Submit: per-page POST emitting `reviewer.created` /
  `reviewee.created` / `relationship.created` (snapshot
  envelope).

### Search + status filter strip

- Above the table on every Setup page. Status `<select>`
  (`all` / `active` / `inactive`) + Search `<input list>`
  autocompleted from the unfiltered roster.
- Server-side filter (the route's view-adapter consults
  `request.query_params`); the visible-rows count line
  reports "Showing N of M" matching the Invitations /
  Responses pattern.
- Search matches case-insensitive substring across the
  page's identity columns (name / email; for Relationships,
  reviewer-name + reviewee-name).
- 200-row cap applies to the unfiltered render; lifts to
  500 when either filter is applied.

### Lifecycle gate

- All mutations land via the existing `_require_editable`
  helper. `validated` → `draft` invalidation via
  `lifecycle.invalidate_if_validated` at the service-layer
  entry point.
- Edits on `ready` sessions: rejected at the route layer
  (409). Operator must revert to draft first.

### Defensive status re-check ride-along

The per-row `invitations_send_one` route
(`_operations.py:541`) currently fetches the Reviewer by FK
without re-checking `status`. The Invitations table itself
filters via `monitoring.per_reviewer_progress` so the button
never renders for inactive reviewers, but a direct POST or
stale tab could still dispatch. Trivial defensive guard to
add alongside 15F so the per-row send-path matches the bulk
send-path's status filter. Ride-along, not its own PR.

## PR sequence

Conservative slicing — each PR self-contained and reviewer-
sized.

### PR 1 — Reviewers service-layer CRUD + audit events

**Scope.** New `app/services/reviewers.py` with `create_reviewer`,
`update_reviewer`, `set_reviewer_status`, `bulk_set_status`. Each
mutator calls `lifecycle.invalidate_if_validated` and emits the
canonical audit event. New event types
(`reviewer.created` / `.updated` / `.status_changed` /
`.status_changed_bulk`) registered in `EVENT_SCHEMAS`. No UI
surface yet — the CSV importer continues to be the only writer.

**Tests.** Service-layer happy-path + lifecycle gate + audit
envelope strict-mode checks.

### PR 2 — Reviewers page search + filter + 200/500 cap

**Scope.** View-adapter consumes
`request.query_params` for search / status; route slices the
result with the 200 / 500 cap. New filter strip above the
table; muted "Showing N of M" line. No per-row edit yet.
Establishes the find-a-row machinery the later UI PRs sit on.

**Tests.** Filter parsing, cap application, "Showing N of M"
rendering.

### PR 3 — Reviewers page inline edit + bulk inactivate +
Add card

**Scope.** Template grows the checkbox column, the per-row
Edit / Save / Cancel state machine, the bulk-action bar, and
the half-width Add-row card layout (friendly-labels editor
narrows to half-width left). Route handlers wire the new
service-layer calls from PR 1. Targeted inline JS for the
row-state toggle + "one row at a time" guard.

**Tests.** Per-row edit happy-path, bulk inactivate, Add card
POST, "one row at a time" guard.

### PR 4 — Reviewees (clone PRs 1–3)

**Scope.** Mirror PRs 1–3 onto the Reviewees page; reuse the
templates / view shapes / service contract from PRs 1–3.
Reviewees-specific columns: name / email_or_identifier /
profile_link / tags / status.

### PR 5 — Relationships (clone PRs 1–3)

**Scope.** Mirror onto the Relationships page. Wrinkle:
reviewer / reviewee FKs are not inline-editable (changing the
FK on a `Relationship` row is conceptually delete + create,
not edit) — the inline-edit form locks the identity columns
and only edits tags + status. Add card needs `<select>`
pickers for reviewer / reviewee.

### PR 6 — Defensive status re-check on `invitations_send_one`

**Scope.** One-liner in `_operations.py:541` — refuse to send
when `reviewer.status != "active"`. Ride-along with whichever
of PR 3 / 4 lands the per-row Inactivate. Catches the
direct-POST / stale-tab edge case.

## Out of scope

- **Per-row hard Delete on Reviewers / Reviewees /
  Relationships pages.** Inactivate-via-edit covers the
  single-row retire case; the Danger Zone Delete-all flow
  covers the bulk-clear case. Per-row Delete is a separate
  ask if it surfaces in pilot feedback.
- **Inline edit on the Assignments preview table.**
  Assignments are derived post-15D — the operator-facing
  edit affordance is the Rule Builder + Relationships
  table.
- **Paging.** Show-first-N + search covers the
  find-the-row case for rosters up to ~1500 rows. If pilot
  evidence ever shows operators routinely need to scroll
  past the 200 / 500 cap unfiltered, paging becomes a clean
  follow-on PR (view-adapter offset/limit + a
  `<nav class="pager">` primitive in `base.html`). No
  commitment now.
- **AG Grid replacement.** Separate concern (Segment 17A).
  The 15F surfaces are achievable on plain HTML + targeted
  progressive-enhancement JS; AG Grid would be a downstream
  re-implementation if Segment 17A ever ships, not a
  blocker.
- **Per-row drill-in.** Inline edit covers the mutation
  case; the row's full state lives in the existing audit
  log accessible from Sys Admin.

## Working notes / open questions

- **Bulk-action audit shape.** Single emit with
  `set_changes` (added / removed) vs. one emit per row.
  Lean single emit so audit-log readers see "operator
  inactivated 7 reviewers in one click" as one entry, not
  seven.
- **Add card validation feedback.** Inline error banner on
  the card (per the existing Setup-page error treatment) vs.
  a global page-top banner. Lean card-local — keeps the
  error close to the form that produced it.
- **Search autocomplete cardinality.** A 1500-row roster
  would produce a 1500-option `<datalist>`. The Invitations
  / Responses pattern works fine at smaller scale (a few
  hundred). If render-time pressure shows up, cap the
  datalist at the first N alphabetically — search-by-typing
  still works against the server-side filter, the autocomplete
  is just a convenience.

## Related context

- **Segment 11** Tier 3 §2.4 — original Inactivate-UI
  filing.
- **Segment 10E** §2.5 — original inline-editable rows
  filing.
- **Segment 15A** (`guide/segment_15A_friendly_labels.md`)
  — friendly labels for tag headers. Sequenced before 15F
  is fine (the tag columns 15F edits inherit the friendly
  labels) but not strictly required.
- **Segment 15D** (`guide/archive/segment_15D_assignments_revamp.md`)
  PR 2 — the Relationships Setup page that 15F extends.
- **`spec/setup_pages.md`** — Setup Pages shared body
  shape; 15F adds inline-edit / Inactivate to the
  contract.
