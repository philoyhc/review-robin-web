# Segment 18A — Sessions lobby enhancements

> **Stub. Sketch-level scope only.** Detailed PR breakdowns get
> drafted when this segment is picked up.
>
> **Consolidated 2026-05-15** from the former `18A — Session
> cloning` and `18B — Session tagging + archiving` stubs (both
> created 2026-05-11 in the Stage 4 guide/ reorg) into a single
> Sessions-lobby segment. **Segment number 18B is retired**; 18C
> (Retention / deletion workflow) and 18D (Export / import
> update) keep their numbers.

## Goal

Turn the Sessions lobby (`/operator/sessions`) from a flat list
of every session the operator has ever touched into a surface
that scales — searchable, tidyable, and quick to spin a new
session off an old one. Three major items:

1. **Session cloning** — one-click "clone an existing session"
   as the starting point for a new one: carry the setup
   (reviewers, reviewees, relationships, instruments, RTDs,
   RuleSets, email-template overrides, settings) **without**
   responses, audit history, or session-runtime state.
2. **Session tagging / grouping** — free-form operator-chosen
   tags on each session (e.g. `2026-Q1`, `pilot`, `cohort-A`)
   surfaced on the lobby as filterable chips.
3. **Session archiving** — move closed / finalised sessions out
   of the default lobby view into an `archived` bucket: still
   readable, still exportable, just no longer in the operator's
   "what am I working on now?" surface. Uses the reserved
   `archived` lifecycle state.

## Why now

- `spec/operator_ui_concept.md` "Out of scope" §3 names **session
  duplication (sans response data)** and **session tagging /
  grouping** among the "adjacent capabilities likely to land
  sooner" — both compose cleanly with the Overview surface
  without forcing any Setup / Control / Operations redesign.
- **Archiving.** `spec/lifecycle.md` §44 already reserves
  `archived` as a real enum value: *"Reserved (Segment 12+,
  post-export retention). Not written by any current route."*
  The schema's ready; only the transition + UI are missing. This
  picks up where Segment 12B's framing left off (the archive
  transition was hinted at in the 12B retention scope but never
  landed — see `guide/archive/segment_12B_audit_retention.md`).
- **Cloning precedent.** 15C's "auto-copy operator library on
  session create" pattern is the natural precedent: per-session
  copies of library RTDs / RuleSets already exist as a category,
  so the cloning service is mostly "do what the operator-library
  auto-copy does, but sourced from a sibling session instead of
  the operator's library."
- **Tagging schema is pre-positioned.** The `session_tags` table
  lands inert in **Segment 13F PR 3** (additive, nullable, no
  backfill), awaiting this segment's light-up.
- `guide/codebase_assessment_11may.md` §22 marks **Session
  cloning** as ❌ not planned today; this segment gives it (and
  tagging / archiving) an owner.

## Scope (sketch)

### Sessions quality-of-life (small enhancements)

Standalone tidy-ups that don't need a full Part — landed
opportunistically as the segment opens:

- **Select-all checkbox** (Sessions lobby) — *shipped.* The
  select-row column's `<th>` header carries a select-all checkbox
  that toggles every row checkbox at once; inline JS keeps it in
  sync with the rows (checked / `indeterminate` / clear). See
  `spec/sessions_overview.md`.
- **Multi-paragraph session description** — *shipped.* The
  session description display — Session Home's Session Details
  card (`.session-detail-description`) and the reviewer-surface
  overview card (`.rs-session-description`) — carries
  `white-space: pre-line`, so the line + paragraph breaks the
  operator types in the `maxlength=2000` `<textarea>` survive on
  display instead of collapsing to whitespace. No input change,
  no new dependency. Richer formatting (markdown / WYSIWYG) stays
  deferred — see the rich-text note under Working notes.
