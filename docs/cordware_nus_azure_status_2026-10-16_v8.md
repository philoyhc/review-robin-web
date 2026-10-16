# Cordware — NUS Azure Deployment Status and Architecture Report

**Version:** 8  
**Date:** 16 October 2026  
**Status:** Current architecture and implementation handoff  
**Public namespace:** `cordware.nus.edu.sg`  
**Subscription:** `sub-nrrw-prd-reviewrobinweb`  
**Subscription ID:** `bfda7cd6-a4cf-4d98-9048-eec5afd2b1b1`  
**Tenant ID:** `5ba5ef5e-3109-4e77-85bd-cfeb0d347e82`  
**Compute RG:** `rg-nrrw-prd-compute-01`  
**Network RG:** `rg-nrrw-prd-network`  
**Monitoring RG:** `rg-nrrw-prd-monitor-01`  
**Region:** Southeast Asia

---

## 1. Executive summary

The production architecture has changed from a standalone Review Robin Web deployment to a shared **Cordware** application host.

NUS IT has advised the following target:

> **one domain namespace, one SSL/TLS certificate, one App Service, one Easy Auth boundary, with project-side separation into application modules.**

The intended public structure is:

```text
https://cordware.nus.edu.sg/
    -> Cordware landing page

https://cordware.nus.edu.sg/reviewrobin
    -> Review Robin module

https://cordware.nus.edu.sg/residentialapps
    -> Residential Apps module

https://cordware.nus.edu.sg/<future-module>
    -> future module
```

The deployment model is now:

> **independent canonical app repos -> automated synchronization into a Cordware integration/deployment repo -> one private Cordware App Service -> one production deployment.**

Authentication and authorization are deliberately separated:

- **Entra / Easy Auth** establishes trustworthy NUS identity;
- **each module** enforces its own application authorization.

The existing Azure infrastructure was originally provisioned with RRW-specific names. Those physical Azure resource names should generally be **retained** and reinterpreted as Cordware platform resources rather than recreated solely for naming consistency.

---

## 2. Naming policy: legacy physical names vs logical ownership

Many existing Azure resources contain `nrrw`, `rrw`, or `reviewrobinweb` in their names because RRW was the original deployment target.

Examples include:

- `sub-nrrw-prd-reviewrobinweb`
- `rg-nrrw-prd-compute-01`
- `vnet-nrrw-prd-hybrid`
- `asp-nrrw-prd-reviewrobinweb-01`
- `app-nrrw-prd-reviewrobinweb-01`
- `psql-nrrw-prd-reviewrobinweb-01`
- `kv-nrrw-prd-rrw-01`
- `law-nrrw-prd-reviewrobinweb-01`
- `ai-nrrw-prd-reviewrobinweb-01`
- `agw-nrrw--intr-app`

These names are now treated as **legacy physical names**.

Unless otherwise stated, those resources are now logically part of the Cordware shared production platform.

No renaming/recreation is planned solely to improve naming consistency.

This avoids unnecessary disruption to already-provisioned networking, DNS, identities, endpoints, RBAC, monitoring, and private resource relationships.

---

## 3. Target production architecture

### 3.1 Public ingress

```text
Internet
   |
   v
cordware.nus.edu.sg
   |
   v
Public IP 137.132.48.31
   |
   v
NUS perimeter firewall / DNAT
137.132.48.31 -> 10.9.0.196
   |
   v
Application Gateway
private frontend 10.9.0.196
   |
   v
Single private Cordware App Service
App Service Private Endpoint 10.9.0.132
   |
   +-- /
   |    Cordware shell / landing
   |
   +-- /reviewrobin
   |    Review Robin module
   |
   +-- /residentialapps
   |    Residential Apps module
   |
   +-- /<future>
        future module
```

The Web App remains private-only with:

`publicNetworkAccess = Disabled`

### 3.2 Key architectural simplification

Application Gateway no longer needs to route `/reviewrobin` and `/residentialapps` to different App Service backends.

Application Gateway's primary production role becomes:

- terminate HTTPS for `cordware.nus.edu.sg`;
- forward Cordware traffic to one private App Service;
- health-check the Cordware application.

Module routing happens inside the Cordware application.

---

## 4. Authentication and authorization model

### 4.1 Authentication

Cordware uses one NUS Entra / Easy Auth boundary.

