# Segment 3 Plan — Authentication Proof-of-Concept

**Project:** Review Robin Web  
**Repository:** <https://github.com/philoyhc/review-robin-web>  
**Segment:** 3 of the low-intensity workplan  
**Purpose:** Prove that Microsoft sign-in through Azure App Service Authentication can identify a user and pass identity information into the app

---

## 1. Segment goal

Segment 3 proves the authentication boundary.

The application should not yet implement full Review Robin permissions. It only needs to confirm that a user can sign in with Microsoft and that the app can read the authenticated identity supplied by Azure App Service Easy Auth.

By the end of this segment, the deployed app should have a `/me` page or endpoint showing the current authenticated user's identity.

---

## 2. Success criteria

Segment 3 is complete when:

1. App Service Authentication / Easy Auth is enabled for the dev App Service.
2. Microsoft is configured as the identity provider.
3. Anonymous access policy is understood and documented.
4. A signed-in user can access the app.
5. The app can read identity headers supplied by Easy Auth.
6. A `/me` route displays or returns the authenticated user's identity.
7. Local development still works through a controlled fake-auth mode.
8. Identity parsing logic has tests.
9. Documentation explains the difference between authentication and authorization.

---

## 3. What this segment deliberately does not do

Do not include:

- full user database;
- session operator roles;
- reviewer invitation links;
- magic links;
- permission model beyond a simple authenticated-user object;
- database-backed users;
- Microsoft Graph calls;
- MSAL in application code;
- custom OpenID Connect implementation.

Authentication proof first; authorization later.

---

## 4. Recommended branch strategy

Create a branch:

```bash
git checkout -b segment-3-auth-poc
```

Suggested PR title:

```text
Segment 3: Add Easy Auth identity proof of concept
```

Suggested PR description:

```text
Adds a small authentication proof-of-concept:

- identity parser for App Service Easy Auth headers
- /me route
- local fake-auth fallback
- tests for identity parsing
- authentication notes

No app authorization, database users, reviewer links, or domain functionality are included.
```

---

## 5. Conceptual model

Separate these concepts clearly:

```text
Authentication = Who is this person?
Authorization  = What may this person do?
```

Segment 3 handles only authentication.

Azure Easy Auth answers:

```text
This request came from this signed-in Microsoft user.
```

Review Robin Web will later answer:

```text
Is this signed-in user a system admin, session operator, or reviewer for this specific session?
```

---

## 6. Files to add or modify

Recommended minimal additions:

```text
app/
  auth/
    __init__.py
    identity.py

  web/
    routes_auth.py

  main.py

tests/
  test_identity.py
  test_auth_routes.py

docs/
  authentication.md
```

If the repository does not yet have `docs/`, create it.

---

## 7. Identity object

Create a small object to represent the authenticated user.

Example:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class AuthenticatedUser:
    principal_id: str | None
    email: str | None
    name: str | None
    raw_provider: str | None = None
```

Keep this deliberately simple. Do not add roles yet.

---

## 8. Easy Auth header parsing

App Service Easy Auth commonly exposes identity through headers such as:

- `X-MS-CLIENT-PRINCIPAL-NAME`
- `X-MS-CLIENT-PRINCIPAL-ID`
- `X-MS-CLIENT-PRINCIPAL-IDP`
- optionally `X-MS-CLIENT-PRINCIPAL`

For Segment 3, parse the simple headers first.

Suggested behavior:

- email/name comes from `X-MS-CLIENT-PRINCIPAL-NAME`;
- principal id comes from `X-MS-CLIENT-PRINCIPAL-ID`;
- provider comes from `X-MS-CLIENT-PRINCIPAL-IDP`;
- if no Easy Auth header is present locally, use a fake local user only when `APP_ENV=local` or `ALLOW_FAKE_AUTH=true`.

Do not rely on fake auth in deployed environments.

---

## 9. `/me` route

Add a route that displays the current authenticated identity.

Options:

- HTML page at `/me`; or
- JSON endpoint at `/me`.

For Segment 3, JSON is sufficient:

```json
{
  "principal_id": "...",
  "email": "...",
  "name": "...",
  "provider": "aad"
}
```

This is a diagnostic route. Later it may be restricted, removed, or replaced with a user profile page.

---

## 10. Local development fallback

Because Easy Auth headers exist only in Azure, local development needs a controlled fallback.

Suggested `.env.example` additions:

```text
ALLOW_FAKE_AUTH=true
FAKE_AUTH_EMAIL=operator@example.edu
FAKE_AUTH_NAME=Local Operator
```

Rules:

- fake auth allowed only in local/dev environment;
- fake auth disabled by default in production;
- the code should make it obvious when fake auth is being used.

---

## 11. Documentation to add

Create `docs/authentication.md`.

Suggested sections:

1. Authentication approach.
2. Why Easy Auth is preferred.
3. What identity headers the app reads.
4. Local fake-auth mode.
5. What this segment does not implement.
6. Future authorization model.

Include a warning:

```text
Fake auth is for local development only and must not be enabled in production.
```

---

## 12. Tests to add

### 12.1 Identity parser tests

Test cases:

- parses Easy Auth headers;
- returns expected email/name/principal id;
- handles missing optional headers;
- uses fake auth only when allowed;
- returns unauthenticated or raises clear error when no identity is available and fake auth is disabled.

### 12.2 `/me` route tests

Test cases:

- `/me` returns identity when headers are supplied;
- `/me` uses fake local identity in test mode;
- `/me` does not expose unrelated data.

---

## 13. Azure setup checklist

In Azure Portal:

1. Open the dev App Service.
2. Go to Authentication.
3. Add identity provider.
4. Choose Microsoft.
5. Use the default app registration if acceptable for dev, or configure an existing one if institutionally required.
6. Set unauthenticated requests behavior.
7. Save configuration.
8. Restart the App Service if needed.
9. Visit the app URL.
10. Confirm Microsoft sign-in flow.
11. Visit `/me`.

Document the chosen settings.

---

## 14. AI-assisted prompts

### Initial implementation prompt

```text
Implement Segment 3 authentication proof-of-concept.

