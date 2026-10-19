# Cordware Repository Planning — Open Issues

**Status:** Working notes, nothing decided  
**Date:** 17 October 2026  
**Inputs:** `cordware_repository_strategy_v0.4.md`, `cordware_rrw_integration_spec_v0.2.md`, `cordware_nus_azure_status_2026-10-16_v8.md`, and the `review-robin-web` (RRW) codebase as of `main` on this date.

The strategy doc sketches a repo shape (`app/core/`, `app/reviewrobin/`, `module-manifest.yml`, …). This document lists the open questions that have to be answered before that shape can be settled. For each issue it gives the facts, the options, and a provisional leaning where there is one. A leaning is a suggestion, not a decision.

Facts about `nuscr-res-apps` (Residential Apps, RA) are **unknown**: that repo has not been read. Every RA statement below is a question.

---

## Summary

| # | Issue | Decides | Blocks |
|---|---|---|---|
| 4 | How module source gets into Cordware, and under what Python package name | Repo layout; the sync mechanism | Almost everything |
| 5 | Mount each module as a sub-app, or merge its routers | `app/core/` composition code; RRW retrofit scope | 7, 11 |
| 6 | One shared set of Python dependencies | Lockfile ownership; module upgrade policy | Packaging |
| 7 | Landing-page discovery vs module-local authorization | The module interface | Shell |
| 8 | Configuration name collisions | Env/Key Vault naming; RRW settings retrofit | Deploy workflow |
| 9 | Migrations for several modules | Deploy workflow; runner tasks | Deploy workflow |
| 10 | What happens to RRW's existing deploy workflows | Transition plan | — |
| 11 | Local fake auth in the assembled app | `app/core/` identity code | Local dev |
| 12 | Infrastructure identifiers in the repos | Repo visibility; doc hygiene | — |

**Decide 4 and 5 first.** Most of the other issues follow from them.

---

## 4. How module source gets in, and the package name

**Facts.**
- RRW's code is a top-level Python package named `app` (`pyproject.toml`: `include = ["app*"]`). Every import is absolute: `from app.services…`, `from app.config import settings`. `alembic/env.py` imports `app.config`.
- The strategy doc puts RRW at `cordware/app/reviewrobin/`. Copied there unchanged, RRW's imports would resolve to `app.services` in Cordware's namespace, which doesn't exist. Or worse, it clashes with Cordware's own `app`.
- The docs require that the copy be "exportable without manual patching" and "not edited directly".
- RA probably has the same problem if it also uses the common `app/` layout (**unknown**).

**Options.**

| Option | How | For | Against |
|---|---|---|---|
| **A. Rename in the source repo** | RRW renames `app/` → `reviewrobin/` (or `rrw/`) in its own repo. The sync copies that folder as-is. | A clean, true copy. Cordware layout as the docs sketch it. | A one-off sweep across all RRW imports, tests, Alembic, workflows, docs and doc-gate tests. Needs the same rename in RA. |
| **B. Rewrite imports during sync** | The sync script rewrites `app.` → `reviewrobin.` while copying. | No change to the source repos. | The copy is no longer byte-identical to the source. A regex rewrite is fragile (strings, dynamic imports, templates). Bends the "not edited" rule. |
| **C. Install as a package, don't copy** | Cordware's dependencies include `review-robin-web @ git+https://…@<sha>`. The manifest *is* the pinned requirement. Still needs a distinct package name (as A). | No copied tree to protect from edits. Rollback means changing a pin. The sync PR is a one-line diff. Matches §10 of the strategy doc (repos stay independently deployable). | Templates, static files and `alembic/` must ship inside the package (package-data). Cordware's code review can't see module source in its own PRs. A private repo needs a deploy-time credential. |
| **D. Git submodule** | `app/reviewrobin` is a submodule pinned to a SHA. | The SHA is recorded natively. | Still needs A for imports. Submodules are awkward in CI and Azure packaging. Easy to drift out of step. |

**Leaning:** do **A** in any case, because a module named `app` can't sit next to another module named `app`. Then choose between **C** (package) and copy-after-rename. C is simpler to keep correct. Copying keeps the module's code visible in Cordware PRs, as the strategy doc wants.

