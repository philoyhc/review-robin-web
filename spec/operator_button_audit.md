# All buttons — operator surface audit

Every interactive button (and button-styled anchor) on the
operator-facing surface, organised by page and card. Each row names the
control and the **role it must carry**.

> **`spec/ui_elements.md` §6 owns the role definitions.** The legend
> below is the reading key for the *Canonical* column, never a second
> definition of a role; where the two could differ, §6 governs. For
> Session Home's behaviour rather than its buttons read
> `spec/session_home.md`; for the Workflow card's state machine,
> `spec/workflow_card.md`.

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
| **Primary** | Solid fill. The page's single main affirmative action. |
| **Secondary** | White bg + `border-default` outline. The default button — routine submits, Cancel, View detail, etc. |
| **Destructive** | Outline red. The confirm step inside `.card.danger-zone`, and the roster Setup pages' `Delete` for checkbox-selected rows — which carries the role **outside** a danger zone. See `spec/ui_elements.md` §6. |
| **Alert** | Filled amber, light label. The attention-seeking affirmative — used where an action is safe but consequential. (See `spec/ui_elements.md` §6.) |
| **Outline-amber** | Outline amber. Recovery action inside a `.card.lock`. |
| **Primary (CTA)** | Layout variant of Primary — large, centered. `.btn-cta`. **No operator surface prescribes it**; a page reaching for it needs a design decision first, not a class. |
| **Nav (page-internal)** | Page-internal view switcher (e.g. Email Template tabs). Reuses the chrome's `.nav-tab` styling for visual consistency: active uses `<span class="nav-tab active" aria-current="page">`, siblings use `<a class="nav-tab">`, "coming soon" uses `<span class="nav-tab disabled" aria-disabled="true">`. Wrap in `.tab-strip`. (See `spec/ui_elements.md` §6.) |
| **Inline text-button (`.btn-reset`)** | Single-line link-styled button used to revert a single field inside an editor without cancelling and exiting. (See `spec/ui_elements.md` §6.) |
| **Return-to (`.back-link`)** | Top-of-body inline link to "wherever you came from" (`return_to_url` round-trip). Required on chrome-detour pages (Operator Settings, About) and on the Sys Admin child pages. (See `spec/ui_elements.md` §6.) |
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
| 4 | Setup tab row | Relationships | `<a>` | `nav-tab` | Chrome nav | Renders only when `relationships_enabled` |
| 5 | Setup tab row | Instruments | `<a>` | `nav-tab` | Chrome nav | |
| 6 | Setup tab row | Email Template | `<a>` | `nav-tab` | Chrome nav | |
| 7 | Operations tab row | Validate | `<a>` | `nav-tab` | Chrome nav | |
| 8 | Operations tab row | Assignments | `<a>` | `nav-tab` | Chrome nav | Operations row, never Setup |
| 9 | Operations tab row | Previews | `<a>` | `nav-tab` | Chrome nav | |
| 10 | Operations tab row | Invitations | `<a>` | `nav-tab` | Chrome nav | |
| 11 | Operations tab row | Responses | `<a>` | `nav-tab` | Chrome nav | |
| 12 | Setup tab row | Observers | `<a>` | `nav-tab` | Chrome nav | Renders only when `observers_enabled`. **Numbered 12 rather than slotted after Relationships** — numbers here are stable identifiers other documents cite, so a new tab takes the next free one and the row order is not the render order |
| 13 | Operations tab row | Extract data | `<a>` | `nav-tab` | Chrome nav | The sixth Operations tab. Render order is Assignments, Validate, Previews, Invitations, Responses, Extract data — `spec/operator_ui_concept.md` §5 carries the row contract |

---

## Section 2 — Sessions overview (`/operator/sessions`)

Source: `app/web/templates/operator/sessions_list.html`.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 11 | Search | Add new session | `<a>` | `btn` | Primary | The lobby's **only** create affordance, in every state — the first-run card names this button instead of carrying a second one (`spec/sessions_overview.md` "Empty state") |
| 12 | Search | Rehydrate / Go to Archive | `<a>` | `btn secondary` | Secondary | Always rendered; `Go to Archive` is active in every state, `Rehydrate` in every state **in which it renders at all** — it is gated behind `rehydrate_enabled`, which ships false, so by default it is absent rather than inactive (`spec/rehydrate.md`), `Cancel` only when live sessions exist |
| 13 | Row expander (single / bulk) | Delete | `<button type="submit">` | `btn destructive` | Destructive | Lives in the row expander, not a standalone Danger Zone card; gated behind a "Yes, delete" checkbox — see `spec/sessions_overview.md` |

---

## Section 3 — New session (`/operator/sessions/new`)

Source: `app/web/templates/operator/session_new.html`.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 14 | Session details form | Create session | `<button type="submit">` | `btn` | Primary | Posts to `POST /operator/sessions` |
| 15 | Session details form | Cancel | `<a>` | `btn secondary` | Secondary | Returns to the sessions lobby |

---

## Section 4 — Edit session — no page, no buttons

**There is no Edit session page.**
`GET /operator/sessions/{id}/edit` is a **308 permanent redirect** to
`/operator/sessions/{id}?editing=1#session-config`
(`app/web/routes_operator/_session_home.py`), keeping the
`require_session_operator` gate so a stale bookmark from a non-owner is
refused rather than bounced. **No buttons render on this path.**

The affordances a reader may be looking for here are on Session Home:
Save / Cancel / Lock in the Session details card footer (§5b), and
Delete Data / Delete session in the Danger Zone (§5e).

---

## Section 5 — Session Home (`/operator/sessions/{id}`)

Source: `app/web/templates/operator/session_detail.html` plus the
included partials `partials/next_action_card.html`,
`partials/_quick_setup_card.html`, `partials/session_top_nav.html` and
`partials/session_setup_status_row.html`.

### 5a — Workflow card

Source: `partials/next_action_card.html`. **The state cascade must not
be duplicated here** — `spec/workflow_card.md` §"Workflow stepper — single-row
button layout" owns which button appears in which of the card's states,
and a second copy of that table is exactly the drift this document
exists to prevent. What belongs here is the **vocabulary**: which role
each button site carries, and that no site carries an inline style.

