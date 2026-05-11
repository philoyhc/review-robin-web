# Segment 18B — Session tagging and archiving

> **Stub created 2026-05-11** as part of the Stage 4 guide/
> reorg. Siblings: **18A** (Session cloning,
> `guide/segment_18A_session_cloning.md`) and **18C**
> (Retention / deletion workflow,
> `guide/segment_18C_retention_deletion.md`).

**Stub. Sketch-level scope only.** Detailed PR breakdowns
get drafted when this segment is picked up.

## Goal

Two related affordances that turn the Sessions lobby from
"flat list of every session this operator has ever touched"
into something searchable + tidyable at scale:

1. **Session tagging / grouping.** Free-form operator-chosen
   tags on each session (e.g. `2026-Q1`, `pilot`, `cohort-A`)
   that surface on the lobby as filterable chips.
2. **Session archiving.** Move closed / finalised sessions
   out of the default lobby view into an `archived` bucket —
   still readable, still exportable, just no longer in the
   operator's "what am I currently working on?" surface. Uses
   the existing reserved `archived` lifecycle state.

## Why now

- **Tagging.** `spec/operator_ui_concept.md` "Out of scope"
  §3 names **session tagging / grouping** as one of the
  "adjacent capabilities likely to land sooner" — it composes
  cleanly with the Overview surface without forcing any
  Setup / Control / Operations redesign.
- **Archiving.** `spec/lifecycle.md` §44 already reserves
  `archived` as a real enum value: *"Reserved (Segment 12+,
  post-export retention). Not written by any current route."*
  The schema's ready; only the transition + UI are missing.
  18B picks up where Segment 12B's framing left off (the
  archive transition was originally hinted at in the 12B
  retention scope but never landed — see
  `guide/archive/segment_12B_audit_retention.md`).

## Scope (sketch)

### Part 1 — Session archiving transition

**Goal.** A new lifecycle transition `closed → archived`
(and an inverse `archived → closed` for un-archive) +
the operator surface that triggers it.

Likely shape:

- New service helper `sessions.archive_session(db, session,
  *, user, correlation_id)`. Pre-condition: session must be
  `closed` (or whatever the post-deadline-close terminal
  state is named — see open question below). Sets
  `session.status = "archived"`. Emits
  `session.archived` audit event.
- Inverse: `sessions.unarchive_session(db, session, *,
  user, correlation_id)` — flips back to `closed`. Emits
  `session.unarchived`.
- **No data deletion.** Archived sessions retain every
  reviewer / reviewee / response / audit row. The archive
  bucket is a UI filter, not a retention mechanism (that's
  18C).
- Sessions lobby (`/operator/sessions`) gains a "Show
  archived" toggle / filter (off by default). The default
  view hides archived rows.
- Per-row "Archive" affordance on closed sessions; per-row
  "Restore" on archived ones.
- Audit-event registrations: `session.archived` /
  `session.unarchived` (`changes` envelope on the status
  column).

### Part 2 — Session tagging

**Goal.** Operator-chosen tags on each session, surfaced as
filterable chips on the lobby.

Likely shape:

- The `session_tags` table — **pre-positioned by Segment
  13F PR 1** (`id` PK / `session_id` FK ON DELETE CASCADE /
  `tag VARCHAR(64)` / `UNIQUE (session_id, tag)` / `created_at`).
- Operator-facing Add / Remove tag affordance on Session
  Home or the Sessions lobby (decide at scoping).
- Sessions lobby gains a filter strip showing every tag the
  operator has used; clicking a tag filters the table to
  sessions carrying it. Multi-tag filter = AND.
- Audit events: `session.tag_added` / `session.tag_removed`
  (`changes` or `set_changes` envelope).
- No friendly-label resolver involvement — tags are
  free-form operator-scoped strings, not the `tag_N` slots
  on `Reviewer` / `Reviewee` / `Relationship` (those are
  per-row data, not per-session classification).

### Part 3 — Lobby search + auto-archive (post-MVP)

**Goal.** Once tagging + archiving are in place, two
post-MVP niceties:

- **Lobby search bar** — case-insensitive substring match
  against session name + session code + tags.
- **Auto-archive on deadline + N days.** A scheduled job (or
  the same lazy-close hook deadline-aware observation
  rides on, per `spec/lifecycle.md` "lazy deadline-close")
  flips a session from `closed` → `archived` after a
  configurable grace period. Default off; per-deployment env
  var.

Deferred — confirm need with pilot feedback before scoping.

## Hard dependencies

- **None strictly required.** Both parts can land
  independently. Part 1 wants `spec/lifecycle.md`'s reserved
  `archived` state — already in the canonical enum.

## Out of scope

- **Tag-driven access control** (e.g. "tag X means only
  user Y can see it"). Tagging is operator-private
  classification, not a security boundary.
- **Cross-operator shared tag vocabulary** — every operator
  curates their own tag set; no global tag table.
- **Auto-archive on age** (e.g. "anything older than 6
  months auto-archives"). That's retention-policy
  territory, owned by **18C**.

## Doc impact

When parts ship:

- `docs/status.md` timeline entry per Part.
- `guide/todo_master.md` updated.
- `spec/lifecycle.md` §44 — `archived` row flips from
  "Reserved" to a real transition row with pre-conditions
  + side effects + audit event.
- `spec/sessions_overview.md` — lobby gains the "Show
  archived" toggle, the tag filter strip, and (Part 3) the
  search bar.
- `spec/architecture.md` audit-event detail schema picks up
  the four new emitters.
- `spec/settings_inventory.md` — session-level tags row
  added.
- `guide/codebase_assessment_11may.md` §22 — relevant
  rows updated.

## Working notes

- _(placeholder for decisions during PR scoping)_
- **Terminal-state name.** `spec/lifecycle.md` reserves
  `expired` (Segment 9.3+ deadline-passed terminal) and
  `archived` (Segment 12+ post-export retention). Whether
  18B archives from `closed` directly or from `expired` (if
  Segment 9.3 lands first) depends on which lifecycle work
  ships before 18B. Default assumption: `closed → archived`.
- **Tag table vs JSON column.** ✅ Locked 2026-05-11 — table.
  `session_tags` is **pre-positioned by Segment 13F PR 1**
  (additive, nullable, no backfill; awaits 18B Part 2 light-up).
- **Should archived sessions stay editable?** Probably no —
  archived sessions should be read-only (export still
  works; setup / response paths return 409 like `ready`-state
  sessions do today). Confirm during scoping.
