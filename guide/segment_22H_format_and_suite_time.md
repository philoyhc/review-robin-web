# Segment 22H — Formatter and suite time

**Opened:** 2026-11-05 · **Theme:** close the last mechanical gate (a
formatter) and shorten the pre-PR wait · **Related:**
`guide/archive/segment_22C_pyright.md` (the ruff rule-set rung),
`tools/ci_lanes.py`, `CLAUDE.md` "Where work runs"

Handed off from a read of the repository at `38a0506` on 2026-11-05 and
re-measured at `dd8af8ff` the same day. Two items, independent, each
closing on its own. Item 1 lands first because its diff touches nearly
every Python file and must not interleave with any open code PR.

## Opportunity

**Formatting.** Segment 22C added `I`, `UP`, `B`, `SIM` to ruff but left
`E501` off. That leaves 1,468 long lines and no formatter to fix them, and
`ruff format --check .` would change 936 of 1,074 files. Of the gate
triad (ruff / pyright / pytest), the formatter is the one mechanical
check still missing. It is also the one that makes agent diffs uniform:
no reflow-only hunks for a reviewer to argue with.

**Suite time.** The full suite runs 8,361 tests in about 270 s with
`-n auto` on 4 cores, and 293 s on 2 cores at `38a0506`: about 63 ms of
CPU a test, which is healthy for ORM + Jinja integration tests. The
fixtures are already right: a session-scoped engine, `create_all`
rather than migration replay, a per-test rollback, one shared `app`. The
suite is slow because it is large, not because anything is broken. Two
tests are outliers, the agent loop runs the whole suite when it needs a
slice of it, and CI's `test` job (6 m 42 s on #3620) is the PR's longest
wait.

## Decision

**Item 1:** adopt `ruff format` with the project's existing
`line-length = 100`, turn `E501` on once the format run makes it nearly
pass, and gate both in CI beside `ruff check`.
- **Rejected: `black`**, a second tool for what ruff already ships.
- **Rejected: leaving `E501` off after formatting.** The formatter cannot
  wrap a long string or comment, so `E501` is the residual check. If the
  residue is small, fix those lines; if it is large, ask in the PR rather
  than ignore the rule.

**Item 2:** three slices: fix the two outlier tests, write the targeted
loop into `CLAUDE.md`, and split CI's `test` job in two.
- **Rejected for now: `pytest-testmon`.** It needs a warm `.testmondata`
  that the ephemeral container does not have. Revisit only if the
  targeted-loop convention proves insufficient.
- **Rejected: a larger GitHub runner**, a billing change for a problem the
  split solves.
- **Rejected: a coverage-redundancy pass** over the 8,361 tests. That is a
  different project: a `codebase_assessment` item, not this segment's.

## Judgment calls — decided

- Item 1 is one PR, not one per package: a formatter half-applied is worse
  than none, and `.git-blame-ignore-revs` keeps `git blame` readable.
- Item 1's format PR carries no other change: not a lint fix, not a
  spelling, nothing. `diff-reviewer` reads it for scope only. The content
  check is that `git diff --stat` matches `ruff format --check`'s file
  list and that the gates are green.
- The blame-ignore file lands in Item 1 rung 2, not the format PR. This
  repository squash-merges, so the branch commit's SHA never reaches
  `main`; only the squash SHA is known after the merge.
- CI splits by directory, not with `pytest-split`: there is no durations
  file to keep current, and the directory boundaries already match the
  lanes' vocabulary.
- `ci-postgres.yml` stays one job: it took 4 m 07 s on #3620 against
  `test`'s 6 m 42 s, so it is not the wait.

## Semantics

- **A formatter run changes no test's verdict.** If any test flips under
  Item 1 rung 1, stop: the test depends on source layout, and that is a
  finding, not a formatting matter.
- **A wrapped line can move a suppression.** A `# pyright: ignore[…]` or
  `# noqa` comment sits on the line it silences. If the formatter splits
  that statement, the comment can end up on a different line from the
  error. `pyright` and `ruff check` must both be clean after the run;
  any that breaks moves by hand in the same PR, and the PR body says so.
- **`E501` after formatting measures only what the formatter cannot
  wrap.** A fix that splits a string literal must keep the string's value
  byte-identical (implicit concatenation), because some strings are
  user-facing copy or audit `detail` keys.
- **Migrations are formatted too.** No committed tool reads their layout:
  `grep -rln "alembic/versions" tools tests` finds one test, which
  imports a migration module and reads a constant from it.
