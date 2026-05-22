# All buttons — operator surface audit

Snapshot of every interactive button (and button-styled anchor)
across the operator-facing templates. Last refreshed 2026-05-22
after the post-18F/18G UI-polish pass: **Danger Zone moved off
Session Home to Edit Session Details** (commit b490825 — the
Delete Data + Delete session buttons now live on `session_edit.html`,
bottom-right of the edit half-grid); **Create Session gates submit
on Name + Code** with both Create and Sessions-lobby Clone redirecting
to Edit Session on success (commit 9cfb70e); and the chrome strip's
single **Invitations** pill was split into four lifecycle states —
`Not created` / `Not sent` / `Partially sent` / `All sent`
(commit 49f1875). The prior "refreshed 2026-05-15" pass covered
Segment 15F (Enhanced Setup pages): the Reviewers / Reviewees /
Relationships Setup pages gained an Operator actions card — a
search / status filter strip and a selection-driven Edit ·
Inactivate · Activate · Add-new-row button row, plus an inline
Save / Cancel pair in Edit / Add mode.

Use it to:

- spot drift between similar buttons on different pages,
- pick the canonical class when adding a new button,
- queue up button-style migration sweeps.

Scope:

- Operator-facing templates only — `app/web/templates/operator/`
  including its `partials/` folder. The reviewer surface is out of
  scope here.
- Excludes pure form controls (text inputs, checkboxes, file inputs,
  selects). Only includes button-shaped controls (`<button>`,
  `<input type="submit">`, button-styled `<a>`).
- Conditional / state-dependent buttons are listed per state when
  the canonical style differs (e.g. an active "Generate" vs a
  disabled placeholder "Generate").
- Per-row buttons in tables (Invitations, Responses, sessions list)
  are listed once with a "per row" note.
