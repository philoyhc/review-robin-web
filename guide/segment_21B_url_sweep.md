# Segment 21B — the URL sweep (RRW emits mount-aware URLs, still at `/`)

**Opened:** 2026-10-21 · **Parent:** `guide/segment_21_domain_retrofit.md`
(the outline; its split, semantics and gates bind here) · **Source:**
`docs/cordware_repository_strategy_v0.8.md` §3 "Mounting" and
`docs/cordware_implementation_sequence.md` §5, workstream B · **Theme:**
every URL RRW emits carries the mount's prefix, while RRW stays mounted
at `/`

The author lifted segment 21's hold for 21B at 21A's close (2026-10-21).
21C may run alongside it; 21D waits for both.

## Opportunity

Under a mount, RRW's emitted URLs lose the prefix, and its path checks
stop matching. Both were probed on Starlette 1.6.0 with RRW-shaped
routes mounted at `/reviewrobin`. Inside the mount, `root_path` is
`/reviewrobin`, `request.url.path` *includes* the prefix,
`request.app.url_path_for(...)` omits it, and `request.url_for(...)`
returns an absolute URL that includes it. So:

- every literal root path RRW writes is wrong under the mount: 192
  template attributes, 47 other template strings, and 76 of 124
  `RedirectResponse`s (§ Blast radius). A redirect built from a
  variable (`return_to` values, `ReturnTarget.url`) is wrong too;
- every comparison against `request.url.path`, 21 in templates and 4 in
  `error_handlers.py`, fails. `return_to=request.url.path` would carry
  the prefix into a value that is meant to stay app-relative;
- the three server cookies and the script's `_rrwCookiePath` scope to
  root paths.

The 5 `url_for` calls (absolute invite links) already work under the
mount.

## Decision

**App-relative values travel; the prefix is added once, at emission.**
Routes, views, services, breadcrumbs and `return_to` keep building
app-relative strings (`/operator/sessions/…`), as the outline requires
(§ Semantics, "App-relative inside RRW"). Four emission points add
`root_path`:

- **Templates.** A `url(path)` global prefixes app-relative paths and
  passes `#…`, `?…`, `mailto:` and absolute URLs through unchanged. It is
  used for every `href`, `action`, `formaction` and `src`, and for every
  root string in an inline script.
- **Redirects.** `redirect(request, url, status_code=307, headers=None)`, with
  `RedirectResponse`'s own parameters and defaults, in
  `app/web/urls.py` is the only place that constructs a
  `RedirectResponse`.
- **Cookies.** `cookie_path(request, path)` supplies every `set_cookie`
  `path=`. The script reads its root from one `data-` attribute on
  `<body>`.
- **Comparisons.** `app_path(request)` is the request path without
  `root_path`. Templates read it as the `here()` global, so nothing else
  reads `request.url.path`.

At `/`, `root_path` is empty, so every helper returns today's string, and
the existing suite is the regression proof.

**Rejected: named-route generation everywhere** (`url_for` /
`url_path_for` at all ~500 sites). It gives the same output under a mount
but means rewriting every literal to a route name and its parameters, on
FastAPI's function-name route names, some of which are generic. It still
needs `root_path` added to `url_path_for`, and `request.url_for` is
absolute, which puts the request's host into every link (v0.8 §3,
requirement 4). The prefix is the only thing a mount changes, so the
sweep changes only that.

**Rejected: a dynamic crawl as the only gate.** Rendering GET pages
under the mount can't reach the 124 redirects, which mostly follow a
POST, nor pages a fixture doesn't seed. So the gate is **static rules
over the source**, which are complete by construction, with a **shrinking
per-file allowlist**. A dynamic crawl under the mount backs them up and
proves that the helpers prefix (§ Semantics).

## Semantics

