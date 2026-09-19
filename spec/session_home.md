# Session Home page — functional spec

The session-scoped home page (Control Panel) for Review Robin. Lands the
operator in a session, surfaces the contextually appropriate next action,
and provides launch points for setup, operations, and metadata.

## Lifecycle state vocabulary

The session lifecycle has five live states. Internal enum values and
user-facing display labels differ for one of them; this spec uses enum
values when referring to code behavior and display labels when referring
to UI copy. See `spec/lifecycle.md` for the full state machine and
transitions.

| Enum | Display label | Status |
|---|---|---|
| `draft` | Draft | live |
| `validated` | Validated | live |
| `ready` | **Activated** | live |
| `expired` | Closed | live (Workflow-card "Close session": `ready → expired`) |
| `archived` | Archived | live (Workflow "Archive" / lobby "Purge and archive"; reversible via unarchive → draft) |

The enum/display divergence on `ready` → "Activated" exists because
"ready" reads as "ready to be activated" rather than "currently
running." Renaming the enum is non-trivial work touching code,
database, and API surfaces, so the divergence is handled at the
display layer instead: a single enum-to-label mapping
(`app/services/lifecycle_display.py` → Jinja filter
`lifecycle_label`) used by every UI surface that renders a
lifecycle state.

**What goes through the display mapping** (anything an operator
reads): the status pill, the page header lifecycle badge, prose in
UI copy, button labels, and confirmations. Inline prose may use
the lowercase form ("Session is currently activated.") since
sentence-case capitalisation is reserved for labels (pills, table
cells), not running prose.

**What stays as the enum** (anything a machine or developer reads):
URL slugs, query params, API responses, log messages, database
values, code identifiers, existing CSS class names.

**There is no `closed` state in the canonical enum.** `expired` is
the post-response-window state and *displays* as "Closed"; `expired`
and `archived` are the two post-life states. Nothing — CSS class,
query param or column value — may name a `closed` state.

## Page identity

| Field | Value |
|---|---|
| Page name | Session Home |
| Template | `session_detail.html` |
| URL | `GET /operator/sessions/{id}` |
| Grouping | Per Session Control Panel |

## Layout

Two full-width stacked cards below the chrome and status strip,
then a two-column bottom row.

### Page-card layout

```
┌────────────── Workflow ──────────────────────────────────────┐
│  full-width, just below the chrome                           │
└──────────────────────────────────────────────────────────────┘
┌────────────── Session details ───────────────────────────────┐
│  full-width; display ↔ edit swap (?editing=1)                │
│  + Owners / UI-settings sub-cards                            │
└──────────────────────────────────────────────────────────────┘
┌── Quick Setup ───────────┐  ┌── Danger Zone ───────────┐
│   scaffolded bulk        │  │   Delete Data / Delete   │
└──────────────────────────┘  └──────────────────────────┘
```

> **There are four cards on Home and no more.** There is no
> standalone Edit page — session config is displayed *and* edited on
> the Session details card, and `GET /operator/sessions/{id}/edit`
> is a redirect to `…?editing=1#session-config`. There is no
> separate read-only metadata card and no Schedule-timeline card:
> the config card carries those fields, and resolved fire-moments
> show inline next to each offset. The Extract Setup card lives on
> the **Extract data** Operations-strip tab
> (`_extract_data_card.html`), not here; see §2.

The Workflow card sits full-width at the top of the page-card
region, just below the chrome (same `next_action_card.html`
partial the Operations-row pages render). The **Session details**
card sits full-width directly below it — a display ↔ edit swap
(see §4). Below those two full-width cards, Quick Setup and
Danger Zone lay out as a `.bottom-grid` half-width pair.

DOM source order = mobile-collapse order:
**Workflow → Session details → Quick Setup → Danger Zone**.
Below a narrow viewport threshold the bottom pair collapses into
a single stacked column in that same order.

## Cards

### 1. Workflow card (full-width, top)

The page's center of gravity. Shows the single lifecycle-advancing
action appropriate to the session's current state, plus supporting
context that helps the operator decide whether to take it.

**Frame.** The card frame is constant across all lifecycle states:

- H2 title is the literal string **"Workflow"** (constant —
  the per-state action verb lives in the primary button label, not
  in the H2).
