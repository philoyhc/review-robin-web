# Contributing

Thanks for contributing to Review Robin Web.

## Workflow

1. Create a branch for each bounded task.
2. Keep pull requests small and focused.
3. Add or update tests for behavior changes.
4. Keep route handlers thin and business logic in services.
5. Update documentation when setup or behavior changes.

## Pull request checklist

- [ ] Tests and lint pass locally (`pytest -n auto`, `ruff check .`).
- [ ] New behavior has tests.
- [ ] Documentation is updated if needed.
- [ ] No unrelated refactoring is included.

## When to wait for CI

`main` carries no branch protection, so nothing mechanically blocks a
merge — the gate is your judgement. Stratify by what the diff touches.

**Wait for `CI - Postgres` to report green** when the diff touches
`alembic/`, `app/db/`, or any service that issues queries. The default
test run is against SQLite; production is Postgres 16, and SQLite is the
more permissive of the two in several ways that have bitten this project
(`BOOLEAN DEFAULT 1`, `WHERE bool_col = 1`, FK enforcement at
`DROP TABLE`, index/FK name mismatches between upgrade and downgrade —
see the migration-portability notes in `AGENTS.md`). That job is the only
check covering the gap: it round-trips the whole Alembic chain in both
directions and runs the full suite against a real `postgres:16`, across
xdist workers with a database each: about four minutes since segment 22B,
nine serially before it (2026-10-26). It
matters because a deployment migrates Postgres from a `main` commit:
the dev slot's workflow did so on every push without depending on
either CI workflow, and the institutional release migrates whichever
`main` commit it takes. A Postgres-only migration failure that reaches
`main` would first be discovered during a production migration. The dev
slot has been dormant since 2026-06-03 and is not being revived
(`docs/deployment_dev.md`); the policy holds for the institutional
release.

**A prose-only PR doesn't run it at all.** CI classifies each pull
request (`tools/ci_lanes.py`, `guide/archive/segment_22A_ci_lanes.md`): one that
changes only Markdown in `spec/`, `docs/`, `guide/`, `cordware/spec/`,
Residential's `docs/`, `guide/` and `spec/`, or at the root, or a `README.md`
outside what ships (`app/`, `alembic/`, `cordware/`, `residentialapps/`), runs the `prose` job
alone, the unit tests plus the tests that read prose, and shows `test` and
`postgres` as skipped. One that changes only prose and `residentialapps/`
runs the `residential` job instead (`ruff check .`, Residential's tests,
`cordware/tests` and the prose lane's), with `test` and `postgres` skipped
too: Residential has no database yet and RRW never imports it. Anything
else, and every push to `main`, runs both in full.

**Merging ahead of it is fine** for changes that cannot reach the
database: documentation, and dev-only tooling under `tools/`. The faster
`CI` job (`ruff check .` plus the SQLite suite, or the `residential`
job for a Residential-only change) still applies to anything containing
executable code, and it takes about three minutes (2026-10-03).

This policy is deliberate rather than a gap: see
`docs/archive/practice-audit-2026-09-04.md` §1 and §3, which measured it in
practice and recommended writing it down instead of enforcing it with
branch protection.

## Project conventions

Please follow repository conventions documented in `AGENTS.md`, including:

- Python 3.12+
- FastAPI backend patterns
- Pydantic schemas at boundaries
- Small, PR-sized changes