- **`url(path)`.** `""` or `None` renders `""`. A value starting with a
  single `/` gains `root_path`. `//host…`, `scheme:…`, `#…` and `?…` pass
  through unchanged. A value already under `root_path` is a bug and is
  *not* deduplicated: the leak test is what catches it. `/.auth/*` is the
  host's (v0.8 §3), so `url()` passes it through and 21D fixes its return
  paths.
- **`app_path(request)`** is `request.url.path` with a leading
  `root_path` removed, so it is equal to the path at `/`. Query strings
  are never included; callers that need one add it explicitly, as today.
- **`return_to`** values are app-relative going in and coming out. Pages
  put `here()` (plus the query, where they do today) into `return_to`.
  `app/web/return_to.py` is unchanged apart from receiving app-relative
  input.
- **Redirect status codes, headers and query strings are unchanged.**
  `redirect()` takes the same arguments a call site passes today,
  `url=` and `headers=` included (`_instruments.py` sends
  `X-FieldKey-Error`), so each call site moves over unchanged.
- **Cookies.** A cookie's `Path` is `root_path` + today's path. Under the
  mount, cookies set before the flip don't match. 21D accepts that (no
  old-path compatibility, v0.8 §3).
- **Absolute links** (`request.url_for("reviewer_invite")`) are left
  alone. Their host is Open question 1.
- **The static rules** (the leak test), each with a per-file allowlist
  of counts that may only fall:
  - **T1.** In templates, a quoted root literal is allowed only inside a
    call to `url(`, `is_here(`, `here_in(` or `here_under(`.
  - **T2.** Every `{{ … }}` value of `href`, `action`, `formaction` or
    `src` passes through `url(`.
  - **P1.** `RedirectResponse(` is called only in `app/web/urls.py`.
  - **P2.** Every `set_cookie` passes `path=cookie_path(...)`.
  - **P3.** `request.url.path` appears only in `app/web/urls.py`.

  "Root literal" means a string starting with one of RRW's top-level
  segments, which are read from `rrw_app().routes` rather than
  hardcoded, so a new top-level route is covered with no edit.
- **The dynamic crawl** runs RRW mounted at `/reviewrobin` through
  `cordware.main.create_app` with a registry override. It requests a
  seeded page set and asserts that every emitted `href`, `action`,
  `formaction`, `src`, `Location` and cookie `Path` is under
  `/reviewrobin`, or is external, a fragment, `mailto:` or `/.auth/*`.
  Its page set grows as each area is swept, and at the last rung it covers
  every parameter-fillable GET HTML route, enumerated from the router.

## Judgment calls — decided

- `app/web/urls.py` sits in the web layer. A service never needs it
  because it never emits URLs, only app-relative strings (Open
  question 2).
- `url()` is a Jinja global, not a filter: `url("/operator/…")` reads
  better than a filter on a literal, and T1 can find it.
- `is_here`, `here_in` and `here_under` replace raw comparisons. A
  literal as a helper argument is checkable; a literal after `!=` is not.
- The allowlist is exact, not a ceiling. A rung that removes leaks must
  lower its counts in the same PR, so the file always states what's left.
- The harness reuses the cached `tests/_rrw_app.py` instance as the
  mounted factory, so the suite's `dependency_overrides` carry into the
  mount.
- Browser tests stay on RRW at `/` until 21D (outline Open question 9).

## Blast radius (measured)

Taken 2026-10-21 at `42936344`, `ROOT` as in the outline's § Blast radius.

