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

2. **Search + filter strip.** Lives inside the right-side
   operator-actions card (see Decision 7), below the
   Add-row inputs. Reuses `app/web/views/_filters.py` (the
   Invitations / Responses helper). `<input list>` +
   `<datalist>` autocompleted from the unfiltered roster's
   distinct values, plus a Status `<select>` (`all` /
   `active` / `inactive`). `GET` form so URL state survives
   reload.

3. **Selection drives row mutation, not per-row buttons.**
   The leftmost checkbox column is the single row-mutation
   selector — rows don't carry their own action buttons.
   The right-side card's action-button row reads the
   checkbox selection and enables / disables its buttons
   accordingly:

   | Selection | Edit | Inactivate selected | Reactivate selected | Add new row |
   | --- | --- | --- | --- | --- |
   | 0 rows | disabled | disabled | disabled | enabled |
   | 1 row | **enabled** | enabled | enabled | enabled |
   | 2+ rows | disabled | enabled | enabled | enabled |
   | Any row in edit mode | (replaced by Save + Cancel) | disabled | disabled | disabled |

   Operators with long rosters narrow with search first,
   then select one (or several) by checkbox, then act. No
   per-row clutter; one consistent "click row → act from
   card" flow for every mutation.

4. **Status flip via inline edit, not a separate button.** The
   Status cell becomes a `<select>` (`active` / `inactive`)
   while the row is in edit mode (Edit button on the card
   was clicked with exactly one row selected). For
   one-shot status flips on a selection set, the card's
   Inactivate selected / Reactivate selected buttons fire
   without entering edit mode. Together: inline edit covers
   "change anything on one row including status"; bulk
   buttons cover "flip status on N rows without touching
   other fields".

5. **Leftmost checkbox column as the sole selection mechanism.**
   Header checkbox selects-all-visible (i.e. all rendered
   rows on the current filtered page; doesn't reach hidden
   capped rows). The card's action buttons react to the
   selection per the table above. While a row is in edit
   mode the other checkboxes render `disabled` so the
   operator can't change selection mid-edit; finishing or
   cancelling the edit re-enables them.

6. **No per-row hard Delete.** Inline-edit covers the
   single-row inactivate use case; bulk inactivate via the
   checkbox column covers the cohort case. Hard delete stays
   on the **Danger Zone Delete-all** flow already shipped,
   plus "upload a new list" via CSV bulk-replace. Avoids
   accidental destruction of audit-pointed data and keeps the
   surface honest about which actions are reversible.

7. **Right-side operator-actions card.** The friendly-labels
   editor card currently runs full-width above the table on
   each Setup page (Segment 15A Slice 3). 15F splits that
   into a `bottom-grid` row of two half-width cards: the
   existing labels editor stays on the **left**, a new
   **operator-actions card** anchors the **right** and
   consolidates every page-level operator action that isn't
   per-row. Two vertically-stacked sections inside that
   card, top to bottom:

   1. **Search + filter.** Status `<select>` (`all` /
      `active` / `inactive`) + Search `<input list>` over
      the page's identity columns. `GET` form; "Showing N
      of M" muted line under the inputs when a filter is
      active. Submit / Clear buttons.
   2. **Action buttons.** Four buttons in one row —
      **Edit**, **Inactivate selected**, **Reactivate
      selected**, **Add new row**. Selection-dependent
      enable/disable per the table in Decision 3. A small
      selected-count pill (e.g. "3 selected") sits to the
      left of the row when ≥1 row is selected.
      Add new row is always live; clicking it prepends a
      fresh editable row to the top of the table (no
      separate inputs section in the card; the new row uses
      the inline-edit machinery in-place).
      When a row is in edit mode the Edit button transforms
      into **Save** + **Cancel**; the other three buttons
      disable until the edit completes or cancels.

   Layout sketch:

   ```
   ┌── Friendly labels editor (15A) ──┐  ┌── Operator actions ───────────────────────┐
   │  left, half-width                │  │  right, half-width                        │
   │                                  │  │                                           │
   │  (existing 15A content)          │  │  Search + status filter                   │
   │                                  │  │  ─────────                                 │
   │                                  │  │  [3 selected]                              │
   │                                  │  │  [Edit] [Inactivate] [Reactivate] [Add new row]
   └──────────────────────────────────┘  └───────────────────────────────────────────┘
   ┌── Rows table ────────────────────────────────────────────────────────────┐
   │  ☐  Reviewer  Email  Tag1  Tag2  Tag3  Status                            │
   │  …                                                                       │
   └──────────────────────────────────────────────────────────────────────────┘
   ```

   The table itself carries only the checkbox column + data
   columns — no per-row Actions column, no per-row buttons.
   Every mutation fires from the operator-actions card.

