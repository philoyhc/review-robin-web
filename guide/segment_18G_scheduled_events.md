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

**Cross-cutting rules.** Two related rules apply to every
(anchor, offset) pair — documented once in `spec/lifecycle.md`
§8.2 rather than per-feature:

- **Always editable; effectiveness signalled, not gated**
  (§8.2.1). Anchor and offset fields are always editable in
  operator-mutable states (`draft` or `validated`). The operator
  declares intent at any time; the UI signals not-effective
  states; the system enforces safety at fire time. No editor
  lock-out — including the "Start at session creation" case
  where the schedule is declared before any validation.
- **Anchor-null inertness** (§8.2.2). An offset is inert when
  its anchor is null. Enforced at one call site — a
  `resolve_offset(session, anchor_field, offset_field) ->
  datetime | None` helper that every scheduler path uses.
- **Event-precondition guard** (§8.2.3). Each scheduled event
  has additional operational preconditions checked at fire time
  (the session is `validated` for activation, invitations exist
  for auto-send, session is `ready` for reminders, session is
  `draft` for archive, session is `archived` for auto-delete).
  The trigger skips + audits + clears the offset on a
  precondition miss.

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

**Service contract (settled 2026-05-20).** The scheduled
trigger is a **single dead-simple call into `activate_session`**
— no auto-Generate, no auto-Validate at fire time. Reasons:
Validate at fire time can surface blocking errors the offline
operator can't fix; Generate at fire time runs assignment
generation outside the operator's review window. The operator's
"Prepare" run (Generate + Validate, manually triggered via the
Workflow card) is the explicit pre-condition for scheduling
activation.

**Minimum lead time on `scheduled_activate_at`.** Two distinct
concerns share the "1 hour" floor — the editor enforces both at
save and they apply per scenario:

- **Operational lead time** — the lazy observer (§8.3 in
  `spec/lifecycle.md`) fires on operator GETs; large rosters
  (1,200-reviewer pilot) need wall-clock to fan out invitations
  + run activation. `SCHEDULED_OPERATIONAL_LEAD_HOURS` (default
  `1`).
- **Reviewer-coordination gap** — when invitations are
  auto-sent, the reviewer needs notice between the invite
  landing and the session opening. `REVIEWER_NOTICE_MIN_HOURS`
  (default `1`).

The per-scenario rules:

| Scenario | Save-time rule |
|---|---|
| Start set, `invite_offsets` empty | `Start ≥ now + SCHEDULED_OPERATIONAL_LEAD_HOURS` |
| Start unset, `invite_offsets` non-empty | inert per §8.2.2 anchor-null — editor renders `invite_offsets` grey with "Set Start first"; no save-time check needed |
| Both set | Each `invite_offset` entry's resolved fire moment (`Start + offset`) must satisfy: (a) `fire ≥ now + SCHEDULED_OPERATIONAL_LEAD_HOURS`; (b) `|offset| ≥ REVIEWER_NOTICE_MIN_HOURS` (reviewer-coordination gap before Start) |

(b) implies the earliest invite always fires at least
`REVIEWER_NOTICE_MIN_HOURS` before Start. For multiple offsets,
the same check applies per entry — the earliest (most negative)
entry pushes Start far enough out for the operational lead; the
latest (least negative) entry must still leave the coordination
gap before Start.

Worked example. `invite_offsets = ["-P1D", "-PT2H"]`, defaults
1 hour for both knobs:

- Earliest (−1d): fire = `Start − 1d`. Requires `Start ≥ now + 1d + 1hr`.
- Latest (−2h): fire = `Start − 2h`. Requires `|−2h| ≥ 1hr` ✓ and `Start − 2h ≥ now + 1hr` → `Start ≥ now + 3hr` (already covered).

Editor errors are explicit when a rule is violated, e.g.
"Auto-send invite −PT30M gives only 30 minutes between invite
and Start; minimum reviewer notice is 1 hour. Choose -PT1H or
larger."