Easy Auth establishes identity only.

The shared authenticated-user context should expose the identity facts required by modules, such as:

- stable Entra/user identifier where available;
- institutional email / UPN;
- display name;
- tenant/provider metadata if needed.

### 4.2 Authorization

Authorization remains fully module-local.

Examples:

- Review Robin retains its operator/admin/super-admin model;
- Residential Apps retains RA/staff/approver/admin and record-level rules;
- future modules may define different authorization models.

An authenticated Cordware user is **not automatically authorized** for every module.

### 4.3 Landing page

The Cordware landing page may show only application tiles the user is eligible to discover.

This is a navigation/discovery convenience only.

A user who navigates directly to `/reviewrobin` or `/residentialapps` must still be authenticated and authorized by the relevant module.

---

## 5. Source-control and deployment architecture

### 5.1 Canonical source repos

The canonical application repositories remain independent:

- `philoyhc/review-robin-web`
- `philoyhc/nuscr-res-apps`
- future app-specific repos as needed

These repositories remain authoritative for:

- application source code;
- module-specific tests;
- module-specific migrations;
- application authorization;
- app-specific documentation/issues/PRs.

### 5.2 Cordware integration/deployment repo

A separate Cordware repository should be created:

`philoyhc/cordware`

It is authoritative for:

- Cordware shell / landing page;
- shared authenticated-identity plumbing;
- integrated route composition;
- exact upstream app versions included;
- cross-module integration tests;
- production packaging;
- Azure production deployment.

### 5.3 Synchronization model

Application source is synchronized one-way into Cordware through automated PRs.

Example:

```text
review-robin-web
      |
      | sync PR
      v
    cordware
      ^
      | sync PR
      |
nuscr-res-apps
```

The Cordware copy of an application is not edited directly.

If Cordware integration reveals an RRW bug:

1. fix it in `review-robin-web`;
2. merge there;
3. resync that revision into Cordware.

The same applies to Residential Apps.

### 5.4 Module manifest

Cordware should record exact upstream commits:

```yaml
modules:
  reviewrobin:
    repo: philoyhc/review-robin-web
    commit: <sha>
    path: app/reviewrobin

  residentialapps:
    repo: philoyhc/nuscr-res-apps
    commit: <sha>
    path: app/residentialapps
```

This supports auditability, rollback, and future separation.

---

## 6. Azure resources: logical reclassification

### 6.1 Resources now considered Cordware platform resources

The following should now be regarded as shared Cordware production infrastructure despite legacy RRW names:

- App Service Plan
- production Web App
- Web App managed identity
- Web App Private Endpoint
- Application Gateway
- public IP / DNAT path
- Easy Auth boundary
- Key Vault
- Log Analytics
- Application Insights
- VNet and shared subnets
- runner subnet / NSG / NIC / future VM
- production GitHub deployment identity / workflow
- PostgreSQL server as shared database infrastructure

### 6.2 Resources that remain RRW-specific logically

The following remain RRW-owned:

- `reviewrobin` database;
- RRW DB application role;
- RRW migrations;
- RRW-specific secrets/config;
- RRW authorization;
- RRW module routes under `/reviewrobin`;
- canonical `review-robin-web` repo.

Residential Apps should receive equivalent module-specific persistence/config boundaries.

---

## 7. Network foundation

### 7.1 VNet

`vnet-nrrw-prd-hybrid`

Current address space:

`10.9.0.128/25`

Current subnets:

- `subnet-nrrw-prd-inte-pe-01` — `10.9.0.128/28`
- `subnet-nrrw-prd-inte-db-01` — `10.9.0.144/28`
- `subnet-nrrw-prd-inte-app-01` — `10.9.0.160/27`
- `subnet-nrrw-prd-inte-agw-01` — `10.9.0.192/28`
- `net-nrrw-prd-inte-runner-01` — `10.9.0.208/28`

The remaining two `/28` blocks from the added `/26` are intentionally unconfigured and reserved for future capacity.

### 7.2 Routing

Route table:

`rt-azlz-vnet-nrrw-prd-hybrid`

Default route:

`0.0.0.0/0 -> VirtualAppliance 10.0.0.38`

Therefore Cordware runtime traffic and runner Internet-bound traffic follow the NUS firewall path.

---

