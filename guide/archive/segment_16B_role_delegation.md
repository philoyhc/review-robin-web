# Segment 16B — User role management + role delegation among operators

> **Archived 2026-05-11.** PR 1 + PR 2 shipped 2026-05-11 (PRs
> **#853 / #854 / #855**); PR 3 (per-session role granularity)
> retired from the roadmap — the binary owner-or-not model is
> the deliberate final shape and revisits only on pilot
> feedback. The plan stays here as historical context for the
> shipped surface.
>
> Sys Admin page itself + the sys-admin authorization gate live
> in **16A** (`guide/archive/segment_16A_sys_admin_page.md`);
> the in-app audit viewer lives in **16C**
> (`guide/archive/segment_16C_richer_audit_views.md`).

**Sizing:** 2 MVP PRs (shipped as one); PR 3 retired.
**Depends on:** **16A PR 1 + PR 6** (shipped — the
operator-allowlist gate + the admit/revoke surface that
populates the eligible pool). 16A PR 1 lit up
`users.is_operator`; 16B picks the admit-pool query off it.

## What shipped (2026-05-11)

- **PR #853** — single combined slice covering both the
  service surface and the UI. New `app/services/session_owners.py`
  with `list_owners` / `workspace_operator_candidates` /
  `add_owner` / `remove_owner` + `OwnerOperationError`
  (codes: `last_owner`, `not_in_workspace`, `already_owner`,
  `not_owner`). Two audit events registered:
  `session.owner_added` / `session.owner_removed` (snapshot
  + refs envelope, `refs.target_user_id` for the target).
  Two new routes: `POST /sessions/{id}/owners/add` (form
  takes `target_email`; case-insensitive email lookup) and
  `POST /sessions/{id}/owners/{user_id}/remove`. The edit
  page + the two owner routes share
  `require_sys_admin_or_session_operator` — a relaxed gate
  that lets a sys-admin reach the edit page of a session
  they don't own (they self-add as owner via the form, then
  act via the normal `require_session_operator` path).
  Sessions Diagnostics row's "Operators" placeholder
  retires; "Details" link to `/edit` replaces it.
- **PR #854** — race fix on last-owner remove. Codex review
  flagged a TOCTOU between count + delete; replaced with
  `SELECT ... FOR UPDATE` over the session's
  `session_operators` rows, then count + locate + delete
  from the locked snapshot.
- **PR #855** — chrome polish: `(sys admin)` suffix on the
  top-right "Signed in as ..." label so sys-admins can tell
  at a glance they're running with elevated workspace
  privileges. Applied to both operator chrome (`base.html`)
  and the reviewer top bar.

**Scope deltas from the original plan:**

- **PR 1 + PR 2 collapsed into one slice.** The service
  surface is small and the UI is a thin wrapper; landing
  them separately would have been ceremony.
- **Surface placement moved from Session Home to the Edit
  page** (`/operator/sessions/{id}/edit#owners`). The edit
  page is where session-identity edits already concentrate,
  and the Diagnostics "Details" link wants a single landing
  page that doubles as the sys-admin self-add surface.
- **Picker submits `target_email`, not `target_user_id`.**
  The HTML5 `<datalist>` typeahead is a presentation layer
  only; submitting the email keeps the form robust to typos
  / unlisted entries and lets the backend normalise the
  lookup. The `not_in_workspace` error code covers both "no
  such user" and "user isn't on the allowlist".
