# Cordware / Review Robin Integration Specification

> **On hold, speculative (author, 2026-10-16).** Nothing here is scheduled;
> see `guide/todo_master.md` "On hold".

**Version:** 0.1 draft  
**Purpose:** Define the intended behavior for hosting Review Robin Web (RRW) as an independently deployed application under a shared Cordware public host.  
**Initial public host:** `https://cordware.nus.edu.sg`  
**Initial RRW mount path:** `/reviewrobin`  
**Status:** Design specification for retrofit planning; not yet an implementation plan.

---

## 1. Context

Cordware is intended to be a lightweight shared public host for a family of independently developed NUS applications.

The intended model is:

```text
https://cordware.nus.edu.sg/
    -> Cordware landing page

https://cordware.nus.edu.sg/reviewrobin
    -> Review Robin Web

https://cordware.nus.edu.sg/<other-app>
    -> another independently deployed application
```

Cordware is **not** intended to turn all applications into one monolith or one repository.

Each application may retain:

- its own codebase;
- its own Azure Web App or equivalent backend;
- its own database;
- its own application authorization model;
- its own deployment workflow;
- its own operational lifecycle.

Cordware supplies a common public namespace, a lightweight landing/discovery experience, and a coherent authentication experience.

---

## 2. Design principles

### 2.1 Shared authentication experience, independent application authorization

Microsoft Entra ID answers:

> Who is this user?

Each application answers:

> What is this user allowed to do here?

A shared Entra authentication realm or registration may be used across Cordware applications if operationally suitable, but this **must not** replace application-level authorization.

RRW must continue to enforce its own operator/admin/super-admin model.

Other applications, including Residential Apps, must continue to enforce their own role, record, module, and action-level permissions.

### 2.2 Cordware landing is optional navigation, not an authentication choke point

The Cordware landing page is a convenience and discovery layer.

A user who navigates directly to:

`https://cordware.nus.edu.sg/reviewrobin`

must be able to authenticate and continue directly into RRW.

The user must **not** be visibly redirected through the Cordware landing page as a required intermediate step.

### 2.3 Applications remain independently deployable

Routing through Cordware must not require RRW to be packaged with the Cordware shell or with other applications.

A new RRW release should remain deployable without redeploying the Cordware landing page or unrelated applications, except where a deliberate shared-infrastructure change requires it.

### 2.4 The public path prefix is part of the deployment contract

RRW must no longer assume that its public root is `/`.

The initial intended public mount is:

`/reviewrobin`

The implementation should avoid scattering this literal path throughout the codebase. The public mount/base path should be represented through a small, explicit configuration surface wherever practicable.

This keeps open the possibility of changing the mount path later without another broad rewrite.

---

## 3. Required user-facing behavior

### 3.1 Cordware landing page

`GET https://cordware.nus.edu.sg/`

should present a lightweight Cordware landing page.

The landing page should:

- authenticate the user using the shared NUS Entra sign-in experience;
- show links/tiles only for applications the user is eligible to discover;
- avoid implying that landing-page visibility is sufficient authorization to use an application;
- provide direct links to application paths such as `/reviewrobin`.

Application discovery/visibility is a convenience layer only.

### 3.2 Direct RRW access: already authenticated

If a user is already authenticated and requests:

`GET /reviewrobin`

the request should route directly to RRW and RRW should render normally.

The user should not see the Cordware landing page unless they explicitly navigate to `/`.

### 3.3 Direct RRW access: not authenticated

If a user is not authenticated and requests:

`GET /reviewrobin`

the expected behavior is:

1. the request is routed to the RRW application/authentication boundary;
2. the user is redirected to NUS Entra sign-in;
3. after successful sign-in, the user returns to the originally requested RRW location;
4. the user continues in RRW.

The visible return URL should remain under:

`https://cordware.nus.edu.sg/reviewrobin...`

The user should not be required to visit the Cordware landing page.

### 3.4 Deep links

The same rule applies to deep links.

For example:

`https://cordware.nus.edu.sg/reviewrobin/sessions/123`

should:

- preserve the requested RRW location through authentication;
- return the user to that location after successful sign-in, subject to RRW authorization;
- not collapse back to `/reviewrobin` merely because authentication occurred.

### 3.5 Unauthorized RRW users

An authenticated NUS user who lacks the required RRW authorization must be handled by RRW's existing authorization rules.

Cordware must not silently grant RRW access merely because the user can authenticate or can see an RRW tile.

### 3.6 Health endpoint

RRW must retain a probeable health endpoint that does not require interactive authentication.

Externally or internally, the final routing arrangement must support a health check equivalent to the current `/health` contract.

The exact public health URL may be:

`/reviewrobin/health`

or a gateway-internal equivalent, depending on the final Application Gateway design.

The important behavior is:

- health probes must not be redirected to Entra;
- healthy RRW must return an accepted success status.

---

## 4. URL and path-prefix behavior

RRW must behave correctly when mounted under a non-root public path.

The retrofit must audit all code that can emit, compare, redirect to, or consume URLs.

At minimum, review:

- server-side redirects;
- route generation;
- HTML links;
- form actions;
- static asset URLs;
- JavaScript fetch/XHR URLs;
- API calls;
- callback URLs;
- pagination links;
- download/export links;
- error-page links;
- canonical URLs if any;
- email-generated links if any;
- tests that assume paths begin at `/`;
- hard-coded `Location` headers;
- any middleware that reasons about `request.url.path`.

### 4.1 Generated links

Links generated by RRW must resolve under the public mount path.

Example:

A logical application route `/sessions` should be externally reachable as:

`/reviewrobin/sessions`

### 4.2 Redirects

Redirects must not accidentally send the user to the Cordware root.

Incorrect:

`Location: /sessions`

when viewed by the browser as a Cordware public URL.

Correct public behavior:

`Location: /reviewrobin/sessions`

or an equivalent proxy-aware redirect strategy.

### 4.3 Static resources

CSS, JS, images, and other static resources must load correctly beneath the path prefix.

No page should depend on browser requests to an unintended path such as:

`https://cordware.nus.edu.sg/static/...`

if RRW assets are supposed to be served under:

`https://cordware.nus.edu.sg/reviewrobin/static/...`

unless the gateway deliberately provides a separate shared static mapping.

### 4.4 Configurable public root

The application should have one documented configuration mechanism for its public mount/base path.

The exact implementation is to be chosen during technical design, but the desired property is:

> changing the public mount path should not require editing many unrelated application files.

Local development should remain simple; a local root deployment at `/` should remain supported unless there is a strong reason not to.

---

## 5. Reverse-proxy behavior

Application Gateway will present the public Cordware host and route application paths to independent backends.

Conceptually:

```text
cordware.nus.edu.sg/
    -> Cordware shell backend

cordware.nus.edu.sg/reviewrobin/*
    -> RRW backend

cordware.nus.edu.sg/residentialapps/*
    -> Residential Apps backend
```

The final design must explicitly decide whether Application Gateway:

1. preserves `/reviewrobin` when forwarding to RRW; or
2. strips `/reviewrobin` and forwards RRW-relative paths to the backend.

The RRW implementation and gateway configuration must agree on this choice.

The project should not depend on undocumented implicit rewrite behavior.

### 5.1 Forwarded host/scheme/path metadata

RRW and Easy Auth must receive enough trusted proxy metadata to reconstruct the correct external URL.

The final design must document the relevant host/scheme/path forwarding behavior, including any use of forwarded headers or gateway rewrite rules.

### 5.2 Backend hostname

The RRW App Service may continue to use its Azure hostname/private endpoint identity internally.

That internal hostname must not leak into normal user-facing redirects or links.

---

## 6. Authentication behavior

### 6.1 Shared Cordware sign-in experience

Cordware applications should present one coherent NUS Entra sign-in experience.

Where practical, a user who has already authenticated to one Cordware application should experience little or no additional interaction when entering another.

This may be implemented using a common Entra application registration or another shared-auth arrangement, provided the security and operational trade-offs are explicitly reviewed.

### 6.2 Per-application authentication boundary remains acceptable

The Cordware landing page does not need to act as a central authentication proxy.

A valid first implementation is:

- Cordware shell has an Entra/Easy Auth boundary;
- RRW has an Entra/Easy Auth boundary;
- other applications have their own authentication boundary;
- they participate in the same NUS Entra sign-in experience.

This preserves backend isolation while allowing near-seamless SSO through the existing Entra browser session.

### 6.3 RRW direct authentication

If RRW retains App Service Easy Auth, authentication must work correctly when the user enters through `/reviewrobin`.

The final design must validate:

- unauthenticated redirect generation;
- callback URI;
- return URL preservation;
- cookie behavior;
- hostname preservation;
- path-prefix preservation;
- deep-link return after sign-in.

### 6.4 Callback URLs

The existing RRW Easy Auth callback based solely on the `azurewebsites.net` public hostname is not the final public contract.

The production authentication configuration must be reviewed against the Cordware public URL.

No final callback/redirect URI should be assumed until the chosen Application Gateway + Easy Auth arrangement has been proven.

### 6.5 No authorization by gateway path alone

Application Gateway routing must not be treated as an authorization control.

Reaching the RRW backend through `/reviewrobin` does not imply permission to use RRW.

RRW must continue to enforce its own authorization.

---

## 7. Cordware application discovery

The standalone Cordware landing page may maintain a small entitlement/discovery registry.

For example:

```text
user@nus.edu.sg
    reviewrobin: visible
    residentialapps: visible
    anotherapp: hidden
```

