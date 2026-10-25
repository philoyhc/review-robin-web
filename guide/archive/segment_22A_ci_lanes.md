# Segment 22A — CI lanes by path

**Opened:** 2026-10-25 · **Theme:** run only what a change can break, before Residential code adds to every run · **Related:** `residentialapps/guide/todo_master.md` ("First: CI by path"), `CONTRIBUTING.md` ("When to wait for CI")

## Opportunity

Every PR runs both workflows in full, whatever it touches. Measured on the prose-only PRs of 2026-10-25: `CI` (`test`) 4 min 28 s to 4 min 33 s, `CI - Postgres` (`postgres`) 6 min 23 s to 9 min 23 s, across `#3261`, `#3262` and `#3264`. A one-line guide edit waits up to ~9 minutes, and Residential's tests and its two databases (`residentialapps/guide/todo_master.md`, ruling 11) would add to every run. The author ruled the split a priority, settled before any Residential code lands.

`CONTRIBUTING.md` already says documentation may merge ahead of `CI - Postgres`; CI does not act on it.

## Decision

**One classifier, two lanes now, a third at the scaffold.** `tools/ci_lanes.py` (stdlib) reads the changed paths and prints the lanes to run. Each workflow starts with a small `changes` job that runs it; the other jobs read its output.

| Lane | When | Runs |
|---|---|---|
| `prose` | every changed path is prose (below) | `pytest tests/unit` plus the integration files that read prose; no Chromium, no Postgres |
| `full` | anything else, every push to `main`, and any run the classifier cannot decide | today's `test` and `postgres` jobs, unchanged |
| `residential` | added by the scaffold segment, when `residentialapps/` has code | Residential's tests and databases, plus `cordware/tests` |

**Prose** is a `.md` file under `spec/`, `docs/`, `guide/`, `cordware/spec/`, `residentialapps/docs/` or `residentialapps/guide/`, or at the repository root, or `residentialapps/README.md`. Any other file in those folders (CSV samples, HTML previews) is not prose.

**Rejected: workflow-level `paths-ignore`.** A skipped workflow reports nothing, so a prose PR would show no check at all and the rule would be split across two YAML files. **Rejected: a third-party filter action** (`dorny/paths-filter`): a pinned dependency for a twenty-line rule this repository can test itself.

## Semantics

- **Fail toward running.** An unknown path, an empty diff, a missing base or a classifier error all give `full`.
- **Push to `main` is always `full`.** Cordware's importer gates on the latest `CI` and `CI - Postgres` runs from a push to `main` (its `required_runs`), so the push runs must stay complete. Both workflow names stay as they are.
- **A skipped job is not a pass.** `main` has no required checks (`CONTRIBUTING.md`), so nothing gates on lanes; the `changes` job's summary names the lane, so a reviewer can see why `test` was skipped.
- **The prose lane's integration files are derived, not listed by hand.** A test fails if a test file outside `tests/unit/` reads a prose folder and the lane does not run it.

## Judgment calls — decided

- The prose lane runs all of `tests/unit` (25 s locally), not a hand-picked set of doc tests: the doc gates are spread across files, and a list would drift.
- `ruff` is skipped in the prose lane: it reads no Markdown.
- The classifier is a tool with unit tests, not inline shell, so the rule lives in one tested place.

## Blast radius (measured)

Taken 2026-10-25 at `d3ba790`.

| What | Count | Command |
|---|---|---|
| Workflows changed | 2 (`ci.yml`, `ci-postgres.yml`); `main_app-review-robin-web-dev.yml` untouched | `ls .github/workflows` |
| Test files outside `tests/unit/` reading a prose folder | 1 (`tests/integration/test_guide_scaffold.py`) | `grep -rlE "\"(spec\|docs\|guide)\"" tests/integration tests/db tests/browser`, read by hand |
| Non-`.md` files in prose folders | 7 (4 in `docs/sample_data/`, 3 in `guide/`); no test reads them | `git ls-files spec docs guide cordware/spec residentialapps \| grep -v "\.md$"` |
| Live prose naming either workflow | 5 (`CLAUDE.md`, `AGENTS.md`, `docs/database.md`, `docs/unenforced_conventions.md`, `new_project_practices_setup.md`) | `grep -rln "ci\.yml\|ci-postgres\.yml" --include=*.md . \| grep -v archive` |

## Status (closed 2026-10-25)

**Done as planned, in four PRs:** `#3265` plan, `#3266` classifier, `#3267` workflows, `#3268` prose and close.

- **Measured.** Prose-only `#3268`: `changes` 5 s, `prose` 58 s, `test` and `postgres` skipped, about 66 s from start to finish, against 6 min 23 s to 9 min 23 s for the same kind of PR before. Code `#3267` (full lane): `test` 4 min 38 s, `postgres` 5 min 33 s, `prose` skipped, so the lane adds about 7 s to a full run.
- **One `diff-reviewer` read** (rung 3, cumulative from `b20cc9b`): no defect against the Decision; two gaps fixed in `#3267`. `git diff --name-only` detected renames, so a non-prose file moved into a prose folder read as prose (now `--no-renames`, with a test). The prose-reader scan matched one way of writing a path (now any string literal naming a prose path, in `tests/` and `cordware/tests`, each match ruled into `PROSE_TESTS` or `NOT_PROSE_READERS` with a reason).
- **Scope moved:** the `tools/README.md` row landed in rung 3, not 4, so rung 4 was prose only and could measure the lane.
- **Recorded, not changed:** if the `changes` job itself fails on a push to `main`, the full jobs still run but the run concludes `failure`, so Cordware's importer refuses that commit until it is re-run. That fails safe.
- **`spec-writer`:** not run; `Doc impact` names no `spec/` path.

## PR ladder

1. **This plan** (prose).
2. **The classifier.** `tools/ci_lanes.py` and `tests/unit/test_ci_lanes.py`: each lane, every fail-toward-running case, and the derived prose-test list. No workflow change.
3. **Wire the workflows.** A `changes` job in both, the `prose` job in `ci.yml`, `if:` on `test` and `postgres`; push to `main` forced `full`. Checked with `actionlint` before the push. Not touching the test or migration steps themselves.
4. **Prose and close.** `CONTRIBUTING.md`, the twins, `docs/database.md`, `tools/README.md`; re-measure a prose PR and a code PR and record both in `Status`.

## Definition of done

- A prose-only PR runs `changes` and `prose` only; `test` and `postgres` show skipped, measured in `Status`.
- A PR touching `app/` runs `full`; a push to `main` runs `full`.
- `tests/unit/test_ci_lanes.py` covers each lane and each fail-toward-running case.
- `CONTRIBUTING.md` "When to wait for CI" describes the lanes.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 22A` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- None open. The `residential` lane's exact jobs are the scaffold segment's to decide.

## Out of scope

- The `residential` lane itself: no Residential code exists to test (rung 1 of the rosters segment adds it).
- Branch protection or required checks: deliberately absent (`CONTRIBUTING.md`).
- Speeding up the suites themselves.

## Doc impact

- `CONTRIBUTING.md` — "When to wait for CI": the two lanes, prose PRs skip `test` and `postgres`.
- `CLAUDE.md` — "Where work runs": CI runs by lane; a prose-only PR runs the unit tests only.
- `AGENTS.md` — twin of `CLAUDE.md`.
- `docs/database.md` — the Postgres job runs on every non-prose PR and every push to `main`.
- `tools/README.md` — a row for `ci_lanes.py` (landed in rung 3).
- `residentialapps/guide/todo_master.md` — "First: CI by path" points here; done at close.
- `guide/todo_master.md` — the queue entry for 22A, deleted at close.
