# Segment 18G — Scheduled events

> **Stub created 2026-05-17.** Sketch-level scope only — detailed
> PR breakdowns get drafted when this segment is picked up.
>
> **Renumbered 18F → 18G on 2026-05-19** when the new
> **Segment 18F — Workflow optimization**
> (`guide/segment_18F_workflow_optimization.md`) was created. The
> scope is unchanged — only the segment number moved.
>
> Consolidates every **scheduled / automatic session-lifecycle
> automation** behind one schema slice (Part 0 below), rather than
> each consumer segment growing its own column-per-feature.
> Auto-archive moved here out of **Segment 18A** (Sessions lobby
> enhancements) — 18A ships only manual archiving.
> **Segment 14C (Reminders workflow) was consolidated into this
> segment on 2026-05-18** — scheduled reminder dispatch is itself
> a scheduled event; it lives here as Part 5 and the standalone
> 14C plan is retired.
>
> **Segment 13F (More DB prep) consolidated into this segment on
> 2026-05-20.** Five of 13F's seven PRs had shipped; the remaining
> two (`sessions.reminder_settings`, `sessions.retention_*`) plus
> the pending scheduled-lifecycle schema audit were all
> 18G-relevant, so they were folded in here as **Part 0 — Schema
> pre-positioning** and the standalone 13F plan retired to
> `guide/archive/segment_13F_more_db_prep.md`.
>
> **Part 0 reshape — anchors + offsets model (2026-05-20).**
> The initial Part 0 sketch carried three absolute datetime
> columns (`auto_archive_at` / `invitations_send_at` /
> `activate_at`). On operator-workflow review the schedules
> closer to the operator's mental model are **anchors** (Start,
> End, Release-from — what they pick on a calendar) plus
> **offsets** anchored on them (auto-send invites "1 day before
> Start", reminders "2 hours before End", auto-archive "30 days
> after End"). Part 0a now holds **anchor** datetimes (just
> `scheduled_activate_at` + `responses_release_at`; `deadline`
> is already live); Part 0b holds **offset** configs
> (`invite_offsets` / `reminder_offsets` / `archive_offset` /
> `release_until_offset`); Part 0c retention is unchanged in
> shape (the auto-delete-after-archive offset lives as a key
> inside `retention_overrides`). The Start anchor was
> renamed `activate_at` → `scheduled_activate_at` (the
> existing live `activated_at` column is the system-stamped
> record of when activation fired — one letter apart from
> `activate_at` was too easy to typo). See `spec/lifecycle.md`
> "Scheduled lifecycle automation" for the model + the
> cross-cutting anchor-null inertness rule.

## Goal

Give the operator **time-based automation** of session lifecycle
events: things that happen on a date/time rather than on an explicit
click. Each one is a scheduled trigger on top of a transition service
that already exists (or ships in its owning segment); 18G adds the
*scheduling*, not the transition.

Why one segment: every item below needs a persisted date/time
(an **anchor**) or anchor-relative **offset**, and a worker /
lazy-observer to fire it. Scoping them together means **one**
schema slice (Part 0 below — anchors + offsets) and **one**
dispatch mechanism instead of a column and a half-worker per
feature.

## Why now / why a segment

- **Auto-archive surfaced it.** Segment 18A Part 3 wanted a
  scheduled `closed → archived` flip; rather than pre-position a
  one-off `auto_archive_at` column, the call (2026-05-17) was to
  run one comprehensive audit of every scheduled automation. The
  audit's resolved column set is now **Part 0** below.
- **The transitions already exist or are cheap.** `archive_session`
  shipped in 18A; the invitation send-path and the reminder
  email transport (14B) exist or are cheap. 18G is mostly
  *scheduling* glue.
- **Shared dispatch.** A scheduled job (or the lazy
  deadline-observer pattern in `spec/lifecycle.md`) fires all of
  these; building it once is the segment's backbone.

## Scope (sketch)

The exact part list depends on which transition services have
shipped at scoping time; the items below are the candidate set.

### Part 0 — Schema pre-positioning (consolidated from 13F, 2026-05-20)

