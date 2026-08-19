# Security posture

The security / compliance posture of Review Robin Web: who can do
what, what the app trusts, and which hardening items are
deliberately deferred. Absorbs the identity-subsystem write-up
(formerly `docs/authentication.md`, retired 2026-08-19); pairs with
`docs/known_limitations.md`.

## Authorization model

Three layers, all in `app/web/deps.py`:

- **`require_operator`** — workspace allowlist gate. Mounted as a
  router-level dependency on the whole `routes_operator` package
  (`routes_operator/__init__.py`), so *every* `/operator/*` route is
  behind it. A signed-in user not on the operator/sys-admin
  allowlist is redirected to `/me`.
- **`require_session_operator`** — per-session membership gate.
  Resolves `{session_id}` and 403s unless the caller is an operator
  of *that* session. Applied per-route on session-scoped operator
  routes, either directly or via slice helpers
  (`_require_instrument_in_session`, `_require_rtd_in_session`, …)
  that also re-scope any child id to the session.
- **`require_sys_admin`** — workspace sys-admin gate; strictly
  tighter than `require_operator`. `require_sys_admin_or_session_operator`
  relaxes the per-session check for sys-admins — **narrowed by Segment 18S
  Item 3** to only `owners/add` (self-add bootstrap, self-only in the handler
  for non-owners) and `clone`. Every other session mutation (edit config,
  lobby rename/tag, remove owners) now requires `require_session_operator`
  (real ownership); a non-owner sys-admin elevates via the audited self-add
  door `POST /operator/sys-admin/sessions/{id}/adopt` (Diagnostics "Manage").
- **`require_reviewer_in_session`** — reviewer identity gate. 403s
  unless the caller has an *active* `Reviewer` row whose email
  matches the authenticated identity (case-insensitive).
- **`require_reviewee_in_session`** — reviewee identity gate for the
  reviewee results surface (`/me/sessions/{id}/results`). 403s unless
  the caller matches an *active* `Reviewee` row by email
  (case-insensitive); reviewees with a non-email identifier fail the
  reachability check.
- **`require_observer_in_session`** — observer identity gate for the
  observer collation surface (`/me/sessions/{id}/collation`). 403s
  unless the caller matches an *active* `Observer` row by email
  (case-insensitive).

### Three-tier role hierarchy (Segment 18S)

**operator ⊂ admin (`is_sys_admin`) ⊂ super-admin.** Capabilities nest
strictly (super-admin ⊇ admin ⊇ operator). The top tier is
**config-anchored and protected**:

- **Super-admin is derived from `SUPER_ADMIN_EMAILS`** (deployer config),
  never a DB column (`app/auth/roles.py::is_super_admin`). No in-app path
  adds or removes one — only editing the App Setting can. App Settings are
  unreachable from inside the app, so this is the hard anchor. A super-admin
  **self-heals** to full admin rights on every sign-in
  (`_reassert_super_admin`).
- **Admin promote / demote is super-admin-only.** The `promote` / `demote`
  service functions require the **actor** to be a super-admin
  (`requires_super_admin` → 403); a plain sys-admin can no longer change who
  is an admin. Operator admit / revoke stays admin-gated. **No-super-tier
  fallback (18S Item 2):** when `SUPER_ADMIN_EMAILS` is empty (no super tier
  configured at all), this guard falls back to the pre-18S rule — any admin may
  promote/demote admins — so a deploy that never sets the list can't lock its
  own admin management out. The strict rule engages only once a super-admin
  exists. A deployed env that boots with no super-admin logs a startup warning
  (`super_admin.unconfigured`).
- **Protected-super-admin guarantee.** No in-app action can demote, revoke,
  hard-remove, or detach-from-all-sessions a super-admin: `demote` /
  `revoke` / `remove_user` / `remove_from_all_sessions` refuse a super-admin
  **target** (`protected_super_admin` → 409), a guard that sits *above* the
  count-based `last_admin` floor (it protects a specific identity, not just a
  count). The Sys Admin UI mirrors this (controls hidden/disabled), but the
  service guards are the enforcement.