- **Session Details card refresh** — *shipped.* The Session Home
  Session Details card drops its "Session Details" heading: the
  card `<h2>` is the session name (the session code trails it
  inline in body-text font), the description sits unlabelled
  directly below, and the metadata moves into a three-column
  labelled grid — Created by / Help contact · Created / Modified
  · Deadline / Timezone. See `spec/session_home.md`.

### Lobby action surface — inline row expander

**Current state (placeholders shipped).** The lobby carries a
two-card row above the table — a "Sessions lobby" stats card and
an "Actions" card (Add new / Duplicate / Duplicate settings only /
Tags / Archive / Delete) — plus a reveal-on-click "Tags" editor
card and the legacy Danger Zone delete card. The action buttons
are disabled placeholders; the Tags card is a UI-only stub. This
subsection specs the **interaction model** those placeholders are
heading toward.

**Problem.** When the operator selects a row far down a long
list, the fixed Actions / Tags cards at the top are scrolled out
of view — the selection and the controls that act on it are far
apart.

**Model — selection-anchored inline expander.** Instead of fixed
top-of-page cards, the action surface is an extra table row
injected directly **below the relevant selected row**, as a
single `<td colspan="N">` (N = every column, so it spans the full
table width). Exactly one expander row exists at a time, and its
contents depend on **how many rows are selected**:

- **Zero rows selected** — no expander row. The table is just
  the table.
- **Exactly one row selected** — a **single-session expander**
  appears directly under that row, hosting the actions that
  operate on one session: **Tags**, **Duplicate**, **Duplicate
  settings only**. The Tags editor (the comma-separated text box
  + Save / Cancel) opens inline within this expander. The
  expander also carries inline **edit boxes for the session's
  core fields — Name, Code, Deadline** — so the operator can
  rename / recode / re-deadline a session straight from the lobby
  without opening Session Home. These boxes back the existing
  Session Details edit path, so they inherit its lifecycle gating
  (editable in `draft` / `validated`; the existing edit-lock and
  response-loss rules apply) — when a session is past that point
  the boxes render read-only / disabled rather than absent, so
  the expander layout stays stable. Field-level validation
  (unique code, deadline shape) reuses the Session Details
  rules.
- **Two or more rows selected** — the single-session expander is
  removed and a **bulk expander** appears instead, anchored under
  the **last-selected row** (the most recently ticked checkbox).
  It hosts only the actions that operate on a set: **Archive**
  and **Delete** (Delete absorbs today's Danger Zone card,
  carrying its confirm checkbox into the expander), a **bulk
  tags** affordance, plus the two selection-management buttons
  below. Single-session actions (and the single-session
  Name / Code / Deadline edit boxes) are hidden — they have no
  unambiguous target across a set.
  - **Bulk tags — precise details TBD.** The intent is a
    set-wide tag operation; the open question is the operation
    *shape*. Candidates to settle at scoping: **add a tag to
    every selected session**, **remove a tag from every
    selected session**, or a fuller "show the union of tags
    across the selection, tick / untick to apply." Whichever
    shape lands, it goes through the same `session.tag_added` /
    `session.tag_removed` audit events as the single-session
    Tags editor, once per affected session.
- Dropping back from two selected rows to one swaps the bulk
  expander back to the single-session expander under the
  remaining row; clearing the selection removes the expander
  entirely.

**Re-anchoring when the selection changes.** The bulk expander
always sits under the **most-recently-ticked row that is still
selected**. The JS keeps the ticked rows in an ordered list (tick
order); the anchor is the last entry still selected. So:

- Un-ticking an **earlier** (non-anchor) row leaves the anchor —
  and the expander — exactly where it is; only the selection set
  shrinks.
- Un-ticking the **anchor row itself** re-anchors the expander to
  the new last entry — the next-most-recently-ticked row that is
  still selected — and the expander moves there.
- Either un-tick that drops the count to exactly one swaps to the
  single-session expander under the surviving row; down to zero
  removes the expander.

