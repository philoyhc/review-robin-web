# Permissions and authorization

**Current as of 2026-09-05 (`36e7b1e7`).** The authorization
contract — *who may reach which route, what happens when they may
not, and what a change of role or ownership must leave behind*. The
altitude is the gate and the route family: which dependency guards
which surface, and with what status code.

What this file is **not**: the audience taxonomy and the reasoning
behind the three-tier role model live in
`spec/audience_and_identity_model.md` §4 (the highest-ranking doc
on identity / audience decisions); the running-system security
review — permission and destructive-action matrices, CSRF posture,
identity-header mechanics, deferred hardening — is
`docs/security_posture.md`. This spec sits between them: it states
the contract those two documents assume, and it is the file the
`diff-reviewer` should open when a route's gate changes.

Identity itself (who the signed-in user *is*) is resolved by
`app/auth/identity.py` from the Easy Auth headers and is out of
scope here; every gate below starts from an already-authenticated
`AuthenticatedUser`.

---

## 1. Principals and roles

Three workspace-level roles, strictly nested, plus one per-session
membership:

| Role | Stored as | Granted by | Revoked by |
|---|---|---|---|
| **Operator** | `users.is_operator` | env bootstrap on first sign-in (`OPERATOR_EMAILS`), or an admin's *Admit* | an admin's *Revoke* (refused while the user still owns any session) |
| **Admin** (`sys_admin`) | `users.is_sys_admin` | env bootstrap (`SYS_ADMIN_EMAILS`), or a **super-admin's** *Promote* | a super-admin's *Demote* (refused for the last admin) |
| **Super-admin** | *derived*, never stored — email ∈ `SUPER_ADMIN_EMAILS` (`app/auth/roles.py::is_super_admin`, case-insensitive) | deployer config only | deployer config only; no in-app path may demote, revoke or remove one |
| **Session owner** | a `session_operators` row (`role="owner"`) | session create (the creator), clone (the cloner), an owner's *Add owner*, or a sys-admin's audited self-add | an owner's *Remove owner* (refused for the last owner) |

**Nesting.** Every gate treats admin as implying operator
(`is_operator OR is_sys_admin`), and a super-admin **self-heals** to
both flags on every sign-in (`deps._reassert_super_admin`), so
super-admin ⊇ admin ⊇ operator holds at every gate without
special-casing. A super-admin is a *protected identity*: the
`protected_super_admin` guard refuses demote / revoke / remove /
detach-from-sessions against one, above and independent of the
count-based `last_admin` floor.

**Bootstrap contract.** The env allowlists seed the two Boolean
columns **once**, on the row's first creation in `get_or_create_user`.
After that the columns are authoritative: removing an email from the
env var does **not** auto-revoke, and every later change is an
audited in-app action on the Accounts Management page. Super-admin is
the exception — being config-derived, it can neither drift from the
env var nor be flipped in-app.

**Fake-auth fold-in (local dev only).** When `ALLOW_FAKE_AUTH=true`,
`FAKE_AUTH_OPERATOR` / `FAKE_AUTH_SYS_ADMIN` grant the fake identity
those flags on first sign-in, and `FAKE_AUTH_SUPER_ADMIN` folds the
fake email into the effective super-admin set. All three are inert
in a deployed environment, where `allow_fake_auth` must be false.

**`session_operators`.** Unique on `(session_id, user_id)`.
`role` is one of `SESSION_OPERATOR_ROLES = ("owner", "manager")`,
gated at the service write path (no DB CHECK); only `"owner"` is
written today — `"manager"` is reserved. Every per-session operator
gate reduces to *"does a row exist for this user and this session"*
(`permissions.user_can_view_session`), and the lobby lists exactly
the sessions the user has a row for (`sessions.list_for_user`).

---

## 2. Gate catalogue

All gates are FastAPI dependencies in `app/web/deps.py`. Each is
listed with its predicate, what it returns on success, and exactly
what happens on failure. A `log.warning("permission denied", gate=…)`
is emitted on every miss.

