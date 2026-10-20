# Cordware Repository and Deployment Strategy

**Version:** 0.8, 20 October 2026  
**Status:** The adopted strategy (author, 2026-10-19). The direction is decided; smaller details may still shift, and each shift is recorded here. This is not authorization for any single production change.  
**Source of truth:** this file, in `philoyhc/review-robin-web`. The `philoyhc/cordware` planning repo stands down later and is not updated.  
**Deployment:** One integrated application on one Azure App Service, at `https://cordware.nus.edu.sg`.

> **Decision:** Evolve RRW's existing repository **in place** into an asymmetric monorepo. RRW keeps its root-level source and development folders. A deliberately small, stateless `cordware/` host package supplies trusted Entra identity and mounts each application under its own path. Residential Apps follows later in a self-contained `residentialapps/` area. The sequence is **mount RRW at `/reviewrobin` → extract shared identity → establish Residential Apps → integrate and deploy**, and both RRW stages land before Residential Apps arrives.

v0.8 replaces v0.7. It folds v0.7's two addenda into the body, replaces v0.7's standalone-compatibility requirement with the independence requirement in §3, and makes the rest of the document consistent with both. §9 has the version history.

---

## 1. Architectural ownership

Cordware is a **stateless identity and hosting shell**, not a shared business platform.

| Concern | Cordware | RRW | Residential Apps |
|---|---|---|---|
| Authentication | Interpret identity authenticated by Entra / Azure Easy Auth; expose trusted claims | Consume Cordware's identity | Consume Cordware's identity |
| Users and roles | **None stored** | Own users, operator/admin/participant permissions | Own RA/staff/admin users and permissions |
| Authorization | No access decisions for any application | Own | Own |
| Auditing | No business or login audit table | Audit business and account-state actions | Audit business actions |
| Data and migrations | **No database or Alembic** | Own | Own |
| UI | Landing page linking the mounted applications; host health | RRW application | Support Log, RA Leave, RA Events |

Cordware's functions are limited to trusted identity resolution, application mounting, the landing page, and minimal process configuration, lifecycle, health and logging. The landing page lists the applications that are mounted, not the ones a viewer is entitled to use: each application gates its own routes. A Cordware database or generic authorization framework is **not planned**.

**RRW is the senior tenant and the starting source of reusable host code, not the permanent owner of shared authentication.** Identity resolution moves to Cordware in stage 2 because the host itself needs it, not merely because a second application will. Beyond identity and hosting, extract shared code only when a second application actually needs it.

## 2. Repository layout and development practice

RRW's files stay substantially at the repository root:

```text
review-robin-web/                    # GitHub rename to cordware is optional, later
├── app/                             # RRW's Python package, imports app.*
├── spec/  docs/  guide/             # RRW contract / reference / plans
├── tests/  tools/                   # RRW verification
├── alembic/  alembic.ini            # RRW migrations
│
├── cordware/                        # Stateless host package
│   ├── main.py                      # Assembled entry point; mounts the configured apps
│   ├── identity.py                  # Trusted institutional principal (stage 2)
│   ├── web/                         # Landing template/assets
│   ├── spec/  docs/  guide/
│   ├── tests/  tools/
│   └── AGENTS.md
│
├── residentialapps/                 # Residential's bounded development area (stage 3)
│   ├── app/                         # Imports residentialapps.app.*
│   │   ├── core/  support/  leave/  events/  web/
│   ├── alembic/  alembic.ini
│   ├── spec/  docs/  guide/
│   ├── tests/  tools/
│   ├── constitution.md
│   └── AGENTS.md
│
├── deployment/                      # Release packaging and migration workflow
├── .github/workflows/  .claude/
├── pyproject.toml                   # Package discovery and the shared dependency set
├── constitution.md  AGENTS.md  README.md
└── requirements.txt                 # Existing setup retained initially
```

Create host files only when they are needed. **Do not** add a Cordware ORM, user registry, migrations or audit store. RRW's `app` stays the only top-level package named `app`; Residential's upstream `app` package is re-namespaced on import, including its imports, tests, Alembic scripts and packaging configuration.

**Separate development ownership** is kept within the one repository:

| Owner | Settled contract | Reference and rationale | Active plans and decisions | Verification |
|---|---|---|---|---|
| RRW | `spec/` | `docs/` | `guide/` | `tests/`, `tools/` |
| Cordware | `cordware/spec/` | `cordware/docs/` | `cordware/guide/` | `cordware/tests/`, `cordware/tools/` |
| Residential | `residentialapps/spec/` | `residentialapps/docs/` | `residentialapps/guide/` | `residentialapps/tests/`, `residentialapps/tools/` |

RRW's practice, documented in `rrw_sdd_in_practice.md`, carries over: **plan on the way in; spec on the way out.** An open segment plan records the planned changes, decisions, blast radius, PR ladder and documentation impact; at its close, approved behavior is reconciled into the owner's `spec/`, reference docs are updated and the plan is archived. Outside an open segment, a code/spec discrepancy is reported rather than silently resolved. Maker/checker separation, close checks and the author's browser verification carry over too. Archives record history, not live requirements.

Root `AGENTS.md` routes work to the right owner; each nested `AGENTS.md` carries local instructions. RRW's tools and history-based metrics that assume the whole repository is RRW's need path scoping once the other owners have code.

## 3. Hosting, independence and trusted identity

### Mounting

The host builds a FastAPI application, adds its own landing page and health endpoint, and mounts each configured application at its path:

```python
# cordware/main.py: conceptual, not production-ready
from fastapi import FastAPI
from app.main import create_app as create_rrw

def create_app() -> FastAPI:
    host = FastAPI(title="Cordware")
    # host landing page and /health
    # for each application named in the CORDWARE_APPS setting:
    host.mount("/reviewrobin", create_rrw())
    return host
```

| Standalone RRW URL today | Cordware URL |
|---|---|
| `/` | `/reviewrobin/` |
| `/operator/sessions` | `/reviewrobin/operator/sessions` |
| `/me` | `/reviewrobin/me` |
| `/static/...` | `/reviewrobin/static/...` |

Cordware owns `/` (the landing page) and `/health`. Easy Auth's `/.auth/*` paths stay at the host level.

**The mount supplies the prefix.** `host.mount("/reviewrobin", …)` strips the prefix before RRW sees a request and sets `root_path`, so route-aware URLs (`url_for`, `request.url_for`) gain `/reviewrobin` without help. No `BASE_PATH` setting or path-rewriting shim is needed, on one condition: **Application Gateway forwards the public path unchanged**, with no path override in its backend settings, so a request for `/reviewrobin/...` reaches Cordware with its prefix intact. A gateway that stripped the prefix would leave Cordware nothing to route on. The production listener and backend settings still to be configured (v8 status report §8.1) must preserve the path.

**Mounting is not URL rewriting.** RRW still writes many links as literal root paths, such as `/operator/sessions` and `/me`. Every redirect, template link, form action, script request path, static URL, cookie path, auth return link and emailed link is swept onto route-aware generation. Links are never written with a hard-coded `/reviewrobin` prefix.

**Old root links are not kept.** There are no redirects from `/operator/...` or `/me` to `/reviewrobin/...`: nothing consequential links to them.

### The independence requirement

**Cordware plus any single application is a complete, runnable system**, locally, in tests and in CI.

- **Dependencies point one way: applications → Cordware.** RRW and Residential Apps may import Cordware's identity and host interfaces. They never import each other. Cordware imports an application only through its factory, at the mount point.
- **The mounted set is a setting.** `CORDWARE_APPS` names the applications to mount (for example `reviewrobin,residentialapps`) and defaults to all of them. An empty value runs Cordware alone, with the landing page and `/health`, which is how the host is tested by itself. Mounting is explicit: there is no plugin discovery.
- **Only mounted applications are configured.** Startup validation, settings and migrations apply only to the applications mounted. A Cordware + RRW run never requires Residential's settings, and the reverse holds too.
- **Packages stay shared.** One Python environment and lockfile serve every application (§6). Independence is a property of the code, not of the installed packages.
- **A test enforces it.** An import-boundary test fails if `app/` imports `residentialapps`, if `residentialapps/` imports `app`, or if `cordware/` imports either beyond their factories.
- **Each application stays a complete ASGI app.** RRW's `create_app()` returns an application that can be mounted, and that RRW's own test suite exercises directly at app-relative paths. There is no supported standalone runtime: RRW is served only through Cordware, at `/reviewrobin`, locally and when deployed.

### Construction, lifecycle and logging