- **Local dev.** With `ALLOW_FAKE_AUTH=true`, `FAKE_AUTH_SUPER_ADMIN`
  (default on) treats the fake operator as a super-admin — inert in any
  deployed env (where `allow_fake_auth` must be false).

## §5.6 Permission audit

Reviewed 2026-05-18. Every route family resolves identity through
the dependencies above; no route trusts a client-supplied actor id.

| Route family | Gate | Notes |
|---|---|---|
| `/operator/*` (all) | `require_operator` | Router-level dependency — no operator route can skip it. |
| Operator session-scoped routes | `require_session_operator` | Direct or via `_require_*_in_session` helpers. |
| `/operator/sessions` bulk routes (tags / archive / delete-selected) | `require_operator` + per-id check | Each client-supplied `session_id` is re-resolved with `sessions.get_for_user`; non-owned ids are skipped. |
| `/operator/settings/library/*` deletes | `require_operator` + owner check | Query filters `owner_user_id == user.id`; cross-operator id 404s. |
| `/operator/sys-admin/*` | `require_sys_admin` | Includes user admit/revoke/promote/demote/remove. Segment 18S adds a service-layer actor-super guard on promote/demote (`requires_super_admin`) and a target-super protection on demote/revoke/remove/remove-from-sessions (`protected_super_admin`). |
| Export routes (`/export/*.csv`, `bundle.zip`) | `require_session_operator` | |
| `/export/audit_log.csv` | `require_sys_admin` | Tightened in Segment 16C PR 1. |
| Reviewer surface + save/submit/clear | `require_reviewer_in_session` | |
| Reviewee results (`/me/sessions/{id}/results` + acknowledge) | `require_reviewee_in_session` | Active-`Reviewee` email match; non-email identifiers fail reachability. |
| Observer collation (`/me/sessions/{id}/collation` + CSV) | `require_observer_in_session` | Active-`Observer` email match. |
| `/me/invite/{token}` | identity + token lookup | Email-mismatch → dedicated 403 page. |

POST endpoints verified not to trust client-side identifiers:
reviewer `save`/`submit` build the assignment index from
`_reviewer_assignments` (scoped to `reviewer_id`), so a foreign
`assignment_id` in the form body is silently dropped — never
written. Operator child-id routes 404 on cross-session ids via the
`_require_*_in_session` helpers.

**Result: no gaps found.**

## §5.7 Destructive-action audit

Reviewed 2026-05-18. Each destructive action carries an explicit
confirmation, a permission gate, and an audit event (every mutating
service writes an `audit_events` row).

| Action | Confirm | Permission | Audit |
|---|---|---|---|
| Delete response data (`/delete-data`) | `confirm=true` | `require_session_operator` | ✓ |
| Delete session (`/delete`, `/delete-selected`, `/delete-archived-selected`) | `confirm=true` | `require_session_operator` / per-id check | ✓ |
| Close / reopen session (`/activate`, `/revert`, `/workflow/activate`) | `activate_confirm` banner | `require_session_operator` | ✓ |
| Replace reviewers / reviewees roster | `confirm_replace` + response-loss ack | `require_session_operator` | ✓ |
| Replace assignments (import / generate / `delete-all`) | `confirm`/`confirm_replace` + response-loss ack | `require_session_operator` | ✓ |
| Replace relationships (`delete-all`) | `confirm=true` | `require_session_operator` | ✓ |
| Delete instrument / field | `confirm=true` | `require_session_operator` (via helper) | ✓ |
| Reviewer clear (`/clear`) | `confirm=true` | `require_reviewer_in_session` | ✓ |
| Revoke / regenerate invitation links | operator UI action | `require_session_operator` | ✓ |

User-facing warnings are rendered by the operator templates that
own each confirm checkbox; they are not exercised by the test
suite and are verified on the dev slot.

**Result: no gaps found.**

## Denial-path test coverage

