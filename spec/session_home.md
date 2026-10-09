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
│  Tags + optional-tab toggles are fields; no sub-cards        │
└──────────────────────────────────────────────────────────────┘
┌── Quick Setup ───────────┐  ┌── Owners ────────────────┐
│   bulk CSV uploads       │  │   add / remove; Unlock   │
│                          │  ├── Danger Zone ───────────┤
│                          │  │   Delete Data / Delete   │
└──────────────────────────┘  └──────────────────────────┘
```

> **There are five cards on Home and no more.** There is no
> standalone Edit page — session config is displayed *and* edited on
> the Session details card, and `GET /operator/sessions/{id}/edit`
> is a redirect to `…?editing=1#session-config`. There is no
> separate read-only metadata card and no Schedule-timeline card:
> the config card carries those fields, and resolved fire-moments
> show inline next to each offset. The Extract Setup card lives on
> the **Extract data** Operations-strip tab
> (`_extract_data_card.html`), not here; see §2. The Owners card
> (§3a) is its own, above the Danger Zone — not a sub-card of the
> Session details card.

The Workflow card sits full-width at the top of the page-card
region, just below the chrome (same `next_action_card.html`
partial the Operations-row pages render). The **Session details**
card sits full-width directly below it — a display ↔ edit swap
(see §4). Below those two full-width cards, Quick Setup pairs with
Owners + Danger Zone as a `.bottom-grid` half-width pair; Owners and
Danger Zone stack in that column, Owners on top (`.bottom-left`,
`spec/ui_elements.md` §10).

DOM source order = mobile-collapse order:
**Workflow → Session details → Quick Setup → Owners → Danger Zone**.
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
- Card height grows to fit content. The card has no `min-height` of
  its own, but `.next-action-body` carries `min-height: 7.5em` so the
  button row lands at the same height in every state; states with
  several explanation paragraphs grow past it (`spec/workflow_card.md`
  "Stable card height").

**Body layout.** Two vertically-stacked blocks inside the card, the
same in **every** state — there is no Activated-state exception:

1. `.next-action-body` — explanation paragraph(s), state-conditional.
   Grows to fill available space (`flex: 1 1 auto`).
2. `.next-action-buttons` — the button row, pinned to the bottom.
   Primary action first, supporting actions following as
   Secondary buttons. `spec/workflow_card.md` "Workflow stepper —
   single-row button layout" carries the gating contract for which
   buttons appear.

`.next-action-confirm` and `<hr class="next-action-divider">` are
**not rendered by any state**; a confirm checkbox rides inside its
form rather than in a block of its own.

The empty-draft short-circuit state renders only a single
paragraph in `.next-action-body` and skips the button row.

**Buttons.** Primary action uses Primary styling (solid
`--btn-primary-bg`); supporting actions use Secondary styling (white
background, default border). Inline middle-dot links are not used
here. POST forms (Activate, and the two draft-returning transitions
`next-action-revert-form` / `next-action-pause-form`) declare a
hidden form id in the body and the submit button declares
`form="next-action-{name}-form"` so the form definitions stay
together in the body while the buttons live in the single button
row. The one exception is Prepare's regenerate confirmation: while it
is open, `Regenerate & prepare` and `Cancel` render inside the banner
above the row.