This registry may be driven by:

- configured allowlists;
- a small Cordware database;
- Entra group/claim information if later approved and available;
- application-provided discovery information.

The first implementation should favor the simplest deterministic mechanism.

### 7.1 Discovery is not authorization

A hidden tile must not be the only thing preventing application access.

A user who knows `/reviewrobin` may navigate there directly. RRW must then authenticate and authorize that request itself.

This is a required property, not an edge case.

---

## 8. Failure and isolation behavior

### 8.1 One app failing must not take down Cordware

If RRW is unavailable:

- `cordware.nus.edu.sg/` should still load if the Cordware shell is healthy;
- other applications should remain independently reachable;
- the Cordware shell may show RRW as unavailable if health information is available.

### 8.2 One app's authorization failure must not affect others

An RRW authorization denial must not invalidate the user's Cordware/Entra sign-in session for unrelated applications.

### 8.3 Independent deployment

Deploying RRW must not require taking the Cordware landing page or another application offline.

---

## 9. Local development and CI

The Cordware retrofit should preserve RRW's current local-development model as far as practicable.

Localhost may continue to run RRW at `/` with fake/local authentication.

CI should continue to test the application without requiring the live Cordware gateway.

However, the repository must gain automated tests for subpath behavior.

Minimum required test categories:

- generated links under configured prefix;
- redirects under configured prefix;
- forms/actions under configured prefix;
- static assets under configured prefix;
- deep-link preservation;
- auth-return URL handling where testable;
- health endpoint behavior;
- root-path compatibility for local development.

A separate integration test may later exercise Application Gateway + Easy Auth in Azure.

---

## 10. RRW retrofit acceptance criteria

The RRW retrofit is complete when all of the following are true:

1. RRW can run locally at `/` without breaking the existing dev loop.
2. RRW can be configured for public mount `/reviewrobin`.
3. All normal pages and workflows operate correctly under that mount.
4. Static resources load without root-path leakage.
5. Redirects remain within `/reviewrobin`.
6. Deep links survive sign-in and return the user to the requested RRW page.
7. Direct entry to `/reviewrobin` works without visiting Cordware `/`.
8. Direct entry by an unauthenticated user triggers NUS Entra sign-in and returns to RRW.
9. An authenticated but unauthorized user is denied by RRW, not by discovery-layer assumptions.
10. Health probing works without interactive authentication.
11. Azure/App Service backend hostnames are not exposed in normal user-facing navigation.
12. Existing RRW authorization semantics remain intact.
13. The automated test suite covers the path-prefix-sensitive behavior.
14. The production routing/auth behavior is documented in `docs/deployment_nus.md` or its successor.

---

## 11. Expected areas of code impact

This specification intentionally does not prescribe exact implementation changes before the repository is audited.

The retrofit should be treated as potentially significant.

Likely impact areas include:

- application/router construction;
- FastAPI/Starlette root-path or proxy configuration;
- URL generation helpers;
- redirects;
- templates;
- static-file mounting;
- authentication helper code;
- tests;
- deployment configuration;
- health-check routing;
- any code that constructs absolute URLs.

The RRW project should begin with a systematic audit for root-path assumptions rather than making isolated fixes as failures are discovered.

---

## 12. Explicit non-goals

This work does **not** require:

- merging RRW into the Cordware repository;
- sharing the RRW database with Cordware;
- replacing RRW's authorization model;
- forcing users to enter through the Cordware landing page;
- making Cordware responsible for all RRW authorization;
- making all Cordware applications use the same code framework;
- making all Cordware applications release on the same cadence.

---

## 13. Open technical decisions for the RRW project

The implementation plan must explicitly resolve:

1. canonical RRW public mount path: `/reviewrobin` versus another stable value;
2. whether Application Gateway preserves or strips the application prefix upstream;
3. how RRW is configured with its external/public base path;
4. exact Easy Auth topology:
   - same Entra app registration across Cordware apps or separate registrations;
   - callback/return URL mechanics;
   - cookie behavior;
5. whether RRW needs explicit trusted-proxy middleware/configuration;
6. exact health-probe path after gateway routing;
7. how the Cordware shell determines RRW tile visibility;
8. how end-to-end subpath/auth behavior is tested before cutover.

---

## 14. Recommended implementation approach

The RRW project should treat this as a bounded architectural retrofit rather than a deployment-only change.

Recommended sequence:

1. audit the current codebase for root-path assumptions;
2. choose and document the proxy prefix strategy;
3. implement a configurable public/root path;
4. retrofit URL generation, redirects, templates, assets, and tests;
5. establish the Easy Auth callback/return behavior in a non-production Azure test;
6. configure Application Gateway path routing and rewrites to match;
7. test direct and landing-page entry paths;
8. only then make the Cordware route the production RRW entry point.