- **Each application is constructed once.** Importing an application's factory has no side effects. RRW's module-level `app = create_app()` in `app/main.py` is removed, and every start command (local, dev slot, NUS) becomes the one Cordware entry point.
- **The host owns process-wide setup.** Root-logger configuration moves to Cordware. An application's factory stops configuring the root logger and logs under its own named logger, with the application recorded in each record.
- **Lifespans are explicit.** A mounted application's lifespan does not run under the parent automatically. Startup work therefore happens in the application's factory, or Cordware's own lifespan runs each mounted application's lifespan explicitly.
- **A critical application failure fails startup.** If a mounted application's startup validation fails, the process fails, unless a deliberately engineered degraded mode is approved later.

### Behavior under the mount

These requirements, carried from the archived integration spec v0.2, apply from stage 1:

1. **Deep links survive sign-in.** A signed-out user opening `/reviewrobin/sessions/123` goes through Easy Auth and returns to that full path, not to `/` or `/reviewrobin/`.
2. **Probe paths need no interactive sign-in.** `/health` for the host, and an optional `/reviewrobin/health` for RRW.
3. **A mounted application keeps its own request handling.** RRW's error handlers, middleware order and app-wide dependencies behave under the mount as they did on their own.
4. **No backend hostname leaks.** Downloads and every absolute URL, invitation emails included, stay under the application's path and never carry the App Service's `azurewebsites.net` name.

### Shared identity, application-specific permissions

Microsoft Entra / Azure Easy Auth performs institutional sign-in. In stage 2, Cordware takes over interpreting the **trusted** claims at the protected ingress and exposes a small request-level identity: principal/object ID where available, email/UPN, display name and provider. It never trusts spoofable identity headers from outside the protected ingress. Fake local identity is Cordware's alone, and is refused outside local development.

