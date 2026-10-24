# Cordware Repository and Deployment Strategy

> **Retired 2026-10-24.** The Cordware strategy and the NUS deployment material are now maintained privately with the deployment, not in this repository. Kept as public decision history of the host this repository carries; `cordware/spec/host.md` and `cordware/spec/identity.md` cite its §3. Not implementation instructions.

**Version:** 0.8, 20 October 2026; stages 1 and 2 resequenced the same day (§5); fake auth, the platform super-admin and host logging settled 21 October (§3); `APP_ENV`, the fake-auth guard and local testing switches settled the same day (§3); URL emission settled the same day (§3, §8); the prefix flip, the public host for absolute links and the one-application landing page settled 22 October (§1, §8)  
**Status:** The adopted strategy (author, 2026-10-19). The direction is decided; smaller details may still shift, and each shift is recorded here. This is not authorization for any single production change.  
**Source of truth:** this file, in `philoyhc/review-robin-web`. The `philoyhc/cordware` planning repo stands down later and is not updated.  
**Deployment:** One integrated application on one Azure App Service, at `https://cordware.nus.edu.sg`.

> **Decision:** Evolve RRW's existing repository **in place** into an asymmetric monorepo. RRW keeps its root-level source and development folders. A deliberately small, stateless `cordware/` host package supplies trusted Entra identity and mounts each application under its own path. Residential Apps follows later in a self-contained `residentialapps/` area. The sequence is **build the host with RRW still at `/` and sweep RRW's links → extract shared identity, then move RRW to `/reviewrobin` → establish Residential Apps → integrate and deploy**, and both RRW stages land before Residential Apps arrives.

v0.8 replaces v0.7. It folds v0.7's two addenda into the body, replaces v0.7's standalone-compatibility requirement with the independence requirement in §3, and makes the rest of the document consistent with both. §9 has the version history.

---

## 1. Architectural ownership

Cordware is a **stateless identity and hosting shell**, not a shared business platform.

| Concern | Cordware | RRW | Residential Apps |
|---|---|---|---|
| Authentication | Interpret identity authenticated by Entra / Azure Easy Auth; expose trusted claims | Consume Cordware's identity | Consume Cordware's identity |
| Users and roles | **None stored**; one configured platform role, super-admin | Own users, operator/admin/participant permissions | Own RA/staff/admin users and permissions |
| Authorization | No access decisions inside any application | Own | Own |
| Auditing | No business or login audit table | Audit business and account-state actions | Audit business actions |
| Data and migrations | **No database or Alembic** | Own | Own |
| UI | Landing page linking the mounted applications; host health | RRW application | Support Log, RA Leave, RA Events |
| Super-admin | **The platform role:** reads `SUPER_ADMIN_EMAILS`, an App Service application setting, and marks the identity; no Cordware console | Grants the platform super-admin its full rights in RRW; keeps its own app-only admins | Grants the platform super-admin its full rights in Residential; keeps its own app-only admins |
| Logging | Operational events only (§3), to stdout and Azure Monitor | Own operational logs and business audit | Own operational logs and business audit |
| Administration | Through Azure: portal, App Service settings, RBAC on Azure Monitor | In-app, by its own admins | In-app, by its own admins |

Cordware's functions are limited to trusted identity resolution, application mounting, the landing page, and minimal process configuration, lifecycle, health and logging. The landing page lists the applications that are mounted, not the ones a viewer is entitled to use: each application gates its own routes. With exactly one application mounted, `/` redirects to that application's path instead of listing it (author, 2026-10-21). A Cordware database, generic authorization framework, admin interface or dashboard is **not planned**: whatever needs administering at the host level is done through Azure.

**RRW is the senior tenant and the starting source of reusable host code, not the permanent owner of shared authentication.** Identity resolution moves to Cordware in stage 2 because the host itself needs it, not merely because a second application will. Beyond identity and hosting, extract shared code only when a second application actually needs it.

## 2. Repository layout and development practice

RRW's files stay substantially at the repository root. The tree is the
target layout: a folder or file it names is created when it is needed
(below), and several do not exist yet.

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
│   ├── settings.py  logging.py      # Host settings; root-logger setup
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

