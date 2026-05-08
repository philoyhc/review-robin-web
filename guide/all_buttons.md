# All buttons — operator surface audit

Snapshot of every interactive button (and button-styled anchor)
across the operator-facing templates as of 2026-05-08. Use it to:

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
| **Nav (page-internal)** | Page-internal view switcher (e.g. Email Template tabs). Active tab renders disabled-Primary; siblings render as Secondary anchors. (See `spec/ui_elements.md` §6.) |
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
| 4 | Setup tab row | Assignments | `<a>` | `nav-tab` | Chrome nav | |
| 5 | Setup tab row | Instruments | `<a>` | `nav-tab` | Chrome nav | |
| 6 | Setup tab row | Email Template | `<a>` | `nav-tab` | Chrome nav | |
| 7 | Operations tab row | Validate | `<a>` | `nav-tab` | Chrome nav | |
| 8 | Operations tab row | Previews | `<a>` | `nav-tab` | Chrome nav | |
| 9 | Operations tab row | Invitations | `<a>` | `nav-tab` | Chrome nav | |
| 10 | Operations tab row | Responses | `<a>` | `nav-tab` | Chrome nav | |

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

Source: `app/web/templates/operator/session_edit.html`.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 16 | Form card | Save changes | `<button type="submit">` | `btn` | Primary | |
| 17 | Form card | Cancel | `<a>` | `btn secondary` | Secondary | Returns to Session Home |

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

### 5b — Danger Zone (left column, bottom)

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 28 | Danger Zone | Delete Data | `<button type="submit">` | `btn destructive` | Destructive | Posts `/delete-data` |
| 29 | Danger Zone | Delete session | `<button type="submit">` | `btn destructive` | Destructive (Disabled when Activated) | Posts `/delete`; disabled while session is `ready` |

### 5c — Session Details card (right column, top)

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 30 | Session Details | Edit | `<a>` | `btn secondary` | Secondary | Bottom-right; opens `session_edit.html` |

### 5d — Quick Setup card (right column, bottom; partial)

Source: `partials/_quick_setup_card.html`. Also rendered inert on
`session_new.html` as a preview.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 31 | Quick Setup footer | Submit | `<button type="submit">` | `btn secondary` | Secondary | Disabled until ≥1 file selected; posts `/quick-setup/submit-all` |
| 32 | Quick Setup footer | Lock / Unlock | `<button type="submit">` | `btn secondary` | Secondary | Two-state toggle; posts `/quick-setup/lock` |

### 5e — Extract Data card (left column, middle; partial)

Source: `partials/_extract_data_card.html`. All buttons inert today
(scaffold pending Segment 12A).

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 33 | Extract Data (per row) | Download | `<a>` | `btn secondary` (with `disabled aria-disabled="true"` until Segment 12A wires the route) | Secondary (Disabled) | One per entity row + a final bundle row |

---

## Section 6 — Reviewers Setup (`/operator/sessions/{id}/reviewers`)

Source: `app/web/templates/operator/session_reviewers.html`.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 34 | Lock card (when Activated) | Revert to draft | `<button type="submit">` | `btn alert` | Outline-amber | Inside `.card.lock` |
| 35 | Upload Reviewers | Upload | `<button type="submit">` | `btn secondary` | Secondary | Posts `/reviewers/import` |
| 36 | Upload Reviewers | Edit Reviewers | `<a>` | `btn secondary disabled` | Secondary (Disabled) | Inline-editing not yet implemented |
| 37 | Danger Zone | Delete all reviewers | `<button type="submit">` | `btn destructive` | Destructive | Posts `/reviewers/delete-all` |

---

## Section 7 — Reviewees Setup (`/operator/sessions/{id}/reviewees`)

