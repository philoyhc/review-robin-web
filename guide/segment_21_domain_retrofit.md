# Segment 21 — RRW under Cordware (stages 1–2: host, sweep, identity, prefix flip)

**Opened:** 2026-10-16 · **Rewritten:** 2026-10-21, against
`docs/cordware_repository_strategy_v0.8.md` (v0.8, as revised to
2026-10-21) and `docs/cordware_implementation_sequence.md` · **Theme:**
RRW hosted by a `cordware/` package and mounted at `/reviewrobin` ·
**Related:** `docs/cordware_nus_azure_status_2026-10-16_v8.md`,
`docs/deployment_dev.md`, `docs/deployment_nus.md`,
`docs/archive/cordware_rrw_integration_spec_v0.2.md`

**On hold (author, 2026-10-16).** Nothing below starts until the author
lifts the hold, and this rewrite does not lift it. What waits on it has
grown: v0.8 sequences Residential Apps (stage 3) after this segment and
deploys nothing to NUS before 21D (v0.8 §5).

This is the **outline** for v0.8's stages 1 and 2 in RRW's repository.
The work lands as sub-segments `21A`–`21D`, each with its own
`guide/segment_21X_<slug>.md` opened when it starts. This file holds the
split, the cross-cutting decisions and the audit; v0.8 is the source of
truth for the strategy, so this file cites it rather than restating it.
The 2026-10-16 outline it replaces is under `## Superseded plan`.

## Opportunity

The target architecture serves RRW inside one Cordware App Service at
`cordware.nus.edu.sg/reviewrobin` (v8 report §3). v0.8 decides how: RRW
stays at the repository root, a small stateless `cordware/` package
hosts it and supplies trusted identity, and Cordware plus any single
application must run on its own (v0.8 §3). RRW today assumes the
opposite at every layer (§ Blast radius):

- **It builds itself:** a module-level app (`app/main.py:138`) that every
  start command and test client names, configuring the root logger.
- **It writes root paths:** 192 template attributes, 194 Python code
  lines (76 redirect targets among them), 3 cookie paths, 6 `/.auth/*`
  references; 5 `url_for` calls are its only route-aware generation.
- **It owns identity:** Easy Auth parsing, the fake user and
  `SUPER_ADMIN_EMAILS`, and nothing enforces "never enable fake auth when
  deployed". `docs/deployment_nus.md` still says hosts change without code.

## Decision

**Four sub-segments, the implementation sequence's workstreams A–D, in
the order A → (B ∥ C) → D** (sequence §3–§5, accepted into v0.8 §5 on
2026-10-20). Every step but D leaves RRW's behavior at `/` unchanged and
merges on its own; D is the only one that changes a URL.

| Sub-segment | What | Gate to start | Provable in CI? | v0.8 |
|---|---|---|---|---|
| **21A — Host skeleton** | `cordware/main.py` with `CORDWARE_APPS` (empty: Cordware alone, `/health`); RRW mounted **at `/`**; RRW built once (module-level app removed, its consumers moved); every start command on `cordware.main:app`, with the dev deploy artifact and package discovery carrying `cordware/`; root logging owned by the host; the import-boundary test | Stage 0's RRW baseline recorded (v0.8 §5) | Yes; the dev slot's start command is the author's, in Azure, switched within A2 | Stage 1 |
| **21B — URL sweep** | A URL helper for strings built outside a request; a harness mounting RRW at `/reviewrobin`; a leak check with a shrinking allowlist; the sweep by area; the allowlist removed | 21A merged (the harness is Cordware) | Yes | Stage 1 |
| **21C — Shared identity** | Easy Auth parsing, the fake identity and its `APP_ENV` guard move to `cordware/identity.py` behind a re-export; RRW's fake roles read Cordware's fake marker; super-admin becomes Cordware's platform role | 21A merged; the dev slot's `APP_ENV` set non-`local` before the guard lands | Yes, except the dev slot | Stage 2 |
| **21D — Prefix flip** | RRW mounted at `/reviewrobin`; Cordware's landing page at `/`; `/.auth/*` return paths; deep-link return; the dev slot live check | 21A and 21B closed; 21C closed, so one live check covers identity and prefix together | App side yes; the live check is the author's, on the dev slot; the NUS gateway's path and host header only at stage 4 | Stage 2 |

```text
21A ──┬──> 21C ──┐
      │          ├──> 21D ──> (v0.8 stage 3: Residential Apps)
21B ──┴──────────┘
```