- Per-instrument buttons on the Instruments page are listed once
  (one instrument's worth) with a "per instrument card" note.

Canonical-style column references the taxonomy in
[`spec/ui_elements.md`](../spec/ui_elements.md) §6 Buttons. The
shorthand:

| Tag | What it means |
|---|---|
| **Primary** | Solid `accent-blue`. The page's single main affirmative action. |
| **Secondary** | White bg + `border-default` outline. The default button — routine submits, Cancel, View detail, etc. |
| **Destructive** | Outline `accent-red`. Confirm-step inside `.card.danger-zone`. |
| **Outline-amber** | Outline `accent-amber-dark`. Recovery action inside a `.card.lock`. |
| **Primary (CTA)** | Layout variant of Primary — large, centered. `.btn-cta`. |
| **Nav (page-internal)** | Page-internal view switcher (e.g. Email Template tabs). Reuses the chrome's `.nav-tab` styling for visual consistency: active uses `<span class="nav-tab active" aria-current="page">`, siblings use `<a class="nav-tab">`, "coming soon" uses `<span class="nav-tab disabled" aria-disabled="true">`. Wrap in `.tab-strip`. (See `spec/ui_elements.md` §6.) |
| **Inline text-button (`.btn-reset`)** | Single-line link-styled button used to revert a single field inside an editor without cancelling and exiting. (See `spec/ui_elements.md` §6.) |
| **Return-to (`.back-link`)** | Top-of-body inline link to "wherever you came from" (`return_to_url` round-trip). Used by chrome-detour pages (Operator Settings, About) and session-level child pages (Rule Builder). (See `spec/ui_elements.md` §6.) |
| **Chrome utility link** | Top-right chrome anchors — Sign-out (`signout`), Settings / About (`chrome-link`). Defined in `spec/visual_style_rrw.md`, not in `.btn` family. |
| **Chrome nav** | The two-row session top-nav tabs (`.nav-tab`). Lives in `spec/visual_style_rrw.md` "Operator session chrome", not in the `.btn` family. |
| **Disabled** | Visual variant of any role — opacity 0.5, `cursor: not-allowed`, `aria-disabled="true"`. |
| **Inline link** | `<a>` rendered without a `.btn` class; reads as a hyperlink, not a button. |

Format note: counts for "per row" / "per instrument" buttons are
counted as 1 in the running number; the duplication is in markup,
not in distinct affordances.

---

## Section 1 — Chrome (every session-scoped operator page)

Source: `app/web/templates/operator/partials/session_top_nav.html`.
Rendered inside `.session-nav-card` on every session-scoped page.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 1 | Session-home anchor | Session Home | `<a>` | `session-home-anchor` (active variant when on Home) | Chrome nav | Tall left-column anchor, two-row chrome |
| 2 | Setup tab row | Reviewers | `<a>` | `nav-tab` (`.active` when current page) | Chrome nav | |
| 3 | Setup tab row | Reviewees | `<a>` | `nav-tab` | Chrome nav | |
| 4 | Setup tab row | Relationships | `<a>` | `nav-tab` | Chrome nav | Replaced Assignments in 15D PR 6a |
| 5 | Setup tab row | Instruments | `<a>` | `nav-tab` | Chrome nav | |
| 6 | Setup tab row | Email Template | `<a>` | `nav-tab` | Chrome nav | |
| 7 | Operations tab row | Validate | `<a>` | `nav-tab` | Chrome nav | |
| 8 | Operations tab row | Assignments | `<a>` | `nav-tab` | Chrome nav | Moved Setup → Operations in 15D PR 6a |
| 9 | Operations tab row | Previews | `<a>` | `nav-tab` | Chrome nav | |
| 10 | Operations tab row | Invitations | `<a>` | `nav-tab` | Chrome nav | |
| 11 | Operations tab row | Responses | `<a>` | `nav-tab` | Chrome nav | |

---

## Section 2 — Sessions overview (`/operator/sessions`)

Source: `app/web/templates/operator/sessions_list.html`.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 11 | Header | Create new session | `<a>` | `btn` | Primary | Top-right of the page header |
| 12 | Empty state | Create new session | `<a>` | `btn-cta` | Primary (CTA) | Only when zero sessions exist |
| 13 | Danger Zone (bulk delete) | Delete selected sessions | `<button type="submit">` | `btn destructive` | Destructive | Card hidden until ≥1 row tick — see `spec/sessions_overview.md` |

---

## Section 3 — New session (`/operator/sessions/new`)

Source: `app/web/templates/operator/session_new.html`.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 14 | Session details form | Create session | `<button type="submit">` | `btn` | Primary | Posts to `POST /operator/sessions` |
| 15 | Session details form | Cancel | `<a>` | `btn secondary` | Secondary | Returns to the sessions lobby |

---

## Section 4 — Edit session (`/operator/sessions/{id}/edit`)

Source: `app/web/templates/operator/session_edit.html`. As of
2026-05-22 (commit b490825) the page splits as a `.bottom-grid`:
the edit form on the left, the Danger Zone card on the
bottom-right.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 16 | Form card | Save changes | `<button type="submit">` | `btn` | Primary | |
| 17 | Form card | Cancel | `<a>` | `btn secondary` | Secondary | Returns to Session Home |
| 17a | Danger Zone (bottom-right) | Delete Data | `<button type="submit">` | `btn destructive` | Destructive | Posts `/delete-data`. Moved from Session Home 2026-05-22 (commit b490825). |
| 17b | Danger Zone (bottom-right) | Delete session | `<button type="submit">` | `btn destructive` | Destructive (Disabled when Activated) | Posts `/delete`; disabled while session is `ready`. Moved from Session Home 2026-05-22 (commit b490825). |

---

## Section 5 — Session Home (`/operator/sessions/{id}`)

Source: `app/web/templates/operator/session_detail.html` + the
included partials `_quick_setup_card.html`, `_extract_data_card.html`.

### 5a — Next Action card

State-conditional surface; one or two buttons render at a time.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 18 | Next Action (draft / pre-validation) | Validate Setup | `<a>` | `btn` | Primary | |
| 19 | Next Action (draft / pre-validation) | See validation details | `<a>` | `btn secondary` | Secondary | |
| 20 | Next Action (validated, no errors) | Activate Session | `<a>` or `<button type="submit">` | `btn` | Primary | Links to `/validate?activate=1` if warnings need acknowledging; otherwise direct POST `/activate` |
| 21 | Next Action (validated, no errors) | See previews | `<a>` | `btn secondary` | Secondary | |
| 22 | Next Action (validated, no errors) | See validation details | `<a>` | `btn secondary` | Secondary | |
| 23 | Next Action (validated, no errors) | Revert to draft | `<button type="submit">` | `btn secondary` | Secondary | Posts `/revert` |
| 24 | Next Action (validated, errors) | See validation details | `<a>` | `btn` | Primary | Promoted to primary when validation has errors |
| 25 | Next Action (activated, §1) | Manage invitations | `<a>` | `btn` | Primary | |
| 26 | Next Action (activated, §1) | Monitor responses | `<a>` | `btn secondary` | Secondary | |
| 27 | Next Action (activated, §2) | Pause Session | `<button type="submit">` | `btn` | Primary | Posts `/revert`; sits below an `<hr class="next-action-divider">` |

### 5b — Danger Zone — relocated

The Danger Zone card (former buttons #28 / #29) moved off Session
Home to the bottom-right of Edit Session Details on 2026-05-22
(commit b490825). See §4 entries 17a / 17b above.

### 5c — Session Details card (left column)

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 30 | Session Details | Edit | `<a>` | `btn secondary` | Secondary | Bottom-right of the card; opens `session_edit.html`. Inert (`aria-disabled`) while session is `ready`. |

### 5d — Quick Setup card (right column, top; partial)

Source: `partials/_quick_setup_card.html`. Also rendered inert on
`session_new.html` as a preview.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 31 | Quick Setup footer | Submit | `<button type="submit">` | `btn secondary` | Secondary | Disabled until ≥1 file selected; posts `/quick-setup/submit-all` |
| 32 | Quick Setup footer | Lock / Unlock | `<button type="submit">` | `btn secondary` | Secondary | Two-state toggle; posts `/quick-setup/lock` |

### 5e — Extract Data card (right column, bottom; partial)

Source: `partials/_extract_data_card.html`. Five live tiles
(Reviewers / Settings / Reviewees / Responses / Relationships)
plus an inert zip-all footer. See `spec/session_home.md` §2 for
the tile table.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 33 | Extract Data (per row, live) | Download | `<a>` | `btn secondary` | Secondary | Wired routes per tile: `/export/{reviewers,reviewees,relationships,responses,settings}.csv`. Greys out (`btn secondary disabled`) when the underlying count is 0 (per 12A-3 polish #781). Settings tile is always clickable. |
| 34 | Extract Data (zip-all footer) | Download all | `<a>` | `btn secondary disabled` | Secondary (Disabled) | Inert — zip bundle is a future segment. |

---

## Section 6 — Reviewers Setup (`/operator/sessions/{id}/reviewers`)

Source: `app/web/templates/operator/session_reviewers.html`.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 105 | Reviewer tag labels (15A Slice 3) | Cancel | `<button type="button">` | `btn secondary` | Secondary | Inline JS reverts the three tag inputs to their initial snapshot and re-disables the pair. Hidden when `is_ready`. |
| 106 | Reviewer tag labels (15A Slice 3) | Save labels | `<button type="submit">` | `btn secondary` | Secondary | Posts `/reviewers/field-labels`. Starts `disabled`; inline JS flips both Save + Cancel on when the form is dirty. Hidden when `is_ready`. |
| 34 | Lock card (when Activated) | Revert to draft | `<button type="submit">` | `btn alert` | Outline-amber | Inside `.card.lock` |
| 35 | Upload Reviewers | Upload | `<button type="submit">` | `btn secondary` | Secondary | Posts `/reviewers/import`. Sits **below** the preview table (PR #892). |
| 36 | Operator actions (15F) | Edit | `<button type="button">` | `btn secondary` | Secondary | Selection-driven — enabled on exactly one checked row; JS navigates to `?edit_id=`. |
| 123 | Operator actions (15F) | Inactivate | `<button type="submit">` | `btn secondary` | Secondary | `formaction` `/reviewers/bulk-inactivate`; enabled on ≥1 selection. |
| 124 | Operator actions (15F) | Activate | `<button type="submit">` | `btn secondary` | Secondary | `formaction` `/reviewers/bulk-reactivate`; enabled on ≥1 selection. |
| 125 | Operator actions (15F) | Add new row | `<a>` | `btn secondary` | Secondary | Links to `?add=1`; renders disabled while a row is being edited / added. |
| 126 | Operator actions (15F) | Search | `<button type="submit">` | `btn secondary` | Secondary | Submits the search + status filter GET. Sits last in the single inline `filter-actions` row, after the selection-driven buttons + pill. |
| 127 | Operator actions (15F) | Clear | `<a>` | `btn secondary` | Secondary | Resets the filter; rendered only when a filter is active. |
| 128 | Operator actions (15F, Edit/Add) | Save | `<button type="submit">` | `btn primary` | Primary | Submits the `/{id}/update` or `/create` form; shown below the divider in Edit/Add mode. |
| 129 | Operator actions (15F, Edit/Add) | Cancel | `<a>` | `btn secondary` | Secondary | Returns to the plain list. |
| 37 | Danger Zone | Delete all reviewers | `<button type="submit">` | `btn destructive` | Destructive | Posts `/reviewers/delete-all`. Sits **below** the preview table. |

---

## Section 7 — Reviewees Setup (`/operator/sessions/{id}/reviewees`)

Source: `app/web/templates/operator/session_reviewees.html`.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 107 | Reviewee field labels (15A Slice 3) | Cancel | `<button type="button">` | `btn secondary` | Secondary | Inline JS reverts the six inputs (Name / Email / Photo / Tag 1-3) to their initial snapshot and re-disables the pair. Hidden when `is_ready`. |
| 108 | Reviewee field labels (15A Slice 3) | Save labels | `<button type="submit">` | `btn secondary` | Secondary | Posts `/reviewees/field-labels`. Starts `disabled`; dirty-check via inline JS. Hidden when `is_ready`. |
| 38 | Lock card (when Activated) | Revert to draft | `<button type="submit">` | `btn alert` | Outline-amber | |
| 39 | Upload Reviewees | Upload | `<button type="submit">` | `btn secondary` | Secondary | Sits **below** the preview table (PR #892). |
| 40 | Operator actions (15F) | Edit | `<button type="button">` | `btn secondary` | Secondary | Selection-driven — enabled on exactly one checked row; JS navigates to `?edit_id=`. |
| 130 | Operator actions (15F) | Inactivate | `<button type="submit">` | `btn secondary` | Secondary | `formaction` `/reviewees/bulk-inactivate`; enabled on ≥1 selection. |
| 131 | Operator actions (15F) | Activate | `<button type="submit">` | `btn secondary` | Secondary | `formaction` `/reviewees/bulk-reactivate`; enabled on ≥1 selection. |
| 132 | Operator actions (15F) | Add new row | `<a>` | `btn secondary` | Secondary | Links to `?add=1`; renders disabled while a row is being edited / added. |
| 133 | Operator actions (15F) | Search | `<button type="submit">` | `btn secondary` | Secondary | Submits the search + status filter GET. Sits last in the single inline `filter-actions` row, after the selection-driven buttons + pill. |
| 134 | Operator actions (15F) | Clear | `<a>` | `btn secondary` | Secondary | Resets the filter; rendered only when a filter is active. |
| 135 | Operator actions (15F, Edit/Add) | Save | `<button type="submit">` | `btn primary` | Primary | Submits the `/{id}/update` or `/create` form; shown below the divider in Edit/Add mode. |
| 136 | Operator actions (15F, Edit/Add) | Cancel | `<a>` | `btn secondary` | Secondary | Returns to the plain list. |
| 41 | Danger Zone | Delete all reviewees | `<button type="submit">` | `btn destructive` | Destructive | Sits **below** the preview table. |

---

## Section 8 — Relationships Setup (`/operator/sessions/{id}/relationships`)

Source: `app/web/templates/operator/session_relationships.html`.
Per-pair context table (15D PR 2) — mirrors the Reviewers /
Reviewees Setup shape (Upload + Danger Zone + preview table).

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 109 | Pair-context labels (15A Slice 3) | Cancel | `<button type="button">` | `btn secondary` | Secondary | Inline JS reverts the three pair-context inputs to their initial snapshot and re-disables the pair. Hidden when `is_ready`. |
| 110 | Pair-context labels (15A Slice 3) | Save labels | `<button type="submit">` | `btn secondary` | Secondary | Posts `/relationships/field-labels`. Starts `disabled`; dirty-check via inline JS. Hidden when `is_ready`. |
| 42 | Lock card (when Activated) | Revert to draft | `<button type="submit">` | `btn alert` | Outline-amber | |
| 43 | Upload Relationships | Upload | `<button type="submit">` | `btn secondary` | Secondary | Posts `/relationships/import`. CSV columns: `ReviewerEmail`, `RevieweeEmail`, `PairContextTag1..3`, `Status`. Sits **below** the preview table (PR #892). |
| 44 | Operator actions (15F) | Edit | `<button type="button">` | `btn secondary` | Secondary | Selection-driven — enabled on exactly one checked row; JS navigates to `?edit_id=`. |
| 137 | Operator actions (15F) | Inactivate | `<button type="submit">` | `btn secondary` | Secondary | `formaction` `/relationships/bulk-inactivate`; enabled on ≥1 selection. |
| 138 | Operator actions (15F) | Activate | `<button type="submit">` | `btn secondary` | Secondary | `formaction` `/relationships/bulk-reactivate`; enabled on ≥1 selection. |
| 139 | Operator actions (15F) | Add new row | `<a>` | `btn secondary` | Secondary | Links to `?add=1`; disabled while editing / when either roster is empty. |
| 140 | Operator actions (15F) | Search | `<button type="submit">` | `btn secondary` | Secondary | Submits the "Search by" + search GET. Sits last in the single inline `filter-actions` row, after the selection-driven buttons + pill. |
| 141 | Operator actions (15F) | Clear | `<a>` | `btn secondary` | Secondary | Resets the filter; rendered only when a filter is active. |
| 142 | Operator actions (15F, Edit/Add) | Save | `<button type="submit">` | `btn primary` | Primary | Submits the `/{id}/update` or `/create` form; reviewer / reviewee chosen via name-or-email `<datalist>` pickers. |
| 143 | Operator actions (15F, Edit/Add) | Cancel | `<a>` | `btn secondary` | Secondary | Returns to the plain list. |
| 45 | Danger Zone | Delete all relationships | `<button type="submit">` | `btn destructive` | Destructive | Posts `/relationships/delete-all`. Sits **below** the preview table. |

**Retired:** Pre-15D this section described the Setup-row
Assignments page (Rule Based Assignment card + Upload Manual
Assignment card + Delete-all assignments). That page moved to
the Operations row in 15D PR 6a; the manual-upload affordance
retired with the move (dev-diagnostic only post-15D); the
buttons live in **Section 11.5 — Assignments Operations** below.

---

## Section 9 — Instruments Setup (`/operator/sessions/{id}/instruments`)

Source: `app/web/templates/operator/instruments_index.html`.
Per-instrument buttons are listed once; the page renders one set
per instrument card.

### 9a — Page-level

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 48 | Status + bulk-actions | Show all when closed / Don't show any when closed | `<button type="submit">` | `btn secondary` | Secondary | Two-state toggle; posts `/instruments/visibility/all-on` or `/all-off` |
| 49 | Lock card (when Activated) | Revert to draft | `<button type="submit">` | `btn alert` | Outline-amber | |

### 9b — Per-instrument card (one set per instrument)

| # | Card / sub-section | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 50 | Section A — Identity (locked, Edit affordance) | Edit | `<a>` | `btn secondary` (or `btn secondary disabled` while another instrument is in edit mode) | Secondary (Disabled when conflicting edit lock active) | Per `spec/instruments.md` |
| 51 | Section C — Action row (editing) | Save | `<button type="submit" form="dfsave-{iid}">` | `btn secondary` | Secondary | Bulk-save covers description, Display Fields, Response Fields, Response Fields Help |
| 52 | Section C — Action row (editing) | Cancel | `<a>` | `btn secondary` | Secondary | Returns to locked state |
| 53 | Section C — Action row (locked) | Edit | `<a>` | `btn secondary` | Secondary | Mirrors button #50; same state machine |
| 54 | Section A right card | Open this Instrument / Close this instrument | `<button type="submit">` | `btn secondary` | Secondary | Two-state toggle on `accepting_responses` |
| 55 | Section A right card | Show when closed / Don't show when closed | `<button type="submit">` | `btn secondary` | Secondary | Two-state toggle on `responses_visible_when_closed` |
| 56 | Section E — per-instrument action row | Add instrument | `<button type="submit">` | `btn secondary` | Secondary | Posts `/instruments/add` with `after={iid}`; disabled while an edit lock is active |
| 56a | Section E — per-instrument action row | Add group instrument | `<button type="submit">` | `btn secondary` | Secondary | Posts `/instruments/add-group` (Segment 13C group-scoped instruments); same edit-lock gating |
| 56b | Section E — per-instrument action row | Replicate | `<button type="submit">` | `btn secondary` | Secondary | Posts `/instruments/{iid}/replicate` — clones the card immediately after it (Segment 13C PR 3); same edit-lock gating |
| 57 | Section E — per-instrument action row | Delete | `<button type="submit">` | `btn destructive` | Destructive | Last button in the per-instrument action row (Danger Zone sub-card retired). Ships `disabled`; a paired confirm checkbox flush-right below the row (`data-delete-confirm` / `data-delete-btn`) gates it. Disabled outright when it is the only instrument or an edit lock is active. |

### 9c — RTD card (page-bottom, "Response Type Definitions")

| # | Card / sub-section | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 58 | RTD row (locked) | Edit | `<a>` | `btn secondary` (or disabled when an instrument card is unlocked) | Secondary (Disabled when conflicting edit lock) | Per `spec/instruments.md` "One editing context at a time" |
| 59 | RTD row (editing) | Save | `<button type="submit">` | `btn secondary` | Secondary | |
| 60 | RTD row (editing) | Cancel | `<a>` | `btn secondary` | Secondary | |
| 61 | RTD row (operator-defined) | Delete | `<button type="submit">` | `btn destructive` | Destructive | Cascade-confirm dialog gates the destructive call |
| 62 | "Add a Response Type" row | Add | `<button type="submit">` | `btn secondary` | Secondary | Disabled while any edit context is active |

---

## Section 10 — Email Template (`/operator/sessions/{id}/setupinvite`)

Source: `app/web/templates/operator/session_setupinvite.html`.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 63 | Template selector (top-of-body) | Invitation / Reminder / Responses received (active) | `<span aria-current="page">` | `nav-tab active` | **Nav (page-internal)** — current view | Reuses the chrome's `.nav-tab` styling for visual consistency |
| 64 | Template selector (top-of-body) | Invitation / Reminder / Responses received (inactive) | `<a>` | `nav-tab` | **Nav (page-internal)** — sibling views | One per template |
| 65 | Email composer (per-field reset) | Reset {{ row.field }} to default | `<button type="submit">` | `btn-reset` | Inline text-button (`.btn-reset`) | Canonical link-styled inline button — reverts a single field without exiting the editor |
| 66 | Email composer actions (bottom-left) | Cancel | `<a>` | `btn secondary` | Secondary | Returns to Session Home |
| 67 | Email composer actions (bottom-left) | Save | `<button type="submit">` | `btn secondary` | Secondary | Disabled until a composer field is touched; posts `/setupinvite` |

---

## Section 11 — Validate (`/operator/sessions/{id}/validate`)

Source: `app/web/templates/operator/session_validate.html`.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 68 | Activate banner (warnings present) | Cancel | `<a>` | `btn alert` | Outline-amber | Returns to validate page without `?activate=1` |
| 69 | Activate banner (warnings present) | Acknowledge and activate | `<button type="submit">` | `btn danger-solid` | Primary (filled) — recovery-as-confirm | Posts `/activate` with `acknowledge_warnings=true` |
| 70 | Activate banner (errors present) | Cancel | `<a>` | `btn alert` | Outline-amber | Errors block activation; this just dismisses the banner |
| 71 | Severity filter chip strip | All / Errors / Warnings / Info | `<a>` | `severity-chip` (with `.active` state) | Filter chip (custom — not in §6) | One per severity level; not part of the canonical button family |

---

## Section 11.5 — Assignments Operations (`/operator/sessions/{id}/assignments`)

Source: `app/web/templates/operator/session_assignments.html`.
Page moved from Setup row to Operations row in 15D PR 6a. Pair-
level context now lives on the Relationships Setup page (Section
8); this page is the materialised-derivative surface where the
operator runs the rule engine to generate the `(reviewer,
reviewee, instrument)` assignment matrix.

Generation now fires from the Workflow card's stepper (rendered
by `next_action_card.html`) — the standalone Generate / Rule
Based Assignment card and the standalone Self-reviews toggle card
retired. Per-instrument Self review is an inline checkbox column
on the Per-instrument status table, and Self review / Show on
that table are plain form checkboxes, not `.btn`-shaped controls,
so they aren't enumerated here. The remaining `.btn`-shaped
controls are the operator-actions search / bulk card.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 71g | Operator-actions card | Inactivate | `<button type="submit">` | `btn secondary` | Secondary | `formaction` `/assignments/bulk-inactivate`; submits the `assignments-bulk-form` from the row-select checkbox column; enabled on ≥1 selection. |
| 71h | Operator-actions card | Activate | `<button type="submit">` | `btn secondary` | Secondary | `formaction` `/assignments/bulk-activate`; enabled on ≥1 selection. |
| 71i | Operator-actions card | Search | `<button type="submit">` | `btn secondary` | Secondary | Submits the "Search by" (All / Reviewers / Reviewees) + search GET; last in the inline `filter-actions` row. |
| 71j | Operator-actions card | Clear | `<a>` | `btn secondary` | Secondary | Resets the filter; rendered only when a search term is active. |

Button numbers in this section are bracketed (`71a` etc.) to
avoid a wholesale renumber of every subsequent section. A future
re-audit can flatten them into the canonical sequence.

---

## Section 12 — Previews (`/operator/sessions/{id}/previews`)

Source: `app/web/templates/operator/session_previews.html` +
included `_preview_picker.html` and `_email_preview_region.html`
partials.

### 12a — Previewing-as picker (partial)

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 72 | Previewing as | Apply | `<button type="submit">` | `btn secondary` | Secondary | Filters to a specific reviewer |
| 73 | Previewing as (nav row) | ← Previous | `<a>` | `btn secondary` (`disabled` when none) | Secondary (Disabled at end of list) | |
| 74 | Previewing as (nav row) | Next → | `<a>` | `btn secondary` (`disabled` when none) | Secondary (Disabled at end of list) | |
| 75 | Previewing as (nav row) | Random | `<button type="submit">` | `btn secondary` | Secondary | Posts `/previews/random` |

### 12b — Email preview tabs (partial)

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 76 | Email preview tabs (active) | {{ tab.label }} | `<span aria-current="page">` | `nav-tab active` | **Nav (page-internal)** — current view | Same pattern as Email Template selector |
| 77 | Email preview tabs (sibling) | {{ tab.label }} | `<a>` | `nav-tab` | **Nav (page-internal)** — sibling views | |
| 78 | Email preview tabs (coming soon) | {{ tab.label }} (coming soon) | `<span aria-disabled="true">` | `nav-tab disabled` | **Nav (page-internal)** — disabled | Reserved tabs not yet wired |

---

## Section 13 — Manage Invitations (`/operator/sessions/{id}/invitations`)

Source: `app/web/templates/operator/session_invitations.html`.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 79 | Main action card | View outbox | `<a>` | `btn secondary` | Secondary | Dev-diagnostic surface |
| 80 | Main action card | Generate invitations | `<button type="submit">` | `btn secondary` | Secondary (Disabled when no uninvited reviewers or session not ready) | Generate-only (no send) is Secondary per the "send is Primary" rule |
| 81 | Main action card | Send all pending | `<button type="submit">` | `btn` | Primary (Disabled when nothing pending or session not ready) | Sending → Primary |
| 82 | Main action card | Regenerate all | `<button type="submit">` | `btn secondary` | Secondary (Disabled when no invitations or session not ready) | |
| 83 | Main action card | Send reminders to {{ N }} incomplete reviewer(s) | `<button type="submit">` | `btn` | Primary (Disabled when no incomplete or session not ready) | Sending → Primary |
| 84 | Filter card | Clear | `<a>` | `btn secondary` | Secondary | |
| 85 | Filter card | Apply | `<button type="submit">` | `btn secondary` | Secondary | |
| 86 | Invitations table (per row) | Send | `<button type="submit">` | `btn secondary` | Secondary (Disabled when session not ready) | One per row |
| 87 | Invitations table (per row) | Remind | `<button type="submit">` | `btn secondary` | Secondary (Disabled when row is complete or session not ready) | One per row |

---

## Section 14 — Responses (`/operator/sessions/{id}/responses`)

Source: `app/web/templates/operator/session_responses.html`.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 88 | Main action card | Manage Invitations | `<a>` | `btn secondary` | Secondary | Cross-link to the Invitations page |
| 89 | Main action card | Send reminders to {{ N }} incomplete reviewer(s) | `<button type="submit">` | `btn` | Primary (Disabled when no incomplete or session not ready) | Sending → Primary; matches button #83 on the Invitations page |
| 90 | Filter card | Clear | `<a>` | `btn secondary` | Secondary | |
| 91 | Filter card | Apply | `<button type="submit">` | `btn secondary` | Secondary | |

---

## Section 15 — Operator Settings (`/operator/settings`)

Source: `app/web/templates/operator/operator_settings.html`.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 92 | Email send (SMTP) form | Cancel | `<a>` | `btn secondary` | Secondary | Returns to `?return_to=<path>` |
| 93 | Email send (SMTP) form | Save | `<button type="submit">` | `btn secondary` | Secondary | Disabled until input touched |
| 93a | Date & time card (18B) | Save timezone | `<button type="submit">` | `btn secondary` | Secondary | Posts `/operator/settings/timezone`; persists the `display_timezone` preference |
| 94 | Danger Zone | Clear all settings | `<button type="submit">` | `btn destructive` | Destructive | Posts `/operator/settings/clear` |

---

## Section 16 — Rule Builder (`/operator/sessions/{id}/assignments/rule-based-editor`)

Source: `app/web/templates/operator/session_rule_builder.html` +
included `_rule_builder_card.html` and `_available_rulesets_card.html`
partials. The Rule Builder card is documented in detail in
[`spec/rule_based_assignment.md`](../spec/rule_based_assignment.md)
§7 — most of its action buttons render conditionally per render
branch (seeded read-only / saved Personal / unsaved draft / blank).
This audit captures the canonical button shapes.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 95 | Rule Builder header | ← Back to Assignments | `<a>` | `back-link` | Return-to (`.back-link`) | Top-of-body navigation; same class as Operator Settings / About |
| 96 | Rule Builder action row | Copy | `<button type="submit">` | `btn secondary` | Secondary | Forks the selected ruleset into a new Personal draft |
| 97 | Rule Builder action row | Save | `<button type="submit">` | `btn secondary` | Secondary | Persists the in-progress draft |
| 98 | Rule Builder action row | Cancel | `<a>` | `btn secondary` | Secondary | Discards in-progress edits and returns to the saved selection |
| 99 | Rule Builder action row | Delete | `<button type="submit">` | `btn destructive` | Destructive | Soft-deletes the selected Personal ruleset |

---

## Section 17 — Global chrome utility menu (every page)

Source: `app/web/templates/base.html` (chrome top-right). Renders
on every page (operator + reviewer); only the operator view is
enumerated here.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 100 | Chrome user menu | Settings | `<a>` | `chrome-link` | Chrome utility link | Round-trips via `?return_to=<path>` |
| 101 | Chrome user menu | About | `<a>` | `chrome-link` | Chrome utility link | Same `?return_to=<path>` pattern |
| 102 | Chrome user menu | Sign out | `<a>` | `signout` | Chrome utility link | Hits `/.auth/logout` (Easy Auth) |

---

## Section 18 — About page (`/about`)

Source: `app/web/templates/about.html`. Read-only chrome-detour
page; the only interactive control is the back-link.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 103 | Page top | ← Back to {{ return_to_label }} | `<a>` | `back-link` | Return-to (`.back-link`) | Returns operator to wherever they came from |

---

## Section 15 supplement — Operator Settings back-link

Operator Settings also renders a top-of-body back-link that the
original audit missed. Listed here with a continuing number; the
canonical home is the `.back-link` row in `spec/ui_elements.md` §6.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 104 | Page top (above the SMTP form card) | ← Back to {{ return_to_label }} | `<a>` | `back-link` | Return-to (`.back-link`) | |

---

## Section 19 — Accounts Management (`/operator/sys-admin/users`)

Source: `app/web/templates/operator/sys_admin_users.html`. Sys-
admin-gated. Reshaped 2026-05-12 (PRs #895 → #897) from per-row
inline buttons + safety checkboxes to a per-row selection
checkbox + a single bulk-action toolbar above the table.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 111 | Page top | ← Back to Sessions Diagnostics | `<a>` | `back-link` | Return-to (`.back-link`) | |
| 112 | Invite by email | Invite | `<button type="submit">` | `btn secondary` | Secondary | Posts `/sys-admin/users/invite`. Starts `disabled`; inline JS enables when the email input has text. |
| 113 | Invite by email | Cancel | `<button type="reset">` | `btn secondary` | Secondary | Clears the email + sys-admin checkbox. Starts `disabled`; same dirty-check as Invite. |
| 114 | Workspace users — bulk toolbar | Admit / Revoke | `<button type="submit">` | `btn secondary` | Secondary | Label flips based on the selected row's `is_operator`. Revoke gated client-side on `session_count == 0`; server-side guard `still_owner` returns 409 otherwise. Starts `disabled`; activates when one row is selected. |
| 115 | Workspace users — bulk toolbar | Remove from all sessions | `<button type="submit">` | `btn secondary` | Secondary | Posts `/sys-admin/users/{id}/remove-from-all-sessions`. Active when row has `session_count > 0` AND `sole_owner_count == 0`; server-side guard `sole_owner` returns 409 otherwise. |
| 116 | Workspace users — bulk toolbar | Promote / Demote | `<button type="submit">` | `btn secondary` | Secondary | Label flips based on the selected row's `is_sys_admin`. Demote gated client-side on `not last sys-admin`; server-side guard `last_admin` returns 409 otherwise. |
| 117 | Workspace users — bulk toolbar | Delete | `<button type="submit">` | `btn destructive` | Destructive | Hard-deletes the `users` row. Active when `session_count == 0`; server-side guard `owns_sessions` returns 409 otherwise. Redirect omits `?selected=` so the deleted row isn't re-selected on the next render. |

Notes:

- **Toolbar layout.** `display: flex; flex-wrap: wrap; gap: 8px;
  align-items: center; justify-content: flex-start;` so the four
  buttons cluster next to the row checkboxes (left-aligned, PR
  #897). Group labels (`Operator:` / `Sys Admin:` / `|`) live
  inline between the buttons.
- **Single-row selection.** Inline JS enforces one row at a time;
  the other checkboxes grey out when one is checked. Self-row
  renders `(self)` instead of a checkbox.
- **Selection persistence.** Every action that doesn't delete the
  row round-trips the selected `user_id` via the redirect's
  `?selected={id}` query param; the template stamps `checked` on
  the matching row so the operator can chain a second action
  without re-selecting (PR #897).
- **Safety checkbox retired.** The earlier inline "confirm
  promote / demote" checkbox is gone (PR #895); the service-
  layer `last_admin` guard is the structural safety net.

---

## Section 20 — Per-session Audit log (`/operator/sys-admin/sessions/{id}/audit-log`)

Source: `app/web/templates/operator/sys_admin_session_audit_log.html`.
Sys-admin-gated. Filter strip reshaped 2026-05-12 (PRs #898 +
#899).

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 118 | Page top | ← Back to Sessions Diagnostics | `<a>` | `back-link` | Return-to (`.back-link`) | |
| 119 | Audit log card heading | Download CSV | `<a>` | `btn secondary` | Secondary | Posts to `/export/audit_log.csv`; the URL forward-carries the active filter set so the CSV matches the on-screen view. |
| 120 | Filter strip (button row) | Apply filters | `<button type="submit">` | `btn secondary` | Secondary | Right-aligned within a `.btn-pair` with `justify-content: flex-end`; Secondary style (was Primary pre-#899) so it doesn't compete with the Download CSV button up at the card heading. |
| 121 | Filter strip (button row) | Clear filters | `<a>` | `btn secondary` | Secondary | Renders only when `filter_form.is_active`. Resets to the canonical viewer URL with no query string. |
| 122 | Per-row detail | (expander) | `<summary>` inside `<details>` | `audit-detail summary` | Inline disclosure (custom) | PR 3 inline expander surfacing the canonical 11K detail envelopes in human-readable sections + raw JSON in a nested `<details>`. Not a `.btn` but interactive — listed for completeness. |

Notes:

- **Filter strip layout** (PR #898 reshape, post-15A):
  - Left column: Event-type multi-select with `Ctrl/Cmd-click
    to select multiple` hint.
  - Right column flows actor email → From / To date selectors
    side-by-side (each half-width, flex children) → severity
    checkboxes on a single inline row.
- **Button-row gap.** `.btn-pair` carries `margin-top: 16px;
  margin-bottom: 24px;` so the row sits clear of both the
  filter strip above and the audit-log table below (PR #899).

---

## Drift / inconsistencies surfaced by the audit

Status of the rough edges the original audit surfaced (now post the
first follow-up sweep):

### 1. "Return to where you came from" affordance (resolved + class adopted)

Several pages share a "go back to the page you came from"
pattern:

- **Chrome-detour pages** — Operator Settings (#104), About
  (#103). Both surfaced from the chrome top-right utility menu
  (#100 / #101), round-trip via `?return_to=<path>`.
- **Session-level child pages** — Rule Builder (#95). Off the
  Assignments page, no chrome of its own.

These pages now use the canonical **`.back-link`** class — a
small inline link rendered as
`<a class="back-link" href="{{ return_to_url }}">← Back to
{{ return_to_label }}</a>` at the top of the body, above the
working cards. Documented in `spec/ui_elements.md` §6.

The Rule Builder previously rolled its own plain `<a>` anchor
inside a card; this PR moves it to `.back-link`, putting it in
visual line with Operator Settings and About.

**Edit Session (`session_edit.html`)** is a remaining outlier —
it carries a `Cancel` anchor (#17) instead of a back-link. The
Cancel and a back-link would do roughly the same thing today
(both navigate to Session Home), but the form-editor pattern
reads coherently as Save+Cancel. Migrating to a back-link would
either drop Cancel entirely or change Cancel's semantics to
"revert the form in place"; either is a design call deferred to
a follow-up.

### 2. Send → Primary, generate → Secondary (resolved)

Adopted convention: any button that **actually sends email** is
Primary; buttons that prepare or rebuild local state without
sending are Secondary. Applied to the Invitations / Responses
pages as part of the follow-up sweep:

- #80 Generate invitations → Secondary.
- #81 Send all pending → Primary.
- #82 Regenerate all → Secondary (it doesn't send).
- #83 Send reminders to N incomplete reviewer(s) → Primary.
- #89 Send reminders … on the Responses page → Primary
  (already was; now consistent with #83).

Per-row Send / Remind (#86, #87) stay Secondary — per-row context
overrides the role-based convention.

### 3. Next Action card during Activated state (flagged for follow-up)

The current activated-state Next Action surface renders Manage
invitations (Primary) + Monitor responses (Secondary) +
Pause Session (separate confirm-step Primary). The proposed
direction is for the activated-state Primary action to be a
single **Generate + send invitations** flow, with the existing
Manage / Monitor anchors demoted to Secondary supporting actions.

Flagged here for a future Next-Action-card segment; the current
treatment ships unchanged.

### 4. Active-tab styling harmonised (resolved)

Page-internal nav tabs (Email Template selector #63/#64 and
email-preview tabs #76/#77/#78) now reuse the chrome's
`.nav-tab` styling. Active tab is `<span class="nav-tab active"
aria-current="page">`; siblings are `<a class="nav-tab">`;
"coming soon" tabs are `<span class="nav-tab disabled"
aria-disabled="true">`.

Wrapper is `<div class="tab-strip tab-strip-page">` — the new
`.tab-strip-page` modifier (in `base.html`) gives the row the
chrome's grey row tint (`#f3f4f6`), a thin `#d1d5db` border, and
rounded corners so the active tab's white background reads
against the strip just like the chrome's Setup row. Hover and
disabled treatments fall out of the existing `.nav-tab` rules.
`spec/ui_elements.md` §6 "Nav button" documents the convention.

### 5. Inline-styled "Reset to default" promoted to `.btn-reset` (resolved)

The previously inline-styled `chrome-link` reset button (#65) is
now a canonical `.btn-reset` class — link-styled inline button
that posts a form to revert a single field inside an editor
without cancelling and exiting. Documented in
`spec/ui_elements.md` §6. The CSS rule sits in `base.html`;
no other templates use it yet, but it can apply to any future
editor with per-field overrides.

### 6. ~~Perma-disabled `Edit Reviewers` / `Edit Reviewees` (deferred)~~ — RESOLVED 2026-05-15

Segment 15F landed the per-record-edit surface. The previously
perma-disabled `Edit` anchors (#36 / #40 / #44) are now live
`<button>`s in the Operator actions card, selection-driven and
enabled on a single checked row. No remaining drift here.

### 7. Confirm-checkbox-gates-button standard (resolved)

App-wide standard: every destructive button (delete-all, delete-data,
delete-session, revert, replace-upload, per-instrument delete, clear-
responses) ships `disabled` and is enabled only while a paired confirm
checkbox is ticked. Pairing is declarative — `data-delete-confirm="KEY"`
on the checkbox, `data-delete-btn="KEY"` on the button — and a single
global JS block in `app/web/templates/base.html` wires every pair. Any
operator / reviewer page picks it up for free by tagging the checkbox +
button. This replaced the assorted per-page inline confirm-checkbox JS.

---

## Maintenance

When a button changes (added / removed / restyled), update this
table and the table of contents in this file's header. Treat it
as a snapshot, not a real-time index — one full re-audit per
visible-change PR is overkill, but a periodic refresh
(roughly per restyle bundle, or when `spec/ui_elements.md` §6
changes) keeps drift in check.
