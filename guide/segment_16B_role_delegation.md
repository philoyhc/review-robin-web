# Segment 16B — User role management + role delegation among operators

> **Carved out of the original Segment 16 (2026-05-11).** The
> Sys Admin page itself + the sys-admin authorization gate live
> in **16A** (`guide/segment_16A_sys_admin_page.md`); the
> in-app audit viewer lives in **16C**
> (`guide/segment_16C_richer_audit_views.md`).

**Status:** Planning — stub created 2026-05-11, sized into
a four-PR ladder 2026-05-11 (PRs 1-2 MVP; PR 3 conditional;
PR 4 post-MVP).
**Sizing:** 2 MVP PRs + 1 conditional PR + 1 post-MVP PR.
**Depends on:** **none for PRs 1-2.** PR 3 hard-deps on 16A
adopting Option A or B; under Option C (env-allowlist —
the current 16A recommendation), PR 3 is skipped entirely.

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

## PR ladder

### PR 1 — Operator-membership service helpers + audit registration (~250 LOC)

**Why first.** Service layer before UI keeps the contract
testable in isolation. PR 2's UI is then a thin wrapper.

**Ships.**

- New service helpers in `app/services/permissions.py`:
  - `add_operator(db, session, target_user, *, actor, correlation_id) -> SessionOperator`
    — inserts a `SessionOperator` row; pre-conditions:
    `actor` must already be an operator on the session;
    `target_user` must not already be an operator;
    `target_user` must exist in `users` (i.e. has signed
    in before).
  - `remove_operator(db, session, target_user, *, actor, correlation_id) -> None`
    — deletes the row; pre-conditions: `actor` is an
    operator; `target_user` is an operator; the operator
    being removed is not the session creator (the creator
    row stays load-bearing); the operator list will still
    have ≥1 row after removal.
  - Both helpers emit canonical audit events on success.
- Audit-event registrations in
  `app.services.audit.EVENT_SCHEMAS`:
  - `session.operator_added` — `refs.target_user_id`,
    `actor_user_id` from the session var, `reason="added"`
    optional context slot.
  - `session.operator_removed` — symmetric to above.
- **No lifecycle gate.** Editing the operator list is an
  access-control change, not a setup mutation —
  `invalidate_if_validated` does not fire. Sessions in any
  lifecycle state can have their operator list edited.

**Tests.**

- Happy path: add / remove operator, audit event emitted
  with correct envelope.
- Pre-condition violations:
  - Adding a user who isn't an operator-actor → 403-shaped
    error.
  - Adding a user who isn't in `users` → 400 ("user must
    sign in first").
  - Removing the session creator → 409.
  - Removing the last operator → 409.
- `EVENT_SCHEMAS` strict-mode gate passes for both new
  event types.

### PR 2 — Operator-membership UI on Session Home (~350 LOC)

**Ships.**

- New "Session operators" card on Session Home (probably
  in the right column near Session Details — decide at
  scoping). Lists current operators with email + a
  per-row "Remove" button.
- Add operator form: email input + Add button. On submit,
  hits the PR 1 helper. Hard-reject if the email doesn't
  match a `users` row, with copy: "<email> hasn't signed
  in yet. Ask them to sign in to the app, then add them
  here." (Simpler than a pending-invitation flow; no new
  column.)
- Remove operator: per-row form with single-click confirm
  (no two-step type-the-email). Disabled (or hidden) for
  the session creator's row.
- New routes in `routes_operator/_session_home.py` (or a
  new slice — decide during scoping):
  - `POST /operator/sessions/{id}/operators` → add.
  - `POST /operator/sessions/{id}/operators/{user_id}/remove`
    → remove.
- View adapter `views.build_session_operators_card(session)
  -> SessionOperatorsContext`.
- Surfaces a small "you're operator on N sessions" hint
  on the Sessions lobby header if N > 1 — **defer to a
  follow-on** if it expands PR 2's scope materially.

**Tests.**

- Renders the operators card for an operator-user; absent
  for non-operator (covered by existing
  `require_session_operator` gate).
- Add by email → 303 + new row visible on re-render +
  audit event emitted.
- Add unknown email → 400 with helpful copy.
- Remove → row gone + audit event emitted.
- Session creator's Remove button absent / disabled.

### PR 3 — Sys-admin promotion UI (~250 LOC) — **conditional**

**Conditional on 16A's auth choice.** Today 16A
recommends **Option C (env-allowlist)**; under Option C, the
env var is the UI and PR 3 is **out of scope** entirely.

PR 3 lands **only if** 16A migrates to:
- **Option A** (Entra app role with an in-app mirror table
  for promotion / demotion), or
- **Option B** (per-user `users.is_sys_admin` boolean).

Until then, this section is a placeholder.

**If Option A or B is chosen, ships:**

- New "Sys-admin roster" section on the Sys Admin page
  (behind the existing sys-admin gate from 16A PR 1).
  Lists every `users` row with the per-user flag; per-row
  Promote / Demote toggle.
- New routes in `routes_operator/_sys_admin.py`:
  - `POST /operator/sys-admin/users/{user_id}/promote`.
  - `POST /operator/sys-admin/users/{user_id}/demote`.
- Confirmation: explicit "I'm promoting <email> to
  sys-admin" / "I'm demoting <email>" checkbox before
  submit (matches 16A PR 4's "I'm overriding the rule
  engine" pattern).
- **Last-admin demotion guard.** Refuses to demote the
  last sys-admin (and refuses self-demotion if you're the
  only sys-admin).
- Audit emitters: `sys_admin.role_promoted` /
  `sys_admin.role_demoted` — `changes` envelope on the
  flag column, `refs.target_user_id`.

**Tests.**

- 403 for non-admin.
- Promote / demote → flag flips + audit event emitted.
- Last-admin-demote → 409 with helpful copy.
- Confirmation checkbox required.

### PR 4 (post-MVP) — Per-session role granularity (~400 LOC)

**Defer until pilot feedback confirms binary
operator-or-not is insufficient.** Adds richer per-session
role granularity beyond the current binary model.

**If it lands, ships:**

- Schema: new `SessionOperator.role` column (`String(32)`,
  default `"operator"`). Initial enum values:
  `operator` / `viewer` / `deputy`. Alembic migration adds
  the column with a default backfill of `"operator"` for
  every existing row.
- Per-role permission predicates:
  - `viewer` — read-only access to every operator page;
    no setup mutations, no lifecycle transitions, no
    Sys Admin chrome.
  - `deputy` — full operator access **except** Activate /
    Pause / Delete-session transitions. The session
    creator + other `operator`-role users retain those.
- PR 2's add / remove UI gains a role-picker
  `<select>` next to the email input.
- Audit-event payload (PR 1 emitters) widens to include
  the role granted / current.
- The existing `require_session_operator` dependency
  splits into `require_session_role(role: str)` /
  `require_setup_edit` / `require_lifecycle_transition` —
  a non-trivial route audit across the operator surface
  to slot the right gate per route.

**Likely deferred indefinitely.** The binary model is
sufficient for most realistic operator populations; richer
delegation is mostly a "compliance / governance" ask that
pilot feedback may or may not surface.

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
