# Segment 16A — Sys Admin page + admin user role

> **Carved out of the original Segment 16 (2026-05-11).** The
> original `segment_16_sys_admin_page.md` bundled three concerns:
> the Sys Admin page itself (this file), user-role management /
> delegation among operators (now **16B**,
> `guide/segment_16B_role_delegation.md`), and richer in-app
> audit views (now **16C**,
> `guide/segment_16C_richer_audit_views.md`).

**Status:** Planning — stub created 2026-05-10, split
2026-05-11, sized into a six-PR ladder 2026-05-11 (revised
from a four-PR ladder after the 2026-05-11 access-model
discussion locked the strict-allowlist Option C posture and
absorbed the workspace user-role-management surface from 16B).
**Sizing:** 6 PRs (each small + reviewable; PRs 2-6 land
sequentially on PR 1 and can ship one per day).
**Depends on:** **13F PRs 1 + 2** for the `users.is_sys_admin`
and `users.is_operator` columns the gates read. PR 4 shipped
2026-05-11; PR 5 pending.

## Goal

Two cohesive halves that together establish the workspace's
access foundation and put every sys-admin-scoped surface
behind one chrome roof:

1. **Access foundation.** Lock down who can use the app at
   all under the **Option C strict-allowlist** posture
   (`users.is_operator` / `users.is_sys_admin`, both shipped
   inert in 13F PRs 1 + 2). A signed-in user not in the
   workspace's operator allowlist hits a "Request access"
   landing page instead of operator routes. The sys-admin
   chrome layers on top.
2. **Sys-admin surfaces.** Three pre-existing dev-diagnostic
   capabilities (Outbox / Audit log / Manual assignment
   upload) move under one chrome roof; one new workspace
   surface (user list with Admit/Revoke + Promote/Demote
   toggles) makes the access foundation self-administering.

## Functional targets

These are the contracts each surface must deliver once
the segment lands. They're independent of how the PRs slice
the work; the PR ladder below explicitly references these
target identifiers (`F1`–`F12`).

### Access foundation

- **F1. Operator gate.** Every operator route gates on
  `is_operator OR is_sys_admin` (the `require_operator`
  dependency). A signed-in user with neither flag is
  redirected to `/request-access` rather than 403-ing — the
  redirect is the deliberate UX choice (gentler for
  misrouted-but-legitimate arrivals).
- **F2. Sys-admin gate.** Every Sys Admin route gates on
  `is_sys_admin` (the `require_sys_admin` dependency).
  Non-admins see no chrome tab and get 403 on direct URLs.
- **F3. Bootstrap from env vars on first sign-in.**
  `get_or_create_user` reads `OPERATOR_EMAILS` and
  `SYS_ADMIN_EMAILS` once, at user-row creation time, and
  sets the respective flags. After that the env vars are
  inert — removing an email from either env var does **not**
  auto-revoke; revocation goes through F6 / F7's UI.
