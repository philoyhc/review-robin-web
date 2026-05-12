# Segment 16A — Sys Admin page + admin user role

> **Archived 2026-05-11.** All six planned PRs shipped (#834
> PR 1 / #841 PR 2 / #844 PR 3 / #845 PR 4 / #851 PR 5 / #852
> PR 6) plus follow-on reshape + polish PRs (#835 / #836 /
> #837 / #838 / #839 / #840 / #842 / #843 / #846 / #847 /
> #848 / #849 / #850). The plan stays here as historical
> context; see `guide/todo_master.md` § "Segment 16A — done"
> for the as-shipped summary and `docs/status.md` for the
> 2026-05-10 → 2026-05-11 timeline rows.
>
> Carved out of the original Segment 16 (2026-05-11). The
> original `segment_16_sys_admin_page.md` bundled three
> concerns: the Sys Admin page itself (this file), user-role
> management / delegation among operators (**16B**,
> `guide/archive/segment_16B_role_delegation.md`), and
> richer in-app audit views (**16C**,
> `guide/archive/segment_16C_richer_audit_views.md`).

**Status:** Shipped 2026-05-10 → 2026-05-11. All six PRs in
plus follow-ons. Two intentional scope deltas from the plan
documented inline below (Outbox bookmark URL story, optional
`sys_admin.outbox_viewed` event skipped).
**PR 5 reshaped 2026-05-11** from "wire manual upload under
Sys Admin" to "retire the manual-upload path entirely" once
it became clear the dev-only escape hatch has no live consumer.
**PR 2 reshaped 2026-05-11 (2b)** from per-session
`/operator/sessions/{id}/sys-admin` URL + third chrome row
to workspace-level `/operator/sys-admin` URL + top-bar
"Admin" link.
**PRs 3-4 reshaped 2026-05-11** to centre on a workspace
sessions-table-as-picker pattern under a new one-row Admin
chrome with two tabs (Sessions Diagnostics + Accounts
Management). See "Sys Admin chrome and navigation" below.
**Sizing:** 6 PRs (each small + reviewable; PRs 3-6 land
sequentially on the shipped PR 1/2 base).
**Depends on:** **13F PRs 1 + 2** for the `users.is_sys_admin`
and `users.is_operator` columns the gates read — both shipped
2026-05-11.

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
- **F12. Manual assignment upload path retired.** The
  dev-only `POST /operator/sessions/{id}/assignments/manual/upload`
  route + `assignments.parse_manual_csv` /
  `manual_rows_to_pairs` services + `ManualAssignmentRow`
  schema + `AssignmentMode.manual` enum value + 12+
  associated tests all go away. The rule engine
  (`AssignmentMode.rule_based`) + the Relationships table
  cover every realistic operator need; the manual path
  hasn't carried operator-facing UI since 15D PR 6a and
  the "dev-only escape hatch" framing from that decision
  no longer justifies the plumbing.
  `assignments.replace_assignments` keeps its `mode`
  parameter but its `manual` branch is removed. **Reversal
  of the 15D PR 7b decision** ("keep manual-CSV as a
  dev-only escape hatch") — 2026-05-11 codebase audit
  confirmed the path has no live consumer beyond its own
  tests.

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

**Under Segment 16A.** Satisfies **F12** — the manual
upload path is **retired entirely** rather than relocated.
Route + service helpers + schema + the `manual` enum
variant all go; the 12+ tests that exercised the path
retire with it. The rule engine + Relationships table
cover every realistic operator need; the dev-only framing
from 15D PR 7b ("escape hatch for tests + admin tooling")
no longer justifies the plumbing — the only live consumer
was the test surface that the retirement also removes.

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

**Functional targets:** F2 (sys-admin gate + Admin entry-point
visibility).

**Why second.** Layers on PR 1's operator-gate foundation
with the higher-privilege sys-admin gate. The Admin link
appears only for sys-admins.

**Shipped (PR 2a / #841 + PR 2b reshape):**

- `app/web/deps.py` gains `require_sys_admin = Depends(…)`
  returning the `User` on hit; 403s with `"sys_admin
  required"` detail on miss.
- New workspace-level route `GET /operator/sys-admin` in a
  new `routes_operator/_sys_admin.py` slice. Renders an
  "Admin" H1 + a `← Back to {return_to_label}` affordance
  resolved from `?return_to=` (mirrors Settings / About);
  body is empty pending PRs 3-6.
- Base top-bar chrome (`base.html`) gains an "Admin" link
  between Settings and About, conditional on
  `user.is_sys_admin`. Carries `?return_to=<current_path>`
  per the Settings / About pattern; self-suppresses on
  `/operator/sys-admin`.
- **NOT shipped (reshape removed):** the per-session
  `/operator/sessions/{id}/sys-admin` URL and the third
  `Sys Admin` row on the session top-nav originally proposed
  in PR 2a — reverted in PR 2b once the workspace-level
  shape was locked.

**Tests.**

- 403 for non-admin GET `/operator/sys-admin`.
- 200 for admin GET `/operator/sys-admin`.
- Top-bar Admin link renders / suppresses on `is_sys_admin`
  flag, plus self-hides on the Admin page itself.
- Back link resolves from `?return_to=` and falls back to
  the sessions lobby when unset.
- `require_sys_admin` returns the `User` on hit;
  signals 403 on miss.

**Locked 2026-05-11 (PR 2b reshape):** workspace-level URL
`/operator/sys-admin`, reached from an "Admin" link in the
base top-bar chrome (between Settings and About), conditional
on `user.is_sys_admin`. Sys-admin is conceptually a
workspace concern (env vars, user allowlist, cross-session
diagnostics); a per-session chrome tab implied "sys-admin
scoped to this session", which is wrong. The original
per-session shell (PR 2a) was retired in PR 2b.

## Sys Admin chrome and navigation

**Locked 2026-05-11.** The Admin page carries a single-row
tab chrome modelled on (but lighter than) the per-session
top nav. Two tabs for now, room to grow:

1. **Sessions Diagnostics** (`/operator/sys-admin/sessions`).
   The default tab. Renders a workspace sessions table
   patterned on the operator lobby (`/operator/sessions`):
   one row per session, columns for session name / code /
   status / created-at / counts, plus per-row affordances:
   - **View outbox** → existing per-session
     `/operator/sessions/{id}/outbox` page (PR 3).
   - **Download audit log** → existing per-session CSV route
     `/operator/sessions/{id}/export/audit_log.csv` (PR 4).
   No per-session-picker / placeholder dance — the table
   row IS the picker.
2. **Accounts Management** (`/operator/sys-admin/users`).
   Workspace user list (Admit / Revoke / Promote / Demote).
   Lands in PR 6.

Picking the table-as-picker shape (over a `<select>`
dropdown + tile region) avoids the empty-state UX entirely:
operator sees every actionable cell at once, scans for the
session they want, clicks the right button. Closed sessions
remain visible — admin diagnostics need historical reach.

**Permissions on the table:** the sys-admin sees every
session in the workspace, including ones they're not on
`session_operators` for. Read-only diagnostic content
bypasses per-session membership. The existing per-session
Outbox / audit-log routes already gate on
`require_session_operator` today, which under PR 1b's
broader operator-allowlist gate already passes for any
sys-admin (sys-admin implies operator); a small relaxation
is needed so a sys-admin who isn't on `session_operators`
for that session can still hit those two routes. Tracked as
PR 3's housekeeping.

**Chrome shape.** The chrome lives in a new
`app/web/templates/operator/partials/sys_admin_top_nav.html`
partial — one row, two tabs, matching the `tab-strip`
styling already in `base.html`. The Admin page templates
include this partial above their content. The base top-bar
"Admin" link continues to point at the canonical
`/operator/sys-admin` URL; that root redirects to the
default tab (`/operator/sys-admin/sessions`) once any tab
content ships. Until PR 3 lands, `/operator/sys-admin`
stays an empty shell.

**Why not "select a session, then tiles":** picker UX adds
a no-session empty state, requires placeholder copy in every
tile, and forces a navigation roundtrip per session change.
The table row collapses picker + action into one click.

### PR 3 — Outbox moves under Sys Admin (~200 LOC, +40 for chrome)

**Functional target:** F10 (Outbox reachable from the
Sys Admin chrome; Manage Invitations button retires).

**Ships.**

- New `sys_admin_top_nav.html` partial (the one-row tab
  chrome described above). Single tab for now —
  "Sessions Diagnostics" — pre-wired for "Accounts
  Management" to slot in at PR 6 without a chrome refactor.
- New route `GET /operator/sys-admin/sessions` rendering the
  workspace sessions table. Columns: name, code, status,
  created-at, reviewer / reviewee / response counts (use the
  existing operator-lobby view-builder where it composes).
  Each row carries a "View outbox" link to the existing
  per-session `/operator/sessions/{id}/outbox` page.
- The existing `/operator/sessions/{id}/outbox` route +
  `session_outbox.html` template + `invitations.list_outbox_for_session`
  service stay. **No template duplication** — the existing
  per-session page is reached from both the operator chrome
  (still present for now) and the Admin table.
- `/operator/sys-admin` (root) redirects (303) to
  `/operator/sys-admin/sessions`.
- The "View outbox" button on Manage Invitations
  (`session_invitations.html:43`) retires — the canonical
  home is the Admin page. Existing direct URL stays
  reachable for bookmarks.
- Relax `require_session_operator` on the Outbox route so a
  sys-admin who isn't a member of `session_operators` for
  that session can still view it (the Admin entry assumes
  this). Cleanest: compose `require_sys_admin OR
  require_session_operator` at the route boundary; or split
  into two route handlers. Decide at scoping.
- Optional: emit `sys_admin.outbox_viewed` audit event on
  page hit. Lean **skip** — read-only views shouldn't spam
  the log.

**Tests.**

- Sys-admin GET `/operator/sys-admin/sessions` → 200 with
  the workspace's sessions in the table.
- Plain-operator GET → 403.
- Each row's outbox link points at the per-session URL.
- The "View outbox" button no longer renders on the
  Manage Invitations page.
- Sys-admin who isn't on `session_operators` for session N
  can still GET `/operator/sessions/N/outbox` (200).

### PR 4 — Audit log download column (~60 LOC)

**Functional target:** F11 (Audit log CSV download
reachable from the Sessions Diagnostics table; no service
code change).

**Ships.**

- New "Download audit log" column / button on the
  workspace sessions table from PR 3 — one button per row,
  wiring the existing
  `GET /operator/sessions/{id}/export/audit_log.csv` route
  (shipped in 12B PR 1).
- The route + `serialize_audit_events` service +
  `session.audit_log_extracted` audit event — already
  shipped, unchanged. **Pure chrome placement.**
- Same `require_sys_admin OR require_session_operator`
  relaxation as PR 3's outbox route, so a sys-admin can
  download the audit log for any session in the workspace.
- The earlier 12B PR 2 already retired the per-session
  Extract Data tile in anticipation of this PR; nothing to
  undo there.

**Tests.**

- Sessions Diagnostics table renders an Audit log column
  for sys-admins; each row's button hits the per-session
  CSV route and the file streams cleanly.
- Download still emits `session.audit_log_extracted`
  (regression covered by 12B's existing tests; assert no
  drift).
- Sys-admin who isn't on `session_operators` for session N
  can still GET the CSV (200).

### PR 5 — Retire the manual-assignment upload path (~150 LOC removed + ~12 tests removed)

**Functional target:** F12 (manual upload path retired
entirely; rule engine + Relationships table are the only
remaining write-paths into `assignments`).

**Why this slot.** Reversal of the 15D PR 7b decision —
the "dev-only escape hatch" was kept on the bet that some
real bypass need would surface; nine days of pilot
preparation later, no such need has appeared. Better to
shed the plumbing than to wire it under a chrome roof that
makes it more visible than it deserves.

**Why this PR shape works.** It's a pure-removal PR — no
new code, no new tests, just deletion. Lands after PRs 1-4
so the gate + relocations are proven (we're not removing
plumbing that 16A's other PRs still depend on).

**Ships (all removals).**

- `app/web/routes_operator/_assignments.py` — remove the
  `POST /operator/sessions/{id}/assignments/manual/upload`
  route handler. Confirm no other surface POSTs to this
  URL (codebase audit: no live operator surface routes
  through it post-15D).
- `app/services/assignments.py` — remove
  `parse_manual_csv` and `manual_rows_to_pairs`.
  `replace_assignments` keeps its `mode` parameter for
  audit-event payload shape, but the `mode ==
  AssignmentMode.manual` branch goes; rule-based remains
  the only consumer.
- `app/schemas/assignments.py` — remove the
  `ManualAssignmentRow` shape; remove the
  `AssignmentMode.manual` enum variant. The enum keeps
  `rule_based` as its only value (worth retaining as an
  enum for future expansion — e.g. when 13C
  group-scoped instruments adds a flavour — rather than
  flattening it to a string).
- `tests/unit/test_assignments_manual.py` — retire
  entirely.
- `tests/unit/test_replace_assignments_self_reviews_active.py`
  — drop the single `AssignmentMode.manual` reference if
  it covers the manual branch; preserve the rule-based
  coverage that's the substance of the file.
- Anywhere else the codebase audit at PR-open surfaces
  (`grep -rn "parse_manual_csv\|manual_rows_to_pairs\|ManualAssignmentRow\|AssignmentMode.manual"`).

**No new audit event.** F12's earlier "Sys Admin
manual-upload audit event" goes away with the removal.

**Tests (after removal).**

- The test suite shrinks by the manual-path tests; no new
  positive tests are needed (we're removing dead code,
  not changing live behaviour).
- Regression check: existing rule-based assignment tests
  (e.g. `test_replace_assignments_*` minus the manual
  branch) still pass — `replace_assignments(... mode=
  AssignmentMode.rule_based ...)` behaviour is unchanged.
- `EVENT_SCHEMAS` strict-mode gate passes (no new
  registrations; no removals from the existing event set).
- The `ci-postgres` job's full pytest run is the final
  safety net.

**Open question for scoping.** Whether to keep the
`AssignmentMode` enum at all if `rule_based` is the only
value. Lean keep — the enum's audit-event use site reads
more clearly as `mode=AssignmentMode.rule_based` than as
`mode="rule_based"`, and the cost of one-value enums in
Python is essentially nil. Confirm at scoping.

### PR 6 — Workspace user list + admit/revoke + promote/demote (~400 LOC + 4 audit events)

**Functional targets:** F6 + F7 + F8 + F9 (Admit / Revoke
operator status; Promote / Demote sys-admin status; auditable
workspace toggles; workspace user list visibility).

**Why last.** Largest UX swing in 16A — full per-row toggle
matrix + last-admin-demote guard + four new audit events. Lands
after PRs 1-5 so the chrome + diagnostics tabs are proven before
introducing a second Admin tab.

**Ships.**

- New route `GET /operator/sys-admin/users` behind
  `Depends(require_sys_admin)`. Becomes the second tab
  ("Accounts Management") in the Admin chrome alongside
  "Sessions Diagnostics" from PR 3. Renders the full
  workspace user table.
- `sys_admin_top_nav.html` (the chrome partial introduced in
  PR 3) gains the Accounts Management tab — the chrome was
  pre-wired for it.
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
- Top-bar Admin link from PR 2b continues to point at
  `/operator/sys-admin` (which redirects to the default tab);
  Accounts Management is reached via the Admin chrome tab,
  no separate top-bar entry needed.

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
| ~~Manual assignment upload~~ | ~~High~~ | ~~Not applicable~~ — **path retired in PR 5** (F12). No Sys Admin surface; no audit event needed since there's nothing to audit. |
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

PR 5 (manual-assignment retire) is a removal — no new
audit events. The earlier draft's
`sys_admin.manual_assignments_uploaded` event goes away
with the path itself.

### Open questions for scoping

- Destructive-action confirmation shape on PR 6's
  workspace toggles — single checkbox (matches the existing
  Quick Setup replace-confirmation pattern) or two-step
  "type the user's email" (GitHub-repo-delete style)?
  Lean single checkbox for the toggles; consider escalating
  to type-the-email if pilot feedback surfaces accidental
  revocations. (PR 5's confirmation question is moot since
  the path is being retired, not surfaced.)
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
  (`guide/archive/segment_16B_role_delegation.md`). The
  user-facing surface for promoting other operators
  to sys-admin / managing per-session
  `SessionOperator` rows.
- **Segment 16C — Richer audit views**
  (`guide/archive/segment_16C_richer_audit_views.md`). The
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
