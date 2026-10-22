# Segment 21D — Prefix flip

**Opened:** 2026-10-21 · **Outline:** `guide/segment_21_domain_retrofit.md`
(sub-segment 21D) · **Strategy:** `docs/cordware_repository_strategy_v0.8.md`
§3 "Behavior under the mount" · **Sequence:**
`docs/archive/cordware_implementation_sequence.md` §5 D1–D2 · **Hold:** lifted for
21D by the author at 21C's close (2026-10-21).

This is the last step of v0.8's stage 2, and the only one that changes
URLs. RRW moves from `/` to `/reviewrobin` and Cordware's landing page
takes `/`. 21A–21C made the move a one-line change in `REGISTRY`; this
plan adds the landing page and the tests that pin v0.8 §3's four
behavior requirements. It also settles the two questions the outline
carried here: the public host for absolute links, and how browser tests
run under the mount.

## Opportunity

- **RRW still answers at `/`** (`cordware/main.py` `REGISTRY`). v0.8 §3
  puts it at `/reviewrobin` so a second application can mount beside
  it, and stage 3 (Residential Apps) cannot start until it moves.
- **`/` has no host page.** v0.8 §1 gives Cordware a landing page that
  lists the mounted applications. None exists: with `CORDWARE_APPS`
  empty, `/` answers 404.
- **Two of the four behavior requirements have no test under the
  mount.** 21B's crawl proves every emitted path carries the prefix, but:
  - no test shows an absolute URL (an invitation link) carrying the
    request's host and `/reviewrobin` (requirement 4);
  - no test shows RRW's error handlers answering under the mount
    (requirement 3).
- **The browser suite runs RRW at `/`** (`tests/browser/conftest.py`).
  After the flip, it would either stop matching what runs or stop
  running.

## Decision

- **The flip is one line:** `REGISTRY["reviewrobin"].path` becomes
  `"/reviewrobin"`. It stays a constant, so no configuration can move it.
  The host registers `/` and `/health` ahead of every mount.
- **The landing page is the host's,** in `cordware/web/`:
  - one server-rendered page at `/`, listing each mounted application
    with a link to its path and its display name;
  - **with exactly one application mounted, `/` redirects to its path
    instead** (302), so a lone RRW opens at `/reviewrobin/`; the page
    shows with none mounted, or with two or more (Open question 3,
    author);
  - `AppEntry` gains a `title`;
  - a host-level `Sign out` (`/.auth/logout`);
  - no identity check and no roles: each application gates its own
    routes (v0.8 §1).
  
  It lands scaffold-first (`CLAUDE.md` "Consequential UI lands
  scaffold-first"): D1 serves it while RRW is still at `/`, at `/` only
  when no application is mounted there.
- **Absolute URLs use the request's own host** (Open question 1,
  author). Every one is already `request.url_for(...)` (5 sites),
  which carries `root_path`. No `PUBLIC_BASE_URL` is added. The gateway's
  host header is stage 4's to check.