- **F4. Sys-admin implies operator.** A user with
  `is_sys_admin=True AND is_operator=False` still passes
  `require_operator`. The two flags are independent at the
  column level (per 13F PR 2's value-set test); the
  implication is enforced at the predicate.
- **F5. Request-access landing page.** A signed-in user
  who isn't an operator lands on a clean page (no chrome
  navigation that they can't follow). The page surfaces
  their email, a configurable contact line
  (`OPERATOR_CONTACT_EMAIL` env var → `mailto:`; generic
  copy if unset), and a Sign-out affordance.

### Workspace user-role management

- **F6. Admit / Revoke (operator status).** A sys-admin can
  flip `is_operator` for any user via a one-click toggle on
  the workspace user list. Revoking an operator with active
  `session_operators` rows locks them out of those sessions
  but preserves the rows (audit trail intact; re-admit
  restores access naturally without re-adding to sessions).
- **F7. Promote / Demote (sys-admin status).** A sys-admin
  can flip `is_sys_admin` for any user via a confirmed
  toggle ("I'm promoting <email> to sys-admin" /
  symmetric). The last-admin-demote guard refuses to leave
  the workspace without a sys-admin (incl. blocking
  self-demote when sole admin).
- **F8. Auditable workspace toggles.** Every flag flip
  writes a canonical 11K-envelope audit event:
  `workspace.operator_admitted` / `.operator_revoked` /
  `sys_admin.role_promoted` / `.role_demoted`. Each carries
  the actor + target user via the `refs` slot.
- **F9. Workspace user list visibility.** A sys-admin can
  see every `users` row in one table — email, display name,
  first sign-in, `is_operator`, `is_sys_admin`, count of
  sessions the user operates on. Keyset pagination on
  `id DESC` for scale.

### Operational surfaces

- **F10. Outbox under Sys Admin.** The existing
  `GET /operator/sessions/{id}/outbox` surface relocates
  into the Sys Admin chrome. The "View outbox" button on
  Manage Invitations retires; the canonical home is the
  Sys Admin page.
- **F11. Audit log CSV under Sys Admin.** The existing
  `GET /operator/sessions/{id}/export/audit_log.csv` route
  (shipped in 12B PR 1, parked behind the Sys Admin
  doorway in 12B PR 2) gets a Download tile on the
  Sys Admin page. No service code changes — pure chrome
  placement.
- **F12. Manual assignment upload under Sys Admin.** The
  existing `POST /operator/sessions/{id}/assignments/manual/upload`
  route gets a Sys Admin form with an explicit "I'm
  overriding the rule engine" confirmation checkbox + a
  new `sys_admin.manual_assignments_uploaded` audit event
  (`counts` envelope). The dev-only operator path
  (15D PR 6a) stays alive; Sys Admin is the operator-
  reachable home for legitimate bypass cases.

## Anchor items (capabilities already exist)

### 1. Outbox

**Today.** `GET /operator/sessions/{id}/outbox` route
already implemented at `app/web/routes_operator/_operations.py:510-527`
with template `app/web/templates/operator/session_outbox.html`.
Reachable today from a "View outbox" button on the
Manage Invitations page (`session_invitations.html:43`).
Backed by `invitations.list_outbox_for_session(...)` in
the invitations service.

**Under Segment 16A.** Satisfies **F10** — relocation to the
Sys Admin chrome; the "View outbox" button on Manage
Invitations retires. Pure chrome / placement change; service +
template unchanged.

### 2. Manual assignment upload

**Today.** `POST` route at
`app/web/routes_operator/_assignments.py:199` uses
`assignments.parse_manual_csv(...)` to write directly
into the assignments table; also reachable via Quick
Setup slot 3 (`_quick_setup.py:529`). Both paths
exposed in the operator UI.

**Under Segment 15D.** Operator-facing surfaces retire
— Quick Setup slot 3 retires (15D PR 7) and the
Setup-page Assignments form retires (15D PR 6 +
chrome restructure). The underlying
`parse_manual_csv` / `replace_assignments` route +
handler **stay as a dev-only feature** per the
2026-05-10 codebase-check decision (no operator UI;
route + handler accessible for tests + admin
tooling).

**Under Segment 16A.** Satisfies **F12** — the dev-only
manual upload gets a discoverable home on the Sys Admin
page, gated behind an explicit "I'm overriding the rule
engine" confirmation checkbox + a new
`sys_admin.manual_assignments_uploaded` audit event. The
operator-facing alternative (Relationships table →
Generate) stays the everyday path; Sys Admin is the
deliberate-bypass route.

### 3. Audit log download

**Today.** `GET /operator/sessions/{id}/export/audit_log.csv`
route shipped in **Segment 12B PR 1** (2026-05-10) at
`app/web/routes_operator/_extracts.py`. 8-column wide CSV
(`EventType` / `Severity` / `Summary` / `ActorEmail` /
`CorrelationId` / `CreatedAt` / `DetailJson`) with the
canonical Segment 11K detail envelope JSON-encoded in
the trailing column. Backed by
`app.services.extracts.audit_events_extract.serialize_audit_events`,
streamed via `yield_per(1000)`. `session.audit_log_extracted`
audit event registered in `EVENT_SCHEMAS`. The route is
live and reachable directly — but **there is no operator-
facing UI surface today** (the Extract Data card tile was
deliberately omitted in favour of relocating the surface to
Sys Admin per industry best practice; see "Why a separate
sys admin page" below).

**Under Segment 16A.** Satisfies **F11** — a Download tile
on the Sys Admin page wiring the existing route. Per
industry best practice (GitHub / Stripe / Slack / Notion /
Atlassian), audit data sits behind an admin / diagnostics
doorway rather than alongside everyday data exports. No
new service code; pure chrome placement.

A richer **in-app** audit log viewer (filter, search,
drill-in) lives in **16C** — out of scope here.

## Why a separate sys admin page

Today's chrome reads as "operator-facing setup +
operations." Surfaces that don't fit that taxonomy
either get tucked behind buttons (Outbox) or sit
awkwardly on a Setup tab they'll outgrow (manual
assignment upload). A dedicated Sys Admin page:

- Keeps the operator-facing chrome focused on the
  rule-based workflow that 15D centres on.
- Gives the dev-diagnostic surfaces a discoverable
  home (no more "where did the View outbox button
  go?" treasure hunts).
- Makes it explicit when a capability is dev /
  support / admin scope rather than everyday
  operator scope.

## PR ladder

### PR 1 — Operator-allowlist gate + bootstrap reads (~300 LOC)

**Functional targets:** F1 + F3 + F4 + F5 (operator gate +
bootstrap + sys-admin-implies-operator predicate + Request-
access landing page).

**Why first.** This is the foundational access gate for the
whole app under the Option C posture. Once it lands, only
admitted operators can hit operator routes — every other
16A PR (and every operator surface in the wider app) sits
behind it.

**Ships.**

- `app/config.py` gains:
  - `operator_emails: list[str]` parsed from a new
    `OPERATOR_EMAILS` env var (first-sign-in bootstrap source
    for `is_operator`).
  - `sys_admin_emails: list[str]` parsed from the existing
    `SYS_ADMIN_EMAILS` env var (first-sign-in bootstrap source
    for `is_sys_admin`; the column shipped inert in 13F PR 1).
- `app/web/deps.py::get_or_create_user` reads both env vars on
  user-create. On first sign-in, sets `is_operator=True` if
  the email is in `OPERATOR_EMAILS`; sets `is_sys_admin=True`
  if the email is in `SYS_ADMIN_EMAILS`. Both flags persist
  after that — removing an email from either env var does
  **not** auto-revoke (revocation is via 16A PR 6 UI).
- New `app/web/deps.py::require_operator = Depends(…)` —
  passes if `current_user.is_operator OR current_user.is_sys_admin`
  (sys-admin implies operator); otherwise returns a redirect
  to the new "Request access" landing page rather than a raw
  403 (gentler UX for the misrouted-but-legitimate
  arrival).
- New "Request access" landing page at `/request-access` —
  unauthenticated routes already 401; this page is for the
  "signed in via Easy Auth but not on the operator allowlist"
  case. Shows the operator's email, a configurable contact
  message (env var `OPERATOR_CONTACT_EMAIL` or copy in the
  template), and a Sign-out affordance.
- Every existing operator route picks up
  `Depends(require_operator)`. The change is mechanical —
  `_shared.py` exports the dependency, every slice imports
  it. `require_session_operator` continues to compose on top
  (operator AND session-operator-member).
- `ALLOW_FAKE_AUTH=true` honours two new toggles
  (`FAKE_AUTH_OPERATOR=true` / `FAKE_AUTH_SYS_ADMIN=true`)
  so the agent's sandbox + local dev exercise the gates
  without env-var coordination.

**Tests.**

- Non-operator signs in → redirect to `/request-access`.
- Email in `OPERATOR_EMAILS` → first sign-in flips
  `is_operator=True`; persists across sessions.
- Email in `SYS_ADMIN_EMAILS` → first sign-in flips both
  `is_sys_admin=True` and (implicitly) operator access via
  the OR check.
- Operator `is_operator=False` after revocation → redirected
  even if previously admitted.
- Sys-admin retains operator access even when `is_operator=False`
  (the OR gate is the load-bearing predicate).
- `FAKE_AUTH_OPERATOR=true` injection in dev mode.

**Open question for scoping.** The "Request access" page
copy — generic ("Contact your administrator") vs deployment-
configurable. Lean configurable via `OPERATOR_CONTACT_EMAIL`
env var; render a `mailto:` link if set, generic copy if
unset.

### PR 2 — Sys-admin gate + chrome scaffold (~250 LOC)

**Functional targets:** F2 (sys-admin gate + chrome tab
visibility).

**Why second.** Layers on PR 1's operator-gate foundation
with the higher-privilege sys-admin gate. The Sys Admin
chrome appears only for sys-admins.

**Ships.**

- `app/web/deps.py` gains `require_sys_admin = Depends(…)`
  returning the `User` on hit; 403s with `"sys_admin
  required"` detail on miss. Plus a non-failing
  `current_user_is_sys_admin(request)` helper for chrome
  rendering.
- Middleware (or a per-request adapter in `_shared.py`)
  populates `request.state.is_sys_admin` so the chrome
  partial can render the Sys Admin tab conditionally.
- New empty-shell route `/operator/sessions/{id}/sys-admin`
  in a new `routes_operator/_sys_admin.py` slice. Renders
  the two-row session chrome + a "Sys Admin" H1 + an empty
  body that PRs 3-6 fill. Breadcrumbs via
  `breadcrumbs.operator_session_child(label="Sys Admin")`.
- Chrome partial `session_top_nav.html` gains the Sys
  Admin tab — rendered only when `is_sys_admin` is true.

**Tests.**

- 403 for non-admin GET `/sys-admin`.
- 200 for admin GET `/sys-admin`.
- Chrome partial renders / suppresses the Sys Admin tab
  conditional on the flag (one test of each).
- `require_sys_admin` returns the `User` on hit;
  signals 403 on miss.

**Open question for scoping.** Per-session URL
(`/operator/sessions/{id}/sys-admin`) vs workspace-level
(`/operator/sys-admin`). PRs 3-5 are session-scoped; PR 6
(workspace user list) is workspace-scoped. Lean
**per-session for PRs 3-5 + workspace-level for PR 6** —
two URLs, same chrome partial. Revisit once 16C PR 5
(cross-session audit search) takes a serious look at
workspace-level too.

### PR 3 — Outbox moves under Sys Admin (~150 LOC)

**Functional target:** F10 (Outbox under Sys Admin chrome;
Manage Invitations button retires).

**Ships.**

- The existing `/operator/sessions/{id}/outbox` route +
  `session_outbox.html` template + `invitations.list_outbox_for_session`
  service all stay. **Pure chrome relocation.**
- New Outbox card / section on the Sys Admin page, rendering
  the same table (probably via a partial extracted from
  `session_outbox.html`).
- The "View outbox" button on Manage Invitations
  (`session_invitations.html:43`) retires — the Sys Admin
  page is the new canonical home. Existing direct URL stays
  reachable for bookmarks.
- Optional: emit `sys_admin.outbox_viewed` audit event on
  page hit. Lean **skip** — read-only views shouldn't spam
  the log.

**Tests.**

- Sys Admin page renders the Outbox section for admin
  users; absent for non-admin (covered by PR 1's 403).
- The "View outbox" button is no longer present on the
  Manage Invitations page.

### PR 4 — Audit log download tile (~80 LOC)

**Functional target:** F11 (Audit log CSV download
reachable from a Sys Admin tile; no service code change).

**Ships.**

- New "Download audit log" tile / button on the Sys Admin
  page wiring the existing
  `GET /operator/sessions/{id}/export/audit_log.csv` route
  (shipped in 12B PR 1).
- The route + `serialize_audit_events` service +
  `session.audit_log_extracted` audit event — already
  shipped, unchanged. **Pure chrome placement.**
- The earlier 12B PR 2 already retired the Extract Data
  tile in anticipation of this PR; nothing to undo there.

**Tests.**

- Sys Admin page renders the Audit log tile for admin
  users.
- Download still emits `session.audit_log_extracted`
  (regression covered by 12B's existing tests; assert no
  drift).

### PR 5 — Manual assignment upload (~250 LOC + 1 audit event)

**Functional target:** F12 (Sys Admin manual-upload form
with confirmation checkbox + new
`sys_admin.manual_assignments_uploaded` audit event).

**Why this slot.** Highest-risk mutating action ("I can wipe
pairings"); landing it after the chrome + read-only
relocations lets the gate behaviour stabilise first. Before
PR 6 because PR 6 is workspace-scoped and benefits from
PR 5's per-session-mutating-action precedent (confirmation
checkbox, audit envelope, etc.).

**Ships.**

- New Manual upload card / form on the Sys Admin page.
  Wires the existing
  `POST /operator/sessions/{id}/assignments/manual/upload`
  route (`_assignments.py:199`) + `parse_manual_csv` /
  `replace_assignments` service. The route stays
  dev-only-discoverable (no operator-facing chrome
  surfaces it post-15D) — Sys Admin is the new operator-
  reachable home for the legitimate "I need to bypass the
  rules engine" case.
- **Explicit confirmation checkbox** ("I'm overriding the
  rule engine; this replaces every assignment for this
  session.") required before submit. Matches the existing
  Quick Setup `confirm_replace=true` gate pattern.
- New audit event `sys_admin.manual_assignments_uploaded`
  (`counts` envelope: rows parsed / accepted / rejected).
  Registered in `EVENT_SCHEMAS` per the canonical 11K
  shape.
- Help text alongside the form pointing operators at the
  Relationships table + Rule Builder as the everyday
  operator path; Sys Admin upload is the explicit "I need
  to bypass" escape.

**Tests.**

- 403 for non-admin POST.
- Happy path: valid CSV, replace_assignments called, audit
  event emitted with correct envelope.
- Missing-confirmation checkbox → 400.
- `EVENT_SCHEMAS` strict-mode gate passes for the new
  event type.

### PR 6 — Workspace user list + admit/revoke + promote/demote (~400 LOC + 4 audit events)

**Functional targets:** F6 + F7 + F8 + F9 (Admit / Revoke
operator status; Promote / Demote sys-admin status; auditable
workspace toggles; workspace user list visibility).

**Why last.** First workspace-level (rather than per-session)
Sys Admin surface, so it's the biggest UX swing in 16A.
Lands after PRs 1-5 so the per-session chrome + gates are
proven before introducing a sibling workspace URL.

**Ships.**

- New workspace-level route `/operator/sys-admin/users`
  behind `Depends(require_sys_admin)`. Renders the full
  workspace user table.
- New read service `users.list_workspace_users(db) ->
  list[WorkspaceUserRow]` returning per-row email / display
  name / first sign-in / `is_operator` / `is_sys_admin` /
  count of session-operator rows. Pagination keyset on
  `users.id DESC`; default page size 50.
- View adapter `views.build_workspace_user_rows(rows) ->
  WorkspaceUserListContext`.
- Per-row toggle forms (one per flag column):
  - `POST /operator/sys-admin/users/{user_id}/admit` →
    `is_operator=True`.
  - `POST /operator/sys-admin/users/{user_id}/revoke` →
    `is_operator=False`.
  - `POST /operator/sys-admin/users/{user_id}/promote` →
    `is_sys_admin=True`.
  - `POST /operator/sys-admin/users/{user_id}/demote` →
    `is_sys_admin=False`.
- **Guards.** Last-admin-demote guard refuses if the target
  is the only sys-admin (incl. self-demote-when-sole-admin).
  Revoking operator status from yourself is allowed but
  immediately drops you off the Sys Admin chrome on the next
  request (since `require_operator` no longer passes).
- **Confirmation.** Promote / Demote need an explicit
  checkbox ("I'm promoting <email> to sys-admin" /
  symmetric); Admit / Revoke don't (one-click toggles match
  Entra's typical access-grant pattern).
- New audit events, registered in `EVENT_SCHEMAS` per the
  canonical 11K envelope:
  - `workspace.operator_admitted` — `refs.target_user_id`,
    `changes.is_operator: [False, True]`.
  - `workspace.operator_revoked` — symmetric.
  - `sys_admin.role_promoted` — `refs.target_user_id`,
    `changes.is_sys_admin: [False, True]`.
  - `sys_admin.role_demoted` — symmetric.
- Chrome partial picks up a "Sys Admin · Users" sub-link or
  sibling chrome row pointing at the workspace URL. Locks
  the "per-session vs workspace-level chrome" question
  raised in PR 2's open questions.

**Tests.**

- Non-admin GET `/operator/sys-admin/users` → 403.
- Admin GET → renders the table with the seeded fixture
  users.
- Admit a user → flag flips + audit event emitted with
  correct envelope.
- Revoke a user → flag flips back + audit event emitted.
- Revoke an operator who's currently on N sessions → flag
  flips; their `session_operators` rows stay in place; on
  re-admit, they regain access without re-adding to
  sessions.
- Promote → flag flips + audit event.
- Demote → flag flips + audit event.
- Last-admin-demote guard → 409.
- Missing confirmation checkbox on promote → 400.
- `EVENT_SCHEMAS` strict-mode gate passes for the four new
  event types.

**Open questions for scoping.**

- Pagination shape for very large workspaces — keyset on
  `id DESC` is fine to start; add a filter strip
  (email-substring search) if pilot operators ask.
- Whether to surface the bootstrap source of each flag
  ("admitted via env var" vs "admitted by Alice on 2026-…").
  The audit log carries the actor; the workspace table can
  cross-reference via a small "Source" column. Defer to a
  follow-on if it expands PR 6 materially.

## Out of scope

- New service code for outbox or manual upload —
  both already exist.
- Operator-facing UX changes to the rule-based
  workflow — those live in 15D and 12A-3.
- **Per-session operator membership UI** (per-session
  Owners card on Session Home, owner add/remove from the
  admitted pool). Lives in **16B**. 16A admits people to
  the workspace; 16B is how owners on a specific session
  pick from the admitted pool.
- **In-app audit viewer beyond the CSV download** —
  richer filters / search / drill-in / per-session
  timeline. Lives in **16C**.

## Security / access — locked posture (2026-05-11)

Two gates, both backed by persisted Boolean flags on `users`:

- **`is_operator`** (the workspace allowlist; 13F PR 2).
  Required to hit any operator route. Bootstrapped from a
  new `OPERATOR_EMAILS` env var on first-sign-in; managed
  in-app via PR 6.
- **`is_sys_admin`** (the elevated tier; 13F PR 1 — shipped).
  Required to hit Sys Admin routes (PR 2's chrome + PRs 3-6's
  surfaces). Bootstrapped from the existing `SYS_ADMIN_EMAILS`
  env var on first-sign-in; managed in-app via PR 6.
  **Sys-admin implies operator** — the read-path predicate
  is `is_operator OR is_sys_admin`.

This is **Option C from the original sketch** (strict
allowlist) — locked 2026-05-11 because the app is a citizen
project with no tech-support promise to broader user
populations. Stricter than open or tenant-restricted; the
explicit admit step is the load-bearing safety control.

### Threat model

- *Accidental damage* — wrong click on Manual assignment
  upload silently wipes a live session's pairings via
  `replace_assignments`.
- *Deliberate misuse* — operator overrides the rule
  engine on a colleague's session, or pulls another
  session's audit log they shouldn't see.
- *Information leak* — audit log download surfaces
  correlation IDs / actor emails / lifecycle history;
  Outbox surfaces queued email bodies (incl. invite
  tokens pre-send).
- *Unwanted access* — anyone Easy Auth admits getting
  unfettered operator rights. **Mitigated by Option C:**
  Easy Auth admits → app rejects with "Request access"
  page → sys-admin reviews → flips `is_operator=True` via
  PR 6.

Risk per surface:

| Surface | Risk | Mitigation |
|---|---|---|
| Operator-facing surfaces (per-session) | Low–medium | `require_operator` gate (PR 1) on top of per-session `require_session_operator` |
| Outbox (read-only) | Low | `require_sys_admin` gate |
| Audit log download | Low–medium | `require_sys_admin` gate + per-download audit event (already emitted as `session.audit_log_extracted` by 12B PR 1) |
| Manual assignment upload | **High** (writes, bypasses rules) | `require_sys_admin` gate + confirmation + audit |
| Workspace user toggles (PR 6) | **High** (grants / revokes access) | `require_sys_admin` gate + confirmation on promote / demote + last-admin-demote guard + audit |
| Future SMTP test-send | Medium | `require_sys_admin` gate + audit |

### Defence in depth

1. **Authentication** — Entra Easy Auth (already
   enforced; nothing new).
2. **Authorization (operator)** — `require_operator`
   dependency (PR 1). 403-or-redirect to "Request access"
   landing page on miss.
3. **Authorization (sys-admin)** — `require_sys_admin`
   dependency (PR 2). 403s on miss; layers on top of
   `require_operator` (sys-admin implies operator).
4. **UI gating** — Sys Admin chrome tab renders only when
   `is_sys_admin`; the workspace user list link renders
   only when `is_sys_admin`; non-admins never see
   navigation they can't use.
5. **Audit + confirmation** — every mutating Sys Admin
   action writes an `audit_event` with `actor_user_id`;
   high-risk actions (Manual upload; Promote / Demote)
   need an explicit confirmation checkbox before submit.

### Bootstrap UX

First-time deployment puts both env vars in App Service
config:

```
OPERATOR_EMAILS=alice@example.edu,bob@example.edu,carol@example.edu
SYS_ADMIN_EMAILS=alice@example.edu
```

On each principal's first sign-in, `get_or_create_user`
flips the matching flags. After that, the persisted columns
are authoritative — removing an email from the env var does
**not** auto-revoke; revocation goes through PR 6's UI.

A signed-in person who isn't on either env var lands on the
"Request access" page; the page tells them which sys-admin
to contact (configurable via `OPERATOR_CONTACT_EMAIL` env
var).

### Audit-event registrations

- `sys_admin.manual_assignments_uploaded` (PR 5; `counts`
  envelope).
- `session.audit_log_extracted` — already shipped by
  12B PR 1; the event_type name stays the same after the
  surface moves under Sys Admin chrome (the *event* is a
  session-scoped extract; the *route* is sys-admin-scoped).
- `workspace.operator_admitted` / `.operator_revoked` (PR 6;
  `changes` envelope on `is_operator`).
- `sys_admin.role_promoted` / `.role_demoted` (PR 6;
  `changes` envelope on `is_sys_admin`).
- `sys_admin.outbox_viewed` — optional, read-only; skip if
  it spams the log.

### Open questions for scoping

- Destructive-action confirmation shape — single checkbox
  (matches the existing Quick Setup replace-confirmation
  pattern) or two-step "type the session code"
  (GitHub-repo-delete style)? Lean single checkbox for PR 5;
  consider escalating to type-the-email for PR 6's Revoke /
  Demote.
- Should `sys_admin.outbox_viewed` exist, or is read-only
  view too low-signal to audit?
- "Request access" page contact copy — generic vs
  deployment-configurable. Lean configurable via
  `OPERATOR_CONTACT_EMAIL` env var.

## Working notes / open questions

- _(placeholder)_
- Should Segment 16A also absorb today's
  `/operator/sessions/{id}/edit` or similar?
- Should the Sys Admin chrome row sit per-session or
  per-deployment (operator-global)?

## Related context

- **Segment 15D — Assignments revamp**
  (`guide/archive/segment_15D_assignments_revamp.md`). PR 7's
  decision to keep `parse_manual_csv` /
  `replace_assignments` as a dev-only feature
  established the route's continued existence; 16A
  picks up where the operator-facing surface
  retires.
- **Segment 12B — Audit retention**
  (`guide/archive/segment_12B_audit_retention.md`). The
  `audit_events` export shipped 2026-05-10 (PR #788)
  with the route live but no operator-facing UI
  surface; Segment 16A wires the existing route under
  the Sys Admin chrome (see Anchor item §3).
- **Segment 16B — Role delegation**
  (`guide/segment_16B_role_delegation.md`). The
  user-facing surface for promoting other operators
  to sys-admin / managing per-session
  `SessionOperator` rows.
- **Segment 16C — Richer audit views**
  (`guide/segment_16C_richer_audit_views.md`). The
  in-app audit log viewer (beyond CSV download).
- **Outbox today.**
  `app/web/routes_operator/_operations.py:510-527`
  (route + handler);
  `app/web/templates/operator/session_outbox.html`
  (template);
  `app.services.invitations.list_outbox_for_session`
  (data source).
- **Manual upload today.**
  `app/web/routes_operator/_assignments.py:199`
  (POST handler);
  `app.services.assignments.parse_manual_csv` +
  `replace_assignments` (service).
- **Chrome partial.**
  `app/web/templates/operator/partials/session_top_nav.html`
  — gains a "Sys Admin" tab (or sub-row) when this
  segment ships. Note: 15D restructures the chrome
  in the same broad time-frame; coordinate the
  taxonomy change with 15D's PR 6.
