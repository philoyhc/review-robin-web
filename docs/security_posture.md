# Security posture

The security / compliance posture of Review Robin Web: who can do
what, what the app trusts, and which hardening items are
deliberately deferred. Pairs with `docs/authentication.md` (the
identity subsystem) and `docs/known_limitations.md`.

## Authorization model

Three layers, all in `app/web/deps.py`:

- **`require_operator`** — workspace allowlist gate. Mounted as a
  router-level dependency on the whole `routes_operator` package
  (`routes_operator/__init__.py`), so *every* `/operator/*` route is
  behind it. A signed-in user not on the operator/sys-admin
  allowlist is redirected to `/request-access`.
- **`require_session_operator`** — per-session membership gate.
  Resolves `{session_id}` and 403s unless the caller is an operator
  of *that* session. Applied per-route on session-scoped operator
  routes, either directly or via slice helpers
  (`_require_instrument_in_session`, `_require_rtd_in_session`, …)
  that also re-scope any child id to the session.
- **`require_sys_admin`** — workspace sys-admin gate; strictly
  tighter than `require_operator`. `require_sys_admin_or_session_operator`
  relaxes the per-session check for sys-admins on diagnostic routes.
- **`require_reviewer_in_session`** — reviewer identity gate. 403s
  unless the caller has an *active* `Reviewer` row whose email
  matches the authenticated identity (case-insensitive).

## §5.6 Permission audit

Reviewed 2026-05-18. Every route family resolves identity through
the dependencies above; no route trusts a client-supplied actor id.

| Route family | Gate | Notes |
|---|---|---|
| `/operator/*` (all) | `require_operator` | Router-level dependency — no operator route can skip it. |
| Operator session-scoped routes | `require_session_operator` | Direct or via `_require_*_in_session` helpers. |
| `/operator/sessions` bulk routes (tags / archive / delete-selected) | `require_operator` + per-id check | Each client-supplied `session_id` is re-resolved with `sessions.get_for_user`; non-owned ids are skipped. |
| `/operator/settings/library/*` deletes | `require_operator` + owner check | Query filters `owner_user_id == user.id`; cross-operator id 404s. |
| `/operator/sys-admin/*` | `require_sys_admin` | Includes user admit/revoke/promote/demote/remove. |
| Export routes (`/export/*.csv`, `bundle.zip`) | `require_session_operator` | |
| `/export/audit_log.csv` | `require_sys_admin` | Tightened in Segment 16C PR 1. |
| Reviewer surface + save/submit/clear | `require_reviewer_in_session` | |
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

## CSRF posture

Review Robin relies on **Easy Auth + `SameSite=Lax` session
cookies** for CSRF protection and does not implement anti-CSRF
tokens in app code (segment-plan decision 2). A `SameSite=Lax`
cookie is not sent on a cross-origin POST, so a forged
state-changing request arrives with no auth cookie and fails the
Easy Auth gate before reaching a handler; every state-changing
route is a POST, never a GET. The full threat model, the
verification, and the alternatives considered are written up in
`docs/authentication.md` → "CSRF defense". This is a deliberate
fit-for-purpose choice for a single-tenant pilot behind Easy
Auth, not an oversight.

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
- `docs/deployment_dev.md` and `docs/authentication.md` both
  state it must not be enabled in App Service config.

Note: the PR 6a startup check (`validate_critical_settings`) does
**not** currently hard-fail on `ALLOW_FAKE_AUTH=true` in a
deployed environment — the check set was scoped to the
empty-allowlist case. Adding a fake-auth assertion there is a
reasonable future tightening.

## Deferred hardening

The following are out of scope for the Segment 14A in-app
hardening ladder — they need the Azure portal or a later segment.
Tracked in `guide/deferred_infra.md`.

| Item | Status |
|---|---|
| Key Vault references for App Settings secrets | Deferred — secrets live as plain App Settings / GitHub secrets today |
| VNet integration / private endpoints for Postgres | Deferred — public access + firewall allow-list today |
| Staging slot + manual-approval production deploy gate | Deferred — single dev slot today (see `docs/deployment_dev.md`) |
| Application Insights resource | Deferred — logs are already structured/JSON and ingestible once it exists (PR 1) |
| Postgres-specific column types / `ENUM` / `JSONB` GIN indexes | Deferred to the Segment 14 type migrations |
| In-app operator/sys-admin revoke UI | Segment 16A PR 6 — not yet shipped; revoke is a manual DB update today |