| # | Label | Element | CSS class | Canonical |
|---|---|---|---|---|
| 144 | Prepare session | `<button type="submit">` | `btn` / `btn secondary` | Primary / Secondary — rendered in both, per state |
| 145 | Create invites | `<button type="submit">` | `btn` | Primary |
| 146 | Send invites | `<button type="submit">` | `btn` | Primary |
| 147 | Activate session | `<a>` or `<button type="submit">` | `btn` | Primary — anchor to `/validate?activate=1` when warnings need acknowledging, otherwise a direct POST |
| 148 | Send reminders | `<button type="submit">` | `btn` | Primary |
| 149 | Revert to draft | `<button type="submit">` | `btn secondary` | Secondary — two sites, per state |
| 150 | Close session | `<button type="submit">` | `btn secondary` | Secondary |
| 151 | Release responses | `<button type="submit">` | `btn secondary` | Secondary |
| 152 | Stop releasing responses | `<button type="submit">` | `btn secondary` | Secondary |
| 153 | Archive session | `<button type="submit">` | `btn danger-solid` | **Alert (filled amber)** — serious but recoverable, per §6 |
| 154 | Regenerate & prepare | `<button type="submit">` | `btn danger-solid` | **Alert (filled amber)** |
| 155 | Cancel | `<a>` | `btn alert` | **Outline-amber** — the mandatory Cancel on an inline `.banner.banner-warning`, per `spec/ui_elements.md` §5a. Not a lock card: §6's lock-card example is one use of this role, not its definition |

### 5b — Session Details card (`#session-config`)

Source: `session_detail.html`, the `.card#session-config` below the
Workflow card. The session's fields are edited **in place** here, gated
by `?editing=1`; there is no Edit page to hop to.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 156 | Session details footer | Save | `<button type="submit">` | `btn secondary` | Secondary | Submits `form="config-save-{id}"` to the shared `/config` POST |
| 157 | Session details footer | Cancel | `<a>` | `btn secondary` | Secondary | Returns to `#session-config` unedited |
| 158 | Session details footer | Lock / Unlock | `<a>` | `btn secondary` | Secondary | Two-state toggle; adds or drops `?editing=1`. Rendered `aria-disabled` with an explanatory `title` once the session is past `validated` — the lock-card recovery path, not a hidden control |
| 159 | Owners sub-card | Add owner | `<button type="submit">` | `btn` | Primary | The one Primary on this card; the `required` input blocks an empty submit without JavaScript |

### 5c — Quick Setup card

Source: `partials/_quick_setup_card.html`. Also rendered on
`session_new.html`, where the slots' inputs associate with the
create-session form via `form="create-session-form"` and the card
renders neither Submit nor Lock of its own — the page's **Create
session** button submits both halves.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 31 | Quick Setup footer | Submit | `<button type="submit">` | `btn secondary` | Secondary | Disabled until ≥1 file selected; posts `/quick-setup/submit-all` |
| 32 | Quick Setup footer | Lock / Unlock | `<button type="submit">` | `btn secondary` | Secondary | Two-state toggle; posts `/quick-setup/lock` |
| 160 | Quick Setup slot | Cancel | `<a>` | `btn alert` | **Outline-amber** | Per-slot cancel on an inline `.banner.banner-error` — same banner convention as #155, not a lock card |

### 5d — Extract Data — not on this page

`session_detail.html` does **not** include the Extract Data card.
`partials/_extract_data_card.html` renders only on
`session_extract_data.html` (`/operator/sessions/{id}/extract-data`).
**That page's buttons are not specified in this document** — a gap in
its coverage, not a page without buttons.

### 5e — Danger Zone (`#danger-zone`)

Source: `session_detail.html`, `.card.danger-zone#danger-zone` — the
bottom-right of Home's `.bottom-grid`.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 17a | Danger Zone | Delete Data | `<button type="submit">` | `btn destructive` | Destructive (outline red) | Ships `disabled aria-disabled="true"`; a confirm checkbox enables it. The checkbox is itself disabled while the session is `ready`, so the button cannot be reached — audit U3 |
| 17b | Danger Zone | Delete session | `<button type="submit">` | `btn destructive` | Destructive (outline red) | Same gating. Session-delete subsumes data-delete: ticking it shows the data checkbox selected but inert |

These two keep the `17a` / `17b` numbers §4 lists them under, so a
reader following either reference lands on the same pair.

---

## Section 6 — Reviewers Setup (`/operator/sessions/{id}/reviewers`)

Source: `app/web/templates/operator/session_reviewers.html`.

