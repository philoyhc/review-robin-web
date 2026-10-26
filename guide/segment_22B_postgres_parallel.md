# Segment 22B — The Postgres job in parallel

**Opened:** 2026-10-26 · **Theme:** run `CI - Postgres`'s suite across xdist workers, one database each, so the slowest check stops setting the pace · **Related:** `guide/archive/segment_22A_ci_lanes.md` (the lanes this follows), `docs/database.md`, `CONTRIBUTING.md` ("When to wait for CI")

## Opportunity

`CI - Postgres` is the slowest check on every full-lane PR. Its `postgres` job took 8 min 12 s, 5 min 56 s, 7 min 13 s and 9 min 16 s on `#3277`, `#3279`, `#3280` and `#3281` (2026-10-26), against 4 to 5 min 21 s for `CI`'s `test` job on the same commits, Chromium install and browser tests included. The difference is that `test` runs `pytest -n auto` and `postgres` runs `pytest -q`, about 7,300 tests one at a time.

It cannot simply add `-n auto`: the session `engine` fixture (`tests/conftest.py`) runs `DROP SCHEMA public CASCADE` and `alembic upgrade head` on the one database `TEST_DATABASE_URL` names, so parallel workers would drop each other's schema mid-run.

## Decision

**One database per xdist worker, derived from `TEST_DATABASE_URL`.** Under xdist (`PYTEST_XDIST_WORKER`, e.g. `gw0`), the fixture rewrites the URL's database name to `<name>_<worker>` (`rrw` becomes `rrw_gw0`). It creates that database if it is missing, connected to the named one, then drops, recreates and migrates the worker's own schema as today. Without xdist nothing changes. `ci-postgres.yml` then runs `pytest -n auto -q --ignore=tests/browser`; its two migration steps (upgrade head; downgrade base and upgrade head) stay on the named database, unchanged.

**Rejected: one schema per worker in a single database.** Alembic's version table, the migrations' own `public.` assumptions and Postgres-specific DDL would all need a `search_path` threaded through, and a migration that hard-codes `public` would pass in one worker and fail in another.

**Rejected: splitting the suite across a job matrix.** Each shard would pay its own setup, about a minute for checkout, install and the service container, and the split would need maintaining as tests move.

## Semantics

- **Only a test database is ever created or dropped.** The derived name is the named test database plus a suffix, and the drop still reads only `TEST_DATABASE_URL` (findings H12; `tests/unit/test_test_database_url.py`). Nothing derives from `DATABASE_URL`.
- **No xdist, or SQLite:** unchanged. A local `TEST_DATABASE_URL=… pytest` still uses the named database.
- **Creating the database needs `CREATEDB`.** The CI role is the container's superuser. Without the privilege the fixture fails with a message naming it, never by falling back to the shared database.
- **A worker's database persists between runs on the same host.** Each session drops its schema first, as the single database does today.
- **Tests that open their own sessions** (`tests/integration/test_owner_add_lock.py`'s row-lock tests) bind to the worker's engine and so stay inside its database.

## Judgment calls — decided

- The suffix is the xdist worker id, not a random name, so a rerun reuses its databases and nothing accumulates.
- The migration round-trip steps stay serial and on the named database: they test the chain once, and the workers each run `upgrade head` again as the fixture does today.

## Blast radius (measured)

Taken 2026-10-26 at `ff0f30c`.

| What | Count | Command |
|---|---|---|
| Fixtures that drop a schema | 1 (`engine`, `tests/conftest.py`) | `grep -rn "DROP SCHEMA" tests` |
| Files reading `TEST_DATABASE_URL` in code or CI | 3 | `grep -rln TEST_DATABASE_URL --include=*.py --include=*.yml . \| grep -v .venv` |
| Test files creating their own engine outside `tests/browser/` | 17, all `sqlite://` except the shared fixture | `grep -rln "create_engine(" tests/integration tests/db tests/unit \| wc -l` |
| Live prose naming the Postgres job's command | `docs/database.md`, `docs/local_setup.md`, `CONTRIBUTING.md` | `grep -rln "TEST_DATABASE_URL\|ci-postgres" docs CONTRIBUTING.md` |

## PR ladder

1. **The per-worker database** in `tests/conftest.py`: derive, create if missing, migrate. Unit tests for the name derivation and the refusal without `CREATEDB` (no Postgres needed for either). `ci-postgres.yml` is untouched, so CI still runs serially and the rung proves nothing breaks without xdist.
2. **`ci-postgres.yml` runs `pytest -n auto`.** Record the job's time on this PR and the next two full-lane PRs in `Status`. Last build rung: `diff-reviewer` reads the cumulative diff.

## Definition of done

- `CI - Postgres` runs `pytest -n auto -q --ignore=tests/browser`, and three full-lane runs' `postgres` times are recorded in `Status`.
- `tests/unit/test_test_database_url.py` still passes, plus tests for the derived name.
- `docs/database.md` describes the per-worker databases.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 22B` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **How many workers on a hosted runner:** `-n auto` takes the runner's four cores, so four databases each migrated at session start. If the migration cost eats the gain, rung 2 tries `-n 2` and records both. Decided by rung 2's measurement.

## Out of scope

- Residential's two databases in CI: segment 1B item 2 (`residentialapps/guide/segment_1B_rosters_and_organization.md`), which should use the same derivation when it lands.
- Making the browser tests run against Postgres: they serve their own SQLite file by design (`guide/archive/browser_test.md`).

## Doc impact

- `docs/database.md` — the test suite's per-worker Postgres databases and the `CREATEDB` need (rung 1).
- `CONTRIBUTING.md` — the Postgres job's duration in "When to wait for CI" (rung 2).
- `guide/todo_master.md` — the queue entry, deleted at close.