**Rejected: the 2026-10-16 outline's `BASE_PATH` shim.** It accepted the
path with or without the prefix so the gateway's keep-or-strip answer
would not matter, and it rejected a fixed mount because that answer was
open and the suite would move off `/`. v0.8 §3 settles both: the
gateway must forward the path unchanged, and the mount supplies the
prefix (`root_path`) with no setting or shim. RRW's TestClient tests
still call RRW's own app at app-relative paths. Also rejected (sequence
§4): v0.8's first order (flip with the sweep) and routing first.

## Semantics

- **Built once.** `create_app()` returns a complete ASGI app; importing
  `app.main` builds nothing, and a test says so. `app/web/return_to.py`
  checks GET routes on `request.app` (RRW's sub-app under a mount), not
  on a module global.
- **App-relative inside RRW.** Routes, specs and RRW's TestClient tests
  stay app-relative: they call `create_app()` directly, through one
  session-scoped fixture, and Cordware's own tests mount RRW. The
  browser tests drive a live server and do move: from 21A it is
  Cordware with RRW at `/`, so their root paths hold until 21D
  (Open question 9).
- **At `/` (21A–21C) behavior is unchanged.** `root_path` is empty, so
  route-aware generation returns today's strings, and the existing suite
  is the regression proof. Output is never edited to suit the mount.
- **Under the mount (21B's harness, then 21D).** Every emitted URL
  carries `/reviewrobin` through route-aware generation: links, form
  actions, redirects, `fetch` targets, `src` and cookie `Path`s. Path
  comparisons compare the app-relative path; `return_to` values travel
  app-relative, normalized once at `app/web/return_to.py`.
  Starlette's `root_path` semantics (what `request.url.path` holds under
  a mount) are pinned by tests in 21B's first rung, not assumed.
- **The literal `/reviewrobin`** appears only in `cordware/` and
  deployment docs, never in `app/` (v0.8 §3).
- **`/.auth/*` is the host's** (v0.8 §3), so the leak check excludes it
  by rule, not by allowlist; 21D fixes its return paths.
- **A mounted application's failed startup validation fails the
  process** (v0.8 §3); no degraded mode.
- **No redirects** from old root paths (v0.8 §3).
- **Probes.** `/health` is the host's and needs no interactive sign-in;
  `/reviewrobin/health` is optional.
- **Identity, fake auth, super-admin, settings and logging** follow
  v0.8 §3 as written; the points RRW's code turns on:
  - Cordware is the only Easy Auth parser (headers, not paths). RRW's
    `users` rows, roles and audits stay RRW's (v0.8 §4); no login audit.
  - RRW's fake *application* roles key off Cordware's fake marker, never
    the literal email. Cordware refuses to start when `ALLOW_FAKE_AUTH`
    is on and `APP_ENV` is not `local`.
  - RRW reads `is_super_admin`, `is_super_admin_email` and
    `super_admin_configured` over Cordware's effective list and never
    parses `SUPER_ADMIN_EMAILS`; its any-admin fallback keys off
    `super_admin_configured`.
  - One repository-root `.env`; every switch keeps its name, default and
    per-run override. RRW logs under a named logger; the host owns root.

## Judgment calls — decided

- Sub-segments follow the sequence's A–D, replacing the old 21A–21D
  (2026-10-21). The old split cut on NUS IT and Azure gates that v0.8
  removes from stages 1–2 (§ Superseded plan).
- The leak check's allowlist only shrinks, so 21B lands in small PRs
  without a flag day (`constitution.md` II), carried from 2026-10-16.
- Sign-in establishes identity only; each application decides
  permissions (v0.8 §1; carried from 2026-10-16).
- The landing page is in scope, in 21D: v0.8 puts it in `cordware/web/`
  in this repository; the old outline excluded it as a separate codebase.
- `app/auth/identity.py` becomes a re-export in 21C, so its 77 importers
  move later or never (sequence C4, optional).
- 21B's harness is Cordware, mounting RRW at `/reviewrobin`, because 21A
  lands first (sequence §3).
- `return_to` travels app-relative, carried from 2026-10-16: one
  normalization point, not a prefix threaded through every value.

## Blast radius (measured)

Taken 2026-10-21 at `50be3a2c`. `ROOT` is a quoted string starting
`/operator`, `/me`, `/guide`, `/about`, `/auth`, `/static`, `/health`,
`/sessions` or `/.auth`; `/templates/` hrefs fall inside the template
counts. "ast" counts skip decorators and docstrings exactly; grep cannot.
The sequence's counts (at `4ed8114`) differ mainly by method.

| Sub | What | Count | Command / note |
|---|---|---|---|
| A | Importers of the module-level app | 16: `app/web/return_to.py:65`, 14 test files, `tools/bench_roster_scale.py` | `grep -rlE 'from app\.main import app\b' --include='*.py' app tests tools` |
| A | `app.main:app` in live start commands | `README.md`, `CLAUDE.md`, `.devcontainer/devcontainer.json`, `tests/browser/conftest.py`, `docs/local_setup.md` (3), `docs/setup_codespaces.md` (2), `docs/deployment_nus.md` (2), `docs/deployment_dev.md` | `grep -rnE 'app\.main:app' .`; the string is in no workflow |
| A | Dev deploy artifact and packaging | the dev workflow uploads `app/`, `alembic/`, `alembic.ini`, `requirements.txt`, `pyproject.toml`, `antenv/` and deploys on every push to `main`; `pyproject.toml:35` finds `app*` only; `testpaths = ["tests"]` (`:38`) | `.github/workflows/main_app-review-robin-web-dev.yml:56–62` |
| A | Root-logger setup | `app/logging_config.py:96–106`, called first in `create_app()` | `alembic/env.py:22`'s `fileConfig` also replaces root handlers |
| B | Template `href`/`action`/`formaction`/`src="/` | 95 / 50 / 9 / 38 (39, 20, 3, 1 files) | `grep -rnoE '(^\|[^a-z])href="/' app/web/templates \| wc -l`, per attribute |
| B | Template attributes built in Python (`="{{`) | 58 href, 28 action, 3 formaction | same, with `\{\{` |
| B | Other `ROOT` strings in templates (Jinja, JS) | 47 lines in 16 files | `grep -rnE "[\"'\`]ROOT" app/web/templates`, less the attribute hits |
| B | `fetch(` / `location` assignments | 7 (3 with a literal root target) / 6 | `grep -rnE '\bfetch\(' app/web/templates` |
| B | `request.url.path` | 20 live lines in 8 templates; 4 in `app/web/error_handlers.py` | `grep -rnE 'request\.url\.path'` |
| B | `ROOT` code lines in Python | 194 in 37 files (ast); 273 by grep | ast: per-line `ROOT` match over `app/**/*.py`, decorator and docstring line ranges dropped; top: `_instruments.py` 15, `_operations.py` 15, `breadcrumbs.py` 12 |
| B | `RedirectResponse` with a `ROOT` target | 76 of 124, in 21 files (ast) | ast: `RedirectResponse` calls whose first argument or `url=` is a `ROOT` constant or f-string; grep finds 4, as most put `url=` on the next line |
| B | Cookies with a root path | 3 server (`_operations.py:281`, `_sys_admin.py:84`, `:403`); 1 script family (`base.html`, `_rrwCookiePath`) | `grep -rnE 'set_cookie\(' app` |
| B | `url_for` | 5, all `request.url_for("reviewer_invite")` (absolute invite links); 0 in templates | `grep -rnE '\burl_for\(' app` |
| B | Proxy or `root_path` handling | 0 | `grep -rniE 'root_path\|ProxyHeaders\|X-Forwarded' app` |
| C | `app/auth/identity.py` | 165 lines; imported by 4 app files, 72 test files, 1 tool | `grep -rlE 'app\.auth\.identity'` |
| C | Settings moving to Cordware | `app_env`, `allow_fake_auth`, `fake_auth_principal_id`/`_email`/`_name`, `fake_auth_super_admin`, `super_admin_emails`, `log_level` | `app/config.py:8–75` |
| C | `APP_ENV` reads | `app/main.py:64` (warning), `app/config.py:140` (`validate_critical_settings`) | `grep -rnE '\bapp_env\b' app` |
| C | Super-admin reads | `effective_super_admin_emails` (`app/auth/roles.py:22`) at `roles.py:53`, `services/users.py:375`, `services/account_listing.py:81, 295`, `_sys_admin.py:386`; empty-list warning `app/main.py:64–70`; `is_super_admin` callers `deps.py:96, 165`, `services/users.py:377, 393`, `services/account_listing.py:222`, `db/models/user.py:100` | `grep -rnE 'effective_super_admin_emails' app` |
| C | Fake roles and `is_fake` | `app/web/deps.py:156–160` (first sign-in only); `is_fake` in `identity.py`, `deps.py`, `services/users.py:123`, `routes_auth.py:37`, `me_debug.html` | `grep -rnE 'is_fake' app` |
| C | Tests on super-admin or fake auth | 13 files; 16 counting env-var spellings | `grep -rlE 'super_admin\|fake_auth' tests`; `-rliE` for 16 |
| D | `/.auth/*` references | 6: `error_handlers.py:118`, `me_debug.html:55`, `_top_bar.html:50`, `base.html:5328`, `error.html:121, 123` | `grep -rnE '/\.auth' app` |
| D | RRW's root redirects | `/` (`app/main.py:113`), `/operator` (`:126–133`), the allowlist-denied redirect (`:111`) | `grep -nE 'RedirectResponse\|@app\.get' app/main.py` |
| — | Test requests at root paths | 3,422 TestClient calls in 296 files (ast), unchanged by design; 79 browser `page.goto`, which move with 21D | ast: calls whose first argument is a `ROOT` constant or f-string; grep on one line finds 797 |

## PR ladder

At this level the ladder is the sub-segment sequence; each plan carries
its own PRs. The rungs below are the sequence's §5, to be re-cut there.

1. **This rewrite**, prose only; it touches no `app/`, `tests/` or
   `cordware/` file.
2. **21A plan, then:** A1 `cordware/` with `CORDWARE_APPS`, `/health`
   and RRW at `/`, tested alone and with RRW · A2 built once: the
   module-level app, `return_to.py`, the 15 test and tool importers onto
   one fixture, the browser harness, every start command, and the dev
   artifact and package discovery carrying `cordware/`, in one rung; the
   author switches the dev slot's start command as A2 merges, since the
   slot redeploys on every push · A3 host-owned logging and the
   import-boundary test.
3. **21B plan, then:** B1 the helper, the harness, Starlette's semantics
   pinned and the leak check with a full allowlist · B2 the sweep by
   area (chrome and `base.html`; Setup; Operations; Instruments; Session
   Home and lobby; Sys Admin; participant surfaces; Guide, About and
   static; Python emitters and services; cookies and `return_to`) ·
   B3 the allowlist removed.
4. **21C plan** (alongside 21B), after the author sets the dev slot's
   `APP_ENV`: C1 `cordware/identity.py`, fake identity, host-level fake
   state, `APP_ENV` and its guard, with `effective_super_admin_emails()`
   switched to that state in the same rung · C2 RRW's fake roles keyed
   off the marker, the fake super-admin still resolving · C3 the
   platform super-admin, its warning moved, RRW's `fake_auth_super_admin`
   retired · C4, optional, the importers repointed.
5. **21D plan, then:** D1 the mount at `/reviewrobin`, the landing page
   (scaffold first), RRW's `/` redirect, the browser harness, `/.auth/*`
   return paths and deep-link return ·
   D2 the dev slot redeployed and the author's live check of v0.8 §3's
   behavior requirements 1–3 and identity under real Easy Auth.

## Definition of done

- Cordware alone and Cordware + RRW both run, and the import-boundary
  test passes (21A).
- Importing `app.main` builds nothing; no live start command names
  `app.main:app` (21A).
- Under the `/reviewrobin` harness the leak check passes with no
  allowlist, `/.auth/*` excluded by rule (21B).
- The trusted-identity interface is tested on its own; Cordware
  refuses to start with `ALLOW_FAKE_AUTH` on and `APP_ENV` not `local`;
  the super-admin flag, predicate and fallback are tested with an empty
  and a non-empty list;
  the fake user keeps every role (21C).
- The dev slot serves RRW at `/reviewrobin`, and the author has
  verified behavior requirements 1–3 and real-Easy-Auth identity there;
  requirement 4 and the gateway's path and host header wait for the NUS
  cutover (21D; v0.8 stage 4).
- v0.8 §8's stage 1–2 decisions are settled and recorded in v0.8
  (21A–21C).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 21` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

1. **Where do 21A's and 21C's plans live?** The author decides
   (sequence §6.2). Recommended: here, as sub-segments, since the plan
   tooling reads `guide/`; the settled contract goes to `cordware/spec/`.
2. **The lifespan contract's shape** (v0.8 §8). Decided in 21A.
3. **URLs built outside a request, and the public host** (v0.8 §3
   behavior requirement 4). The helper is 21B's; whether absolute links
   (the five invite `url_for`s, emails) take a configured public base or
   a forwarded host depends on the gateway's host-header behavior, still
   open with NUS IT (v8 report §8.1). The dev slot sits on its own
   `azurewebsites.net` host, so it cannot show a backend-name leak; that
   check is stage 4's.
4. **The trusted-identity interface** (v0.8 §8). Decided in 21C.
5. **The dev slot's `APP_ENV`** (v0.8 §8): non-`local` before C1, the author's.
6. **Path scoping for RRW's repo-wide tooling** once `cordware/` has
   code (v0.8 §8): `tools/close_check.py`, `tools/pace_audit.py`, the
   doc gates, `test_spec_coverage`, ruff and pytest paths, and CI's
   required checks for `cordware/tests/`. Decided in 21A.
7. **Console logs reaching Log Analytics** (v0.8 §8): the author, in Azure.
8. **Should a service build URLs?** `services/validation.py`'s fix
   links could move to a view. The author rules in 21B.
9. **The browser tests under the mount.** After 21D, a root
   `page.goto` reaches Cordware, not RRW. Prefix them through the
   harness's base URL, or keep a browser harness that mounts RRW at
   `/`. Decided in 21D.

Answered by v0.8 and the v8 report, from the 2026-10-16 list: one Easy
Auth boundary on one App Service serves every application (v8 report
§4.1, §11.1); `/reviewrobin` is the path (v0.8 §3). The gateway's
keep-or-strip is answered for RRW's design only: v0.8 §3 requires it to
forward the path unchanged, which NUS IT has yet to configure (v8 report
§8.1); it is checked at stage 4 (Out of scope).

## Out of scope

- **Stage 0's privacy step and Residential's provenance:** the author's,
  before Residential's import (v0.8 §5). Its RRW baseline gates 21A.
- **Stages 3 and 4:** Residential Apps, the integrated release, the NUS
  deploy and cutover, database option B or C and `RRW_DATABASE_URL`
  precedence, the NUS deploy workflow's artifact.
- **Infrastructure:** Application Gateway, whose path forwarding and host
  header NUS IT configures and stage 4 checks; DNS, TLS, the Easy Auth
  registration's repurposing (v8 report §8.1, §11.1), the runner VM.
- **v0.8 non-goals:** a Cordware database, console or log viewer; a
  standalone RRW runtime.
- **The repository rename**, optional and later (v0.8 §7).
- **Segment 20's administrator guide**, gated where it is.

## Doc impact

Provisional at outline level; each sub-segment plan takes over its bullets.

- `spec/architecture.md` — RRW as a mounted application: built once by `create_app()`, app-relative routes, route-aware links, identity from Cordware (21A, 21B, 21C).
- `spec/settings_inventory.md` — settings ownership per v0.8 §3; cookie paths under the mount (21B, 21C).
- `spec/sort_by_reviewee.md` — the sort-cookie path under the mount (21B).
- `spec/permissions.md` — super-admin from Cordware's flag, predicate and `super_admin_configured`; the fake-auth fold-in and the no-super-tier fallback (21C).
- `spec/audience_and_identity_model.md` — super-admin as Cordware's platform role; fake identity and its guard owned by Cordware (21C).
- `docs/local_setup.md` — running through `cordware.main:app`; one `.env`; `CORDWARE_APPS` (21A, 21C).
- `docs/setup_codespaces.md` — the start command (21A).
- `docs/deployment_dev.md` — the dev slot's start command (21A), `APP_ENV` (21C), served at `/reviewrobin` (21D).
- `docs/deployment_nus.md` — the start command; "no code change" retired (21A, 21D).
- `docs/security_posture.md` — the fake-auth guard enforced; identity interpreted by the host (21C).
- `docs/cordware_repository_strategy_v0.8.md` — §8's stage 1–2 decisions recorded as each sub-segment settles them (21A–21C).
- `docs/cordware_implementation_sequence.md` — retired to `docs/archive/` at 21D's close; the sub-segment plans carry its ladder (21D).
- `CLAUDE.md` — the run command; "never write a root-path URL"; "Identity and auth" and the local auth shortcut (21A, 21B, 21C). `AGENTS.md` twinned.
- `.github/workflows/main_app-review-robin-web-dev.yml` — the dev artifact carries `cordware/` (21A).
- `pyproject.toml` — package discovery and test paths take in `cordware/` (21A).
- `README.md` — the run command (21A).
- `cordware/spec/` — Cordware's host and identity contract, created by 21A (21A, 21C); checked by hand at close, since `close_check` does not read `cordware/` paths.

## Superseded plan

The 2026-10-16 outline, in full: `git show
68097709:guide/segment_21_domain_retrofit.md`. Written against
integration spec v0.1 for RRW as its own App Service, it split 21A
base-path foundation, 21B sweep, 21C auth and edge, 21D NUS cutover.

- `BASE_PATH`, the shim and `app_url()` → the mount's `root_path`.
- The trusted-proxy allowlist and `PUBLIC_BASE_URL` → not adopted; the
  public host for absolute links is Open question 3.
- Old 21C (Easy Auth on a shared host, gated on NUS IT) → one Easy Auth
  boundary, identity moved to Cordware in new 21C, no outside gate.
- Old 21D (NUS cutover) → v0.8 stage 4; the live proof is new 21D's,
  on the dev slot. Its audit (`74f57a71`) → § Blast radius.
