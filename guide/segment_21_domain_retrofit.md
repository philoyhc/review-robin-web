# Segment 21 — Domain retrofit (RRW under `cordware.nus.edu.sg/reviewrobin`)

**Opened:** 2026-10-16 · **Theme:** RRW stops assuming its public root is `/` · **Related:** `docs/cordware_rrw_integration_spec.md`, `docs/nus_azure_status_cordware_addendum.md`, `docs/nus_azure_status.md`, `docs/deployment_nus.md`

This is the **outline** for the whole retrofit. The work lands as
sub-segments `21A`, `21B`, … each with its own
`guide/segment_21X_<slug>.md` plan opened when it starts. This file holds
the split, the cross-cutting decisions and the audit. It does not hold the
sub-segments' PR ladders.

## Opportunity

Production is moving to a shared host. RRW will be served at
`https://cordware.nus.edu.sg/reviewrobin`, not on a hostname of its own
(the addendum, §1). RRW was written for a root mount, and the integration
spec's §10 lists fourteen acceptance criteria it does not meet today. The
audit below finds:

- about 200 template links, form targets and image sources written as root paths;
- 198 root-path URLs built in Python, across 38 files;
- about 45 root paths in inline scripts;
- 22 template comparisons against `request.url.path`;
- four cookies (three set by the server, one family set by script) scoped to root paths;
- four links into Easy Auth's `/.auth/*`, which App Service serves at the host root;
- no trusted-proxy handling at all. Absolute invite links in emails are built from the request's own host header, so behind the gateway they could carry the `azurewebsites.net` backend name.

`docs/deployment_nus.md` line 103 still says "No code change is required
to change hosts". The addendum's §8 retires that claim.

## Decision

**One segment is not enough. Use an outline plus four sub-segments,** cut
where the gates differ:

| Sub-segment | What | Gate to start | Provable in CI? |
|---|---|---|---|
| **21A — Base-path foundation** | A `BASE_PATH` setting (default empty); an ASGI shim; one URL helper for Python, Jinja and inline JS; the *mechanisms* for trusted-proxy headers (an allowlist, empty by default) and a `PUBLIC_BASE_URL` for absolute links, both inert until set; a prefixed-mode test harness; a **leak ratchet** test. No visible change at root. | None. Can start now. | Yes |
| **21B — The sweep** | Every emitter routed through the helper, area by area (§ Blast radius), each PR shrinking the ratchet's allowlist; then the allowlist removed and the ratchet made a hard gate. | 21A merged | Yes |
| **21C — Auth and edge under the mount** | `/.auth/*` links and sign-out; Easy Auth's callback, return URL and session cookie on a shared host; the health probe path; the production values for 21A's proxy allowlist and `PUBLIC_BASE_URL`; proof in a non-production Azure slot (integration spec §14 step 5). | NUS IT decisions (Open questions 1–3) and a reachable Azure test slot | Partly: the app side yes, the Easy Auth side no |
| **21D — Cutover runbook and verification** | `docs/deployment_nus.md` and `docs/nus_azure_status.md` revised, with the addendum folded in; the addendum's twelve cutover checks as a runbook checklist; the cutover itself. | 21B and 21C closed; gateway listener and path map live | No: the author, on Azure |

