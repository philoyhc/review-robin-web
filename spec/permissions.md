# Permissions and authorization

The authorization contract — *who may reach which route, what
happens when they may not, and what a change of role or ownership
must leave behind*. The altitude is the gate and the route family:
which dependency guards which surface, and with what status code.

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
| **Admin** (`sys_admin`) | `users.is_sys_admin` | env bootstrap (`SYS_ADMIN_EMAILS`), or a **super-admin's** *Promote* or *Invite* with the chip on `Invite as sys-admin` | a super-admin's *Demote* (refused for the last admin, and while a user with no Operator flag still owns any session) |
| **Super-admin** | *derived*, never stored — email ∈ `SUPER_ADMIN_EMAILS` (`app/auth/roles.py::is_super_admin`, case-insensitive) | deployer config only | deployer config only; no in-app path may demote, revoke or remove one |
| **Session owner** | a `session_operators` row (`role="owner"`) | session create (the creator, plus any co-owners named on Create's Owners card), clone (the cloner), an owner's *Add owner*, or a sys-admin's audited self-add | an owner's *Remove owner* (refused for the last owner) |

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

All gates are FastAPI dependencies in `app/web/deps.py`, except the
two feature-toggle wrappers, which live in
`app/web/routes_operator/_shared.py`. Each is listed with its
predicate, what it returns on success, and exactly what happens on
failure. The `deps.py` gates emit a
`log.warning("permission denied", gate=…)` when they refuse a
signed-in user.

| Gate | Predicate | Returns | On miss |
|---|---|---|---|
| `get_or_create_user` | signed in with an email claim | `User` (the oldest row with the identity's Entra object id, moved to a changed email — audited as `workspace.user_email_changed`; a row already holding that email that was never signed in to (an invite) is absorbed, flags OR'd and memberships moved, audited as `workspace.user_absorbed`; one that was signed in to leaves both rows as they are; failing that, a case-insensitive email lookup, oldest match wins, recording the object id on a row that has none; else created) | **401** if the principal carries no email, or if there are no identity headers and fake auth is off |
| `require_operator` | `is_operator OR is_sys_admin` | `User` | raises `OperatorAllowlistDenied` → the handler in `app/main.py` **303s to `/me?notice=organizers`** (deliberately not a 403 — the arrival is more often a misrouted legitimate user than an attacker; the "how do I get access" copy lives on `/about`) |
| `require_sys_admin` | `is_sys_admin` | `User` | **403** `sys_admin required` |
| `require_session_operator` | a `session_operators` row for (user, `{session_id}`) | `ReviewSession`; also stamps the session's display timezone on `request.state` | **404**, bare — for a non-member *and* for an id that does not resolve, so the two are indistinguishable and session ids cannot be enumerated. **Exception:** a **sys-admin** (hence super-admin) who is not an owner of an *existing* session gets **403** `You are not an owner of this session…`, pointing at the adopt door; an absent id still answers 404 |
| `require_sys_admin_or_session_operator` | `is_sys_admin`, else falls through to `require_session_operator` | `ReviewSession` | as above; a sys-admin gets **404** on an unknown id |
| `require_relationships_enabled_session` / `require_observers_enabled_session` | wraps `require_session_operator`, then the per-session feature toggle | `ReviewSession` | **404** when the feature is off — a deep link to a disabled tab misses cleanly rather than rendering an orphan page. The permission check still runs first |
| `require_reviewer_in_session` | a session that is not `archived`, and an **active** `Reviewer` row in it whose email matches the signed-in email (case-insensitive) | `(Reviewer, ReviewSession)` | **404**, bare — unknown session and "not an active reviewer" answer identically |
| `require_reviewee_in_session` | a session that is not `archived`, and an **active** `Reviewee` row whose `email_or_identifier` *parses as an email* and matches | `(Reviewee, ReviewSession)` | as above. A confidential reviewee (non-email identifier) can never reach the surface, by construction |
| `require_reviewee_with_current_grant` | wraps `require_reviewee_in_session`, then `visibility_policies.reviewee_has_current_grant` | `(Reviewee, ReviewSession)` | **404**, bare — a reviewee with nothing currently granted is indistinguishable from a stranger |
| `require_observer_in_session` | a session that is not `archived`, and an **active** `Observer` row whose email matches | `(Observer, ReviewSession)` | as above |

Two things the table implies and the code relies on:

- **Roster status is part of the predicate.** A reviewer, reviewee
  or observer whose row is anything other than `"active"` fails the
  gate, so inactivating a roster row is a revocation.
- **Every participant gate is email-identity, never token.** The
  invitation token (`/me/invite/{token}`) is a *landing* route
  gated only by `get_or_create_user`: it looks the invitation up by
  `sha256(token)` (404 if unknown, its reviewer is inactive, or its session is
  archived),
  compares the invitation's reviewer email to the signed-in email
  (403 page on mismatch), stamps `opened_at`, and 303s to the
  reviewer surface — which then
  applies `require_reviewer_in_session` itself. A token grants
  nothing on its own.

---

## 3. Per-route matrix

| Route family | Gate | How mounted |
|---|---|---|
| **every** `/operator/*` route | `require_operator` | router-level dependency on the `routes_operator` package — no operator route can opt out |
| session-scoped operator routes `/operator/sessions/{session_id}/…` | `require_session_operator` | per route, directly or via the two feature-toggle wrappers. **Every** such route carries one. Checking it means following `Depends()` **transitively**: a decorator scan alone reports false positives, because several routes in `_instruments.py` are gated two levels deep through `Depends(_require_instrument_in_session)` and never name `require_session_operator` in their own signature. *A check that flags a correctly-gated route is worse than none, because the next reader believes it.* |
| the two **relaxed** session routes: `POST …/owners/add`, `POST …/clone` | `require_sys_admin_or_session_operator` | a non-owner sys-admin may reach them; `owners/add` additionally enforces **self-only** for a non-owner in its handler (`self_only` error otherwise); `clone` makes the cloner owner of the copy and leaves the original's setup untouched, but writes `session.duplicated` on the original's audit trail naming the actor and the copy (`refs.clone_session_id`, `context.clone_code`, `context.mode`), so a non-owner sys-admin's full Duplicate, which carries the roster the original's roster page would refuse them, is on the original's own trail (read by a sys-admin, like every audit trail) |
| lobby bulk routes (tags / archive / bulk-delete, and the Archived page's bulk-unarchive / bulk-delete-archived) | `require_operator` + per-id re-resolution | each client-supplied `session_id` is re-resolved with `sessions.get_for_user`; non-owned ids are skipped, never acted on |
| `/operator/sys-admin/*` (root redirect, Sessions Diagnostics, per-session Outbox + Audit log children, Accounts Management, adopt, and the per-user actions) | `require_sys_admin` | per route |
| `GET …/export/audit_log.csv` | `require_sys_admin` | the one session-scoped export that is *not* owner-reachable: there is no operator-facing entry point to it |
| reviewer surface, save / submit / recall / clear, post-submit summary + `summary.csv` | `require_reviewer_in_session` | per route |
| `/me/sessions/{id}/results` (+ acknowledge) | `require_reviewee_with_current_grant` | per route — composes the roster gate with `visibility_policies.reviewee_has_current_grant`; both the GET and the acknowledge POST share it |
| `/me/sessions/{id}/collation` (+ CSV) | `require_observer_in_session` | per route |
| `/me` dashboard, `/me/invite/{token}`, `/`, `/about`, `/guide` | `get_or_create_user` only | any signed-in user; `/me` renders an empty dashboard for a user with no roles; `/` **302s by role** — operator or sys-admin → `/operator/sessions`, everyone else → `/me` (never 301: the target follows a role that can change); `/about` is the "signed in but no access" landing; `/guide` **303s to `/about`** for a viewer with no Guide audience |
| bare `/me/sessions/{id}` | none | a 303 to `/me/sessions/{id}/1`, whose handler applies `require_reviewer_in_session` |
| `/auth/me`, `/auth/me/debug`, `/templates/starter.zip` / `demo.zip` / `full.zip` | `get_current_user` only (no `users` row created) | identity display and diagnostics; the setup-template downloads |
| bare `/operator`, `/operator/` | none | a 302 to the lobby, deliberately unguarded so that one place — the lobby's `require_operator` — decides operator access |
| `/health` | none | liveness only |

**Sys-admin does not mean edit access.** A sys-admin can *read*
any session's diagnostics (Outbox, Audit log)
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
| Demote | **super-admin** | `self_action`, `requires_super_admin`, `protected_super_admin`, `last_admin` (target is the only admin), `still_owner` (target has no Operator flag and owns ≥1 session — the demote would take their operator access) | `sys_admin.role_demoted` |
| Remove from all sessions | admin | `self_action`, `protected_super_admin`, `sole_owner` (target is the only owner of some session) | `workspace.user_detached_from_all_sessions` |
| Delete user | admin | `self_action`, `protected_super_admin`, `last_admin`, `owns_sessions`, `has_history` (target created a session or acted in the audit log; an operator's access is taken away by Revoke) | `workspace.user_removed` |
| Invite (pre-seed a `users` row before first sign-in) | admin; **super-admin** to switch the role chip from `Invite as operator` to `Invite as sys-admin` (it posts `invite_as_sys_admin=true`), a chip the page renders only to an actor who could Promote | `invalid_email`, `duplicate` (case-insensitive), `requires_super_admin` (sys-admin chip only) | `workspace.user_invited` |

**No-super-tier fallback.** `requires_super_admin` engages only
once a super-admin actually exists in the effective set; with
`SUPER_ADMIN_EMAILS` empty (and no fake-auth fold-in) any admin
may promote / demote, and invite as an admin. This keeps a deployment
that never configures the top tier from locking itself out of admin
management.

**Self-action is refused outright** (`self_action`), not merely for
the dangerous cases: an admin cannot admit, revoke, promote or
demote *themselves*, nor delete or detach their own row — the route
returns **400** and the page offers no checkbox on the actor's own
row (it reads `(self)`). The recovery path for "I demoted myself" is therefore "ask
another admin", never a self-service one.

**Bulk actions.** The page acts only on the selection, through the row
expander (`spec/setup_pages.md` § *The row expander*): `POST
/operator/sys-admin/users/bulk-<action>`, `<action>` one of `admit`,
`revoke`, `remove-from-all-sessions`, `promote`, `demote`, `delete`,
taking the repeated `user_ids`, the page's `view` and, for Delete,
`confirm`. Gate `require_sys_admin`; service `users.apply_batch`.

- **All or nothing.** One refusal refuses the batch and nothing
  changes. Every row first takes its own guards from the table above,
  in that order, minus the two counts; Promote adds `not_operator` (the
  row has neither the Operator nor the Admin flag: admit it first). The
  first refusal in row-id order wins.
- **The counts judge the state after the batch.** `last_admin` refuses a
  Demote or Delete that would leave no sys-admin, however many admins
  are selected; `sole_owner` refuses a Remove from all sessions that
  would leave any session with no owner, however many of its co-owners
  are selected. Each names a row involved.
- **What a count reads is locked first,** in id order: the selected
  rows, plus every sys-admin row for Demote and Delete, `FOR NO KEY
  UPDATE` (Delete alone `FOR UPDATE`, since it removes them), and for
  Remove from all sessions the owner rows of every session the selection
  owns, `FOR UPDATE`. The locked rows are re-read, so no guard judges
  a copy loaded earlier in the request. Otherwise two concurrent batches
  each pass the count and both commit. `FOR NO KEY UPDATE` is the mode
  `session_guard` takes on its session row: an audit row's foreign-key
  check doesn't wait on it, so a batch and a concurrent owner removal by
  a selected user can't deadlock.
- **Delete needs `confirm=true`** (the expander's *Yes, delete these*
  tick), else **400**; the button stays disabled until it is ticked.
- **Audit.** Each row writes the event its single-row action writes
  (§6), all under one correlation id.
- **Failure.** Empty selection and `self_action`: **400**. Unknown
  action or an id that matches no account: **404**. `requires_super_admin`
  on Promote / Demote: **403**. Every other refusal is a **303** back to
  the page with the `view` restored and `?toggle_error=<code>&refused=<id>`,
  not the 409 the single-row routes return; the banner reads *Nothing
  changed: <reason>*, the reason naming the refused row's email (every
  reason but `last_admin`'s does). The reason comes from the
  view's own table by code (`views.account_refusal_message`), never from
  the URL, so a link cannot put other words on the page; an unlisted code
  reads the fixed *Couldn't apply that change.*
- **Success** is a **303** that restores the view. A single non-Delete
  row also carries `?selected=<id>`.

The single-row routes (`POST …/users/{user_id}/<action>`) remain and keep
the §5 mapping; the page no longer posts to them.

### 4.2 Session ownership

Full card + staging contract: `spec/session_owners.md`.

| Action | Route | Gate | Guards | Audit event |
|---|---|---|---|---|
| Create's owners | `POST /operator/sessions` | router-level `require_operator` (no session to own yet) | `not_in_workspace` on any staged address — **422**, nothing created | `session.owner_added` per co-owner |
| Add owner | `POST /operator/sessions/{id}/owners/add` | `require_sys_admin_or_session_operator` | `not_in_workspace` (no account matches the address, or it lacks both flags — admit them first), `already_owner`; handler-level `self_only` for a non-owner sys-admin | `session.owner_added` |
| Remove owner | `POST …/owners/{user_id}/remove` | `require_session_operator` | `not_owner`, `last_owner` (would leave zero owners; the owner set is locked `FOR UPDATE` before counting so two concurrent removals cannot both pass) | `session.owner_removed` |
| Adopt (sys-admin self-add) | `POST /operator/sys-admin/sessions/{id}/adopt` | `require_sys_admin` | idempotent; `already_owner` swallowed | `session.owner_added` |

The creator is inserted as the inaugural owner inside
`sessions.create_session`; a clone inserts the cloner as owner of the
new session (`session_clone`). Self-removal is allowed when another
owner remains, and redirects to the sessions lobby. `owners/add` and
`owners/{user_id}/remove` carry no lifecycle check; Session Home's
Owners card posts to them directly, each action saving at once
(`spec/session_owners.md` §2 and §7).

**An owner add and a revoke of the same user can't both commit.** An
owner row's foreign-key check takes only `FOR KEY SHARE`, which passes
a revoke's lock, so every owner-row write first re-reads the user
`FOR SHARE` (`session_owners.lock_owner_eligible`): `add_owner`, and so
Create's owners and Adopt; and the creator on Create, Duplicate and
Rehydrate, who bounce to `/me` as `require_operator` would. A revoke,
single-row or bulk, and a Demote, locks the user row `FOR NO KEY UPDATE`
(a Demote locks every admin row with it, for its `last_admin` count)
before it counts owned sessions, so either the add commits first and `still_owner` counts it,
or it waits and sees the flag cleared. A Create owner revoked, demoted
or deleted between the 422 check and the write is skipped, silently;
the owners staged after them still land (`spec/session_owners.md` §1).

---

## 5. Failure semantics

The status codes a client sees, by cause. Gates are in §2; these are
the operation-level mappings.

| Cause | Status | Where mapped |
|---|---|---|
| Not on the operator allowlist | **303 → `/me?notice=organizers`** | `OperatorAllowlistDenied` handler, `app/main.py` |
| Not a sys-admin | **403** `sys_admin required` | `require_sys_admin` |
| Not a session member; not an active participant; session archived (participant gates) | **404**, bare | `require_session_operator`, `require_reviewer_in_session`, `require_reviewee_in_session`, `require_observer_in_session` |
| Sys-admin, not an owner of an **existing** session | **403** naming the adopt door | `require_session_operator` only |
| Unknown session / child id, disabled feature tab, unknown invite token | **404** | the gate or route |
| No identity headers (fake auth off), or no email claim | **401** | `get_or_create_user` |
| `self_action` | **400** | `_sys_admin._handle_toggle` |
| `requires_super_admin` on Promote / Demote | **403** | same |
| `last_admin`, `owns_sessions`, `has_history`, `still_owner`, `sole_owner`, `protected_super_admin`, on the single-row routes | **409** | same |
| every Invite error (`invalid_email`, `duplicate`, `requires_super_admin`) | **303** back to the page with `?invite_error=<code>`, which renders a banner | `_sys_admin.invite_user` |
| any other Accounts bulk refusal (§4.1) | **303** back with `?toggle_error=<code>&refused=<id>`, which renders a banner | `_sys_admin.bulk_account_action` |
| `last_owner` on remove-owner | **409** (the card disables that Remove, so only a direct POST or a concurrent remove reaches it) | `_session_home.session_owners_remove` |
| every other owner error on `owners/add` / `owners/{user_id}/remove` (`not_in_workspace`, `already_owner`, `not_owner`, `self_only`) | **303** back to `#owners-card` with `?owners_error=<code>` | same |
| `not_in_workspace` on Create's Owners card — checked before the session exists, so nothing is created | **422** | `_quick_setup.create_session` |
| Lifecycle refusals (`_require_editable`, `not_draft`, `locked`, …) | **409** (or 400 for missing acknowledgements) | `_shared.py`; contract in `spec/lifecycle.md` |

**Why every session-scoped refusal is a bare 404.** Splitting them —
404 for "no such session", 403 with a one-line `detail` for "the
session exists but you are not on it" — lets any signed-in person
enumerate session ids, and count them, by reading the status code. It
is the **403** that confirms a session is there, and a `detail` string
(*"You are not an active reviewer in this session"*) confirms it in
prose; a 404 discloses nothing. Content would not leak either way;
existence and count would.

`require_operator` and `require_sys_admin` keep their codes: neither
takes a session id, so neither discloses anything about one.

**The one exemption, and why it is not a hole.**
Overseeing the workspace as a whole *is* the sys-admin role, and
`/operator/sys-admin/sessions` already lists every session by name —
linking each one to `/operator/sessions/{id}`, the route this gate
guards. A 404 therefore conceals nothing from a sys-admin that the app
does not already hand them on a page of their own, while turning a link
that page renders into a dead end. They get the legible refusal instead,
naming the adopt action that is the sanctioned way in.

Two properties keep it narrow. It is **behind an existence check**:
without one the exemption would answer *"you are not an owner of this
session"* for ids that have never existed, turning a refusal into a
confirmation — a worse leak than the bare 404 prevents. And it is
**`require_session_operator` only**: nothing in the app routes a
sys-admin to `/results` or `/collation`, so there is no affordance to
keep legible on the three participant gates, and they answer 404 to
everyone.

---

## 6. Audit

Every operation in §4 writes exactly one canonical audit event,
except an adopt by a sys-admin who already
owns the session, and a Remove from all sessions that finds the user on
no session, which write none (envelope contract:
`spec/architecture.md` "Audit-event detail schema"; every `event_type`
above is registered in `EVENT_SCHEMAS`). Reads never audit; denied
requests log a warning but write no event. `docs/security_posture.md` §5.7 is the
destructive-action ledger that confirms each mutating route carries a
confirm + a gate + an event.

---

## 7. Tests

The denial paths are covered by name; the files are the place to add
a case when a gate changes.

| Contract | Test file |
|---|---|
| allowlist bootstrap, case-insensitive match, once-only seeding, super-admin self-heal, fake-auth toggles, revoked-operator redirect | `tests/integration/test_operator_allowlist_gate.py` |
| participant-only user bounced from lobby + per-session route; workspace operator non-owner 404 + lobby exclusion; sys-admin reaches another owner's session only via adopt | `tests/integration/test_operator_lobby_access_gate.py` |
| session ids are not enumerable: for each of `require_session_operator`, `require_reviewer_in_session`, `require_reviewee_in_session`, `require_observer_in_session`, an existing session the caller holds no role on is byte-identical to an id that does not exist | `tests/integration/test_session_enumeration_gate.py` |
| owner add / remove invariants, last-owner 409, self-remove, sys-admin self-add via the relaxed gate | `tests/integration/test_session_owners.py` |
| every Accounts Management action and guard code | `tests/integration/test_sys_admin_users.py` |
| the Accounts bulk actions: each action, every refusal, the two post-batch counts | `tests/integration/test_sys_admin_accounts_batch.py` |
| an owner add and a revoke of the same user serialize (§4.2): every owner-row write re-reads under the lock, and on Postgres each side waits on the other | `tests/integration/test_owner_add_lock.py`; Rehydrate's in `tests/integration/test_rehydrate_commit_route.py` |
| every route that makes a session takes the owner-add lock first, and only the known services write owner rows | `tests/unit/test_owner_lock_wiring.py` |
| super-admin resolver (config membership, fake fold-in) | `tests/unit/test_roles_super_admin.py` |
| audit-log CSV is sys-admin-only | `tests/integration/test_outbox_sys_admin_relax.py` |
| reviewer gate 404s (other session, inactive row) and foreign `assignment_id` dropped | `tests/integration/test_reviewer_response_flow.py` |

---

## 8. Cross-references

- `spec/audience_and_identity_model.md` §4 / §4b — the three-tier
  model's rationale, the who-can-manage-whom matrix, owner delegation.
- `docs/security_posture.md` — §5.6 permission audit, §5.7
  destructive-action audit, denial-path coverage table, identity
  trust model, CSRF posture, deferred hardening.
- `spec/lifecycle.md` — the edit-lock guards that sit *after* the
  permission gates on mutating routes.
- `spec/operator_ui_concept.md` §6 — the Accounts Management
  and Sessions Diagnostics surfaces.
- `spec/settings_inventory.md` — `OPERATOR_EMAILS` /
  `SYS_ADMIN_EMAILS` / `SUPER_ADMIN_EMAILS` and the fake-auth knobs.
- `guide/archive/segment_16A_sys_admin_page.md` (Option C
  strict-allowlist posture) and
  `guide/archive/segment_18S_security.md` (three tiers, protected
  super-admin, ownership tightening) — the design records behind
  §1 and §4.