| What | Count | Command / note |
|---|---|---|
| Template `href`/`action`/`formaction`/`src="/` | 95 / 50 / 9 / 38 (39, 20, 3, 1 files; all 38 `src` in `guide.html`) | `grep -rnoE '(^\|[^a-z])href="/' app/web/templates \| wc -l`, per attribute |
| Template attributes built in Jinja (`="{{`) | 58 href, 28 action, 3 formaction | same, with `\{\{` |
| Other `ROOT` strings in templates | 47 lines in 16 files | `grep -rnE "[\"'\`]/(operator\|me\|guide\|about\|auth\|static\|health\|sessions\|\.auth\|templates\|invite)" app/web/templates`, less attribute hits |
| `fetch(` in templates | 7 | `grep -rnE '\bfetch\(' app/web/templates` |
| `request.url.path` | 21 in 9 templates; 4 in `app/web/error_handlers.py` | `grep -rnE 'request\.url\.path' app` |
| `RedirectResponse(` | 124 in 23 files; 76 with a `ROOT` target, in 21 files (ast) | `grep -rn 'RedirectResponse(' app --include=*.py`; ast scan in scratch |
| `ROOT` code lines in Python | 195 in 37 files (ast, decorators and docstrings dropped); top `_instruments.py` 15, `_operations.py` 15, `breadcrumbs.py` 12 | same ast scan |
| Server cookies | 3: `_operations.py:277`, `_sys_admin.py:84`, `:402`; script `_rrwCookiePath` in `base.html` | `grep -rnE 'set_cookie\(' app` |
| `url_for` | 6 lines, all `reviewer_invite` | `grep -rnE '\burl_for\(' app` |
| `/.auth` | 6, left to 21D | `grep -rnE '/\.auth' app` |

## Status