**Concurrency, retry, and notification follow the cross-cutting
rules in `spec/lifecycle.md` §8.3** (SELECT … FOR UPDATE +
idempotency check; 3 retries from audit-log count; Session Home
banner on skip/failure for MVP, email deferred).

**Always editable; effectiveness signalled, not gated.** Per
the cross-cutting rule in `spec/lifecycle.md` §8.2.1, the
`scheduled_activate_at` field is **always editable** while the
session is operator-mutable (`draft` or `validated`) — including
at session-creation time, before any validation has happened.
The operator declares intent on a calendar; effectiveness is
visible (the workflow-card caption — see *Right-column signals*
below) and enforced at fire time (the precondition guard
below), not by locking the editor.

**Persistence across invalidation.** A schedule **persists**
across `validated → draft` flips (operator edits a roster, the
session invalidates, the schedule remains set). Same model
applies whether the operator set the schedule at creation
(never validated yet) or after a prior validation that got
invalidated — both end up `draft` + schedule set, and the
fire-time guard handles both the same way.

**Fire-time guard.** When the trigger fires, it checks the
session's current status:

```python
if not lifecycle.is_validated(session):
    audit.write_event(
        "session.scheduled_activation_skipped",
        reason="not_validated",
        ...
    )
    session.scheduled_activate_at = None  # one-shot
    return
activate_session(...)
```

A skipped schedule is **one-shot** — `scheduled_activate_at` is
cleared on the skip. The operator validates and re-schedules;
this avoids a stale schedule firing days later after a
re-validation the operator didn't expect.

**Manual Activate inside the window.** If the operator clicks
Activate at 8:30am for a 9am scheduled session, `activate_session`
runs immediately **and clears `scheduled_activate_at`** in the
same transaction (a one-line side effect on the existing
service). The 9am trigger fires on a `ready` session, sees
`scheduled_activate_at = NULL`, and no-ops.

**Right-column signals (Workflow card).** The Workflow card's
right column (the "Activate" column) captions the scheduled
activation per session state:

| Session state | `scheduled_activate_at` | Right-column caption |
|---|---|---|
| `draft` | unset | (none — Activate button stays disabled) |
| `draft` | set, in future | **Amber warning** — "Scheduled activation at «9am Mon Jun 1» — currently inactive: Prepare session before then or the schedule will skip." |
| `draft` | set, in past (after skip) | **Amber-grey skipped notice** — "Scheduled activation at «9am Mon Jun 1» skipped — session was not validated." (rendered once after the skip; clears on next operator interaction) |
| `validated` | unset | (none — Activate button live, no schedule caption) |
| `validated` | set, in future | **Green calm caption** — "System will auto-activate at «9am Mon Jun 1». You can also click Activate now." |
| `ready` | (any — moot post-activation) | Existing "Activated at «X»" treatment; no schedule caption. |

The captions integrate into `spec/workflow_card.md` "Right
column — per state" when this Part ships; until then the spec
flags the integration point.

**Schema / audit / dependencies.**

- Schema: `sessions.scheduled_activate_at` (Part 0a, shipped) —
  the scheduled `validated → ready` trigger. Add a B-tree index
  in this Part (the scheduler queries it by value).
- Audit events: `session.activation_scheduled` (`changes`
  envelope, when the operator sets / changes / clears the
  scheduled time); `session.scheduled_activation_skipped`
  (`reason` + `context.scheduled_at`, when fire-time guard
  skips); the existing `session.activated` event covers both
  manual and scheduled-trigger activations (a
  `context.trigger="scheduled"` adds the provenance).
- A scheduled trigger calls `session_lifecycle.activate_session`
  at `scheduled_activate_at`; an explicit operator "Activate now"
  stays available (it already exists).