- Border picks up `--card-active-border`, the same shade as the Primary
  button inside the card. The blue framing signals this is the
  page's single most important card and ties visually to the
  primary action it carries.
- Card height grows to fit content. There's no fixed `min-height` —
  early states (empty draft) read short; states carrying several
  explanation paragraphs and a full button row read taller. Each
  state's vertical extent matches its content rather than padding to
  a uniform frame.

**Body layout.** Two vertically-stacked blocks inside the card, the
same in **every** state — there is no Activated-state exception:

1. `.next-action-body` — explanation paragraph(s), state-conditional.
   Grows to fill available space (`flex: 1 1 auto`).
2. `.next-action-buttons` — the button row, pinned to the bottom.
   Primary action first, supporting actions following as
   Secondary buttons. `spec/workflow_card.md` "Single-row button
   layout" carries the gating contract for which buttons appear.

`.next-action-confirm` and `<hr class="next-action-divider">` are
**not rendered by any state**. Both once described an Activated-state
split — two inline sections with their own buttons, no bottom-pinned
row — that the card has never shipped; the single row above replaced
it, and a confirm checkbox rides inside the form rather than in a
block of its own.

The empty-draft short-circuit state renders only a single
paragraph in `.next-action-body` and skips the button row.

**Buttons.** Primary action uses Primary styling (solid
`--btn-primary-bg`); supporting actions use Secondary styling (white
background, default border). Inline middle-dot links are not used
here. POST forms (Activate, and the two draft-returning transitions
`next-action-revert-form` / `next-action-pause-form`) declare a
hidden form id in the body and the submit button declares
`form="next-action-{name}-form"` so the form definition stays
near its checkbox while the button lives in the row (or, in the
Activated state, in the inline section).

**Contents by lifecycle state:** see **`spec/workflow_card.md`**.
That spec is the canonical source for the ten-state cascade
(States 1 / 2 / 3 / 4 / 4Err / 5 / 6 / 7 / 8 / 9 / 10, plus the
`W` overlay that rides on 4 / 5 / 6 when validation has
non-blocking findings),
the single-row button layout (≤ 4 visible buttons per state,
each at 25% column width, inactive hidden), the **Prepare
session** button (runs Generate + Validate + Invite in sequence with
per-step rollback and a saved-response reconcile-detour), the
standalone **Activate session** button (live from `validated`,
with a warnings-detour link to `/validate?activate=1` when the
readiness report has non-blocking findings to acknowledge),
and the right-column state-aware status / errors aside. Session
Home renders the same partial that every Operations-row page
renders; nothing on Home overrides the card's per-state
behaviour.

Notes specific to Session Home:

- **Empty-draft short-circuit.** The card surfaces a clear
  "fill the rosters first" instruction rather than sending the
  operator to Validate, where every error would amount to
  the same gap. The operator's path forward is the chrome top-nav
  Setup links (Reviewers / Reviewees / Relationships), which stay
  reachable while this state shows.
- **Workflow card in `ready`.** The forward action depends on
  invitation state: Send invites (Primary) until they're sent, then
  Send reminders (Primary). **With no invitations at all there is no
  forward action here** — Prepare creates them and a `ready` session
  cannot run Prepare, so the card's copy names Revert to draft
  instead (19Q Item 2 rung 3). Close session is always Secondary when
  live; Revert to draft is always Secondary when live — the
  layout never promotes either to Primary. The `ready → draft` form
  carries **no confirmation checkbox**; the lifecycle service's `confirm` gate is
  satisfied by a hidden field in the form.
- **No "See previews" button in any state.** The card has never rendered
  one. Email and reviewer-surface previews are reached from an Invitations
  per-reviewer drill-in once assignments exist; Home does not add a second
  door.
- **Status pills live in the right column**, not the body. States
  3 and 5 surface the readiness pill row (`pill-error` /
  `pill-empty` / `pill-count`) in the right-column
  `.next-action-status` aside, followed by a single link to the
  Validate page; the left column carries prose only. Home reports
  *how many*, Validate reports *which* — the column stopped
  enumerating the issues at 19Q Item 4. See `spec/workflow_card.md`
  "Right column — per state".
- **`expired` and `archived` are live states**, and the card's
  behaviour in each is `spec/workflow_card.md`'s State 10 and the
  no-buttons case respectively — see the lifecycle-behavior summary
  below.

