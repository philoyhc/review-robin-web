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
| **Nav (page-internal)** | Page-internal view switcher (e.g. Email Template tabs). Reuses the chrome's `.nav-tab` styling for visual consistency: active uses `<span class="nav-tab active" aria-current="page">`, siblings use `<a class="nav-tab">`, "coming soon" uses `<span class="nav-tab disabled" aria-disabled="true">`. Wrap in `.tab-strip`. (See `spec/ui_elements.md` §6.) |
| **Inline text-button (`.btn-reset`)** | Single-line link-styled button used to revert a single field inside an editor without cancelling and exiting. (See `spec/ui_elements.md` §6.) |
| **Return-to (`.back-link`)** | Top-of-body inline link to "wherever you came from" (`return_to_url` round-trip). Required on chrome-detour pages (Operator Settings, About) and on the Sys Admin child pages. (See `spec/ui_elements.md` §6.) |
| **Chrome utility link** | Top-right chrome anchors — Sign-out (`signout`), Settings / Admin / Guide / About (`chrome-link`). Defined in `spec/ui_elements.md` §1, not in `.btn` family. |
| **Chrome nav** | The two-row session top-nav tabs (`.nav-tab`). Lives in `spec/visual_style_rrw.md` "Operator session chrome", not in the `.btn` family. |
| **Disabled** | Visual variant of any role — opacity 0.5, `cursor: not-allowed`, `aria-disabled="true"`; applied once, not again inside an already-faded locked strip. |
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
| 10 | Operations tab row | Invitations | `<a>` | `nav-tab` | Chrome nav | |
| 11 | Operations tab row | Responses | `<a>` | `nav-tab` | Chrome nav | |
| 12 | Setup tab row | Observers | `<a>` | `nav-tab` | Chrome nav | Renders only when `observers_enabled`. **Numbered 12 rather than slotted after Relationships** — numbers here are stable identifiers other documents cite, so a new tab takes the next free one and the row order is not the render order |
| 13 | Operations tab row | Extract data | `<a>` | `nav-tab` | Chrome nav | The fifth Operations tab. Render order is Assignments, Validate, Invitations, Responses, Extract data — `spec/operator_ui_concept.md` §5 carries the row contract |

---

## Section 2 — Sessions overview (`/operator/sessions`)

Source: `app/web/templates/operator/sessions_list.html`.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 193 | Filter | Add new session | `<a>` | `btn` | Primary | The lobby's **only** create affordance, in every state — the first-run card names this button instead of carrying a second one (`spec/sessions_overview.md` "Empty state") |
| 194 | Filter | Rehydrate / Go to Archive | `<a>` | `btn secondary` | Secondary | Always rendered; `Go to Archive` is active in every state, `Rehydrate` in every state **in which it renders at all** — it is gated behind `rehydrate_enabled`, which ships false, so by default it is absent rather than inactive (`spec/rehydrate.md`) |
| 194a | Filter | Clear | `<button type="button">` | `btn secondary` | Secondary | Empties the filter box. `Clear`, not `Cancel`: the control is a filter, and a live filter has nothing in flight to cancel. Only when live sessions exist; inert as a `<span class="btn secondary disabled">`, not a disabled `<a>`, because `a.btn.disabled` still navigates. **Note the adjacency**: the `Sessions` card's tag strip carries its own `Clear` chip, which clears the selected tags rather than the box |
| 195 | Row expander (single / bulk) | Delete / Delete all | `<button type="submit">` | `btn destructive` | Destructive | Lives in the row expander, not a standalone Danger Zone card; gated behind a "Yes, delete" checkbox — see `spec/sessions_overview.md` |
| 199 | Row expander (single) | Save | `<button type="button">` | `btn secondary` | Secondary | Posts the row's Name / Code / Deadline / Tags to `{id}/lobby-edit`. Name, Code and Deadline are editable in `draft` and `validated` (`is_editable`, as on Session Home); Tags in any state |
| 200 | Row expander (single) | Cancel | `<button type="button">` | `btn secondary` | Secondary | Unticks the row, which closes the expander; writes nothing |
| 201 | Row expander (single) | Duplicate | `<button type="button">` | `btn secondary` | Secondary | Posts `{id}/clone` with `mode=all` |
| 202 | Row expander (single) | Duplicate settings only | `<button type="button">` | `btn secondary` | Secondary | Posts `{id}/clone` with `mode=config` |
| 203 | Row expander (single) | Purge and archive | `<button type="submit">` | `btn danger-solid` | Alert | Posts `bulk-archive` with the ticked purge options (Responses / Rosters / Audit log); inert when the row's lifecycle state cannot be archived |
| 204 | Row expander (bulk) | Cancel | `<button type="button">` | `btn secondary` | Secondary | Unticks the expander's anchor row, re-anchoring it to the previous selection (or swapping to the single-session expander once one row remains) |
| 205 | Row expander (bulk) | Unselect others | `<button type="button">` | `btn secondary` | Secondary | Unticks every selected row but the anchor |
| 206 | Row expander (bulk) | Unselect all | `<button type="button">` | `btn secondary` | Secondary | Clears the selection |
| 207 | Row expander (bulk) | All tags to all | `<button type="submit">` | `btn secondary` | Secondary | Posts `bulk-tags` with `op=add`: adds the Tags box's tags to every selected session |
| 208 | Row expander (bulk) | Remove from all | `<button type="submit">` | `btn secondary` | Secondary | Posts `bulk-tags` with `op=remove`. The Tags box is prefilled with the union of the selection's tags |
| 209 | Row expander (bulk) | Purge and archive all | `<button type="submit">` | `btn danger-solid` | Alert | Posts `bulk-archive`; non-archivable rows are skipped server-side, and the button is inert only when none of the selection can be archived |

---

## Section 2a — Archived sessions (`/operator/sessions/archived`)

Source: `app/web/templates/operator/sessions_archived.html`.

Its whole body is inside `{% if sessions %}`, so on an
empty archive none of these render at all — unlike the Lobby, which
keeps its card and inerts the controls because that card also holds the
ways out of an empty lobby.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 181 | Filter | Clear | `<button type="button">` | `btn secondary` | Secondary | Empties the filter box. Mirrors #194a; no inert variant, since the card is absent when there is nothing to filter |
| 182 | Row expander (bulk) | Unselect all | `<button type="button">` | `btn secondary` | Secondary | Clears the row selection |
| 183 | Row expander (bulk) | Unarchive | `<button type="submit">` | `btn` | Primary | Posts `/operator/sessions/bulk-unarchive`; the page's one forward action, hence Primary |
| 184 | Row expander (bulk) | Download | `<button type="button">` | `btn secondary` | Secondary | **Ships `disabled` unconditionally** — a placeholder for an export that does not exist. A permanently inert control with no explanation beside it |
| 185 | Row expander (bulk) | Delete | `<button type="submit">` | `btn destructive` | Destructive | Posts `/operator/sessions/bulk-delete-archived`; gated behind the "Yes, delete" checkbox, same shape as #195 |

---

## Section 2b — Rehydrate (`/operator/sessions/rehydrate`)

