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
display layer instead: a single enum-to-label mapping in the
codebase, used by every UI surface that renders a lifecycle state.

**What goes through the display mapping** (anything an operator
reads): the status pill, the page header lifecycle badge, prose in
UI copy ("This session is currently Activated"), button labels and
confirmations, help text.

**What stays as the enum** (anything a machine or developer reads):
URL slugs, query params, API responses, log messages, database
values, code identifiers, existing CSS class names.

**Stale references to "closed".** Older docs and CSS (e.g.
`.pill-lifecycle-closed`) reference a `closed` state that doesn't
exist in the canonical enum. Slated for cleanup; `expired` and
`archived` are the post-life states.

## Page identity

| Field | Value |
|---|---|
| Page name | Session Home |
| Template | `session_detail.html` |
| URL | `GET /operator/sessions/{id}` |
| Grouping | Per Session Control Panel |

## Layout

Two-column body below the chrome and status strip.

### Left column — running the session

The operator's working column. Stack of cards, top to bottom:

1. **Contextual primary action card.**
2. **Quick Setup card.**
3. **Extract Data card.**

### Right column — metadata and danger

1. **Session Details card** (top).
2. **Danger Zone card** (bottom).

## Cards

### 1. Contextual primary action card (left column, top)

The page's center of gravity. Shows the single lifecycle-advancing action
appropriate to the session's current state, plus supporting context that
helps the operator decide whether to take it.

**Contents by lifecycle state:**

| State (enum / display) | Primary button | Supporting links | Readiness summary |
|---|---|---|---|
| `draft` / Draft | **Validate Setup** | View validation detail (Operations → Validate) | Setup state badges |
| `validated` / Validated | **Activate Session** | View validation detail · Preview reviewer surface · Revert to Draft | Setup state badges + "Setup validated" confirmation |
| `ready` / Activated | **Pause Session** (returns to Draft) | Manage invitations · Monitor responses · Preview reviewer surface | Operations pointers (terse status with links) |

The primary button uses primary-button styling per the visual style spec.
Supporting links use link styling (no buttons), to keep visual hierarchy
clear: one action stands out; everything else is reference.

The readiness summary varies by state:

- In Draft / Validated: the five Setup entity counts as badges
  (`Reviewers ✓ · Reviewees ✓ · Assignments ✓ · Instruments ✓ ·
  Email Template ⚠`). Visual cue helps the operator predict whether
  Validate will succeed.
- In Activated: terse operations pointers, e.g. "12 invitations sent ·
  4 responses received · 2 reminders due", with each item linking to
  the relevant Operations page.

**Pause behavior.** "Pause Session" returns the session to Draft
(enum `draft`), unlocking setup for modification. This is the
canonical recovery path when the operator notices a setup problem
after activation. The button's confirmation should make the
consequence clear: "Pausing returns the session to Draft. Reviewers
will not be able to access forms while paused. Existing responses
are preserved." Pausing does not destroy collected data; it just
suspends reviewer access and re-enables setup edits.

The Validated → Draft "Revert to Draft" link is the analogous
action when the operator catches a problem before activation. Same
mechanism (return to Draft); different framing because no responses
exist yet.

**Reserved states (Expired, Archived).** Not yet in scope. When
introduced:

- **Expired** likely gets an Extract Data primary action, with the
  card surfacing "Deadline has passed" prominently. Reviewers lose
  write access automatically.
- **Archived** likely renders the card empty or with a "Restore"
  affordance, depending on whether archived sessions are
  re-activatable.

Specific treatment to be defined when those states ship.

### 2. Quick Setup card (left column, middle)

Existing Quick Setup card per its own spec
(`spec/quick_setup_card_spec.md`). Always visible in Draft and
Validated.