> **Lifecycle. This note governs §§6, 7, 8 and 8.5** — every roster
> Setup page — and is stated here once rather than four times.
>
> The selection-driven controls, the Upload button and the Danger Zone
> button render only while the session is `is_editable`
> (`draft` / `validated`); outside those states they must be
> **absent**, not disabled. Since each page moved to the Unlock panel
> — Reviewers 19P.1, Observers 19P.2, Reviewees and Relationships
> 19P.3 — that is achieved by suppressing the whole panel the cards
> live in, which is the same rule reaching them through one gate
> instead of three. The enable/disable rules in the Notes column
> describe behavior *within* an editable session. `Clear` and `Search`
> render in every state.
>
> **Observers is the exception, and it is now the whole page, not just
> its checkboxes.** 19P.2 relaxed all eight of its mutating routes to
> `_require_not_archived`, so its row actions, its import and its
> `delete-all` are live through `ready` and `expired` and its Unlock
> panel is suppressed only on `archived`. The sentence here used to
> scope the looser gate to the row checkboxes alone, on the reasoning
> that they drove the cohort rule editor; the editor moved into the
> expander with the actions and the gate went with it. See
> `spec/lifecycle.md` §5 for why an observer's roster is allowed the
> wider predicate.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 105 | Reviewer tag labels | Cancel | `<button type="button">` | `btn secondary` | Secondary | Inline JS reverts the three tag inputs to their initial snapshot and re-disables the pair. Suppressed whenever the session is not `is_editable`. **In the Unlock panel** since 19P.1 — and in the card's `.card-columns` fallback home the editor keeps for the states the panel cannot render in, where the partial drops this pair rather than disabling it. |
| 106 | Reviewer tag labels | Save labels | `<button type="submit">` | `btn secondary` | Secondary | Posts `/reviewers/field-labels`. Starts `disabled`; inline JS flips both Save + Cancel on when the form is dirty. Suppressed whenever the session is not `is_editable` — which is why the whole panel is suppressed rather than disabled, since a locked page must carry no `Save labels` anywhere. **In the Unlock panel** since 19P.1; its redirect carries `?unlocked=1` so the save does not close the panel it was made from. |
| 34 | Lock card (when Activated) | Revert to draft | `<button type="submit">` | `btn alert` | Outline-amber | Inside `.card.lock` |
| 35 | Upload Reviewers | Upload | `<button type="submit">` | `btn secondary` | Secondary | Posts `/reviewers/import`. **In the roster card's Unlock panel** since 19P.1 (it sat below the preview table before); role, route and confirm gate all unchanged by the move. |
| 36 | Row expander (was Operator actions) | Edit | `<button type="button">` | `btn secondary` | Secondary | Selection-driven — enabled on exactly one checked row; JS navigates to `?edit_id=`, and since 19P.1 to `#reviewer-row-<id>` with it so the page lands on the row rather than the top. Rendered into the expander row injected beneath the selection. |
| 123 | Row expander (was Operator actions) | Inactivate | `<button type="submit">` | `btn secondary` | Secondary | `formaction` `/reviewers/bulk-inactivate`; enabled on ≥1 selection **and** `can_edit`. |
| 124 | Row expander (was Operator actions) | Activate | `<button type="submit">` | `btn secondary` | Secondary | `formaction` `/reviewers/bulk-reactivate`; enabled on ≥1 selection **and** `can_edit`. |
| 125 | Table toolbar (was Operator actions) | Add new | `<a>` | `btn secondary` | Secondary | Links to `?add=1`; renders disabled while a row is being edited / added. **Relabelled `Add new` at 19P.1 rung 2a**, when the constraint that shortened it dissolved — `Delete` moved to the row expander, so the two no longer share a row. The old cell's rationale (*"`Add` and `Delete` must both fit this row"*) went with it. **Observers followed at 19P.2 rung 3**, for the same reason and with the same result: its `Delete` moved to the row expander, so its toolbar row is `Clear` / `Add new` / `Search`. **Reviewees and Relationships followed at 19P.3 rung 2** (rows 132 and 139), so all four toolbars now read `Add new`. |
| 161 | Row expander (was Operator actions) | Delete | `<button type="submit">` | `btn destructive` | Destructive | Deletes the checkbox-selected rows via `/reviewers/bulk-delete`. Sits in the row expander with the selection it acts on; nothing sits between `Add new` and `Search` in the toolbar. Two-stage gate: a selection enables the `Yes, delete these` checkbox beside it, which enables this button through the confirm-checkbox-gates-button standard below (`data-delete-btn="reviewers-bulk-delete"`). Posts the bulk form via `form=` + `formaction`, like Inactivate / Activate. The server re-checks both gates: `confirm` must be `"true"`, and where the selected rows carry saved responses so must `acknowledge_response_loss`. |
| 126 | Table toolbar (was Operator actions) | Search | `<button type="submit">` | `btn secondary` | Secondary | Submits the search + status filter GET. Sits last in the `filter-actions` row. The selection-driven buttons are not beside it — they are in the row expander, with the selected count. |
| 127 | Table toolbar (was Operator actions) | Clear | `<a>` | `btn secondary` | Secondary | Resets the filter; rendered only when a filter is active. |
| 128 | Row expander bar (Edit/Add) | Save | `<button type="submit">` | `btn secondary` | Secondary | Submits the `/{id}/update` or `/create` form. **Not "below the divider"** since 19P.1: there is no divider on Reviewers and no editor card — the pair renders in an expander bar directly beneath the edited row, styled as that row's own expander. **Role corrected here, not changed in code:** this row said **Primary** while the template has always rendered `btn secondary`, and so do Reviewees, Relationships and Observers — measured on all four. The audit was wrong about the shipped role rather than the code drifting from the audit, so the cell now records what ships; whether the pair *should* be Primary is a question for the page that next revisits it. |
| 129 | Row expander bar (Edit/Add) | Cancel | `<a>` | `btn secondary` | Secondary | Returns to the plain list, carrying the pager anchor so Cancel lands where Save would. |
| 37 | Danger Zone | Delete all reviewers | `<button type="submit">` | `btn destructive` | Destructive | Posts `/reviewers/delete-all`. **In the roster card's Unlock panel** since 19P.1 (below the preview table before). Rendered only when the roster has rows — not because the route refuses an empty one (it answers 303 and writes "Deleted all 0 reviewers") but because `_delete_all` invalidates a `validated` session before it counts, so an ungated one demotes to `draft` while deleting nothing. |

---

## Section 7 — Reviewees Setup (`/operator/sessions/{id}/reviewees`)

