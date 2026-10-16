# Addendum to NUS Azure Deployment Status v7 — Cordware Shared Host Direction

> **On hold, speculative (author, 2026-10-16).** `docs/nus_azure_status.md`
> stays the status of record; see `guide/todo_master.md` "On hold".

**Addendum date:** 15 October 2026  
**Applies to:** `docs/nus_azure_status.md` (NUS Azure deployment status, handoff revision 7)  
**Status:** Proposed architecture update; use this addendum for planning until the main status document is revised.

---

## 1. Reason for this addendum

The v7 Azure status assumed that Review Robin Web would receive its own production hostname and that Application Gateway would be configured specifically around that RRW hostname.

The intended direction has now changed.

The production hostname being approved is:

`cordware.nus.edu.sg`

Cordware is intended to become a shared public host for a small family of independently developed applications.

RRW is expected to be mounted under a stable path, initially proposed as:

`https://cordware.nus.edu.sg/reviewrobin`

rather than receiving a dedicated public hostname such as:

`reviewrobin.nus.edu.sg`

This is not merely a DNS naming change. It affects Application Gateway routing, Easy Auth, public URL behavior, and RRW code assumptions.

---

## 2. Revised target architecture

The previous conceptual target:

```text
public RRW hostname
    -> Application Gateway
    -> RRW App Service
```

should be replaced by:

```text
                         +-> Cordware landing Web App
                         |
Internet                 |   /reviewrobin/*
   |                     +-> RRW App Service
   v                     |
cordware.nus.edu.sg      |   /residentialapps/*
   |                     +-> Residential Apps backend
   v                     |
Application Gateway      +-> future Cordware applications
```

The existing public publishing foundation remains useful:

```text
137.132.48.31
    -> DNAT
    -> Application Gateway private frontend 10.9.0.196
```

The major change is that the Application Gateway becomes a **shared Cordware path router**, not an RRW-only ingress endpoint.

---

## 3. What from v7 remains valid

The following v7 work remains directly applicable and should not be undone:

- NUS subscription and resource groups;
- VNet `10.9.0.128/25`;
- existing App Service subnet;
- existing DB subnet;
- existing Private Endpoint subnet;
- Application Gateway subnet;
- runner subnet;
- route table / forced egress through `10.0.0.38`;
- RRW App Service;
- RRW App Service Private Endpoint `10.9.0.132`;
- RRW PostgreSQL server and private DNS;
- RRW Key Vault and Private Endpoint;
- monitoring resources;
- RRW GitHub OIDC deployment identity;
- runner NSG;
- runner NIC `10.9.0.212`;
- public IP `137.132.48.31`;
- DNAT to Application Gateway frontend `10.9.0.196`.

The runner VM capacity blocker is unchanged:

NUS IT is waiting for Microsoft Support to advise on a deployable/approved VM SKU or capacity path in Southeast Asia.

---

## 4. v7 item superseded: production hostname

The v7 item "production hostname / domain pending" is now substantially resolved in direction.

The intended shared hostname is:

`cordware.nus.edu.sg`

The remaining IT/DNS/TLS tasks are therefore narrower:

- complete/confirm public DNS for `cordware.nus.edu.sg`;
- obtain/approve a TLS certificate for `cordware.nus.edu.sg`;
- bind that certificate to the Application Gateway HTTPS listener.

RRW should no longer be planned around obtaining a dedicated RRW public hostname unless the Cordware plan is abandoned.

---

## 5. Application Gateway changes

The v7 report described application-specific RRW listener/routing configuration.

That work must now be reframed as shared Cordware ingress configuration.

### 5.1 HTTPS listener

The production listener should be associated with:

`cordware.nus.edu.sg`

and the TLS certificate for that hostname.

### 5.2 Path-based routing

Application Gateway should use a URL path map or equivalent path-based routing model.

Initial target:

- `/` and Cordware-shell routes -> Cordware landing backend;
- `/reviewrobin` and `/reviewrobin/*` -> RRW backend;
- future path prefixes -> their respective application backends.

The exact Cordware shell backend does not yet exist and must be provisioned/designed.

### 5.3 Rewrite behavior

A deliberate decision is required for each routed application:

- preserve the public path prefix when sending to the backend; or
- strip/rewrite the public prefix before forwarding.