8. **Edit / Add new row mechanics.** Clicking **Edit** (with
   exactly one row checked) flips that row's editable cells
   from text to `<input>` / `<select>` in-place; the card's
   Edit button becomes Save + Cancel. Save POSTs the row's
   update to the per-page edit endpoint; Cancel restores
   the snapshot and leaves the row checked.

   Clicking **Add new row** prepends a fresh `<tr>` to the
   top of the table in edit mode — empty inputs in every
   editable column, Status defaulting to `active`. The
   card's Edit button becomes Save + Cancel (same affordance
   as Edit). Save POSTs to the per-page create endpoint and
   303s back. Cancel removes the row from the DOM (nothing
   was persisted; no server round-trip).

   Both flows reuse the same in-table inline-edit machinery —
   inputs are anchored to the row that will be saved, not to
   the card. The "one row in edit mode at a time" guard
   (Decision 9) prevents starting either flow while another
   is pending.

9. **One row in edit mode at a time.** While a row is in
   edit mode, the card's Edit / Inactivate / Reactivate /
   Add-new-row buttons disable (Edit replaced by Save +
   Cancel) and the other rows' checkboxes disable. The
   operator finishes by clicking Save (commits) or Cancel
   (reverts) before any other mutation can start. Keeps the
   form state model simple and prevents losing unsaved
   changes silently.

10. **Lifecycle gate stays at `_require_editable`.** Every new
    mutation route (per-row edit / per-row add / bulk
    inactivate / bulk reactivate) wraps with the existing
    `_require_editable` helper and calls
    `lifecycle.invalidate_if_validated` from the service layer.
    Same pattern every other Setup-page mutation uses.

11. **Stack choice: vanilla JS, no AG Grid.** The shipped
    surfaces (Invitations / Responses tables, Instruments
    edit-lock, 13B sort affordance) prove the row-level
    edit + search + filter shape works on plain HTML +
    targeted progressive-enhancement JS. AG Grid is a
    separate question (Segment 17A) — 15F doesn't depend
    on it.

12. **Bulk-status audit shape: two events.** Inactivate
    selected emits `reviewer.bulk_inactivated` (snapshot
    envelope listing the flipped ids); Reactivate selected
    emits `reviewer.bulk_reactivated`. Mirror events on
    Reviewees + Relationships. Distinct event types
    surface the operator's two distinct intents in the
    audit log without forcing readers to crack a
    set_changes envelope.

13. **Inline-edit always emits `reviewer.updated`** (changes
    envelope) regardless of which fields the operator
    changed — including a status-only change made via the
    inline-edit form. The targeted `reviewer.bulk_*` events
    stay reserved for the bulk-button path. Avoids
    double-emission when a single mutation surface (the
    inline-edit form) writes a single event.

14. **Search `<datalist>` capped at 200 alphabetically.** A
    1500-row roster's autocomplete list is bigger than
    operators ever scan; the suggestions are a convenience,
    not the search itself. The server-side filter still
    runs against the full roster when the operator types
    something not in the suggestions. Pilot feedback can
    re-tune the cap if needed.

15. **Cancel keeps the row checked.** Cancelling an inline
    edit restores the row's pre-edit text without touching
    the checkbox state — the operator can immediately retry
    Edit, or click Inactivate selected, etc. Selection is
    independent of edit state.

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

- Edit affordance: selection-driven from the right-side
  operator-actions card. Operator checks exactly one row,
  card's **Edit** button enables, click flips that row's
  editable cells from text to `<input>` / `<select>` (Status
  becomes a `<select>`) in-place. Card's Edit button
  transforms into **Save** + **Cancel**. Save POSTs the row,
  Cancel restores the snapshot. One row at a time.
- No per-row Edit button on the table itself; the table has
  no Actions column. The card carries every mutation
  affordance.
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

### Right-side operator-actions card

Half-width card on the right; left-side half-width is the
existing 15A friendly-labels editor. Two vertically-stacked
sections, in order:

**Section 1 — Search + status filter.**
- Status `<select>` (`all` / `active` / `inactive`) +
  Search `<input list>` autocompleted from the unfiltered
  roster's distinct identity values. Submit + Clear
  buttons; "Showing N of M" muted line below when a filter
  is active.
- Server-side filter (the route's view-adapter consults
  `request.query_params`); `GET` form so URL state survives
  reload.
- Search matches case-insensitive substring across the
  page's identity columns (name / email; for Relationships,
  reviewer-name + reviewee-name).
- 200-row cap applies to the unfiltered render; lifts to
  500 when either filter is applied.
- `<datalist>` autocomplete capped at 200 alphabetically
  (Decision 14) — the suggestions are a convenience, not
  the search itself; the server-side filter handles
  anything the operator types.

**Section 2 — Action buttons.**
- Four buttons in one row — **Edit** ·
  **Inactivate selected** · **Reactivate selected** ·
  **Add new row**. Selected-count pill (e.g. "3 selected")
  to the left of the row when ≥1 row is selected.
  Selection-dependent enable/disable per Decision 3:

  | Selection | Edit | Inact. sel. | React. sel. | Add new row |
  | --- | --- | --- | --- | --- |
  | 0 rows | disabled | disabled | disabled | enabled |
  | 1 row | **enabled** | enabled | enabled | enabled |
  | 2+ rows | disabled | enabled | enabled | enabled |
  | Any row in edit mode | (Save + Cancel) | disabled | disabled | disabled |