**Bulk-expander selection-management buttons.** The bulk expander
carries two buttons for trimming the selection without scrolling
back through the table:

- **Clear all selected** — un-ticks every selected row. The
  selection empties, so the expander disappears.
- **Clear all others** — un-ticks every selected row *except the
  anchor row*. One row remains selected, so the expander swaps to
  the single-session expander under it — a quick "I over-selected;
  just keep this one" path.

**Repurposing the Actions card.** Once the per-row expanders host
every session-scoped action, the standing **Actions card** above
the table no longer needs its button cluster. Rather than delete
it, repurpose it as the lobby's **search + create** strip:

- A **search box** — case-insensitive substring match against
  session name / code / tags, filtering the table rows. (This
  promotes the former Post-MVP "Lobby search bar" item into the
  segment proper.) Whether the filter is client-side over
  rendered rows or a server `?q=` round-trip is a scoping
  decision — client-side is consistent with the tag-filter chips
  and needs no route change while the lobby isn't paginated.
- The **"Add new" button** — the one genuinely global,
  non-session-scoped affordance — stays here alongside search.

So the transition is: action *buttons* migrate into the inline
expanders; the Actions card becomes the search-and-create card.

**Why this works.** Selection count is a clean discriminator:
one-vs-many maps exactly onto single-session-vs-bulk action
scope, so the expander never shows an action whose target is
ambiguous. Anchoring to the last-selected row keeps the controls
next to where the operator's attention just was.

Likely shape:

- Pure client-side, no schema, no server round-trip for the
  show/hide/relocate logic. The expander markup is rendered once
  as a hidden template fragment (or two — single + bulk) and the
  inline JS detaches it and re-inserts it as a `<tr>` after the
  anchor row when the selection changes.
- The JS tracks the most-recently-ticked checkbox to know the
  bulk expander's anchor; it extends (does not fight) the
  existing select-all / `indeterminate` sync script.
- Form semantics: the bulk expander's Archive / Delete still post
  the ticked `session_ids` (the table is already wrapped in the
  bulk `<form>`); the single-session expander's Duplicate / Tags
  act on the one selected `session_id`.
- Accessibility: the injected `<tr>` needs a sensible reading
  order and focus move (focus into the expander on appear);
  `colspan` row gets an `aria` label naming the anchor session.
- Decide at scoping: animation (none vs slide-down), and whether
  the expander row re-anchors live as the operator re-sorts the
  table.

Out of scope for this subsection: the actual cloning / tagging /
archiving / delete *behavior* — that is Parts 1-3 plus the
existing delete route. This is purely the placement / reveal
model for those actions' controls.

### Part 1 — Session cloning

**Goal.** A new `sessions.clone_session(db, source_session, *,
new_name, owner_user, mode, correlation_id) -> ReviewSession`
service helper that creates a fresh `draft` session and copies
setup-shape rows from `source_session`.

**Two clone modes** — the operator picks one at clone time:

- **Mode A — "Duplicate all except responses."** Copies the full
  setup: reviewers, reviewees, relationships, instruments (with
  RTD pointers cloned via the same library-clone mechanism 15C
  ships), `instrument_display_fields`,
  `instrument_response_fields`, `session_rule_sets`,
  `session_field_labels`, `email_template_overrides`,
  `responses_received_enabled`, `help_contact`. For re-running
  the same review with the same cohort.
- **Mode B — "Duplicate all except responses, reviewers,
  reviewees, relationships."** Copies the configuration shell
  only — instruments + their display / response fields,
  `session_rule_sets`, `session_field_labels`,
  `email_template_overrides`, `responses_received_enabled`,
  `help_contact`. The roster (reviewers / reviewees) and the
  relationships are **not** copied. For standing a
  structurally-identical session up for a *different* cohort.

Likely shape (service):