In the target layout, root `AGENTS.md` routes work to the right owner and each nested `AGENTS.md` carries local instructions; today the root file is RRW's alone. RRW's tools and history-based metrics that assume the whole repository is RRW's need path scoping once the other owners have code.

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

**Mounting is not URL rewriting.** At decision time RRW wrote many links as literal root paths, such as `/operator/sessions` and `/me`. Every redirect, template link, form action, script request path, static URL, cookie path, auth return link and emailed link has since been swept onto mount-aware emission (§8, segment 21B): an app-relative path travels through RRW and gains the mount's `root_path` once, where it is emitted (`app/web/urls.py`). Links are never written with a hard-coded `/reviewrobin` prefix.

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

These requirements, carried from the archived integration spec v0.2, apply from the prefix flip at the end of stage 2:

1. **Deep links survive sign-in.** A signed-out user opening `/reviewrobin/sessions/123` goes through Easy Auth and returns to that full path, not to `/` or `/reviewrobin/`.
2. **Probe paths need no interactive sign-in.** `/health` for the host, and an optional `/reviewrobin/health` for RRW.
3. **A mounted application keeps its own request handling.** RRW's error handlers, middleware order and app-wide dependencies behave under the mount as they did on their own.
4. **No backend hostname leaks.** Downloads and every absolute URL, invitation emails included, stay under the application's path and never carry the App Service's `azurewebsites.net` name.

### Shared identity, application-specific permissions

Microsoft Entra / Azure Easy Auth performs institutional sign-in. In stage 2, Cordware takes over interpreting the **trusted** claims at the protected ingress and exposes a small request-level identity: principal/object ID where available, email/UPN, display name, provider, and whether the user holds the platform super-admin role. It never trusts spoofable identity headers from outside the protected ingress. Fake local identity is Cordware's alone, and is refused outside local development.