- **Edit** opens inline edit on the single checked row.
  Card's Edit button transforms into **Save** + **Cancel**.
  Save POSTs to the per-page edit endpoint
  (`reviewer.updated` / `reviewee.updated` /
  `relationship.updated`, canonical `changes` envelope per
  Segment 11K). Cancel restores the row's pre-edit text and
  leaves the checkbox checked.
- **Add new row** prepends a fresh `<tr>` at the top of the
  table in edit mode (empty inputs in every editable column;
  Status defaults to `active`). Card's Edit button
  transforms into **Save** + **Cancel** (same mechanism as
  Edit). Save POSTs to the per-page create endpoint
  (`reviewer.created` / `reviewee.created` /
  `relationship.created`, snapshot envelope) and 303s back.
  Cancel removes the row from the DOM — nothing was
  persisted, no server round-trip.
- **Inactivate selected** / **Reactivate selected** fire on
  the current checkbox selection without entering edit mode.
  Two distinct audit events per Decision 12 — Inactivate
  selected emits `reviewer.bulk_inactivated` (snapshot
  envelope listing the flipped ids); Reactivate selected
  emits `reviewer.bulk_reactivated`. Mirror events on
  Reviewees (`reviewee.bulk_inactivated` / `.bulk_reactivated`)
  and Relationships
  (`relationship.bulk_inactivated` / `.bulk_reactivated`).
  These work on a one-row selection too, for "flip status
  only" without opening the edit form (Decision 13:
  inline-edit still emits `reviewer.updated` even for a
  status-only change made via the form).
- All four buttons render in fixed positions (always
  present) so the card layout doesn't reflow on selection
  change. No bulk Edit (Edit is single-row by design); no
  bulk Delete.
- Validation feedback for Edit / Add: inline error banner
  inside the row being edited (or inside the
  operator-actions card if the error is row-shape-agnostic),
  not a page-top banner.

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
`update_reviewer`, `bulk_inactivate`, `bulk_reactivate`. Each
mutator calls `lifecycle.invalidate_if_validated` and emits the
canonical audit event. New event types
(`reviewer.created` / `.updated` / `.bulk_inactivated` /
`.bulk_reactivated`) registered in `EVENT_SCHEMAS` per
Decisions 12–13. No UI
surface yet — the CSV importer continues to be the only writer.

**Tests.** Service-layer happy-path + lifecycle gate + audit
envelope strict-mode checks.

### PR 2 — Reviewers page right-side operator-actions card scaffolding

**Scope.** Split the full-width 15A friendly-labels editor
into a half-width left card + new half-width right
operator-actions card. Wire the right card's top section
(search + filter) end-to-end: view-adapter consumes
`request.query_params`, route slices the result with the
200 / 500 cap, template renders the muted "Showing N of M"
line. The card's action-button row renders as inert
placeholders this PR. No per-row edit yet. Establishes the
find-a-row machinery the later UI PRs sit on.

**Tests.** Layout regression, filter parsing, cap application,
"Showing N of M" rendering.

### PR 3 — Reviewers page selection-driven Edit + bulk inactivate + Add new row

**Scope.** Template grows the leftmost checkbox column.
Right-side operator-actions card's four action buttons light
up with selection-dependent enable/disable: **Edit** (single
row), **Inactivate selected** / **Reactivate selected** (≥1
row), **Add new row** (always). Edit + Add new row drive the
shared inline-edit machinery in-table (Edit button on the
card transforms into Save + Cancel while a row is being
edited). Inactivate / Reactivate fire on the checkbox
selection without opening edit mode. Route handlers wire the
new service-layer calls from PR 1. Targeted inline JS for the
selection→button-state binding, the row-state toggle, the
"one row in edit mode at a time" guard (disables other
checkboxes during edit), the selected-count pill, and the
Add-new-row DOM insertion. No per-row Actions column on the
table.

**Tests.** Selection→button-state binding, single-row Edit
happy-path, bulk inactivate / reactivate, Add new row POST,
Cancel-removes-row-from-DOM, "one row at a time" guard
(other checkboxes disabled during edit), selected-count pill
behaviour.

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
and only edits tags + status. Add new row prepends an empty
`<tr>` whose Reviewer + Reviewee inputs are `<input list>`
typeaheads (Decision 14: datalist capped at 200
alphabetically; the server-side validator handles anything
the operator types and resolves it back to an id).
UNIQUE constraint on `(session_id, reviewer_id, reviewee_id)`
— Add must reject duplicate pairs with a clean inline error.

### PR 6 — Defensive status re-check on `invitations_send_one` (folded into PR 3)

**Scope.** One-liner in `_operations.py:541` — refuse to send
when `reviewer.status != "active"`. Ride-along with PR 3
(when per-row Inactivate first becomes operator-reachable).
Catches the direct-POST / stale-tab edge case. Kept as a
named entry here for traceability; doesn't ship as a
standalone PR.

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

## Working notes

All open questions resolved 2026-05-15 (see Decisions 12–15
in `## Decisions locked`). PR scoping conversations may surface
follow-on details (e.g. exact button copy, error-banner
placement specifics) but no design-shape decisions are
outstanding.

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
