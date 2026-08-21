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
| `expired` | Expired | live (Workflow-card "Close session": `ready → expired`) |
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

**Historical note.** Older docs and CSS once carried a
`.pill-lifecycle-closed` class referencing a `closed` state that
doesn't exist in the canonical enum. Cleanup landed during
Segment 11B PR E; `expired` and `archived` are the post-life
states.

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

### Page-card layout (18R Item 4)

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

> **Note.** Segment 18R Item 4 consolidated the session config
> display **and** edit onto Session Home. The standalone Edit
> page (`session_edit.html` + its GET/POST routes) was retired;
> `GET /operator/sessions/{id}/edit` now 301-redirects to
> `…?editing=1#session-config`. The old read-only "Session
> Details" metadata card (Created by / Created / Modified grid)
> and the Schedule-timeline card were both removed — the config
> card carries the same fields, and resolved fire-moments show
> inline next to each offset. The Extract Setup card (porting
> CSVs) moved off Home to the **Extract data** Operations-strip
> tab (`_extract_data_card.html`); see §2.

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

*Layout history:*
- 2026-05-14 (PR #967): Workflow card retired from Session Home;
  cards reorganised into a 2×2 grid (Session Details / Quick
  Setup top, Danger Zone / Extract Data bottom).
- 2026-05-14 (PR #969): Session Details + Quick Setup swapped
  with Danger Zone + Extract Data so Session Details anchored
  the top-left slot.
- 2026-05-14 (PR 6): Workflow card returns to Session Home (the
  card now functions as Operations-page chrome generally and
  Session Home is no exception); 2×2 grid replaced with two
  independent flex columns so Extract Data sits directly below
  Quick Setup without row-alignment forcing.
- 2026-05-22 (commit b490825): Danger Zone moved off Session Home
  into the bottom-right of the Edit Session Details page
  (`session_edit.html`) so destructive operations live alongside
  the other edit affordances. The left column now carries Session
  Details alone.
- 2026-08 (Segment 18R Item 4): the standalone Edit page retired;
  session config display + edit consolidated onto Home as the
  full-width **Session details** card (`?editing=1` swap, `/config`
  POST). Extract Setup relocated to the Extract data tab; the
  read-only metadata card + Schedule-timeline card removed; Danger
  Zone moved **back** to Home's bottom-right, paired with Quick
  Setup in the `.bottom-grid`.

## Cards

### 1. Workflow card (full-width, top)

The page's center of gravity. Shows the single lifecycle-advancing
action appropriate to the session's current state, plus supporting
context that helps the operator decide whether to take it.

**Frame.** The card frame is constant across all lifecycle states:

- H2 title is the literal string **"Workflow"** (constant —
  the per-state action verb lives in the primary button label, not
  in the H2).
- Border picks up `accent-blue`, the same shade as the Primary
  button inside the card. The blue framing signals this is the
  page's single most important card and ties visually to the
  primary action it carries.
- Card height grows to fit content. There's no fixed `min-height` —
  early states (empty draft) read short; the Activated state's two-
  section layout reads taller. Each state's vertical extent matches
  its content rather than padding to a uniform frame.

**Body layout.** Three vertically-stacked blocks inside the card,
in the standard treatment used by every state except Activated:

1. `.next-action-body` — explanation paragraph(s), state-conditional.
   Grows to fill available space (`flex: 1 1 auto`).
2. `.next-action-confirm` — optional, used in pre-Activated states
   that need a confirm checkbox. Sits immediately above the button
   row so the operator's eye flows top-down: read → confirm →
   click.
3. `.next-action-buttons` — the button row, pinned to the bottom.
   Primary action first, supporting actions following as
   Secondary buttons.

The **Activated state is an exception** — its body splits into two
inline sections separated by `<hr class="next-action-divider">`,
each with its own buttons and (for the Pause section) its own
`.next-action-confirm`. The bottom-pinned `.next-action-buttons`
row is *not* rendered while Activated; the buttons live next to
the body sections they belong to. See the per-state breakdown
below.

The empty-draft short-circuit state renders only a single
paragraph in `.next-action-body` and skips both
`.next-action-confirm` and `.next-action-buttons` entirely.

**Buttons.** Primary action uses Primary styling (solid
`accent-blue`); supporting actions use Secondary styling (white
background, default border). Inline middle-dot links are not used
here. POST forms (Activate, Revert to draft, Pause) declare a
hidden form id in the body and the submit button declares
`form="next-action-{name}-form"` so the form definition stays
near its checkbox while the button lives in the row (or, in the
Activated state, in the inline section).

**Contents by lifecycle state:** see **`spec/workflow_card.md`**.
That spec is the canonical source for the ten-state cascade
(States 1 / 2 / 3 / 4 / 4W / 4Err / 5 / 6 / 7 / 8 / 9 / 10),
the single-row button layout (≤ 4 visible buttons per state,
each at 25% column width, inactive hidden), the **Prepare
session** button (runs Generate + Validate in sequence with
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
  invitation state: Create invites (Primary) until invites
  exist, Send invites (Primary) until they're sent, then Send
  reminders (Primary). Close session is always Secondary when
  live; Revert to draft is always Secondary when live — the
  layout never promotes either to Primary. The pre-layout Pause
  confirmation checkbox retired with the State 6 refresh; the
  lifecycle-service `confirm` gate is upheld via a hidden field
  in the form.
- **No "See previews" in `ready`.** Operators monitor live
  responses while Activated; previewing is the validation-time
  affordance.
- **Status pills + per-issue list live in the right column**, not
  the body. States 3 and 5 surface the readiness pill row
  (`pill-error` / `pill-empty` / `pill-count`) and per-issue list
  in the right-column `.next-action-status` aside; the left
  column carries prose only. See `spec/workflow_card.md`
  "Right column — per state".
- **Reserved states (Expired, Archived).** Not yet in scope.
  Expected treatments:
  - **Expired** likely gets an Extract data primary action with
    "Deadline has passed" prominent (the new Operations-strip
    tab, not the Session Home Extract Setup card).
  - **Archived** likely renders the card empty or with a
    "Restore" affordance.

### 2. Extract Setup card — relocated to the Extract data tab

**As of Segment 18R Item 4 the Extract Setup card no longer
renders on Session Home.** It moved to the **Extract data**
Operations-strip tab (`session_extract_data.html`, via the
`_extract_data_card.html` partial), where it sits in the
page's right-hand wrap-up column alongside the Archive-session
and (observers-gated) Token-keys cards. Its contract is
unchanged — the tile table and grey-out rules below still
describe it, they just live on the Extract data page now, not
Home. The rest of this section is retained for that contract.

The card for porting / archiving — the CSVs Quick Setup can
re-ingest. Four always-present per-entity download tiles, plus a
conditional Observers tile when `observers_enabled`, plus a Zip-all
bundle — arranged in two columns mirroring the Quick Setup slot
placement:

| Tile | DOM column | Condition | Wired by |
|---|---|---|---|
| Reviewers | col 1, top | always | 12A-1 PR 2 (#717) |
| Reviewees | col 1, bottom | always | 12A-1 PR 2 (#717) |
| Relationships | col 2, top | always | 12A-3 PR 1 (#779) |
| Observers | col 2, second | `observers_enabled` | W13, PR #1755 |
| Settings  | col 2, third | always | 12A-1 PR 1 (#713) |
| Zip all | col 2, bottom | always | 18D PR E1 |

The Observers tile is gated on `review_session.observers_enabled` — when the toggle is off the right column collapses to Relationships → Settings → Zip all. The tile greys out its Download button when observer count is 0. The `GET /operator/sessions/{id}/export/observers.csv` route emits a `session.observers_extracted` audit event. The Zip-all bundle (`build_setup_bundle`) includes `{code}_observers.csv` as a member only when `observers_enabled`.

Originally five tiles (Reviewers / Reviewees / Relationships /
Settings / Responses) plus a zip footer; the Responses tile
moved to the new **Extract data** Operations-strip tab on
2026-05-29 (per `guide/archive/extract_data.md`). The Zip-all bundle
slimmed in the same change — it now contains only the four
setup CSVs and exports as `{code}_setup.zip` (was
`{code}_bundle.zip`). Response-side downloads — unified
Responses CSV, reviewer/reviewee stats, per-instrument files
— moved to the responses bundle at
`/export/responses_bundle.zip` (filename
`{code}_responses.zip`) behind the Extract data tab's
Zip-all button.

The post-15D + post-12A-3 layout settled in 12A-3 PR 2 (#780)
which also retired the Assignments tile end-to-end (route +
service + audit event) since assignments are a materialised
derivative post-15D and the operator's preferred round-trip is
Settings ↔ Relationships ↔ Reviewers / Reviewees.

**Grey-out when empty.** The Reviewers / Reviewees /
Relationships tiles grey out their Download button when the
underlying count is `0` (post-12A-3 polish #781). The Settings
tile is always clickable — a session always has settings to
extract. The Zip-all tile stays clickable for the same reason
(Settings always contributes).

**No audit-log tile in Extract Setup.** Segment 12B shipped the
audit-events CSV route (`GET /export/audit_log.csv`) live but
deliberately **without** an Extract Setup tile — industry best
practice (GitHub / Stripe / Slack / Notion / Atlassian) parks
audit data behind an admin / diagnostics doorway. The operator-
facing surface relocates to the Sys Admin page when Segment 16A
ships; the route + service + 13 tests stay live in the meantime.

**No lifecycle gate.** The card renders identically in every
session state. Extraction is read-only and useful at every
state — `draft` (sanity-check the configured artefacts),
`validated`, `ready` (mid-flight responses snapshot), `closed`
(final dataset).

**Filenames** follow `{code}_{kind}.csv` (e.g.
`CS101_reviewers.csv`) via `app/services/extracts/__init__.py::filename`.

**Out of scope for this card.** The zip-all bundle stream remains
inert. Excel-format export was never an MVP item. The audit-log
tile relocates to Sys Admin in Segment 16A.

### 3. Danger Zone card (bottom-right)

The Danger Zone card (Delete Data + Delete Session) lived on
Session Home through 2026-05-21, moved to the Edit Session
Details page on 2026-05-22 (commit b490825), and **returned to
Session Home in Segment 18R Item 4** when the Edit page retired.
It now occupies the bottom-right of Home's `.bottom-grid`,
paired with Quick Setup in the bottom-left (`#danger-zone`).

The card's contents and behaviour are unchanged:

- **Delete Data** — wipes all reviewer responses while preserving
  setup. Confirmation checkbox (`required`) + Destructive button.
  POSTs to `/operator/sessions/{id}/delete-data`. **Locked while
  Activated** on the same terms as Delete Session (below): confirm
  checkbox `disabled`, a "Data deletion is locked while status is
  Activated" note, and the `_require_editable` gate on
  `/delete-data`. Reviewer responses only exist once the session is
  Activated, so deleting them is a pause-first workflow — Pause via
  the Workflow card, delete the data (the revert preserves the
  `Response` rows), then re-activate.
- **Delete Session** — removes the session entirely. Confirmation
  checkbox (`required`) + Destructive button. **Visible-but-disabled
  while Activated**: the button and confirm checkbox carry the
  `disabled` attribute, with an explanatory note ("Pause the
  session first to enable deletion."). The server-side lifecycle
  gate (`_require_editable`) in `/delete` is the source of truth —
  a direct POST while Activated still 4xxs. Visible greyed-out so
  the operator always sees the affordance and the path forward
  (Pause via the Workflow card first, then delete).

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

**Segment 18R Item 4 consolidated the session config display
*and* edit onto Session Home.** The standalone Edit page was
retired; this full-width card (`#session-config`) carries every
config field in an in-place **display ↔ edit swap**. The card
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
  (`views.build_offset_display_rows`) — the Schedule-timeline
  card that formerly sat below Session Details was retired, its
  resolved fire-moments now shown inline here.

Below the field block, a half-width `.bottom-grid` pair of
**sub-cards**:

- **Owners** (`#config-owners-card`, Segment 16B PR 2) —
  display mode is a read-only Email / Name / Role / Added table;
  edit mode gains an Action (Remove) column plus an Add-owner
  typeahead over the workspace operator allowlist. Owner
  add/remove POST to `/owners/add` + `/owners/{user_id}/remove`
  and redirect back to Home in edit mode
  (`?editing=1#config-owners-card`); `owners_error` surfaces
  inline. (Owners moved onto Home with the config consolidation —
  it no longer lives only on a separate Edit sub-page.)
- **User interface settings** (`#config-ui-settings-card`,
  PR #1705) — two checkboxes: **Relationships tab and page**
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
- `GET /operator/sessions/{id}/edit` survives only as a **301
  redirect** to `…?editing=1#session-config` for stale bookmarks.

Lifecycle state is shown in the chrome status strip and (on Home)
in the Workflow card's body copy when relevant.

### 5. Quick Setup card (bottom-left)

The Quick Setup card sits in the bottom-left of Home's
`.bottom-grid`, paired with the Danger Zone card on the right
(18R Item 4 — relocated from the old right column). It renders
the real four-slot shape, all wired: Reviewers / Reviewees
(Segment 11J), Relationships (Segment 15D PR 7c), Settings
(Segment 12A-3 PR 4), plus a conditional Observers slot when
`observers_enabled` (W12). The functional spec is
`spec/quick_setup_card_spec.md`.

Layout: a 2-column grid (post-15D cleanup polish #768) — Reviewers
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
  session is Activated. Pause the session to re-enable bulk
  setup." The Lock / Unlock button stays visible — unlocking
  is purely visual; the importer rejects mutating submits at
  the service layer (`_require_editable`) and the rejection
  surfaces inline as a scoped `banner-error` carrying "Pause
  the session before applying setup changes" copy. The
  operator's actual path forward is Pause, but the cosmetic
  unlock affordance stays consistent across states.

## Placeholder cards

The shared placeholder pattern is no longer used on Session Home —
both Quick Setup and Extract Data have graduated. The pattern
remains documented here for any future placeholder card on any
page.

- **Macro:** `app/web/templates/operator/partials/_placeholder_card.html`,
  exporting `placeholder_card(id, title, description,
  button_label, button_tooltip)`.
- **Class:** `body.ui-v2 .card.placeholder` — `bg-muted`
  background, `text-muted` heading, `text-secondary` body,
  `not-allowed` cursor.

The visual signal *"this is a placeholder, not a working
action"* is uniform across every instance. Per-card state
distinctions live in the body copy, not in opacity flips that
would desynchronise sibling placeholders. A future placeholder
card on any page reuses the same macro without further design
work.

Cards that have graduated out of the placeholder pattern:

- **Quick Setup** graduated in Segment 11H — now ships as a full
  five-slot card (`_quick_setup_card.html`) with every slot wired
  (Reviewers / Reviewees in 11J, Relationships in 15D PR 7c,
  Settings in 12A-3 PR 4, Observers W12 PR #1754; Observers slot
  conditional on `observers_enabled`).
- **Extract Data** graduated across the 12A landings — now ships
  four always-present tiles plus a conditional Observers tile plus
  a Zip-all bundle footer (`_extract_data_card.html`). See §2
  above for the tile table.
- **Rule Based Assignment** (on the Assignments page, not Home)
  graduated across Segments 13A → 13A-1 — now ships as a wired
  card via `_rule_based_card.html` with a live RuleSet dropdown
  and a Generate submit. See `spec/assignments.md`.

## Lifecycle behavior summary

| State (enum / display) | Workflow card | Quick Setup | Extract Data |
|---|---|---|---|
| `draft` / Draft, rosters empty | State 1: "Session not fully set up…" — setup-completion checklist in right column; no buttons rendered | Live (up to five slots, Observers conditional; default-locked) | Live (4–5 tiles, Observers conditional; empty-count tiles grey their Download button) |
| `draft` / Draft, rosters populated, pre-generate | State 2: Prepare session live (Primary; runs Generate + Validate in sequence) | Live (up to five slots, Observers conditional; default-locked) | Live (4–5 tiles, Observers conditional) |
| `draft` / Draft, validated_just_ran with errors | State 3: Prepare session re-runnable (Primary); right column carries validation pill row + per-issue list | Live (up to five slots, Observers conditional; default-locked) | Live (4–5 tiles, Observers conditional) |
| `validated` / Validated | States 4 / 4W / 4Err / 5 / 6: Activate session live (Primary; 4W detours through `/validate?activate=1`); Prepare session re-runnable (Secondary); Revert to draft live (Secondary); Create / Send invites surface based on invitation state | Live (up to five slots, Observers conditional; default-locked) | Live (4–5 tiles, Observers conditional) |
| `ready` / Activated | States 7 / 8 / 9: Create invites / Send invites / Send reminders forward stages (whichever is next renders Primary); Close session + Release responses live (Secondary); Revert to draft live (Secondary, "Pause") | Live but body-greyed (toggle still visible; submits rejected at the service layer with a "Pause first" banner) | Live (4–5 tiles, Observers conditional; identical rendering across lifecycle) |
| `expired` / Closed | State 10: Release responses (or Stop releasing when the window's open) · Archive session (Danger); Revert to draft live (Secondary, reopens for editing) | Live but body-greyed | Live |
| `archived` / Archived | No buttons rendered (the Workflow card surfaces no actions on archived sessions) | Body-greyed | Live |

The **Extract Data** column above describes the Extract Setup
card as it now renders on the **Extract data** Operations tab —
it relocated off Session Home in 18R Item 4 (see §2); its
per-state rendering is unchanged.

The **Danger Zone** card (Delete Data + Delete Session) returned
to Home's bottom-right in 18R Item 4 (see §3). Its per-state
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
  `accent-blue` border; height grows to fit content. The standard
  body / confirm / buttons stack handles every state except
  Activated, which uses an inline two-section layout. Implement as
  a single block in the template that switches body / confirm /
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
- The Pause action (returning `ready` → `draft`) reuses
  `lifecycle.revert_session_to_draft`; the validated → draft
  "Revert to draft" supporting button reuses
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

## Implementation history

Segment 11B shipped this spec in seven slices:

| PR | Slice | Outcome |
|---|---|---|
| #380 (PR B) | Contextual primary action card (initial shape) | Replaced Run Session + Validation summary cards |
| #381 (PR A) | Lifecycle display mapping (`ready` → "Activated") | New `lifecycle_display.py` + Jinja filter |
| #382 (PR C) | Extract Data card | Promoted from CTA to its own placeholder card |
| #383 (PR D) | Quick Setup disabled in ready + Danger Zone visible-disabled | Two visual changes, no behaviour change beyond the Delete-Session UI |
| #384 (PR E) | Stale `.pill-lifecycle-closed` cleanup | CSS-only |
| #385 / #386 / #387 / #388 | Placeholder card unification | Quick Setup + Extract Data + Rule Based Assignment now share `.card.placeholder` + `placeholder_card` macro |
| #390 / #391 / #392 / #393 | Workflow card refinements | Constant title + bottom button row + sentence-case button copy + state-conditional trims + confirm above buttons + 200px min-height + blue border + Title Case heading |