| Gate | Test |
|---|---|
| `require_operator` | `test_operator_allowlist_gate.py` |
| `require_session_operator` | `test_assignment_routes.py::test_non_operator_gets_403_on_assignments_hub_and_post` |
| `require_sys_admin` | `test_sys_admin_chrome.py` (root + diagnostics) |
| `require_reviewer_in_session` | `test_reviewer_response_flow.py::test_other_session_url_returns_403`, `::test_inactive_reviewer_row_403s_on_surface` |
| Client-id trust (reviewer POST) | `test_reviewer_response_flow.py::test_save_drops_foreign_assignment_id_from_post` |
| Export sys-admin gate | `test_extracts_audit_log_route.py::test_audit_log_route_rejects_non_sys_admin` |

## Identity trust model — Azure Easy Auth

In deployed environments the app does **not** implement
authentication itself. Azure App Service Authentication ("Easy
Auth") sits in front of the app: an unauthenticated request is
bounced to Microsoft Entra ID and never reaches Python. A request
that does reach a route handler has already been authenticated by
the platform, and Easy Auth injects the identity as request
headers (`X-MS-CLIENT-PRINCIPAL` and friends).

What this means for the trust boundary:

- `app/auth/identity.py` **trusts** the `X-MS-CLIENT-PRINCIPAL*`
  headers. That trust is only sound because Easy Auth strips
  client-supplied copies of those headers before forwarding — a
  caller cannot forge identity by setting the header themselves.
  This holds **only** while the app is reached through the App
  Service front end with Easy Auth enabled. Exposing the
  container directly (or disabling Easy Auth) would break the
  model.
- The app's own gates (`require_operator` / `require_session_operator`
  / `require_sys_admin` / `require_reviewer_in_session`, see the
  Authorization model above) are layered **on top** of that
  authenticated identity — they decide *what* an authenticated
  user may do, not *whether* they are who they claim.