Source: `app/web/templates/operator/session_reviewees.html`.
The lifecycle note above §6 governs this section. The page took the
shared roster shape at 19P.3 — toolbar, row expander, Unlock panel
(`spec/setup_pages.md` § *The roster card and the Unlock panel*).

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 107 | Reviewee field labels | Cancel | `<button type="button">` | `btn secondary` | Secondary | Inline JS reverts the six inputs (Name / Email / Photo / Tag 1-3) to their initial snapshot and re-disables the pair. Suppressed whenever the session is not `is_editable`. |
| 108 | Reviewee field labels | Save labels | `<button type="submit">` | `btn secondary` | Secondary | Posts `/reviewees/field-labels`. Starts `disabled`; dirty-check via inline JS. Suppressed whenever the session is not `is_editable`. |
| 38 | Lock card (when Activated) | Revert to draft | `<button type="submit">` | `btn alert` | Outline-amber | |
| 39 | Upload Reviewees | Upload | `<button type="submit">` | `btn secondary` | Secondary | Posts `/reviewees/import`. In the **Unlock panel's right column** since 19P.3; nothing sits below the preview table. Ships `disabled` behind the `replace-roster` confirm whenever the roster has rows. |
| 40 | Row expander (was Operator actions) | Edit | `<button type="button">` | `btn secondary` | Secondary | Selection-driven — enabled on exactly one checked row; JS navigates to `?edit_id=`. |
| 130 | Row expander (was Operator actions) | Inactivate | `<button type="submit">` | `btn secondary` | Secondary | `formaction` `/reviewees/bulk-inactivate`; enabled on ≥1 selection **and** `can_edit`. |
| 131 | Row expander (was Operator actions) | Activate | `<button type="submit">` | `btn secondary` | Secondary | `formaction` `/reviewees/bulk-reactivate`; enabled on ≥1 selection **and** `can_edit`. |
| 132 | Table toolbar (was Operator actions) | Add new | `<a>` | `btn secondary` | Secondary | Links to `?add=1`; renders disabled while a row is being edited / added. **Relabelled `Add new` at 19P.3 rung 2**, with `Delete` moving to the row expander — the old cell's rationale (*"`Add` and `Delete` must both fit this row"*) went with the constraint. |
| 162 | Row expander (was Operator actions) | Delete | `<button type="submit">` | `btn destructive` | Destructive | Deletes the checkbox-selected rows via `/reviewees/bulk-delete`. Sits in the row expander with the selection it acts on; nothing sits between `Add new` and `Search` in the toolbar. Two-stage gate: a selection enables the `Yes, delete these` checkbox beside it, which enables this button through the confirm-checkbox-gates-button standard below (`data-delete-btn="reviewees-bulk-delete"`). Posts the bulk form via `form=` + `formaction`, like Inactivate / Activate. The server re-checks both gates: `confirm` must be `"true"`, and where the selected rows carry saved responses so must `acknowledge_response_loss`. |
| 133 | Table toolbar (was Operator actions) | Search | `<button type="submit">` | `btn secondary` | Secondary | Submits the search + status filter GET. Sits last in the `filter-actions` row. The selection-driven buttons are not beside it — they are in the row expander, with the selected count. |
| 134 | Table toolbar (was Operator actions) | Clear | `<a>` | `btn secondary` | Secondary | Resets the filter; rendered only when a filter is active. |
| 135 | Row expander bar (Edit/Add) | Save | `<button type="submit">` | `btn secondary` | Secondary | Submits the `/{id}/update` or `/create` form; shown below the divider in Edit/Add mode. **Role corrected 19P.1 rung 4** alongside row 128, not changed in code: `session_reviewees.html` renders `btn secondary` and always has. |
| 136 | Row expander bar (Edit/Add) | Cancel | `<a>` | `btn secondary` | Secondary | Returns to the plain list. |
| 41 | Danger Zone | Delete all reviewees | `<button type="submit">` | `btn destructive` | Destructive | Posts `/reviewees/delete-all`. In the **Unlock panel's left column** since 19P.3, beneath the tag-labels editor; the card renders only on a roster with rows. |

---

## Section 8 — Relationships Setup (`/operator/sessions/{id}/relationships`)

Source: `app/web/templates/operator/session_relationships.html`.
The lifecycle note above §6 governs this section. The per-pair context
table takes the shared roster shape, as it has since 19P.3 — toolbar,
row expander, Unlock panel (`spec/setup_pages.md` § *The roster card
and the Unlock panel*).

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 109 | Pair-context labels | Cancel | `<button type="button">` | `btn secondary` | Secondary | Inline JS reverts the three pair-context inputs to their initial snapshot and re-disables the pair. Suppressed whenever the session is not `is_editable`. |
| 110 | Pair-context labels | Save labels | `<button type="submit">` | `btn secondary` | Secondary | Posts `/relationships/field-labels`. Starts `disabled`; dirty-check via inline JS. Suppressed whenever the session is not `is_editable`. |
| 42 | Lock card (when Activated) | Revert to draft | `<button type="submit">` | `btn alert` | Outline-amber | |
| 43 | Upload Relationships | Upload | `<button type="submit">` | `btn secondary` | Secondary | Posts `/relationships/import`. CSV columns: `ReviewerEmail`, `RevieweeEmail`, `PairContextTag1..3`, `Status`. In the **Unlock panel's right column** since 19P.3; nothing sits below the preview table. |
| 44 | Row expander (was Operator actions) | Edit | `<button type="button">` | `btn secondary` | Secondary | Selection-driven — enabled on exactly one checked row; JS navigates to `?edit_id=`. |
| 137 | Row expander (was Operator actions) | Inactivate | `<button type="submit">` | `btn secondary` | Secondary | `formaction` `/relationships/bulk-inactivate`; enabled on ≥1 selection **and** `can_edit`. |
| 138 | Row expander (was Operator actions) | Activate | `<button type="submit">` | `btn secondary` | Secondary | `formaction` `/relationships/bulk-reactivate`; enabled on ≥1 selection **and** `can_edit`. |
| 139 | Table toolbar (was Operator actions) | Add new | `<a>` | `btn secondary` | Secondary | Links to `?add=1`; disabled while editing / when either roster is empty. **Relabelled `Add new` at 19P.3 rung 2**, with `Delete` moving to the row expander — the old cell's rationale (*"`Add` and `Delete` must both fit this row"*) went with the constraint. |
| 163 | Row expander (was Operator actions) | Delete | `<button type="submit">` | `btn destructive` | Destructive | Deletes the checkbox-selected rows via `/relationships/bulk-delete`. Sits in the row expander with the selection it acts on; nothing sits between `Add new` and `Search` in the toolbar. Two-stage gate: a selection enables the `Yes, delete these` checkbox beside it, which enables this button through the confirm-checkbox-gates-button standard below (`data-delete-btn="relationships-bulk-delete"`). Posts the bulk form via `form=` + `formaction`, like Inactivate / Activate. The server re-checks both gates: `confirm` must be `"true"`, and where the selected rows carry saved responses so must `acknowledge_response_loss`. |
| 140 | Table toolbar (was Operator actions) | Search | `<button type="submit">` | `btn secondary` | Secondary | Submits the Status + search GET; there is no "Search by" side-picker. Sits last in the `filter-actions` row. The selection-driven buttons are not beside it — they are in the row expander, with the selected count. |
| 141 | Table toolbar (was Operator actions) | Clear | `<a>` | `btn secondary` | Secondary | Resets the filter; rendered only when a filter is active. |
| 142 | Row expander bar (Edit/Add) | Save | `<button type="submit">` | `btn secondary` | Secondary | Submits the `/{id}/update` or `/create` form; reviewer / reviewee chosen via name-or-email `<datalist>` pickers. **Role corrected 19P.1 rung 4** alongside row 128, not changed in code: `session_relationships.html` renders `btn secondary` and always has. |
| 143 | Row expander bar (Edit/Add) | Cancel | `<a>` | `btn secondary` | Secondary | Returns to the plain list. |
| 45 | Danger Zone | Delete all relationships | `<button type="submit">` | `btn destructive` | Destructive | Posts `/relationships/delete-all`. In the **Unlock panel's left column** since 19P.3, beneath the pair-context labels editor; the card renders only on a roster with rows. |