RRW maps that identity to its own user and permission records; Residential does its own mapping. Neither receives an authorization decision from Cordware. Fake *roles* (RRW's operator, admin and super-admin flags, for example) stay with each application, because they are authorization, not identity.

RRW's tested Easy Auth parsing moves into `cordware/identity.py` once the mounted URL behavior is established. Because RRW has no standalone runtime, it keeps no second parser of its own.

## 4. Audit and persistence

### Audit only meaningful application actions

RRW deliberately **does not write audit records merely for login**. Sign-in records belong to Entra / Easy Auth, and an application visit is not necessarily a new sign-in.

RRW's `audit_events` table has foreign keys to RRW's `users` and `sessions`. It records business actions and certain account-state changes, such as a recorded principal ID or an email reconciliation. First-time user creation is not a separate login event. These records stay with RRW.

RRW's `users` table stays too. It holds Entra principal ID, email and name, but also RRW roles, SMTP details, preferences and relational links. Moving **identity-processing code** to Cordware does not move **identity-related rows**.

Residential owns its business-action audit in the same way. Cordware uses ordinary host diagnostics and telemetry where warranted, **not** a persistent cross-application audit or users table.

### Production PostgreSQL: B or C

The shortlist is **B or C on the existing institutional PostgreSQL server. C is preferred**, subject to NUS IT feasibility, cost and operational constraints.

| | **B: one database, separate schemas** | **C: two databases, same server (preferred)** |
|---|---|---|
| Structure | RRW's tables plus Residential's `core`, `support`, `leave`, `events` schemas in one database | RRW's database plus a separate Residential database holding those four schemas |
| Incremental base cost | Normally minimal | Normally no second compute or server charge for another database; more workload or storage can cost more |
| Access boundary | Schema-specific roles and grants | Database-specific access plus schema roles and grants |
| Migration boundary | Separate Alembic histories **and separately located version tables** | Separate Alembic histories in separate databases |
| Cross-application SQL | Technically possible; discouraged | Ordinary cross-database foreign keys and joins unavailable |
| Isolation | Moderate logical separation | Stronger administrative and logical separation |
| Server compute, availability and Azure point-in-time recovery | Shared | Shared |
| Development CI | Independent | Independent |

**B** needs disciplined schema qualification, search-path and grant management, migration scope, and separately located Alembic version tables to protect RRW's existing objects. **C** is cleaner for credentials and migration isolation, but it is still **one** server, with shared capacity and server-level restore. Logical backups can cover database-specific recovery under either option.

**Choose C** if NUS IT can create a second database and roles on the existing server without disproportionate obstacles or material extra cost; otherwise **B** is an acceptable fallback. Shared business tables (A) and a second PostgreSQL server (D) are not pursued without a new requirement.

Settings are namespaced: `RRW_DATABASE_URL` and `RES_DATABASE_URL`. Under B they can address the same database with distinct restricted credentials; under C, two databases on one server. RRW's existing `DATABASE_URL` keeps working, with a documented, unambiguous precedence between the two names.

**Cordware needs no database under either option.**

## 5. Implementation pathway and stage gates

Make small, reviewable changes. **Nothing is deployed to the NUS host until this repository runs as Cordware with RRW mounted**, so RRW is never deployed there on its own and the first NUS deploy uses the Cordware entry point.

| Stage | Work | Gate before the next stage |
|---|---|---|
| **0. Baseline and privacy** | Record RRW and Residential source SHAs, tests, migration heads, launch and deploy configuration. Make this repository **private before importing Residential's private material**, then check Actions, access and integrations after the change. | Known-good RRW baseline, provenance kept |
| **1. Mount RRW** | Add the minimal `cordware/main.py` and the `CORDWARE_APPS` setting; mount RRW at `/reviewrobin`; move the module-level app out of `app/main.py` and host-owned logging into Cordware; sweep root-relative URLs onto route-aware generation; add the import-boundary test; test mounted routes, redirects, static assets, deep links and authorization. The personal dev slot switches to the Cordware entry point here, as the live check of §3's behavior requirements under real Easy Auth. | RRW behavior unchanged at `/reviewrobin`; Cordware alone and Cordware + RRW both run |
| **2. Extract shared identity** | Move RRW's tested Easy Auth claims parsing into `cordware/identity.py`, with fake local identity; RRW consumes it and keeps its `users`, roles and audits. No Cordware database. | Trusted-identity interface tested on its own; RRW permission behavior unchanged |
| **3. Establish Residential** | Import its skeleton, architectural decisions, specs, plans, tests, tools, agent guidance and Alembic; re-namespace `app`; consume Cordware identity; mount at `/residentialapps`. Settle B or C **before production database setup**, not necessarily before the code import. | Cordware + Residential runs without RRW; both applications coexist |
| **4. Integrated release** | Resolve the one dependency environment; package the applications and assets; run each mounted application's migrations with its own database and credentials; verify in staging, then a controlled production cutover. | One validated build and release, with documented rollback and recovery |

The NUS deploy workflow currently packages `app/`, `alembic/`, `alembic.ini`, requirements and `antenv/`. Broaden the artifact only when the integrated application is ready. The **deployment workflow** runs each mounted application's migrations; Cordware does not become a migration service. Prefer backward-compatible migrations: reverting code does not reverse a database change.

## 6. Scoped CI and shared-runtime risks

One repository and one production deployment **do not require RRW's database tests on every Residential PR.** Each application keeps its own CI jobs and disposable Postgres fixtures, and routine CI never runs against production data.

| Changed area | Expected checks |
|---|---|
| RRW only | RRW's tests (Cordware + RRW), and its migrations where touched |
| Residential only | Residential's tests (Cordware + Residential) and its Alembic round trips against a **Residential-only disposable database** |
| Cordware | Host unit tests with no applications mounted, plus targeted mount and identity tests; usually **no PostgreSQL** |
| Shared dependencies or packaging | Every application's tests, and the integrated checks |
| Production release candidate | The full agreed regression, migration, auth, routing and artifact checks |

Residential's current `ci-postgres.yml` already provisions its own disposable Postgres container and runs upgrade/downgrade round trips and pytest. Keep that independence **whether production uses B or C**. Prefer path detection inside a job over skipping required workflows, which can leave pull-request checks pending. The import-boundary test (§3) runs on every PR.

The production process still shares Python dependency resolution, startup, compute and the release boundary. A compromise of the shared process can potentially reach both applications' database credentials. Database permissions and application authorization reduce that risk but are not hard runtime isolation. B and C both share the PostgreSQL server's capacity, failure and recovery domains.

## 7. Repository governance

- **Active source of truth:** `philoyhc/review-robin-web`, keeping its Git and PR history and RRW's development machinery. No parallel writable application source lives in `philoyhc/cordware`.
- **Repository privacy:** GitHub visibility applies to the whole repository, not individual folders. Make this repository private **before** importing Residential's private sources or documents. Agreeing to that does not confirm it has been done.
- **Residential's transfer:** keep Residential's provenance and archived planning material. Archive its original repository only after its content, workflows and migration history are verified here.
- **Cordware planning documents:** v0.4–v0.7, the planning notes and integration spec v0.2 are in `docs/archive/` as decision history. The `philoyhc/cordware` copies are not maintained.
- **Optional rename:** postpone `review-robin-web` → `cordware` until operation is stable. The `philoyhc/cordware` planning repo must first give up that name, and GitHub OIDC federation and other integrations may need updating.
- **Institutional deployment:** the NUS Azure OIDC subject is scoped to `repo:philoyhc/review-robin-web:ref:refs/heads/main`. Keeping the repository name through functional integration may reduce IT changes; verify the live configuration before cutover.

## 8. Acceptance, open decisions and non-goals

**The architecture is realized when:**

- RRW's folders, history, tooling and behavior survive, served at `/reviewrobin`;
- mounted `/reviewrobin/operator/...` and `/reviewrobin/me` routes, deep links and every critical link work, and §3's behavior requirements hold;
- Cordware is stateless and supplies trusted identity, hosting and the landing page;
- Cordware alone, Cordware + RRW and Cordware + Residential each run, and the import-boundary test passes;
- each application enforces its own permissions and owns its action audits, data and migrations;
- Residential has its own `spec/`, `docs/`, `guide/`, `tests/` and `tools/` folders, and scoped CI;
- B or C is implemented safely (C preferred);
- the integrated artifact is staged, tested and deployed, with a documented recovery path.

**Implementation decisions still open:** the lifespan contract's exact shape; the route-aware URL helper for strings built outside a request; the trusted-identity interface; the `DATABASE_URL` / `RRW_DATABASE_URL` precedence; B versus C, and the database-role and recovery arrangements with NUS IT; dependency locking and the build artifact; CI required-check and release-gate policy; path scoping for RRW's repo-wide tooling; repository privacy and rename timing.

**Non-goals:** moving RRW's source into a `reviewrobin/` folder; cross-repository source sync or private package composition; plugin discovery; a supported standalone RRW runtime; Cordware user or role tables, or any Cordware persistence; a login audit table; shared business tables; a second PostgreSQL server without a new requirement; redirects for old root paths; a big-bang rewrite.

## 9. Decision history

| Version | Approach | Status |
|---|---|---|
| v0.4 | Separate canonical RRW and Residential repositories; code synced into Cordware for deployment | Archived |
| v0.5 | Separate installable, pinned application packages composed by Cordware | Archived; a retrospective reconstruction, never adopted |
| v0.6 | One canonical Cordware monorepo with symmetrical subprojects | Archived; refined into v0.7 |
| v0.7 | Evolve RRW in place; minimal Cordware identity and hosting shell; independent Residential development; B/C PostgreSQL shortlist | Archived; adopted 2026-10-19, superseded by v0.8 |
| **v0.8** | v0.7, with its addenda folded in and the independence requirement replacing standalone compatibility | **Current** |

All earlier versions, `cordware_repo_planning.md` and integration spec v0.2 are in `docs/archive/`. They are decision history, not implementation instructions.

**Changed in v0.8** (author, 2026-10-19 and 2026-10-20):

- **Standalone compatibility replaced by independence (§3).** v0.7 required RRW to "work both standalone locally and mounted". v0.8 requires that Cordware plus any single application runs, with the mounted set named by `CORDWARE_APPS` and Cordware runnable alone. Packages stay shared. There is no supported standalone RRW runtime, so RRW keeps no second identity parser.
- **v0.7 Addendum A folded into §3** as "Behavior under the mount": deep links, auth-free probes, mounted request handling, no backend-host leak.
- **v0.7 Addendum B folded into §3 and §5:** the mount replaces the `BASE_PATH` shim; each application is constructed once, with host-owned logging and the module-level app removed; NUS sees only the assembled application; the dev slot switches at stage 1; old root links are not kept.
- **Gateway path forwarding stated (§3):** the mount needs Application Gateway to forward the public path unchanged; v0.7 had called keep-or-strip irrelevant.
- **The v8 status report marked superseded in part:** its source-control and deployment model (independent repos synced into `philoyhc/cordware`) conflicts with this strategy, and the report now says so.
- **Consistency fixes:** identity extraction ahead of Residential is explained (§1); the landing page lists mounted applications (§1, §3); the stage 1 and stage 3 gates name the independence checks (§5); the status line records adoption, and the broken version-history pointer is fixed.
