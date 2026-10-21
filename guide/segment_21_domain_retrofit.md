# Segment 21 — RRW under Cordware (stages 1–2: host, sweep, identity, prefix flip)

**Opened:** 2026-10-16 · **Rewritten:** 2026-10-21, against
`docs/cordware_repository_strategy_v0.8.md` (v0.8, as revised to
2026-10-21) and `docs/cordware_implementation_sequence.md` · **Theme:**
RRW hosted by a `cordware/` package and mounted at `/reviewrobin` ·
**Related:** `docs/cordware_nus_azure_status_2026-10-16_v8.md`,
`docs/deployment_dev.md`, `docs/deployment_nus.md`,
`docs/archive/cordware_rrw_integration_spec_v0.2.md`

**On hold (author, 2026-10-16);** this rewrite does not lift it.
Residential Apps (v0.8 stage 3) and any NUS deploy wait on 21D (v0.8 §5).
**The dev slot is dormant** until the Azure work settles, and every rung
is tested on localhost (author, 2026-10-21). Its steps, start command,
`APP_ENV` and 21D's live check, wait in `docs/deployment_dev.md`
"Resuming the dev slot".

The **outline** for v0.8's stages 1–2: sub-segments `21A`–`21D`, each
with its own `guide/segment_21X_<slug>.md` opened when it starts. This
file holds the split, the cross-cutting rules and the audit, and cites
v0.8 rather than restating it. The 2026-10-16 outline is under
`## Superseded plan`.

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
| **21A — Host skeleton** | `cordware/main.py` with `CORDWARE_APPS` (empty: Cordware alone, `/health`); RRW mounted **at `/`**; RRW built once (module-level app removed, its consumers moved); every start command on `cordware.main:app`, with the dev deploy artifact and package discovery carrying `cordware/`; root logging owned by the host; the import-boundary test | Stage 0's RRW baseline recorded (v0.8 §5) | Yes; the dev slot's start command waits for its resumption | Stage 1 |
| **21B — URL sweep** | A URL helper for strings built outside a request; a harness mounting RRW at `/reviewrobin`; a leak check with a shrinking allowlist; the sweep by area; the allowlist removed | 21A merged (the harness is Cordware) | Yes | Stage 1 |
| **21C — Shared identity** | Easy Auth parsing, the fake identity and its `APP_ENV` guard move to `cordware/identity.py` behind a re-export; RRW's fake roles read Cordware's fake marker; super-admin becomes Cordware's platform role | 21A merged | Yes; the dev slot's `APP_ENV` waits for its resumption | Stage 2 |
| **21D — Prefix flip** | RRW mounted at `/reviewrobin`; Cordware's landing page at `/`; `/.auth/*` return paths; deep-link return; the dev slot live check | 21A and 21B closed; 21C closed, so one live check covers identity and prefix together | Yes, requirement 4 included; the author checks on localhost, and the real-Easy-Auth check runs when the dev slot resumes; the NUS gateway itself only at stage 4 | Stage 2 |

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
- **Failed startup validation in a mounted app fails the process**; **no
  redirects** from old root paths; `/health` is the host's, with no
  interactive sign-in (all v0.8 §3).
- **Identity** follows v0.8 §3; the points RRW's code turns on:
  - Cordware is the only Easy Auth parser; `users`, roles and audits
    stay RRW's (v0.8 §4). Fake roles key off Cordware's fake marker,
    never the literal email. Cordware refuses to start when
    `ALLOW_FAKE_AUTH` is on and `APP_ENV` is not `local`.
  - RRW reads `is_super_admin`, `is_super_admin_email` and
    `super_admin_configured` over Cordware's effective list and never
    parses `SUPER_ADMIN_EMAILS`; its any-admin fallback keys off
    `super_admin_configured`.
  - From C1, `effective_super_admin_emails()` reads Cordware's host-level
    fake state, and the fake super-admin resolves at every rung through
    C3 (sequence C1–C3).
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
| A | Dev deploy artifact and packaging | the dev workflow uploads `app/`, `alembic/`, `alembic.ini`, `requirements.txt`, `pyproject.toml`, `antenv/` and deploys on every push to `main`; `pyproject.toml:36` finds `app*` only; `testpaths = ["tests"]` (`:39`) | `.github/workflows/main_app-review-robin-web-dev.yml:56–62` |
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

