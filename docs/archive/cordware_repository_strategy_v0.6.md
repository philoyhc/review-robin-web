# Cordware Repository and Deployment Strategy

**Version:** 0.6 draft  
**Date:** 17 October 2026  
**Status:** Proposed replacement for v0.4; architectural direction for review, not an implementation authorization  
**Architecture:** One canonical Cordware monorepo, internally bounded subprojects, one production Azure App Service.

**Supersedes as a proposal:** `cordware_repository_strategy_v0.4.md`. Retain v0.4 and the intervening planning notes as decision history, not as concurrent implementation instructions.

---

## 1. Decision and rationale

Cordware will be the **canonical source and development repository** for its constituent applications, not a deployment-only integration repository consuming synchronized copies or private Git packages.

The intended path is:

```text
Cordware monorepo (platform + Review Robin + Residential Apps)
    -> one integrated CI/build/release process
    -> one Azure App Service
```

This replaces v0.4's:

```text
independent canonical app repos
    -> synchronization into Cordware
    -> integration and deployment
```

The change is deliberately organizational as well as technical. RRW and Residential Apps are currently small in number, share an institutional production boundary, and are developed through a disciplined agent-assisted, specification-anchored practice. Separate upstream repositories would require recurring sync or package-release coordination without providing separately deployed production services.

**One repository does not mean one undifferentiated application.** Modules retain distinct packages, specifications, plans, tests, tools, domain authorization, persistence boundaries, and ownership rules.

This is a **modular monolith**: one process and deployment/release boundary, with deliberate internal separation. It is *not* independent runtime isolation. Changes to shared dependencies, process startup, resource usage, and production releases can affect all subprojects.

## 2. Scope and canonical ownership

The initial bounded subprojects are:

1. **Platform** — Cordware landing shell, shared authenticated-identity plumbing, module composition, platform configuration, logging, health, and common hosting concerns.
2. **Review Robin** — the existing RRW application, including domain services, UI, authorization, database models and migrations.
3. **Residential Apps** — the residential modular monolith containing Resident Support Log, RA Leave, and RA Events. Residential retains its own internal `core` and its established `core`, `support`, `leave`, and `events` Postgres schema design.

Cordware owns production assembly, deployment, cross-project integration, and final release decisions. Each subproject owns its domain behavior and development lifecycle **within** the monorepo.

The original `philoyhc/review-robin-web` and `philoyhc/nuscr-res-apps` repositories remain available during transition. After a verified cutover they can be archived as historical records; they must not continue as competing canonical source trees. Repository renaming is unnecessary.

## 3. Development-unit boundaries and directory layout

The **subproject directory**, not merely the Python package, is the primary unit for an agent or contributor. Each subproject owns its code, `spec/`, `docs/`, `guide/`, `tests/`, `tools/`, local instructions and rationale.

Target layout (illustrative; physical code-package names may be finalized during the packaging proof):

```text
cordware/
├── platform/
│   ├── cordware/                 # importable platform Python package
│   │   ├── main.py               # assembled application factory
│   │   ├── identity.py
│   │   ├── config.py
│   │   ├── modules.py
│   │   ├── logging.py
│   │   ├── health.py
│   │   ├── templates/
│   │   └── static/
│   ├── spec/
│   ├── docs/
│   ├── guide/
│   ├── tests/
│   ├── tools/
│   ├── AGENTS.md
│   └── README.md
├── reviewrobin/
│   ├── reviewrobin/              # importable RRW package (formerly app/)
│   │   ├── routes/
│   │   ├── services/
│   │   ├── models/
│   │   ├── auth/
│   │   ├── templates/
│   │   └── static/
│   ├── alembic/
│   ├── spec/
│   │   ├── README.md
│   │   └── archive/
│   ├── docs/
│   │   ├── README.md
│   │   └── archive/
│   ├── guide/
│   │   ├── README.md
│   │   ├── segment_plan_template.md
│   │   ├── deferred_consolidated.md
│   │   └── archive/
│   ├── tests/
│   ├── tools/
│   ├── constitution.md
│   ├── AGENTS.md
│   └── README.md
├── residential/
│   ├── residentialapps/          # importable residential package (formerly app/)
│   │   ├── core/
│   │   ├── support/
│   │   ├── leave/
│   │   └── events/
│   ├── alembic/
│   ├── spec/
│   ├── docs/
│   ├── guide/
│   ├── tests/
│   ├── tools/
│   ├── constitution.md
│   ├── AGENTS.md
│   └── README.md
├── integration-tests/            # tests crossing project boundaries
├── deployment/                   # packaging, migrations, startup, rollback procedures
├── docs/                         # repository-wide architecture, decisions, operations
├── guide/                        # whole-platform transition / integration plans only
├── .github/workflows/
├── .claude/                       # optional shared agents/skills
├── pyproject.toml                 # assembled environment / tooling
├── uv.lock                        # or another chosen checked-in lockfile
├── constitution.md                # monorepo-wide invariants
├── AGENTS.md                      # routing instructions for agents
└── README.md
```

