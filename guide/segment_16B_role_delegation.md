# Segment 16B — User role management + role delegation among operators

> **Carved out of the original Segment 16 (2026-05-11).** The
> Sys Admin page itself + the sys-admin authorization gate live
> in **16A** (`guide/segment_16A_sys_admin_page.md`); the
> in-app audit viewer lives in **16C**
> (`guide/segment_16C_richer_audit_views.md`).

**Stub. Sketch-level scope only.** Detailed PR breakdowns get
drafted when this segment is picked up.

## Goal

Give operators a UI to **delegate** session access to other
operators and to **promote / demote** the sys-admin role
(once 16A lands and the role exists).

Today's gaps:

- **`SessionOperator` table exists, no UI to manage it.**
  `app/db/models/session_operator.py` defines per-session
  operator membership; `app.services.permissions.require_session_operator`
  reads it; but every row is inserted today via the
  `create_session` service (the creator becomes operator)
  with no follow-on add / remove affordance. Adding a second
  operator to an existing session is a DB-edit operation.
- **No sys-admin promotion UI.** Whatever 16A chooses for the
  sys-admin role (Entra app role / per-user flag / env
  allowlist), promoting someone today is a deployment / Entra-
  side operation, not an in-app one.

The functional-spec acceptance criterion **"Role delegation
among multiple operators"** (§22 Expanded release items) is
the canonical scope ask — `guide/codebase_assessment_11may.md`
marks it ⚠️ "table exists; no UI".

## Scope (sketch)

### Part 1 — Per-session operator membership UI

**Goal.** A small operator-facing surface for "who else can
operate this session?"

Likely shape:

- New card / section on Session Home (or under Session Details
  / a new "Access" sub-page — decide at scoping time): list of
  current operators with Add / Remove affordances.
- Add operator flow: type an email; if the email matches an
  existing `users` row, insert a `SessionOperator` row; if it
  doesn't, decide between (a) reject with "user must sign in
  first" or (b) write an `invited_email`-shaped pending row.
  Lean (a) for MVP — simpler, no new column.
- Remove operator flow: per-row Remove button with confirm.
  The session creator cannot be removed (or, if removable,
  another operator must exist; lock at scoping time).
- Audit emitters: `session.operator_added` /
  `session.operator_removed` using the canonical envelope
  (`refs` for the affected user; `reason` for the actor's
  motive if captured).
- Lifecycle gate: editing operator membership does **not**
  invalidate `validated` — it's an access-control change, not
  a setup mutation. Sessions in any lifecycle state can have
  their operator list edited.

### Part 2 — Sys-admin promotion UI

**Goal.** If 16A ships with Option B (per-user
`users.is_sys_admin` boolean) or Option A (Entra app role
+ in-app mirror table), expose a workspace-level UI for
flipping the flag.

If 16A ships with Option C (env-allowlist) instead, Part 2 is
**out of scope** — the env var is the UI, and 16B Part 1 is
the only meaningful work here. Revisit Part 2 when 16A
migrates from C → A or C → B.

Likely shape (only relevant under 16A Option A or B):

- New section on the Sys Admin page (lives behind the
  sys-admin gate itself) — list of every `users` row with the
  per-user role flag; per-row Promote / Demote toggle.
- Audit emitters: `sys_admin.role_promoted` /
  `sys_admin.role_demoted` (`changes` envelope with the actor +
  target).
- Confirmation: explicit "I'm promoting <email> to sys-admin"
  checkbox before submit (matches 16A's "I'm overriding the
  rule engine" pattern).
- Guard: a sys-admin cannot demote themselves if they're the
  last sys-admin (avoid lockout).

### Part 3 — Role delegation polish (post-MVP)

**Goal.** Beyond add / remove, give operators a way to assign
narrower per-session roles (read-only viewer? deputy operator
who can edit setup but not activate?).

Likely shape (deferred — confirm need before scoping):

- New column or join table for per-session role
  (`role ∈ {operator, viewer, deputy}` or similar). The
  current `SessionOperator` table is binary — exists or not.
- Per-role permission checks layered on top of
  `require_session_operator` (currently a binary gate).
- Audit-event payload widening to include the role granted.

Likely deferred. The binary "you're an operator on this
session" model is probably sufficient for the first pilot;
revisit when richer delegation is a real ask.

## Hard dependencies

- **16A** for Part 2 (and for the sys-admin gate on Part 1's
  emitters if some are sys-admin-only). Part 1 itself can ship
  independently — `SessionOperator` rows are operator-visible
  per-session, not sys-admin-scoped.

## Out of scope

- The Sys Admin page itself — that's 16A.
- The in-app audit viewer for "who added whom as an operator
  when" — that's 16C (the operator-added / removed events
  emitted in Part 1 are read by 16C's surface).
- **Reviewee-as-user** flows — reviewees aren't `users` rows
  today and don't get operator permissions. Out of scope for
  this segment.

## Doc impact

When parts ship:

- `docs/status.md` timeline entry per Part.
- `guide/todo_master.md` updated.
- `spec/architecture.md` — identity / permissions section
  picks up the per-session operator membership UI.
- `spec/settings_inventory.md` — `SessionOperator` row gains a
  cross-reference to the new UI.
- `spec/audience_and_identity_model.md` — operator audience
  picks up the "operators are added / removed by other
  operators" affordance.

## Working notes

- _(placeholder for decisions during PR scoping)_
- Per-session operator card: lives on Session Home or as its
  own sub-page (e.g. `/operator/sessions/{id}/access`)? Lean
  Session Home for discoverability.
- Email-based Add: hard-reject vs pending-invitation flow.
  Lean hard-reject for MVP.
- Should Part 1 surface a "you've been added to N sessions"
  banner on the operator's lobby? Probably not in this
  segment; nice-to-have.