---

## Section 8.5 — Observers Setup (`/operator/sessions/{id}/observers`)

Source: `app/web/templates/operator/session_observers.html`.

**Added at the 19P.2 close.** This page had no section: §§6/7/8 were the
other three rosters and the only Observers row in the file was the nav
tab (row 8). That was a gap rather than a scoping choice — this file
audits *every* button on the operator surface — and 19P.2 widened it,
giving the page a row expander, a table toolbar and an Unlock panel.
Numbered 8.5 so the three existing roster sections keep their numbers
and the cross-references to them stay true.

> **Lifecycle.** This page does **not** read `is_editable`. All eight
> mutating routes take `_require_not_archived`, so **every mutating
> control below** — rows 165, 167–180 — renders through `ready` and
> `expired` and is absent only on `archived`. That is the exception the
> gate note above §6 describes; `spec/lifecycle.md` §5 carries the
> reason.
>
> **Rows 164 and 166 are outside that rule**, as the gate note also
> says: `Clear` and `Search` are read-only filter controls and render in
> every state, `archived` included — an archived roster with rows still
> renders its table card and toolbar, so it can still be searched. The
> claim here is about the surface that mutates, not the whole page.

> **Gate-hidden by default.** The page is only reachable, and its nav
> tab only rendered, when `session.observers_enabled` is true.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 164 | Table toolbar | Clear | `<a>` | `btn secondary` | Secondary | Renders only when a search or status filter is active; links back to the bare list with the pager fragment. |
| 165 | Table toolbar | Add new | `<a>` | `btn secondary` | Secondary | Links to `?add=1#observers-row-editor`. Renders `disabled` while a row is being edited / added. Relabelled from `Add` at 19P.2 rung 3, following Reviewers at 19P.1 rung 2a — `Delete` left the row, so the two no longer share it. |
| 166 | Table toolbar | Search | `<button type="submit">` | `btn secondary` | Secondary | Submits the search + status filter GET. Last in the row; the toolbar carries no selection-driven controls. |
| 167 | Row expander | Edit | `<button type="button">` | `btn secondary` | Secondary | Selection-driven — enabled on exactly one checked row. JS navigates to `?edit_id=<id>#observer-row-<id>`. Built into the injected expander, not server-rendered. |
| 168 | Row expander | Inactivate | `<button type="submit">` | `btn secondary` | Secondary | `formaction` `/observers/bulk-inactivate`. **Offered by status, not arity** — it renders only when the selection holds an active row, so a selection admitting neither pair shows neither button rather than two disabled ones. |
| 169 | Row expander | Activate | `<button type="submit">` | `btn secondary` | Secondary | `formaction` `/observers/bulk-reactivate`; the mirror of row 168, offered when the selection holds an inactive row. |
| 170 | Row expander | Delete | `<button type="submit">` | `btn destructive` | Destructive | Deletes the checkbox-selected rows via `/observers/bulk-delete`. Ships `disabled`: nothing syncs an injected confirm pair until its first tick, so a live-by-default Delete would be a destructive control with its gate open. Two-stage gate — a selection enables the `Yes, delete these` checkbox in the same panel, which enables this button (`data-delete-btn="observers-bulk-delete"`). |
| 171 | Row expander (cohort pane) | `+` | `<button type="button">` | `btn secondary cohort-combinator-btn` | Secondary | Adds a rule cell. Sized by a class, not an inline `style` — see §6's no-inline-styled-buttons rule, which this page's four builder buttons were the last violation of. |
| 172 | Row expander (cohort pane) | `AND` / `OR` | `<button type="button">` | `btn secondary cohort-combinator-btn` | Secondary | Toggles the combinator; the label *is* the current value, written back to a hidden input. |
| 173 | Row expander (cohort pane) | operator cycle | `<button type="button">` | `btn secondary cohort-cell-btn` | Secondary | Cycles the six operators (`IS THE SAME AS` / `IS DIFFERENT FROM` / `IS` / `IS NOT` / `CONTAINS` / `DOES NOT CONTAIN`); the label is the current value. One per rule cell. |
| 174 | Row expander (cohort pane) | `X` | `<button type="button">` | `btn destructive cohort-cell-btn` | Destructive | Removes a rule cell; `disabled` on the first. Removing the **last** cell destroys the `Save` riding in its row, which is rebuilt — anything bound to `Save` is bound where `Save` is built. |
| 175 | Row expander (cohort pane) | Save | `<button type="submit">` | `btn secondary cohort-cell-btn cohort-save-btn` | Secondary | Posts `/observers/cohort-rule` for every selected observer. Inline after the last cell's `X`, not bottom-right. `disabled` **until the rule is dirty**. An unsaved edit is guarded rather than discarded — `spec/setup_pages.md` § *Cohort match rule editor*. |
| 176 | Edit-row bar | Save | `<button type="submit">` | `btn secondary` | Secondary | Posts `/observers/create` or `/observers/{id}/update` via `form="observer-edit-form"`. Renders in a bracketed expander beneath the row being edited, not in a card — the same shape Reviewers took at 19P.1 rung 2b. |
| 177 | Edit-row bar | Cancel | `<a>` | `btn secondary` | Secondary | Returns to the bare list with the pager fragment, abandoning the edit. |
| 178 | Roster card | Unlock / Lock | `<button type="button">` | `btn secondary` | Secondary | Toggles the Unlock panel. **One element, two homes** — the card's last child when collapsed, inside the panel beneath the card its column holds when open. The label names the state it moves *to*. Each home carries a `<noscript>` twin (`?unlocked=1#roster-card` and back), the panel being unreachable without JS otherwise. |
| 179 | Unlock panel — Upload Observers | Upload | `<button type="submit">` | `btn secondary` | Secondary | Posts `/observers/import`. On a roster with rows it ships `disabled` behind the `replace-observers` confirm; on an empty roster it renders enabled, that being the initial bulk create. **Left** column, unlike Reviewers' right — see `spec/setup_pages.md` § *Body layout*. |
| 180 | Unlock panel — Danger Zone | Delete all observers | `<button type="submit">` | `btn destructive` | Destructive | Posts `/observers/delete-all`; `disabled` until the `delete-all` confirm is ticked, and the route 400s without it. No response-loss acknowledgement: nothing references an observer, so the loss the gate guards cannot occur. |

