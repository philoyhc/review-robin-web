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
- Sessions lobby gains a filter strip showing every tag the
  operator has used; clicking a tag filters the table to
  sessions carrying it. Multi-tag filter = AND.
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
- Sessions lobby gains a "Show archived" toggle / filter (off by
  default — the default view hides archived rows).
- Per-row "Archive" affordance on closed sessions; per-row
  "Restore" on archived ones.
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
- **Lobby search bar.** Case-insensitive substring match against
  session name + session code + tags.
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
- `spec/sessions_overview.md` — Sessions lobby gains the per-row
  Clone affordance, the tag filter strip, the "Show archived"
  toggle, and (post-MVP) the search bar.
- `spec/session_home.md` — Session Home gains the clone surface
  if it lives there, and the Add / Remove tag affordance.
- `spec/lifecycle.md` §44 — the `archived` row flips from
  "Reserved" to a real transition row with pre-conditions + side
  effects + audit event.
- `spec/architecture.md` — audit-event detail schema picks up the
  new `session.cloned` / `session.archived` / `session.unarchived`
  / `session.tag_added` / `session.tag_removed` envelopes.
- `spec/settings_inventory.md` — session-level tags row added.
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