- **Session-creator immunity replaced with the simpler
  last-owner guard.** The original plan special-cased the
  creator row (couldn't be removed while sole owner). The
  ship-as-is rule is: any owner can be removed *unless*
  they're the last remaining owner. Cleaner invariant, no
  awkward "(creator)" badge to maintain.
- **Actor-owner check lives at the route layer, not the
  service.** PR 1's original wording required
  `session_owners.add_owner` / `remove_owner` to enforce
  "actor is an owner on the session" inside the service.
  What shipped: the service only validates target state;
  actor authority is gated entirely at the route via
  `require_sys_admin_or_session_operator`. This is the
  deliberate final shape — the relaxed gate intentionally
  lets sys-admins act without owning the session (they
  self-add first via the same form). Service-level
  enforcement was dropped to keep the gate decision in one
  place. Read the per-PR pre-condition bullets below in
  that light: they're historical scope, not the shipped
  invariant.
- **PR 3 (per-session role granularity) retired from the
  roadmap.** Binary `"owner"` is the deliberate final shape.
  The PR 3 section below is historical only — `viewer` /
  `deputy` / role-picker UI / `require_session_role` split
  will not ship without explicit pilot-feedback demand.

---

## Goal

Give a session's current owners a UI to **add another owner**
to the session (from the workspace-admitted operator pool)
and to remove owners they no longer need.

**Scope split with 16A.** 16A owns the workspace-level
admit / revoke / promote / demote toggles — who's
in the operator pool at all, who's a sys-admin. 16B owns
the per-session "from the admitted pool, who can edit
*this* session" affordance.

Today's gap:

- **`SessionOperator` table exists, no UI to manage it.**
  `app/db/models/session_operator.py` defines per-session
  operator membership; `app.services.permissions.require_session_operator`
  reads it; but every row is inserted today via the
  `create_session` service (the creator becomes the
  inaugural owner with `role="owner"` per the
  Segment 13F PR 1 default fix) with no follow-on add /
  remove affordance. Adding a second owner to an existing
  session is a DB-edit operation.

The functional-spec acceptance criterion **"Role delegation
among multiple operators"** (§22 Expanded release items) is
the canonical scope ask — `guide/archive/codebase_assessment_11may.md`
marks it ⚠️ "table exists; no UI".

## PR ladder

### PR 1 — Operator-membership service helpers + audit registration (~250 LOC)

**Why first.** Service layer before UI keeps the contract
testable in isolation. PR 2's UI is then a thin wrapper.

**Ships.**

- New service helpers in `app/services/permissions.py`:
  - `add_owner(db, session, target_user, *, actor, correlation_id) -> SessionOperator`
    — inserts a `SessionOperator` row with `role="owner"`;
    pre-conditions:
    - `actor` is an owner on the session (i.e. exists in
      `session_operators` with `role="owner"`);
    - `target_user` is in the admitted-operator pool
      (`is_operator OR is_sys_admin`);
    - `target_user` is not already a `session_operators`
      member on this session.
  - `remove_owner(db, session, target_user, *, actor, correlation_id) -> None`
    — deletes the row; pre-conditions:
    - `actor` is an owner on the session;
    - `target_user` is currently a `session_operators`
      member on this session;
    - removing the row leaves ≥1 owner on the session;
    - `target_user.id != session.created_by_user_id` (the
      creator's owner row is non-removable while they're
      the sole owner — they can be demoted only if another
      owner exists).
  - Both helpers emit canonical audit events on success.
- Audit-event registrations in
  `app.services.audit.EVENT_SCHEMAS`:
  - `session.owner_added` — `refs.target_user_id`;
    `actor_user_id` from the session var.
  - `session.owner_removed` — symmetric to above.
- **No lifecycle gate.** Editing the owner list is an
  access-control change, not a setup mutation —
  `invalidate_if_validated` does not fire. Sessions in any
  lifecycle state can have their owner list edited.

**Tests.**

- Happy path: add / remove owner, audit event emitted with
  correct envelope.
- Pre-condition violations:
  - Actor isn't an owner on the session → 403-shaped
    error.
  - `target_user` not in the admitted-operator pool → 409
    ("not an admitted operator").
  - `target_user` already an owner → 409.
  - Remove the session creator while sole owner → 409.
  - Remove the last owner → 409.
- Sys-admin who isn't `is_operator=True` is still in the
  eligible pool (regression on the `is_operator OR
  is_sys_admin` predicate).
- `EVENT_SCHEMAS` strict-mode gate passes for both new
  event types.

### PR 2 — Owners card on Session Home (~400 LOC)

**Ships.**

- New "Session owners" card on Session Home (in the right
  column near Session Details — decide exact slot at
  scoping). Lists current owners with display name + email
  + per-row "Remove" button. The session creator row
  carries a "(creator)" badge sourced from
  `sessions.created_by_user_id`.
- Add-owner form: typeahead `<input list>` + `<datalist>`
  populated server-side from the **admitted-operator pool
  minus current session operators** — i.e. the set of
  `users` rows where `(is_operator OR is_sys_admin) AND
  NOT EXISTS (SELECT 1 FROM session_operators ...)`. The
  picker is the safest write affordance under Option C:
  it forecloses both "they haven't signed in" and "they
  aren't admitted" failure modes by simply not offering
  unviable choices.
- Per-row Remove: single-click confirm (no two-step
  type-the-email). Absent for the session creator's row.
  Service-layer guard refuses if removal would leave zero
  owners.
- New routes:
  - `POST /operator/sessions/{id}/owners` → add.
  - `POST /operator/sessions/{id}/owners/{user_id}/remove`
    → remove.
- View adapter `views.build_session_owners_card(session,
  user) -> SessionOwnersContext` returns both the current
  owners list and the eligible-pool dropdown options.
- **Race-condition handling.** If the picked user is no
  longer admitted by the time the POST lands (a sys-admin
  revoked them between page render and form submit), the
  PR 1 service-layer pre-condition fails — return 409 with
  copy: "<email> is no longer an admitted operator. Ask
  the sys-admin to re-admit, or pick a different
  colleague."

**Tests.**

- Renders the owners card for an operator-user; absent for
  non-operator (covered by existing `require_session_operator`
  gate).
- Picker pool excludes users already on the session.
- Picker pool excludes non-admitted users
  (`is_operator=False AND is_sys_admin=False`).
- Picker pool **includes** sys-admins even with
  `is_operator=False` (since sys-admin implies operator).
- Pick + Add → 303 + new row visible on re-render + audit
  event emitted.
- Revoke race → 409 with helpful copy.
- Remove → row gone + audit event emitted.
- Session creator's Remove button absent.
- Remove-last-owner → 409.

### PR 3 (post-MVP) — Per-session role granularity (~400 LOC)

**Defer until pilot feedback confirms binary
operator-or-not is insufficient.** Adds richer per-session
role granularity beyond the current binary model.

**If it lands, ships:**

- Schema: `session_operators.role` column already exists
  (`String(32)`, NOT NULL, model default `"owner"` post-13F
  PR 4). The value-set constant
  `SESSION_OPERATOR_ROLES = ("owner", "manager")` was locked
  in 13F PR 1; this slice widens it (e.g. to add `"viewer"`)
  via a deliberate Python edit, no migration.
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

- **16A PR 1** — the operator-allowlist gate. PR 2's picker
  queries `users WHERE is_operator OR is_sys_admin`; without
  that gate the pool isn't a meaningful set.
- **16A PR 6** — the workspace admit / revoke UI. PR 2's
  picker is meaningfully empty until a sys-admin admits
  more operators beyond the bootstrap set; revoke is the
  inverse affordance.
- **13F PR 1** (shipped) — `session_operators.role`
  value-set lock + `"owner"` default. PR 1's `add_owner`
  writes `role="owner"`; the locked value-set keeps the
  service-layer write-path honest.

## Out of scope

- **Workspace admit / revoke / promote / demote** — that's
  16A PR 6. 16B is per-session only.
- **Sys Admin page chrome** — 16A PR 2.
- **The in-app audit viewer** for "who added whom as an
  owner when" — that's 16C (the `session.owner_added` /
  `.owner_removed` events emitted in PR 1 are read by 16C's
  surface).