## Section 9 — Instruments Setup (`/operator/sessions/{id}/instruments`)

Source: `app/web/templates/operator/instruments_index.html`.
Per-instrument buttons are listed once; the page renders one set
per instrument card.

### 9a — Page-level

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 49 | Lock card (when Activated) | Revert to draft | `<button type="submit">` | `btn alert` | Outline-amber | |

### 9b — Per-instrument card (one set per instrument)

| # | Card / sub-section | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 50 | Section A right card | Open this Instrument / Close this instrument | `<button type="submit">` | `btn secondary` | Secondary | Two-state toggle on `accepting_responses` (post-activation only) |
| 52 | Bottom action row (unlocked) | Save | `<button type="submit" form="dfsave-{iid}">` | `btn secondary` | Secondary | Bulk-save covers Band 1 form fields + Band 3 row state. Starts `disabled`; activates on first dirty event. Preserves `?editing=<id>` on redirect. |
| 53 | Bottom action row (unlocked) | Cancel | `<button type="button">` | `btn secondary` | Secondary | Confirms then reloads to discard unsaved client-side state. Mirrors Save's dirty-aware enabled state. |
| 54 | Bottom action row | Replicate | `<button type="submit">` | `btn secondary` | Secondary | Posts `/instruments/{iid}/replicate` — clones the card immediately after it; same edit-lock gating |
| 55 | Bottom action row | Delete | `<button type="submit">` | `btn destructive` | Destructive | Ships `disabled`; a paired confirm checkbox flush-right below the row (`data-delete-confirm` / `data-delete-btn`) gates it. Disabled outright when it is the only instrument or an edit lock is active. |
| 56 | Bottom action row | +Instrument | `<button type="submit">` | `btn secondary` | Secondary | Posts `/instruments/add-new-model` with `after={iid}`. **The sole "create new instrument" affordance on the row** — every new instrument is a new-model one, so there is no separate `Add instrument` / `Add group instrument` pair. |
| 56b | Bottom action row | +Page break | `<button type="submit">` | `btn secondary` | Secondary | Posts `/instruments/{iid}/page-break/create` (sets `starts_new_page=true` on the successor). Same Secondary role as +Instrument. Disabled on the last instrument, when the successor already carries a break, or past the editable window. |
| 57 | Bottom action row | Lock / Unlock | `<a>` (or disabled `<button>`) | `btn secondary` | Secondary | The gating toggle. Unlocked = `?editing=<id>` in URL; locked = no editing param. Clicking Lock with a dirty Save prompts `confirm()`. Renders as a disabled `<button>` (not `<a>`) when an edit lock is active. Same footer shape as the Quick Setup card's. |

### 9c — Per-field type and bounds — in the Band 3 row

**There is no Response Type Definitions card**, and no
`response_type_definitions` table behind one. Per-field type, bounds
and list options live inline on `InstrumentResponseField`'s
`_inline_*` columns and are edited directly in the Band 3 row (Type
select, Min / Max / Step inputs, List options text, R / ≡ / ✓ / X
buttons) — see `spec/instruments.md` "Band 3 — Response fields".

---

## Section 10 — Email Template (`/operator/sessions/{id}/setup-invite`)

Source: `app/web/templates/operator/session_setupinvite.html`.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 63 | Template selector (top-of-body) | Invitation / Reminder / Responses received (active) | `<span aria-current="page">` | `nav-tab active` | **Nav (page-internal)** — current view | Reuses the chrome's `.nav-tab` styling for visual consistency |
| 64 | Template selector (top-of-body) | Invitation / Reminder / Responses received (inactive) | `<a>` | `nav-tab` | **Nav (page-internal)** — sibling views | One per template |
| 65 | Email composer (per-field reset) | Reset {{ row.field }} to default | `<button type="submit">` | `btn-reset` | Inline text-button (`.btn-reset`) | Canonical link-styled inline button — reverts a single field without exiting the editor |
| 66 | Email composer actions (bottom-left) | Cancel | `<a>` | `btn secondary` | Secondary | Returns to Session Home |
| 67 | Email composer actions (bottom-left) | Save | `<button type="submit">` | `btn secondary` | Secondary | Disabled until a composer field is touched; posts `/setup-invite` |

---

## Section 11 — Validate (`/operator/sessions/{id}/validate`)

Source: `app/web/templates/operator/session_validate.html`.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 68 | Activate banner (warnings present) | Cancel | `<a>` | `btn alert` | Outline-amber | Returns to validate page without `?activate=1` |
| 69 | Activate banner (warnings present) | Acknowledge and activate | `<button type="submit">` | `btn danger-solid` | Alert (filled amber) | Posts `/activate` with `acknowledge_warnings=true` |
| 70 | Activate banner (errors present) | Cancel | `<a>` | `btn alert` | Outline-amber | Errors block activation; this just dismisses the banner |
| 71 | Severity filter chip strip | All / Errors / Warnings / Info | `<a>` | `severity-chip` (with `.active` state) | Filter chip (custom — not in §6) | One per severity level; not part of the canonical button family |

---

## Section 11.5 — Assignments Operations (`/operator/sessions/{id}/assignments`)

Source: `app/web/templates/operator/session_assignments.html`.
Pair-level context lives on the Relationships Setup page (Section 8);
this page is the materialized-derivative surface where the operator
runs the rule engine to generate the `(reviewer, reviewee, instrument)`
assignment matrix.