**Disabled treatment when session is Activated:** the card renders
disabled with simple greyed-out styling — **no yellow lock card**.
The yellow lock card pattern is reserved for surfaces where the lock
itself needs explanation (e.g., the Setup tabs, where the operator
might wonder why they can't edit). On Home, the contextual primary
action card sits directly above Quick Setup and already communicates
the session's state and what actions are available; a yellow lock
card on Quick Setup would duplicate that messaging redundantly.

If the operator needs to mutate setup on a running session, the
contextual primary action card surfaces the path: "Pause Session"
returns the session to Draft, at which point Quick Setup re-enables.

No changes to Quick Setup's behavior on Draft and Validated states.

### 3. Extract Data card (left column, bottom)

Lets the operator pull response data out of the session for
downstream use.

**State-conditional behavior:**

- **Draft / Validated:** Card renders disabled with explanatory text
  ("No responses to extract yet. Available once the session is
  Activated and responses have been received.") Greyed out per the
  disabled-state pattern.
- **Activated:** Card renders enabled. Operator can extract responses
  while the session is running (useful for partial pulls, checking
  data shape, intermediate analysis).
- **Reserved states (Expired, Archived)** when introduced will
  likely render this card prominently — Expired in particular is the
  natural state where extraction matters most. Specific treatment to
  be defined when those states ship.

**Card contents:**

- One-line description ("Extract reviewer responses for analysis or
  reporting.")
- Extract action button.
- Format selector (CSV, JSON, etc. — per existing extraction
  capabilities).
- Optional: terse summary of what would be extracted ("104 responses
  across 8 reviewers, 13 reviewees").

**Out of scope for this card:** complex filtering, scheduled exports,
partial-extraction UIs. If extraction grows beyond a button + format
picker, it spawns a sub-page or Operations page; the card on Home
stays the launch point.

### 4. Session Details card (right column, top)

Reference metadata with an edit affordance. Read-mostly, but the
operator does occasionally need to update session metadata (revising
the deadline, fixing a typo in the description, etc.), and Home is
the natural place for that since it's where session identity lives.

**Contents:**

- Deadline.
- Created by.
- Description (full text, may be long).
- **Edit button** (secondary styling), top-right of the card. Opens
  `session_edit.html` as a sub-page of Home for full metadata
  editing.

**Edit affordance behavior:**

- Available in Draft and Validated states without restriction.
- In Activated state, the Edit button remains visible and clickable,
  but the edit form itself may restrict which fields are mutable
  (e.g., changing the deadline mid-run is allowed; changing the
  session name might not be). Field-level restrictions are the edit
  page's concern; Home just offers the launch point.
- No inline editing on the card itself. Edit always opens the
  sub-page. This keeps Home's right column read-only-feeling and
  avoids a mid-card form that competes with the action work in the
  left column.

**Removed from current implementation:** the duplicate `Status:
DRAFT` badge. Lifecycle state is shown in the page header / status
strip; no need to repeat it here.

### 5. Danger Zone card (right column, bottom)

Destructive cleanup actions. Visually distinct (per existing
implementation: amber/red border and title).

**Contents:**

- **Delete Data** — wipes all reviewer responses while preserving
  setup. Confirmation checkbox + button. Available when responses
  exist; disabled otherwise.
- **Delete Session** — removes the session entirely. Confirmation
  checkbox + button. Disabled while session is Activated (no lock
  card; the contextual primary action card above explains the
  session's state and the path forward — Pause Session first, then
  delete is available).

Both actions follow the inline-confirmation pattern per the visual style
spec: the primary button is a normal secondary button until the operator
checks the confirmation box, at which point it activates with destructive
styling.

## Lifecycle behavior summary

| State (enum / display) | Primary action card | Quick Setup | Extract Data | Danger Zone Delete Session |
|---|---|---|---|---|
| `draft` / Draft | Validate Setup | Active | Disabled | Active |
| `validated` / Validated | Activate Session | Active | Disabled | Active |
| `ready` / Activated | Pause Session (returns to Draft) | Disabled (greyed) | Active | Disabled (greyed) |

Reserved states (Expired, Archived) not yet in scope. When
introduced, this table extends with their treatment.

**Disabled treatment on Home is plain greying-out, not yellow lock
cards.** The contextual primary action card carries any explanatory
messaging the operator needs about the session's current state and
what's locked. Yellow lock cards remain in use elsewhere in the app
(the Setup tabs, for instance) where there's no adjacent action card
doing the explanatory job.

Extract Data uses straightforward disabled styling regardless: its
disabled state is informational ("nothing to extract yet"), not
lifecycle-locked, and would never warrant a lock card even outside
Home.

## Out of scope for this page

- **Per-entity setup work.** Belongs on the five Setup pages.
- **Operations work** (invitations, monitoring, validation detail,
  reviewer experience preview). Belongs on the Operations pages. Home
  surfaces pointers and links, not the work itself.
- **Live operational dashboards.** Home shows terse pointers ("12
  invitations sent"), not live updating widgets. Operations pages own
  the detail.
- **Multi-session views.** Home is single-session; cross-session
  navigation goes through the Overview.

## Doc impact

UI concept doc:

- The description of Home's body updates to reflect the two-column
  layout and the contextual primary action pattern.
- Lifecycle state listing should reflect the canonical enum:
  `draft`, `validated`, `ready`, plus reserved `expired` and
  `archived`. Note the `ready` → "Activated" display divergence.
- Stale references to `closed` should be cleaned up.

`spec/operator_ui_concept.md`:

- Page-level layout contract for `session_detail.html` updates per
  this spec.
- The current "Run Session" four-button card pattern is retired.

Stale CSS / code:

- The `.pill-lifecycle-closed` rule (and any other `closed`-state
  references) should be removed or repurposed for `expired` /
  `archived`.

## Implementation pointers

- The contextual primary action card's content is state-conditional
  but the card's *shape* is constant. Implement as a single component
  that takes lifecycle state as input and renders the appropriate
  button + supporting links + readiness summary.
- Reuse the existing primary/secondary button styling from the
  visual style spec; do not introduce new button variants for this
  page.
- The Pause action (returning `ready` → `draft`) should reuse
  whatever state-machine code path already implements that
  transition. The button is a UI affordance over an existing
  capability.
- **Lifecycle display mapping.** A single function or constant in
  the codebase maps enum values to display labels (`ready` →
  "Activated", others identity). Every UI surface that renders a
  lifecycle state — status pill, page header badge, prose, button
  labels — goes through this mapping. No template hardcodes display
  strings. URL slugs, API responses, log messages, and CSS class
  names continue to use enum values.
- The two-column layout should be responsive only insofar as the
  app is generally desktop-first. Below some narrow viewport
  threshold the columns can stack (right column below left); no
  need to over-engineer this.
