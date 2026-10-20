# Cordware Repository and Deployment Strategy

**Version:** 0.7 draft — editorial consolidation, 18 October 2026  
**Status:** Proposed architecture, not authorization for implementation or production changes  
**Canonical source repository (proposed):** `philoyhc/review-robin-web`; optional rename later  
**Deployment:** One integrated application on one Azure App Service

> **Decision:** Evolve RRW's existing repository **in place** into an asymmetric monorepo. Keep its established root-level source and development folders. Introduce a deliberately small `cordware/` shell for trusted Entra identity and application hosting, then a self-contained `residentialapps/` development area. The sequence is **mount RRW at `/reviewrobin` → extract shared identity → establish Residential Apps → integrate and deploy**.

This replaces earlier multi-repository or symmetrical-monorepo proposals. See `9 for the version history.

---

## 1. Architectural ownership

Cordware is a **stateless authentication/hosting shell**, not a shared business platform.

| Concern | Cordware | RRW | Residential Apps |
|---|---|---|---|
| Authentication | Consume identity authenticated by Entra / Azure Easy Auth; expose trusted claims | Consume identity | Consume identity |
| Users and roles | **None stored** | Own local users, operator/admin/participant permissions | Own RA/staff/admin users and permissions |
| Authorization | No app-level permissions or access decisions | Own | Own |
| Auditing | No business or login audit table | Audit business/account-state actions | Audit business actions |
| Data and migrations | **No database or Alembic** | Own | Own |
| UI | Landing links, minimal host health | RRW application | Support Log, RA Leave, RA Events |

Cordware's foreseeable functions are limited to trusted identity resolution, sub-application mounting, a simple landing page, and minimal process configuration, lifecycle, health and logging. Its homepage need not know which applications someone is entitled to use; each application gates its own routes. A Cordware database or generic authorization framework is **not planned**.

**RRW is the senior tenant and the starting source of reusable infrastructure, not the permanent owner of shared authentication.** Extract shared code only when there is an actual second consumer. Neither business application may import the other's domain services or models.

## 2. Repository layout and development practice

The existing RRW files remain substantially at repository root:

```text
review-robin-web/                    # GitHub rename to cordware is optional
├── app/                             # Existing RRW Python package, imports app.*
├── spec/  docs/  guide/            # Existing RRW contract / reference / plans
├── tests/  tools/                   # Existing RRW verification
├── alembic/  alembic.ini           # RRW migrations
│
├── cordware/                        # New stateless host/platform package
│   ├── main.py                     # Assembled FastAPI entrypoint
│   ├── identity.py                 # Trusted institutional principal
│   ├── web/                        # Optional landing template/assets
│   ├── spec/  docs/  guide/
│   ├── tests/  tools/
│   └── AGENTS.md
│
├── residentialapps/                 # New bounded domain development space
│   ├── app/                         # Imports residentialapps.app.*
│   │   ├── core/                    # Residential-specific shared services
│   │   ├── support/                 # Resident Support Log
│   │   ├── leave/                   # RA Leave
│   │   ├── events/                  # RA Events
│   │   └── web/
│   ├── alembic/  alembic.ini
│   ├── spec/  docs/  guide/
│   ├── tests/  tools/
│   ├── constitution.md
│   └── AGENTS.md
│
├── deployment/                      # Release packaging and migration workflow
├── .github/workflows/  .claude/
├── pyproject.toml                   # Integrated package discovery/dependencies
├── constitution.md  AGENTS.md  README.md
└── requirements.txt                # Existing setup retained initially
```

Only create host files when needed; **do not** add a Cordware ORM, user registry, database migrations or audit store. RRW's `app` remains the sole top-level package named `app`. Residential's current upstream `app` package must be re-namespaced during import, including its imports, tests, Alembic scripts and packaging configuration.

**Separate development ownership** is retained even within one repo:

| Owner | Settled behavioral contract | How it works / rationale | Active plans and decisions | Verification |
|---|---|---|---|---|
| RRW | `spec/` | `docs/` | `guide/` | `tests/`, `tools/` |
| Platform | `cordware/spec/` | `cordware/docs/` | `cordware/guide/` | `cordware/tests/`, `cordware/tools/` |
| Residential | `residentialapps/spec/` | `residentialapps/docs/` | `residentialapps/guide/` | `residentialapps/tests/`, `residentialapps/tools/` |

Preserve RRW's practice documented in `rrw_sdd_in_practice.md`: **plan on the way in; spec on the way out**. An active segment plan records planned changes, decisions, blast radius, PR ladder and documentation impact; on closure, reconcile approved behavior into `spec/`, update reference docs and archive the plan. Outside an active segment, report code/spec discrepancies rather than silently altering the contract. Retain maker/checker separation, close checks and human browser verification where appropriate. Archives record history, not live requirements.

Root `AGENTS.md` should route work to the correct subproject; each nested `AGENTS.md` provides local instructions. Existing RRW tools/history-based metrics that currently assume the entire repo belongs to RRW will need path scoping once new projects arrive.

## 3. URL composition and trusted identity

### Mounting RRW without moving its files

A minimal host mounts RRW's existing application factory, later adding Residential:

```python
# cordware/main.py — conceptual; not production-ready
from fastapi import FastAPI
from app.main import create_app as create_rrw

