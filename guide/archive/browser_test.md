# Browser tests — the hand checks, made repeatable

**Opened:** 2026-10-01 · **Theme:** committed browser tests that run in CI
on every PR, so a builder sequence the author has checked stays checked ·
**Related:** `guide/post_azure_todo_checklist.md` items 5 and 6 (the rows
these tests come from), `guide/codebase_assessment_30sep.md` §5 and §8
move 1 (the case for it).

A standalone plan rather than a `segment_*.md`, at the author's naming.
`tools/close_check.py` reads segment ids, so this plan closes by its own
definition of done rather than by that tool.

## Opportunity

The author checks every change in a browser against a local run. Nothing
repeats those checks. The Instruments builder is client-side staging
before one save, in one inline script inside
`app/web/templates/operator/instruments_index.html` (7,202 lines). The
suite proves the posted payload and that the script parses, not that a
click sequence produces it. So an edit to that script can break a sequence
the author already approved, and only the next hand check would notice.

Evidence the class is real: headless Chromium, driven by hand during 19T,
found three defects on main in Item 1 alone. Of thirty fix commits counted
by the 2026-09-04 audit, fifteen were browser-only
(`rrw_sdd_in_practice.md` §6.6). Every one of those Chromium drives was a
throwaway script: 151 of them in one session's scratchpad, gone with the
container.

## Decision

Python Playwright tests under `tests/browser/`, run by `pytest` like the
rest of the suite, **required in CI** on every PR (author, 2026-10-01).

- **A live server, not a rendered snapshot.** A session-scoped fixture
  migrates a temporary SQLite file, starts `uvicorn app.main:app` on a free
  port with `ALLOW_FAKE_AUTH=true`, and tears it down. The browser talks
  to it over HTTP, so a Save reaches the server and a reload proves it
  persisted.
- **Seeding through the app's own routes**, over HTTP, the way
  `tests/integration/test_instrument_builder_routes.py`'s `_make_session`
  and `_populate_rosters` use the `TestClient`. Each test makes its own
  session with a unique code, so tests share a server but not data.
- **Assertions on the DOM and on the server's state**, and waits on
  conditions (`expect(...).to_be_visible()`), never fixed delays.
- **Skipped locally when the tool is missing; failed in CI.** Without
  `playwright` or a Chromium build the tests skip and say so in the skip
  reason. `RRW_REQUIRE_BROWSER=1`, set in `ci.yml`, turns that skip into a
  failure, so CI can't pass a browser suite by not running it.

**Rejected: sandbox-only, like `tools/css_parity_check.py`.** It adds no
dependency, but it runs only when an agent remembers to run it. It would
also add a second silent skip to a suite whose `CLAUDE.md` calls
`test_inline_scripts_parse.py` "the suite's only tool-gated skip".
**Rejected: Node Playwright.** The 151 scratch scripts were Node, but the
suite, its fixtures and CI are Python, and a second test runner is a second
thing to keep green.

## Semantics