Do **not** create a fourth full-fledged `integration/` subproject by default. Put shared contracts in `platform/spec/`, cross-module tests in `integration-tests/`, operational docs in root `docs/`, and whole-platform change plans in root `guide/`. Reconsider only if integration work develops an independently substantial body of plans, tests and tools.

The structure is an **end state**, not a requirement to move and refactor everything in one PR. The established RRW and Residential folder trees should initially be imported as intact as practical and reorganized in controlled slices.

## 4. Three-layer documentation authority (each subproject)

The discipline recorded in `docs/rrw_sdd_in_practice.md` is preserved as a first-class architectural requirement.

| Folder | Question | Authority |
|---|---|---|
| `spec/` | What is the subsystem supposed to look like and do? | Settled behavioral contract |
| `docs/` | How does it work today; why was it designed that way; how is it operated? | Reference, rationale, human-facing documentation and dated status |
| `guide/` | What is being changed next and how? | Active segment plans, work decisions, findings, deferred work and archived build record |

These folders exist inside `platform/`, `reviewrobin/`, and `residential/`. Each has its own README/index and archive convention as appropriate. Do not merge their contents into a global documentation corpus merely because the Git repository is shared.

**Phase rule:** plan on the way in; spec on the way out. While a segment is open, its `guide/` plan records intended changes and amendments, while `spec/` remains the last settled contract. At segment/item closure, reconcile the agreed shipped behavior into `spec/`, update affected `docs/`, check the declared documentation impact, and archive or compact the plan as established practice requires. Outside an active change, a discrepancy between code and spec is reported for decision; do not silently rewrite the spec to match code.

Preserve other useful RRW practices: bounded segment plans; measured blast radius; explicit judgment calls and rejected alternatives; defined PR ladder and done criteria; documentation impact at planning time; separate maker and checker where appropriate; human verification for visual/behavioral outcomes that automated tests cannot establish; findings/deferred registers; and periodic spec/documentation sweeps.

An archive records historical reasoning; it is not a live contract. Avoid blindly copying RRW's volume of documentation to new subprojects—preserve the distinctions and mechanisms, not unnecessary duplication.

## 5. Local ownership and cross-project changes

- RRW feature work normally lives within `reviewrobin/`, including its plan, code, tests, specs and docs.
- Residential feature work normally lives within `residential/`; Support, Leave and Events remain domains inside one residential subproject, not three top-level Cordware projects.
- Shared authentication, common host behavior, route composition, cross-module logging and platform health belong to `platform/`.
- Cross-project contract changes explicitly name affected subprojects, documents and tests. A PR may span boundaries where necessary, but the blast radius must be reviewed deliberately.
- Neither RRW nor Residential imports the other's internals. Shared code enters platform only if it is truly host-level infrastructure, not a convenient dumping ground for domain services.
- A document lives at the lowest level owning its subject. Do not maintain duplicate supposedly authoritative interface specifications.

Place instructions in root `AGENTS.md` to route work to the correct subproject; use nested `AGENTS.md` for context, commands, local constraints and document indexes. Module-specific agent tooling may remain local, while genuinely reusable skills can reside under `.claude/`.

## 6. Python namespace and assembly

Both existing source projects use a top-level Python package named `app` (their package discovery includes `app*`). Those packages cannot coexist safely in one assembled Python import namespace as-is.

Target distinctive import names: `cordware`, `reviewrobin`, `residentialapps`. This is **not** a rename of the GitHub repositories. The import refactor must cover absolute imports, tests, Alembic environments, scripts, packaging, templates/resources and local launch commands.

Prefer **mounting complete ASGI sub-applications** over merging routers for RRW, because RRW already has application-level error handlers, middleware/static behavior and a factory. Conceptually:

```python
app.mount("/reviewrobin", create_rrw_app())
app.mount("/residentialapps", create_residential_app())
```