- **Never copied (either mode):** `assignments` (regenerated from
  each instrument's pinned rule set after clone — and in Mode B
  there is no roster to pair anyway), `responses`, `invitations`,
  `email_outbox`, `audit_events`. The deadline is offset by an
  operator-chosen delta or cleared. Session tags (Part 2) are
  per-session classification — whether a clone carries them is a
  scoping call (lean: Mode A may copy tags, Mode B starts
  untagged).
- **Lifecycle state:** the clone target lands in `draft`
  regardless of source state. Operator runs Validate + Generate
  + Activate as they would for any fresh session.
- **New session code:** generated by the existing
  `_generate_session_code` helper; the source's code is not
  reused.
- **Audit events:** `session.cloned` on the source
  (`refs.target_session_id`, `context.mode`) + the canonical
  `session.created` on the target (`reason="cloned"`,
  `refs.source_session_id`, `context.mode`).

Likely shape (UI):

- "Clone session" affordance — a per-row action on the Sessions
  lobby and/or a button in Session Home (probably both, like the
  current Delete-session affordance pattern). Decide at scoping.
- Clone-session form: prompts for the new session name, the
  clone mode (A / B above), and optionally a deadline override;
  everything else is copied verbatim per the chosen mode.

### Part 2 — Session tagging / grouping

**Goal.** Operator-chosen tags on each session, surfaced as
filterable chips on the lobby.

Likely shape:

- The `session_tags` table — **pre-positioned by Segment 13F
  PR 3** (`id` PK / `session_id` FK ON DELETE CASCADE /
  `tag VARCHAR(64)` / `UNIQUE (session_id, tag)` / `created_at`).
- Operator-facing Add / Remove tag affordance on Session Home or
  the Sessions lobby (decide at scoping).
- Sessions lobby gains a tag-filter strip in the "Sessions lobby"
  card, below the status-count pills, introduced by a
  "Show sessions tagged with:" label. It lists every tag the
  operator has used as a clickable chip.
  - **Selection is additive and per-tag.** Each tag chip toggles
    independently — clicking one shows/hides the sessions carrying
    it without disturbing the other chips' state. With several
    chips selected the table shows sessions matching the selected
    set (multi-tag combine rule — AND vs OR — to be locked at
    scoping; the lobby Tags column already AND-implies a row
    carries all its own tags).
  - **Clear all / Select all toggle.** A trailing "Clear all"
    chip deselects every tag at once. When no tags are selected
    it is replaced in place by a "Select all" chip that
    re-selects them all.
  - **Selection persists per browser via `localStorage`.** The
    chosen tag set survives reload, stored under a per-page key
    (`rrw-lobby-tag-filter`) — mirroring the Setup pages'
    column-visibility toggles (`rrw-reviewer-tag-visibility` &
    siblings, `spec/setup_pages.md`). No cookie: filter state is
    pure presentation, so it stays client-side rather than riding
    on every request. Inline JS reads the key on load and writes
    it on each toggle. A stored tag no longer present in the
    operator's current tag set is silently dropped on load.
  - **Placeholder shipped first.** The strip currently renders
    static placeholder chips (`HSH1000` / `2610` / `PEER` +
    `Clear all`) with no behavior — the click-to-filter wiring,
    selected-state styling, and the Clear all ⇄ Select all swap
    land with the rest of Part 2.
- Audit events: `session.tag_added` / `session.tag_removed`
  (`changes` or `set_changes` envelope).
- No friendly-label resolver involvement — tags are free-form
  operator-scoped strings, not the `tag_N` slots on `Reviewer` /
  `Reviewee` / `Relationship` (those are per-row data, not
  per-session classification).

### Part 3 — Session archiving

**Goal.** A new lifecycle transition `closed → archived` (and an
inverse `archived → closed` for un-archive) + the operator
surface that triggers it.

Likely shape:

- New service helper `sessions.archive_session(db, session, *,
  user, correlation_id)`. Pre-condition: session must be
  `closed` (or whatever the post-deadline-close terminal state
  is named — see the working note below). Sets
  `session.status = "archived"`; emits `session.archived`.
- Inverse: `sessions.unarchive_session(...)` — flips back to
  `closed`; emits `session.unarchived`.
- **No data deletion.** Archived sessions retain every reviewer /
  reviewee / response / audit row. The archive bucket is a UI
  filter, not a retention mechanism (that's 18C).
- **Archived sessions live on a separate child page, not in the
  main lobby table.** The main `/operator/sessions` table shows
  only non-archived sessions; archiving a session removes it from
  that table entirely. A child page — e.g.
  `/operator/sessions/archived` — hosts a **separate table** of
  the operator's archived sessions, reached by a link from the
  main lobby (decide placement at scoping — likely near the
  Sessions-lobby stats card, where the "archived" count pill
  already sits).
- **The archived page is a pared-down mirror of the lobby:**
  - An **info card** with the archived sessions' **tag chips**
    (the same chip vocabulary as the main lobby's tag-filter
    strip, scoped to archived sessions).
  - An **Actions card** hosting **search** over the archived
    table (name / code / tags) — no "Add new" here, since you
    cannot create a session directly into the archived bucket.
  - The same inline row-expander mechanism, but **bulk-only and
    archived-specific**: archived sessions need no
    rename / clone / re-deadline affordance. Selecting one or
    more archived rows opens a bulk expander offering
    **Unarchive**, **Download**, and **Delete** on the selected
    archived sessions. There is no single-session expander on
    this page — the expander is the bulk expander regardless of
    selection count (one or many).
  - `Unarchive` is the `archived → closed` inverse transition;
    `Download` exports the selected sessions (extract / bundle —
    align with 18D's zip-bundle work); `Delete` is the existing
    destructive delete, carrying its confirm checkbox into the
    expander as on the main lobby.
- Audit-event registrations: `session.archived` /
  `session.unarchived` (`changes` envelope on the status column).

### Post-MVP

Deferred — confirm need with pilot feedback before scoping:

- **Cross-operator clone handoff.** Clone a session into another
  operator's ownership (or copy a colleague's session to
  yourself): the clone target's `creator_id` is the destination
  operator, a `SessionOperator` row is inserted only for them,
  and the audit-event payload widens to include both actor +
  target operator IDs. Depends on **16B** (operator role
  delegation surface — shipped).
- **Auto-archive on deadline + N days.** A scheduled job (or the
  lazy deadline-close hook per `spec/lifecycle.md` "lazy
  deadline-close") flips a session `closed → archived` after a
  configurable grace period. Default off; per-deployment env var.

## Hard dependencies

- **None strictly required.** All three parts can land
  independently.
- **Cloning sequencing hint:** lands more cleanly **after 15C**
  (the library auto-copy helper exists to factor against) and
  **after 15B** (per-instrument RuleSet pointers
  `instruments.rule_set_id` have a meaningful "copy this pointer
  to the equivalent target-session row" semantic). Both shipped.
- **Tagging:** wants `session_tags` from **13F PR 3**.
- **Archiving:** wants `spec/lifecycle.md`'s reserved `archived`
  state — already in the canonical enum.
- **Cross-operator handoff (post-MVP):** 16B.

## Out of scope

- **Cross-deployment / cross-tenant cloning.** Single-deploy by
  design (`codebase_assessment_11may.md` Weakness #10).
- **Cloning responses.** Responses are session-runtime data, not
  setup; clone targets always start with empty responses.
- **Copy-paste of partial setup** ("just copy the instruments
  from session A"). Cloning is whole-session; partial copies
  remain a Settings-CSV exercise.
- **Tag-driven access control** (e.g. "tag X means only user Y
  can see it"). Tagging is operator-private classification, not a
  security boundary.
- **Cross-operator shared tag vocabulary** — every operator
  curates their own tag set; no global tag table.
- **Auto-archive on age / retention policy.** That's
  retention-policy territory, owned by **18C**.

## Doc impact

When parts ship:

- `docs/status.md` timeline entry per Part.
- `guide/todo_master.md` updated.
- `spec/sessions_overview.md` — Sessions lobby gains the inline
  row-expander action surface, the repurposed Actions card
  (search + "Add new"), the tag filter strip, and a link to the
  separate archived-sessions child page; the archived page (its
  table, info card, Actions card, and bulk-only expander) gets
  its own section or sibling spec.
- `spec/session_home.md` — Session Home gains the clone surface
  if it lives there, and the Add / Remove tag affordance.
- `spec/lifecycle.md` §44 — the `archived` row flips from
  "Reserved" to a real transition row with pre-conditions + side
  effects + audit event.
- `spec/architecture.md` — audit-event detail schema picks up the
  new `session.cloned` / `session.archived` / `session.unarchived`
  / `session.tag_added` / `session.tag_removed` envelopes.
- `spec/settings_inventory.md` — session-level tags row added,
  plus the `rrw-lobby-tag-filter` `localStorage` key in the
  browser-local UI-state primitives list.
- `guide/codebase_assessment_11may.md` §22 rows updated.

## Working notes

- _(placeholder for decisions during PR scoping)_
- **Clone surface:** per-row "Clone" anchor on the Sessions lobby
  vs. a "Clone session" button inside Session Home? Probably
  both, like the current Delete-session affordance pattern.
- **Clone of `email_template_overrides`:** byte-identical, or
  strip recipient-specific data (e.g. `help_contact` may be
  operator-scoped)? Lean byte-identical; operator can edit
  post-clone.
- **Clone audit trail:** cloning emits one `session.cloned` event
  on the source; the target gets the usual `session.created`.
  Confirm at scoping that the source's audit trail is NOT
  surfaced on the target (probably not — clean slate).
- **Terminal-state name.** `spec/lifecycle.md` reserves `expired`
  (Segment 9.3+ deadline-passed terminal) and `archived`
  (Segment 12+ post-export retention). Whether archiving
  transitions from `closed` directly or from `expired` depends on
  which lifecycle work ships first. Default assumption:
  `closed → archived`.
- **Tag table vs JSON column.** ✅ Locked 2026-05-11 — table.
  `session_tags` is pre-positioned by 13F PR 3 (easier per-tag
  indexing + delete-cascade).
- **Should archived sessions stay editable?** Probably no —
  archived sessions should be read-only (export still works;
  setup / response paths return 409 like `ready`-state sessions
  do today). Confirm at scoping.
- **Rich text in the session description — what the stack
  supports.** The app is server-rendered Jinja with no JS
  framework and no JS build step (`CLAUDE.md`). Three tiers of
  affordance:
  1. *Plain multi-paragraph* (this segment's small-enhancement
     item) — preserve line / paragraph breaks on display via
     `white-space: pre-line` or a split-to-`<p>` render. No
     dependency, no input change. The MVP.
  2. *Markdown subset, server-rendered* — bold / italic / lists /
     links authored as plain markdown in the existing
     `<textarea>`, rendered to **sanitised** HTML. Needs two
     Python deps (a markdown renderer + an HTML sanitiser such as
     `nh3`); no JS framework, so it fits the stack. An optional
     inline-JS toolbar over the textarea (inserts `**bold**`
     etc.) is progressive enhancement — still no build step.
  3. *True WYSIWYG* — a `contenteditable` editor library. A
     single pre-built file can be vendored without a build step,
     but it stores HTML (server-side sanitisation mandatory — a
     real XSS surface) and pushes against the no-frontend-
     framework posture. Not recommended without a deliberate
     call.
  Recommendation: tier 1 now; tier 2 only if pilot feedback asks
  for formatting; tier 3 is overkill for a session description.
