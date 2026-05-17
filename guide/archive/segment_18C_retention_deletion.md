# Segment 18C — Operator-triggered purge

> **Status: shipped 2026-05-17** (PR #1123) — the "Purge and
> archive" expander action + `app/services/session_purge.py`.
> See `docs/status.md`. Plan archived; kept as the
> design-of-record.
>
> **Stub created 2026-05-11; re-scoped 2026-05-17.** Originally
> "Retention / deletion workflow", spanning both operator-triggered
> *and* scheduled / policy-driven purge. The **scheduled** half —
> per-deployment retention policy, per-session overrides, the
> scheduled worker — moved to **Segment 18F — Scheduled events**
> (`guide/segment_18F_scheduled_events.md`, Part 4). 18C now owns
> only the **operator-triggered** purge: explicit, immediate
> "delete just these rows" actions an operator runs by hand.

## Goal

Give operators **selective hard-delete** of a session's data —
finer-grained than today's only sub-session option (none: the
sole deletion path is the whole-session Danger Zone delete).
Three purge operations, offered together as a **"Purge and
archive"** action on the Sessions-lobby row expander:

- **Purge responses** — hard-delete every `response` + `invitation`
  row for the session. Assignments and all setup retain.
- **Purge rosters** — hard-delete reviewers + reviewees +
  relationships. Because assignments / responses / invitations
  carry foreign keys onto the rosters, those cascade out too;
  instruments, RTDs, display / response fields and settings
  retain. Reverts the session to a "setup skeleton with no
  people".
- **Purge audit log** — hard-delete every `audit_event` row for
  the session.

All three are **hard-deletes, no undo** (soft-delete stays out
of scope — see below).

## Why now

- **§21 #16** "Basic retention/deletion workflow" is the only
  MVP acceptance criterion not even partially satisfied in
  `guide/codebase_assessment_11may.md`; Weakness #2 names the
  gap. Operator-triggered purge closes the operator-facing half.
- Segment 18A shipped the Sessions-lobby inline row expander and
  `draft ⇄ archived` archiving. "Purge and archive" composes
  directly onto that surface — the operator is already there to
  archive a finished session; offering "and purge X while you're
  at it" needs no new page.

## Delivery — the "Purge and archive" expander action

The single-session and bulk Sessions-lobby expanders today carry
an **Archive** / **Archive all** button (posts the ticked
`session_ids` to `/operator/sessions/archive-selected`) and an
**Allow delete** confirm checkbox gating the Delete button.

18C extends that row:

- The **Archive** / **Archive all** button is renamed **"Purge
  and archive"**.
- Immediately after the **Allow delete** checkbox, inline: the
  label **"Archive after purging"** followed by three
  checkboxes — **Responses**, **rosters**, **audit log**.
- **No purge checkbox ticked** → the action archives exactly as
  wired today (plain `archive_session`, no deletes).
- **One or more ticked** → for each ticked session the selected
  purges run *first*, then `archive_session`.

Archiving stays **draft-only** (18A's locked `draft ⇄ archived`
model), so "Purge and archive" only acts on draft sessions; a
non-draft session ticked in a bulk selection is skipped whole
(no purge, no archive), exactly as `archive-selected` skips it
today.

### Purge order and the audit log

When more than one purge is selected they run in a fixed order
so the audit trail of *this* action survives:

1. **Audit log** first — deletes every pre-existing
   `audit_event` row, then emits its own
   `session.audit_log_purged` event (which therefore survives).
2. **Responses**, then **rosters** — each emits its event.
3. **`archive_session`** — emits `session.archived`.

So after a full purge-and-archive the audit log holds a clean
record of just the action that produced the current state.

## Service shape

A new `app/services/session_purge.py`:

- `purge_responses(db, *, review_session, user, correlation_id)`
  — FK-safe delete of `responses` then `invitations`; emits
  `session.responses_purged` (`counts` envelope).
- `purge_rosters(db, *, ...)` — FK-safe cascade: `responses`,
  `invitations`, `assignments`, `relationships`, then
  `reviewers` + `reviewees`; emits `session.rosters_purged`.
- `purge_audit_log(db, *, ...)` — delete `audit_events` for the
  session; emits `session.audit_log_purged` *after* the delete.

The FK-safe delete order mirrors the explicit pre-delete pattern
in `sessions.delete_session`. Each emitter is registered in
`audit.EVENT_SCHEMAS`.

The `/operator/sessions/archive-selected` route grows optional
`purge` form values; the bulk-tags-style "buttons carry the
choice" pattern is not needed — the three checkboxes submit
their own names.

## Hard dependencies

- **Segment 18A** — the Sessions-lobby inline expander and
  `archive_session` (both shipped).

## Out of scope

- **Scheduled / policy-driven retention** — per-deployment
  retention policy, per-session overrides, the scheduled worker.
  Moved to **Segment 18F — Scheduled events** Part 4.
- **Soft-delete** (mark-deleted, retain in DB). Every purge here
  is a hard-delete; soft-delete is a bigger schema change and a
  separate ask. The `archived` lifecycle state covers the
  closest-to-soft-delete case for whole sessions.
- **Cross-session purge** ("every session's responses older
  than X"). 18C is per-session and operator-triggered; a
  cross-session sweep would be a Sys Admin / 18F concern.
- **Outbox + email-audit rows.** "Purge responses" deletes
  `responses` + `invitations` only; `email_outbox` rows and the
  `email.sent` / `email.send_failed` audit rows are left
  (the audit rows go anyway if "purge audit log" is also
  ticked).

## Doc impact

When it ships:

- `docs/status.md` timeline entry; `guide/todo_master.md`.
- `guide/codebase_assessment_11may.md` §21 #16 flips ❌ → ⚠️/✅;
  Weakness #2 closes (operator-facing half).
- `spec/sessions_overview.md` — the expander's "Purge and
  archive" action + the three purge checkboxes.
- `spec/architecture.md` — the `session.responses_purged` /
  `session.rosters_purged` / `session.audit_log_purged`
  audit-event envelopes.

## Working notes

- _(placeholder for decisions during PR scoping)_
- **Purge rosters is a superset of purge responses.** Both
  delete `responses` + `invitations`; ticking both is harmless
  (the second purge finds the rows already gone).
- **No re-type confirmation.** The earlier stub floated a
  GitHub-style "re-type the session code" gate. With the action
  living on the expander behind the existing **Allow delete**
  checkbox — and the purges only running as part of an
  already-deliberate archive — a single confirm checkbox is the
  gate. Revisit if pilot feedback wants more friction.