This is illustrative, not drop-in code. The chosen integration contract must define constructors, identity consumption, config namespace, health, and startup/shutdown handling. Mounted app lifespan events do not automatically run under the parent; Cordware must explicitly manage any required lifecycle work. Process-level logger configuration belongs to platform, not repeated module factories.

Preserve direct navigation and deep links under `/reviewrobin` and `/residentialapps`. Audit hard-coded root paths, redirects, JavaScript requests, form actions, static URLs, cookie paths, auth return links and URL generation; mounting alone does not correct all of these.

RRW should continue to have a standalone **local** harness where practical. Independent production deployment capability is a useful future extraction option, not a constraint that should force duplicate operational infrastructure now.

## 7. Authentication, authorization and security

Cordware has one institutional Microsoft Entra / Azure Easy Auth boundary and exposes a narrow **trusted identity** interface to each module. A user authenticated to Cordware is *not* thereby authorized to use either module.

- Platform parses/validates trusted identity at the outer boundary; only trusted Easy Auth ingress can supply identity headers.
- RRW keeps operator/admin/super-admin authorization semantics.
- Residential keeps its own RA/staff/admin and support-record access rules.
- Local fake identity is platform-controlled and categorically disallowed in deployed environments. Domain-specific fake *roles* may remain module-owned for tests.
- The landing page is for discovery, **never** an authorization boundary. The initial shell may expose all module tiles; access checks still occur inside modules.
- Distinct module settings namespaces prevent clashes (e.g., `RRW_DATABASE_URL`, `RES_DATABASE_URL`).
- Keep RRW and Residential persistence boundaries separate. Residential retains separate `core`, `support`, `leave`, `events` schemas and intended least-privilege roles, with Support isolated sufficiently to be extractable later.

**Security limitation:** one shared application process is not a strong security boundary. A process compromise, dependency vulnerability, or unsafe shared credential access can affect multiple modules. Database roles reduce impact but do not create full runtime isolation; this accepted risk must be documented and revisited if Support's sensitivity or institutional requirements change. Secrets belong in approved runtime secret storage, not repository files.

## 8. Dependencies, tests, and developer tooling

One process uses one resolved Python environment. Cordware owns the central dependency declaration/lockfile, while module-specific dependency expectations and commands can remain documented locally. Keep a pinned, reproducible production build.

Each subproject owns `tests/` and `tools/`. RRW's existing tools (close checks, sweeps, metrics, browser checks, etc.) should move with it and be preserved before being generalized. Some currently assume the repository root, path prefixes, or full-repo merge counts; adapt such scripts to a project-root argument or a path-scoped Git history/baseline. Do not silently substitute whole-Cordware activity for RRW-specific historical metrics.

CI may selectively run relevant subproject tests during development, but shared-platform changes and production release candidates must run appropriate integration and complete build/package checks. At minimum cover:
- package/import collision and dependency resolution;
- mounted routes, assets, deep links and redirects;
- identity, authorization boundaries and local-fake-auth guards;
- configuration isolation;
- database migrations against appropriate Postgres environments;
- one module's startup failure and platform health behavior;
- production artifact contents and startup command.

A monorepo does not remove the maker/checker separation or the human approval point for consequential UI or deployment changes.

## 9. Database migration and release operation

Each domain owns its Alembic migration history in its subproject. Cordware orchestrates migration execution with correctly scoped credentials and a fixed, documented order. RRW and Residential must not accidentally share an Alembic version table or migration namespace.

Production releases are **one unit**: build and test the complete assembled app, run pre-deploy checks, apply approved compatible migrations, deploy, and verify. A failure in a module's critical startup configuration should initially fail the release, rather than silently hide a broken module.

Database rollback is not the same as reverting the Git commit. Prefer backward-compatible expand/contract migrations and separately tested rollback/restore plans. Do not promise that `alembic downgrade` is safe for arbitrary production rollback.

Retain separate least-privilege runtime and migration database identities where feasible. Cordware's deploy workflow and Azure deployment identity become the sole production deployment authority after cutover.

## 10. Migration from the two source repositories

**No big-bang refactor.** Move RRW first, establish a verified functional baseline, then restructure for composition, then incorporate Residential before substantial residential feature growth.