21A and 21B are most of the code. They depend on nothing outside the
repository, so they run in parallel with the infrastructure workstream
(the addendum's §12 workstream B).

**One app-relative model, whichever way the gateway forwards.**
- Inside RRW every route, spec and test stays app-relative (`/operator/sessions/…`).
- A small ASGI shim in front of the app accepts the request path with or without `BASE_PATH`. It strips the prefix when it is present, and either way sets the ASGI `root_path` to `BASE_PATH`.
- Starlette's `url_for` and one helper (`app_url(path)`) then add the prefix on the way out.
- So the open question of whether the gateway **keeps or strips** `/reviewrobin` changes only gateway configuration and the probe path, not RRW's code.

**Rejected: mount the app under a fixed prefix (`Mount("/reviewrobin", app)`).** It hard-codes the keep-the-prefix answer before NUS IT has given it, and local development and the 6,000-test suite would have to move off `/`.

**Also rejected: fix each emitter as it breaks.** The integration spec's §11 rules this out explicitly. A shared-host leak fails quietly: the link resolves to the Cordware shell's 404, not to an error in RRW. So only a sweep checked by a test closes it.

## Semantics

- **Root mode is byte-identical.** With `BASE_PATH` empty, `app_url("/x")` returns `"/x"` and the shim does nothing. The existing suite is the regression proof: 763 root-path test requests and 465 root-path assertions across 120 files. Root-mode output is therefore never edited to suit prefix mode.
- **Prefix mode.**
  - `app_url("/x")` gives `"/reviewrobin/x"`. Redirect `Location`s, form actions, `fetch` targets, `src` attributes and cookie `Path`s all carry the prefix.
  - Path comparisons compare app-relative paths: `request.url.path` minus `root_path`. That covers active navigation, `return_to` allowlists and "not on this page" checks.
  - `return_to` values travel app-relative. A prefixed value arriving from outside is normalized once, at `app/web/return_to.py`.
- **Absolute URLs.** Emails and anything else rendered outside a request use `PUBLIC_BASE_URL` (scheme, host and `BASE_PATH`), not the request host. When it is unset they fall back to today's `request.url_for` behavior, so local development and the dev slot are unchanged.
- **`/health`** answers at both `/health` and `{BASE_PATH}/health`, without auth, in either gateway mode.
- **Bare and trailing-slash entry.** `{BASE_PATH}` and `{BASE_PATH}/` both reach the role-aware `/` redirect.
- **Starlette 1.6 `root_path` semantics** (whether `request.url.path` includes `root_path`, and what `url_for` returns under a stripped prefix) are pinned by tests in 21A's first rung. They are not assumed here.

## Judgment calls — decided

- Four sub-segments, not three. 21C waits on NUS IT and 21D waits on infrastructure, and folding either into 21B would leave a merged code segment unable to close (2026-10-16).
- The leak ratchet is a test that renders every route the suite already reaches in prefix mode and fails on any root-path URL. Its allowlist only shrinks. This is the repo's usual "derive the gate" pattern (`constitution.md` II), and it lets 21B land in small PRs without a flag day (2026-10-16).
- The literal `/reviewrobin` appears only in deployment configuration and docs, never in `app/`. This is the integration spec's §2.4 and §4.4 (2026-10-16).
- **Sign-in is identity only; permissions are each app's own** (author, 2026-10-16). Cordware's shared sign-in tells RRW who the person is; RRW alone decides what they may do. This is the integration spec's §2.1, and RRW's model today.
- 21A builds the proxy and absolute-URL mechanisms inert; 21C sets their production values once NUS IT says how the gateway forwards the host. This keeps 21A free of outside gates (Codex review of #3081, 2026-10-16).
- The Cordware landing app is out of scope. It is a separate codebase (addendum §6) (2026-10-16).

## Blast radius (measured)

Taken 2026-10-16 at `74f57a71`. "Root path" means a URL beginning `/operator`, `/me`, `/guide`, `/about`, `/auth`, `/static`, `/templates`, `/.auth` or `/health`. Route definitions are not counted; they stay app-relative.

| What | Count | Command / note |
|---|---|---|
| Template `href="/…"` | 94 in 37 files | `grep -rEo 'href="/[^"]*' app/web/templates \| wc -l` |
| Template `action="/…"` | 59 in 22 files | `grep -rEo 'action="/[^"]*' app/web/templates \| wc -l` |
| Template `formaction="/…"` | 9 | `grep -rEo 'formaction="/[^"]*' app/web/templates \| wc -l` |
| Template `src="/…"` (all `/static/guide/` screencaps) | 36 | `grep -rEo 'src="/[^"]*' app/web/templates \| wc -l` |
| Template `href`/`action` from a Python value (`"{{ … }}"`; the root path is built in Python) | 58 + 28 | `grep -rEo 'href="\{\{' …` / `'action="\{\{'` |
| Root-path literals in inline JS and Jinja string concatenation | 45 lines | quoted `/operator`, `/me`, `/guide`, `/about`, `/auth`, `/static`, `/.auth`, `/templates` or `/health` strings in `app/web/templates`, less the attribute hits above; includes 7 `fetch` calls and 6 `location` assignments |
| Template `request.url.path` uses (comparisons plus 13 self or `return_to` links) | 22 | `grep -rEn "request\.url\.path" app/web/templates \| wc -l` |
| Python root-path URL strings (docstrings and route decorators excluded) | 198 sites in 38 files (147 f-strings, 51 literals) | AST count over `app/`; the script is committed with 21A. Largest: `app/web/routes_operator/_instruments.py` 15, `app/web/routes_operator/_operations.py` 15, `app/web/breadcrumbs.py` 12, `app/web/routes_reviewer/_surface/_routes.py` 11 |
| …of which in `app/services/` (fix-link builders in `validation.py`) | 7 | A layering question for 21B: a service emitting URLs |
| Server cookies with a root `path` | 3 | `_operations.py:275` (`/operator/sessions`), `_sys_admin.py:81` (`/operator/sys-admin`), `:403` (`/operator/sys-admin/users`) |
| Script-set sort cookies (`_rrwCookiePath` in `base.html`) | 1 family | Paths `/me/sessions/N` and `/operator/sessions/N` |
| Links to Easy Auth `/.auth/*` | 4 (+1 JS check) | `base.html:5183`, `reviewer/_top_bar.html:50`, `me_debug.html:55`, `error_handlers.py:118`; `error.html:123` checks `pathname` |
| `request.url_for` (absolute invite links in emails) | 5 call sites | `grep -rn "url_for(\"reviewer_invite\"" app` |
| Trusted-proxy or `root_path` configuration | 0 | `grep -rn "root_path\|ProxyHeaders\|forwarded_allow_ips" app` |
| Tests: root-path requests / root-path assertions | 763 / 465 lines in 120 files | Unchanged by design (root mode byte-identical) |
| Browser tests: `page.goto` | 86 | A prefixed-mode subset is added in 21A/21B |
| Specs with root cookie paths | 2 | `spec/settings_inventory.md`, `spec/sort_by_reviewee.md` |

## PR ladder

At this level the ladder is the sub-segment sequence. Each sub-segment's
own plan carries its PRs.

1. **This outline**, prose only. Must not touch `app/` or `tests/`.
2. **21A plan**, then its build. The scaffold-first rung is the setting, the shim, the helper and the ratchet with a full allowlist. Nothing is converted yet.
3. **21B plan**, then the sweep by area: chrome and `base.html`; operator Setup pages; Operations pages; Instruments; Session Home and lobby; Sys Admin; reviewer and participant surfaces; Guide, About and static files; Python emitters and services; cookies and `return_to`. Then the allowlist is deleted.
4. **21C plan**, opened once Open questions 1–3 are answered. The app side lands in CI; the Azure proof is the author's.
5. **21D plan**: docs, the runbook checklist, the cutover.

## Definition of done

- `BASE_PATH=/reviewrobin` runs the full suite's prefixed-mode harness green, and the leak ratchet passes with no allowlist (21B).
- `BASE_PATH` unset leaves the existing suite green and unchanged (21A, 21B).
- Each of the integration spec's §10 criteria 1–14 is checked against a named test or a recorded Azure check (21A–21D).
- `docs/deployment_nus.md` no longer says hosts change without code. `docs/nus_azure_status.md` has the addendum folded in, and the addendum is retired to `docs/archive/` (21D).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 21` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

1. **Does the gateway keep or strip `/reviewrobin`?** NUS IT decides, with the gateway design. RRW's code supports both (Decision), so this sets only the gateway rewrite and the probe path. 21C cannot finish without it.
2. **How one sign-in reaches every app on the shared host.** NUS IT and EUC decide, with a 21C spike. The principle is already ruled (Judgment calls): sign-in establishes identity only, so a person signs in once for Cordware. What remains is the mechanism.
   - App Service serves `/.auth/*` at the host root, and its `AppServiceAuthSession` cookie is host-wide and readable only by the App Service that issued it. So per-app Easy Auth behind one host may mean the apps clobber each other's session rather than share one. This is unverified, which is why it is a spike.
   - The candidates are a gateway rewrite of `{BASE_PATH}/.auth/*` per app, one shared registration with per-app sessions, or one identity layer in front that hands each app the same identity headers.
   - Whatever is chosen, RRW keeps reading identity from headers and deciding permissions itself. App-level OIDC in place of Easy Auth would break the project convention of no Microsoft authentication in app code, so it needs the author's explicit say.
3. **Does the gateway pass the public host in `X-Forwarded-Host` or `Host`?** NUS IT decides. 21A builds both mechanisms without needing the answer; the answer sets which one production uses and its values, in 21C.
4. **Is `/reviewrobin` the final path?** The author and NUS IT decide. Nothing in `app/` depends on it (Judgment calls).
5. **Should a service build URLs at all?** The author rules in 21B. `services/validation.py`'s fix links could move to a view.

## Out of scope

- **The Cordware landing app and its discovery registry.** A separate codebase (addendum §6; integration spec §7).
- **Application Gateway, DNS and TLS configuration.** NUS IT and the project's infrastructure workstream (addendum §12 B). 21D only verifies them.
- **The runner VM capacity blocker.** Unchanged; tracked in `docs/nus_azure_status.md`.
- **Segment 20's administrator guide.** It documents the deployment once it exists, and stays gated where it is.

## Doc impact

Provisional at outline level. Each sub-segment plan takes over its bullets.

- `spec/architecture.md` — a "Public base path and proxy" section: the app-relative model, `BASE_PATH`, the shim, the helper, and trusted-proxy handling (21A).
- `spec/settings_inventory.md` — `BASE_PATH` and `PUBLIC_BASE_URL` rows; cookie `path` cells relative to the base path (21A, 21B).
- `spec/sort_by_reviewee.md` — sort-cookie path under the base path (21B).
- `docs/local_setup.md` — running locally with a `BASE_PATH` to reproduce production (21A).
- `docs/security_posture.md` — trusted-proxy posture and Easy Auth under a shared host (21C).
- `docs/deployment_nus.md` — remove "no code change"; the cutover checklist (21D).
- `docs/nus_azure_status.md` — fold in the Cordware addendum (21D).
- `CLAUDE.md` — the convention "never write a root-path URL; use the helper", enforced by the ratchet (21B). `AGENTS.md` twinned.