Source: `app/web/templates/operator/session_rehydrate.html`. The page
404s unless `rehydrate_enabled` is on (`spec/rehydrate.md`).

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 252 | Upload, validate, rehydrate | Validate | `<button type="submit">` | `btn secondary` | Secondary | Submits `#rehydrate-validate-form` (the file upload) via `form=` to `rehydrate/validate` |
| 253 | Upload, validate, rehydrate | Rehydrate (validated) | `<button type="submit">` | `btn` | Primary | Only when the last Validate run passed; submits the stash token in `#rehydrate-commit-form` to `rehydrate/commit` |
| 254 | Upload, validate, rehydrate | Rehydrate (not validated) | `<button type="button">` | `btn disabled` | Primary (Disabled) | Before a Validate run, or after one that failed |
| 255 | Rehydrate finished — with responses dropped | Download dropped responses | `<a>` | `btn secondary` | Secondary | Only on a commit that dropped responses; GETs `rehydrate/dropped.csv` with the outcome token |
| 256 | Rehydrate finished — with responses dropped | Go to {session name} | `<a>` | `btn` | Primary | Links to the new session's Home |

---

## Section 3 — New session (`/operator/sessions/new`)

Source: `app/web/templates/operator/session_new.html`.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 14 | Session details form | Create session | `<button type="submit">` | `btn` | Primary | Posts to `POST /operator/sessions` |
| 15 | Session details form | Cancel | `<a>` | `btn secondary` | Secondary | Returns to the sessions lobby |
| 186 | Owners card | Add owner | `<button type="button">` | `btn secondary` | Secondary | Stages a row via `_owners_stager_js`; the card has no save of its own — **Create session** (#14) submits the staged set. Ships `hidden`, un-hidden by the stager script (`spec/session_owners.md` §3) |
| 187 | Owners card | Remove (per staged row) | `<button type="button">` | `chrome-link` | **Not `.btn`, kept deliberately** — reuses the chrome nav's `chrome-link` class for an in-card control; no canonical role above covers a per-row remove, and by the author's ruling the Owners cards' Removes (#187, #190) stay `chrome-link` rather than take one. The class has a base rule outside the chrome (`body.ui-v2 .chrome-link`: no background, border or padding, the link colour, a muted disabled state), so the button draws as a link. Removes a staged row client-side; nothing is written until **Create session**. Not present on the creator's fixed row |

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
| 156 | Session details footer | Save | `<button type="submit">` | `btn secondary` | Secondary | Submits `form="config-save-{id}"` to the shared `/config` POST, which returns to Home still unlocked (`?editing=1`); only Lock locks |
| 157 | Session details footer | Cancel | `<a>` | `btn secondary` | Secondary | Returns to `#session-config` unedited |
| 158 | Session details footer | Lock / Unlock | `<a>` | `btn secondary` | Secondary | Two-state toggle; adds or drops `?editing=1`. Rendered `aria-disabled` with an explanatory `title` once the session is past `validated` — the lock-card recovery path, not a hidden control |

The Owners card is its own card, above the Danger Zone, not a sub-card
of this one; its buttons, including #159, are in §5f.

### 5c — Quick Setup card

Source: `partials/_quick_setup_card.html`. Also rendered on
`session_new.html`, where the slots' inputs associate with the
create-session form via `form="create-session-form"` and the card
renders no Submit of its own — the page's **Create
session** button submits both halves.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 31 | Quick Setup footer | Submit | `<button type="submit">` | `btn secondary` | Secondary | Disabled until ≥1 file selected; posts `/quick-setup/submit-all` |
| 160 | Quick Setup slot | Cancel | `<a>` | `btn alert` | **Outline-amber** | Per-slot cancel on an inline `.banner.banner-error` — same banner convention as #155, not a lock card |

### 5d — Extract Data — not on this page

`session_detail.html` does **not** include the Extract Data card.
`partials/_extract_data_card.html` renders only on
`session_extract_data.html` (`/operator/sessions/{id}/extract-data`).
That page's buttons are in Section 14.5.

### 5e — Danger Zone (`#danger-zone`)

Source: `session_detail.html`, `.card.danger-zone#danger-zone` — the
bottom-right of Home's `.bottom-grid`.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 17a | Danger Zone | Delete Data | `<button type="submit">` | `btn destructive` | Destructive (outline red) | Ships `disabled aria-disabled="true"`; a confirm checkbox enables it. The checkbox is itself disabled while the session is `ready`, so the button cannot be reached |
| 17b | Danger Zone | Delete session | `<button type="submit">` | `btn destructive` | Destructive (outline red) | Same gating. Session-delete subsumes data-delete: ticking it shows the data checkbox selected but inert |

These two keep the `17a` / `17b` numbers §4 lists them under, so a
reader following either reference lands on the same pair.

### 5f — Owners card (`#owners-card`)

Source: `session_detail.html`, `.card#owners-card` — stacked above
Danger Zone in the same `.bottom-left` column. Always
shown, no display/edit swap; full contract in `spec/session_owners.md`.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 159 | Owners card | Add owner | `<button type="submit" form="owners-add-form">` | `btn secondary` | Secondary | Posts the picker's address to `owners/add` and saves at once. Sits alone in the card's action row, outside its form. Live on load: the card has no Lock / Unlock. |
| 190 | Owners card | Remove (per row) | `<button type="submit">` | `chrome-link` | **Not `.btn`** — see #187's note | Its own form per row, posting to `owners/{user_id}/remove`; saves at once. `disabled` when one owner remains. Every other row's form asks first (`confirm()` on submit): your own that you will lose access; another owner's naming them, its text in a `data-confirm` attribute |

Rows 188, 189 and 191 — the card's staged **Save**, **Cancel** and a
`<noscript>` Remove fallback — are retired with the staging; the
numbers are not reused.

---

## Section 6 — Reviewers Setup (`/operator/sessions/{id}/reviewers`)

Source: `app/web/templates/operator/session_reviewers.html`.

> **Lifecycle. This note governs §§6, 7, 8 and 8.5** — every roster
> Setup page — and is stated here once rather than four times.
>
> The selection-driven controls, the Upload button and the Danger Zone
> button render only while the session is `is_editable`
> (`draft` / `validated`); outside those states they must be
> **absent**, not disabled. That is achieved by suppressing the whole
> Unlock panel the cards live in, which is the same rule reaching them through one gate
> instead of three. The enable/disable rules in the Notes column
> describe behavior *within* an editable session. `Clear` and `Search`
> render in every state.
>
> **Observers is the exception, for the whole page.** Every one of its
> mutating routes takes `_require_not_archived`, so its row actions, its
> import and its `delete-all` are live through `ready` and `expired` and
> its Unlock panel is suppressed only on `archived`. See
> `spec/lifecycle.md` §5 for why an observer's roster is allowed the
> wider predicate.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 105 | Reviewer tag labels | Cancel | `<button type="button">` | `btn secondary` | Secondary | Inline JS reverts the three tag inputs to their initial snapshot and re-disables the pair. Suppressed whenever the session is not `is_editable`. **In the Unlock panel** — and in the card's `.card-columns` fallback home the editor keeps for the states the panel cannot render in, where the partial drops this pair rather than disabling it. |
| 106 | Reviewer tag labels | Save labels | `<button type="submit">` | `btn secondary` | Secondary | Posts `/reviewers/field-labels`. Starts `disabled`; inline JS flips both Save + Cancel on when the form is dirty. Suppressed whenever the session is not `is_editable` — which is why the whole panel is suppressed rather than disabled, since a locked page must carry no `Save labels` anywhere. **In the Unlock panel**; its redirect carries `?unlocked=1` so the save does not close the panel it was made from. |
| 34 | Lock card (when Activated or Closed) | Revert to draft | `<button type="submit">` | `btn alert` | Outline-amber | Inside `.card.lock` |
| 35 | Upload Reviewers | Upload | `<button type="submit">` | `btn secondary` | Secondary | Posts `/reviewers/import`. **In the roster card's Unlock panel**. |
| 36 | Row expander | Edit | `<button type="button">` | `btn secondary` | Secondary | Selection-driven — enabled on exactly one checked row; JS navigates to `?edit_id=` with `#reviewer-row-<id>`, so the page lands on the row rather than the top. Rendered into the expander row injected beneath the selection. |
| 123 | Row expander | Inactivate | `<button type="submit">` | `btn secondary` | Secondary | `formaction` `/reviewers/bulk-inactivate`; enabled on ≥1 selection **and** `can_edit`. Rendered **by status, not arity** — `statusActions()` emits `Inactivate` only when the selection holds an active row and `Activate` only when it holds an inactive one, so a single-status selection gets one button rather than two of which one would no-op. The same on all four roster pages (Observers: #168). |
| 124 | Row expander | Activate | `<button type="submit">` | `btn secondary` | Secondary | `formaction` `/reviewers/bulk-reactivate`; enabled on ≥1 selection **and** `can_edit`. Rendered **by status, not arity**, as #123. |
| 125 | Table toolbar | Add new | `<a>` | `btn secondary` | Secondary | Links to `?add=1`; renders disabled while a row is being edited / added. Labeled `Add new`, not `Add`: `Delete` lives in the row expander, so nothing shares this toolbar row with it. All four roster toolbars read `Add new` (rows 132, 139, 165); Observers' row is `Clear` / `Add new` / `Search`. |
| 161 | Row expander | Delete | `<button type="submit">` | `btn destructive` | Destructive | Deletes the checkbox-selected rows via `/reviewers/bulk-delete`. Sits in the row expander with the selection it acts on; nothing sits between `Add new` and `Search` in the toolbar. Two-stage gate: a selection enables the `Yes, delete these` checkbox beside it, which enables this button through the confirm-checkbox-gates-button standard below (`data-delete-btn="reviewers-bulk-delete"`). Posts the bulk form via `form=` + `formaction`, like Inactivate / Activate. The server re-checks both gates: `confirm` must be `"true"`, and where the selected rows carry saved responses so must `acknowledge_response_loss`. |
| 126 | Table toolbar | Search | `<button type="submit">` | `btn secondary` | Secondary | Submits the search + status filter GET. Sits last in the `filter-actions` row. The selection-driven buttons are not beside it — they are in the row expander, with the selected count. |
| 127 | Table toolbar | Clear | `<a>` | `btn secondary` | Secondary | Resets the filter; rendered only when a filter is active. |
| 128 | Row expander bar (Edit/Add) | Save | `<button type="submit">` | `btn secondary` | Secondary | Submits the `/{id}/update` or `/create` form. **Not "below the divider"**: there is no divider on Reviewers and no editor card — the pair renders in an expander bar directly beneath the edited row, styled as that row's own expander. **Secondary on all four roster pages**; whether the pair *should* be Primary is a question for the page that next revisits it. |
| 129 | Row expander bar (Edit/Add) | Cancel | `<a>` | `btn secondary` | Secondary | Returns to the plain list, carrying the pager anchor so Cancel lands where Save would. |
| 37 | Danger Zone | Delete all reviewers | `<button type="submit">` | `btn destructive` | Destructive | Posts `/reviewers/delete-all`. **In the roster card's Unlock panel**. Rendered only when the roster has rows — not because the route refuses an empty one (it answers 303 and writes "Deleted all 0 reviewers") but because `_delete_all` invalidates a `validated` session before it counts, so an ungated one demotes to `draft` while deleting nothing. |
| 231 | Roster card | Unlock / Lock | `<button type="button">` | `btn secondary` | Secondary | Toggles the Unlock panel; renders only while the session is `is_editable` and no row is being edited or added. **One element, two homes**, as Observers' #178: the card's last child when collapsed, inside the panel when open. The label names the state it moves *to*. Each home carries a `<noscript>` twin (`?unlocked=1#roster-card` and back) |

---

## Section 7 — Reviewees Setup (`/operator/sessions/{id}/reviewees`)

Source: `app/web/templates/operator/session_reviewees.html`.
The lifecycle note above §6 governs this section. The page takes the
shared roster shape — toolbar, row expander, Unlock panel
(`spec/setup_pages.md` § *The roster card and the Unlock panel*).

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 107 | Reviewee field labels | Cancel | `<button type="button">` | `btn secondary` | Secondary | Inline JS reverts the six inputs (Name / Email / Photo / Tag 1-3) to their initial snapshot and re-disables the pair. Suppressed whenever the session is not `is_editable`. |
| 108 | Reviewee field labels | Save labels | `<button type="submit">` | `btn secondary` | Secondary | Posts `/reviewees/field-labels`. Starts `disabled`; dirty-check via inline JS. Suppressed whenever the session is not `is_editable`. |
| 38 | Lock card (when Activated or Closed) | Revert to draft | `<button type="submit">` | `btn alert` | Outline-amber | |
| 39 | Upload Reviewees | Upload | `<button type="submit">` | `btn secondary` | Secondary | Posts `/reviewees/import`. In the **Unlock panel's right column**; nothing sits below the preview table. Ships `disabled` behind the `replace-roster` confirm whenever the roster has rows. |
| 40 | Row expander | Edit | `<button type="button">` | `btn secondary` | Secondary | Selection-driven — enabled on exactly one checked row; JS navigates to `?edit_id=`. |
| 130 | Row expander | Inactivate | `<button type="submit">` | `btn secondary` | Secondary | `formaction` `/reviewees/bulk-inactivate`; enabled on ≥1 selection **and** `can_edit`. Rendered **by status, not arity**, as #123. |
| 131 | Row expander | Activate | `<button type="submit">` | `btn secondary` | Secondary | `formaction` `/reviewees/bulk-reactivate`; enabled on ≥1 selection **and** `can_edit`. Rendered **by status, not arity**, as #123. |
| 132 | Table toolbar | Add new | `<a>` | `btn secondary` | Secondary | Links to `?add=1`; renders disabled while a row is being edited / added. Labeled `Add new` — see #125. |
| 162 | Row expander | Delete | `<button type="submit">` | `btn destructive` | Destructive | Deletes the checkbox-selected rows via `/reviewees/bulk-delete`. Sits in the row expander with the selection it acts on; nothing sits between `Add new` and `Search` in the toolbar. Two-stage gate: a selection enables the `Yes, delete these` checkbox beside it, which enables this button through the confirm-checkbox-gates-button standard below (`data-delete-btn="reviewees-bulk-delete"`). Posts the bulk form via `form=` + `formaction`, like Inactivate / Activate. The server re-checks both gates: `confirm` must be `"true"`, and where the selected rows carry saved responses so must `acknowledge_response_loss`. |
| 133 | Table toolbar | Search | `<button type="submit">` | `btn secondary` | Secondary | Submits the search + status filter GET. Sits last in the `filter-actions` row. The selection-driven buttons are not beside it — they are in the row expander, with the selected count. |
| 134 | Table toolbar | Clear | `<a>` | `btn secondary` | Secondary | Resets the filter; rendered only when a filter is active. |
| 135 | Row expander bar (Edit/Add) | Save | `<button type="submit">` | `btn secondary` | Secondary | Submits the `/{id}/update` or `/create` form; shown below the divider in Edit/Add mode. Secondary, as #128. |
| 136 | Row expander bar (Edit/Add) | Cancel | `<a>` | `btn secondary` | Secondary | Returns to the plain list. |
| 41 | Danger Zone | Delete all reviewees | `<button type="submit">` | `btn destructive` | Destructive | Posts `/reviewees/delete-all`. In the **Unlock panel's left column**, beneath the tag-labels editor; the card renders only on a roster with rows. |
| 232 | Roster card | Unlock / Lock | `<button type="button">` | `btn secondary` | Secondary | Toggles the Unlock panel; renders only while the session is `is_editable` and no row is being edited or added. **One element, two homes**, as Observers' #178: the card's last child when collapsed, inside the panel when open. The label names the state it moves *to*. Each home carries a `<noscript>` twin (`?unlocked=1#roster-card` and back) |

---

## Section 8 — Relationships Setup (`/operator/sessions/{id}/relationships`)

Source: `app/web/templates/operator/session_relationships.html`.
The lifecycle note above §6 governs this section. The per-pair context
table takes the shared roster shape — toolbar,
row expander, Unlock panel (`spec/setup_pages.md` § *The roster card
and the Unlock panel*).

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 109 | Pair-context labels | Cancel | `<button type="button">` | `btn secondary` | Secondary | Inline JS reverts the three pair-context inputs to their initial snapshot and re-disables the pair. Suppressed whenever the session is not `is_editable`. |
| 110 | Pair-context labels | Save labels | `<button type="submit">` | `btn secondary` | Secondary | Posts `/relationships/field-labels`. Starts `disabled`; dirty-check via inline JS. Suppressed whenever the session is not `is_editable`. |
| 42 | Lock card (when Activated or Closed) | Revert to draft | `<button type="submit">` | `btn alert` | Outline-amber | |
| 43 | Upload Relationships | Upload | `<button type="submit">` | `btn secondary` | Secondary | Posts `/relationships/import`. CSV columns: `ReviewerEmail`, `RevieweeEmail`, `PairContextTag1..3`, `Status`. In the **Unlock panel's right column**; nothing sits below the preview table. |
| 44 | Row expander | Edit | `<button type="button">` | `btn secondary` | Secondary | Selection-driven — enabled on exactly one checked row; JS navigates to `?edit_id=`. |
| 137 | Row expander | Inactivate | `<button type="submit">` | `btn secondary` | Secondary | `formaction` `/relationships/bulk-inactivate`; enabled on ≥1 selection **and** `can_edit`. Rendered **by status, not arity**, as #123. |
| 138 | Row expander | Activate | `<button type="submit">` | `btn secondary` | Secondary | `formaction` `/relationships/bulk-reactivate`; enabled on ≥1 selection **and** `can_edit`. Rendered **by status, not arity**, as #123. |
| 139 | Table toolbar | Add new | `<a>` | `btn secondary` | Secondary | Links to `?add=1`; disabled while editing / when either roster is empty. Labeled `Add new` — see #125. |
| 163 | Row expander | Delete | `<button type="submit">` | `btn destructive` | Destructive | Deletes the checkbox-selected rows via `/relationships/bulk-delete`. Sits in the row expander with the selection it acts on; nothing sits between `Add new` and `Search` in the toolbar. Two-stage gate: a selection enables the `Yes, delete these` checkbox beside it, which enables this button through the confirm-checkbox-gates-button standard below (`data-delete-btn="relationships-bulk-delete"`). Posts the bulk form via `form=` + `formaction`, like Inactivate / Activate. The server re-checks both gates: `confirm` must be `"true"`, and where the selected rows carry saved responses so must `acknowledge_response_loss`. A relationship carries none, so the second never applies; a pair the delete moves to another pair-context group gives up its group answer copy without one. |
| 140 | Table toolbar | Search | `<button type="submit">` | `btn secondary` | Secondary | Submits the Status + search GET; there is no "Search by" side-picker. Sits last in the `filter-actions` row. The selection-driven buttons are not beside it — they are in the row expander, with the selected count. |
| 141 | Table toolbar | Clear | `<a>` | `btn secondary` | Secondary | Resets the filter; rendered only when a filter is active. |
| 142 | Row expander bar (Edit/Add) | Save | `<button type="submit">` | `btn secondary` | Secondary | Submits the `/{id}/update` or `/create` form; reviewer / reviewee chosen via name-or-email `<datalist>` pickers. Secondary, as #128. |
| 143 | Row expander bar (Edit/Add) | Cancel | `<a>` | `btn secondary` | Secondary | Returns to the plain list. |
| 45 | Danger Zone | Delete all relationships | `<button type="submit">` | `btn destructive` | Destructive | Posts `/relationships/delete-all`. In the **Unlock panel's left column**, beneath the pair-context labels editor; the card renders only on a roster with rows. |
| 233 | Roster card | Unlock / Lock | `<button type="button">` | `btn secondary` | Secondary | Toggles the Unlock panel; renders only while the session is `is_editable` and no row is being edited or added. **One element, two homes**, as Observers' #178: the card's last child when collapsed, inside the panel when open. The label names the state it moves *to*. Each home carries a `<noscript>` twin (`?unlocked=1#roster-card` and back) |

---

## Section 8.5 — Observers Setup (`/operator/sessions/{id}/observers`)

Source: `app/web/templates/operator/session_observers.html`.

Numbered 8.5 so the three other roster sections keep their numbers and
the cross-references to them stay true.

> **Lifecycle.** This page does **not** read `is_editable`. Every
> mutating route takes `_require_not_archived`, so **every mutating
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
| 165 | Table toolbar | Add new | `<a>` | `btn secondary` | Secondary | Links to `?add=1#observers-row-editor`. Renders `disabled` while a row is being edited / added. Labeled `Add new` — see #125. |
| 166 | Table toolbar | Search | `<button type="submit">` | `btn secondary` | Secondary | Submits the search + status filter GET. Last in the row; the toolbar carries no selection-driven controls. |
| 167 | Row expander | Edit | `<button type="button">` | `btn secondary` | Secondary | Selection-driven — enabled on exactly one checked row. JS navigates to `?edit_id=<id>#observer-row-<id>`. Built into the injected expander, not server-rendered. |
| 168 | Row expander | Inactivate | `<button type="submit">` | `btn secondary` | Secondary | `formaction` `/observers/bulk-inactivate`. **Offered by status, not arity** — it renders only when the selection holds an active row, so a selection admitting neither pair shows neither button rather than two disabled ones. |
| 169 | Row expander | Activate | `<button type="submit">` | `btn secondary` | Secondary | `formaction` `/observers/bulk-reactivate`; the mirror of row 168, offered when the selection holds an inactive row. |
| 170 | Row expander | Delete | `<button type="submit">` | `btn destructive` | Destructive | Deletes the checkbox-selected rows via `/observers/bulk-delete`. Ships `disabled`: nothing syncs an injected confirm pair until its first tick, so a live-by-default Delete would be a destructive control with its gate open. Two-stage gate — a selection enables the `Yes, delete these` checkbox in the same panel, which enables this button (`data-delete-btn="observers-bulk-delete"`). |
| 171 | Row expander (cohort pane) | `+` | `<button type="button">` | `btn secondary cohort-combinator-btn` | Secondary | Adds a rule cell. Sized by a class, not an inline `style` (`spec/ui_elements.md` §6's no-inline-styled-buttons rule). |
| 172 | Row expander (cohort pane) | `AND` / `OR` | `<button type="button">` | `btn secondary cohort-combinator-btn` | Secondary | Toggles the combinator; the label *is* the current value, written back to a hidden input. |
| 173 | Row expander (cohort pane) | operator cycle | `<button type="button">` | `btn secondary cohort-cell-btn` | Secondary | Cycles the six operators (`IS THE SAME AS` / `IS DIFFERENT FROM` / `IS` / `IS NOT` / `CONTAINS` / `DOES NOT CONTAIN`); the label is the current value. One per rule cell. |
| 174 | Row expander (cohort pane) | `X` | `<button type="button">` | `btn destructive cohort-cell-btn` | Destructive | Removes a rule cell; `disabled` on the first. Removing the **last** cell destroys the `Save` riding in its row, which is rebuilt — anything bound to `Save` is bound where `Save` is built. |
| 175 | Row expander (cohort pane) | Save | `<button type="submit">` | `btn secondary cohort-cell-btn cohort-save-btn` | Secondary | Posts `/observers/cohort-rule` for every selected observer. Inline after the last cell's `X`, not bottom-right. `disabled` **until the rule is dirty**. An unsaved edit is guarded rather than discarded — `spec/setup_pages.md` § *Cohort match rule editor*. |
| 176 | Edit-row bar | Save | `<button type="submit">` | `btn secondary` | Secondary | Posts `/observers/create` or `/observers/{id}/update` via `form="observer-edit-form"`. Renders in a bracketed expander beneath the row being edited, not in a card — the same shape as Reviewers' (#128). |
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
| 49 | Lock card (when Activated or Closed) | Revert to draft | `<button type="submit">` | `btn alert` | Outline-amber | |
| 234 | Session status card | Expand all instruments | `<button type="button">` | `btn secondary` | Secondary | Opens every per-instrument card's `<details>` on the page |
| 235 | Session status card | Collapse all instruments | `<button type="button">` | `btn secondary` | Secondary | Closes every per-instrument card's `<details>` |
| 236 | Save-error banner (an instrument being edited) | Cancel | `<a>` | `btn alert` | Outline-amber | The mandatory Cancel on the `.banner.banner-error` a rejected bulk save renders (`spec/ui_elements.md` §5a). Returns to `?editing=<id>#instrument-<id>`, so the card stays unlocked |
| 237 | Save-error banner (no instrument being edited) | Cancel | `<a>` | `btn alert` | Outline-amber | The same banner's Cancel when no `editing` id is carried; returns to the bare page |
| 257 | Sort-save error banner | Cancel | `<a>` | `btn alert` | Outline-amber | The Cancel on `#sort-save-error-banner`, which renders when the no-JS `/fields/save` fallback rejects a sort spec. Returns to `?editing=<id>#instrument-<id>` for the instrument named by `sort_save_error_instrument_id` |

### 9b — Per-instrument card (one set per instrument)

| # | Card / sub-section | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 52 | Bottom action row (unlocked) | Save | `<button type="submit" form="dfsave-{iid}">` | `btn secondary` | Secondary | Bulk-save covers Band 1 form fields + Band 3 row state. Starts `disabled`; activates on first dirty event. Preserves `?editing=<id>` on redirect. |
| 53 | Bottom action row (unlocked) | Cancel | `<button type="button">` | `btn secondary` | Secondary | Confirms then reloads to discard unsaved client-side state. Mirrors Save's dirty-aware enabled state. |
| 54 | Bottom action row | Replicate | `<button type="submit">` | `btn secondary` | Secondary | Posts `/instruments/{iid}/replicate` — clones the card immediately after it; disabled only when the session is not editable |
| 55 | Bottom action row | Delete | `<button type="submit">` | `btn destructive` | Destructive | Ships `disabled`; a paired confirm checkbox flush-right below the row (`data-delete-confirm` / `data-delete-btn`) gates it. Disabled outright when it is the only instrument or the session is not editable. |
| 56 | Bottom action row | +Instrument | `<button type="submit">` | `btn secondary` | Secondary | Posts `/instruments/add-new-model` with `after={iid}`. **The sole "create new instrument" affordance on the row** — every new instrument is a new-model one, so there is no separate `Add instrument` / `Add group instrument` pair. |
| 56b | Bottom action row | +Page break | `<button type="submit">` | `btn secondary` | Secondary | Posts `/instruments/{iid}/page-break/create` (sets `starts_new_page=true` on the successor). Same Secondary role as +Instrument. Disabled on the last instrument, when the successor already carries a break, or past the editable window. |
| 57 | Bottom action row | Lock / Unlock | `<a>` | `btn secondary` | Secondary | The gating toggle, both anchors always rendered and swapped in-page by the client lock layer; their `?editing=<id>` hrefs are the no-JS fallback. An in-page Lock strips `?editing` from the URL. Clicking Lock with a dirty Save prompts `confirm()`. Marked disabled (`.disabled`, `aria-disabled`) only when the session is not editable. |
| 238 | Card header (unlocked) | Lock | `<a>` | `btn secondary` | Secondary | Header mirror of #57's Lock, sharing its `data-instrument-lock-toggle` so the dirty-state `confirm()` fires from either; there so the operator need not scroll past Bands 1–3 to change mode. Marked disabled (`.disabled`, `aria-disabled`) when the session is not editable |
| 239 | Card header (unlocked) | Save | `<button type="submit" form="dfsave-{iid}">` | `btn secondary` | Secondary | Header mirror of #52; starts `disabled` and is enabled in lockstep with it by the dirty tracker |
| 240 | Card header (unlocked) | Cancel | `<button type="button">` | `btn secondary` | Secondary | Header mirror of #53; starts `disabled`, enabled with Save |
| 241 | Card header (locked) | Unlock | `<a>` | `btn secondary` | Secondary | Header mirror of #57's Unlock; its `?editing=<id>` href is the no-JS fallback. Marked disabled when the session is not editable |
| 242 | Page-break card (before an instrument that starts a page) | × | `<button type="submit">` | `page-break-card-delete` | **Not `.btn`** — the page-break card's own control, outside §6 | Posts `/instruments/{iid}/page-break/delete`; `aria-label="Remove page break"`. `disabled`, with a title naming the unlock, while the page cannot be edited. Not rendered before the first instrument |
| 243 | Band 2, beside the preview heading (unlocked) | ↻ Refresh sample | `<button type="button">` | `btn secondary cohort-combinator-btn` | Secondary | Picks a new preview sample reviewee from the current Link 1 and Link 2 rules. `disabled` until every Band 1 link is set, because running on a Not-set link uses an empty filter |

### 9c — Row controls — Band 3's display-field and response-field tables

**There is no Response Type Definitions card**, and no
`response_type_definitions` table behind one. Per-field type, bounds
and list options live inline on `InstrumentResponseField`'s
`_inline_*` columns and are edited directly in the response-field row
(Type select, Min / Max / Step inputs, List options text, R / ≡ / X
buttons) — see `spec/instruments.md` "Response fields". There is no ✓
button: a row commits to the preview by itself once its live name and
shape are valid.

Each row carries its field's on/off chip around a hidden Active checkbox
— a response field's labeled with its name (`spec/instruments.md`
"Response fields" and "Display-field table");
both carry ▲ ▼ move buttons, `btn secondary`, except Name and Email. The
bindings differ: a response-field chip's box is the field's
`InstrumentResponseField.visible`; a display-field chip's puts its key in
the instrument's `selected_display_keys`. The response-field row's ▲ ▼
are full-size, like its other row buttons; the display-field row's are
the short size, `btn secondary btn-short` — see `spec/instruments.md` "Display-field table".

The response-field row's **R** (required), **≡** (help-text card) and
**⑂** (branch) take §6's **Toggle** role: each renders `btn` (Primary's
fill) when on and `btn secondary` when off, with `aria-pressed`
carrying the state.

| # | Card / sub-section | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 223 | Response-field row | R | `<button type="button">` | `btn` (on) / `btn secondary` (off) | **Toggle** | Toggles the field's `required`; disabled ("Enter a field name first.") while the row has no field name, and while a Require branch governs the field |
| 224 | Response-field row | ≡ | `<button type="button">` | `btn` (on) / `btn secondary` (off) | **Toggle** | Toggles the field's help-text card on the reviewer surface (`help_text_visible`); disabled ("Enter a field name first.") while the row has no field name |
| 230 | Response-field row | ⑂ | `<button type="button">` | `btn rf-glyph` (on) / `btn secondary rf-glyph` (off) | **Toggle** | Adds a branch below the field. On (`aria-pressed="true"`) once the field has a branch, and disabled then; also disabled while the row has no field name, for a String field, and inside a branch whose responses lock it (`branch_locked`). Absent on level-2 rows, which cannot branch again |
| 244 | Response-field row | + | `<button type="button">` | `btn secondary rf-glyph` | Secondary | Adds a response field below this one — inside a branch, a field to that branch. The branch's condition row carries one too, which adds a field at the top of the branch and is `disabled` while the branch's responses lock it |
| 245 | Response-field row | ↰ | `<button type="button">` | `btn secondary rf-glyph` | Secondary | On a row outside any branch, joins the deepest branch that ends directly above it, at that branch's level; it never starts a branch (⑂ does). `disabled` on the first row, on a field with a branch, on a field with saved responses, on an unnamed field, in a locked branch, and when no branch ends directly above. A level-1 row carries a second ↰, before its ↳, that joins the branch inside its own branch ending directly above; `disabled` on a field with a branch, on an unnamed field, in a locked branch, or when no such branch exists |
| 246 | Response-field row (inside a branch) | ↳ | `<button type="button">` | `btn secondary rf-glyph` | Secondary | The same control as #245's join on a row a branch governs: moves the field out of its branch, or, on the branch's only field, detaches it and ends the branch. `disabled` on a field with a branch and in a branch whose responses lock it |
| 265 | Display-field row | ▲ / ▼ | `<button type="button">` | `btn secondary btn-short` | Secondary | Moves the row up or down. Absent on a locked field; ▲ is `disabled` on the first row and below a locked one, ▼ on the last row |
| 266 | Response-field row | ▲ / ▼ | `<button type="button">` | `btn secondary` | Secondary | Moves the field up or down — inside a branch, within that branch. `disabled` at either end of its run |
| 267 | Response-field row | X | `<button type="button">` | `btn destructive` | Destructive | Removes the row client-side; the bulk Save (#52) writes it. `disabled` on a field with saved responses, a field with a branch, and a field in a branch whose responses lock it; a card's last row is never removed. A branch's condition row has no X — the branch goes with its last field |

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
not enumerated here. **The `.btn`-shaped controls sit where the four
roster pages put theirs**: the filter strip in the preview table's
toolbar right pane, the selection's status buttons in the row
expander.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 71g | Row expander | Inactivate | `<button type="submit">` | `btn secondary` | Secondary | `formaction` `/assignments/bulk-inactivate`; submits the `assignments-bulk-form` from the row-select checkbox column; enabled on ≥1 selection **and** `can_edit`. Rendered **by status, not arity**, as rows 123 / 124 are: emitted only when the selection holds an included pair, so a selection of entirely-included rows no longer also carries an `Activate` that would no-op on every row. Sits in the expander injected beneath the selection, after the `N of M selected` count. |
| 71h | Row expander | Activate | `<button type="submit">` | `btn secondary` | Secondary | `formaction` `/assignments/bulk-activate`; enabled on ≥1 selection **and** `can_edit`. Emitted only when the selection holds an excluded pair — see 71g. **No `Edit` and no `Delete` join them**: assignments are not edited row by row and not deleted, so this expander is the count and the status button(s) — two only on a mixed selection — where the rosters' also carries `Edit`, `Delete` and its confirm. |
| 71i | Table toolbar | Search | `<button type="submit">` | `btn secondary` | Secondary | Submits the "Search by" (All / Reviewers / Reviewees) + search GET; last in the `filter-actions` row, which is now the toolbar's right pane. Carries the `#assignments-table-card` fragment so a search lands on the table. |
| 71j | Table toolbar | Clear | `<a>` | `btn secondary` | Secondary | Resets the filter; rendered whenever a filter is on — a search term or a status other than All — as on the other table pages. |
| 71k | Replace-not-confirmed banner | Cancel | `<a>` | `btn alert` | Outline-amber | The mandatory Cancel on the `.banner.banner-error` a direct POST to `/assignments/generate` without `confirm_replace` lands on (`?needs_confirm=1`; `spec/ui_elements.md` §5a). Returns to the bare page |

Button numbers in this section carry letter suffixes (`71g` etc.) so
that inserting the section did not renumber every section after it.
**Numbers are stable identifiers here** — other documents cite them —
so a later pass may flatten the sequence only together with those
citations.

---

## Section 12 — Previews — no page, no picker

**There is no Previews hub.** Its two jobs are on the Manage
Invitations per-reviewer drill-in. `GET /operator/sessions/{id}/previews`
is a **308 permanent redirect** to `/operator/sessions/{id}/invitations`,
and `POST /previews/random` does not exist — a POST is not a bookmark.
There is no `session_previews.html` or `_preview_picker.html`.

The affordances a reader may be looking for here are on the drill-in:
**Open reviewer surface** (§13 row 87b) and the email preview tab
strip (§12b). There is no previewing-as picker: no `Apply`,
`← Previous`, `Next →` or `Random`.

### 12b — Email preview tabs (partial, on the drill-in)

`_email_preview_region.html` renders on
`session_invitations_reviewer_detail.html`, for a named reviewer.

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
| 84 | Table toolbar | Clear | `<a>` | `btn secondary` | Secondary | Rendered only when a filter is active; carries the `#<noun>-table-card` fragment, so clearing lands on the table |
| 85 | Table toolbar | Search | `<button type="submit">` | `btn secondary` | Secondary | Labeled `Search`, not `Apply`, matching the four rosters and Assignments. |
| 86 | Invitations table (per row) | Send | `<button type="submit">` | `btn secondary` | Secondary (Disabled when session not ready) | One per row; visible while the invitation is `pending` |
| 87 | Invitations table (per row) | Send reminder | `<button type="submit">` | `btn secondary` | Secondary (Disabled when row is complete or session not ready) | One per row; visible once the invitation is past `pending` |
| 87a | Invitations table (per row) | Regenerate | `<button type="submit">` | `btn secondary` | Secondary (Disabled when session not ready) | One per row, whenever an `Invitation` row exists |
| 87b | **Per-reviewer drill-in** → Review Progress card | Open reviewer surface | `<a>` | `btn secondary` | Secondary | Source is `session_invitations_reviewer_detail.html`, not this section's page — the drill-in is filed here because it belongs to the Invitations tab and has no section of its own. In a `.card-action-row` at the card's foot; `target="_blank"` + `rel="noopener"`. Renders only when the reviewer has a table row with at least one assignment |

**The page body carries no bulk-action bar.** Send invites and Send
reminders belong to the Workflow card's stepper (§5a), and the outbox
is reached from Sessions Diagnostics (§21), not from here —
`spec/operations_pages.md`. There is no Create invites button: Prepare
creates one invitation per eligible reviewer.

---

## Section 14 — Responses (`/operator/sessions/{id}/responses`)

Source: `app/web/templates/operator/session_responses.html`.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 90 | Table toolbar | Clear | `<a>` | `btn secondary` | Secondary | Rendered only when a filter is active; carries the `#<noun>-table-card` fragment, so clearing lands on the table |
| 91 | Table toolbar | Search | `<button type="submit">` | `btn secondary` | Secondary | Labeled `Search` — see row 85. |

**No bulk-action bar and no Actions column.** Send reminders belongs
to the Workflow card's stepper (§5a) and the Invitations tab is
reached from the chrome — `spec/operations_pages.md`.

---

## Section 14.5 — Extract data (`/operator/sessions/{id}/extract-data`)

Source: `app/web/templates/operator/session_extract_data.html`. The
Data shaper's action row repeats on every shape sub-card and is listed
once, as are the Extract Setup card's per-entity rows
(`operator/partials/_extract_data_card.html`, included by the page).

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 210 | Extract all data | Zip all | `<a download>` | `btn secondary` | Secondary | `GET …/export/responses_bundle.zip` |
| 211 | By instrument | Zip all | `<a download>` | `btn secondary` | Secondary | `GET …/export/by_instrument_bundle.zip` |
| 212 | Reviewer response metadata | Download | `<a download>` | `btn secondary` | Secondary | `GET …/export/reviewer_metadata.csv` |
| 213 | Reviewee response metadata | Download | `<a download>` | `btn secondary` | Secondary | `GET …/export/reviewee_metadata.csv` |
| 214 | Data shaper, shape sub-card | Save | `<button type="button">` | `btn secondary` | Secondary | `POST …/extract-data/shapes`, or `PATCH …/shapes/{shape_id}` once saved. Enabled in edit mode when the shape is valid and has unsaved changes |
| 215 | Data shaper, shape sub-card | Edit | `<button type="button">` | `btn secondary` | Secondary | Saved mode only; switches the sub-card into edit mode |
| 216 | Data shaper, shape sub-card | Cancel | `<button type="button">` | `btn secondary` | Secondary | Abandons unsaved edits and unselects the sub-card; disabled outside edit mode |
| 217 | Data shaper, shape sub-card | Delete | `<button type="button">` | `btn destructive` | Destructive | `DELETE …/shapes/{shape_id}`. Ships `disabled aria-disabled="true"`; the sub-card's confirm checkbox beneath the action row, flushed right, enables it (convention 6, keyed `shape-{id}` / `shape-new-N`). Cancel or a change of shape clears the tick. On the only sub-card it resets that card to blank |
| 218 | Data shaper, shape sub-card | +Shape | `<button type="button">` | `btn secondary` | Secondary | Spawns a blank sub-card after this one and selects it |
| 219 | Data shaper, shape sub-card | Download | `<a download>` | `btn secondary` | Secondary (Disabled until saved) | `aria-disabled` until the shape has an id, then `GET …/shapes/{shape_id}/download.csv` |
| 220 | Data shaper | Zip all | `<a download>` | `btn secondary` | Secondary (Disabled until a shape is saved) | `GET …/export/data_shapes_bundle.zip`, every saved shape's file; `href="#"` + `aria-disabled` while none is saved, re-synced as shapes save and delete |
| 221 | Archive session | Purge and archive / Already archived | `<button type="submit">` | `btn danger-solid` | Alert | Posts `/operator/sessions/bulk-archive` with the ticked purge options and `return_to=archived` — the lobby's #203 route. Disabled when the session is Activated or already archived |
| 222 | Token keys | Download token keys | `<a>` | `btn secondary` | Secondary | `GET …/export/participant_tokens.csv`. The card renders only when `observers_enabled` |
| 227 | Extract Setup, per-entity row (Reviewers / Reviewees / Relationships / Observers) | Download | `<a download>` | `btn secondary` | Secondary (Disabled when the roster is empty) | `GET …/export/{key}.csv`. With no rows it renders `aria-disabled="true"` with no `href`, titled "No {noun}s to download yet". The Observers row renders only when `observers_enabled` |
| 228 | Extract Setup | Download (Session settings) | `<a download>` | `btn secondary` | Secondary | `GET …/export/settings.csv`; always live |
| 229 | Extract Setup | Download (Zip all) | `<a download>` | `btn secondary` | Secondary | `GET …/export/bundle.zip` — the setup CSVs only |

---

## Section 15 — Operator Settings (`/operator/settings`)

Source: `app/web/templates/operator/operator_settings.html`.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 92 | Email send (SMTP) form | Cancel | `<a>` | `btn secondary` | Secondary | Returns to `?return_to=<path>` |
| 93 | Email send (SMTP) form | Save | `<button type="submit">` | `btn secondary` | Secondary | Disabled until input touched |
| 93a | Date & time card | Save timezone | `<button type="submit">` | `btn secondary` | Secondary | Posts `/operator/settings/timezone`; persists the `display_timezone` preference |
| 94 | Danger Zone | Clear all settings | `<button type="submit">` | `btn destructive` | Destructive | Posts `/operator/settings/clear` |

---

## Section 16 — Rule authoring — Band 1, not a page of its own

**There is no Rule Builder page and no Rule Based Assignment card.**
Band 1 of the per-instrument card on the Instruments page is the sole
rule-authoring surface — see [`spec/assignments.md`](assignments.md)
and `spec/instruments.md` "Link 1 / Link 2 — filter rule list" and
"Link 3 — Unit of review" for what each control does. Every control
here acts client-side; the card's bulk Save (#52) writes the rule.

| # | Card / sub-section | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 258 | Link 1 / Link 2 builder | + | `<button type="button">` | `btn secondary cohort-combinator-btn` | Secondary | Adds a rule cell |
| 259 | Link 1 / Link 2 builder | AND / OR | `<button type="button">` | `btn secondary cohort-combinator-btn` | Secondary | Labeled with the Link's current combinator; toggles it |
| 260 | Link 1 / Link 2 rule cell | Operator (`IS`, `IS NOT`, …) | `<button type="button">` | `btn secondary cohort-cell-btn` | Secondary | Labeled with the cell's current operator; cycles through the Link's operators |
| 261 | Link 1 / Link 2 rule cell | X | `<button type="button">` | `btn destructive cohort-cell-btn` | Destructive | Removes the cell; `disabled` on the first cell |
| 262 | Link 3 builder | + | `<button type="button">` | `btn secondary cohort-combinator-btn` | Secondary | Adds a boundary-tag cell |
| 263 | Link 3 builder | THE SAME | `<button type="button">` | `btn secondary cohort-combinator-btn` | Secondary (Disabled) | Always `disabled`: a marker that group members agree on every picked tag, not an action |
| 264 | Link 3 boundary cell | X | `<button type="button">` | `btn destructive cohort-cell-btn` | Destructive | On the last cell only; removes it. `disabled` when it is the only cell |
| 268 | Link 3 boundary cell | AND | `<button type="button">` | `btn secondary cohort-cell-btn` | Secondary (Disabled) | On every cell but the last, in place of the X: a marker, not an action |

---

## Section 17 — Global chrome utility menu (every page)

Source: `app/web/templates/base.html` (chrome top-right). Renders
on every page (operator + reviewer); only the operator view is
enumerated here.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 100 | Chrome user menu | Settings | `<a>` | `chrome-link` | Chrome utility link | Round-trips via `?return_to=<path>`. Not rendered on `/operator/settings` itself |
| 101 | Chrome user menu | About | `<a>` | `chrome-link` | Chrome utility link | Same `?return_to=<path>` pattern. Not rendered on `/about` itself |
| 102 | Chrome user menu | Sign out | `<a>` | `signout` | Chrome utility link | Hits `/.auth/logout` (Easy Auth) |
| 225 | Chrome user menu | Admin | `<a>` | `chrome-link` | Chrome utility link | Sys-admins only, and not on the `/operator/sys-admin` pages; same `?return_to=<path>` pattern |
| 226 | Chrome user menu | Guide | `<a>` | `chrome-link` | Chrome utility link | Same `?return_to=<path>` pattern. Suppressed on `/guide` itself and for a viewer who resolves no Guide audiences (`spec/operator_ui_concept.md` "`/guide` — Guide") |

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
Sys-admin-gated. Sections 19, 20 and 22 catalogue this page's children and
link back to it.

**Section numbers are stable identifiers, not an ordering.** This page
is §21 rather than slotted before §19 because other documents cite
sections by number — `spec/email_template_editor.md` cites §10 — so
renumbering to tidy the order breaks those citations. A new section
takes the next free number.

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 196 | Sessions table, per row (Actions) | Manage | `<button type="submit">` in a `<form>` | `btn secondary` | Secondary | POSTs `…/sessions/{id}/adopt` — self-adds the sys-admin as an owner (audited `session.owner_added`), then opens the session. **The only door**: no row may link straight into a session the sys-admin does not own. |
| 197 | Sessions table, per row (Actions) | Outbox | `<a>` | `btn secondary` | Secondary | Child page, read-only for a non-owner sys-admin. |
| 198 | Sessions table, per row (Actions) | Audit log | `<a>` | `btn secondary` | Secondary | Child page (Section 20). |
| 247 | Page top | ← Back to {{ return_to_label }} | `<a>` | `back-link` | Return-to (`.back-link`) | Returns to wherever the chrome's Admin link (#225) was followed from |
| 248 | Sys Admin tab strip | Sessions Diagnostics | `<a>` | `nav-tab` (`.active` on this page and its Outbox and Audit log children) | Nav (page-internal) | `app/web/templates/operator/partials/sys_admin_top_nav.html`, in a `tab-strip tab-strip-page sys-admin-nav` wrapper, on all four Sys Admin pages (§§19–22). The active tab stays an `<a>`, not the `<span aria-current>` convention 4 describes |
| 249 | Sys Admin tab strip | Accounts Management | `<a>` | `nav-tab` (`.active` on §19's page) | Nav (page-internal) | As #248 |

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
| 117 | Workspace users — bulk toolbar | Delete | `<button type="submit">` | `btn destructive` | Destructive | Hard-deletes the `users` row. Active when `session_count == 0` and the row has no history (created no session, no audit row as actor); server-side guards `owns_sessions` and `has_history` return 409 otherwise. Redirect omits `?selected=` so the deleted row isn't re-selected on the next render. |

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
| 119 | Audit log card heading | Download CSV | `<a download>` | `btn secondary` | Secondary | Links (GET) to `/operator/sessions/{id}/export/audit_log.csv`; the URL forward-carries the active filter set so the CSV matches the on-screen view. |
| 120 | Filter strip (button row) | Apply filters | `<button type="submit">` | `btn secondary` | Secondary | Right-aligned within a `.btn-pair` whose `justify-content: flex-end` is an inline `style` on the wrapper, not the class's; **Secondary, never Primary**, so it doesn't compete with the Download CSV button up at the card heading. |
| 121 | Filter strip (button row) | Clear | `<a>` | `btn secondary` | Secondary | Renders only when `filter_form.is_active`, before Apply filters. Resets to the canonical viewer URL with no query string. |
| 122 | Per-row detail | (expander) | `<summary>` inside `<details>` | `audit-detail summary` | Inline disclosure (custom) | Inline expander surfacing the canonical audit detail envelopes in human-readable sections + raw JSON in a nested `<details>`. Not a `.btn` but interactive — listed for completeness. |
| 250 | Below the table | Older events → | `<a>` | `chrome-link` | **Not `.btn`** — `chrome-link` reused in page content, as #187 | Renders only when a further page of events exists; carries the cursor and the active filter set |

Notes:

- **Filter strip layout:**
  - Left column: Event-type multi-select with `Ctrl/Cmd-click
    to select multiple` hint.
  - Right column flows actor email → From / To date selectors
    side-by-side (each half-width, flex children) → severity
    checkboxes on a single inline row.
- **Button-row gap.** The row's `.btn-pair` takes `margin-top: 16px;
  margin-bottom: 24px;` from an inline `style` on the wrapper — the
  class sets neither — so the row sits clear of both the filter strip
  above and the audit-log table below.

---

## Section 22 — Session outbox (`/operator/sys-admin/sessions/{id}/outbox`)

Source: `app/web/templates/operator/sys_admin_session_outbox.html`.
Sys-admin-gated and read-only; reached from §21's per-row Outbox (#197).

| # | Card | Label | Element | CSS class | Canonical | Notes |
|---|---|---|---|---|---|---|
| 251 | Page top | ← Back to Sessions Diagnostics | `<a>` | `back-link` | Return-to (`.back-link`) | |

---

## Cross-page button conventions

Conventions that bind every operator page, and are not restated per
section.

### 1. "Return to where you came from" is one class

Pages reached as a detour from the chrome — Operator Settings (#104),
About (#103), and the Sys Admin pages (#111, #118, #247, #251) — carry a
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
(§5a), where Send invites is Primary and Prepare session is
Secondary in the states that also offer Activate. *Prepare is the
interesting case for this rule*: it creates the invitations, but it does not send them, so it stays Secondary.

Per-row Send / Send reminder (#86, #87) stay **Secondary**: per-row
context overrides the role-based convention, because a table of
Primary buttons has no primary action at all.

### 3. Which action earns Primary in an activated session

In `ready` the Primary is the next forward stage of the invitation
flow — Send invites, then Send reminders. **With no invitations at
all there is no forward stage**: Prepare creates them and a `ready`
session cannot run Prepare, so State 7 offers Revert and Close only,
and the body copy names Revert. Close
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
`.tab-strip-page` modifier (in `base.html`) gives the row a grey tint
(`--surface-muted`), a thin `--border-default` border, and rounded
corners, so the active tab's `--nav-tab-active-bg` reads against the
gray strip. The chrome's Setup row is tinted differently
(`--nav-strip-setup-bg`, a pale blue). Hover and disabled treatments
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
revert, replace-upload, per-instrument delete, per-shape delete,
clear-responses) ships `disabled` and is enabled only while a paired
confirm checkbox is ticked. **The pairing is declarative and there is
one implementation**: `data-delete-confirm="KEY"` on the checkbox,
`data-delete-btn="KEY"` on the button, wired by a single global JS block
in `app/web/templates/base.html`. Any operator or reviewer page picks it
up by tagging the pair; no page carries its own confirm-checkbox JS.
The one thing a page may do is **clear** a tick whose context has gone
— uncheck it and dispatch `change` — as the Data shaper does on Cancel
or a change of shape (#217); the pairing then re-disables the button.

## Maintenance

**A PR that adds, removes or restyles a button updates its row here in
the same PR.** A row and its control change together, or the row is
prescribing something nobody built.

Numbers are stable identifiers — other documents cite them — so a new
button takes the next free number or a letter suffix within its
section, never a renumber of what follows. A restyle bundle, or a
change to `spec/ui_elements.md` §6, is the point at which to re-read
the sections it touches.
