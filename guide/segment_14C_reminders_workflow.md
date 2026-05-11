# Segment 14C — Reminders workflow

> **Carved out of the original Segment 14 family (2026-05-11).**
> Production hardening lives in **14A**
> (`guide/segment_14A_production_hardening.md`); email
> transport activation + backend swaps live in **14B**
> (`guide/segment_14B_email_infrastructure.md`, formerly
> `segment_14-1`). 14C is the *reminders policy* layer that
> sits on top of 14B's transport.

**Stub. Sketch-level scope only.** Detailed PR breakdowns get
drafted when this segment is picked up.

## Goal

Move reminders from "operator clicks Send-reminders to the
incomplete cohort, on their own cadence" to **scheduled,
policy-driven dispatch** — the app decides when reminders go
out, the operator configures the cadence per session, and the
dispatch helper from 14B Part A does the actual sending.

Today's surface (post-Segment 11C Part 1):

- Manage Invitations page has a per-row "Last reminder"
  column and a bulk "Send reminder to incomplete reviewers"
  button that enqueues `kind="reminder"` outbox rows. Send
  itself activates in 14B Part A.
- No scheduled / automatic reminder dispatch — the operator
  must press a button each time.
- Cadence policy (how often, how many) doesn't exist as a
  per-session setting; the operator's discretion is the policy.

14C closes that gap.

## Scope (sketch)

### Part 1 — Per-session reminder cadence settings

**Goal.** A small operator-facing settings surface for "when
should reminders go out automatically".

Likely shape:

- New per-session columns (or a JSON blob) capturing:
  - Auto-reminders enabled (default: off).
  - Cadence — e.g. "every 3 days" / "1 week + 3 days + 1 day
    before deadline" / cron-like expression. Pick the simplest
    expression that covers the realistic operator vocabulary;
    don't ship a general cron editor.
  - Max reminder count per reviewer (default: 3).
  - Time-of-day for dispatch (operator's timezone).
  - Quiet hours / weekend skip (optional polish).
- A reminder-cadence card on the Email Template editor
  (`/operator/sessions/{id}/setupinvite`) or on Session Home,
  TBD at scoping time.
- Per-cadence-change `session.reminder_cadence_updated` audit
  event using the `changes` envelope.

### Part 2 — Scheduled dispatch job

**Goal.** A background worker (or scheduled task) that
periodically scans sessions with auto-reminders enabled and
enqueues `kind="reminder"` outbox rows for incomplete reviewers
who are due for one.

Likely shape:

- Reuse 14B Part C's queue + worker scaffold if it's already
  landed; otherwise an Azure Functions timer trigger or
  equivalent.
- Per-reviewer dedup: don't enqueue a reminder if the most
  recent `kind="reminder"` outbox row for that reviewer was
  enqueued less than the cadence interval ago.
- Per-reviewer cap: never exceed the configured
  `max_reminder_count` for a single reviewer per session.
- Respect session lifecycle — only `ready` sessions inside
  their `accepting_responses` window get reminders.
- Respect per-instrument open/close state if any instrument
  the reviewer is responsible for is closed.
- Per-batch `session.reminder_batch_enqueued` audit event
  with `{"reviewer_ids": [...], "scheduled_run_at": ...}` in
  the `refs` slot.

### Part 3 — Targeted reminder cohorts (post-MVP)

**Goal.** Beyond the existing "incomplete reviewers" bulk
trigger, expose richer cohort slicing.

Today's `monitoring.AT_RISK_THRESHOLDS` already classifies
reviewers into Complete / Adequate / At risk / No responses
on the Responses page; per `guide/codebase_assessment_11may.md`,
the workplan acceptance criterion "Targeted reminders by
completion state" is ⚠️ partial (the "incomplete" cohort is
covered; richer slicing isn't).

Likely shape (deferred — confirm need before scoping):

- Per-cohort bulk Send buttons on Manage Invitations / Responses:
  "Send reminder to At-risk reviewers", "Send reminder to
  No-response reviewers".
- Reminder template differentiation by cohort (one tag in
  `email_template_overrides`, gated by cohort, or a per-cohort
  override block — TBD).
- Per-cohort `session.reminder_cohort_sent` audit event.

### Part 4 — Reminder analytics surface (post-MVP)

**Goal.** Surface reminder effectiveness on the Operations row.

Likely shape:

- A small "Reminders" card on Manage Invitations summarising:
  - reminders sent (count, last 7 days);
  - delivery success rate (reads `email.sent` /
    `email.send_failed` from 14B);
  - completion-after-reminder rate (joins reminder send time
    against response submit time).
- No new tables — reads against the audit log + outbox rows.

## Out of scope

- Email *transport* activation — that's 14B.
- Per-row Send-reminder button on Manage Invitations — that's
  already in 14B Part A's PR A1 scope (the per-row Action
  column handles invitation send today and extends to reminder
  send via the same dispatch helper).
- Replying-to-reminder handling — the app doesn't process
  inbound replies (per 14B "What's not in this segment").

## Hard dependencies

- **14B Part A** — at minimum, so reminder enqueues actually
  send. 14C's Part 2 (scheduled dispatch) is meaningless
  without a working transport.
- **14B Part B** (`correlation_id` strategy) — the per-reviewer
  dedup logic in Part 2 wants the
  `reminder:{session_id}:{reviewer_id}:{n}` correlation_id
  format that 14B Part B defines.
- **14B Part C** (queue + worker) — if Part 2 reuses Part C's
  scaffold rather than standing up its own; otherwise 14C Part
  2 brings its own scheduler.

## Doc impact

When parts ship:

- `docs/status.md` timeline entry per Part.
- `guide/todo_master.md` updated.
- `spec/settings_inventory.md` — reminder cadence settings
  added to the per-session settings table.
- `spec/operations_pages.md` — Manage Invitations contract
  picks up cohort buttons (Part 3) / reminders card (Part 4)
  if those parts ship.
- `spec/architecture.md` "Audit-event detail schema" — new
  reminder-related event types registered.

## Working notes

- _(placeholder for decisions during PR scoping)_
- Cadence expression vocabulary — pick during Part 1 scoping.
  Lean towards a small named-policy enum
  (`weekly` / `bi-weekly` / `pre-deadline-cascade`) rather
  than a generic cron editor.
- Should the scheduler live inside the app process (FastAPI
  startup background task) or as a separate Azure Functions /
  Container Apps timer trigger? Latter cleaner; former simpler.
  Decide at Part 2 scoping after 14B Part C's worker pattern
  settles.