## 8. Application Gateway and public publishing

Application Gateway:

`agw-nrrw--intr-app`

Current state:

- running;
- private frontend: `10.9.0.196`;
- backend target: `10.9.0.132`;
- generic/default HTTP listener on port 80;
- generic/default basic routing rule;
- no production TLS certificate yet.

Public IP:

`137.132.48.31`

Confirmed public path:

`137.132.48.31 -> DNAT -> 10.9.0.196 -> 10.9.0.132`

### 8.1 Production configuration still required

The final production configuration should now be Cordware-specific:

- hostname: `cordware.nus.edu.sg`;
- HTTPS listener;
- Cordware TLS certificate;
- backend settings appropriate for the single private App Service;
- correct host-header behavior;
- Cordware health probe;
- end-to-end validation.

The previous RRW-specific path-routing design is no longer required.

---

## 9. App Service

### 9.1 App Service Plan

Physical resource:

`asp-nrrw-prd-reviewrobinweb-01`

- Linux
- P0v3 / Premium0V3
- Southeast Asia

Logical role:

**Cordware production App Service Plan**

### 9.2 Web App

Physical resource:

`app-nrrw-prd-reviewrobinweb-01`

- Python 3.12
- Always On
- HTTPS-only
- `publicNetworkAccess = Disabled`
- state: Running

Logical role:

**Cordware production Web App**

The project should first assess whether this existing Web App can simply become the Cordware runtime target.

This is preferred over creating a new App Service if:

- configuration can be updated safely;
- legacy resource naming is acceptable;
- no NUS policy requires a newly named resource.

### 9.3 Managed identity

Existing system-assigned managed identity principal:

`164bf965-59c9-45a7-a717-b20460e50448`

Logical role:

**Cordware runtime managed identity**

Its permissions should be reviewed against Cordware's final shared runtime needs.

---

## 10. App Service Private Endpoint and DNS

Private Endpoint:

`pe-nrrw-prd-reviewrobinweb-app-01`

Private IP:

`10.9.0.132`

Private DNS zone:

`privatelink.azurewebsites.net`

Current records resolve the existing App Service and SCM endpoint to `10.9.0.132`.

Logical role:

**Cordware private App Service endpoint**

No change is required solely because RRW becomes a Cordware module.

---

## 11. Easy Auth / Entra

Current registration:

`NRRW PRD - Review Robin Web (Easy Auth)`

Client ID:

`281691c5-702b-48fa-942c-3074cf3968e2`

Tenant:

`5ba5ef5e-3109-4e77-85bd-cfeb0d347e82`

Admin consent is complete for:

- `openid`
- `profile`
- `email`

Easy Auth v2 is enabled on the App Service.

### 11.1 Required Cordware transition

The current RRW-specific registration should be reviewed for repurposing rather than automatically replaced.

Preferred path if EUC/IT permits:

1. retain the existing client ID;
2. rename the registration display name to a Cordware name;
3. retain the already-approved delegated permissions;
4. add/update the production redirect URI for `cordware.nus.edu.sg`;
5. continue using it as the single Cordware Easy Auth identity boundary.

This preserves completed consent work and minimizes new EUC intervention.

### 11.2 Credential wiring

Remaining work still includes:

- private Key Vault validation;
- client secret creation/rotation as required;
- Key Vault-backed App Service setting;
- `clientSecretSettingName`;
- end-to-end Cordware sign-in validation.

---

## 12. PostgreSQL

Physical server:

`psql-nrrw-prd-reviewrobinweb-01`

PostgreSQL 16.

Private IP:

`10.9.0.148`

Private DNS zone:

`nrrw.postgres.database.azure.com`

Logical role:

**Cordware shared PostgreSQL infrastructure**

### 12.1 RRW database

Existing database:

`reviewrobin`

This remains RRW-specific.

Remaining RRW DB work:

- create least-privilege RRW app role;
- run RRW migrations;
- validate RRW connectivity.

### 12.2 Future module data

Residential Apps should receive its own database or schema boundary.

Recommended principle:

> one App Service does not imply one undifferentiated application database.

Where practical, use separate DB roles per module.

---

## 13. Key Vault

Physical resource:

`kv-nrrw-prd-rrw-01`

Private Endpoint IP:

`10.9.0.133`

Logical role:

**Cordware production Key Vault**

The legacy name may remain.

Secrets should be namespaced clearly, for example:

- RRW-specific DB/config secrets;
- Residential Apps secrets;
- shared Cordware secrets.

Do not turn module-specific secrets into generic shared credentials merely because they live in one vault.

---

## 14. Monitoring

Physical resources:

- `law-nrrw-prd-reviewrobinweb-01`
- `ai-nrrw-prd-reviewrobinweb-01`

Logical role:

**Cordware production telemetry**

Recommended runtime convention:

- shared Application Insights / Log Analytics;
- module name included in structured logs/telemetry;
- module-specific dashboards/queries where useful.

---

## 15. GitHub deployment identity

Current deployment registration:

`NRRW PRD - Review Robin Web (GitHub deploy)`

Client ID:

`ffa64d98-87c1-463b-aedb-9bcff1355fbe`

Current OIDC subject:

`repo:philoyhc/review-robin-web:ref:refs/heads/main`

Existing role:

- Website Contributor
- scoped to `app-nrrw-prd-reviewrobinweb-01`

### 15.1 Cordware transition

Preferred path if technically/governance-wise acceptable:

1. retain the same Azure service principal / app registration;
2. retain its existing Website Contributor assignment;
3. rename its display name to Cordware;
4. add or replace the federated credential with:

`repo:philoyhc/cordware:ref:refs/heads/main`

or a production GitHub-environment subject if adopted.

If this works, IT may **not** need to perform another Website Contributor role assignment.

This should be tested/confirmed before requesting a new deploy identity.

---

## 16. GitHub Actions runner

Prepared resources:

- subnet: `net-nrrw-prd-inte-runner-01`
- NSG: `nsg-nrrw-prd-runner-01`
- NIC: `nic-nrrw-prd-runner-01`
- private IP: `10.9.0.212`
- public IP: none

Logical role:

**Cordware production integration/deployment runner**

The runner should handle:

- Cordware production deployment;
- RRW migrations;
- Residential Apps migrations;
- Key Vault private operations;
- PostgreSQL administration;
- private App Service deployment/SCM;
- future Cordware integration tasks.

### 16.1 Current blocker

VM allocation in Southeast Asia remains blocked by capacity.

Confirmed failed sizes include:

- `Standard_B2ms`
- `Standard_B2s_v2`
- `Standard_D2as_v7`
- `Standard_D2s_v3`

This is a capacity/allocation issue, not subscription quota.

**Current external status:** NUS IT is waiting for Microsoft Support.

---

## 17. GitHub repository settings and production workflow

The old RRW production-deployment assumption is superseded.

### 17.1 Source repos

`review-robin-web` and `nuscr-res-apps` retain application CI and source ownership.

They do not need Azure production deployment rights merely to synchronize into Cordware.

### 17.2 Cordware repo

Production Azure secrets/variables should live in the Cordware repo.

Likely shared deployment settings include:

- Azure client ID;
- tenant ID;
- subscription ID;
- Web App name;
- Cordware production environment settings.

Module-specific secrets should remain separately named, for example:

- `RRW_DATABASE_URL`
- Residential Apps database secret
- module-specific configuration values

rather than one ambiguous `NUS_DATABASE_URL`.

### 17.3 Production deployment workflow

The final production workflow should live in `philoyhc/cordware`.

It should:

1. build the assembled Cordware application;
2. run required module migrations;
3. deploy the single Cordware artifact;
4. perform Cordware-level health/smoke checks.

---

## 18. External IT / EUC work still expected

After the architecture discussion with IT, remaining external work is now concentrated and mostly one-off.

### 18.1 DNS

Complete/confirm publication of:

`cordware.nus.edu.sg`

### 18.2 TLS certificate

Provide or approve the certificate/process for:

`cordware.nus.edu.sg`

### 18.3 Runner VM capacity

Continue the Microsoft Support escalation for a deployable VM SKU/capacity path.

### 18.4 Easy Auth / Entra governance

Assist only if required to:

- rename/repurpose the existing RRW Easy Auth registration;
- update production redirect URI under NUS governance;
- create a replacement registration if repurposing is not allowed.

### 18.5 Production deploy identity

IT intervention may be avoidable if the existing deployment service principal can be repurposed while retaining its current Website Contributor role.

