# Segment 18F — Scheduled events

> **Stub created 2026-05-17.** Sketch-level scope only — detailed
> PR breakdowns get drafted when this segment is picked up.
>
> Consolidates every **scheduled / automatic session-lifecycle
> automation** behind the one 13F scheduled-lifecycle schema audit,
> rather than each consumer segment growing its own
> column-per-feature. Auto-archive moved here out of **Segment 18A**
> (Sessions lobby enhancements) — 18A ships only manual archiving.
> **Segment 14C (Reminders workflow) was consolidated into this
> segment on 2026-05-18** — scheduled reminder dispatch is itself
> a scheduled event; it lives here as Part 5 and the standalone
> 14C plan is retired.

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
  email transport (14B) exist or are cheap. 18F is mostly
  *scheduling* glue.
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
- **Ride-along: 18D Part 5.** The Settings-CSV round-trip of the
  retention columns (`retention_exception` / `retention_overrides`)
  — Segment 18D's Part 5 — was handed to this part: once 13F PR 5
  lands the columns, add the `retention.*` rows to the Settings
  CSV serialiser / importer as part of Part 4.

### Part 5 — Reminders workflow

Scheduled, policy-driven reminder dispatch — **consolidated from
the former Segment 14C on 2026-05-18** (that standalone plan is
retired). Today reminders are operator-triggered: the Manage
Invitations bulk "Send reminder to incomplete reviewers" button
enqueues `kind="reminder"` outbox rows, and the send itself
activates in 14B Part A. Part 5 makes dispatch scheduled and
policy-driven. Unlike Parts 1–4, this is a **recurring
cadence**, not a fire-once trigger — the deliberate exception
in this segment.

- **5a — Per-session reminder cadence settings.** An
  operator-facing surface for "when reminders go out
  automatically", persisted in the `sessions.reminder_settings`
  JSON column (pre-positioned by 13F PR 4). Keys, locked at
  scoping: auto-reminders enabled (default off); cadence — a
  small named-policy enum (`weekly` / `bi-weekly` /
  `pre-deadline-cascade`), not a general cron editor; max
  reminder count per reviewer (default 3); dispatch time-of-day
  (operator timezone); optional quiet-hours / weekend skip. A
  cadence card on the Email Template editor or Session Home
  (TBD at scoping); a `session.reminder_cadence_updated` audit
  event (`changes` envelope).
- **5b — Scheduled dispatch job.** A background worker scans
  sessions with auto-reminders enabled and enqueues
  `kind="reminder"` rows for incomplete reviewers who are due.
  Per-reviewer dedup (skip if the last reminder enqueued less
  than the cadence interval ago — uses 14B Part B's
  `reminder:{session_id}:{reviewer_id}:{n}` correlation_id);
  per-reviewer cap at `max_reminder_count`; only `ready`
  sessions inside their accepting-responses window; respects
  per-instrument open/close. A `session.reminder_batch_enqueued`
  audit event. Reuses 14B Part C's queue + worker scaffold if
  landed; otherwise the shared dispatch mechanism below.
- **5c — Targeted reminder cohorts (post-MVP).** Beyond the
  "incomplete" cohort, richer slicing off
  `monitoring.AT_RISK_THRESHOLDS` (At risk / No responses) —
  per-cohort bulk Send buttons, optional per-cohort template
  differentiation, a `session.reminder_cohort_sent` event.
  Confirm need before scoping.
- **5d — Reminder analytics (post-MVP).** A small "Reminders"
  card on Manage Invitations — reminders sent, delivery success
  rate (reads 14B's `email.sent` / `email.send_failed`),
  completion-after-reminder rate. No new tables; reads the
  audit log + outbox.

## Hard dependencies

- **The 13F scheduled-lifecycle schema audit** must resolve to a
  locked column set first — it becomes a new 13F PR. Until then
  every part here is schema-blocked.
- **Part 1** wants 18A's `archive_session` (shipped).
- **Part 3** is also a `spec/lifecycle.md` change (the gate
  semantics), not just a column.
- **Part 5 (reminders)** hard-depends on **14B Parts A / B**
  (the email transport, and the `correlation_id` strategy the
  per-reviewer dedup uses) and reuses **14B Part C**'s
  queue / worker scaffold if available.
- A **dispatch mechanism** — a scheduled job or the lazy
  deadline-observer hook — shared across all parts.

## Out of scope

- The underlying transitions themselves (`archive_session`,
  invitation send, the 14B email transport) — those belong to
  their owning segments; 18F only schedules them.
- Email *transport* activation and backend swaps — 14B's.
  Part 5 owns the reminder *cadence* and the *scheduled
  enqueue*; 14B owns the *send*.

## Doc impact

When parts ship:

- `docs/status.md` timeline entry per Part.
- `guide/todo_master.md` updated.
- `spec/lifecycle.md` — the `opens_at` gate (Part 3) as a real
  gate within `ready`; activation's "gate starts closed" change.
- `spec/settings_inventory.md` — the new scheduled-datetime
  columns, plus the Part 5 reminder-cadence settings.
- `spec/operations_pages.md` — Manage Invitations picks up the
  Part 5c cohort buttons / Part 5d reminders card if those
  ship.
- `spec/architecture.md` — `session.opened`, the reminder
  events, and any other new audit-event envelopes.

## Working notes

- _(placeholder for decisions during PR scoping)_
- **Pin order against 13F.** Pick this up only after the 13F
  scheduled-lifecycle audit lands its column set.