RRW code and gateway configuration must implement the same model.

This is now a first-class architecture decision rather than a gateway detail.

### 5.4 Health probes

The current default RRW backend probe returns 404.

The production design should provide explicit per-backend health probes.

For RRW, the existing `/health` behavior should be retained, but the final gateway probe path depends on whether the `/reviewrobin` prefix is preserved or stripped upstream.

### 5.5 Backend host handling

The RRW backend remains the existing private App Service.

Application Gateway must be configured so that:

- the backend is reachable through its private endpoint;
- App Service accepts the backend request;
- the public `cordware.nus.edu.sg` identity is preserved/reconstructed correctly for redirects and authentication;
- the `azurewebsites.net` backend hostname does not leak into user-facing navigation.

---

## 6. New Azure component: Cordware landing Web App

The new direction introduces a component not present in v7:

> a small standalone Cordware landing application.

Its responsibilities should be intentionally limited:

- authenticate the user through NUS Entra;
- present the Cordware landing page;
- show only application links/tiles the user is eligible to discover;
- link directly to application paths such as `/reviewrobin`;
- optionally show application availability/health later.

It should **not** become the authorization proxy for RRW or other applications.

### 6.1 Isolation

The Cordware shell should be independently deployable.

RRW should continue to run as its own application backend.

Residential Apps and future applications should likewise remain independent unless there is a separate reason to consolidate them.

### 6.2 Hosting choice

The precise Azure hosting arrangement for the Cordware shell is still open.

A small independent Web App is the preferred conceptual model.

Whether it shares an App Service Plan with another Cordware application should be decided separately based on cost, isolation, ownership, and lifecycle.

---

## 7. Authentication architecture must be revisited

The v7 report treated RRW Easy Auth as an RRW-specific production authentication setup.

Cordware introduces a broader model:

- one shared public host;
- optional landing-page sign-in;
- direct per-application entry;
- desired near-seamless Entra SSO across applications.

### 7.1 Required user experience

A user visiting:

`https://cordware.nus.edu.sg/reviewrobin`

must be able to sign in and continue into RRW without being visibly required to visit the Cordware landing page.

Likewise, a user already signed into Cordware should normally experience little or no additional authentication friction entering RRW.

### 7.2 Shared Entra registration is now a design option

It is plausible for multiple Cordware applications to share one Entra authentication registration/realm.

This may simplify:

- consent;
- redirect-URI administration;
- sign-in consistency;
- future application onboarding.

However, it increases coupling and must be evaluated deliberately.

An alternative is per-application Easy Auth registrations participating in the same NUS Entra browser SSO experience.

### 7.3 Authorization remains application-local

Regardless of the Entra registration choice:

- RRW retains its own operator/admin/super-admin authorization;
- Residential Apps retain their own role/module/record permissions;
- the Cordware landing page's tile visibility does not constitute authorization.

### 7.4 Existing RRW callback cannot simply be assumed

The existing RRW callback based on:

`app-nrrw-prd-reviewrobinweb-01.azurewebsites.net`

must be revisited.

The final Easy Auth configuration must be proven against:

- `cordware.nus.edu.sg`;
- the `/reviewrobin` path;
- Application Gateway rewrites;
- direct deep-link sign-in;
- return URL preservation;
- cookie behavior.

This is now a material implementation task.

---

## 8. RRW code is now part of the Azure migration critical path

The earlier `docs/deployment_nus.md` states that no application code change is required to change hosts.

That statement is no longer valid under the Cordware path-hosting model.

RRW currently needs to be audited and potentially retrofitted for operation under a public path prefix such as:

`/reviewrobin`

Potential impact includes:

- redirects;
- URL generation;
- template links;
- form actions;
- static resources;
- JavaScript/API requests;
- auth return URLs;
- health routing;
- tests;
- proxy-awareness.

This should be treated as a significant bounded retrofit, not as an Azure-only configuration task.

A separate specification should govern the intended RRW behavior under Cordware.

---

## 9. GitHub/deployment consequences

The RRW repository remains independently deployed.

The Cordware direction does **not** imply:

- merging RRW into a Cordware monorepo;
- sharing RRW's database;
- sharing RRW's deployment release with the Cordware shell.

The RRW GitHub workflow still deploys to:

`app-nrrw-prd-reviewrobinweb-01`