### 2. Extract Setup card — on the Extract data tab, not Home

**The Extract Setup card does not render on Session Home.** It lives
on the **Extract data** Operations-strip tab
(`session_extract_data.html`, via the `_extract_data_card.html`
partial), in that page's right-hand wrap-up column alongside the
Archive-session and (observers-gated) Token-keys cards. Its contract
is specified here, because the round-trip it forms with Quick Setup
is a Home concern; the surface it renders on is not Home.

The card for porting / archiving — the CSVs Quick Setup can
re-ingest. Four always-present per-entity download tiles, plus a
conditional Observers tile when `observers_enabled`, plus a Zip-all
bundle — arranged in two columns mirroring the Quick Setup slot
placement:

| Tile | DOM column | Condition |
|---|---|---|
| Reviewers | col 1, top | always |
| Reviewees | col 1, bottom | always |
| Relationships | col 2, top | always |
| Observers | col 2, second | `observers_enabled` |
| Settings  | col 2, third | always |
| Zip all | col 2, bottom | always |

The Observers tile is gated on `review_session.observers_enabled` — when the toggle is off the right column collapses to Relationships → Settings → Zip all. The tile greys out its Download button when observer count is 0. The `GET /operator/sessions/{id}/export/observers.csv` route emits a `session.observers_extracted` audit event. The Zip-all bundle (`build_setup_bundle`) includes `{code}_observers.csv` as a member only when `observers_enabled`.

**This card is setup-side only.** Its Zip-all bundle carries the four
setup CSVs and nothing else, exported as `{code}_setup.zip`. The
response-side downloads — unified Responses CSV, reviewer / reviewee
stats, per-instrument files — belong to a separate bundle at
`/export/responses_bundle.zip` (filename `{code}_responses.zip`),
behind the Extract data tab's own Zip-all button.

**There is no Assignments tile, and there is no assignments extract
route or audit event behind one.** Assignments are a materialized
derivative of the instrument rules, so the round-trip the operator
needs is Settings ↔ Relationships ↔ Reviewers / Reviewees.

**Grey-out when empty.** The Reviewers / Reviewees /
Relationships tiles grey out their Download button when the
underlying count is `0`. The Settings
tile is always clickable — a session always has settings to
extract. The Zip-all tile stays clickable for the same reason
(Settings always contributes).

**No audit-log tile in Extract Setup, deliberately.** The
audit-events CSV route (`GET /export/audit_log.csv`) exists, but
audit data belongs behind an admin / diagnostics doorway — as it does
at GitHub, Stripe, Slack, Notion and Atlassian — so its
operator-facing affordance is the `Download CSV` button on the Sys
Admin per-session audit-log page, never a tile here.

**No lifecycle gate.** The card renders identically in every
session state. Extraction is read-only and useful at every
state — `draft` (sanity-check the configured artefacts),
`validated`, `ready` (mid-flight responses snapshot), `expired`
(final dataset) and `archived`.

**Filenames** follow `{code}_{kind}.csv` (e.g.
`CS101_reviewers.csv`) via `app/services/extracts/__init__.py::filename`.

**Out of scope for this card.** Excel-format export. The audit-log
download, which lives on the Sys Admin per-session audit-log page.

### 3. Danger Zone card (bottom-right)

The Danger Zone card (Delete Data + Delete Session) occupies the
bottom-right of Home's `.bottom-grid`, paired with Quick Setup in the
bottom-left (`#danger-zone`).

Its contents:

- **Delete Data** — wipes all reviewer responses while preserving
  setup. Confirmation checkbox (`required`) + Destructive button.
  POSTs to `/operator/sessions/{id}/delete-data`. **Locked while
  Activated** on the same terms as Delete Session (below): confirm
  checkbox `disabled`, a "Data deletion is locked while status is
  Activated" note, and the `_require_editable` gate on
  `/delete-data`. Reviewer responses only exist once the session is
  Activated, so deleting them is a revert-first workflow — Revert to
  draft via the Workflow card, delete the data (the revert preserves the
  `Response` rows), then re-activate.
