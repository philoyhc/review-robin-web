# Segment 18C — Retention / deletion workflow

> **Stub created 2026-05-11** as part of the Stage 4 guide/
> reorg. Siblings: **18A** (Session cloning,
> `guide/segment_18A_session_cloning.md`) and **18B**
> (Session tagging and archiving,
> `guide/segment_18B_session_tagging_archiving.md`).

**Stub. Sketch-level scope only.** Detailed PR breakdowns
get drafted when this segment is picked up.

## Goal

Close the **retention / purge** gap that's been hanging since
Segment 12B reduced to the audit-events export only. Two
related capabilities:

1. **Policy-driven retention** — a per-deployment (or
   per-session) policy that says "responses older than N days
   get purged" / "audit rows older than M days get purged"
   etc., enforced by a scheduled job.
2. **Operator-triggered purge** — explicit "delete every
   response on this session but keep the setup" or "delete
   every audit row older than X" affordances for operators
   who need to honour a one-off retention obligation.

Today's only deletion path is **whole-session hard-delete**
(the Danger Zone "Delete session" button on Session Home +
Sessions lobby), which cascades to every related row via the
explicit pre-delete pattern in `app/services/sessions.py`.
That's a blunt tool — there's no "delete just the responses"
or "delete just the audit log".

## Why now

- **§21 #16** "Basic retention/deletion workflow" is still
  ❌ in `guide/codebase_assessment_11may.md` — the only MVP
  acceptance criterion not even partially satisfied.
- **§22** "Advanced retention policies" is also ❌ "deferred
  (no current plan owner)".
- **Weakness #2** of the May 11 assessment names this gap
  explicitly: *"Retention / purge tooling deferred. Segment
  12B was re-scoped during the sprint: the audit-log export
  shipped, but the retention/purge piece the original 12B
  plan owned has no current plan file. Functional spec §12.2
  / §12.4 still go unanswered."*
- The original 12B plan's "Audit-events purge / retention
  policy" sub-bullet was deferred with this prescription:
  *"If pilot feedback flips that, it lands in its own
  segment with proper retention-policy + scheduled-job
  design."* — 18C is that segment.

## Scope (sketch)

### Part 1 — Per-session selective purge

**Goal.** Operator-triggered "delete responses but keep
setup" / "delete audit log" / "delete reviewers + reviewees
but keep instruments" affordances, all from the same Danger
Zone surface.

Likely shape:

- New Danger Zone sub-cards on Session Home (or a dedicated
  `/operator/sessions/{id}/retention` page — decide at
  scoping):
  - **Purge responses.** Hard-deletes every `response` row +
    `invitation` row; `assignments` retain; setup retain.
    Triggerable on any lifecycle state ≥ `validated`.
  - **Purge audit log.** Hard-deletes every `audit_event`
    row for this session. Triggerable on any state.
    Confirmation requires re-typing the session code
    (GitHub-repo-delete pattern); no undo.
  - **Purge rosters.** Hard-deletes reviewers + reviewees +
    relationships; instruments retain. Effectively reverts
    the session to "setup skeleton with no people".
- Each action emits its own audit event with the deleted
  row count in a `counts` envelope: `session.responses_purged`,
  `session.audit_log_purged`, `session.rosters_purged`.
- Lives behind 16A's sys-admin gate? Probably yes —
  destructive actions of this scale belong behind the
  diagnostic doorway, not in the everyday operator surface.
  Revisit at scoping.

### Part 2 — Per-deployment retention policy

**Goal.** A scheduled job that enforces a retention policy
defined per-deployment (env var or admin-set settings).

Likely shape:

- Env-var-backed config in `app/config.py`:
  - `RETENTION_RESPONSE_DAYS` (default unset = no auto-purge).
  - `RETENTION_AUDIT_DAYS` (default unset = no auto-purge).
  - `RETENTION_SESSION_ARCHIVED_DAYS` (default unset = no
    auto-purge of archived sessions).
- Scheduled worker (reuses 14B Part C's queue + worker
  scaffold if available; otherwise an Azure Functions timer
  trigger or equivalent).
- Per-batch audit event: `retention.policy_run` with a
  `counts` envelope summarising rows purged per category.
- Manual override: an operator can opt their session **out**
  of the auto-purge via a per-session "Retention exception"
  flag (e.g. for a session under legal hold).

### Part 3 — Per-session retention policy (post-MVP)

**Goal.** Beyond per-deployment defaults, let each session
carry its own policy (e.g. "this session purges responses
after 30 days; the deployment default is 90").

Likely shape (deferred — confirm need with pilot feedback):

- Per-session columns or JSON blob mirroring the env-var
  schema.
- Settings-page editor surface.
- Audit emitter: `session.retention_policy_updated`.

## Hard dependencies

- **14A** (production hardening) for the scheduled-job
  infrastructure if Part 2 reuses it.
- **16A** (Sys Admin gate) if Part 1 lives behind sys-admin
  rather than operator-facing chrome.

## Out of scope

- **Soft-delete** (mark deleted, retain in DB). All purges
  in this segment are hard-deletes; soft-delete would be a
  bigger schema change and a separate ask. The reserved
  `archived` lifecycle state (owned by 18B) covers the
  closest-to-soft-delete use case for whole sessions.
- **Cross-session purge** ("delete every session's responses
  older than X"). 18C is per-session-scoped or
  per-deployment-scheduled-job; cross-session ad-hoc purge
  would be a Sys Admin feature.
- **Backup integration.** Database-level backups are owned
  by 14A's "backup and restore notes". 18C purges run
  against live data; backup retention is a separate concern.

## Doc impact

When parts ship:

- `docs/status.md` timeline entry per Part.
- `guide/todo_master.md` updated.
- `guide/codebase_assessment_11may.md` §21 #16 row flips
  ❌ → ⚠️ / ✅; Weakness #2 closes; §22 "Advanced retention
  policies" row picks up the plan.
- `spec/session_home.md` — Danger Zone card picks up the
  selective-purge sub-cards.
- `spec/architecture.md` — audit-event detail schema picks
  up the new emitters.
- `spec/settings_inventory.md` — retention-policy env vars
  + per-session columns rows added.
- `docs/operations_runbook.md` (when 14A's runbook lands)
  — retention-policy operational pages.

## Working notes

- _(placeholder for decisions during PR scoping)_
- **Operator surface vs sys-admin surface.** Per-session
  selective purge is plausibly an operator-facing action
  (an operator wants to wipe a session's responses without
  destroying the setup template they spent two weeks
  building). But the bulkier "purge audit log" is closer to
  sys-admin territory. Split the surfaces by action?
- **Schedule job home.** 14B Part C ships the bulk-send
  queue + worker; whether 18C Part 2 reuses that worker or
  stands up its own is a 14B-readiness question.
- **Legal-hold override.** Worth a one-line note in the
  pilot operator runbook either way.
- **Cascade depth.** "Purge responses" deletes responses +
  invitations + outbox rows; does it also delete the
  `email.sent` / `email.send_failed` audit rows that
  reference the deleted outbox? Default: yes (the audit
  events were a side-effect of the data we're deleting).
  Confirm during scoping.