**Contents by lifecycle state:** see **`spec/workflow_card.md`**.
That spec is the canonical source for the ten-state cascade
(States 1 / 2 / 4 / 4Err / 5 / 6 / 7 / 8 / 9 / 10, plus the
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
  instead. Close session is always Secondary when
  live; Revert to draft is always Secondary when live — the
  layout never promotes either to Primary. The `ready → draft` form
  carries **no confirmation checkbox**; the lifecycle service's `confirm` gate is
  satisfied by a hidden field in the form.
- **No "See previews" button in any state.** The card has never rendered
  one. Email and reviewer-surface previews are reached from an Invitations
  per-reviewer drill-in once assignments exist; Home does not add a second
  door.
- **Status pills live in the right column**, not the body. State
  4Err and the `W` overlay surface the readiness pill row (`pill-error` /
  `pill-empty` / `pill-count`) in the right-column
  `.next-action-status` aside, followed by a single link to the
  Validate page; the left column carries prose only. Home reports
  *how many*, Validate reports *which*; the column does not enumerate
  the issues. See `spec/workflow_card.md` "Right-column content by
  state".
- **`expired` and `archived` are live states**, and the card's
  behaviour in each is `spec/workflow_card.md`'s State 10 and the
  no-buttons case respectively — see the lifecycle-behavior summary
  below.

### 2. Extract Setup card — on the Extract data tab, not Home

**The Extract Setup card does not render on Session Home.** It lives
on the **Extract data** Operations-strip tab
(`session_extract_data.html`, via the `_extract_data_card.html`
partial), alone in the right-hand column of that page's wrap-up grid;
the left column stacks the (observers-gated) Token-keys card above
the Archive-session card. Its contract
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
| Session settings | col 2, third | always |
| Zip all | col 2, bottom | always |

The Observers tile is gated on `review_session.observers_enabled` — when the toggle is off the right column collapses to Relationships → Session settings → Zip all. The tile greys out its Download button when observer count is 0. The `GET /operator/sessions/{id}/export/observers.csv` route emits a `session.observers_extracted` audit event. The Zip-all bundle (`build_setup_bundle`) includes `{code}_observers.csv` as a member only when `observers_enabled`.

**This card is setup-side only.** Its Zip-all bundle carries the four
setup CSVs and nothing else, exported as `{code}_setup.zip`. The
response-side downloads — the unified Responses CSV plus the Extract
data cards' files — belong to a separate bundle at
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
bottom-left (`#danger-zone`). The Owners card (§3a) stacks above it in
the same column.

Its contents:

- **Delete Data** — wipes all reviewer responses while preserving
  setup. Confirmation checkbox (`required`) + Destructive button.
  POSTs to `/operator/sessions/{id}/delete-data`. **Locked while
  Activated** on the same terms as Delete Session (below): confirm
  checkbox `disabled`, a "Data deletion is locked while status is
  Activated" note, and the `_require_not_ready` gate on
  `/delete-data`. Once the session has ended (`expired`) or been
  `archived`, both deletes are live.
  During the response window it is a revert-first workflow — Revert to
  draft via the Workflow card, delete the data (the revert preserves the
  `Response` rows), then re-activate.
- **Delete Session** — removes the session entirely. Confirmation
  checkbox (`required`) + Destructive button. **Visible-but-disabled
  while Activated**: the button and confirm checkbox carry the
  `disabled` attribute, with an explanatory note ("Revert the
  session to draft first to enable deletion."). The server-side lifecycle
  gate (`_require_not_ready`) in `/delete` is the source of truth —
  a direct POST while Activated still answers 409. Visible greyed-out so
  the operator always sees the affordance and the path forward
  (Revert to draft via the Workflow card first, then delete).

Description copy on the card: "Delete Data wipes every reviewer
response while leaving session setup intact. Delete session
removes the entire session. Both are locked while the session is
Activated — Revert to draft first."

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

### 3a. Owners card (above Danger Zone)

A card of its own, half width, stacked above Danger Zone in the same
`.bottom-left` column (`#owners-card`) — not a sub-card of the Session
details card, and gated on no lifecycle state: it is always visible,
in every state, with no `?editing=1`. It has a **Lock / Unlock of its
own, as Quick Setup does**, against accidental edits: locked by default, the `oou_{session_id}` cookie
when unlocked, relocked on leaving Home or on any other Home form's submit, visual only. **Add owner and
each Remove save at once** — no Save or Cancel. Full contract — the table, the
candidates, and the Create page's matching card, which stages instead
— in `spec/session_owners.md`.

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
plain `<label>` above its value:

- **Name / Code** — the two identity fields, top-left.
- **Description** — below Name / Code in the left column; a
  `<textarea>` in edit mode, a `.config-value-multiline` block in
  display mode ("—" when null).
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
  Schedule-timeline card. Each box is seeded with its stored value in
  the session's zone and read back as wall-clock in the submitted zone,
  except that while the zone is unchanged a box still holding its seeded
  text keeps the stored instant (`sessions.datetime_box_unedited`): in
  the repeated hour after a DST fall-back the text names two instants,
  and re-reading it would move the value an hour early on every Save.
  A kept Start, and the stored offsets on a kept Start or End, skip
  only the lead-time floor: a schedule that aged past it after saving
  stays put (`spec/lifecycle.md` §8.3), so a rename is never refused
  over it. Every other check still runs.

Two more fields follow Description in the left column. The card holds
no sub-card, `.card` or `.bottom-grid`; Owners is a card of its own
(§3a).

- **Tags** (`#config-tags-field`, label "Tags (optional)", set a step
  further below Description than a label's own top margin puts it, by
  `.config-field-gap`) — a field of this card: it shares the card's
  display/edit swap, its edit window and its `config-save` form, with
  no save of its own. Locked, it shows the tags as the sessions lobby's
  pills (`.pill .pill-count` in
  `.session-tags`, uppercased by `.pill`), or an em dash `.config-value`
  when there are none; unlocked, one comma-separated box that completes
  the tag at the end of the line as it is typed (the shared tag
  typeahead, `spec/sessions_overview.md`), with a `.form-help` below the
  box ("Comma-separated; also editable from the sessions list.",
  `spec/ui_elements.md` "Helper text") that shows only while editing
  because it describes the box. **An emptied box clears the tag set**,
  as the lobby's row expander does — the opposite of the Create
  page's box, where there is no set yet (`spec/csv_contracts.md`
  § *Settings CSV — apply precedence*). The card also posts a
  `tags_present` marker, and **only a save carrying it writes
  tags**: FastAPI hands an absent field and an empty one to the
  route identically, and a page rendered before the field existed
  must not clear every tag on its first Save. Because `/config`
  refuses a non-editable session, this surface edits tags in draft
  and validated only; the lobby edits them in any state
  (`spec/sessions_overview.md`).
- **Optional setup tabs and pages** (`#config-optional-tabs`, a
  `role="group"` labeled "Optional setup tabs and pages", no
  subtitle) — two selector chips, **Relationships** (`relationships_enabled`) and
  **Observers** (`observers_enabled`), in the rosters' "Show columns"
  chip style, letting the operator opt into those optional Setup tabs
  at any point. Unlocked, each chip is a `<label>` around its
  visually hidden checkbox, filled while the box is ticked
  (`spec/ui_elements.md` "Label or control"). Locked, they are inert
  `.tag-chip.is-locked` spans showing the stored state, and stating it
  to assistive technology as disabled checkboxes (`role="checkbox"`,
  `aria-checked`, `aria-disabled`, no tab stop). Each is lock-on-data:
  in edit mode its checkbox renders disabled and its chip `is-locked`,
  titled "The session has relationships, so the tab stays on." (or
  observers), once the corresponding roster has rows
  (`has_relationships` / `has_observers`), mirroring the service-layer
  guard against orphaning data.

**Edit affordance behavior:**

- Canonical edit state is the **`?editing=1`** URL param,
  server-set into `config_editing` and gated on the session
  actually being editable (`is_draft` or `is_validated`) so a
  stale link on an Activated session degrades to display mode.
- The Save / Cancel / Lock-toggle cluster sits at the foot of the
  right (schedule) column, flushed right (`margin-top: auto`).
  **Unlock** (display mode) links to
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
  response-loss acknowledgement gate. It also leaves a `validated`
  session `validated`: no field on the card can change the readiness
  check's verdict (`spec/lifecycle.md` §2.3).
- The Details / Schedule / Tags / optional-tab inputs submit as one form
  via the HTML5 `form="config-save-{id}"` association rather than a
  literal wrapping `<form>`. The Owners card (§3a) is not among
  them — it saves through its own route.
  **Save POSTs to `/operator/sessions/{id}/config`** (shared
  persistence helper `_apply_session_config_form`) and redirects
  back to Home **still unlocked** (`?editing=1`, no fragment): Save
  only saves, and **Lock** is what locks the card. The operator saves
  in place instead of hopping to a child page, and keeps their seat:
  the card's form stores the scroll position, with the time, on
  submit, and an inline script restores it on the reload (deferring to
  a shown `.banner-scroll-target`). The stored seat is read once and
  removed on any Home load, and counts only when it is under 15 seconds
  old and the load is Save's landing URL (`?editing=1`, no fragment),
  so a Save the server refuses — whose error page leaves the seat
  behind — gives a visit to Home after 15 seconds, or anywhere but
  Save's landing URL, neither its scroll nor its fade;
  a page restored from the back/forward cache drops both too. Save's
  reload alone also cross-fades
  rather than repainting from blank: a cross-document view
  transition whose `@view-transition` rule no stylesheet declares —
  `rrwSaveFade` adds it from script on the way out and on the way
  back, unless the reader prefers reduced motion — so every other
  navigation stays a plain load. A browser without view transitions
  skips the fade and keeps the scroll; without JS the reload lands at
  the top of the page (before 19U Item 4 it landed at the card's top
  edge). An in-place Lock, Unlock or Cancel rewrites `?editing` in the
  address (`history.replaceState`), so a reload keeps the card's
  mode. The
  tag write runs **after** the config apply, so a save the card
  rejects writes no tags either, and every audit event one save
  produces shares one correlation id (the `audit_events`
  `correlation_id` column, one value per request). A code another
  session holds answers **422** before anything is written, the
  timezone included (`sessions.ensure_code_available`), and so does a
  Name or Code longer than its column (255 / 64), which the browser's
  `maxlength` otherwise prevents.
- `GET /operator/sessions/{id}/edit` exists only as a **308
  permanent redirect** to `…?editing=1#session-config` for stale
  bookmarks. It keeps the `require_session_operator` gate, so a
  non-owner is refused rather than bounced.

Lifecycle state is shown in the chrome status strip and (on Home)
in the Workflow card's body copy when relevant.

### 5. Quick Setup card (bottom-left)

The Quick Setup card sits in the bottom-left of Home's
`.bottom-grid`, paired with the Owners card on the right, which sits
level with it above the Danger Zone. It
renders four wired slots — Reviewers, Reviewees, Relationships,
Session settings — plus a conditional Observers slot when
`observers_enabled`. The functional spec is
`spec/quick_setup_card_spec.md`.

Layout: a 2-column grid — Reviewers
+ Reviewees stack in the left column; Relationships, Observers (when
rendered) and Session settings stack in the right column. A Lock / Unlock button sits in a footer
at the bottom-right and renders only while the card is available —
setup editable (`draft` or `validated`) with no persisted responses (`spec/quick_setup_card_spec.md`
"Visibility"); there the card defaults to locked so the operator
must explicitly Unlock before any setup change. Lock state lives in a per-session `HttpOnly`
cookie (`qsu_{session_id}=1` when unlocked, path `/` so the
navigation middleware can expire it anywhere; `spec/settings_inventory.md`
"Cookies").

State-conditional copy only — the card frame is constant:

- **Default (no responses):** "Bulk-populate {the slots} from files in
  one place. Available only while setup is editable (draft or
  validated) and the session has no responses." The slot list follows the slots rendered.
- **When the session holds responses (any state):** the same opening, then
  "Quick Setup is locked because this session already holds reviewer
  responses from a prior activation. Use the individual Setup pages
  to make changes."
- Whenever the card is unavailable (any session with responses,
  `ready`, `expired`, `archived`) the body greys and the Lock /
  Unlock button is hidden.

## Placeholder cards

**Session Home carries no placeholder card** — all five of its cards
are wired. The pattern is documented here because it is the app's one
shape for an inert card, and any future placeholder on any page must
match it rather than invent a second. It is a **class, not a macro**.
No live page uses the placeholder class today.

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
| `draft` / Draft, rosters empty | State 1: "Session not fully set up…" — setup-completion checklist in right column; no buttons rendered | Live while no responses exist (up to five slots, Observers conditional; default-locked) | Live (4–5 tiles, Observers conditional; empty-count tiles grey their Download button) |
| `draft` / Draft, rosters populated (before Prepare, or after a Prepare that failed) | State 2: Prepare session live (Primary; runs Generate + Validate + Invite in sequence) | Live while no responses exist (up to five slots, Observers conditional; default-locked) | Live (4–5 tiles, Observers conditional) |
| `validated` / Validated | States 4 / 4Err / 5 / 6: Activate session live (Primary; under the `W` overlay it detours through `/validate?activate=1`); Prepare session re-runnable (Secondary); Revert to draft live (Secondary); Send invites surfaces once invitations exist (Primary, State 5) | Live while no responses exist (default-locked; an import demotes to `draft`) | Live (4–5 tiles, Observers conditional) |
| `ready` / Activated | States 7 / 8 / 9: Send invites / Send reminders forward stages (whichever is next renders Primary; State 7 — no invitations — has none, and the copy names Revert to draft); Close session + Release responses live (Secondary); Revert to draft live (Secondary; the `ready → draft` form) | Body-greyed; no Lock / Unlock toggle | Live (4–5 tiles, Observers conditional; identical rendering across lifecycle) |
| `expired` / Closed | State 10: Release responses (or Stop releasing when the window's open) · Archive session (Alert); Revert to draft live (Secondary, reopens for editing) | Body-greyed; no Lock / Unlock toggle | Live |
| `archived` / Archived | No buttons rendered (the Workflow card surfaces no actions on archived sessions) | Body-greyed | Live |

The **Extract Data** column above describes the Extract Setup card
as it renders on the **Extract data** Operations tab, not on Home
(see §2).

The **Danger Zone** card (Delete Data + Delete Session) sits in
Home's bottom-right (see §3). Its per-state
availability: both Delete Data and Delete Session are active in
`draft` / `validated` / `expired` / `archived` and visible-but-disabled
in `ready` (Activated) — **Revert to draft** first to enable either. The **Owners** card
(§3a) stacked above it carries no such gate — it is active in every
lifecycle state.

**Disabled treatment on Home is plain greying-out, not yellow
lock cards.** The Workflow card carries any explanatory
messaging the operator needs about the session's current state
and what's locked. Yellow lock cards remain in use elsewhere in
the app (the Setup tabs, for instance) where there's no adjacent
action card doing the explanatory job.

## Out of scope for this page

- **Per-entity setup work.** Belongs on the six Setup pages.
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
  special case computed in `build_workflow_card_context`: a draft
  session with no reviewers (`csv_imports.existing_reviewer_count`),
  no reviewees (`existing_reviewee_count`), or an unconfigured
  instrument (`instruments.has_unconfigured`).
- Reuse the existing Primary / Secondary button styling from the
  visual style spec; do not introduce new button variants for
  this page.
- **Both draft-returning transitions ship under one label, "Revert to
  draft", and are two different service calls.** `ready → draft`
  (`next-action-pause-form`, the transition legacy prose calls *Pause*,
  and the same form for `expired → draft`) reuses
  `lifecycle.revert_session_to_draft`, which accepts both; `validated → draft`
  (`next-action-revert-form`) reuses
  `lifecycle.invalidate_session(reason="operator_revert")`. Both
  are wired via the same `POST /operator/sessions/{id}/revert`
  endpoint, which calls `lifecycle.operator_revert`. That dispatches by
  the status read under the session lock, not the loaded row, so a
  scheduled activation that committed after the page loaded takes the
  `ready → draft` branch (`spec/lifecycle.md` §2.6).
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