**Generation fires from the Workflow card's stepper** (rendered by
`next_action_card.html`) — this page carries no standalone Generate or
Rule Based Assignment card, and no Self-reviews toggle card.
Per-instrument Self review is an inline checkbox column on the
Per-instrument status table, and Self review / Show on that table are
plain form checkboxes rather than `.btn`-shaped controls, so they are
not enumerated here. The `.btn`-shaped controls are the
operator-actions search / bulk card's.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 71g | Operator-actions card | Inactivate | `<button type="submit">` | `btn secondary` | Secondary | `formaction` `/assignments/bulk-inactivate`; submits the `assignments-bulk-form` from the row-select checkbox column; enabled on ≥1 selection **and** `can_edit`. |
| 71h | Operator-actions card | Activate | `<button type="submit">` | `btn secondary` | Secondary | `formaction` `/assignments/bulk-activate`; enabled on ≥1 selection **and** `can_edit`. |
| 71i | Operator-actions card | Search | `<button type="submit">` | `btn secondary` | Secondary | Submits the "Search by" (All / Reviewers / Reviewees) + search GET; last in the inline `filter-actions` row. |
| 71j | Operator-actions card | Clear | `<a>` | `btn secondary` | Secondary | Resets the filter; rendered only when a search term is active. |

Button numbers in this section carry letter suffixes (`71g` etc.) so
that inserting the section did not renumber every section after it.
**Numbers are stable identifiers here** — other documents cite them —
so a later pass may flatten the sequence only together with those
citations.

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

## Section 13 — Invitations (`/operator/sessions/{id}/invitations`)

Source: `app/web/templates/operator/session_invitations.html`.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 84 | Filter card | Clear | `<a>` | `btn secondary` | Secondary | Rendered only when a filter is active |
| 85 | Filter card | Apply | `<button type="submit">` | `btn secondary` | Secondary | |
| 86 | Invitations table (per row) | Send | `<button type="submit">` | `btn secondary` | Secondary (Disabled when session not ready) | One per row; visible while the invitation is `pending` |
| 87 | Invitations table (per row) | Send reminder | `<button type="submit">` | `btn secondary` | Secondary (Disabled when row is complete or session not ready) | One per row; visible once the invitation is past `pending` |
| 87a | Invitations table (per row) | Regenerate | `<button type="submit">` | `btn secondary` | Secondary (Disabled when session not ready) | One per row, whenever an `Invitation` row exists |

**The page body carries no bulk-action bar.** Create invites, Send
invites and Send reminders belong to the Workflow card's stepper
(§5a), and the outbox is reached from Sessions Diagnostics (§21), not
from here — `spec/operations_pages.md`.

---

## Section 14 — Responses (`/operator/sessions/{id}/responses`)

Source: `app/web/templates/operator/session_responses.html`.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 90 | Filter card | Clear | `<a>` | `btn secondary` | Secondary | Rendered only when a filter is active |
| 91 | Filter card | Apply | `<button type="submit">` | `btn secondary` | Secondary | |

**No bulk-action bar and no Actions column.** Send reminders belongs
to the Workflow card's stepper (§5a) and the Invitations tab is
reached from the chrome — `spec/operations_pages.md`.

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

## Section 16 — Rule authoring — Band 1, not a page of its own

**There is no Rule Builder page and no Rule Based Assignment card.**
Band 1 of the per-instrument card on the Instruments page is the sole
rule-authoring surface — see [`spec/assignments.md`](assignments.md)
and [`spec/instruments.md`](instruments.md) § Band 1 for the canonical
button shapes there (`+` to add a rule cell, `X` to remove, the
operator-cycle button, and the AND / OR combinator toggle).

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

Operator Settings also renders a top-of-body back-link. Listed here
under a continuing number rather than inserted into Section 15; the
canonical role definition is the `.back-link` row in
`spec/ui_elements.md` §6.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 104 | Page top (above the SMTP form card) | ← Back to {{ return_to_label }} | `<a>` | `back-link` | Return-to (`.back-link`) | |

---

## Section 21 — Sessions Diagnostics (`/operator/sys-admin/sessions`)

Source: `app/web/templates/operator/sys_admin_sessions.html`.
Sys-admin-gated. Sections 19 and 20 catalogue this page's children and
link back to it.

**Section numbers are stable identifiers, not an ordering.** This page
is §21 rather than slotted before §19 because other documents cite
sections by number — `spec/email_template_editor.md` cites §10 — so
renumbering to tidy the order breaks those citations. A new section
takes the next free number.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 123 | Sessions table, per row (Actions) | Manage | `<button type="submit">` in a `<form>` | `btn secondary` | Secondary | POSTs `…/sessions/{id}/adopt` — self-adds the sys-admin as an owner (audited `session.owner_added`), then opens the session. **The only door**: no row may link straight into a session the sys-admin does not own. |
| 124 | Sessions table, per row (Actions) | Outbox | `<a>` | `btn secondary` | Secondary | Child page, read-only for a non-owner sys-admin. |
| 125 | Sessions table, per row (Actions) | Audit log | `<a>` | `btn secondary` | Secondary | Child page (Section 20). |

Notes:

- **All three carry the same role, and the page carries no inline
  styles.** They sit in a `.btn-pair`, whose `> form { margin: 0 }`
  rule is what lets the form wrapper need none. Styling one of the
  three differently — a link-styled button beside two button-styled
  anchors, say — hides the inconsistency rather than resolving it.
- **Why Secondary and not Alert.** Adopting a session grants yourself
  ownership, which is consequential — but it is reversible, audited, and
  the routine way a sys-admin opens someone else's session. Per
  `spec/ui_elements.md` §6, gravity belongs to the surrounding context,
  not the button colour; filled amber in every row of a diagnostics table
  would spend the alarm on the normal case.
- **The page also carries the read-only Visibility grid audit card** —
  prose and a table, no buttons, so it contributes no rows here.

---

## Section 19 — Accounts Management (`/operator/sys-admin/users`)

Source: `app/web/templates/operator/sys_admin_users.html`.
Sys-admin-gated. **One per-row selection checkbox and a single
bulk-action toolbar above the table** — never per-row inline action
buttons, which would put four destructive controls on every row.

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
  buttons cluster left-aligned, next to the row checkboxes. Group
  labels (`Operator:` / `Sys Admin:` / `|`) live inline between the
  buttons.