Source: `app/web/templates/operator/session_reviewees.html`.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 38 | Lock card (when Activated) | Revert to draft | `<button type="submit">` | `btn alert` | Outline-amber | |
| 39 | Upload Reviewees | Upload | `<button type="submit">` | `btn secondary` | Secondary | |
| 40 | Upload Reviewees | Edit Reviewees | `<a>` | `btn secondary disabled` | Secondary (Disabled) | |
| 41 | Danger Zone | Delete all reviewees | `<button type="submit">` | `btn destructive` | Destructive | |

---

## Section 8 — Assignments Setup (`/operator/sessions/{id}/assignments`)

Source: `app/web/templates/operator/session_assignments.html` +
the included `_rule_based_card.html` partial.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 42 | Lock card (when Activated) | Revert to draft | `<button type="submit">` | `btn alert` | Outline-amber | |
| 43 | Rule Based Assignment (live) | Generate | `<button type="submit">` | `btn secondary` | Secondary | Posts `/assignments/rule-based/generate` |
| 44 | Rule Based Assignment (live) | Edit ruleset | `<a>` | `btn secondary` | Secondary | Opens the Rule Builder |
| 45 | Rule Based Assignment (placeholder branch) | Generate | `<button type="button">` | `btn secondary disabled` | Secondary (Disabled) | Inert when no live ruleset selected |
| 46 | Upload Manual Assignment | Upload | `<button type="submit">` | `btn secondary` | Secondary | Posts `/assignments/manual/import` |
| 47 | Danger Zone | Delete all assignments | `<button type="submit">` | `btn destructive` | Destructive | Posts `/assignments/delete-all` |

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
| 56 | Add new instrument footer | Add new instrument | `<button type="submit">` | `btn secondary` | Secondary | Posts `/instruments/add`; disabled while another card is in edit mode |
| 57 | Section C — Danger sub-card | Delete this instrument | `<button type="submit">` | `btn destructive` | Destructive | Confirm checkbox inside the danger sub-card |

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
| 63 | Template selector (top-of-body) | Invitation / Reminder / Responses received (active) | `<button type="button">` | `btn disabled aria-disabled="true"` | **Nav (page-internal)** — current view | One per template; only the active one renders disabled |
| 64 | Template selector (top-of-body) | Invitation / Reminder / Responses received (inactive) | `<a>` | `btn secondary` | **Nav (page-internal)** — sibling views | One per template |
| 65 | Email composer (per-field reset) | Reset {{ row.field }} to default | `<button type="submit">` | `chrome-link` (inline-styled) | Inline link | One per field that carries an override |
| 66 | Email composer actions (bottom-left) | Cancel | `<a>` | `btn secondary` | Secondary | Returns to Session Home |
| 67 | Email composer actions (bottom-left) | Save | `<button type="submit">` | `btn` | Primary | Disabled until a composer field is touched; posts `/setupinvite` |

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
| 76 | Email preview tabs (active) | {{ tab.label }} | `<button type="button">` | `btn disabled` | **Nav (page-internal)** — current view | Same pattern as Email Template selector |
| 77 | Email preview tabs (sibling) | {{ tab.label }} | `<a>` | `btn secondary` | **Nav (page-internal)** — sibling views | |
| 78 | Email preview tabs (coming soon) | {{ tab.label }} | `<button type="button">` | `btn secondary disabled` | Secondary (Disabled) | Reserved tabs not yet wired |

---

## Section 13 — Manage Invitations (`/operator/sessions/{id}/invitations`)

Source: `app/web/templates/operator/session_invitations.html`.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 79 | Main action card | View outbox | `<a>` | `btn secondary` | Secondary | Dev-diagnostic surface |
| 80 | Main action card | Generate invitations | `<button type="submit">` | `btn` | Primary (Disabled when no uninvited reviewers or session not ready) | |
| 81 | Main action card | Send all pending | `<button type="submit">` | `btn secondary` | Secondary (Disabled when nothing pending or session not ready) | |
| 82 | Main action card | Regenerate all | `<button type="submit">` | `btn secondary` | Secondary (Disabled when no invitations or session not ready) | |
| 83 | Main action card | Send reminders to {{ N }} incomplete reviewer(s) | `<button type="submit">` | `btn secondary` | Secondary (Disabled when no incomplete or session not ready) | |
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
| 89 | Main action card | Send reminders to {{ N }} incomplete reviewer(s) | `<button type="submit">` | `btn` | Primary (Disabled when no incomplete or session not ready) | Note: rendered as Primary here even though the same affordance on the Invitations page is Secondary — see "Drift" below |
| 90 | Filter card | Clear | `<a>` | `btn secondary` | Secondary | |
| 91 | Filter card | Apply | `<button type="submit">` | `btn secondary` | Secondary | |

