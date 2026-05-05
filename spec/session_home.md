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

### Left column — running the session

The operator's working column. Stack of cards, top to bottom:

1. **Next Action card.**
2. **Quick Setup card.** *(placeholder until full implementation lands)*
3. **Extract Data card.** *(placeholder until Segment 12 lands real extraction)*

### Right column — metadata and danger

1. **Session Details card** (top).
2. **Danger Zone card** (bottom).

## Cards

### 1. Next Action card (left column, top)

The page's center of gravity. Shows the single lifecycle-advancing
action appropriate to the session's current state, plus supporting
context that helps the operator decide whether to take it.

**Frame.** The card frame is constant across all lifecycle states:

- H2 title is the literal string **"Next Action"** (constant —
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

**Contents by lifecycle state:**

| State / trigger | Body | Primary | Supporting (Secondary) |
|---|---|---|---|
| **Empty draft** — `is_draft` AND any of reviewers / reviewees / assignments has zero rows | "Session not fully set up. Make sure that reviewers, reviewees, and assignments have been set up before continuing." | — *(none)* | — *(none)* |
| **Draft, pre-validation** — `is_draft`, rosters populated, no `?validated=1` yet | "Run validation to surface errors and warnings before activating. Validation never mutates session data." | **Validate Setup** | See validation details |
| **Draft, validation just failed** — `is_draft` AND `validation_summary` populated (i.e. operator clicked Validate Setup but the report didn't pass) | "Validation didn't pass." headline + a pill row (`pill-error` / `pill-empty` / `pill-count` for error / warning / info counts) + "Resolve the errors and re-run validation before activating." | **Validate Setup** | See validation details |
| **Validated (no errors)** — `is_validated` AND `can_activate` | "The session setup data has successfully validated. Preview the reviewer surface to make sure that it conforms to your requirements before activating." (+ optional `acknowledge_warnings` checkbox in the body when `needs_acknowledge`) | **Activate Session** | See validation details · See previews · Revert to draft |
| **Validated (errors)** — `is_validated` AND not `can_activate` | "Validation shows that there are error(s). Resolve them and re-run validation before activating." | **See validation details** | Revert to draft |
| **Activated** — `is_ready` | Two sections split by `<hr class="next-action-divider">`. **§1 body:** "Session is currently activated. Reviewers can access forms and save responses. Don't forget to generate and send out emails to notify the reviewers." **§2 body:** "Pausing returns the session to draft and stops reviewers from submitting new responses. Existing responses will be preserved." | **§1:** Manage invitations · **§2:** Pause Session (with `.next-action-confirm` carrying "Yes, pause [Session name] and return to draft.") | **§1:** Monitor responses |

Notes:

- **Empty-draft short-circuit.** The card surfaces a clear
  "fill the rosters first" instruction rather than sending the
  operator to Validate Setup, where every error would amount to
  the same gap. The operator's path forward is the chrome top-nav
  Manage links (Reviewers / Reviewees / Assignments), which stay
  reachable while this state shows.
- **Manage invitations promoted to Primary in `ready`.** During
  the running session, inviting reviewers is the day-to-day
  "doing things" action; Pause is the wind-down concern, separated
  out into its own section so its consequences read explicitly.
- **No "See previews" in `ready`.** Operators monitor live
  responses while Activated; previewing is the validation-time
  affordance.
- **No status pills in body** (other than the validation-failure
  count row above). Earlier drafts surfaced a "Setup validated"
  pill plus warning / info counts; the current spec drops them in
  favour of plain prose. Lifecycle and per-entity state belong in
  the chrome status strip, not the card body.
- **Pause confirmation checkbox copy:** "Yes, pause [Session
  name] and return to draft." (lowercase "draft" — running
  prose).
- **Reserved states (Expired, Archived).** Not yet in scope.
  Expected treatments:
  - **Expired** likely gets an Extract Data primary action with
    "Deadline has passed" prominent.
  - **Archived** likely renders the card empty or with a
    "Restore" affordance.

### 2. Quick Setup card (left column, middle)

Existing Quick Setup placeholder until its full spec lands
(`spec/quick_setup_card_spec.md`). Renders via the canonical
`placeholder_card` macro (see "Placeholder cards" below).

State-conditional copy only — the card frame is constant:

- **Draft / Validated:** "Bulk-populate reviewers, reviewees, and
  assignments from files or rules in one place."
- **Ready / Activated:** "Setup edits are paused while the
  session is Activated. Pause the session to re-enable bulk
  setup."

The disabled "Set up" placeholder button carries a tooltip
pointing at the quick-setup spec.

### 3. Extract Data card (left column, bottom)

Lets the operator pull response data out of the session for
downstream use. Renders via the same `placeholder_card` macro
as Quick Setup (see "Placeholder cards" below) until Segment 12
ships real extraction.

State-conditional copy:

- **Draft / Validated:** "No responses to extract yet. Available
  once the session is Activated and responses have been
  received."
- **Activated:** "Extract reviewer responses for analysis or
  reporting."

The disabled "Extract" placeholder button carries a tooltip
pointing at Segment 12.

**Out of scope for this card** (deferred to Segment 12): real
extraction, format selector (CSV / JSON / etc.), terse summary of
what would be extracted, complex filtering, scheduled exports,
partial-extraction UIs.

### 4. Session Details card (right column, top)

Reference metadata with an edit affordance. Read-mostly, but the
operator does occasionally need to update session metadata
(revising the deadline, fixing a typo in the description, etc.),
and Home is the natural place for that since it's where session
identity lives.

**Contents:**

- Deadline.
- Created by.
- Description (full text, may be long).
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

The previously-rendered duplicate `Status:` pill on this card
was retired in PR #375; lifecycle state is shown in the chrome
status strip and (on Home) in the Next Action card's body copy
when relevant.

### 5. Danger Zone card (right column, bottom)

Destructive cleanup actions. Visually distinct (`accent-amber-dark`
border, H2 in the same warning brown).

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
  via the Next Action card first, then delete).

Both actions follow the inline-confirmation pattern: the operator
ticks the checkbox to enable the destructive submit.

## Placeholder cards

Quick Setup and Extract Data on Home, plus Rule Based Assignment
on the Assignments page, all render via a single shared Jinja
macro and a single canonical CSS class:

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

## Lifecycle behavior summary

| State (enum / display) | Next Action card | Quick Setup | Extract Data | Danger Zone Delete Session |
|---|---|---|---|---|
| `draft` / Draft, rosters empty | "Session not fully set up…" — no buttons | Active (placeholder) | Greyed (placeholder) | Active |
| `draft` / Draft, rosters populated | Primary: Validate Setup | Active (placeholder) | Greyed (placeholder) | Active |
| `validated` / Validated | Primary: Activate Session (or See validation details on errors) | Active (placeholder) | Greyed (placeholder) | Active |
| `ready` / Activated | Two sections: Manage invitations (Primary) + Monitor responses; `<hr>`; Pause Session (Primary, with confirm) | Greyed (placeholder) | Active (placeholder, button still disabled until Segment 12) | Visible-but-disabled |

Reserved states (Expired, Archived) not yet in scope. When
introduced, this table extends with their treatment.

**Disabled treatment on Home is plain greying-out, not yellow
lock cards.** The Next Action card carries any explanatory
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

- The Next Action card's content is state-conditional. The card
  frame's constants are the H2 ("Next Action") and the
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
| #390 / #391 / #392 / #393 | Next Action card refinements | Constant title + bottom button row + sentence-case button copy + state-conditional trims + confirm above buttons + 200px min-height + blue border + Title Case heading |