- **Depends on 18F Part 2** for the reviewer-facing states: the
  pre-open page ("scheduled to open at «scheduled_activate_at» —
  come back later") reads the `scheduled_activate_at` this part
  adds. 18F Part 2 builds the states; this part supplies the
  scheduled time.
- Establishes the **shared dispatch mechanism** Parts 2–5 reuse —
  whichever pattern the segment settles on (background worker or
  lazy observer extended to additional anchors) lands here first.

#### Part 1 PR breakdown

**PR 1A — Observer scaffolding** (pure infra; no operator-visible
behaviour).

- New `app/services/scheduled_events.py` module: the lazy-observer
  skeleton (`observe_scheduled_events(session)`), the
  `resolve_offset(session, anchor_field, offset_field)` helper
  (§8.2.2), and the SELECT … FOR UPDATE + idempotency guard
  pattern (§8.3). No triggers wired yet — just the framework.
- Hook the observer call into the session-GET path used by
  Session Home, Operations pages, and the Sessions lobby
  (existing `_session_home.get_session_detail` / equivalents).
- Unit tests for `resolve_offset` (anchor-null, valid duration,
  invalid duration), the SELECT-FOR-UPDATE concurrency guard
  (two concurrent triggers; second no-ops), and the
  observer-hook integration (empty session → no-op).
- Audit-event registration in `EVENT_SCHEMAS` for the family
  pattern (`*_skipped` / `*_retry` / `*_failed_persistent` /
  `*_fired`).
- No migration; no editor change; no UI change.

**PR 1B — Scheduled-activation trigger** (service + index +
audit; still no operator-visible UI).

- Add `_observe_scheduled_activation(session)` to the
  `scheduled_events` module: precondition check, retry counter
  from audit log (`session.scheduled_activation_retry` count for
  the current scheduled-fire moment), the
  3-retries-then-`failed_persistent` policy, and the success
  path that calls `lifecycle.activate_session(...)` with
  `context.trigger="scheduled"`.
- New audit events:
  `session.scheduled_activation_skipped` (with
  `reason=<not_validated|...>`),
  `session.scheduled_activation_retry`,
  `session.scheduled_activation_failed_persistent`.
- `session.activated` event grows `context.trigger ∈ {operator,
  scheduled}` (default `operator` for backwards compat).
- Migration `xxxx_segment_18g_pr1b_scheduled_activate_at_index.py`
  adds a B-tree index on `sessions.scheduled_activate_at` (the
  observer queries it by value when the lazy-observer pass is
  extended to scan-many-sessions, even though the per-session
  observer only reads one row).
- Tests: fire happy path (validated → ready), skip path
  (still-draft → skipped), retry path (transition raises 3
  times → failed_persistent), the `context.trigger` provenance,
  the audit-log-derived retry counter.
- Still no operator-visible UI — but operators who
  hand-edit `scheduled_activate_at` (via a future light-up or
  the sys-admin route) will see scheduled activations fire.

**PR 1C — Start editor wiring + Workflow card signals**
(operator UX: light up the field on the Create / Edit forms
and the right-column captions on the Workflow card).

- Editor: enable the `scheduled_activate_at` input on
  `session_new.html` and `session_edit.html` (currently a
  disabled placeholder per the 2026-05-21 batch). The
  `_quick_setup.py` (Create) and `_session_home.py` (Edit)
  routes parse the field and write it via `update_session`
  (already iterates over a column-set list — add the column
  there).
- New `SCHEDULED_OPERATIONAL_LEAD_HOURS` setting in
  `app/config.py` (default `1`). Save-time validator:
  `if scheduled_activate_at and scheduled_activate_at - now() <
  timedelta(hours=...)` → `HTTP 422` with the documented error
  string ("Scheduled activation must be at least N hours in
  the future").
- Audit event: `session.activation_scheduled` (`changes`
  envelope) when the operator sets / changes / clears the
  value via the editor.
- View / template: extend `views._workflow_card.build_workflow_card`
  (or the equivalent right-column-aside builder) with the
  scheduled-activation caption per the state × value table in
  the Part 1 plan section above. Visual treatment per the
  amber-warning / amber-grey-skipped / green-calm captions.
- Session Home banner: when the most recent audit event is
  `session.scheduled_activation_skipped` or
  `session.scheduled_activation_failed_persistent`, the page
  shows a top-of-page banner ("Scheduled activation skipped at
  «X» — reason: «reason»"). Clears on next operator
  interaction.
- Tests: editor save accepts a valid future time, rejects past
  / too-soon times; the `session.activation_scheduled` audit
  fires on set / change / clear; the right-column caption
  renders per session state × value; the Session Home banner
  appears after a skip and clears.

Dependencies: PR 1A → PR 1B → PR 1C in order (1B's index
migration and audit-event registration are needed before
1C's editor writes them).

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
- **Precondition (`spec/lifecycle.md` §8.2.3).** Invitations must
  already have been **created** (the operator ran "Create
  invitations") at fire time. Without `Invitation` rows there's
  nothing to send. Fire-time guard: skip with
  `reason="invitations_not_created"`, audit
  `session.scheduled_invites_skipped`, clear the relevant
  offset entry (per-entry one-shot via the
  `(session_id, offset_index)` dedup key).
- **Signals (Manage Invitations card).**
  - Precondition not met (invitations not generated yet) —
    **amber warning**: "Auto-send scheduled at «earliest fire»
    — currently inactive: create invitations before then or
    these will skip."
  - Precondition met (invitations generated) — **green calm
    caption**: "Auto-send scheduled at «earliest fire», «next
    fire», … System will dispatch automatically; you can also
    Send all now."
  - Editor save errors surface inline on the invite-offsets
    field per the rules below.
- **Save-time rules for `invite_offsets`.** Both
  `SCHEDULED_OPERATIONAL_LEAD_HOURS` and
  `REVIEWER_NOTICE_MIN_HOURS` (Part 1 — defaults 1 hour each)
  apply. For each offset entry the editor checks (a) `Start +
  offset ≥ now + SCHEDULED_OPERATIONAL_LEAD_HOURS` and (b)
  `|offset| ≥ REVIEWER_NOTICE_MIN_HOURS`. Violations surface
  per-entry, e.g. "Auto-send invite −PT30M gives only 30
  minutes between invite and Start; minimum reviewer notice
  is 1 hour. Choose -PT1H or larger."
- Depends on **18F Part 2** relaxing the invitation gate so
  invitations can be sent before activation, and on **Part 1**
  surfacing `scheduled_activate_at` as a configurable operator input.

#### Part 2 PR breakdown

**PR 2A — Auto-send invitations trigger** (service + audit
events; still no editor change beyond the disabled placeholder).

- Add `_observe_scheduled_invites(session)` to
  `scheduled_events`: resolve each `invite_offsets[i]` against
  `scheduled_activate_at`, check the precondition (invitations
  created — i.e. `session.invitations` is non-empty), and fire
  on each entry whose resolved moment ≤ `now()`. Per-entry
  dedup keyed on `(session_id, offset_index, scheduled_fire_at)`
  from the audit log — re-ordering the list doesn't re-fire a
  consumed entry.
- The fire path calls the existing `send_invitations` /
  `send_all` service (operator-triggered path today) with a
  `context.trigger="scheduled"` marker on the resulting outbox
  rows + audit events.
- New audit events:
  `session.scheduled_invites_skipped` (with `reason` +
  `context={"offset_index": …}`),
  `session.scheduled_invites_fired` (carrying the
  scheduled-fire moment AND the actual-fire moment so
  late-fires from observer lag are observable).
- Migration: B-tree index on `sessions.invite_offsets` is **not
  added** — JSON columns aren't usefully indexed for value
  queries. The observer reads per-session, so no scan-many
  index is needed.
- Tests: happy fire path (per entry), skip on missing
  invitations, the per-entry dedup, the late-fire scheduled-vs-
  actual stamps, the `context.trigger` provenance, the
  catch-up behaviour (multiple past-due entries fire in
  chronological order on a single observer pass).

**PR 2B — invite-offsets editor + Manage Invitations signals +
timeline preview** (operator UX for Auto-send).

- Editor (`session_new.html` / `session_edit.html`): enable the
  `invite_offsets` input as a multi-entry control. Initial UX:
  comma-separated text input parsed into a JSON list at save
  ("`-P1D, -PT2H`"); per-entry validation surfaces the
  documented error strings. A richer add/remove-row editor can
  follow as 18H polish if needed.
- New `REVIEWER_NOTICE_MIN_HOURS` setting in `app/config.py`
  (default `1`). Save-time validator runs the per-entry rules
  (operational lead, reviewer-notice gap) against the (possibly
  freshly-changed) `scheduled_activate_at`.
- Audit event: `session.invite_schedule_updated` (`changes`
  envelope) when the operator sets / changes / clears the
  list.
- Manage Invitations card captions: amber when invitations not
  yet created, green when created — per the per-entry table in
  Part 2's plan section.
- Schedule timeline preview: a read-only block beneath the
  inputs on `session_new.html` / `session_edit.html` rendering
  resolved fire moments in chronological order (the §"Editor
  timeline preview" item in the coordination section). New
  helper `views.build_schedule_timeline(session)` returns the
  list of `(at, label)` rows; the template renders the block.
- Tests: editor save round-trips a non-empty list, rejects
  rule-violating entries per-entry, the
  `session.invite_schedule_updated` audit fires; the Manage
  Invitations captions render per (precondition met / not met);
  the timeline preview renders when both fields are set and
  sorts chronologically.

**PR 2C — Cross-Part coordination + manual-activate cancellation
modal** (the five behaviours from the Part 1 ↔ Part 2
coordination section).

- Edit-Start re-resolution: the `update_session` write path
  (or the route layer) runs the `invite_offsets` save-time
  rules against the new anchor on every save where
  `scheduled_activate_at` changes. Per-entry errors surface
  inline as today.
- Unset-Start warning: when the operator submits a save that
  clears `scheduled_activate_at` while `invite_offsets` is
  non-empty, the editor surfaces an inline info caption ("Auto-
  send invites will become inactive — no Start to anchor
  against. They reactivate when Start is re-set.") — no hard
  block.
- Manual-activate confirmation modal: the existing Activate
  button (Workflow card right column) grows a confirmation
  modal when `invite_offsets` is non-empty (or
  `scheduled_activate_at` is set). The modal lists pending
  auto-sends ("Sun May 31 9:00 AM, Mon Jun 1 7:00 AM") and the
  text "N scheduled auto-send(s) will be cancelled. Continue
  with manual activation?" The submit path is
  `POST /operator/sessions/{id}/workflow/activate` as today;
  on success it clears `scheduled_activate_at` (the existing
  Part 1 behaviour). `invite_offsets` stays in the column but
  becomes inert (anchor-null).
- Scheduled-activate catch-up: the observer's existing
  ordering (fire invites before activation in the same pass)
  is verified end-to-end in a test that sets up a 48-hour
  window where no operator visits, then renders Session Home —
  expects both `session.scheduled_invites_fired` and
  `session.activated` events in chronological order.
- Tests: each of the five coordination behaviours has a
  dedicated test case. Modal markup is asserted via
  `httpx.TestClient.get` against the Workflow card render.

Dependencies: PR 1B + PR 1C → PR 2A; PR 2A + PR 1C → PR 2B;
PR 2B → PR 2C. PR 2A can land before 1C if needed (no operator
UI required), but 2B and 2C need both 1C and 2A.

### Part 1 ↔ Part 2 coordination

Start and Auto-send share an anchor relationship and a tight
chronology — `invite_offsets` is anchored on
`scheduled_activate_at`, and the save-time rules tie the two
fields' valid ranges together. Five coordination behaviours,
all shipped together with Part 2:

**1. Editing Start re-resolves all `invite_offsets`.** Every
save-time rule re-runs against the new anchor. If any offset
now violates the per-entry rules (operational lead, reviewer
notice gap), the editor errors per-entry on save. The operator
fixes the conflicting entries or moves Start before they can
save.

**2. Unsetting Start while `invite_offsets` is non-empty.** No
hard block at save — `invite_offsets` becomes inert via the
§8.2.2 anchor-null rule. The editor surfaces an inline warning
beneath the invite-offsets field: "Auto-send invites will
become inactive — no Start to anchor against. They reactivate
when Start is re-set." Same warning in reverse when
`scheduled_activate_at` is set but `invite_offsets` is emptied
(no impact, just an info caption: "Auto-send schedule cleared;
Start remains scheduled for «X»").

**3. Manual-activate before the scheduled time.** When the
operator clicks Activate manually for a session with
`scheduled_activate_at` and a non-empty `invite_offsets`:

- `activate_session` runs immediately and clears
  `scheduled_activate_at` in the same transaction.
- `invite_offsets` stays in the column but becomes inert
  (anchor-null). Any past-due `invite_offsets` entries that
  hadn't fired (no operator visit between their resolved fire
  moment and now) are **not** caught up — the operator uses
  Send all manually to dispatch invitations going forward.
- The Activate button's confirmation modal includes, when
  `invite_offsets` is non-empty: "N scheduled auto-send(s) will
  be cancelled. Continue with manual activation? You can use
  Send all to dispatch invitations after activation."

**4. Scheduled-activate catches up past-due `invite_offsets`.**
When the observer fires at the scheduled Start time and the
session is still `validated`, the same observer pass also
sweeps any past-due `invite_offsets` entries (in chronological
order) before firing activation. Missed invites land alongside
activation as a final batch — this is just the lazy-observer
default ("fire everything overdue on each visit"), not a
special coordination path. Reviewers may receive the invite
later than the operator originally targeted; the
`session.scheduled_invites_fired` audit event carries both the
scheduled-fire moment and the actual-fire moment.

**5. Editor timeline preview.** When both `scheduled_activate_at`
and `invite_offsets` are set, the editor renders a read-only
**Schedule timeline** block beneath the inputs, listing the
resolved fire moments in chronological order:

```
Schedule timeline (Asia/Singapore):
  Sun May 31  9:00 AM — Auto-send invites fire (-P1D)
  Mon Jun  1  7:00 AM — Auto-send invites fire (-PT2H)
  Mon Jun  1  9:00 AM — Session activates (Start)
```

The operator can sanity-check the chronology before saving.
The same primitive extends to Parts 3 / 4 / 5 entries when
those land, so the timeline gradually becomes the full
session-lifecycle visualisation.

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
- **Preconditions (`spec/lifecycle.md` §8.2.3).**
  `session.status == "ready"` + invitations exist + within the
  accepting-responses window. Fire-time guard: skip with
  `reason="not_ready"` or `"no_invitations"`,
  `session.scheduled_reminder_skipped` audit event, per-entry
  one-shot via the same `(session, reviewer, offset_index)`
  dedup key the dispatch job uses. The Email Template editor /
  Session Home cadence card surfaces "Auto-reminders scheduled
  at «…» — currently inactive: activate the session before then
  or these will skip" when the session isn't `ready` yet.
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
  trigger is new.
- Schema: `sessions.archive_offset` (Part 0b). Inert when
  `deadline` is unset per the cross-cutting anchor-null rule.
- **Precondition (`spec/lifecycle.md` §8.2.3).**
  `session.status == "draft"` (18A's locked `draft ⇄ archived`
  archive model). A running `ready` session must be reverted to
  draft first. Fire-time guard: skip with `reason="not_draft"`,
  `session.scheduled_archive_skipped` audit event, clear the
  offset (one-shot). The Sessions lobby surfaces "Auto-archive
  scheduled at «X» — currently inactive: revert the session to
  draft before then or this will skip" when the session is
  still `ready` at fire time.
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
  past its archive timestamp.
- **Precondition (`spec/lifecycle.md` §8.2.3).**
  `session.status == "archived"`. The archive timestamp itself
  is the anchor, so a not-yet-archived session has neither anchor
  nor precondition. Fire-time guard: skip with
  `reason="not_archived"`, `session.scheduled_purge_skipped`
  audit event. The Sessions lobby archived child page surfaces
  the active vs not-yet-effective state on each archived row.
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