If a new Cordware deployment identity is required, IT will need to grant the Azure role because the project cannot create role assignments.

### 18.6 Future networking

IT remains responsible for future VNet/subnet/route-table changes if the platform outgrows current reserved capacity.

---

## 19. Work that no longer needs repeated IT involvement

Under the adopted architecture, adding a new Cordware module should generally **not** require:

- a new public hostname;
- a new SSL certificate;
- a new App Service;
- a new App Service Private Endpoint;
- a new Easy Auth boundary;
- a new Application Gateway backend/listener;
- a new GitHub production deploy identity;
- a new Website Contributor grant;
- a new runner.

A new module is primarily a project-side source/integration concern.

---

## 20. Project-side work now required

### Cordware platform

1. create `philoyhc/cordware`;
2. implement Cordware shell / landing page;
3. establish one shared identity interface;
4. establish module route structure;
5. establish synchronization/manifest model;
6. establish integration CI;
7. build the final production deployment workflow.

### Review Robin

1. retrofit RRW as a Cordware module;
2. expose RRW under `/reviewrobin`;
3. replace standalone Easy Auth assumptions with shared trusted identity consumption;
4. preserve RRW authorization;
5. preserve RRW DB/migration boundaries;
6. add module-mode/path-prefix tests;
7. define deterministic sync/export behavior.

### Residential Apps

1. retain `nuscr-res-apps` as canonical source;
2. expose Residential Apps under `/residentialapps`;
3. preserve its internal permissions/data boundaries;
4. define Cordware integration/sync contract;
5. keep its DB/schema logically separate.

---

## 21. Current status matrix

| Item | Status | Logical owner / next action |
|---|---|---|
| Cordware hostname | Approved direction; publication to confirm | IT / DNS |
| TLS certificate | Pending | IT / certificate process |
| Public IP `137.132.48.31` | Ready | Shared Cordware ingress |
| DNAT to `10.9.0.196` | Ready | Shared Cordware ingress |
| Application Gateway | Ready foundation | Project final HTTPS config |
| Cordware App Service | Existing RRW Web App to be repurposed if feasible | Project |
| App Service PE `10.9.0.132` | Ready | Cordware |
| VNet integration / Route All | Ready | Cordware |
| Easy Auth admin consent | Complete | Repurpose registration if permitted |
| Easy Auth production callback | Pending Cordware update | Project / EUC if needed |
| Key Vault | Ready foundation | Cordware shared vault |
| PostgreSQL server | Ready foundation | Cordware shared DB infrastructure |
| `reviewrobin` database | Ready | RRW |
| Log Analytics / App Insights | Ready | Cordware telemetry |
| Runner subnet / NSG / NIC | Ready | Cordware |
| Runner VM | Blocked on SEA capacity | IT + Microsoft Support |
| Existing deploy SP RBAC | Ready on current Web App | Try to repurpose for Cordware |
| Cordware repo | Not yet created | Project |
| RRW Cordware retrofit | Not started | Project |
| Residential Apps Cordware integration | Not started | Project |
| Cordware production workflow | Not yet created | Project |

---

## 22. Immediate next sequence

The most useful immediate sequence is:

1. confirm DNS publication status for `cordware.nus.edu.sg`;
2. confirm TLS certificate process/status;
3. determine whether the existing RRW Easy Auth registration can be renamed/repurposed;
4. determine whether the existing RRW GitHub deploy app can be renamed/repurposed with a Cordware federated credential;
5. create the Cordware repository;
6. begin RRW modularization and sync-contract work;
7. proceed with Cordware shell/integration CI in parallel with runner-capacity escalation;
8. create the runner VM when Microsoft/NUS IT resolves capacity;
9. finish private DB/Key Vault work;
10. configure final Application Gateway HTTPS listener;
11. deploy Cordware;
12. perform end-to-end tests.

---

## 23. End state

Production:

> **`cordware.nus.edu.sg` -> Application Gateway -> one private Cordware App Service -> one Easy Auth identity boundary -> internally separated modules -> module-local authorization and persistence boundaries.**

Source control:

> **independent canonical app repos -> automated sync PRs -> Cordware integration/deployment repo -> one Azure production deployment.**

Operational principle:

> **change logical ownership and configuration first; retain working Azure physical resources unless recreation is actually necessary.**