- **Item 2 rung 1 changes no test's verdict, only its clock.**

## Blast radius (measured)

Taken 2026-11-05 at `dd8af8ff`, except where a row says `38a0506`.

| What | Count | Command |
|---|---|---|
| Files `ruff format` would change | 936 / 1,074 | `ruff format --check .` (ruff 0.15.22) |
| `E501` violations before formatting | 1,468 | `ruff check --select E501 .` |
| Tests, full suite, 4 cores | 8,361 passed, 12 skipped, ~270 s | `pytest -n auto` |
| Wall / CPU on 2 cores (at `38a0506`) | 293 s / 8.5 min | `time pytest -n 2 --ignore=tests/browser` |
| `tests/unit` / `tests/integration` / `tests/db` (at `38a0506`) | 2,096 / 5,298 / 30 | `pytest --collect-only -q <dir> \| grep -c ::` |
| `test_no_url_leaks`, serial | 8.0 s (13.1 s at `38a0506`, 2 cores) | `pytest -p no:xdist tests/unit/test_url_leaks.py --durations=5` |
| `test_import_order`, 16 parametrizations | 0.85–1.2 s each | as above, `tests/unit/test_import_order.py` |
| CI `test` / `postgres` job, #3620 | 6 m 42 s / 4 m 07 s | the PR's check runs |
| Browser tests outside `tests/browser` | 3 files | `ls residentialapps/tests \| grep browser` |

## Item 1 — `ruff format`

### Status (closed 2026-11-05)

**Intended vs done.** The format run went in as #3623. A follow-up PR,
#3624, which the ladder did not have, turned `E501` on after it (the
ruling below). The gate went in as #3625, and this close as the PR after it. Item 1 took one read: a cold
scope read of #3623, which confirmed the diff was `ruff format` output
plus the named hand edits.