- `/health` is the one route excluded from Easy Auth (so platform
  probes don't bounce through sign-in). It exposes no data.

### Identity-subsystem mechanics

*Easy Auth is App Service Authentication V2; the app never implements
MSAL / OpenID Connect itself — it only reads the headers Easy Auth
injects.*

- **Dev Easy Auth config** (`app-review-robin-web-dev`): authentication
  enabled, "Require authentication", unauthenticated → HTTP 302 to
  Microsoft, token store enabled, `/health` set in
  `globalValidation.excludedPaths` of the `authsettingsV2` resource.
- **Headers consumed** by `app/auth/identity.py`:
  `X-MS-CLIENT-PRINCIPAL-NAME` (UPN/email),
  `X-MS-CLIENT-PRINCIPAL-ID` (Entra object id),
  `X-MS-CLIENT-PRINCIPAL-IDP` (provider, e.g. `aad`), and
  `X-MS-CLIENT-PRINCIPAL` (base64 JSON claim set, used when the simple
  headers don't supply email / name / object id). The parser is
  defensive: a malformed `X-MS-CLIENT-PRINCIPAL` falls back to the
  simple headers rather than raising.
- **Fake auth** (local only): with `ALLOW_FAKE_AUTH=true`,
  `FAKE_AUTH_EMAIL` / `FAKE_AUTH_NAME` inject an identity carrying
  `is_fake=True` / `provider="fake"`. Activates only when no Easy Auth
  headers are present. See "`ALLOW_FAKE_AUTH` gating" below for the
  deployed-environment guard.
- **Diagnostic routes:** `GET /auth/me` (JSON — `principal_id`,
  `email`, `name`, `provider`, `is_fake`) and `GET /auth/me/debug`
  (HTML — the parsed `AuthenticatedUser`, the raw decoded claims list,
  a fake-auth pill when the local fallback is in use, and a
  `/.auth/logout` sign-out link).

## CSRF posture (decided 2026-05-03)

Review Robin relies on **Easy Auth + `SameSite=Lax` session cookies**
for CSRF protection and does not implement anti-CSRF tokens in app code
(segment-plan decision 2). A deliberate fit-for-purpose choice for a
single-tenant pilot behind Easy Auth, not an oversight.

**Threat model.** Authenticated session cookies are the only thing a
forged cross-origin POST could replay. Easy Auth's session cookie
(`AppServiceAuthSession`) is set by the App Service platform with
`HttpOnly`, `Secure` (HTTPS-only), and `SameSite=Lax` (the modern
browser default). A `SameSite=Lax` cookie is **not** sent on a
cross-origin POST / PUT / DELETE / PATCH — so a forged form submit from
another origin reaches the app with no auth cookie, fails Easy Auth's
gate, and never hits a route handler. Top-level cross-origin GET
navigation still sends the cookie (the `Lax` exception), but every
state-changing route is a POST, never a GET, so the GET exception isn't
exploitable.

**Verification.** The `SameSite=Lax` default has been App Service's
behaviour since 2020 (Chrome 80). Confirm on the dev slot when
deploying by inspecting the `Set-Cookie` header on the auth response
(`AppServiceAuthSession=`). If Microsoft ever changes the platform
default, this section is the canonical place to revisit the decision.

**Alternatives ruled out (and why that's fine).**

- *CSRF tokens per form* — would need a token-mint-and-verify
  middleware + per-form plumbing across ~20+ state-changing POSTs.
  Defence in depth, but redundant with `SameSite=Lax` behind Easy Auth.
- *Origin / Referer checks* — possible without tokens, but again
  redundant with the cookie's `SameSite=Lax`.
- *Custom request headers (`X-Requested-With`)* — useful for AJAX
  endpoints; the app's POSTs are all `<form>`-based, so no benefit.

If the deployment model ever shifts (multi-tenant, embedded iframe from
a foreign origin), revisit this and likely add CSRF tokens.

**Local dev / `ALLOW_FAKE_AUTH=true`.** The fake-auth path uses request
headers, not cookies, so SameSite-on-the-cookie doesn't apply; local
dev is single-origin (`127.0.0.1:8000`), so cross-origin CSRF isn't a
realistic threat anyway.

## `ALLOW_FAKE_AUTH` gating

`ALLOW_FAKE_AUTH=true` swaps the Easy Auth header parsing for a
fake injected identity — the local development escape hatch, since
there is no Easy Auth in front of a laptop / sandbox. It **must
stay `false` in every deployed environment**; with it on, anyone
would be handed a fake operator identity.

Defence against that footgun:

- It defaults to `false` (`app/config.py`).
- The companion `FAKE_AUTH_OPERATOR` / `FAKE_AUTH_SYS_ADMIN`
  flags are honoured only when `ALLOW_FAKE_AUTH` is also true and
  the resolved identity is `is_fake`, so they are inert in a
  deployed environment regardless.
- `docs/deployment_dev.md` states it must not be enabled in App
  Service config, and the "Identity-subsystem mechanics" note above
  flags the same.

Note: the PR 6a startup check (`validate_critical_settings`) does
**not** currently hard-fail on `ALLOW_FAKE_AUTH=true` in a
deployed environment — the check set was scoped to the
empty-allowlist case. Adding a fake-auth assertion there is a
reasonable future tightening.

## Deferred hardening

The following are out of scope for the Segment 14A in-app
hardening ladder — they need the Azure portal or a later segment.
Tracked in `guide/deferred_consolidated.md`.

| Item | Status |
|---|---|
| Key Vault references for App Settings secrets | Deferred — secrets live as plain App Settings / GitHub secrets today |
| VNet integration / private endpoints for Postgres | Deferred — public access + firewall allow-list today |
| Staging slot + manual-approval production deploy gate | Deferred — single dev slot today (see `docs/deployment_dev.md`) |
| Application Insights resource | Deferred — logs are already structured/JSON and ingestible once it exists (PR 1) |
| Postgres-specific column types / `ENUM` / `JSONB` GIN indexes | Deferred infrastructure (`guide/deferred_consolidated.md`) |