Add:
- app/auth/identity.py
- app/web/routes_auth.py
- /me route
- local fake-auth fallback controlled by settings
- tests for identity parsing and /me
- docs/authentication.md

Constraints:
- Use Azure App Service Easy Auth headers.
- Do not implement MSAL or OpenID Connect in app code.
- Do not add database users or roles yet.
- Keep route handlers thin.
```

### Review prompt

```text
Review this authentication proof-of-concept.

Check:
- Is authentication clearly separated from authorization?
- Does fake auth only apply in local/dev settings?
- Are Easy Auth headers parsed defensively?
- Are tests sufficient?
- Is any Microsoft auth flow incorrectly implemented in app code?
```

### Azure debug prompt

```text
Easy Auth is enabled, but /me is not showing the expected user.

Here are the request headers visible to the app:

[paste sanitized headers]

Here are the Azure Authentication settings:

[paste settings summary]

Diagnose the likely issue and propose the smallest fix.
```

---

## 15. Suggested GitHub issues

### Issue 1 — Add Easy Auth identity parser

Scope:

- `AuthenticatedUser` object;
- header parsing;
- fake local user fallback;
- tests.

Acceptance criteria:

- parser works with Easy Auth headers;
- fake auth is controlled by settings;
- tests pass.

### Issue 2 — Add `/me` diagnostic route

Scope:

- route;
- JSON response;
- route tests.

Acceptance criteria:

- `/me` returns authenticated user identity;
- no roles or permissions are added.

### Issue 3 — Document authentication approach

Scope:

- `docs/authentication.md`;
- update `.env.example`;
- update README if needed.

Acceptance criteria:

- docs explain Easy Auth;
- docs explain local fake auth;
- docs clearly state authorization is later.

---

## 16. Common mistakes to avoid

### 16.1 Implementing MSAL too early

Do not implement Microsoft login in code. Easy Auth is the intended authentication mechanism.

### 16.2 Treating authentication as permission

A signed-in user is not automatically allowed to operate a session. Authorization comes later.

### 16.3 Trusting client-supplied headers locally without guardrails

In production, Easy Auth strips and injects trusted headers. Locally, headers can be faked. Keep local fake-auth behavior explicit.

### 16.4 Adding reviewer link logic too early

Unique reviewer links are an access policy question for later. Segment 3 proves Microsoft identity only.

### 16.5 Storing user records too early

Do not create database-backed users until the database segment is ready.

---

## 17. Segment 3 completion note template

```markdown
## Segment 3 completion note

Completed:
- Easy Auth enabled on dev App Service
- identity parser added
- /me route added
- local fake-auth fallback added
- identity tests added
- authentication notes written

Verified:
- deployed app requires Microsoft sign-in
- /me shows signed-in identity
- local fake auth works for development
- pytest passes

Deferred:
- user database
- roles and permissions
- reviewer invitation links
- magic links
- session authorization

Notes:
- [Easy Auth settings]
- [headers observed]
- [local fake auth settings]
```

---

## 18. Final checkpoint

Before moving to Segment 4, confirm:

- [ ] Easy Auth is enabled in dev.
- [ ] `/me` works in Azure.
- [ ] Local fake-auth works only when enabled.
- [ ] Identity parsing tests pass.
- [ ] Authentication documentation exists.
- [ ] No database or role logic was added prematurely.

Next segment: **Core data model and migrations**.

