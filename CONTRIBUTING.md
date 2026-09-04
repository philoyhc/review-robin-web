# Contributing

Thanks for contributing to Review Robin Web.

## Workflow

1. Create a branch for each bounded task.
2. Keep pull requests small and focused.
3. Add or update tests for behavior changes.
4. Keep route handlers thin and business logic in services.
5. Update documentation when setup or behavior changes.

## Pull request checklist

- [ ] Tests pass locally (`pytest`).
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
directions and runs the full suite against a real `postgres:16`. It
matters because the deploy workflow runs `alembic upgrade head` against
Azure Postgres on every push to `main` and does **not** depend on either
CI workflow — so a Postgres-only migration failure that reaches `main`
is first discovered during a production migration.

**Merging ahead of it is fine** for changes that cannot reach the
database: documentation, and dev-only tooling under `tools/`. The faster
`CI` job (`ruff check .` plus the SQLite suite) still applies to anything
containing executable code, and it usually finishes inside two minutes.

This policy is deliberate rather than a gap: see
`docs/practice-audit-2026-09-04.md` §1 and §3, which measured it in
practice and recommended writing it down instead of enforcing it with
branch protection.

## Project conventions

Please follow repository conventions documented in `AGENTS.md`, including:

- Python 3.12+
- FastAPI backend patterns
- Pydantic schemas at boundaries
- Small, PR-sized changes