- **Single-row selection.** Inline JS enforces one row at a time;
  the other checkboxes grey out when one is checked. Self-row
  renders `(self)` instead of a checkbox.
- **Selection persistence.** Every action that doesn't delete the
  row round-trips the selected `user_id` via the redirect's
  `?selected={id}` query param; the template stamps `checked` on
  the matching row so the operator can chain a second action
  without re-selecting.
- **No confirm checkbox on Promote / Demote.** The service-layer
  `last_admin` guard is the structural safety net, and a checkbox in
  front of it would be a second, weaker one.

---

## Section 20 — Per-session Audit log (`/operator/sys-admin/sessions/{id}/audit-log`)

Source: `app/web/templates/operator/sys_admin_session_audit_log.html`.
Sys-admin-gated.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 118 | Page top | ← Back to Sessions Diagnostics | `<a>` | `back-link` | Return-to (`.back-link`) | |
| 119 | Audit log card heading | Download CSV | `<a>` | `btn secondary` | Secondary | Posts to `/export/audit_log.csv`; the URL forward-carries the active filter set so the CSV matches the on-screen view. |
| 120 | Filter strip (button row) | Apply filters | `<button type="submit">` | `btn secondary` | Secondary | Right-aligned within a `.btn-pair` with `justify-content: flex-end`; **Secondary, never Primary**, so it doesn't compete with the Download CSV button up at the card heading. |
| 121 | Filter strip (button row) | Clear filters | `<a>` | `btn secondary` | Secondary | Renders only when `filter_form.is_active`. Resets to the canonical viewer URL with no query string. |
| 122 | Per-row detail | (expander) | `<summary>` inside `<details>` | `audit-detail summary` | Inline disclosure (custom) | Inline expander surfacing the canonical audit detail envelopes in human-readable sections + raw JSON in a nested `<details>`. Not a `.btn` but interactive — listed for completeness. |

Notes:

- **Filter strip layout:**
  - Left column: Event-type multi-select with `Ctrl/Cmd-click
    to select multiple` hint.
  - Right column flows actor email → From / To date selectors
    side-by-side (each half-width, flex children) → severity
    checkboxes on a single inline row.
- **Button-row gap.** `.btn-pair` carries `margin-top: 16px;
  margin-bottom: 24px;` so the row sits clear of both the
  filter strip above and the audit-log table below.

---

## Cross-page button conventions

Conventions that bind every operator page, and are not restated per
section.

### 1. "Return to where you came from" is one class

Pages reached as a detour from the chrome — Operator Settings (#104),
About (#103), and the Sys Admin child pages (#111, #118) — carry a
**`.back-link`**, rendered as
`<a class="back-link" href="{{ return_to_url }}">← Back to
{{ return_to_label }}</a>` at the top of the body, above the working
cards. It round-trips via `?return_to=<path>` from the chrome
top-right utility menu (#100 / #101). Documented in
`spec/ui_elements.md` §6.

**A form editor uses Save + Cancel, not a back-link.** The two would
navigate to the same place, but Cancel belongs to the form and reads
with Save; adding a back-link beside them either duplicates Cancel or
silently changes its meaning to "revert the form in place". Session
Home's `#session-config` card (§5b) is the case that settles it: the
operator never left the page, so there is nowhere to go back to.

### 2. Send → Primary, generate → Secondary

Any button that **actually sends email** is Primary; a button that
prepares or rebuilds local state without sending is Secondary. Both
apply wherever the pair appears — today the Workflow card's stepper
(§5a), where Create invites and Send invites are Primary.

Per-row Send / Send reminder (#86, #87) stay **Secondary**: per-row
context overrides the role-based convention, because a table of
Primary buttons has no primary action at all.

### 3. Which action earns Primary in an activated session

In `ready` the Primary is the next forward stage of the invitation
flow — Create invites, then Send invites, then Send reminders. Close
session and Revert to draft stay **Secondary** however consequential
they are: gravity belongs to the surrounding context, not to promoting
a supporting action. `spec/workflow_card.md`'s per-state table is the
contract.

### 4. Page-internal nav tabs reuse the chrome's `.nav-tab`

Page-internal view switchers — the Email Template selector (#63/#64)
and the email-preview tabs (#76/#77/#78) — reuse the chrome's
`.nav-tab` styling. Active tab is `<span class="nav-tab active"
aria-current="page">`; siblings are `<a class="nav-tab">`; reserved
"coming soon" tabs are `<span class="nav-tab disabled"
aria-disabled="true">`.

Wrapper is `<div class="tab-strip tab-strip-page">`. The
`.tab-strip-page` modifier (in `base.html`) gives the row the chrome's
grey row tint (`#f3f4f6`), a thin `#d1d5db` border, and rounded
corners, so the active tab's white background reads against the strip
just as the chrome's Setup row does. Hover and disabled treatments
fall out of the existing `.nav-tab` rules. `spec/ui_elements.md` §6
"Nav button" documents the convention.

### 5. Reverting one field inside an editor is `.btn-reset`

A link-styled inline button that posts a form to revert a single field
without cancelling and exiting the editor — never an inline-styled
`chrome-link`. The Email composer's per-field reset (#65) is its one
caller; the rule sits in `base.html` and applies to any editor with
per-field overrides.

### 6. Confirm-checkbox-gates-button

Every destructive button (delete-all, delete-data, delete-session,
revert, replace-upload, per-instrument delete, clear-responses) ships
`disabled` and is enabled only while a paired confirm checkbox is
ticked. **The pairing is declarative and there is one implementation**:
`data-delete-confirm="KEY"` on the checkbox, `data-delete-btn="KEY"` on
the button, wired by a single global JS block in
`app/web/templates/base.html`. Any operator or reviewer page picks it
up by tagging the pair; no page carries its own confirm-checkbox JS.

## Maintenance

**A PR that adds, removes or restyles a button updates its row here in
the same PR.** A row and its control change together, or the row is
prescribing something nobody built.

Numbers are stable identifiers — other documents cite them — so a new
button takes the next free number or a letter suffix within its
section, never a renumber of what follows. A restyle bundle, or a
change to `spec/ui_elements.md` §6, is the point at which to re-read
the sections it touches.
