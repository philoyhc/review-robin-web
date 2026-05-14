# Session Home page — functional spec

The session-scoped home page (Control Panel) for Review Robin. Lands the
operator in a session, surfaces the contextually appropriate next action,
and provides launch points for setup, operations, and metadata.

## Lifecycle state vocabulary

The session lifecycle has three live states and two reserved
(future) states. Internal enum values and user-facing display
labels differ for one of them; this spec uses enum values when
referring to code behavior and display labels when referring to
UI copy.

| Enum | Display label | Status |
|---|---|---|
| `draft` | Draft | live |
| `validated` | Validated | live |
| `ready` | **Activated** | live |
| `expired` | Expired | reserved (Segment 9.3+; deadline has passed) |
| `archived` | Archived | reserved (Segment 12+) |

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

Two-column body below the chrome and status strip.

### Page-card layout (workflow card + two columns)

```
┌────────────── Workflow ──────────────────────────────────────┐
│  full-width, just below the chrome                           │
└──────────────────────────────────────────────────────────────┘
┌── Session Details ───────┐  ┌── Quick Setup ───────────┐
│   metadata + Edit        │  │   scaffolded bulk        │
└──────────────────────────┘  └──────────────────────────┘
┌── Danger Zone ───────────┐  ┌── Extract Data ──────────┐
│   destructive cleanup    │  │   responses extract      │
└──────────────────────────┘  └──────────────────────────┘
```

The Workflow card sits full-width at the top of the page-card
region, just below the chrome (same `next_action_card.html`
partial the Operations-row pages render). Underneath it, the
remaining four cards lay out in two **independent flex columns**
(`.bottom-left` flex-column wrappers); each column flows
independently so Extract Data sits directly below Quick Setup
with the normal inter-card gap regardless of how tall Danger
Zone grows in the other column.

DOM source order = mobile-collapse order:
**Workflow → Session Details → Danger Zone → Quick Setup →
Extract Data**. Below ~800px viewport width the columns collapse
into a single stacked column in that same order.

Quick Setup + Extract Data live in the right column so the
destructive-cleanup column (Danger Zone) stays on the left and
the bulk-setup affordances cluster on the right. Extract Data
anchors the bottom of the right column — operators reach for it
once responses are in, which is late in the session lifecycle.

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

## Cards

### 1. Workflow card (left column, top)

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
(States 1 / 1A / 2 / 3 / 4A / 4B / 5 / 6 / 7 / 8), the uniform
seven-stage stepper, the **Activate session** super-button (which
collapses Generate → Validate → Activate into a single click with
per-step rollback and a warnings-detour to `/validate?activate=1`),
and the right-column state-aware status / errors aside. Session
Home renders the same partial that every Operations-row page
renders; nothing on Home overrides the card's per-state behaviour.

Notes specific to Session Home:

- **Empty-draft short-circuit.** The card surfaces a clear
  "fill the rosters first" instruction rather than sending the
  operator to Validate, where every error would amount to
  the same gap. The operator's path forward is the chrome top-nav
  Manage links (Reviewers / Reviewees / Assignments), which stay
  reachable while this state shows.
- **Workflow stepper in `ready`.** The forward stages (Create
  invites · Send invites · Send reminders) advance through States
  6 → 7 → 8 as Invitation rows are created and sent; whichever
  stage is the next forward action renders Primary, the others
  Secondary. Revert to draft is always Secondary when live — the
  stepper never promotes it to Primary. The pre-stepper Pause
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
  - **Expired** likely gets an Extract Data primary action with
    "Deadline has passed" prominent.
  - **Archived** likely renders the card empty or with a
    "Restore" affordance.

### 2. Extract Data card (left column, middle)

Lets the operator pull response data out of the session for
downstream use. Five live per-entity download tiles plus a
single zip-bundle footer:

| Tile | DOM order | Wired by |
|---|---|---|
| Reviewers | left col, top | 12A-1 PR 2 (#717) |
| Settings  | right col, top | 12A-1 PR 1 (#713) |
| Reviewees | left col, middle | 12A-1 PR 2 (#717) |
| Responses | right col, middle | 12A-1 PR 4 (#721) |
| Relationships | left col, bottom | 12A-3 PR 1 (#779) |
| Download all (zip) | footer | Inert — future bundle |

The post-15D + post-12A-3 layout settled in 12A-3 PR 2 (#780)
which also retired the Assignments tile end-to-end (route +
service + audit event) since assignments are a materialised
derivative post-15D and the operator's preferred round-trip is
Settings ↔ Relationships ↔ Reviewers / Reviewees.

**Grey-out when empty.** The Reviewers / Reviewees /
Relationships / Responses tiles grey out their Download button
when the underlying count is `0` (post-12A-3 polish #781). The
Settings tile is always clickable — a session always has
settings to extract.

**No audit-log tile in Extract Data.** Segment 12B shipped the
audit-events CSV route (`GET /export/audit_log.csv`) live but
deliberately **without** an Extract Data tile — industry best
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

### 3. Danger Zone card (left column, bottom)

Destructive cleanup actions. Visually distinct (`accent-amber-dark`
border, H2 in the same warning brown).

**Description copy:** "Delete Data wipes every reviewer response while leaving session setup intact. Delete session removes the entire session and is locked while session is Activated."

**Contents:**

- **Delete Data** — wipes all reviewer responses while preserving
  setup. Confirmation checkbox + Destructive button.
- **Delete Session** — removes the session entirely. Confirmation
  checkbox + Destructive button. **Visible-but-disabled while
  Activated**: form, button, and confirm checkbox all render but
  carry the `disabled` attribute, with an explanatory note ("Pause
  the session first to enable deletion."). The server-side
  lifecycle gate in `/delete` is the source of truth — a direct
  POST while Activated still 4xxs. Visible greyed-out so the
  operator always sees the affordance and the path forward (Pause
  via the Workflow card first, then delete).

Both actions follow the inline-confirmation pattern: the operator
ticks the checkbox to enable the destructive submit.

### 4. Session Details card (right column, top)

Reference metadata with an edit affordance. Read-mostly, but the
operator does occasionally need to update session metadata
(revising the deadline, fixing a typo in the description, etc.),
and Home is the natural place for that since it's where session
identity lives.

**Contents.** Two-column meta row above a single-column Name + Description block:

- **Column 1 (all rendered as count pills):** Created by · Created · Last Modified. Created and Last Modified render the full ISO 8601 timestamp (date + time), matching Deadline's grain.
- **Column 2:** Deadline (count pill with the full ISO 8601 timestamp, or `pill-empty` "Not set" when null) · Code (rendered in `<code>`) · Help contact (plain text, "—" when null).
- **Below the meta row:** full-width Name and Description rows.
- **Edit button** (Secondary styling), bottom-right of the card.
  Opens `session_edit.html` as a sub-page of Home for full
  metadata editing.

**Edit affordance behavior:**

- Available in Draft and Validated states without restriction.
- In Activated state, the Edit button remains visible and
  clickable, but the edit form itself may restrict which fields
  are mutable. Field-level restrictions are the edit page's
  concern; Home just offers the launch point.
- No inline editing on the card itself. Edit always opens the
  sub-page. Keeps Home's right column read-only-feeling and
  avoids a mid-card form that competes with the action work in
  the left column.
- The Edit sub-page also hosts the **Owners** card (Segment
  16B PR 2) — current co-owners + an Add-owner typeahead
  picker over the workspace operator allowlist. The card
  doesn't render on Session Home itself: per-session
  permission management is rare enough that surfacing it on
  Home would steal real estate from the next-action work,
  and the Edit sub-page is already the canonical landing
  page for session-identity changes.

The previously-rendered duplicate `Status:` pill on this card
was retired in PR #375; lifecycle state is shown in the chrome
status strip and (on Home) in the Workflow card's body copy
when relevant.

### 5. Quick Setup card (right column, bottom)

The Quick Setup card on Session Home renders the real four-slot
shape, all wired: Reviewers / Reviewees (Segment 11J),
Relationships (Segment 15D PR 7c), Settings (Segment 12A-3 PR 4).
The functional spec is `spec/quick_setup_card_spec.md`.

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
  four-slot card (`_quick_setup_card.html`) with every slot wired
  (Reviewers / Reviewees in 11J, Relationships in 15D PR 7c,
  Settings in 12A-3 PR 4).
- **Extract Data** graduated across the 12A landings — now ships
  five live tiles plus an inert zip-all bundle footer
  (`_extract_data_card.html`). See §2 above for the tile table.
- **Rule Based Assignment** (on the Assignments page, not Home)
  graduated across Segments 13A → 13A-1 — now ships as a wired
  card via `_rule_based_card.html` with a live RuleSet dropdown
  and a Generate submit. See `spec/rule_based_assignment.md`.

## Lifecycle behavior summary

| State (enum / display) | Workflow card | Quick Setup | Extract Data | Danger Zone Delete Session |
|---|---|---|---|---|
| `draft` / Draft, rosters empty | State 1: "Session not fully set up…" — setup-completion checklist in right column; every stepper slot inert | Live (all four slots wired; default-locked) | Live (5 tiles; empty-count tiles grey their Download button) | Active |
| `draft` / Draft, rosters populated, pre-generate | State 1A: Activate session live (Primary; super-button runs Generate → Validate → Activate) | Live (all four slots wired; default-locked) | Live (5 tiles) | Active |
| `draft` / Draft, generated | States 2 / 3: Activate session live (Primary); right column carries validation pill row + per-issue list when State 3 | Live (all four slots wired; default-locked) | Live (5 tiles) | Active |
| `validated` / Validated | States 4A / 4B / 5: Activate session live (Primary; 4B detours through `/validate?activate=1`); Revert to draft live (Secondary) | Live (all four slots wired; default-locked) | Live (5 tiles) | Active |
| `ready` / Activated | States 6 / 7 / 8: Create invites · Send invites · Send reminders forward stages (whichever is next renders Primary); Revert to draft live (Secondary, "Pause") | Live but body-greyed (toggle still visible; submits rejected at the service layer with a "Pause first" banner) | Live (5 tiles; identical rendering across lifecycle) | Visible-but-disabled |

Reserved states (Expired, Archived) not yet in scope. When
introduced, this table extends with their treatment.

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