| Gate | Predicate | Returns | On miss |
|---|---|---|---|
| `get_or_create_user` | signed in with an email claim | `User` (created on first sight; case-insensitive lookup, oldest match wins) | **401** if the principal carries no email |
| `require_operator` | `is_operator OR is_sys_admin` | `User` | raises `OperatorAllowlistDenied` → the handler in `app/main.py` **303s to `/me`** (deliberately not a 403 — the arrival is more often a misrouted legitimate user than an attacker; the "how do I get access" copy lives on `/about`) |
| `require_sys_admin` | `is_sys_admin` | `User` | **403** `sys_admin required` |
| `require_session_operator` | a `session_operators` row for (user, `{session_id}`) | `ReviewSession`; also stamps the session's display timezone on `request.state` | **403** `You do not have access to this session`; **404** if the session id does not resolve *for this user* (the membership check runs first, so a non-member sees 403, never a 404 that leaks existence) |
| `require_sys_admin_or_session_operator` | `is_sys_admin`, else falls through to `require_session_operator` | `ReviewSession` | as above; a sys-admin gets **404** on an unknown id |
| `require_relationships_enabled_session` / `require_observers_enabled_session` | wraps `require_session_operator`, then the per-session feature toggle | `ReviewSession` | **404** when the feature is off — a deep link to a disabled tab misses cleanly rather than rendering an orphan page. The permission check still runs first |
| `require_reviewer_in_session` | an **active** `Reviewer` row in the session whose email matches the signed-in email (case-insensitive) | `(Reviewer, ReviewSession)` | **404** unknown session; **403** `You are not an active reviewer in this session` |
| `require_reviewee_in_session` | an **active** `Reviewee` row whose `email_or_identifier` *parses as an email* and matches | `(Reviewee, ReviewSession)` | as above (`… active reviewee …`). A confidential reviewee (non-email identifier) can never reach the surface, by construction |
| `require_observer_in_session` | an **active** `Observer` row whose email matches | `(Observer, ReviewSession)` | as above (`… active observer …`) |

Two things the table implies and the code relies on:

- **Roster status is part of the predicate.** A reviewer, reviewee
  or observer whose row is anything other than `"active"` fails the
  gate, so inactivating a roster row is a revocation.
- **Every participant gate is email-identity, never token.** The
  invitation token (`/me/invite/{token}`) is a *landing* route
  gated only by `get_or_create_user`: it looks the invitation up by
  `sha256(token)` (404 if unknown), compares the invitation's
  reviewer email to the signed-in email (403 page on mismatch),
  stamps `opened_at`, and 303s to the reviewer surface — which then
  applies `require_reviewer_in_session` itself. A token grants
  nothing on its own.

---

## 3. Per-route matrix

| Route family | Gate | How mounted |
|---|---|---|
| **every** `/operator/*` route | `require_operator` | router-level dependency on the `routes_operator` package — no operator route can opt out |
| session-scoped operator routes `/operator/sessions/{session_id}/…` | `require_session_operator` | per route, directly or via the two feature-toggle wrappers. **128 of 128** such routes carry one (counted 2026-09-05 by scanning every `@router.get/post` decorator under `routes_operator/` whose path begins `/sessions/{session_id}`) |
| the two **relaxed** session routes: `POST …/owners/add`, `POST …/clone` | `require_sys_admin_or_session_operator` | a non-owner sys-admin may reach them; `owners/add` additionally enforces **self-only** for a non-owner in its handler (`self_only` error otherwise); `clone` makes the cloner owner of the copy, leaving the original untouched |
| lobby bulk routes (tags / archive / bulk-delete) | `require_operator` + per-id re-resolution | each client-supplied `session_id` is re-resolved with `sessions.get_for_user`; non-owned ids are skipped, never acted on |
| `/operator/sys-admin/*` (13 routes: root redirect, Sessions Diagnostics, per-session Outbox + Audit log children, Accounts Management, adopt, and the seven user actions) | `require_sys_admin` | per route |
| `GET …/export/audit_log.csv` | `require_sys_admin` | the one session-scoped export that is *not* owner-reachable — tightened in Segment 16C PR 1 when the operator-facing entry point retired |
| reviewer surface, save / submit / clear, post-submit summary | `require_reviewer_in_session` | per route |
| `/me/sessions/{id}/results` (+ acknowledge) | `require_reviewee_in_session` | per route |
| `/me/sessions/{id}/collation` (+ CSV) | `require_observer_in_session` | per route |
| `/me` dashboard, `/me/invite/{token}`, `/` | `get_or_create_user` only | any signed-in user; `/me` renders an empty dashboard for a user with no roles; `/` **302s by role** — operator or sys-admin → `/operator/sessions`, everyone else → `/me` (never 301: the target follows a role that can change) |
| `/about`, `/auth/me`, `/auth/me/debug` | `get_current_user` only (no `users` row created) | identity display and diagnostics |
| bare `/operator`, `/operator/` | none | a 302 to the lobby, deliberately unguarded so that one place — the lobby's `require_operator` — decides operator access |
| `/health` | none | liveness only |