Each sub-segment plan cuts its own rungs from sequence §5; this file
holds only the gates between them and the constraints a rung must carry.

1. **This rewrite**, prose only; it touches no `app/`, `tests/` or
   `cordware/` file.
2. **21A.** A2 moves the module-level app and all its consumers in one
   rung (sequence A2), with the dev artifact and package discovery
   carrying `cordware/`. Plan: `guide/segment_21A_cordware_foundations.md`.
3. **21B**, after 21A. Its allowlist only shrinks, rung by rung.
4. **21C**, alongside 21B. The C1–C3 rule in § Semantics holds at every
   rung.
5. **21D**, after 21A–21C close. The landing page lands scaffold-first;
   D2 is the author's live check (§ Definition of done).

## Definition of done

- Cordware alone and Cordware + RRW both run, and the import-boundary
  test passes (21A).
- Importing `app.main` builds nothing; no live start command names
  `app.main:app` but the NUS runbook's, which waits for stage 4 (21A).
- Under the `/reviewrobin` harness the leak check passes with no
  allowlist, `/.auth/*` excluded by rule (21B).
- The trusted-identity interface is tested on its own; Cordware
  refuses to start with `ALLOW_FAKE_AUTH` on and `APP_ENV` not `local`;
  the super-admin flag, predicate and fallback are tested with an empty
  and a non-empty list;
  the fake user keeps every role (21C).
- v0.8 §3's four behavior requirements hold before stage 3 starts (21D):
  a test under the mount with a non-backend `Host` shows every absolute
  URL and download carrying that host and `/reviewrobin`
  (requirement 4); the author has verified all four on localhost. The
  real-Easy-Auth check on the dev slot runs when it resumes (the
  dormant note at the top), before any NUS deploy. Only the NUS gateway's own
  path and host header wait for stage 4.
- v0.8 §8's stage 1–2 decisions are settled and recorded in v0.8
  (21A–21C).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 21` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

1. **Where do the sub-segment plans live?** In `guide/`, as
   `segment_21X_*.md`: the author opened 21A's there (2026-10-21; sequence
   §6.2). The settled contract still goes to `cordware/spec/`.
2. **The lifespan contract's shape** (v0.8 §8). Decided in 21A.
3. **The public host for absolute links** (invites, emails): a
   configured base or a forwarded host, per the gateway's host-header
   behavior (v8 report §8.1). Decided in 21B; proved at 21D by test.
4. **The trusted-identity interface** (v0.8 §8). Decided in 21C.
5. ~~The dev slot's `APP_ENV`~~ (v0.8 §8): set non-`local` when the slot
   resumes, step 1 of `docs/deployment_dev.md` "Resuming the dev slot"
   (author, 2026-10-21).
6. **Repo-wide tooling's path scope** once `cordware/` has code (v0.8
   §8): `tools/`, the doc gates, ruff, pytest paths and CI's required
   checks for `cordware/tests/`. Decided in 21A.
7. **Console logs reaching Log Analytics** (v0.8 §8): the author, in Azure.
8. **Should a service build URLs?** `services/validation.py`'s fix
   links could move to a view. The author rules in 21B.
9. **Browser tests under the mount:** a base-URL prefix, or a harness
   mounting RRW at `/`. Decided in 21D.

Answered, from the 2026-10-16 list: one Easy Auth boundary serves every
application (v8 report §4.1, §11.1); the path is `/reviewrobin`; the
gateway must keep the prefix (v0.8 §3), which NUS IT has yet to
configure (v8 report §8.1) and stage 4 checks.

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
- `docs/deployment_nus.md` — "no code change" retired (21D); its start command moves with stage 4's artifact.
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
68097709:guide/segment_21_domain_retrofit.md`. Written for RRW as its own
App Service, it split 21A base-path foundation, 21B sweep, 21C auth and
edge, 21D NUS cutover. `BASE_PATH` and `app_url()` became the mount's
`root_path`; the trusted-proxy allowlist and `PUBLIC_BASE_URL` became
Open question 3; old 21C became new 21C with no NUS IT gate; old 21D
became v0.8 stage 4, its audit (`74f57a71`) § Blast radius.
