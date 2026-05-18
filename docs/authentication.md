# Authentication

Review Robin Web delegates authentication to **Azure App Service Easy Auth**
(App Service Authentication V2). The application code never implements MSAL,
OpenID Connect, or any Microsoft sign-in flow itself — it only reads the
identity headers Easy Auth injects after a successful sign-in.

## Authentication is not authorization

```text
Authentication = Who is this person?       (Easy Auth answers this)
Authorization  = What may this person do?  (Review Robin Web answers this later)
```

Segment 3 covers authentication only. A signed-in user is **not** automatically
allowed to operate sessions, invite reviewers, or see other users' data. Those
checks belong to later segments once the data model exists.

## How Easy Auth is configured (dev)

On `app-review-robin-web-dev`:

- **App Service Authentication:** enabled.
- **Restrict access:** Require authentication.
- **Unauthenticated requests:** HTTP 302 → Microsoft.
- **Token store:** enabled.
- **Excluded paths:** `/health` (set via `globalValidation.excludedPaths` in
  the `authsettingsV2` resource so uptime probes still work).

The consequence: every path other than `/health` is gated by Microsoft sign-in
in Azure. The application receives only authenticated requests in deployed
environments.

## Identity headers consumed

The identity parser in `app/auth/identity.py` reads:

- `X-MS-CLIENT-PRINCIPAL-NAME` — typically the user's UPN/email.
- `X-MS-CLIENT-PRINCIPAL-ID` — the principal id (object id for Entra ID).
- `X-MS-CLIENT-PRINCIPAL-IDP` — the identity provider (e.g. `aad`).
- `X-MS-CLIENT-PRINCIPAL` — base64-encoded JSON containing the full claims set
  (available because the token store is enabled). Used to extract email, name,
  and object id when the simple headers don't supply them.

The parser is defensive: a malformed `X-MS-CLIENT-PRINCIPAL` header falls back
to whatever the simple headers provide, rather than raising.

## Local development: fake auth

Easy Auth headers do not exist when running `uvicorn` locally. To make `/me`
and other authenticated routes usable on a developer machine, the app supports
a **controlled fake-auth fallback**:

```text
ALLOW_FAKE_AUTH=true
FAKE_AUTH_EMAIL=operator@example.edu
FAKE_AUTH_NAME=Local Operator
```

Rules:

- Fake auth activates only when no Easy Auth headers are present **and**
  `ALLOW_FAKE_AUTH=true`.
- The default for `allow_fake_auth` is `False`, so deployed environments do
  not accept it unless someone explicitly sets the env var (don't).
- The resulting user has `is_fake=True` and `provider="fake"`, so it's
  obvious in `/me` output and in any future audit log.

> **Warning:** Fake auth is a development convenience only. Never set
> `ALLOW_FAKE_AUTH=true` in Azure App Service configuration.

## Diagnostic routes

There are two diagnostic surfaces:

### `GET /me` (JSON)

Machine-readable identity, useful for scripting and tests:

```json
{
  "principal_id": "00000000-0000-0000-0000-000000000000",
  "email": "alice@example.edu",
  "name": "Alice Example",
  "provider": "aad",
  "is_fake": false
}
```

### `GET /me/debug` (HTML)

Human-readable page that renders:

- the parsed `AuthenticatedUser` (name, email, principal id, provider);
- the **raw claims list** decoded from `X-MS-CLIENT-PRINCIPAL`, useful for
  confirming what Entra is actually sending for the current tenant;
- a "fake auth" pill when the local fallback is in use;
- a sign-out link to `/.auth/logout` (handled by Easy Auth in Azure).

Both routes are diagnostic. Later segments may restrict, remove, or replace
them with a richer user-profile surface.

## CSRF defense (decided 2026-05-03)

Review Robin **relies on Easy Auth + SameSite cookies for CSRF protection**;
it does not implement CSRF tokens in app code.

**Threat model.** Authenticated session cookies are the only thing a forged
cross-origin POST could replay. Easy Auth's session cookie
(`AppServiceAuthSession`) is set by the Azure App Service platform with
`HttpOnly`, `Secure` (HTTPS-only), and `SameSite=Lax` (the modern browser
default). A `SameSite=Lax` cookie is **not** sent on cross-origin POST,
PUT, DELETE, or PATCH requests — so a forged form submit from another
origin reaches the app with no auth cookie, fails Easy Auth's gate, and
never hits a route handler. Top-level cross-origin GET navigation still
sends the cookie (the `Lax` exception), but every state-changing route in
the app is gated on POST, never on GET, so the GET exception isn't
exploitable.

**Verification.** The `SameSite=Lax` default has been Azure App Service's
behaviour since 2020 (when Chrome 80 forced the change). Confirm on the
dev slot when next deploying by inspecting the `Set-Cookie` header on
the auth response — search dev-slot HTTP traffic for
`AppServiceAuthSession=` and verify the attribute. If Microsoft ever
changes the platform default, this section is the canonical place to
revisit the decision.

**What this rules out (and why that's fine).**

- **CSRF tokens per form.** Would need a token-mint-and-verify middleware
  + per-form template plumbing across every state-changing POST in the
  app (~20+ forms across the operator and reviewer surfaces). Defense
  in depth, but redundant with `SameSite=Lax` for a single-tenant pilot
  deployment behind Easy Auth.
- **Origin / Referer header checks.** Possible without tokens, but again
  redundant with the cookie's `SameSite=Lax`.
- **Custom request headers (e.g. `X-Requested-With`).** Useful when
  defending AJAX endpoints; the app's POSTs are all `<form>`-based,
  not AJAX, so no benefit here.

If the deployment model ever shifts (multi-tenant, embedded iframe with a
foreign origin, etc.) this decision should be revisited and CSRF tokens
likely added at that point.

**Local-dev / `ALLOW_FAKE_AUTH=true`.** The fake auth path uses request
headers, not cookies, so SameSite-on-the-cookie doesn't apply. Local dev
is single-origin (`127.0.0.1:8000`) so cross-origin CSRF isn't a
realistic threat anyway.

## What this segment does not implement

- No database-backed user records.
- No roles, permissions, or session-operator concepts.
- No reviewer invitation links or magic links.
- No Microsoft Graph calls.
- No MSAL or custom OpenID Connect implementation in app code.

## Authorization model

Authorization is layered on top of the authenticated identity from Easy
Auth. `AuthenticatedUser` is the stable input; the route-level gates in
`app/web/deps.py` — `require_operator`, `require_session_operator`,
`require_sys_admin`, and `require_reviewer_in_session` — decide what an
authenticated user may do. See `docs/security_posture.md` for the full
authorization model and the permission audit.