**Sys-admin does not mean edit access.** Since Segment 18S Item 3 a
sys-admin can *read* any session's diagnostics (Outbox, Audit log)
but every session **mutation** — config, lobby rename / tag, owner
removal, every Setup and Operations action — is behind
`require_session_operator`, i.e. real ownership. The elevation door
is `POST /operator/sys-admin/sessions/{id}/adopt`: it self-adds the
sys-admin as an owner (audited `session.owner_added`, idempotent) and
redirects to the session's Home, after which the normal operator
path applies. There is no unrecorded route from "can see" to "can
edit".

**Client-supplied ids are never trusted as authority.** Child-id
routes re-scope the child to the gated session
(`_require_instrument_in_session` and the per-roster
`_require_*_in_session` helpers → 404 on a cross-session id); the
reviewer `save` / `submit` handlers build the assignment index from
the authenticated reviewer's own assignments, so a foreign
`assignment_id` in a form body is dropped, not written. The route-by-
route audit of this is `docs/security_posture.md` §5.6.

---

## 4. Role and ownership operations

All role changes go through `app/services/users.py`, all ownership
changes through `app/services/session_owners.py`. Routes trust the
`require_sys_admin` / `require_session_operator` gate and the
services re-check nothing about the *actor's* gate — they enforce
the **invariants** below and raise a coded error the route maps to a
status.

### 4.1 Accounts Management (`/operator/sys-admin/users`)

| Action | Actor must be | Guards (in order) | Audit event |
|---|---|---|---|
| Admit | admin | `self_action` | `workspace.operator_admitted` |
| Revoke | admin | `self_action`, `protected_super_admin`, `still_owner` (target owns ≥1 session — detach first) | `workspace.operator_revoked` |
| Promote | **super-admin** (`requires_super_admin`) | `self_action`, `requires_super_admin` | `sys_admin.role_promoted` |
| Demote | **super-admin** | `self_action`, `requires_super_admin`, `protected_super_admin`, `last_admin` (target is the only admin) | `sys_admin.role_demoted` |
| Remove from all sessions | admin | `self_action`, `protected_super_admin`, `sole_owner` (target is the only owner of some session) | `workspace.user_detached_from_all_sessions` |
| Delete user | admin | `self_action`, `protected_super_admin`, `last_admin`, `owns_sessions` | `workspace.user_removed` |
| Invite (pre-seed a `users` row before first sign-in) | admin | `invalid_email`, `duplicate` (case-insensitive) | `workspace.user_invited` |

**No-super-tier fallback (18S Item 2).** `requires_super_admin`
engages only once a super-admin actually exists in the effective
set; with `SUPER_ADMIN_EMAILS` empty (and no fake-auth fold-in) any
admin may promote / demote, as before 18S. This keeps a deployment
that never configures the top tier from locking itself out of admin
management.

**Self-action is refused outright** (`self_action`), not merely for
the dangerous cases: an admin cannot admit, revoke, promote or
demote *themselves*, nor delete or detach their own row — the route
returns **400** and the page hides the buttons on the actor's own
row. The recovery path for "I demoted myself" is therefore "ask
another admin", never a self-service one.

### 4.2 Session ownership

| Action | Route | Gate | Guards | Audit event |
|---|---|---|---|---|
| Add owner | `POST /operator/sessions/{id}/owners/add` (Session Home config card, edit mode) | `require_sys_admin_or_session_operator` | `not_in_workspace` (target lacks both flags — admit them first), `already_owner`; handler-level `self_only` for a non-owner sys-admin | `session.owner_added` |
| Remove owner | `POST …/owners/{user_id}/remove` | `require_session_operator` | `not_owner`, `last_owner` (would leave zero owners; the owner set is locked `FOR UPDATE` before counting so two concurrent removals cannot both pass) | `session.owner_removed` |
| Adopt (sys-admin self-add) | `POST /operator/sys-admin/sessions/{id}/adopt` | `require_sys_admin` | idempotent; `already_owner` swallowed | `session.owner_added` |

The creator is inserted as the inaugural owner inside
`sessions.create_session`; a clone inserts the cloner as owner of the
new session (`session_clone`). Self-removal is allowed when another
owner remains.

---

## 5. Failure semantics

The status codes a client sees, by cause. Gates are in §2; these are
the operation-level mappings.