- **Browser tests run under the real mount** (Open question 2,
  author):
  - the harness's base URL gains `/reviewrobin`;
  - every navigation goes through one `app_url(path)` helper: the
    `page` fixture's `goto`, every raw `browser.new_context(...)` page,
    every in-page `window.location` navigation or path assertion, and
    every URL assertion (Codex, #3215);
  - a guard test fails on a root-path literal passed to `goto` or
    `window.location` in `tests/browser/`, so a new test cannot slip
    back to `/`.

**Rejected:**
- *A `PUBLIC_BASE_URL` setting:* it can drift from the gateway, and
  nothing yet needs a URL built outside a request.
- *A browser harness that mounts RRW at `/`:* the browser tests would
  stop exercising client-built URLs under the prefix, which is the one
  thing the static checks cannot see at runtime.
- *Redirects from the old root paths:* a v0.8 non-goal. Nothing is in
  the wild.

## Semantics

- **`/reviewrobin` without a slash** redirects (307, Starlette's slash
  redirect, measured) to `/reviewrobin/`, which
  is RRW's role-aware root (`app/main.py` `root`). Old root paths such
  as `/operator/sessions` answer the host's 404.
- **`/.auth/*` stays host-level.** `url()` already passes it through
  unprefixed (`app/web/urls.py`). Its 6 references need no change; a
  test pins them unprefixed under the mount.
- **Deep links through sign-in (requirement 1)** are Easy Auth's: the
  platform redirects an unauthenticated request and returns it to the
  original path. Nothing in RRW builds that redirect, so the live check
  is the dev slot's when it resumes.
- **Probes (requirement 2):** `/health` is the host's;
  `/reviewrobin/health` is RRW's. Easy Auth's exclusion list gains the
  second when the slot resumes (`docs/deployment_dev.md`).
- **Request handling (requirement 3):** RRW's error handlers, middleware
  and app-wide dependencies run inside the mounted application. A test
  shows a 404, a 403 and a 422 rendered by RRW under the mount.
- **Absolute URLs (requirement 4):**
  - Invitation and reminder links come from the request's scheme, host
    and `root_path`.
  - A test with `Host: reviews.example.edu` shows an invite link of
    `http://reviews.example.edu/reviewrobin/invite/…`, never the
    App Service name.
  - A scheduled send outside a request has no URL builder and sends no
    invites, as today (`app/services/scheduled_events/__init__.py`).
- **TestClient tests stay at `/`.** `rrw_app` builds RRW alone, so their
  3,422 calls are unchanged. 21B's crawl remains the mount's
  route-complete gate.

## Judgment calls — decided

- D1 adds the landing page without touching `/`'s behavior while RRW is
  there, so it is behavior-neutral and reviewable alone.
- `title` goes on `AppEntry` rather than into a separate map: one entry
  per application stays the registry's shape.
- The landing page is a template in `cordware/web/templates/`, with its
  own small inline style. RRW's `base.html` is RRW's, and Cordware
  imports no application.

## Blast radius (measured)

Taken 2026-10-21 at `d3420be9`.

| What | Count | Command |
|---|---|---|
| Registry entry | 1 line, `cordware/main.py` | `grep -n 'path="/"' cordware/main.py` |
| Host tests assuming RRW at `/` | 3 in `cordware/tests/test_host.py` (at root, shadows nothing, registry) | `grep -n "def test" cordware/tests/test_host.py` |
| `/.auth/` references | 6: `base.html`, `reviewer/_top_bar.html`, `me_debug.html`, `error.html` ×2, `error_handlers.py` | `grep -rn "/\.auth" app --include=*.py --include=*.html` |
| Absolute-URL builders | 5 `request.url_for("reviewer_invite", …)`: `_shared.py` ×1, `_operations.py` ×4 | `grep -rn 'url_for("reviewer_invite"' app` |
| Browser suite | 49 files; 99 `page.goto`, 31 URL assertions, 11 `live_server.base_url` uses, 4 `new_context(` (3 in tests, 1 in `conftest.py`), 4 `window.location` in 2 files | `grep -rn "page.goto(" tests/browser \| wc -l`; `grep -rn "to_have_url\|page.url\|wait_for_url" tests/browser`; `grep -rn "new_context(\|window.location" tests/browser` |
| Docs naming the local URL | 7 lines in `README.md`, `CLAUDE.md`, `docs/local_setup.md`, `docs/security_posture.md` | `grep -rn "127.0.0.1:8000" README.md CLAUDE.md docs/*.md` |
| TestClient calls at root | 3,422, unchanged by design | outline § Blast radius |

## Status

**Closed 2026-10-22.** PRs **#3215** (plan), **#3216** (D1), **#3217**
(D2), **#3218** (D3) and the close; the author checked all four
requirements on localhost. Item base for the cumulative read: `7c2512f9`.

**Intended vs done:** as laddered, with these divergences.
- **The harness prefixes at each call** through `app_url`
  (`tests/browser/conftest.py`). Each context's `base_url` stays the
  origin, not the Decision's prefixed base URL, because Playwright
  resolves a leading `/` against the origin. The `api` client's base URL
  carries the mount. `page.url` `endswith` / `in` checks and `**` globs
  stay, since they hold under any prefix.
- **Two sites outside the measured count** read the page's pathname
  and moved too: Home's scroll-seat `sessionStorage` key and the
  sort-cookie paths.
- **Requirement 4's link** is `…/reviewrobin/me/invite/…`: the route is
  `/me/invite/{token}`, where Semantics wrote `/reviewrobin/invite/…`.
- **The 403 under the mount** is a Sys Admin page refusing a plain
  operator. A non-operator on an operator page is redirected to `/me`,
  not refused.
- **The Easy Auth exclusion of `/reviewrobin/health`** is its own
  resumption step in `docs/deployment_dev.md`. The slot's invite check
  says what it cannot show: the gateway's public name is stage 4's.

**Decisions confirmed at build:** `AppEntry.title` defaults to empty, and
the page then shows the registry name; the landing redirect and links
keep the host's `root_path`. The guard is
`tests/unit/test_browser_app_urls.py`. It failed 35 files on the
pre-flip tree, and its self-tests pin each form it refuses and passes.

**Reads:**
- **`diff-reviewer`, one cumulative read** at D3, from `7c2512f9`: no
  high findings; four medium and five low, all acted on in D3.
  - Guard gaps, including negative URL assertions that would pass
    vacuously.
  - Stale Easy Auth and verification steps in the two deployment
    runbooks.
  - The dev-slot invite check's limit.
  - `/.auth/` pinned on every emitter.
  - The suite's `MOUNT` tied to `REGISTRY`.
  - Two nits.
- **Codex** found two further guard gaps (#3217, #3218), both fixed.
- **`spec-writer`** wrote the close (`spec/architecture.md`,
  `cordware/spec/host.md`) and found three more specs naming `/` as the
  mount root, now in `Doc impact`. Its one flag kept a requirement:
  host-logging events 4 and 5 were never built, and are queued
  (`guide/archive/segment_21_domain_retrofit.md` § Status).

**Waiting:** the real-Easy-Auth check on the dev slot, step 5 of
`docs/deployment_dev.md` "Resuming the dev slot"; the gateway's path
forwarding and host header, at stage 4.

## PR ladder

1. **D0, this plan**, prose only.
2. **D1, the landing page scaffold.**
   - Adds `cordware/web/` (page and template) and `AppEntry.title`. The
     page is served at `/` only when no application is mounted there,
     so it shows today with `CORDWARE_APPS` empty.
   - Tests: the page lists exactly the mounted set, with links and
     titles; the host alone serves it; one application not at `/`
     redirects `/` to its path; RRW at `/` still owns `/`.
   - **Must not change** any response with RRW mounted.
3. **D2, the flip.**
   - `REGISTRY` path `/reviewrobin`; with RRW alone, `/` redirects to
     `/reviewrobin/`.
   - Host tests move to the mount. The browser harness moves to the
     mount through `app_url`, covering raw contexts and `window.location`
     too, with the guard test and every browser test passing.
   - `docs/deployment_nus.md` retires its "no code change" line.
   - Docs that name the local URL say `/reviewrobin/`.
   - The `.env.example` and start commands are unchanged.
4. **D3, the behavior requirements pinned.**
   - Tests under the mount:
     - requirement 3: RRW's own 404, 403 and 422;
     - requirement 4: an invite link on a non-backend `Host`;
     - `/.auth/*` unprefixed;
     - `/reviewrobin` redirects to `/reviewrobin/`;
     - both health probes.
   - `docs/deployment_dev.md`'s resumption steps gain
     `/reviewrobin/health` on the Easy Auth exclusion list and the
     four-requirement live check.
   - This is the item's last build rung: the cumulative `diff-reviewer`
     read runs here, from D1's base.
5. **Close:** the author's localhost check of all four requirements, then
   the specs (§ Doc impact), v0.8 §8, the outline's close, archive.

## Definition of done

- With `CORDWARE_APPS` empty, `/` serves the landing page and `/health`
  answers; with RRW alone, `/` redirects to `/reviewrobin/`; with two
  stub applications, `/` lists both (D1, D2).
- `REGISTRY["reviewrobin"].path == "/reviewrobin"`, pinned by a host
  test (D2).
- The full browser suite passes under the mount (D2).
- A test under the mount shows an invite link carrying the request's
  host and `/reviewrobin`, and RRW's own 404, 403 and 422 pages (D3).
- Every local URL that `grep -rn "127.0.0.1:8000" README.md CLAUDE.md docs/*.md`
  finds is a `/reviewrobin/` form (D2), but for the two hits that name
  the bare origin: `README.md`'s redirect source and
  `docs/security_posture.md`'s single-origin note.
- The author has checked all four requirements on localhost (close). The
  real-Easy-Auth check waits for the dev slot (outline § Definition of
  done).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 21D` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

1. ~~The public host for absolute links~~: the request's own host, no
   configured base (author, 2026-10-21, on the recommendation).
2. ~~Browser tests under the mount~~: the real mount (author,
   2026-10-21, on the recommendation), through `app_url` at each call
   (Status).
3. ~~The landing page with one application~~: `/` redirects to that
   application's path; the page lists applications when none or two or
   more are mounted (author, 2026-10-21, overruling the recommendation
   to list it).

## Out of scope

- **The dev slot's live check** under real Easy Auth: when it resumes
  (`docs/deployment_dev.md` "Resuming the dev slot").
- **The NUS gateway's path forwarding and host header:** stage 4.
- **Repointing RRW's 77 identity importers:** the re-export stays (21C).
- **Residential Apps:** stage 3, after this closes.

## Doc impact

- `spec/architecture.md` — RRW served at `/reviewrobin`; old root paths answer the host's 404; absolute URLs from the request's host (close).
- `spec/settings_inventory.md` — the session-list sort cookies' path is the mount root, `/reviewrobin/` (close; found by `spec-writer`).
- `spec/sort_by_reviewee.md` — the same cookie paths (close; found by `spec-writer`).
- `spec/operator_ui_concept.md` — "Entry & landing": the browser root is `/reviewrobin/`, which the host's `/` redirects to (close; found by `spec-writer`).
- `docs/local_setup.md` — the local URL is `http://127.0.0.1:8000/reviewrobin/`; `/` redirects there while RRW is the only application (D2).
- `docs/deployment_dev.md` — `/reviewrobin/health` excluded from Easy Auth; the four-requirement live check (D3).
- `docs/security_posture.md` — `/health` and `/reviewrobin/health` as the unauthenticated probes; sign-out stays host-level (close).
- `docs/cordware_repository_strategy_v0.8.md` — §8: the public host and the browser harness settled (close).
- `README.md` — the local URL (D2).
- `.env.example` — an empty `CORDWARE_APPS` serves the landing page and `/health` (D3).
- `CLAUDE.md` — the local URL the author checks at (D2). `AGENTS.md` twinned.
- `docs/deployment_nus.md` — the "no code change" line retired; its start command moves with stage 4's artifact (D2; carried from the outline).
- `docs/cordware_implementation_sequence.md` — retired to `docs/archive/` at the close; the sub-segment plans carry its ladder (carried from the outline). <!-- cites: docs/cordware_implementation_sequence.md -->
- `cordware/spec/host.md` — the landing page and the one-application redirect, `AppEntry.title`, RRW at `/reviewrobin` (close); checked by hand.