- **Reviewee-as-user** flows — reviewees aren't `users`
  rows today and don't get operator permissions. Out of
  scope for this segment.

## Doc impact

When PRs ship:

- `docs/status.md` timeline entry per PR.
- `guide/todo_master.md` updated.
- `spec/architecture.md` — identity / permissions section
  picks up the per-session owner-membership UI + the
  picker-from-admitted-pool pattern.
- `spec/settings_inventory.md` — `SessionOperator` row
  gains a cross-reference to the new UI.
- `spec/audience_and_identity_model.md` — operator
  audience picks up the "owners add other owners from the
  admitted pool" affordance.
- `spec/session_home.md` — Session Home gains the Session
  owners card.

## Working notes

- _(placeholder for decisions during PR scoping)_
- Session owners card: confirmed on Session Home (right
  column near Session Details). Sub-page
  (`/operator/sessions/{id}/access`) deferred unless the
  card outgrows the slot.
- Picker affordance: typeahead `<input list>` + `<datalist>`
  is the lightest-touch fit; revisit if N admitted operators
  exceeds a comfortable dropdown size (~50).
- Should the lobby surface a "you've been added to N
  sessions" hint when an admitted operator gets pulled onto
  a new one? Probably not in PR 2's scope; nice-to-have for
  pilot polish.