| Cause | Status | Where mapped |
|---|---|---|
| Not on the operator allowlist | **303 → `/me`** | `OperatorAllowlistDenied` handler, `app/main.py` |
| Not a sys-admin; not a session member; not an active participant | **403** with a one-line `detail` | the gate |
| Unknown session / child id, disabled feature tab, unknown invite token | **404** | the gate or route |
| Missing email claim | **401** | `get_or_create_user` |
| `self_action` | **400** | `_sys_admin._handle_toggle` |
| `requires_super_admin` | **403** | same |
| `last_admin`, `owns_sessions`, `still_owner`, `sole_owner`, `protected_super_admin` | **409** | same |
| `last_owner` on remove-owner | **409** | `_session_home.session_owners_remove` |
| every other owner error (`not_in_workspace`, `already_owner`, `not_owner`, `self_only`) | **303** back to Session Home with `?owners_error=<code>` | same |
| Lifecycle refusals (`_require_editable`, `not_draft`, `locked`, …) | **409** (or 400 for missing acknowledgements) | `_shared.py`; contract in `spec/lifecycle.md` |

---

## 6. Audit

Every operation in §4 writes exactly one canonical audit event
(envelope contract: `spec/architecture.md` "Audit-event detail
schema"; all nine `event_type`s above are registered in
`EVENT_SCHEMAS`). Reads never audit; denied requests log a warning
but write no event. `docs/security_posture.md` §5.7 is the
destructive-action ledger that confirms each mutating route carries a
confirm + a gate + an event.

---

## 7. Tests

The denial paths are covered by name; the files are the place to add
a case when a gate changes.

| Contract | Test file |
|---|---|
| allowlist bootstrap, case-insensitive match, once-only seeding, super-admin self-heal, fake-auth toggles, revoked-operator redirect | `tests/integration/test_operator_allowlist_gate.py` (21) |
| participant-only user bounced from lobby + per-session route; workspace operator non-owner 403 + lobby exclusion; sys-admin reaches another owner's session only via adopt | `tests/integration/test_operator_lobby_access_gate.py` (6) |
| owner add / remove invariants, last-owner 409, self-remove, sys-admin self-add via the relaxed gate | `tests/integration/test_session_owners.py` (19) |
| the seven Accounts Management actions and every guard code | `tests/integration/test_sys_admin_users.py` (48) |
| super-admin resolver (config membership, fake fold-in) | `tests/unit/test_roles_super_admin.py` (6) |
| audit-log CSV is sys-admin-only | `tests/integration/test_outbox_sys_admin_relax.py` (4) |
| reviewer gate 403s (other session, inactive row) and foreign `assignment_id` dropped | `tests/integration/test_reviewer_response_flow.py` |

---

## 8. Drift noted at writing (2026-09-05)

Recorded rather than silently rewritten, per the spec-writer charter.

- `spec/rrw_functional_spec.md` §17 listed four gates and described
  the reviewer gate as "email match *or* a valid invitation token".
  The code has six gates and the token never grants access (§2 here).
  §17 is corrected in the same change as this file.
- `spec/audience_and_identity_model.md` §4b placed the Owners card
  on `/operator/sessions/{id}/edit`; since Segment 18R Item 4 it is
  the Session Home config card in edit mode (`?editing=1
  #config-owners-card`). Corrected alongside.
- `app/db/models/user.py` still says `is_sys_admin` gates "Manual
  assignment upload"; that route retired 2026-05-11 (16A PR 5). Code
  comment, not spec — left for a code change.

---

## 9. Cross-references

- `spec/audience_and_identity_model.md` §4 / §4b — the three-tier
  model's rationale, the who-can-manage-whom matrix, owner delegation.
- `docs/security_posture.md` — §5.6 permission audit, §5.7
  destructive-action audit, denial-path coverage table, identity
  trust model, CSRF posture, deferred hardening.
- `spec/lifecycle.md` — the edit-lock guards that sit *after* the
  permission gates on mutating routes.
- `spec/operator_ui_concept.md` "Sys Admin" — the Accounts Management
  and Sessions Diagnostics surfaces.
- `spec/settings_inventory.md` — `OPERATOR_EMAILS` /
  `SYS_ADMIN_EMAILS` / `SUPER_ADMIN_EMAILS` and the fake-auth knobs.
- `guide/archive/segment_16A_sys_admin_page.md` (Option C
  strict-allowlist posture), `guide/archive/segment_18S_security.md`
  (three tiers, protected super-admin, ownership tightening).