- **2026-10-21, B1 (#3200).** The allowlist keys each leak by rule, file
  and the leaking source itself, whitespace collapsed, and lives in
  `tests/unit/url_leaks_allowlist.json`. It is not a per-file count. Codex
  found that a count lets a rung fix one leak and add another in the same
  file unseen. The crawl's checker is proved on probe pages, and its first
  RRW pages come with B2. The cumulative read's base is `fdcfee36`.
- **2026-10-21, B3: `url()` is idempotent under a mount**, departing from
  § Semantics ("not deduplicated"). Templates `{% set %}` app-relative
  values and pass them to the partials that emit them, so wrapping at
  both ends is the only way the static rules stay mechanical. A value
  already under `root_path` comes back unchanged. `return_to` values still
  travel app-relative (`here()`), which B3's own read checks. The crawl
  takes `cookies=False` on Validate and the sys-admin users page until B6
  scopes their cookies.
- **2026-10-21, B5.** Every route that redirects, or calls a helper that
  does, takes `request: Request` as its first parameter, and so do the
  helpers (`_redirect_keeping_selection`, `_instruments_redirect`,
  `dismiss_held_upload`, `_users_redirect`, `_handle_toggle`). The rewrite
  was mechanical, driven by the AST. Rejected: middleware that prefixes a
  `Location` header after the fact. It would touch less code, but it hides
  where a redirect is built, and the plan's `redirect()` keeps it visible.
- **2026-10-21, B6.** Script strings are written `{{ url('/…') | tojson }}`,
  rendered server-side, not read from a `data-` attribute at runtime, so
  the static rules see them as `url()` calls. The allowlist is empty.
- **2026-10-21, cumulative read (1, `diff-reviewer` on `fdcfee36..` B6).**
  It confirmed that nothing at `/` changes and that `return_to` stays
  app-relative. It found:
  - two script values on the sys-admin users page built from a Python
    URL with no `url()`. Both are fixed. The static rules cannot see such
    a value, so the crawl's checker now also scans inline-script strings
    for a root path;
  - error-handler log lines now record the app-relative path. This is
    kept by decision: a log line names the route, not the mount;
  - a no-op `url()` wrap on an already-prefixed value. It is harmless,
    since `url()` is idempotent;
  - "route-aware generation" wording in the v0.8 strategy and the
    implementation sequence. It is reconciled at close.

## PR ladder

1. **B0, this plan**, prose only.
2. **B1, the helpers and the gates.** Adds `app/web/urls.py` (`url_path`,
   `app_path`, `redirect`, `cookie_path`), the Jinja globals (`url`,
   `here()`, `is_here`, `here_in`, `here_under`), the `/reviewrobin`
   harness, tests that pin § Opportunity's Starlette facts at `/` and
   under the mount, the static leak test with its allowlist at today's
   counts, and the crawl's checker, proved on probe pages. **Must not change a template,
   a route or an emitted string.** Record `main`'s SHA as the cumulative
   read's base.
3. **B2, the chrome:** `base.html`, `_top_bar.html`, the nav partials,
   `error.html`, `error_handlers.py` and `breadcrumbs.py`. These are
   every page's shared links and its `request.url.path` comparisons.
4. **B3, operator templates**, setup and session pages. Split into two
   PRs if the diff passes ~40 files.
5. **B4, the participant surfaces:** reviewer and participant templates,
   plus `guide.html` and `about.html`.
6. **B5, redirects:** all 124 `RedirectResponse`s through `redirect()`,
   one routing package per PR if needed.
7. **B6, cookies and scripts:** the three cookies, `_rrwCookiePath`, the
   `fetch` targets and the other script strings. This is the last build
   rung, and the cumulative `diff-reviewer` read runs here from B1's base.
8. **B7, the gate goes hard**, prose plus one test edit: the allowlist is
   removed and the crawl covers every fillable GET route. Specs at close
   (§ Doc impact).

Each sweep rung lowers the allowlist for the files it touches, and must
not change a route, a status code or a string at `/`.

## Definition of done

- At `/`, every helper returns its input path unchanged, pinned by test
  (B1).
- Under the `/reviewrobin` harness, tests pin that `root_path` is
  `/reviewrobin`, that `request.url.path` keeps the prefix and
  `app_path()` drops it, and that `url_for` is absolute with the prefix
  (B1).
- The static leak test's allowlist is empty, and the test has no
  allowlist parameter left (B7).
- The crawl covers every GET HTML route whose parameters a seeded
  session fills; a route it skips is named with its reason (B7).
- `git grep -n 'RedirectResponse(' app` finds only `app/web/urls.py`
  (B5).
- The full suite passes on SQLite and Postgres with no test's request
  path or expected `Location` changed (B1–B7).
- On localhost, the author has clicked through the operator and
  participant surfaces at `/` and found no change (close).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 21B` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

1. **The public host for absolute links** (outline Open question 3). The
   recommendation is the request's own host: no configured base URL, with
   the server trusting the gateway's forwarded host. That makes 21D's
   requirement-4 test a non-backend `Host` header, and the gateway's
   host-header behavior an NUS IT item at stage 4. The rejected
   alternative is a `PUBLIC_BASE_URL` setting, a second source of truth
   for the host that can drift from the gateway. 21B emits no absolute
   URL of its own, so this binds at 21D. The author decides.
2. **Should a service build URLs?** (outline Open question 8). The
   recommendation is yes, as app-relative strings:
   `services/validation.py`'s fix links stay where they are, and
   templates add the prefix with `url()`. Moving them to a view would buy
   nothing under this design. The author decides; B3 proceeds on the
   recommendation unless the author rules otherwise.

## Out of scope

- **The prefix flip**, `/.auth/*` return paths, the landing page and
  browser tests under the mount: 21D.
- **Identity:** 21C.
- **Old-path cookie compatibility and redirects from root paths:** none,
  per v0.8 §3.
- **Renaming routes or adopting route names:** rejected above.

## Doc impact

- `spec/architecture.md` — the emission rule: app-relative values, `url()` / `redirect()` / `cookie_path()` / `app_path()` at emission, and the leak test (close).
- `spec/settings_inventory.md` — cookie paths under the mount, in browser-local UI state (close).
- `spec/sort_by_reviewee.md` — the sort cookie's path takes the mount root (close; the code lands in B6).
- `CLAUDE.md` — "never write a root-path URL": templates use `url()`, routes use `redirect()` (B7). `AGENTS.md` twinned.
- `cordware/spec/host.md` — the `/reviewrobin` test harness, and the host's part in `root_path` (close); checked by hand.
