# Segment 18F — Scheduled events

> **Stub created 2026-05-17.** Sketch-level scope only — detailed
> PR breakdowns get drafted when this segment is picked up.
>
> Consolidates every **scheduled / automatic session-lifecycle
> automation** behind the one 13F scheduled-lifecycle schema audit,
> rather than each consumer segment growing its own
> column-per-feature. Auto-archive moved here out of **Segment 18A**
> (Sessions lobby enhancements) — 18A ships only manual archiving.

## Goal

Give the operator **time-based automation** of session lifecycle
events: things that happen on a date/time rather than on an explicit
click. Each one is a scheduled trigger on top of a transition service
that already exists (or ships in its owning segment); 18F adds the
*scheduling*, not the transition.

Why one segment: every item below needs a persisted date/time (or
schedule) column, and a worker / lazy-observer to fire it. Scoping
them together means **one** 13F schema slice and **one** dispatch
mechanism instead of a column and a half-worker per feature.

## Why now / why a segment

- **Auto-archive surfaced it.** Segment 18A Part 3 wanted a
  scheduled `closed → archived` flip; rather than pre-position a
  one-off `auto_archive_at` column, the call (2026-05-17) was to
  run one comprehensive audit of every scheduled automation — see
  `guide/segment_13F_more_db_prep.md`, "Scope re-sweep
  (2026-05-17)".
- **The transitions already exist or are cheap.** `archive_session`
  shipped in 18A; the invitation send-path and the reminder
  dispatch exist / are 14C's. 18F is mostly *scheduling* glue.
- **Shared dispatch.** A scheduled job (or the lazy
  deadline-observer pattern in `spec/lifecycle.md`) fires all of
  these; building it once is the segment's backbone.

## Scope (sketch)

The exact part list depends on which transition services have
shipped at scoping time; the items below are the candidate set.

### Part 1 — Auto-archive

**Goal.** A session carries an auto-archive date/time (or
deadline + grace period); a scheduled trigger flips it
`draft → archived` via 18A's `archive_session`.

- Reuses `session_lifecycle.archive_session` verbatim — only the
  trigger is new. Note: archiving is draft-only (18A's locked
  `draft ⇄ archived` model), so the schedule fires only on draft
  sessions; a running session must be reverted first.
- Schema: an `auto_archive_at` column (13F audit).

### Part 2 — Auto-send invitations

**Goal.** Instead of sending every invitation immediately on
activation, a session can carry an **invitations-send date/time**;
a scheduled trigger dispatches them at that point. Lets an operator
stage a session ahead of an announced start.

- Schema: an `invitations_send_at` column (13F audit).

### Part 3 — Session "opening" gate

**Goal.** Decouple *activation* from the *start of reviewing* so a
review begins at the same moment for everyone — a synchronised
open.

**Settled design (2026-05-17, see 13F):** "open" is a **gate
within the `ready` state — no new `SessionStatus` value**, the
same shape as the per-instrument `accepting_responses` flag and
the session `deadline`, all funnelled through
`session_lifecycle.session_accepts_responses()`.

- `activate_session` assumes the open-gate is **closed**: the
  session goes `ready`, invitations are sendable, but responses
  are not accepted until the gate opens — by **either** the
  `opens_at` datetime being reached **or** an explicit operator
  "Open now" action.
- Schema: an `opens_at` datetime (13F audit), possibly an
  `opened_at` stamp.
- `session_accepts_responses()` gains the gate check; the
  reviewer surface shows "activated — opens at X"; a
  `session.opened` audit event records the open.

### Part 4 — Scheduled / policy-driven purge (retention)

**Goal.** A retention policy that purges aged data on a schedule —
moved here out of **Segment 18C** when 18C was re-scoped to the
*operator-triggered* purge only (2026-05-17). 18C owns the purge
*mechanics*; 18F Part 4 owns the *scheduled trigger* that runs them.

- **Per-deployment policy** — env-var config in `app/config.py`
  (`RETENTION_RESPONSE_DAYS` / `RETENTION_AUDIT_DAYS` /
  `RETENTION_SESSION_ARCHIVED_DAYS`; unset = no auto-purge), a
  scheduled worker, and a `retention.policy_run` audit event with
  a `counts` envelope.
- **Per-session override** — the `sessions.retention_exception`
  Boolean (opt a session out, e.g. legal hold) and the
  `sessions.retention_overrides` JSON column, both pre-positioned
  by **13F PR 5**; a Settings-page editor; a
  `session.retention_policy_updated` emitter.
- Reuses 18C's `session_purge` service for the actual deletes —
  this part adds only the schedule + policy resolution.

### Reminders — owned by 14C, reconciled here

Scheduled reminder dispatch is **Segment 14C**'s
(`sessions.reminder_settings` JSON, 13F PR 4). 18F does not own
reminders; the 13F audit reconciles whether absolute reminder
datetimes are a new slot or fold into the existing JSON.

## Hard dependencies

- **The 13F scheduled-lifecycle schema audit** must resolve to a
  locked column set first — it becomes a new 13F PR. Until then
  every part here is schema-blocked.
- **Part 1** wants 18A's `archive_session` (shipped).
- **Part 3** is also a `spec/lifecycle.md` change (the gate
  semantics), not just a column.
- A **dispatch mechanism** — a scheduled job or the lazy
  deadline-observer hook — shared across all parts.

## Out of scope

- The underlying transitions themselves (`archive_session`,
  invitation send, reminder dispatch) — those belong to their
  owning segments; 18F only schedules them.
- Recurring / cron-style schedules — each item fires once at a
  set point. Repeating cadences (reminders) stay 14C's.

## Doc impact

When parts ship:

- `docs/status.md` timeline entry per Part.
- `guide/todo_master.md` updated.
- `spec/lifecycle.md` — the `opens_at` gate (Part 3) as a real
  gate within `ready`; activation's "gate starts closed" change.
- `spec/settings_inventory.md` — the new scheduled-datetime
  columns.
- `spec/architecture.md` — `session.opened` (and any other new)
  audit-event envelopes.

## Working notes

- _(placeholder for decisions during PR scoping)_
- **Pin order against 13F.** Pick this up only after the 13F
  scheduled-lifecycle audit lands its column set.