def create_app() -> FastAPI:
    host = FastAPI(title="Cordware")
    # Host landing and health endpoints
    host.mount("/reviewrobin", create_rrw())
    # Later: host.mount("/residentialapps", create_residential())
    return host
```

| RRW standalone URL | Cordware public URL |
|---|---|
| `/` | `/reviewrobin/` |
| `/operator` | `/reviewrobin/operator` |
| `/operator/sessions` | `/reviewrobin/operator/sessions` |
| `/me` | `/reviewrobin/me` |
| `/static/...` | `/reviewrobin/static/...` |

Cordware owns `/` (simple application links) and `/health` (host health). Deep links into either app remain directly usable.

**Mounting is not automatic URL rewriting.** RRW currently contains literal absolute redirects such as `/operator/sessions` and `/me`. Audit redirects, generated links/emails, templates, forms, JS/fetch paths, static URLs, cookies and auth return links; prefer route-aware URL generation over hard-coded prefixes. Easy Auth's `/.auth/*` paths remain host-level.

RRW's existing `app/main.py` also creates a module-level `app = create_app()`, and its factory configures logging and validates settings. Avoid double app construction/process initialization when importing the factory. Mounted sub-app lifespans do not automatically execute under the parent; explicitly manage required startup/shutdown.

**Compatibility requirement:** RRW must continue to work both standalone locally and mounted under `/reviewrobin`, without intended changes to its business behavior.

### Shared identity, application-specific permissions

Microsoft Entra / Azure Easy Auth performs institutional sign-in. Cordware interprets **trusted** claims at the protected ingress, exposing a small request-level identity (principal/object ID where available, email/UPN, display name, provider). It must not trust spoofable external identity headers, and fake-local identity must be disabled in deployed environments.

RRW maps that identity to its own existing user and permission records. Residential performs its own mapping. Neither application receives its authorization decisions from Cordware.

Extract RRW's tested Entra identity-resolution logic **after** the mounted URL behavior is established. Retain a standalone RRW local adapter if needed. Additional shared infrastructure must be justified by real cross-application needs.

## 4. Audit and persistence

### Audit only meaningful application actions

The established RRW choice is **not to write audit records merely for login**. Authentication records belong to Entra / Easy Auth. Application visits are not necessarily new sign-ins.

RRW's existing `audit_events` table is tied by foreign keys to RRW `users` and `sessions`. It records business actions and certain local account-state changes (such as recorded principal IDs or email reconciliation). First-time user creation is not currently a separate login audit event. These records stay with RRW.

The RRW `users` table also stays put: although it includes Entra principal ID, email and name, it contains RRW roles, SMTP information, preferences and relational links. Extracting **identity-processing code** does not require relocating **identity-related database rows**.

Residential similarly owns its business-action audit. Cordware should use ordinary host diagnostics/telemetry where warranted, **not** a persistent cross-app audit or users table.

### Production PostgreSQL decision: B or C

The shortlist is **B or C on the existing institutional PostgreSQL server**. **C is preferred**, subject to NUS IT feasibility, cost and operational constraints.

| | **B: one database, separate schemas** | **C: two databases, same server (preferred)** |
|---|---|---|
| Structure | Existing RRW tables plus Residential's `core`, `support`, `leave`, `events` schemas in one database | Existing RRW database plus a distinct Residential database containing those four schemas |
| Incremental base cost | Normally minimal | Normally no second compute/server charge merely for another DB; increased workload/storage can cost more |
| Access boundary | Schema-specific roles and grants | Database-specific access plus schema roles and grants |
| Migration boundary | Separate Alembic histories **and distinct version-table locations** | Separate Alembic histories in separate databases |
| Cross-domain SQL | Technically possible; discouraged | Ordinary cross-database foreign keys/joins not available |
| Isolation | Moderate logical separation | Stronger administrative and logical separation |
| Server compute, availability and standard Azure point-in-time recovery | Shared | Shared |
| Development CI | Independent | Independent |

**Option B** requires disciplined schema qualification, search-path/grant management, migration scope and independently located Alembic version tables to protect RRW's existing objects. **Option C** is cleaner for credentials and migration isolation, but is still **one** shared server with common capacity and server-level restore; logical backups can address database-specific recovery needs under either option.

**Choose C** if NUS IT can create a second database and roles on the existing server without disproportionate obstacles or material extra cost; otherwise **B** is an acceptable fallback. Do not pursue shared business tables (A) or a second PostgreSQL server (D) absent a new requirement.

Use namespaced settings, for example `RRW_DATABASE_URL` and `RES_DATABASE_URL`. Under B these can address the same DB with distinct restricted credentials; under C they address two databases on one server. Keep RRW's existing `DATABASE_URL` working in standalone mode with documented, nonambiguous precedence.

**Cordware needs no third database under either B or C.**

## 5. Implementation pathway and stage gates

Make small, reviewable changes. Keep current RRW development and deployment working until the integrated target is verified.

| Stage | Work | Gate before proceeding |
|---|---|---|
| **0. Baseline and privacy** | Record RRW/Residential source SHAs, tests, migration heads, launch/deploy configuration. Make the expanded RRW repo **private before importing Residential's private materials**. Verify Actions, access and integrations after visibility change. | Known-good RRW baseline and provenance preserved |
| **1. Prefix-host RRW** | Add minimal `cordware/main.py`; mount at `/reviewrobin`; repair root-relative URLs; handle app factory/lifespan; test standalone and mounted routes, redirects, static assets, deep links and authorization. | RRW behavior unchanged; both launch modes pass |
| **2. Extract shared identity** | Move/wrap tested Entra/Easy Auth claims parsing into `cordware/identity.py`; connect mounted RRW; keep its existing `users`, roles and audits. No Cordware database. | Trusted identity interface independently tested; RRW permission behavior preserved |
| **3. Establish Residential** | Import skeleton, architectural decisions, specs, plans, tests, tools, agent guidance and Alembic; re-namespace `app`; consume Cordware identity; mount `/residentialapps`. Settle B/C **before production DB setup**, not necessarily before code import. | Both applications coexist; Residential can be developed and tested independently |
| **4. Integrated release** | Resolve one dependency environment; package both apps and assets; run migrations with correct DB/schema and credentials; verify full app in staging, then controlled production cutover. | One validated build/release with documented rollback and recovery |

RRW's existing deployment workflow currently packages `app/`, `alembic/`, `alembic.ini`, requirements and `antenv/`; broaden the artifact only when the integrated application is ready. The **deployment workflow** coordinates each application's migrations—Cordware does not acquire a database/migration service. Prefer backward-compatible migrations: reverting code does not automatically reverse database changes. A critical module failure should fail startup/deployment unless a deliberately engineered degraded mode is approved.

## 6. Scoped CI and shared-runtime risks

One repository and one production deployment **do not require full RRW database tests on every Residential PR**. Keep app-specific CI jobs and disposable Postgres fixtures; never run routine CI against production data.

| Changed area | Expected development checks |
|---|---|
| RRW only | Relevant RRW tests and migrations where applicable |
| Residential only | Residential tests and Alembic round trips against a **Residential-only disposable database** |
| Cordware identity/hosting | Platform unit tests, targeted mount/auth integration; usually **no PostgreSQL for platform unit tests** |
| Shared dependencies / packaging | Both-app compatibility and relevant integrated checks |
| Production release candidate | Full agreed regression, migration, auth, routing and artifact checks |

Residential's current `ci-postgres.yml` already provisions a separate disposable Postgres container and tests upgrade/downgrade plus pytest. Preserve that independence **whether production uses B or C**. Prefer job-level path detection over skipping required workflows, which can leave pull-request checks pending.

The production process still shares Python dependency resolution, startup, compute resources and the deployment release boundary. A shared-process compromise can potentially expose both DB credentials; schema/database permissions and app authorization mitigate, but do not create hard runtime isolation. Similarly, B and C both share Postgres server resource/failure and Azure server-level recovery domains.

## 7. Repository governance

- **Active source of truth:** evolve `philoyhc/review-robin-web`, preserving its Git/PR history and RRW development machinery. Avoid a parallel writable application source in `philoyhc/cordware`.
- **Repository privacy:** GitHub visibility applies to the whole repository, not individual directories. Make RRW private **before** importing Residential's private sources or documents. Agreement to do so is not confirmation it has been done.
- **Project transfer:** preserve Residential's provenance and archival planning material. Archive its original repository only after its content, workflows and migration history are verified in the canonical repo.
- **Existing Cordware planning documents:** move/reconcile pertinent v0.4–v0.7 and integration decisions into the evolved RRW repository with source references.
- **Optional repo rename:** postpone `review-robin-web` → `cordware` until stable operation. The existing `philoyhc/cordware` planning repo must first vacate that name. GitHub OIDC federation and other integrations may require updates.
- **Institutional deployment:** the existing NUS Azure OIDC subject was scoped to `repo:philoyhc/review-robin-web:ref:refs/heads/main`. Keeping that name during functional integration may reduce IT changes, but verify the live configuration before cutover.

## 8. Acceptance and open decisions

**Architecture is accepted when:** RRW's existing folders, history, tooling and standalone behavior survive; mounted `/reviewrobin/operator/...` and `/reviewrobin/me` routes and all critical links work; Cordware is stateless and supplies trusted identity, hosting and a simple landing page; both apps independently enforce permissions, own action audits, data and migrations; Residential has its own `spec/docs/guide/tests/tools` and scoped CI; B or C is implemented safely (C preferred); and the integrated artifact is staged, tested and deployed with a documented recovery path. <!-- path-ref-ok -->

**Implementation decisions still open:** exact app factory/lifespan contract; mount-aware URL approach; trusted-identity adapter; B versus C and DB-role/recovery arrangements with NUS IT; dependency locking/build artifact; CI required-check and release-gate policy; scopes for RRW's repo-wide tooling; repository privacy/rename timing.

**Non-goals:** relocating all RRW source into a `reviewrobin/` directory, cross-repo source synchronization/private package composition, generic plugin discovery, Cordware user/role tables or a persistence layer, a login audit table, shared business tables, a second PostgreSQL server without new requirements, and a big-bang rewrite.

## 9. Decision history

| Version | Approach | Status |
|---|---|---|
| `v0.4` | Separate canonical RRW/Residential repositories; synchronize code into Cordware for deployment | Reconsidered |
| `v0.5` | Separate installable/pinned app packages composed by Cordware | **Retrospective reconstruction**, not an adopted specification |
| `v0.6` | One canonical Cordware monorepo, symmetrical subprojects | Refined |
| **`v0.7`** | Evolve RRW in place; minimal Cordware identity/hosting shell; independent Residential development; B/C PostgreSQL shortlist | **Current proposal** |

Historical notes, including `cordware_repo_planning.md`, are decision history rather than concurrent implementation instructions. **Required sequence:** RRW URL prefix → shared identity → Residential development → integrated release.

## Addendum A — carried from integration spec v0.2 (2026-10-19)

Integration spec v0.2 (`docs/archive/cordware_rrw_integration_spec_v0.2.md`) is archived: §3–§5 and §8 above cover most of it, and its sync contract belongs to the v0.4 model. These four requirements appeared only there and still apply to stage 1:

1. **Deep links survive sign-in.** A signed-out user opening `/reviewrobin/sessions/123` goes through Easy Auth and returns to that full path, not to `/` or `/reviewrobin/` (v0.2 §3, §11).
2. **Probe paths need no interactive sign-in.** `/health` for the host, and an optional `/reviewrobin/health` for RRW (v0.2 §12).
3. **Mounted RRW keeps its own request handling.** Its error handlers, middleware order and app-wide dependencies behave as they do standalone (v0.2 §7).
4. **No backend hostname leaks.** Downloads and every absolute URL, invitation emails included, stay under `/reviewrobin` and never carry the App Service's `azurewebsites.net` name (v0.2 §10, §18 criterion 14).

## Addendum B — stage 1 decisions (author, 2026-10-19)

Three implementation decisions for stage 1 (mount RRW at `/reviewrobin`), settled ahead of the Segment 21 rework:

1. **The mount supplies the prefix.** `host.mount("/reviewrobin", …)` strips the prefix before RRW sees a request and sets `root_path`, so route-aware URLs (`url_for`, `request.url_for`) gain `/reviewrobin` without help. The `BASE_PATH` setting and ASGI shim proposed in `guide/segment_21_domain_retrofit.md` are dropped, and that outline's rejection of a fixed mount is reversed: it rested only on the gateway's keep-or-strip behavior, which Cordware now owns. The sweep of literal root paths in templates, Python, inline scripts and cookies is still required.
2. **RRW is constructed once, and the host owns logging.** The module-level `app = create_app()` moves out of `app/main.py` into a small entry module of its own, so importing the factory has no side effects. Standalone start commands and the docs that name them (`app.main:app` today) move to that entry module. Process-wide logging setup moves to the Cordware host, and RRW's factory stops configuring the root logger when it is mounted.
3. **Azure sees only the assembled app; old root links are not kept.** Nothing is deployed to the NUS host until this repository runs as Cordware with RRW mounted, so its first deploy uses the Cordware entry point and RRW is never deployed there standalone. The personal dev slot switches to the Cordware entry point when stage 1 lands, as the live check of Addendum A's deep-link and hostname requirements under real Easy Auth. No redirects from old root paths (`/operator/...`, `/me`) to `/reviewrobin/...`: nothing consequential links to them.