**Decisions confirmed at build:**
- The run left 222 lines over 100, not about 50. The author ruled to
  exempt `tools/theme_customizer.gen.py` (92 of them, the generated
  page's markup) and fix the rest in their own PR.
- The 130 others: 85 strings split by implicit concatenation, 4
  comments rewrapped, 20 docstring lines rewrapped (whitespace only),
  and 23 lines inside 11 multi-line strings (mock CSV, JS and HTML)
  marked `# noqa: E501`, because they cannot split without changing
  their value. Every edited file's AST matched its parent once docstring
  whitespace was normalized.
- The run needed three kinds of hand edit, as Semantics predicted: a
  moved `noqa`, a `pyright` ignore split onto two lines, and two
  `# not-identity:` markers. Two joined lines had tripped
  `test_identity_columns_are_compared_through_the_fold`, which reads
  layout. The formatter also normalized four docstrings' whitespace.
- `ruff` is pinned exactly (`0.15.22`), which the ladder did not say.
  A version range would let CI format differently from the tree.

### PR ladder

1. **Config and the big diff (one PR, nothing else in it).**
   - `pyproject.toml` gains an empty `[tool.ruff.format]` block (the
     defaults: double quotes, magic trailing commas respected, and the
     line length from `[tool.ruff]`), so the decision is visible.
   - Run `ruff format .`, then `ruff check --select E501 . | tail -1`.
     If the residue is about 50 or fewer, fix it here and add `"E501"` to
     `extend-select`. If it is more, leave `E501` off and ask in the PR.
   - `pytest -n auto`, `ruff check .` and `pyright` are green, with any
     suppression moved by hand (Semantics).
   - The PR body gives the file count, the `E501` residue, and the
     statement that the diff is `ruff format` output plus only the named
     hand moves.
   - Land it when no code PR is open, since every one would conflict.
2. **The gate (one PR).**
   - `.github/workflows/ci.yml`: a `Format check` step
     (`ruff format --check .`) after `Lint`, in the `test` and
     `residential` jobs.
   - `.git-blame-ignore-revs` at the root with rung 1's squash SHA;
     `README.md` gains `git config blame.ignoreRevsFile .git-blame-ignore-revs`
     and `ruff format` beside its dev commands.
   - `CLAUDE.md`: `ruff format --check .` joins the pre-PR gate sentence
     and "Common commands", with `ruff format .` as the fix. Then
     `cp CLAUDE.md AGENTS.md`.
   - `.claude/skills/babysit-merge/SKILL.md`: the check joins its
     Stage 1 list.
3. **Close.**

### Definition of done

- `ruff format --check .` and `ruff check .` pass on `main`, and CI runs
  both in the `test` and `residential` jobs.
- `E501` is in `extend-select`, or the PR records the author's ruling to
  leave it off.
- `.git-blame-ignore-revs` names rung 1's squash commit.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 22H.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

### Doc impact

- `CLAUDE.md` — the format check in the pre-PR gate sentence and Common commands.
- `AGENTS.md` — the twin, copied from `CLAUDE.md`.
- `README.md` — `ruff format` among the dev commands, and the blame-ignore config line.
- `.claude/skills/babysit-merge/SKILL.md` — the format check in Stage 1's list.
- `guide/todo_master.md` — delete the item's entry at its close.

## Item 2 — Suite time

### PR ladder

1. **The two outlier tests (one PR, code).**
   - **`tests/unit/test_url_leaks.py::test_no_url_leaks`, 8–13 s.**
     Profiled at `38a0506`: `python_leaks()` calls
     `ast.get_source_segment(source, node)` 16,324 times, and that
     function re-splits the whole file into lines on every call
     (`ast._splitlines_no_ff`, 11.9 of 14.4 s). Split each file once and
     slice by `lineno` / `end_lineno` / `col_offset` / `end_col_offset`,
     or cache the split per file. The second cost, `_segments()` at 3 s,
     calls `app.openapi()` to list route prefixes; cache it with
     `functools.cache`. The test's finding set must be identical before
     and after: dump both once and compare.
   - **`tests/unit/test_import_order.py`, 16 × about 1 s.** Each
     parametrization runs `python -c "import <module>"`, and the
     subprocess is the point (import isolation). Keep it and lose only the
     serial wait: launch all 16 together (`subprocess.Popen` or a thread
     pool) and collect. Under xdist the 16 already spread across workers,
     so this only helps a single-worker run. Do it only if it stays about
     a ten-line change; otherwise leave it and say so in `Status`.
2. **The targeted loop (prose only, no read).** `CLAUDE.md` "Where work
   runs" keeps the full suite as the gate on every push, and adds the loop
   before it, in substance:

   > While building, run the files the change reaches, and the full
   > `pytest -n auto` once before pushing. A full run per edit is 3–5
   > minutes of waiting that finds nothing a targeted run would not.

   It says what "the files the change reaches" means here: the test files
   named for the route, service or view module changed, plus
   `tests/unit/` when prose or a template changed (the doc-convention and
   template tests live there). Then `cp CLAUDE.md AGENTS.md`.
3. **Split CI's `test` job (one PR, CI).** `.github/workflows/ci.yml`'s
   `test` job becomes a two-entry matrix, `fail-fast: false`, running
   `pytest -n auto <paths>`:
   - `unit`: `tests/unit tests/db cordware/tests utilityapps/tests residentialapps/tests`;
   - `integration`: `tests/integration tests/browser`.

   Both keep `RRW_REQUIRE_BROWSER=1`, and both install Chromium:
   `residentialapps/tests` holds three browser tests, so a Chromium step
   skipped on `unit` would fail it. Lint, format and type check run in
   one entry only. A test asserts the two path lists together equal
   `pyproject.toml`'s `testpaths`, so a new test root cannot fall out of
   CI. The job names become `test (unit)` / `test (integration)`; update
   any live prose that names the `test` job (`CLAUDE.md`). `tools/ci_lanes.py` picks a lane, not a job name, so it does
   not change.
4. **Close.**

### Definition of done

- `test_no_url_leaks` runs in under 2 s serially, with an unchanged
  finding set.
- `CLAUDE.md` and `AGENTS.md` state the targeted loop; the twins are
  byte-identical.
- CI's `test` job runs as two matrix entries whose paths together cover
  `testpaths`, checked by a test.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 22H.2` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

### Doc impact

- `CLAUDE.md` — the targeted loop in "Where work runs"; the `test` job's new names.
- `AGENTS.md` — the twin, copied from `CLAUDE.md`.
- `guide/todo_master.md` — delete the item's entry at its close.

## Open questions

- ~~The `E501` residue after formatting~~: 222 lines. The author ruled
  to exempt `tools/theme_customizer.gen.py` and fix the rest (Item 1
  Status).

## Out of scope

- `pytest-testmon`, a larger runner, and a coverage-redundancy pass:
  rejected above, with when each comes back.
- Splitting `ci-postgres.yml`: it is not the long job (Judgment calls).
- Formatting templates, inline scripts or Markdown: `ruff format` reads
  Python only, and `test_inline_scripts_parse.py` already checks the
  scripts parse.