**Decisions needed:**
1. Is a package rename in RRW acceptable? If so, what name?
2. Copy or package install?
3. Does RA already avoid the name `app`?

---

## 5. Sub-app mount or router merge

**Facts.** RRW's `create_app()` (in `app/main.py`) sets up more than routers:
- an app-wide dependency (`refuse_oversized_ids`);
- a `/static` mount;
- `register_error_handlers(app)`, plus an `OperatorAllowlistDenied` handler that redirects to `/me`;
- a role-aware `/` route;
- `configure_logging()` and `validate_critical_settings()`, called inside `create_app()` itself (RRW has no lifespan or `on_event` handlers), so they run when Cordware calls the factory.

**Options.**
- **Mount:** `cordware.mount("/reviewrobin", reviewrobin.create_app())`. Each module stays a complete ASGI app. Starlette sets `root_path`, so `url_for` and `request.url_for` produce prefixed URLs automatically. Error handlers, middleware and static files stay contained in the module. Cordware core only needs to know "path prefix → ASGI app".
- **Router merge:** `cordware.include_router(reviewrobin.router, prefix="/reviewrobin")` (the spec's example). App-level pieces have to be lifted out and re-applied by Cordware, and RRW's exception handlers would become global, affecting RA too.

**Interaction with Segment 21.** The Segment 21 outline rejected a fixed mount only because the gateway's keep-or-strip behavior was unknown. Under v8, Cordware owns the routing, so that reason is gone. Strings written as root paths (`href="/…"`, `RedirectResponse("/me…")`, inline JS, cookie `Path`s, the `/.auth/*` links) still need the Segment 21 sweep under either option. Mounting fixes only the `url_for` URLs.

**Shared-process issues that remain even with mounting:**
- **Logging.** RRW's `configure_logging()` replaces the root logger's handlers. Two modules doing that collide, so logging setup should move to Cordware core, with modules logging under a named logger plus a `module` field (v8 §14).
- **Process-wide singletons.** Each module's settings object, SQLAlchemy engine and `DeclarativeBase` are created when its module is imported. That's fine if each module has its own, which follows from the distinct package names in issue 4.
- **Lifespans don't propagate.** Starlette/FastAPI run lifespan and startup events only for the top-level app, not for mounted sub-apps. RRW is unaffected today (see above), but the module contract must say so. Either startup work happens in the factory, or Cordware's own lifespan explicitly runs each module's lifespan. Check RA for lifespan handlers.
- **Startup validation.** If one module's settings fail validation, the whole process is down, RA included. Is that acceptable, or should a failing module be disabled while the rest serve?

**Leaning:** mount.

**Decisions needed:**
1. Mount or merge?
2. Should one module's startup failure take down the whole process?

---

## 6. Shared dependencies

**Facts.**
- One process means one virtualenv. RRW's lower bounds are `fastapi>=0.115`, `pydantic>=2.7`, `sqlalchemy>=2.0`, `alembic>=1.13`, Python 3.12, with no upper pins. Azure deploys from `requirements.txt`.
- RA's stack and versions are **unknown**.

**Issues.**
- Who owns the lockfile? Probably Cordware: a `requirements.txt`/lock generated from the union of module requirements, checked in CI.
- A module that needs an upgrade (e.g. a new FastAPI major) now needs the other module to keep up. The module repos would need a shared compatibility range, or Cordware CI fails the sync PR.
- Frontend: RRW has no build step (inline CSS/JS). If RA has a build step, Cordware packaging must run it.

**Decisions needed:**
1. Is RA FastAPI / SQLAlchemy 2 / Pydantic 2 on Python 3.12?
2. Should Cordware own one lockfile, with module repos declaring ranges?
3. Is RA's repo to be added to this workspace so it can be read?

---

## 7. Landing-page discovery vs module authorization

**Facts.**
- v8 §4.3: the landing page may show only the tiles a user is eligible to discover. This is not an authorization boundary.
- Eligibility is module knowledge. In RRW it depends on operator/admin allowlists (`OPERATOR_EMAILS`, `SYS_ADMIN_EMAILS`) and on roster membership in the RRW database.

**Options.**
- **A. Show every tile to everyone.** No coupling between core and modules. Unauthorized users are denied by the module itself (RRW already redirects non-operators to `/me`).
- **B. A per-module discovery hook.** Each module exposes `discoverable(identity) -> bool`. Core calls every module's hook on each landing-page load, which touches every module's database. The interface stays narrow, but it is new code to write and keep working.
- **C. Static config.** A tile is visible only to certain email domains or groups. Crude, and kept outside the module.

**Leaning:** A first, with B designed into the module interface for later.

**Decisions needed:**
1. Show all tiles now, or filter from day one?
2. Should the landing page also show anonymous/public content?

---

## 8. Configuration name collisions

**Facts.**
- RRW's `Settings` reads bare environment names (no `env_prefix`) from `.env`: `DATABASE_URL`, `APP_ENV`, `LOG_LEVEL`, `ALLOW_FAKE_AUTH`, `FAKE_AUTH_*`, `OPERATOR_EMAILS`, `SYS_ADMIN_EMAILS`, `SUPER_ADMIN_EMAILS`, `OPERATOR_CONTACT_EMAIL`, … All modules share one App Service, so they share one environment.
- `DATABASE_URL`, `APP_ENV` and `LOG_LEVEL` are almost certain to collide with RA.
- v8 §17.2 wants separately named settings, e.g. `RRW_DATABASE_URL`.

**Options.**
- **A. Prefix in the module.** RRW sets `env_prefix="RRW_"`. If RRW's dev slot keeps running standalone, it needs either a fallback that also reads the bare names, or an env rename on the dev slot.
- **B. Cordware passes settings in.** Each module's factory takes a settings object (`create_app(settings=…)`), and Cordware builds it from prefixed variables. This is a cleaner interface, but RRW's `settings` is a module-level global imported in many places.
- **Shared settings** (`APP_ENV`, log level, fake auth) become Cordware-level. Modules read them through core, or core sets them for each module.

**Leaning:** A, with platform-wide settings (environment, logging, identity) owned by core. Key Vault secret names follow the same prefix (`rrw-database-url`, …).

**Decisions needed:**
1. Which prefix (`RRW_`, `REVIEWROBIN_`)?
2. Should RRW keep bare names working for the standalone/dev case?
3. Which settings are platform-level?

---

## 9. Migrations

**Facts.**
- RRW has its own Alembic chain. `alembic.ini` leaves `sqlalchemy.url` empty, and `env.py` reads `app.config.settings.database_url`. Both of RRW's current deploy workflows run `alembic upgrade head` before deploying.
- v8 §12: RRW uses the `reviewrobin` database. RA should get its own database or schema, with one database role per module.
- Only the runner (VM allocation blocked) can reach the private database.

**Issues.**
- **One chain per module.** Each module ships its own `alembic.ini`/`env.py` and runs against its own URL. Cordware's deploy runs them in a fixed order. They must not share an `alembic_version` table, which separate databases already guarantee. A shared database with separate schemas would need `version_table_schema`.
- **Invocation.** Run `alembic -c <module>/alembic.ini upgrade head` per module, or have each module expose a `migrate()` entry point. If the copy approach puts modules in subfolders, `script_location` paths must still resolve. With the package approach, `alembic/` must be shipped as package data.
- **Failure handling.** If RRW's migrations succeed and RA's fail, do we deploy anyway, or halt? A partial schema upgrade plus old code is the risky case.
- **Roles.** The migration role and the runtime role per module (least privilege, v8 §12.1).
- **Cordware CI** should run each chain's `upgrade head` and `downgrade base` round-trip against Postgres 16, as RRW's `ci-postgres` job does now.

**Decisions needed:**
1. Separate databases or separate schemas for RA?
2. Halt the whole deploy on any module's migration failure?
3. Is a `migrate()` entry point per module acceptable?

---

## 10. RRW's existing deploy workflows

**Facts.** RRW has two deploy workflows:
- `main_app-review-robin-web-dev.yml`: deploys to `app-review-robin-web-dev` on push to `main`.
- `deploy_nus.yml`: manual, deploys to the NUS Web App via `vars.NUS_WEBAPP_NAME`. The NUS OIDC subject is `repo:philoyhc/review-robin-web:ref:refs/heads/main`.

**Issues.**
- **The dev slot.** It is the author's only deployed RRW today. Does it stay standalone at root? Strategy §10 says the module repos should stay deployable on their own, which argues for keeping it. Keeping it means RRW supports both root mode and prefix mode indefinitely, and Segment 21's design (`BASE_PATH` empty = byte-identical) already supports that.
- **`deploy_nus.yml`** should be retired, or reduced to a dead stub, once Cordware deploys. Until then, two repos can deploy to the same Web App. The OIDC subject swap (v8 §15.1) cuts RRW off automatically.
- **A Cordware non-production target.** Is there anywhere to deploy the assembled app before production? Could the RRW dev slot host a Cordware build, or is a separate target needed?

**Decisions needed:**
1. Keep the RRW dev slot standalone?
2. Is there a Cordware staging target, and which one?
3. When should `deploy_nus.yml` be retired?

---

## 11. Local fake auth in the assembled app

**Facts.**
- RRW's `app/auth/identity.py` parses the `X-MS-CLIENT-PRINCIPAL*` headers. `ALLOW_FAKE_AUTH` (with `FAKE_AUTH_EMAIL`, `FAKE_AUTH_NAME` and role flags such as `FAKE_AUTH_OPERATOR`) injects a fake user locally. `validate_critical_settings` refuses fake auth outside `local`.
- Integration spec §6: core provides a narrow identity interface; modules consume it.

**Issues.**
- **Where headers are parsed.** In the assembled app, core should parse Easy Auth headers once and hand modules an identity (e.g. on `request.state` or `scope`). Modules shouldn't read the headers themselves. Standalone RRW still needs its own parser, so RRW's identity code becomes "use the identity core supplies if present, otherwise parse."
- **Fake auth splits in two.** The fake *identity* (email, name) belongs to core. The fake *role* flags (`FAKE_AUTH_OPERATOR`, …) are RRW authorization, so they stay in RRW, under the issue-8 prefix.
- **One switch, one guard.** Core owns `ALLOW_FAKE_AUTH` and the fail-fast check that it's off outside `local`. Modules shouldn't be able to turn on fake auth on their own.
- **A user switcher** for local testing across modules (operator in RRW, plain user in RA)? This would be nice to have, not required.
- **Header spoofing.** With `publicNetworkAccess = Disabled` and the gateway in front, only Easy Auth can set these headers. The identity interface should still document that it trusts them only behind Easy Auth.

**Decisions needed:**
1. Should core own fake identity and the guard, with modules owning fake roles?
2. How should identity be handed over: `request.state`, a FastAPI dependency exported by core, or both?

---

## 12. Infrastructure identifiers in the repos

**Facts.**
- The v8 report contains the subscription ID, tenant ID, Easy Auth and deploy client IDs, the managed-identity principal ID, internal IPs and the public IP. None of these are credentials, but together they are a reconnaissance map.
- Copies sit in both `cordware/docs/` and `review-robin-web/docs/`.

**Issues.**
- Are both repos private? If either is (or will become) public, these docs should move out, or be redacted down to resource names.
- **Two copies will drift.** Choose one owner: Cordware, since v8 describes the Cordware platform. RRW keeps only the integration spec (its own contract) and a pointer to the rest.
- Production secrets and variables go in Cordware's GitHub environment (v8 §17.2). None belong in either repo's files.

**Decisions needed:**
1. Confirm both repos' visibility.
2. Should Cordware become the only home for the v8 status report and the strategy doc?

---

## What this means for the repo shape

Provisionally, if the leanings above hold:

```text
cordware/
├── cordware/                 # core package: shell, identity, composition, logging
│   ├── main.py               # create_app(): mounts modules at their prefixes
│   ├── identity.py           # Easy Auth parsing + fake auth (local only)
│   ├── modules.py            # module registry: prefix, factory, migrate(), discoverable()
│   └── templates/            # landing page
├── modules.yml               # manifest: repo, commit, package, prefix
├── requirements.txt          # one lock for the process (incl. pinned modules if installed)
├── tests/                    # shell, identity, mount, cross-module, config-collision tests
├── deployment/               # startup command, migration runner script
├── docs/
└── .github/workflows/        # ci, sync-<module>, deploy
```

With the copy approach instead of package install, add `modules/reviewrobin/` and `modules/residentialapps/` (generated, CODEOWNERS-protected) and drop the pins from `requirements.txt`. The core package is named `cordware`, not `app`, for the same reason as issue 4.