1. **Freeze and record baselines.** Record reviewed RRW and Residential commit SHAs, live deployment details, current CI gates, migration heads, applicable planning decisions and tests. Keep both original repos usable during transition.
2. **Import RRW with its complete development context.** Move source, Alembic chain, `spec/`, `docs/`, `guide/` including archives, tests, tools, constitution, AGENTS/CLAUDE guidance and design rationale. Prefer an initial snapshot import with provenance (old repo URL and commit SHA) and read-only archived repo later; full rewritten-history import is optional if commit-by-commit continuity is judged worth its complexity.
3. **Establish a passing RRW baseline in Cordware.** Make its existing tests and local launch work before sweeping import paths or changing host routing. Keep the current RRW deployment path available.
4. **Introduce distinct Python package names and platform shell.** Do this as tested, reviewable slices. Prove mounted RRW paths, deep links, identity behavior, static assets, logging and lifecycle.
5. **Import Residential's existing skeleton and documentary/practice context.** Include its current schema strategy, Alembic chain, tests and tools, then give it a distinct import namespace and adapt it to the host contract. Do not discard decisions merely because its business-feature implementation is still early.
6. **Build the integrated app and staging release.** Establish centralized dependencies, complete artifact, migration orchestration, integration checks and a non-production verification target.
7. **Cut over production ownership.** After tests and staged verification, obtain/activate any required Cordware GitHub OIDC federation and Azure role assignment, deploy from Cordware, verify real direct/deep-link behavior, then retire RRW's production deploy workflow. Preserve an agreed rollback path.
8. **Archive source repositories only after validation.** Preserve their issues, PRs and history. Mark Cordware as canonical; avoid dual-write development.

A minimal intermediate state in which RRW runs unchanged or at its old root is acceptable as a **migration checkpoint**, not the final Cordware route contract. Avoid combining source transfer, Python rename, new auth, route rewrite, migration overhaul and deploy identity swap in one PR.

## 11. Deployment and GitHub organization

- The `cordware` repository is authoritative for all production source, platform/integration CI, release artifacts, and deployment workflow.
- One Git commit identifies the entire application source revision; an explicit dependency lock and immutable build artifact complete reproducibility.
- Source-specific pull requests can stay scoped to local directories, but every merged revision still affects a common `main`.
- Central GitHub workflows can dispatch local checks by changed paths while enforcing broader gates for platform changes and release.
- Root guidance and nested project guidance should agree on scope, test commands, document authority, review expectations and cross-project changes.
- Azure configuration and credentials are never copied into documentation verbatim where avoidable; live secrets remain outside Git. Historical infrastructure reports may need ownership consolidation/redaction.

## 12. Deliberate non-goals

The initial migration does **not** require:
- a generalized plugin marketplace or dynamic discovery/loader;
- synchronization PR bots, Git submodules, private Git package fetching or a module SHA manifest;
- merging RRW and Residential databases;
- centralizing domain authorization;
- unifying the three residential domain schemas;
- migrating unrelated business logic to platform;
- rewriting RRW's established development practice or discarding its archives;
- implementing Residential business features before the platform integration is sound.

## 13. Acceptance criteria for v0.6 implementation

The direction is realized when:

1. Cordware is the only canonical repository receiving new RRW and Residential source changes.
2. Each subproject retains independently navigable `spec/`, `docs/`, `guide/`, `tests/`, `tools/` and local agent instructions.
3. Established RRW contract/segment/close-check practices still function with monorepo-aware paths and history.
4. RRW's existing behavior and authorization remain intact, apart from approved hosting-boundary changes.
5. The Residential architectural contracts and migration history survive the import.
6. Both packages coexist without top-level `app` namespace collision.
7. The platform serves direct and deep links at `/reviewrobin` and `/residentialapps`, including correct assets and authentication returns.
8. One verified release artifact runs both modules under the approved single App Service.
9. Separate data and authorization boundaries remain testable.
10. Only Cordware has active production deployment authority after cutover.
11. Source-repo provenance, archived development records and rollback instructions are available.

## 14. Open decisions before implementation

The following are decisions to settle in short planning segments, not reasons to revert to a three-repository architecture:

1. Precise on-disk package roots and packaging method (single root `pyproject.toml` vs workspaces/editable subproject packages).
2. Extent of Git-history import versus snapshot-and-archive.
3. How to adapt RRW's Git-history-dependent tooling and what migration baseline to record.
4. Whether Cordware uses `uv.lock` or another existing dependency-lock convention.
5. Explicit mounted-app lifecycle contract, trusted identity propagation and readiness/failure policy.
6. Staging target, migration ordering, compatibility checks and production rollback mechanics.
7. Rules for selective CI versus full release-gate CI.
8. Ownership of platform-wide documents that currently exist in multiple repositories.

**Recommended order:** prove code/package integration, retain the existing development practice, verify the complete deployment, then cut over production. Documentation and repository layout should support the development method, not dictate business-domain coupling.