RRW maps that identity to its own user and permission records; Residential does its own mapping. Neither receives an authorization decision from Cordware: Cordware asserts one platform role, super-admin, from configuration, and what that role unlocks, like every other permission, each application decides. Fake *application* roles (RRW's operator and admin flags, for example) stay with each application, because they are authorization, not identity. An application's role resolution reads whether the user is the fake one from Cordware's identity, never from its own copy of the fake-auth settings, so there is one source for it.

**Local fake auth.** The baked-in localhost account stays **Local Operator `<operator@example.edu>`**. Cordware builds it (principal ID, email and name) together with the switch that enables it (`ALLOW_FAKE_AUTH`) and the guard described below. While fake auth is on, Cordware also marks that fake user as platform super-admin, so it holds super-admin in every hosted application without any per-application setting. The switch for this, `FAKE_AUTH_SUPER_ADMIN`, moves from RRW to Cordware with its name and its default (on) unchanged, so a local run can still turn it off to test as a non-super-admin; RRW's own copy of the flag retires. Applications recognize the fake user by Cordware's fake marker, not by matching the literal email, so changing the fake account's email in Cordware can't strip its rights in any application.

**Super-admin is a platform role** (author, 2026-10-21). It is the Cordware-level account; each application already has its own application-only admins for everything narrower.

- **Cordware reads it.** `SUPER_ADMIN_EMAILS` becomes a Cordware setting, kept under its current, unprefixed name because it is deliberately shared. It is an App Service application setting: a comma-separated list, so there can be more than one super-admin; matched case-insensitively against the signed-in email; evaluated on every request; never stored.
- **The identity carries it.** Cordware exposes it as a flag on the request-level identity (`is_super_admin`), alongside email and display name. Because applications also judge accounts other than the signed-in user (RRW refuses to demote or remove a super-admin, and its account listings mark and count them), Cordware exposes the same test as a host-level predicate on any email (`is_super_admin_email`), readable outside a request. It also exposes whether the effective list is empty (`super_admin_configured`), on the identity and at host level, so an application can tell "no platform super-admin is configured" from "this user isn't one". The effective list is the configured entries plus, while fake auth and `FAKE_AUTH_SUPER_ADMIN` are both on, the fake account, as RRW computes it today; so the flag, the predicate and `super_admin_configured` always agree. Applications read these three and never parse the setting themselves, so every application interprets the list the same way.
- **The work happens inside each application.** Each application grants the platform super-admin its full rights there, the way RRW's top tier works today, and decides what that means. There is no separate Cordware application, dashboard or console for a super-admin to use.
- **Editing the list is done in Azure**, in the App Service's settings; it can't be changed from inside any application. An empty list, with no fake super-admin, means no platform super-admin: `super_admin_configured` is false, and each application's existing fallback applies (in RRW, any admin may manage admins). Because the setting is Cordware's, the startup warning about an empty list is Cordware's too (host logging, event 1); RRW's own warning retires with its parsing of the setting. When the list has entries, the fallback is off, even for users who aren't in it.

RRW's role resolution (`app/auth/roles.py`) moves from reading `SUPER_ADMIN_EMAILS` itself to reading Cordware's flag, predicate and `super_admin_configured` in stage 2, with the identity extraction.

RRW's tested Easy Auth parsing moves into `cordware/identity.py` once the host exists (stage 1), and before RRW moves to `/reviewrobin`, so the dev slot's one live check at the prefix flip covers the new identity and the new prefix together. Identity parsing reads headers, not paths, so it doesn't depend on the mount. Because RRW has no standalone runtime, it keeps no second parser of its own.

### Environment, guard and local testing switches

**`APP_ENV` is a platform setting** (author, 2026-10-21). Cordware reads it and exposes it as a host-level value; applications consult that value rather than reading the setting themselves. It keeps its name and its default, `local`. Today RRW reads it in two places, both asking only whether it is `local`: its fail-fast startup check (`validate_critical_settings`, which refuses to start when no one could sign in) and the empty-super-admin startup warning, which moves to Cordware (host logging, event 1).

**Cordware enforces the fake-auth guard.** It refuses to start when `ALLOW_FAKE_AUTH` is on and `APP_ENV` is anything other than `local`. At decision time nothing enforced this: fake auth was gated only by `ALLOW_FAKE_AUTH`, and "never enable it when deployed" was a documented rule. The host now refuses at startup (`cordware/main.py`; §8, segment 21C). Every deployed environment, the personal dev slot included, therefore sets `APP_ENV` to a non-`local` value (NUS uses `production`).

**Local testing switches keep their names, defaults and behavior.** Every environment switch RRW reads today stays settable in the repository-root `.env` or per run (`$env:NAME=…` in PowerShell, `export NAME=…` in a POSIX shell), with the shell value overriding `.env`, and a restart picking up a change. One `.env` is read by Cordware and every mounted application. Ownership splits as follows:

- **Cordware:** `APP_ENV`, `ALLOW_FAKE_AUTH`, `FAKE_AUTH_EMAIL`, `FAKE_AUTH_NAME`, `FAKE_AUTH_PRINCIPAL_ID`, `FAKE_AUTH_SUPER_ADMIN`, `SUPER_ADMIN_EMAILS`, `LOG_LEVEL`.
- **RRW:** `APP_VERSION` (the version RRW's pages display), `FAKE_AUTH_OPERATOR`, `FAKE_AUTH_SYS_ADMIN`, `OPERATOR_EMAILS`, `SYS_ADMIN_EMAILS`, `DATABASE_URL`, `REHYDRATE_ENABLED`, `AUDIT_STRICT_MODE`, `SMTP_ENCRYPTION_KEY`, `SCHEDULED_OPERATIONAL_LEAD_HOURS`, `REVIEWER_NOTICE_MIN_HOURS`, `PARTICIPANT_TOKEN_SALT`, `OPERATOR_CONTACT_EMAIL`, and the test and tool switches (`TEST_DATABASE_URL`, `RRW_REQUIRE_BROWSER`, `RRW_PARITY_DUMP`, `RRW_VALIDATION_PARITY_DUMP`, `RRW_NODE_ROOT`).

RRW's identity diagnostics, `/auth/me` and `/auth/me/debug`, keep working (at `/reviewrobin/auth/…` after the prefix flip) and show Cordware's identity, including whether it is the fake user.

### Host logging

Cordware writes **operational logs only**, as JSON lines on stdout, using the formatter RRW already has. App Service collects them, and Azure Monitor (the existing Log Analytics workspace and Application Insights) stores and queries them. Reading them is controlled by Azure RBAC on those resources. So host logging needs **no Cordware tables, users, admin interface or log viewer**. Locally the same lines print to the terminal.

Cordware logs only what no application can see:

1. process start and stop, which applications `CORDWARE_APPS` mounted, any mounted application's startup validation failure, and a warning when `SUPER_ADMIN_EMAILS` is empty in a deployed environment;
2. fake auth being enabled (a warning on every start) and every refusal by its guard;
3. identity problems: missing or malformed Easy Auth headers (the fact, never the header contents). A well-formed but forged header is indistinguishable from Easy Auth's to the host, so Cordware does not claim to detect requests that bypass the protected ingress. The network path rules that out (the Web App has `publicNetworkAccess = Disabled` and is reached only through Application Gateway and Easy Auth), and watching for a bypass belongs to infrastructure monitoring in Azure, not to host logging;
4. requests no mounted application handled, the live counterpart of stage 1's leak check;
5. errors outside any mounted application, and failing `/health` checks.

Cordware does **not** log sign-ins (Entra's sign-in logs cover them), duplicate request access logs (App Service, Application Gateway and Application Insights already record requests), or anything an application logs about its own work. It does stamp every log record and telemetry item with the application that produced it (`reviewrobin`, `residentialapps` or the host), so the shared workspace can be read per application.

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

Make small, reviewable changes. **Nothing is deployed to the NUS host until this repository runs as Cordware with RRW mounted at `/reviewrobin`**, so RRW is never deployed there on its own and the first NUS deploy uses the Cordware entry point.

| Stage | Work | Gate before the next stage |
|---|---|---|
| **0. Baseline and privacy** | Record RRW and Residential source SHAs, tests, migration heads, launch and deploy configuration. Make this repository **private before importing Residential's private material**, then check Actions, access and integrations after the change. | Known-good RRW baseline, provenance kept |
| **1. Host skeleton and URL sweep** | Two workstreams, each behavior-neutral while RRW stays at `/`. **Host skeleton (first):** add `cordware/main.py` and the `CORDWARE_APPS` setting, with Cordware alone serving `/health`; mount RRW **at `/`** for now; move the module-level app out of `app/main.py` and every start command to the Cordware entry point; move root-logger setup into Cordware; add the import-boundary test. The personal dev slot's start command switches to the Cordware entry point here. **URL sweep:** move every literal root path in templates, Python, inline scripts, path comparisons and cookies onto route-aware generation; add a test harness that mounts RRW under `/reviewrobin` and a leak-check test that becomes a hard gate once the sweep is done. | Cordware alone and Cordware + RRW both run; RRW behavior unchanged at `/`; no root-path leak under the test mount |
| **2. Shared identity, then the prefix flip** | **Shared identity** may start as soon as the host skeleton lands, in parallel with the sweep: move RRW's tested Easy Auth claims parsing into `cordware/identity.py`, with fake local identity and its guard, and the `SUPER_ADMIN_EMAILS` platform role; RRW consumes it through a re-export and keeps its fake roles, `users`, permissions and audits. No Cordware database. **Prefix flip (last, after the sweep):** mount RRW at `/reviewrobin`, serve the Cordware landing page at `/`, and fix the `/.auth/*` login and logout return paths. The personal dev slot then serves the assembled app, as the live check of §3's behavior requirements and the new identity under real Easy Auth. | Trusted-identity interface tested on its own; RRW permission behavior unchanged; RRW behavior unchanged at `/reviewrobin` |
| **3. Establish Residential** | Import its skeleton, architectural decisions, specs, plans, tests, tools, agent guidance and Alembic; re-namespace `app`; consume Cordware identity; mount at `/residentialapps`. Settle B or C **before production database setup**, not necessarily before the code import. | Cordware + Residential runs without RRW; both applications coexist |
| **4. Integrated release** | Resolve the one dependency environment; package the applications and assets; run each mounted application's migrations with its own database and credentials; verify in staging, then a controlled production cutover. | One validated build and release, with documented rollback and recovery |

The NUS deploy workflow currently packages `app/`, `alembic/`, `alembic.ini`, requirements, `pyproject.toml` and `antenv/`. Broaden the artifact only when the integrated application is ready. The **deployment workflow** runs each mounted application's migrations; Cordware does not become a migration service. Prefer backward-compatible migrations: reverting code does not reverse a database change.

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

**Implementation decisions still open:** the `DATABASE_URL` / `RRW_DATABASE_URL` precedence; confirming that the Web App's diagnostic settings route App Service console logs to the Log Analytics workspace; confirming that the personal dev slot sets `APP_ENV` to a non-`local` value before the guard lands; B versus C, and the database-role and recovery arrangements with NUS IT; dependency locking and the build artifact; CI required-check and release-gate policy; repository privacy and rename timing.

**Settled in stage 1 (segment 21A, 2026-10-21):**

- *The lifespan contract.* The host enters each mounted application's `router.lifespan_context` in mount order and exits in reverse; state a lifespan yields is merged and reaches `request.state` inside that application, and a repeated key refuses to start. Startup work may also stay in the factory. Contract: `cordware/spec/host.md`.
- *Path scoping for RRW's repo-wide tooling.* ruff and pytest take in `cordware/` (`cordware/tests` is in `testpaths`); RRW's doc-reference, doc-convention and spec-coverage gates stay RRW's, and `cordware/spec/` is checked by hand at each close. Per-owner CI jobs wait for a second application (§6).

**Settled in stage 1 (segment 21B, 2026-10-21):**

- *URL emission.* Routes keep their literal app-relative paths rather than adopting route names. A value, built in a template or in Python, stays app-relative until it is emitted; `app/web/urls.py` then adds `root_path` once: `url()` in templates, `redirect()` for responses, `cookie_path()` for cookies, `app_path()` and `here()` for comparisons. A string built outside a request is app-relative too, and gains the prefix where a template emits it. Two tests gate it: a static leak test, and a crawl of every GET route under a `/reviewrobin` test mount. Contract: `spec/architecture.md`.

**Settled in stage 2 (segment 21C, 2026-10-21):**

- *The trusted-identity interface.* `cordware/identity.py` is the one Easy Auth parser and the only source of the fake identity. Applications depend on `get_identity(request)`, which takes the request alone, and read host-level `fake_auth()`, `app_env()` / `is_local()`, `is_super_admin_email()`, `super_admin_configured()` and `super_admin_emails()`. The identity's `is_super_admin` and `super_admin_configured` are computed, never stored. The settings live in `cordware/settings.py` under their old names. The host refuses fake auth outside `APP_ENV=local` before mounting anything. RRW re-exports the interface from `app/auth/identity.py` and keeps its fake operator and admin roles, keyed off `is_fake`. Contract: `cordware/spec/identity.md`.

**Settled in stage 2 (segment 21D, 2026-10-22):**

- *The prefix flip.* RRW is mounted at `/reviewrobin`, a constant in `cordware/main.py`'s `REGISTRY`. `/reviewrobin` redirects to `/reviewrobin/`, and the old root paths answer the host's 404. `/health` is the host's probe and `/reviewrobin/health` RRW's; both are excluded from Easy Auth. Easy Auth's `/.auth/*` stays at the host level. Tests under the mount pin §3's behavior requirements; the author checked them on localhost, and the real-Easy-Auth check runs when the dev slot resumes. Contracts: `cordware/spec/host.md`, `spec/architecture.md`.
- *The public host for absolute links.* An invitation link takes the request's own scheme, host and `root_path`; there is no `PUBLIC_BASE_URL`. Checking that the gateway forwards the public host is stage 4's.
- *Browser tests under the mount.* The browser suite drives the real mount, with every navigation and URL assertion written through one `app_url(path)` helper; a static guard refuses a root path.

**Non-goals:** moving RRW's source into a `reviewrobin/` folder; cross-repository source sync or private package composition; plugin discovery; a supported standalone RRW runtime; Cordware user or role tables, or any Cordware persistence; a Cordware application, admin interface, console, dashboard or log viewer (the platform super-admin works inside the applications); a login audit table; shared business tables; a second PostgreSQL server without a new requirement; redirects for old root paths; a big-bang rewrite.

## 9. Decision history

| Version | Approach | Status |
|---|---|---|
| v0.4 | Separate canonical RRW and Residential repositories; code synced into Cordware for deployment | Archived |
| v0.5 | Separate installable, pinned application packages composed by Cordware | Archived; a retrospective reconstruction, never adopted |
| v0.6 | One canonical Cordware monorepo with symmetrical subprojects | Archived; refined into v0.7 |
| v0.7 | Evolve RRW in place; minimal Cordware identity and hosting shell; independent Residential development; B/C PostgreSQL shortlist | Archived; adopted 2026-10-19, superseded by v0.8 |
| **v0.8** | v0.7, with its addenda folded in and the independence requirement replacing standalone compatibility | **Current** |

All earlier versions, `cordware_repo_planning.md` and integration spec v0.2 are in `docs/archive/`. They are decision history, not implementation instructions.

**Changed in v0.8** (author, 2026-10-19 to 2026-10-21):

- **Standalone compatibility replaced by independence (§3).** v0.7 required RRW to "work both standalone locally and mounted". v0.8 requires that Cordware plus any single application runs, with the mounted set named by `CORDWARE_APPS` and Cordware runnable alone. Packages stay shared. There is no supported standalone RRW runtime, so RRW keeps no second identity parser.
- **v0.7 Addendum A folded into §3** as "Behavior under the mount": deep links, auth-free probes, mounted request handling, no backend-host leak.
- **v0.7 Addendum B folded into §3 and §5:** the mount replaces the `BASE_PATH` shim; each application is constructed once, with host-owned logging and the module-level app removed; NUS sees only the assembled application; the dev slot switches to the Cordware entry point; old root links are not kept.
- **Gateway path forwarding stated (§3):** the mount needs Application Gateway to forward the public path unchanged; v0.7 had called keep-or-strip irrelevant.
- **The v8 status report marked superseded in part:** its source-control and deployment model (independent repos synced into `philoyhc/cordware`) conflicts with this strategy, and the report now says so.
- **Stages 1 and 2 resequenced (§5, same day):** v0.8 first put the whole mount, sweep included, in stage 1 and identity after it. Stage 1 is now the host skeleton (RRW still at `/`) and the URL sweep, both behavior-neutral. Stage 2 is shared identity, which may run alongside the sweep, then the prefix flip, which is the only step that changes URLs and comes last. The behavior requirements apply from the flip; the dev slot changes its start command in stage 1 and its served path in stage 2.
- **Fake auth, the platform super-admin and host logging settled (§1, §3; author, 2026-10-21):** Cordware builds the localhost account, Local Operator `<operator@example.edu>`, and marks it platform super-admin while fake auth is on. Super-admin is one platform role: Cordware reads `SUPER_ADMIN_EMAILS` (an App Service application setting, one or more emails) and exposes it on the identity, and each application grants it full rights inside itself; there is no Cordware console, and the list is edited in Azure. Cordware writes operational logs only, to stdout and Azure Monitor, so it needs no tables, users or viewer.
- **`APP_ENV`, the fake-auth guard and local testing switches (§3; author, 2026-10-21):** `APP_ENV` becomes a platform setting Cordware reads and exposes. Cordware refuses to start with fake auth on outside `APP_ENV=local`, turning a documented rule into an enforced one, so every deployed environment sets a non-`local` value. Every local testing switch keeps its name, default and override behavior, with one repository-root `.env` read by Cordware and every application; §3 lists which side owns each.
- **URL emission settled (§3, §8; segment 21B, 2026-10-21):** the sweep emits through prefix-adding helpers rather than route names, so routes and their tests keep their app-relative paths.
- **The prefix flip settled (§1, §8; segment 21D, 2026-10-22):** RRW serves at `/reviewrobin`; absolute links take the request's host, with no configured base; a lone application gets `/` as a redirect rather than a one-item list.
- **Consistency fixes:** identity extraction ahead of Residential is explained (§1); the landing page lists mounted applications (§1, §3); the stage 1 and stage 3 gates name the independence checks (§5); the status line records adoption, and the broken version-history pointer is fixed.
