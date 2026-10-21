# Segment 21A — Cordware foundations (the host skeleton, RRW still at `/`)

**Opened:** 2026-10-21 · **Parent:** `guide/segment_21_domain_retrofit.md`
(the outline; its split, semantics and gates bind here) · **Source:**
`docs/cordware_repository_strategy_v0.8.md` §2–§3, §5 stage 1 and
`docs/cordware_implementation_sequence.md` workstream A · **Theme:** a
stateless `cordware/` host serves RRW, mounted at `/`, and every start
command names it

**Segment 21's hold** (author, 2026-10-16) was lifted for A0 on
2026-10-21, when the author started it. A1 onward still waits on the
author.

## Opportunity

v0.8 serves RRW only through Cordware (§3, "no supported standalone
runtime"), and RRW is built to be its own process (§ Blast radius):

- `app/main.py:138` builds the app at import, and 16 modules import that
  object, among them `app/web/return_to.py:65`, which reads it mid-request
  to ask whether a GET route serves a path.
- 13 live start-command lines in 8 files (and `AGENTS.md`'s twin) name
  `app.main:app`, including the dev slot's `gunicorn` line and the
  browser harness.
- `create_app()` configures the **root** logger (`app/logging_config.py:89`),
  which a host that mounts a second application cannot allow.
- Nothing ships, packages or tests a `cordware/` directory: the dev
  artifact uploads six named paths, `pyproject.toml` finds `app*` only and
  pytest collects `tests/` only.

## Decision

**Three build rungs after a stage 0 record, in the sequence's A1–A3
order, with RRW mounted at `/` so its behavior and URLs do not change.**

- **The host.** `cordware/main.py` holds `create_app(apps=None)` and the
  entry point `app = create_app()`. It registers the host's `/health`
  first, then mounts each application named by `CORDWARE_APPS` from an
  explicit registry (`reviewrobin` → `app.main:create_app`, mounted at
  `/` until 21D). An empty `CORDWARE_APPS` runs the host alone.
- **Lifespan contract** (v0.8 §8, outline Open question 2): the host's
  lifespan enters each mounted application's `router.lifespan_context` in
  mount order and exits in reverse. RRW has no lifespan today, so a stub
  application proves the contract. Rejected: startup work only in
  factories. It holds for RRW today, but it would forbid any future
  application a lifespan, and Starlette silently skips a mounted
  application's lifespan.
- **Built once.** RRW's module-level `app` goes. `return_to` asks the
  router the request runs in (`request.app`, RRW's own app under the
  mount). Tests build RRW through one session-scoped fixture.
- **The host owns logging.** It configures the root logger with RRW's
  `JsonFormatter`, and each record carries the application that wrote it.
  RRW's factory stops touching root.

Rejected: **one rung for A1–A3** (the sequence's A collapsed). The start
command and the module-level app cannot change in the same push as the
host's first appearance: the dev slot deploys every merge to `main` and
would start a command that does not exist yet (§ PR ladder, A1).

## Semantics

- **`CORDWARE_APPS`**: comma-separated names, whitespace trimmed, case
  kept. Unset means every registered application; empty (`""`) means
  none. An unknown or repeated name refuses to start, naming the bad
  value. Read once at host construction, from the repository-root `.env`,
  and a shell value overrides it (v0.8 §3).
- **`/health`** is the host's, `{"status": "ok"}` as RRW's is today, so
  the probe and the Easy Auth excluded path keep working. Registered
  before the mount, it shadows RRW's own `/health` at the root. RRW's
  route stays and `tests/test_health.py` still reaches it directly.
- **At `/`, nothing RRW serves changes.** `root_path` is empty, so URLs
  are byte-identical. The existing suite runs against `create_app()` and
  is the regression proof (outline § Semantics).
- **A failed RRW startup check fails the host.** `validate_critical_settings`
  raising inside `create_app()` propagates out of the host's
  construction. There is no degraded mode (v0.8 §3).
- **Importing `app.main` builds nothing**, and a test imports it fresh
  and asserts so. Importing `cordware.main` builds the host once: the
  entry point is the one construction (v0.8 §3).
- **`return_to` under a mount.** The GET-route check reads the routes of
  the application handling the request. Its paths stay app-relative
  (outline § Semantics), so the check is unchanged at `/` and correct
  under `/reviewrobin`.
- **Logging.** The root handler's level comes from `LOG_LEVEL`, as now.
  Every record gains `application` (`reviewrobin`, or `cordware` for the
  host's own). The host logs start, stop and the mounted set; any mounted
  application's startup failure, logged before the process exits; and
  failing `/health` checks. These are v0.8's host-logging events 1 and 5,
  less the super-admin warning that 21C moves. `alembic/env.py`'s
  `fileConfig` is a separate process and is left alone.
- **Import boundary.** `cordware/` imports an application only through
  its registry entry. `app/` imports nothing from `cordware/` until 21C,
  and imports no `residentialapps`.

## Judgment calls — decided

- Plans for 21A–21D live in `guide/` as sub-segments: the author opened
  this one there (2026-10-21; outline Open question 1, for 21A).
- `cordware/main.py` keeps a module-level `app`, because v0.8 and the
  sequence name `cordware.main:app` as the one start command. Its tests
  call `create_app(apps=…)`.
- Mount at `/` stays a registry constant, not a setting. 21D flips it in
  one line, and no setting can move RRW off its path by accident.
- Cordware's tests live in `cordware/tests/` (v0.8 §2), collected by
  adding that path to `testpaths`. RRW's CI jobs then run them with no
  workflow change.
- The import-boundary test lives in `cordware/tests/`: it guards
  Cordware's rule, and it runs on every PR because both CI jobs collect
  that path (v0.8 §6).
- No `cordware/docs/`, `cordware/guide/` or `cordware/AGENTS.md` yet
  (v0.8 §2: "create host files only when they are needed"). Only
  `cordware/spec/` is created, at close, for the settled contract.

## Blast radius (measured)

Taken 2026-10-21 at `8b430421`.

| Rung | What | Count | Command / note |
|---|---|---|---|
| A2 | Importers of `app.main.app` | 16: `app/web/return_to.py:65`, 13 test files, `tests/integration/_public_id.py`, `tools/bench_roster_scale.py` | `grep -rlE 'from app\.main import app\b' --include='*.py' app tests tools` |
| A2 | `dependency_overrides` on that object | 59 lines in 12 files | `grep -rn --include='*.py' dependency_overrides tests` |
| A2 | `resolve_return_to(` calls needing the router | 6 in 5 app files; 31 in `tests/unit/test_return_to.py` | `grep -rn 'resolve_return_to(' app tests --include='*.py'` |
| A2 | Live `app.main:app` start lines | `README.md:115`, `CLAUDE.md:95` (+ twin), `.devcontainer/devcontainer.json:23`, `tests/browser/conftest.py:4, 96`, `docs/local_setup.md:159, 326, 507`, `docs/setup_codespaces.md:31, 54`, `docs/deployment_dev.md:38`; `docs/deployment_nus.md:109, 127` stay until stage 4 broadens the NUS artifact | `grep -rnI 'app\.main:app' . --exclude-dir=archive`, less `.claude/worktrees/` and segment 21's plans |
| A1 | Dev artifact paths | `app/`, `alembic/`, `alembic.ini`, `requirements.txt`, `pyproject.toml`, `antenv/`; deploys on every push to `main` | `.github/workflows/main_app-review-robin-web-dev.yml:56–62` |
| A1 | Packaging and collection | `include = ["app*"]` (`pyproject.toml:36`); `testpaths = ["tests"]` (`:39`); ruff already covers `.` | `grep -n 'include\|testpaths' pyproject.toml` |
| — | NUS deploy | `deploy_nus.yml` is `workflow_dispatch` only; its artifact stays as is until stage 4 (v0.8 §5) | `sed -n 1,10p .github/workflows/deploy_nus.yml` |
| A1 | Lifespans in RRW | 0 | `grep -rnE 'lifespan\|on_event\|add_event_handler' app` |
| A3 | Root-logger setup | `configure_logging()` (`app/logging_config.py:89–106`), first line of `create_app()` | — |
| A3 | Logger call sites | 12 `get_logger(` lines; 15 files log at all | `grep -rn 'get_logger(' app --include='*.py'`; `-rlE 'getLogger\|get_logger\('` for 15 |
| A1 | RRW's `/health` | `app/web/routes_health.py`, `{"status": "ok"}`; Easy Auth excludes `/health` on both slots | `docs/deployment_dev.md:247`, `docs/deployment_nus.md:159` |

## Status

- **2026-10-21, A0.** The baseline is `docs/cordware_stage0_baseline.md`,
  taken at `b03fd1be`. **It found the dev deploy workflow
  `disabled_manually`**: last run 2026-06-03, so the slot has not followed
  `main` since then. This changes the premise behind the A1 → A2 switch
  timing and § Decision's rejected alternative. A disabled workflow
  cannot be dispatched either, so no deploy reaches the slot until it is
  re-enabled. The ordering holds from then on (Open question 4).

## PR ladder

1. **This plan**, prose only.
2. **A0, the stage 0 baseline**, prose only, touching nothing under
   `app/`, `tests/` or `cordware/`. Records RRW's SHA, test totals,
   Alembic head, and launch and deploy configuration in
   `docs/cordware_stage0_baseline.md` (v0.8 §5: the gate before A1).
   Residential's provenance and the privacy step stay the author's, for
   stage 3.
3. **A1, the host.** Adds `cordware/__init__.py`, `cordware/main.py`
   (registry, `CORDWARE_APPS`, `/health`, lifespan, mount at `/`) and
   `cordware/tests/` (host alone, host + RRW, an unknown name refusing to
   start, the lifespan stub, RRW's startup failure failing the host).
   It also adds `cordware*` to package discovery, `cordware/tests` to
   `testpaths`, and `cordware/` to the dev artifact. Must not touch
   `app/` or any start command. **After it deploys, the author switches
   the dev slot's start command to `cordware.main:app`, before A2
   merges.** A2 removes the object the old command names.
4. **A2, built once.** Removes `app = create_app()`. Moves `return_to`
   onto the request's router, the 16 importers onto a session-scoped
   `rrw_app` fixture in `tests/conftest.py`, the browser harness onto
   `cordware.main:app`, and every live start line but the NUS runbook's
   (§ Blast radius). Adds
   the "importing `app.main` builds nothing" test. Must not change a
   route, a template or a URL.
5. **A3, logging and the boundary.** `configure_logging()` moves to the
   host. RRW logs under its named loggers with `application` stamped, and
   the host emits events 1 and 5. Adds the import-boundary test. Must not
   change a log record's existing fields. This is the last code rung:
   the cumulative `diff-reviewer` read runs here from A1's base SHA.
6. **Close**, prose only: `cordware/spec/host.md` by `spec-writer`, the
   lifespan and path-scope answers recorded in v0.8 §8, the specs below,
   and the plan archived.

## Definition of done

- `docs/cordware_stage0_baseline.md` records the SHA, totals and Alembic
  head the build started from (A0).
- `pytest cordware/tests` passes with `CORDWARE_APPS` unset, empty and
  `reviewrobin`; an unknown name fails construction (A1).
- `git grep -n 'app\.main:app' -- ':!guide/archive' ':!docs/archive'`
  finds only segment 21's own plans and `docs/deployment_nus.md`, whose
  command changes with stage 4's artifact (A2).
- A test imports `app.main` and finds no `FastAPI` instance on it
  (A2).
- The full suite passes on SQLite and Postgres with no test's request
  path changed (A1–A3).
- The dev slot serves RRW from `cordware.main:app`; the author checked
  sign-in and the lobby there (A2).
- A captured log line carries `application: reviewrobin`, and no RRW
  module adds a root handler (A3).
- The import-boundary test fails on a planted `import residentialapps`
  under `app/` (A3).
- Segment 21's `guide/todo_master.md` entry records 21A done and stays
  until 21D closes; only 21A's own mention in it is deleted (close).
- `cordware/spec/host.md` documents `CORDWARE_APPS`, the registry,
  `/health`, the lifespan contract and host logging (close).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 21A` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

1. **Does RRW's `/health` stay reachable at `/reviewrobin/health`?** v0.8
   §3 calls it optional. Recommended: keep it (it costs nothing and it
   probes RRW alone). The author decides in 21D.
2. **The logged form of `application`**: a top-level JSON key, or inside
   `extra`. Decided in A3 against how Log Analytics queries it
   (outline Open question 7, the author's in Azure).
3. **Repo-wide tooling's path scope** (outline Open question 6).
   Recommended for 21A: ruff and pytest take `cordware/`, the
   doc-reference and spec-coverage gates stay RRW's, and
   `cordware/spec/` is checked by hand at close. Decided in A1.

4. **When does the dev deploy workflow come back on?** It has been
   `disabled_manually` since 2026-06-03 (§ Status). Disabled, it runs on
   neither push nor dispatch, so the slot has no deploy path. Re-enabling
   it before A1 merges keeps the A1 → switch → A2 order. Re-enabling it
   only for 21D's live check means the slot jumps from the June build to
   the full A1–A2 tree, with the start command switched first. The
   author decides before A1 merges.

## Out of scope

- **The URL sweep, identity and the prefix flip:** 21B, 21C and 21D
  (the outline). Nothing here generates or rewrites a URL.
- **Host-logging events 2–4** (fake auth, identity problems, unhandled
  requests) and moving the super-admin warning: 21C and 21D.
- **The NUS deploy workflow, its start command and its runbook line**
  (`docs/deployment_nus.md:109, 127`): stage 4, together with the
  artifact that carries `cordware/` (v0.8 §5).
- **Cordware settings beyond `CORDWARE_APPS`** (`APP_ENV`, fake auth,
  super-admin): 21C.
- **Path-detected CI jobs per owner** (v0.8 §6): not needed until a
  second application lands (stage 3).

## Doc impact

- `docs/cordware_stage0_baseline.md` — created: RRW's stage 0 baseline (A0).
- `docs/local_setup.md` — run through `cordware.main:app`; `CORDWARE_APPS` (A2).
- `docs/setup_codespaces.md` — the restart command (A2).
- `docs/deployment_dev.md` — the dev slot's start command and the artifact's `cordware/` (A1–A2).
- `spec/architecture.md` — RRW as a mounted application built once; the host owns root logging (close).
- `spec/settings_inventory.md` — `CORDWARE_APPS` and `LOG_LEVEL`'s owner (close).
- `docs/cordware_repository_strategy_v0.8.md` — §8: the lifespan contract and 21A's path scope recorded as settled (close).
- `CLAUDE.md` — the run command (A2). `AGENTS.md` twinned.
- `README.md` — the run command (A2).
- `pyproject.toml` — package discovery and `testpaths` take in `cordware` (A1).
- `.github/workflows/main_app-review-robin-web-dev.yml` — the artifact carries `cordware/` (A1).
- `.devcontainer/devcontainer.json` — `postStartCommand` on `cordware.main:app` (A2).
- `cordware/spec/host.md` — created at close by `spec-writer`; checked by hand, since `close_check` does not read `cordware/` paths (close).