- **Delete Session** — removes the session entirely. Confirmation
  checkbox (`required`) + Destructive button. **Visible-but-disabled
  while Activated**: the button and confirm checkbox carry the
  `disabled` attribute, with an explanatory note ("Revert the
  session to draft first to enable deletion."). The server-side lifecycle
  gate (`_require_editable`) in `/delete` is the source of truth —
  a direct POST while Activated still 4xxs. Visible greyed-out so
  the operator always sees the affordance and the path forward
  (Revert to draft via the Workflow card first, then delete).

Description copy on the card: "Delete Data wipes every reviewer
response while leaving session setup intact. Delete session
removes the entire session. Both are locked while the session is
Activated — pause it first."

Both confirm checkboxes are `required`, so the destructive submit
is blocked without JavaScript unless the operator ticks the box.

**Confirm coupling (progressive enhancement).** Deleting the whole
session subsumes deleting its data, so ticking **Delete session**
marks the **Delete data** confirm as selected + inactive — its
checkbox goes checked + disabled and its button disabled; unticking
restores it (to its own disabled-while-Activated state). The
relationship is one-directional: ticking **Delete data** leaves
**Delete session** untouched and still selectable. Inline JS on
Session Home, acting at click-time so it cooperates with the
app-wide disabled-until-checked handler; with no JS the two forms
stay independent and the server still wipes all data on session
delete.

### 4. Session details card (full-width, below Workflow)

Session config is displayed *and* edited here: this full-width card
(`#session-config`) carries every config field in an in-place
**display ↔ edit swap**, and there is no Edit page to hop to. The card
element carries `data-config-mode="display|edit"`; each field
holds one slot in the same position — a read-only value
(`data-display-only`) in display mode and its `<input>`
(`data-edit-only`) in edit mode — toggled by the card's mode.

**Contents.** The card's `<h2>` is the literal string "Session
details". Then a two-column body of config fields, each with a
`form-help` label above its value:

- **Name / Code** — the two identity fields, top-left.
- **Description** — full-width `<textarea>` in edit mode; a
  `.config-value-multiline` block in display mode ("—" when null).
- **Help contact / Timezone** — top-right. Timezone renders the
  resolved zone as a compact GMT-offset + IANA id (e.g. "GMT+8
  Asia/Singapore") via `date_formatting.gmt_offset_zone_label`;
  edit mode is a datalist typeahead over the timezone options.
- **Schedule fields** — Start / End / Release-responses-from /
  Release-responses-until (`datetime-local` in edit mode) plus
  the **Send invites** (offset from Start) and **Send reminders**
  (offset from End) offset lists. In display mode each offset
  shows as a pill next to its **resolved send datetime**
  (`views.build_offset_display_rows`). Resolved fire-moments read
  inline beside their offset; there is no separate
  Schedule-timeline card.

Below the field block, a half-width `.bottom-grid` pair of
**sub-cards**:

- **Owners** (`#config-owners-card`) —
  display mode is a read-only Email / Name / Role / Added table;
  edit mode gains an Action (Remove) column plus an Add-owner
  typeahead over the workspace operator allowlist. Owner
  add/remove POST to `/owners/add` + `/owners/{user_id}/remove`
  and redirect back to Home in edit mode
  (`?editing=1#config-owners-card`); `owners_error` surfaces
  inline.
- **User interface settings** (`#config-ui-settings-card`) — two
  checkboxes: **Relationships tab and page**
  (`relationships_enabled`) and **Observers tab and page**
  (`observers_enabled`), letting the operator opt into those
  optional Setup tabs at any point. Each is lock-on-data:
  disabled once the corresponding roster has rows
  (`has_relationships` / `has_observers`), mirroring the
  service-layer guard against orphaning data.

**Edit affordance behavior:**

- Canonical edit state is the **`?editing=1`** URL param,
  server-set into `config_editing` and gated on the session
  actually being editable (`is_draft` or `is_validated`) so a
  stale link on an Activated session degrades to display mode.
- The Save / Cancel / Lock-toggle cluster sits bottom-right of
  the UI-settings sub-card. **Unlock** (display mode) links to
  `?editing=1`; **Lock** (edit mode) drops it. **Cancel** and
  **Lock** are anchors carrying real `?editing` hrefs so no-JS
  degrades to navigation; with JS the inline `sessionConfig`
  script swaps mode in place and resets the form on discard.
  **Save** submits the config form and starts `disabled` (a
  dirty-tracking script enables it once an edit is made, but it
  renders enabled server-side so no-JS still works).
- In Activated (and any non-editable) state the Lock toggle
  renders **inert** — `aria-disabled="true"` with a "Revert the
  session to draft to edit its details" tooltip.
- Editing session metadata (name / code / description / deadline
  / schedule / help contact / timezone) is non-destructive: it
  never deletes assignments or responses, so the form carries no
  response-loss acknowledgement gate.
- The Details / Schedule / UI-settings inputs submit as one form
  via the HTML5 `form="config-save-{id}"` association (they can't
  physically nest — the Owners sub-card carries its own form).
  **Save POSTs to `/operator/sessions/{id}/config`** (shared
  persistence helper `_apply_session_config_form`) and redirects
  back to Home in **display** mode (`#session-config`) — the
  operator saves in place instead of hopping to a child page.
- `GET /operator/sessions/{id}/edit` exists only as a **308
  permanent redirect** to `…?editing=1#session-config` for stale
  bookmarks. It keeps the `require_session_operator` gate, so a
  non-owner is refused rather than bounced.

Lifecycle state is shown in the chrome status strip and (on Home)
in the Workflow card's body copy when relevant.

### 5. Quick Setup card (bottom-left)

The Quick Setup card sits in the bottom-left of Home's
`.bottom-grid`, paired with the Danger Zone card on the right. It
renders four wired slots — Reviewers, Reviewees, Relationships,
Settings — plus a conditional Observers slot when
`observers_enabled`. The functional spec is
`spec/quick_setup_card_spec.md`.

Layout: a 2-column grid — Reviewers
+ Reviewees stack in the left column; Relationships + Settings
stack in the right column. A Lock / Unlock button sits in a footer
at the bottom-right and renders in every editable-conceivable
state on Session Home (`draft` / `validated` / `ready`); the card
defaults to locked so the operator must explicitly Unlock before
any setup change. Lock state lives in a per-session `HttpOnly`
cookie scoped to `/operator/sessions/{id}` (`qsu_{session_id}=1`
when unlocked).

State-conditional copy only — the card frame is constant:

- **Draft / Validated:** "Bulk-populate reviewers, reviewees,
  relationships, and settings from CSV files in one place."
- **Ready / Activated:** "Setup edits are paused while the
  session is Activated. Revert the session to draft to re-enable
  bulk setup." The Lock / Unlock button stays visible — unlocking
  is purely visual; the importer rejects mutating submits at
  the service layer (`_require_editable`) and the rejection
  surfaces inline as a scoped `banner-error` carrying "Revert the
  session to draft before applying setup changes" copy. The
  operator's actual path forward is Revert to draft, but the cosmetic
  unlock affordance stays consistent across states.

## Placeholder cards

**Session Home carries no placeholder card** — all four of its cards
are wired. The pattern is documented here because it is the app's one
shape for an inert card, and any future placeholder on any page must
match it rather than invent a second. It is a **class, not a macro**:
a `placeholder_card` macro existed and was retired unused. No live page uses
the placeholder class today.

- **Class:** `body.ui-v2 .card.placeholder` — `--surface-muted`
  background, with `--text-subtle` on both the heading and the body,
  `not-allowed` cursor.

The visual signal *"this is a placeholder, not a working
action"* is uniform across every instance. Per-card state
distinctions live in the body copy, not in opacity flips that
would desynchronize sibling placeholders. A future placeholder card on any
page reuses the same class without further design work.

## Lifecycle behavior summary

| State (enum / display) | Workflow card | Quick Setup | Extract Data |
|---|---|---|---|
| `draft` / Draft, rosters empty | State 1: "Session not fully set up…" — setup-completion checklist in right column; no buttons rendered | Live (up to five slots, Observers conditional; default-locked) | Live (4–5 tiles, Observers conditional; empty-count tiles grey their Download button) |
| `draft` / Draft, rosters populated, pre-generate | State 2: Prepare session live (Primary; runs Generate + Validate + Invite in sequence) | Live (up to five slots, Observers conditional; default-locked) | Live (4–5 tiles, Observers conditional) |
| `draft` / Draft, validated_just_ran with errors | State 3: Prepare session re-runnable (Primary); right column carries validation pill row + Validate link | Live (up to five slots, Observers conditional; default-locked) | Live (4–5 tiles, Observers conditional) |
| `validated` / Validated | States 4 / 4Err / 5 / 6: Activate session live (Primary; under the `W` overlay it detours through `/validate?activate=1`); Prepare session re-runnable (Secondary); Revert to draft live (Secondary); Send invites surfaces once invitations exist (Primary, State 5) | Live (up to five slots, Observers conditional; default-locked) | Live (4–5 tiles, Observers conditional) |
| `ready` / Activated | States 7 / 8 / 9: Send invites / Send reminders forward stages (whichever is next renders Primary; State 7 — no invitations — has none, and the copy names Revert to draft); Close session + Release responses live (Secondary); Revert to draft live (Secondary; the `ready → draft` form) | Live but body-greyed (toggle still visible; submits rejected at the service layer with a "Revert to draft first" banner) | Live (4–5 tiles, Observers conditional; identical rendering across lifecycle) |
| `expired` / Closed | State 10: Release responses (or Stop releasing when the window's open) · Archive session (Danger); Revert to draft live (Secondary, reopens for editing) | Live but body-greyed | Live |
| `archived` / Archived | No buttons rendered (the Workflow card surfaces no actions on archived sessions) | Body-greyed | Live |

The **Extract Data** column above describes the Extract Setup card
as it renders on the **Extract data** Operations tab, not on Home
(see §2).

The **Danger Zone** card (Delete Data + Delete Session) sits in
Home's bottom-right (see §3). Its per-state
availability: both Delete Data and Delete Session are active in
`draft` / `validated` and visible-but-disabled in `ready`
(Activated) — pause first to enable either.

**Disabled treatment on Home is plain greying-out, not yellow
lock cards.** The Workflow card carries any explanatory
messaging the operator needs about the session's current state
and what's locked. Yellow lock cards remain in use elsewhere in
the app (the Setup tabs, for instance) where there's no adjacent
action card doing the explanatory job.

## Out of scope for this page

- **Per-entity setup work.** Belongs on the five Setup pages.
- **Operations work** (invitations, monitoring, validation
  detail, reviewer experience preview). Belongs on the
  Operations pages. Home surfaces pointers and links, not the
  work itself.
- **Live operational dashboards.** Home shows terse pointers,
  not live updating widgets. Operations pages own the detail.
- **Multi-session views.** Home is single-session; cross-session
  navigation goes through the Overview.

## Implementation pointers

- The Workflow card's content is state-conditional. The card
  frame's constants are the H2 ("Workflow") and the
  `--card-active-border` border; height grows to fit content. The
  body / buttons stack above handles **every** state, Activated
  included — there is no two-section exception, and
  `.next-action-confirm` / `.next-action-divider` render nowhere.
  Implement as a single block in the template that switches body and
  buttons by lifecycle state.
- The empty-draft short-circuit (rosters not yet populated) is a
  special case computed in the route handler from
  `lifecycle.is_draft(session)` plus
  `csv_imports.existing_reviewer_count` /
  `existing_reviewee_count` / `assignments.existing_count`. Computed
  *after* the validation flow may have flipped `draft → validated`
  so a session that just transitioned out of draft doesn't fall
  through this gate.
- Reuse the existing Primary / Secondary button styling from the
  visual style spec; do not introduce new button variants for
  this page.
- **Both draft-returning transitions ship under one label, "Revert to
  draft", and are two different service calls.** `ready → draft`
  (`next-action-pause-form`, the transition legacy prose calls *Pause*)
  reuses `lifecycle.revert_session_to_draft`; `validated → draft`
  (`next-action-revert-form`) reuses
  `lifecycle.invalidate_session(reason="operator_revert")`. Both
  are wired via the same `POST /operator/sessions/{id}/revert`
  endpoint, which dispatches by current status.
- **Lifecycle display mapping.** Single function in
  `app/services/lifecycle_display.py`, registered as the
  `lifecycle_label` Jinja filter on the operator templates
  instance. Every UI surface that renders a lifecycle state in
  user-visible copy goes through this filter. URL slugs, API
  responses, log messages, and CSS class names continue to use
  enum values.
- The two-column layout is responsive only insofar as the app
  is generally desktop-first. Below a narrow viewport threshold
  the columns stack (right column below left).
