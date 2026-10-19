# Cordware Repository and Deployment Strategy — v0.5 (Retrospective Reconstruction)

**Version:** 0.5 — retrospective discussion record  
**Recorded:** 18 October 2026  
**Original discussion:** Between v0.4 and v0.6  
**Status:** Explored but **not formally adopted or previously published as a versioned strategy**  
**Disposition:** Superseded by the single-canonical-repository direction in v0.6, then refined in v0.7.

> **Provenance note.** No file named `cordware_repository_strategy_v0.5.md` was present in `cordware/docs/` when this was recorded. This document reconstructs the **distinct architectural alternative considered in discussion** between the committed v0.4 and v0.6 files. It is not an original historical artifact and should not be mistaken for an approved specification or an exact transcript. The discussion itself ended by reopening the v0.4 synchronized-source option rather than settling on a package-based v0.5.

---

## 1. Context: the v0.4 baseline

v0.4 chose:

```text
review-robin-web (canonical) ─┐
                              ├──> automated source-copy PRs
nuscr-res-apps (canonical) ───┘          into cordware
                                             │
                                         integration CI
                                             │
                                     one Azure App Service
```

RRW and Residential Apps would retain their own source, tests, migrations, plans, and histories. Cordware would own the landing shell, shared identity, route composition, cross-module tests, selected source revisions, and the single production deployment.

The v0.4 example put synchronized source under `cordware/app/reviewrobin/` and `cordware/app/residentialapps/`.

The accompanying `cordware_repo_planning.md` identified the immediate problem: RRW uses a top-level Python package called `app` and absolute imports such as `from app.config import settings`. Placing this unchanged under `app/reviewrobin` would not give it a separate import namespace. Residential Apps likewise uses a top-level `app` package, as later confirmed by inspection. A literal copy of the proposed layout would therefore not work without resolving imports and package identity.

The planning notes also called out mounted ASGI apps versus merged routers, shared dependencies, configuration prefixes, independent Alembic chains, fake authentication, and production workflow ownership.

## 2. The v0.5 option examined: source repos plus pinned installable packages

The principal v0.5 candidate retained **three repositories and one production deployment**, but made Cordware a *release composition repository* rather than a repository holding copied application source.

```text
review-robin-web ──> versioned/installable Python package ─┐
                                                            ├──> Cordware CI
nuscr-res-apps ────> versioned/installable Python package ──┘       │
                                                               tested, locked
                                                               deploy artifact
                                                                    │
                                                            one App Service
```

Responsibilities:

- `review-robin-web`: canonical RRW business code, tests, migrations, authorization, domain docs, and development history.
- `nuscr-res-apps`: canonical Residential domain code, tests, migrations, authorization, domain docs, and development history.
- `cordware`: platform shell and identity, exact selected upstream package revisions, integration tests, consolidated runtime dependencies, migration orchestration, artifact build, and Azure deployment.

RRW and Residential Apps would be installed *into the Cordware build environment*, not synchronized as folders checked into the Cordware Git repository. An updated application revision would trigger a Cordware dependency-pin/lockfile PR rather than a large source-copy PR.

Crucially, the production artifact would still **contain and execute both applications' Python code**. Absence of application source from the Cordware *Git checkout* is not absence from the deployed environment.

## 3. Provisional repository shape

The candidate layout was intentionally small:

```text
cordware/
├── cordware/
│   ├── main.py                # assembled FastAPI app factory
│   ├── identity.py            # shared Easy Auth / Entra identity
│   ├── config.py
│   ├── modules.py             # mounted sub-app registration
│   ├── health.py
│   ├── templates/
│   └── static/
├── tests/
│   ├── test_shell.py
│   ├── test_identity.py
│   ├── test_mounts.py
│   └── integration/
├── deployment/
│   ├── startup.sh
│   ├── migrate.py
│   └── verify.py
├── docs/
├── .github/workflows/
├── pyproject.toml             # includes upstream package dependencies
├── uv.lock                    # suggested, not decided
├── AGENTS.md
└── README.md
```

A module manifest, if retained, would record module identity, import/package name, and public prefix; the lockfile would own exact dependency revisions. Two conflicting authorities for version selection were to be avoided.

The illustrative dependency approach was a source pinned by Git commit in `pyproject.toml` (or alternatively an internally published immutable package). A checked-in lockfile and built artifact would fix the production composition.

## 4. Sub-app mounting and module boundaries

**Mounted ASGI applications** were preferred for RRW and Residential Apps:

```python
from fastapi import FastAPI
from reviewrobin.main import create_app as create_rrw
from residentialapps.main import create_app as create_residential

host = FastAPI(title="Cordware")
host.mount("/reviewrobin", create_rrw())
host.mount("/residentialapps", create_residential())
```

Illustrative only. Distinct importable package names (`reviewrobin`, `residentialapps`, `cordware`) would be required. RRW's established `app` package would need a substantial import and packaging retrofit *inside its canonical source repo*.

Mounting preserves more module-level behavior than merging routers, but does **not** automatically correct hard-coded absolute redirects, links, fetch URLs, auth return links, cookies, or process-wide logging. Mounted sub-app lifespans would need explicit handling. RRW and Residential would keep domain authorization and database ownership; Cordware would provide trusted identity and host-level services.

The same single-process coupling remained: one Python dependency resolution, one release and startup boundary, and potentially shared resource/failure risks.

## 5. Build and deployment implications

The main operational change was an explicit **assemble-before-deploy** build:

1. Check out Cordware in GitHub Actions.
2. Resolve/install exact, approved RRW and Residential revisions (from private Git or a package store).
3. Include the packages' Python code, templates, static assets, and Alembic migration resources in the resulting deployable artifact.
4. Execute integrated tests and migration validation against appropriate databases.
5. Deploy the complete artifact to Azure App Service; production Azure should not need credentials to fetch private GitHub dependencies.

This differs from a workflow that simply deploys the Cordware source checkout and has Azure install its requirements on arrival. Private dependency access, platform-compatible wheels/virtual environments, data-file packaging, and Alembic paths all require careful design.

App-specific migrations would remain authored upstream, but Cordware would coordinate them. Failed critical migrations would block deployment; downgrading app code would not automatically reverse database migrations.

## 6. Assessment reached during discussion

**Benefits over v0.4 synchronized source:**

- No duplicated application code committed into the Cordware repository.
- No code-copy replacement mechanism or prohibition on hand-editing imported trees.
- Small, auditable module-version update PRs.
- A natural distinction between application development and release composition.
- Future independent deployment remained straightforward in principle.

**Costs and risks:**

- Private Git source/package retrieval and complete artifact packaging become part of release engineering.
- Application source diffs are not visible within the Cordware release PR; reviewers need upstream PRs or changelogs.
- Package names must be made distinct despite both existing projects using top-level `app`.
- Template/static/Alembic resources must be packaged explicitly.
- Coordinated dependency and migration compatibility remains necessary.
- With only two upstream application projects, the packaging/release layer risks being more machinery than the situation justifies.

The discussion did **not** conclusively endorse this design. When the implications for the existing Azure workflow were examined, the simpler v0.4-style source-copy arrangement was reconsidered as a serious candidate. In particular, copied source checked into Cordware made it easier to build a complete application from a single repository checkout, without a private package retrieval step.

Thus the precise record is: **the package-based alternative was developed as the main v0.5 proposal, and then its advantage over synchronized source was questioned. No final v0.5 implementation choice was made.**

## 7. Why v0.6 displaced the question

A further simplification was then proposed: stop treating RRW and Residential Apps as separate canonical source repositories. Put all application source and development work in one canonical Cordware monorepo, avoiding both source synchronization **and** private package dependency management.

That became the recorded v0.6 draft, with symmetrical `platform/`, `reviewrobin/`, and `residential/` subprojects. The subsequently recorded v0.7 draft refined it again: evolve the mature RRW repository in place, retain RRW's root `app/`, `spec/`, `docs/`, `guide/`, `tests/`, and `tools/`, first make RRW serve under `/reviewrobin`, then extract shared Entra identity into `cordware/`, and only then establish `residentialapps/`.

The specific v0.5 machinery—pinned external application packages, source-repo release coordination, and Cordware as deployment-only composition repo—is **not part of the v0.7 direction**.

## 8. Status and references

- `cordware_repository_strategy_v0.4.md` — original separate canonical repos and synchronized source.
- `cordware_repo_planning.md` — packaging, ASGI composition, dependencies, auth, configuration, migrations, and workflow questions.
- **This v0.5 file** — reconstructed evaluation of the pinned-package alternative; retrospective, never adopted.
- `cordware_repository_strategy_v0.6.md` — canonical monorepo with bounded subprojects.
- `cordware_repository_strategy_v0.7.md` — RRW-first, asymmetric monorepo and explicit implementation stages.

**Archival interpretation:** Keep this file for continuity of architectural reasoning, not as a currently actionable design contract. Do not infer from its version number that an approved v0.5 design existed at the time.