- **Version pin.** `playwright==1.56.*` matches the sandbox's preinstalled
  `chromium-1194` (`/opt/pw-browsers`, the Node 1.56.1 install's build), so
  the sandbox needs no download. CI runs `python -m playwright install
  --with-deps chromium`, which fetches the same build. A version bump is a
  deliberate change, made in both places together.
- **xdist.** `pytest -n auto` gives each worker that collects a browser test
  its own server and browser; workers that collect none start nothing.
- **Fake auth only.** The tests sign in as the fake operator. Real Easy
  Auth stays a deployment check (`CLAUDE.md`, "Where work runs").
- **SQLite only.** `ci-postgres.yml` doesn't run them; the live app on
  Postgres is a deployment check too.
- **Not a layout test.** Pixel widths and "reads right" are the author's.
  A test asserts behavior: a row appears, a button disables, a value
  persists.

## Judgment calls — decided

- One file per surface (`test_builder_rows.py`, `test_builder_branching.py`,
  `test_owners_card.py`, `test_tag_typeahead.py`), not one per checklist
  row: rows share setup.
- The checklist rows stay in `guide/post_azure_todo_checklist.md` as the
  record of what the author checked; a test cites the row it covers in its
  docstring rather than the checklist citing tests.

## Blast radius (measured)

Taken 2026-10-01 at `85f8f92d`.

| What | Count | Command |
|---|---|---|
| Checklist rows, item 5 (owners, tags) | 12 | `awk '/^## 5\./,/^## 6\./' guide/post_azure_todo_checklist.md \| grep -c "^\| [^C-]"` |
| Checklist rows, item 6 (builder) | 40 | `awk '/^## 6\./,0' guide/post_azure_todo_checklist.md \| grep -c "^\| [^C-]"` |
| `<script` blocks in the builder template | 12 | `grep -c "<script" app/web/templates/operator/instruments_index.html` |
| Existing tool-gated skips | 1 | `test_inline_scripts_parse.py`'s `pytestmark = pytest.mark.skipif(` |
| CI `test` job today | 2 min 19 s | #2704's run, 02:54:32 → 02:56:51 |
| Smoke run (live server, one page, sandbox) | 7.3 s total, 2.6 s browser | scratch `pw_smoke.py`, 2026-10-01 |

Files the build touches: `pyproject.toml` (dev dependency),
`.github/workflows/ci.yml` (browser install, `RRW_REQUIRE_BROWSER=1`),
`tests/browser/` (new), `README.md` (tooling changed), `CLAUDE.md` /
`AGENTS.md` (the tool-gated-skip sentence), `docs/local_setup.md` (running
them locally). `.claude/hooks/session-start.sh` already runs
`pip install -e ".[dev]"` every session, so the sandbox picks the dependency
up with no change there.

## Status

Closed 2026-10-01, PRs #2706 → #2710 and this close. **34 tests** in
`tests/browser/`, run by `pytest -n auto` in the sandbox and required in
CI's `test` job; about 25 s of browser time per run.

**What the ladder became.** Rungs 1–5 landed as planned, one PR each: the
harness and one Save-and-reload test (2); 14 builder-row tests (3); 6
builder branching and 2 reviewer branch-row tests (4); 11 Owners-card,
typeahead and Create tests (5). Every test from rung 3 on names its
checklist row in its docstring; rung 2's Save round trip is the harness's
smoke test and repeats no single row. The tag file is `test_tags_and_create.py`, not
`test_tag_typeahead.py`, because Create's Owners card shares its setup.

**Divergences from the plan:**
- **A missing `playwright` is an import error, not a skip**: it is a dev
  dependency like `pytest`, so only a missing Chromium skips, and fails
  under `RRW_REQUIRE_BROWSER=1` (checked with `PLAYWRIGHT_BROWSERS_PATH`
  pointed at nothing: 34 skipped, or 34 errors with the variable set).
- **`ci-postgres.yml` passes `--ignore=tests/browser`**, an exclusion said
  out loud rather than a skip.
- **`.claude/hooks/session-start.sh` changed**, against Blast radius: it
  warns when no Chromium is found, as it does for `node`.
- **People other than the fake operator** sign in through the Easy Auth
  headers, which `app/auth/identity.py` reads first; colleagues come from
  `OPERATOR_EMAILS`. A full matrix is pinned through the server's database,
  as `tests/integration/_full_matrix.py` does.
- **The browser is module-scoped**, with a session-scoped launch check
  owning skip-or-fail. Session-scoped, it kept sync Playwright's event loop
  running in each xdist worker, and a later `asyncio.run()` on that worker
  failed (`test_session_new_tags_card.py`, found by CI on #2710).

**CI cost:** the Chromium install step takes 21 s; the `test` job went from
2 min 19 s (#2704) to 2 min 29 s at rung 2 (#2707) and 2 min 42 s with all
34 tests (#2710's head, `9a2a5d12`).

**Rows not automated, with the reason:**
- *The hide-confirm on a field with saved responses* — an activated
  session's card won't unlock.
- *A refused parent keeps the text* — the number input carries `max`, so
  Chromium's own validation stops the Save before the server can refuse it.
- *Create is unchanged, JavaScript off* — Create can't submit at all
  without script: its button renders `disabled` (since `9cfb70e1`,
  2026-05-22), while `spec/session_owners.md` and a `session_new.html`
  comment still describe that path. A defect, not a test gap.
- *The datalist popup* (headless draws none), *Owners above the Danger
  Zone* (layout), and the parts of rows tested only in part: relocking via
  another session's Home, Quick Setup's lock unaffected, the details card
  staying locked when Activated, and the lobby's two typeahead boxes.

The refused parent and the no-JS Create were raised with the author and
were unanswered at the close.

**Reads:** two `diff-reviewer` reads. The cumulative read at rung 4
(`df7a5942..b8f35a33`) found seven issues, all fixed: two tests claimed more
than they checked, a port race under xdist, a server that might not stop, a
silent migration failure, fake-auth keys a developer's `.env` could
override, and a redundant click. Rung 5's own read found seven, all fixed,
mostly tests asserting less than their row. Template breakages were used
to check that tests fail: two at rung 3, four at rung 5. Codex found one
more at rung 5: the lock test had checked a Remove button that was already
disabled for another reason.

## PR ladder

1. **This plan.** Prose only.
2. **The harness and one test.** `tests/browser/conftest.py` (server,
   browser, seeding helpers, the skip-or-fail rule), one test (unlock an
   instrument, rename a field, Save, reload, the name persisted), the
   dependency, the CI step, and the README, `CLAUDE.md` and
   `docs/local_setup.md` edits. Settles the CI cost on something small. Must
   not touch `app/`.
3. **The builder rows.** Item 6's rows a headless browser settles: "+",
   default names, the preview following a row, Active and ▲ ▼, R and ≡ alone,
   a new field saved twice, order persisting, the last row kept, Cancel,
   Delete's checkbox, Name and Email fixed, visibility in the card.
4. **Branching.** ⑂, join and detach, List conditions, the Active cascade,
   two levels, range conditions, and the reviewer-side branch rows (closed
   cell, refused parent, required only while open). **Expected last build
   rung: `diff-reviewer` reads the cumulative diff from the base SHA rung 2
   records.**
5. **Owners and tags.** Item 5's rows: the lock, Add owner and Remove saving
   at once, the last owner, the self-remove confirm, relocking, Create
   unchanged, and the typeahead's filtering and Enter in Chromium (not the
   popup, which headless doesn't draw). Reopens `tests/`, so it takes its
   own read.
6. **Close.** Definition of done checked, `docs/status.md` row.

## Definition of done

- `tests/browser/` exists and `pytest -n auto` runs it in the sandbox with
  no skip.
- `ci.yml` installs Chromium and sets `RRW_REQUIRE_BROWSER=1`; a PR run
  shows the browser tests passing, and removing the browser makes the job
  fail rather than skip.
- Every item 5 and item 6 row a headless browser can settle has a test
  naming it in its docstring; the rows it can't are listed in this plan's
  `Status` with the reason.
- The CI `test` job's added time is recorded in `Status`.
- `README.md`, `CLAUDE.md` / `AGENTS.md` and `docs/local_setup.md` describe
  the new tests and how to run them.
- `## Doc impact` section present and current.
- `spec-writer` not needed: no `spec/` change is planned.
- `## Status` compacted to intended vs done; answered open questions
  collapsed.
- `docs/status.md` row added; plan moved to `guide/archive/` + index row.

## Open questions

- **Does a layout measurement ever become a test?** Not ruled; shipped as
  proposed: none does.
- **Run them on the `postgres:16` job too?** Not ruled; shipped as
  proposed: excluded, by `--ignore` (Status).

## Out of scope

- **Visual regression** (screenshot diffs): brittle against intended change,
  and the author's eye is the check.
- **Safari and screen readers**: `guide/deferred_consolidated.md` Part C.
- **Real Easy Auth, the network, the deployed configuration**: deployment
  checks, `guide/post_azure_todo_checklist.md`.
- **The builder-script extraction**: waits for its trigger
  (`guide/codebase_assessment_30sep.md` §8 move 3), and goes better after
  this lands.

## Doc impact

- `README.md` — the browser tests, their dependency, and how CI runs them (rung 2).
- `CLAUDE.md` — "Where work runs": the tool-gated skip sentence names the browser tests and `RRW_REQUIRE_BROWSER` (rung 2); `AGENTS.md` copied.
- `docs/local_setup.md` — running the browser tests locally, including `playwright install chromium` (rung 2).
- `docs/status.md` — a row at the close.
- `.claude/hooks/session-start.sh` — warn when no Chromium is found (rung 2).