once the self-hosted runner is available.

However, deployment verification must now include public path-prefix checks through Application Gateway.

The NUS deployment runbook should be revised so that a successful deployment is not considered production-ready until:

- RRW works through `/reviewrobin`;
- redirects stay under `/reviewrobin`;
- static assets work;
- Easy Auth works for direct and deep-link entry;
- health probing succeeds;
- backend Azure hostnames do not leak to the browser.

---

## 10. New acceptance tests for the Azure cutover

In addition to the existing RRW smoke test, final Cordware/RRW verification should include:

1. `GET https://cordware.nus.edu.sg/` loads the Cordware landing page.
2. An eligible signed-in user sees the RRW application link.
3. A user can navigate directly to `https://cordware.nus.edu.sg/reviewrobin` without first visiting `/`.
4. An unauthenticated direct RRW request triggers NUS Entra sign-in and returns to RRW.
5. A deep RRW link survives authentication and returns to the original RRW route.
6. RRW-generated links remain under `/reviewrobin`.
7. RRW redirects remain under `/reviewrobin`.
8. RRW static assets load correctly.
9. An authenticated but unauthorized user is rejected by RRW's own authorization model.
10. RRW health probing succeeds without interactive authentication.
11. A failure of RRW does not prevent the Cordware landing page or unrelated Cordware apps from operating.
12. Normal browser navigation does not expose `app-nrrw-prd-reviewrobinweb-01.azurewebsites.net`.

---

## 11. Revised blocker / work matrix

| Item | Status | Owner / next action |
|---|---|---|
| Cordware hostname `cordware.nus.edu.sg` | Being approved | NUS IT / DNS governance |
| Cordware TLS certificate | Pending | IT / project according to certificate process |
| Shared App Gateway HTTPS listener | Pending | Project after DNS/cert available |
| Cordware path map | Pending | Project |
| Cordware landing app | New work | Project |
| RRW subpath retrofit | New significant work | RRW project |
| RRW Easy Auth under Cordware | Requires redesign/test | Project + EUC if registration changes |
| Runner VM | Blocked on SEA capacity | IT waiting for Microsoft Support |
| Runner NSG/NIC | Ready | Project |
| Existing RRW App Service/PE/DB/KV | Ready foundation | Project |
| Existing public IP / DNAT | Ready foundation | IT |
| RRW production deployment | Blocked by runner + Cordware retrofit | Project |

---

## 12. Recommended sequencing

Do not wait for the runner VM capacity issue before beginning the Cordware retrofit.

The two workstreams can proceed in parallel.

### Workstream A — RRW / Cordware application architecture

1. adopt the Cordware behavior specification;
2. audit RRW for root-path assumptions;
3. choose prefix-preserve versus prefix-strip routing;
4. implement configurable subpath support;
5. add automated subpath tests;
6. design/prototype Easy Auth behavior under `cordware.nus.edu.sg/reviewrobin`;
7. implement the Cordware landing shell.

### Workstream B — Azure infrastructure

1. complete approval/DNS for `cordware.nus.edu.sg`;
2. obtain TLS certificate;
3. receive Microsoft Support advice on runner VM capacity;
4. create runner VM;
5. configure shared HTTPS listener;
6. configure Cordware path-based routing/rewrite rules;
7. configure per-backend health probes;
8. complete Key Vault/DB private execution work;
9. deploy/test RRW through the Cordware path.

---

## 13. End-state wording

The previous end target:

> GitHub repository -> OIDC-authenticated deployment through an in-VNet runner -> private Azure Web App -> private PostgreSQL/Key Vault -> NUS public publishing path via Application Gateway -> NUS Entra sign-in -> usable Review Robin Web application.

should now be expanded to:

> Cordware shared public host (`cordware.nus.edu.sg`) -> Application Gateway path routing -> independently deployed applications such as Review Robin Web -> shared/coherent NUS Entra authentication experience -> application-local authorization and data boundaries.

For RRW specifically:

> GitHub repository -> OIDC-authenticated deployment through an in-VNet runner -> private RRW App Service + private PostgreSQL/Key Vault -> Application Gateway route `/reviewrobin` under `cordware.nus.edu.sg` -> NUS Entra sign-in -> RRW-local authorization -> usable Review Robin Web application.