**Status: shipped 2026-05-20** (PR #1253). All eight columns
landed inert on `sessions` — Parts 1–5 below now have a stable
schema to consume. Inert audit at close-out verified zero hits
across `app/services/` + `app/web/`.

**Goal.** Pre-position the additive, nullable, no-backfill schema
slots that Parts 1–5 read. Mirrors the 13D / 13E / 13F
inert-migrations pattern: every column is nullable, every
migration round-trips on SQLite + `ci-postgres`, no service code
reads or writes the new shape until its owning Part lights it up.
This Part lands first inside 18G; Parts 1–5 are schema-blocked on
it.

**Origin.** Consolidated 2026-05-20 from the two outstanding 13F
PRs (`reminder_settings`, `retention_*`) and the pending 13F
scheduled-lifecycle schema audit (`auto_archive_at`,
`invitations_send_at`, `activate_at` — later renamed
`scheduled_activate_at` in the anchors + offsets reshape; see
preamble). All three items were already 18G-relevant, so folding
them in here retires the schema-only segment.

#### Part 0a — Anchor datetime columns (operator-set, absolute)

Two nullable `DateTime(timezone=True)` columns on `sessions`:

```python
# app/db/models/review_session.py
scheduled_activate_at: Mapped[datetime | None]  # Start  → Part 1
responses_release_at:  Mapped[datetime | None]  # Release-from (Participants platform, inert until then)
```

**Anchors are the absolute datetimes the operator sets directly.**
Every scheduled-event offset (Part 0b) is *relative to* one of
them. Today's session already carries one anchor — `sessions.deadline`
(End) — and Part 0a adds two more:

- **`scheduled_activate_at` (Start)** — the operator-set trigger
  for the scheduled `validated → ready` transition (consumer
  Part 1). Per the 18F Part 2 Activated-as-gate model, no new
  `SessionStatus` value and no sub-gate within `ready` —
  `ready` already means "open for responses". Distinct from the
  existing `activated_at` (live, system-stamped on the first
  `→ ready`): one is the operator-set *trigger*, the other is
  the system *record* of when it fired.
- **`responses_release_at` (Release-from)** — the
  Participants-platform "reviewees can view responses from this
  point" anchor; pre-positioned **inert** in 18G so future
  participant-model work doesn't need a follow-on migration. No
  18G Part reads it.

**Shape decision.** Individual nullable datetime columns rather
than a single `sessions.schedule` JSON container. The scheduler
queries these by value ("find every session whose `scheduled_activate_at`
has passed and is still `validated`") — unlike the offset configs
below, which are read per session at trigger time. Datetime
columns are queryable and indexable; JSON is not. Add a B-tree
index per column when its owning Part lights it up (deferred
to that Part — the column is inert until then).

#### Part 0b — Offset config columns (operator-set, anchor-relative)

Four nullable columns on `sessions` — two JSON lists (for events
that fire on a *sequence* of offsets) and two String singletons
(for events that fire once):

```python
# app/db/models/review_session.py
invite_offsets:        Mapped[list[str] | None]  # JSON; anchor=scheduled_activate_at; → Part 2
reminder_offsets:      Mapped[list[str] | None]  # JSON; anchor=deadline;               → Part 3
archive_offset:        Mapped[str | None]        # String(16) ISO 8601 duration; anchor=deadline; → Part 4
release_until_offset:  Mapped[str | None]        # String(16) ISO 8601 duration; anchor=responses_release_at (Participants platform, inert until then)
```

**Anchor table.**

| Offset column | Anchor | Shape | Consumer |
|---|---|---|---|
| `invite_offsets` | `scheduled_activate_at` (Start) | JSON list of ISO 8601 durations, e.g. `["-P1D", "-PT2H"]` | Part 2 (auto-send invites) |
| `reminder_offsets` | `deadline` (End) | JSON list of ISO 8601 durations, e.g. `["-P2D", "-PT4H"]` | Part 3 (auto-send reminders) |
| `archive_offset` | `deadline` (End) | Single ISO 8601 duration, e.g. `"P30D"`; **editor default `P30D`** (the column is nullable with no `server_default`; the editor pre-fills `P30D` to give operator time to download data before the session disappears from the active lobby) | Part 4 (auto-archive) |
| `release_until_offset` | `responses_release_at` | Single ISO 8601 duration (Release-until is derived as Release-from + this offset) | Participants platform (inert until then) |

**Shape decision.** Separate columns (not a single
`sessions.lifecycle_offsets` JSON) so each consumer Part lights
up its own surface independently and audits cleanly (`session.invite_schedule_updated`
vs an over-broad `session.lifecycle_offsets_changed`). Hybrid types
match the data shape: lists are JSON, singletons are
`String(16)`. ISO 8601 duration strings are dialect-neutral
(SQLite + Postgres) and round-trip cleanly through the Settings
CSV export.

**Maximum offset.** Sized for a 10-day cap on any single offset
— the worst-case representation `-PT240H` is 7 chars, so
`String(16)` carries comfortable headroom while still being
short enough for SQLite/Postgres index-friendliness later. The
cap is enforced at the editor / validator (consumer Part), not
by the schema.

**Cross-cutting rule — anchor-null inertness.** An offset is
**inert when its anchor is null**: the scheduler skips it, the
editor disables the offset field. This is a general rule across
every (anchor, offset) pair — documented once in
`spec/lifecycle.md` rather than per-feature. Single-point
enforcement lives in a `resolve_offset(session, anchor_field,
offset_field) -> datetime | None` helper that every scheduler
path uses.

#### Part 0c — `sessions.retention_exception` Boolean + `sessions.retention_overrides` JSON (feeds Part 5)

Two nullable columns on `sessions` (was 13F PR 5), landed
together because they're tightly coupled (one is the "opt out
entirely" flag; the other is the "override the deployment
defaults" JSON):

```python
# app/db/models/review_session.py
retention_exception: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
retention_overrides: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

`retention_exception=NULL` and `=False` both mean "no exception"
(Part 5 normalises on read). `retention_overrides=NULL` means
"use the deployment retention defaults" (Part 5's env vars).

**`retention_overrides` key inventory.** Per-session overrides
for the deployment retention env vars, plus the per-session
**auto-delete offset**:

| Key | Type | Anchor | Meaning |
|---|---|---|---|
| `response_days` | int | n/a | overrides `RETENTION_RESPONSE_DAYS` |
| `audit_days` | int | n/a | overrides `RETENTION_AUDIT_DAYS` |
| `archived_days` | int | n/a | overrides `RETENTION_SESSION_ARCHIVED_DAYS` |
| `delete_after_archive` | str (ISO 8601 duration) | session archive time | per-session auto-delete offset — fires hard-delete of an *archived* session this far past its archive timestamp |

`delete_after_archive` lives inside `retention_overrides` rather
than as a top-level column because (i) it's anchor-relative to
the *archive* event (already system-stamped, no new anchor
column needed) and (ii) it's a retention-policy lever
operationally — the same Part 5 editor surfaces both the env-var
overrides and this offset.

**Sequencing inside Part 0.** Three migrations (0a / 0b / 0c),
independent of each other, batched into **one PR** since every
column lands inert — there's no incremental light-up to gate on.
Migrations land in numeric order for tidy history. Round-trip
tests in `tests/integration/test_*_schema.py` shape (mirrors
13F PR 6 / 7 precedent). Inert audit at PR close: `grep` for
the new identifiers across `app/services/` + `app/web/` returns
zero hits — light-up happens in Parts 1–5.

> **Parts 1–5 are ordered by workflow sequence — the chronological
> order each scheduled event fires across a session's life.**
> Activation is the first scheduled event (the session opens),
> then invites land just before / at activation, then reminders
> fire as the deadline approaches, then auto-archive cleans up
> after End, and finally auto-delete purges archived sessions.
> Implementation dependency order roughly matches workflow order:
> later Parts read scaffolding the earlier Parts can settle (the
> shared dispatch mechanism, audit-event naming conventions).

### Part 1 — Scheduled activation

**Goal.** A session can carry an **activation date/time**; a
scheduled trigger flips it `validated → ready` at that point.
Because **Activation is the open event** (Activated-as-gate —
see 18F Part 2), a scheduled activation *is* the synchronised
open: every reviewer's window starts at the same moment. This
is the first scheduled event in the workflow — every downstream
offset that anchors on Start (`invite_offsets`) reads the
column this Part lights up.

**Settled design (2026-05-19).** The earlier "opening gate" idea
— a separate gate *within* `ready`, with an `opens_at` datetime
and an "Open now" action — is **retired**. Instead the existing
`draft → ready` Activate transition is the open, and this part
just lets that transition be *scheduled*. No new `SessionStatus`
value and no sub-gate within `ready`: `ready` already means
"open for responses".

- Schema: `sessions.scheduled_activate_at` (Part 0a) — the scheduled
  `validated → ready` trigger; possibly reuse the existing
  activation audit event, or add a `session.activation_scheduled`
  event.
- A scheduled trigger calls `session_lifecycle.activate_session`
  at `scheduled_activate_at`; an explicit operator "Activate now" stays
  available (it already exists).
- **Depends on 18F Part 2** for the reviewer-facing states: the
  pre-open page ("scheduled to open at «scheduled_activate_at» — come back
  later") reads the `scheduled_activate_at` this part adds. 18F Part 2
  builds the states; this part supplies the scheduled time.
- Establishes the **shared dispatch mechanism** Parts 2–5 reuse —
  whichever pattern the segment settles on (background worker or
  lazy observer extended to additional anchors) lands here first.

### Part 2 — Auto-send invitations

**Goal.** Instead of sending every invitation immediately, a
session can carry a list of **invitation send offsets** anchored
on `scheduled_activate_at` (Start); a scheduled trigger dispatches them at
each `scheduled_activate_at + offset` moment. With the Activated-as-gate
model (Part 1 / 18F), invitations are sendable from the
**Prepared (`validated`)** state — so an operator can schedule
notification emails to land *ahead of* the scheduled open
(e.g. one day before, two hours before).

- Schema: `sessions.invite_offsets` (Part 0b). Inert when
  `scheduled_activate_at` is unset per the cross-cutting anchor-null rule.
- Depends on **18F Part 2** relaxing the invitation gate so
  invitations can be sent before activation, and on **Part 1**
  surfacing `scheduled_activate_at` as a configurable operator input.

### Part 3 — Auto-send reminders

Scheduled, policy-driven reminder dispatch — **consolidated from
the former Segment 14C on 2026-05-18** (that standalone plan is
retired). Today reminders are operator-triggered: the Manage
Invitations bulk "Send reminder to incomplete reviewers" button
enqueues `kind="reminder"` outbox rows, and the send itself
activates in 14B Part A. Part 3 makes dispatch scheduled and
policy-driven. Unlike Parts 1 / 2 / 4 / 5, this Part fires a
**sequence** of triggers per session (one per offset entry),
not a single one — the deliberate exception in this segment.

- **3a — Per-session reminder offsets.** An operator-facing
  surface for "when reminders go out automatically", persisted in
  the `sessions.reminder_offsets` JSON column (pre-positioned by
  Part 0b). The list itself carries the cadence: an empty list /
  null means auto-reminders off; entries are ISO 8601 durations
  anchored on `deadline` (e.g. `["-P3D", "-P1D", "-PT4H"]`
  fires three reminders at 3 days, 1 day, and 4 hours before
  End). Ancillary controls (dispatch time-of-day in operator
  timezone, optional quiet-hours / weekend skip) settle at
  scoping — either as additional `sessions.*` columns or as keys
  inside the offset entries (e.g. each entry an object instead of
  a string). A cadence card on the Email Template editor or
  Session Home (TBD at scoping); a `session.reminder_schedule_updated`
  audit event (`changes` envelope).
- **3b — Scheduled dispatch job.** A background worker scans
  sessions with `reminder_offsets` set and enqueues
  `kind="reminder"` rows for incomplete reviewers at each
  resolved `deadline + offset`. Per-reviewer / per-offset dedup
  (skip if a reminder for this `(session, reviewer, offset_index)`
  was already enqueued — uses 14B Part B's
  `reminder:{session_id}:{reviewer_id}:{n}` correlation_id);
  only `ready` sessions inside their accepting-responses window;
  respects per-instrument open/close. A `session.reminder_batch_enqueued`
  audit event. Reuses 14B Part C's queue + worker scaffold if
  landed; otherwise the shared dispatch mechanism Part 1
  established.
- **3c — Targeted reminder cohorts (post-MVP).** Beyond the
  "incomplete" cohort, richer slicing off
  `monitoring.AT_RISK_THRESHOLDS` (At risk / No responses) —
  per-cohort bulk Send buttons, optional per-cohort template
  differentiation, a `session.reminder_cohort_sent` event.
  Confirm need before scoping.
- **3d — Reminder analytics (post-MVP).** A small "Reminders"
  card on Manage Invitations — reminders sent, delivery success
  rate (reads 14B's `email.sent` / `email.send_failed`),
  completion-after-reminder rate. No new tables; reads the
  audit log + outbox.

### Part 4 — Auto-archive

**Goal.** A session carries an archive *offset* (anchored on
`deadline`, default `P30D`); a scheduled trigger flips it
`draft → archived` via 18A's `archive_session` at
`deadline + archive_offset`. The first lifecycle event past
the session's End — the operator's data-download window sits
inside this offset.

- Reuses `session_lifecycle.archive_session` verbatim — only the
  trigger is new. Note: archiving is draft-only (18A's locked
  `draft ⇄ archived` model), so the schedule fires only on draft
  sessions; a running session must be reverted first (when the
  scheduled trigger fires on a still-`ready` session, log + skip
  until the next sweep).
- Schema: `sessions.archive_offset` (Part 0b). Inert when
  `deadline` is unset per the cross-cutting anchor-null rule.
- The default `P30D` (30 days post-deadline) is operator-editable;
  it gives the operator time to download data before the session
  disappears from the active lobby.

### Part 5 — Scheduled / policy-driven purge (auto-delete)

**Goal.** A retention policy that purges aged data on a schedule —
moved here out of **Segment 18C** when 18C was re-scoped to the
*operator-triggered* purge only (2026-05-17). 18C owns the purge
*mechanics*; 18G Part 5 owns the *scheduled trigger* that runs them.
Last event in the workflow — fires only on already-archived
sessions, anchored on the system-stamped archive timestamp Part 4
produces.

- **Per-deployment policy** — env-var config in `app/config.py`
  (`RETENTION_RESPONSE_DAYS` / `RETENTION_AUDIT_DAYS` /
  `RETENTION_SESSION_ARCHIVED_DAYS`; unset = no auto-purge), a
  scheduled worker, and a `retention.policy_run` audit event with
  a `counts` envelope.
- **Per-session override** — the `sessions.retention_exception`
  Boolean (opt a session out, e.g. legal hold) and the
  `sessions.retention_overrides` JSON column, both pre-positioned
  by **Part 0c**; a Settings-page editor; a
  `session.retention_policy_updated` emitter.
- **Per-session auto-delete offset** — `retention_overrides.delete_after_archive`
  (ISO 8601 duration, anchored on the system-stamped archive
  time) — when set, an archived session is hard-deleted this far
  past its archive timestamp. Inert when the session is not
  archived per the cross-cutting anchor-null rule.
- Reuses 18C's `session_purge` service for the actual deletes —
  this part adds only the schedule + policy resolution.
- **Ride-along: 18D Part 5.** The Settings-CSV round-trip of the
  retention columns (`retention_exception` / `retention_overrides`)
  — Segment 18D's Part 5 — was handed to this part: once Part 0c
  lands the columns, add the `retention.*` rows to the Settings
  CSV serialiser / importer as part of Part 5.

## Hard dependencies

- **Part 0 (Schema pre-positioning) shipped 2026-05-20** —
  Parts 1–5 read the columns it pre-positioned. No longer a
  dependency in flight.
- **Part 1 / Part 2** depend on **18F Part 2** — the
  Activated-as-gate model, the relaxed invitation gate, and the
  reviewer pre-open / closed states. 18F lands first; this
  segment supplies the scheduled times those states read.
- **Part 1** also establishes the **shared dispatch mechanism**
  (scheduled worker or lazy observer extended to additional
  anchors) Parts 2–5 reuse.
- **Part 2** depends on Part 1 surfacing `scheduled_activate_at`
  as a configurable operator input (otherwise the offset has no
  anchor to resolve against).
- **Part 3 (reminders)** hard-depends on **14B Parts A / B**
  (the email transport, and the `correlation_id` strategy the
  per-reviewer dedup uses) and reuses **14B Part C**'s
  queue / worker scaffold if available.
- **Part 4** wants 18A's `archive_session` (shipped).
- **Part 5** wants 18C's `session_purge` (shipped) and reads the
  archive timestamp Part 4 produces.

## Out of scope

- The underlying transitions themselves (`archive_session`,
  invitation send, the 14B email transport) — those belong to
  their owning segments; 18G only schedules them.
- Email *transport* activation and backend swaps — 14B's.
  Part 3 owns the reminder *cadence* and the *scheduled
  enqueue*; 14B owns the *send*.

## Doc impact

When parts ship:

- `docs/status.md` timeline entry per Part.
- `guide/todo_master.md` updated.
- `spec/lifecycle.md` — already carries the **Scheduled lifecycle
  automation** section (the anchors + offsets model + the
  cross-cutting anchor-null inertness rule). Part 1's
  `scheduled_activate_at` is the scheduled `validated → ready`
  trigger; no separate opening gate (see 18F Part 2 for the
  Activated-as-gate model).
- `spec/settings_inventory.md` — the new scheduled-datetime
  columns, plus the Part 3 reminder-cadence settings.
- `spec/operations_pages.md` — Manage Invitations picks up the
  Part 3c cohort buttons / Part 3d reminders card if those
  ship.
- `spec/architecture.md` — the scheduled-activation and reminder
  events, and any other new audit-event envelopes.

## Working notes

- _(placeholder for decisions during PR scoping)_
- **Part 0 shipped 2026-05-20.** Parts 1–5 are unblocked on
  schema and ready to scope; start with Part 1 (scheduled
  activation) because it establishes the shared dispatch
  mechanism Parts 2–5 reuse, plus surfaces
  `scheduled_activate_at` as a configurable operator input
  (Part 2 depends on that).