---

## Section 15 — Operator Settings (`/operator/settings`)

Source: `app/web/templates/operator/operator_settings.html`.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 92 | Email send (SMTP) form | Cancel | `<a>` | `btn secondary` | Secondary | Returns to `?return_to=<path>` |
| 93 | Email send (SMTP) form | Save | `<button type="submit">` | `btn` | Primary | Disabled until input touched |
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
| 95 | Rule Builder header | ← Back to Assignments | `<a>` | (no `.btn` class — plain anchor) | Inline link | The page lacks a chrome top-nav |
| 96 | Rule Builder action row | Copy | `<button type="submit">` | `btn secondary` | Secondary | Forks the selected ruleset into a new Personal draft |
| 97 | Rule Builder action row | Save | `<button type="submit">` | `btn` | Primary | Persists the in-progress draft |
| 98 | Rule Builder action row | Delete | `<button type="submit">` | `btn destructive` | Destructive | Soft-deletes the selected Personal ruleset |

---

## Drift / inconsistencies surfaced by the audit

A short list of rough edges to consider in a follow-up sweep. Not
fixed in this PR.

1. **Rule Builder back link (#95)** is a plain `<a>` without a
   `.btn` class. Every other "back to <page>" affordance on
   operator surfaces lives inside the chrome top-nav; the Rule
   Builder is the only sub-page that rolls its own back link.
   Either add it to the chrome or style it as a Secondary button.

2. **"Send reminders" affordance** (#83 vs #89) renders Secondary
   on the Invitations page and Primary on the Responses page. Same
   POST endpoint, same disabled rules, same label format. Unless
   the Responses page intends "Send reminders" to be the page's
   single affirmative action (it might — the page is monitor-
   focused), one of the two should be brought in line.

3. **Manage invitations links** (#25 inside Next Action's
   activated state and #88 on the Responses page) — both link to
   the same `/invitations` page. The Next Action one is Primary
   ("the page's single affirmative action"); the Responses one is
   Secondary ("cross-link"). Consistent with the role each page
   plays; flagged here for future ergonomics review.

4. **Active-tab styling.** The Email Template selector (#63) and
   the email-preview tabs (#76) use `btn disabled` for the active
   state; the chrome's session-level nav tabs (#1–#10) use a
   different `.nav-tab.active` class. Both work, but the duplicate
   patterns are a likely source of confusion for new contributors.
   The new "Nav button" class in `spec/ui_elements.md` §6 names
   the page-internal flavour; the chrome flavour is documented in
   `spec/visual_style_rrw.md`.

5. **Inline `style=` on `chrome-link`** for the per-field "Reset
   to default" button (#65). Documented as out-of-scope inline
   styling in `spec/ui_elements.md` "Drift catalogue" — folded
   into the same sweep that retires the rest of the inline-styled
   buttons.

6. **"Edit Reviewers" / "Edit Reviewees"** (#36, #40) render as
   `btn secondary disabled` anchors with a "coming soon" tooltip.
   They've stayed disabled across the chrome migration; either
   wire them up as part of a per-record-edit segment or hide the
   anchors entirely until that segment lands.

---

## Maintenance

When a button changes (added / removed / restyled), update this
table and the table of contents in this file's header. Treat it
as a snapshot, not a real-time index — one full re-audit per
visible-change PR is overkill, but a periodic refresh
(roughly per restyle bundle, or when `spec/ui_elements.md` §6
changes) keeps drift in check.
