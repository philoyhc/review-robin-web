# Database

Review Robin Web uses **SQLAlchemy 2.x** with **Alembic** for migrations.

The implementation contract for this segment lives in
`guide/archive/segment_04A.md`. This document is the operator-facing how-to.

## Local development

The default `database_url` is `sqlite:///./review_robin_web.db`. SQLite is
sufficient for unit tests and most local development through Segment 5.

**Local Postgres is intentionally deferred** (see `guide/archive/segment_05A.md`
§3.5). The repo no longer ships a `docker-compose.yml` for Postgres, and
`docs/local_setup.md` does not require Docker. Postgres-vs-SQLite parity
is enforced by the CI job at `.github/workflows/ci-postgres.yml` (every
PR — runs Alembic round-trip *and* the full pytest suite against Postgres)
and by the migration-on-deploy step in
`.github/workflows/main_app-review-robin-web-dev.yml` (every deploy).

If you do need a local Postgres for a Postgres-only investigation, install
any local Postgres 16 you prefer (Postgres.app, Homebrew, native package,
or `docker run postgres:16`), create a database, and set `DATABASE_URL` in
your `.env` to point at it — `.env.example` shows the format.

### First-time setup

```bash
pip install -e .[dev]
alembic upgrade head
```

That creates `review_robin_web.db` in the project root with all 12 tables.

### Pointing at a different database

`database_url` is read by `app.config.settings` from either `.env` or the
`DATABASE_URL` environment variable:

```bash
DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/rrw" alembic upgrade head
```

The Alembic `env.py` script reads this same setting, so the same value
applies to migrations and runtime.

## Generating a new migration

```bash
alembic revision --autogenerate -m "describe the change"
```

**Always review the generated migration by hand before committing.** Alembic
autogenerate is good but not perfect — it can miss column-type changes,
mis-order operations, and produce SQLite-incompatible DDL when batch mode is
needed. Run the migration up and down at least once before pushing.

```bash
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

Migration filenames live in `alembic/versions/`. They are checked in and
should never be edited after they ship in `main` — write a follow-up
migration instead.

## SQLite vs PostgreSQL

Segment 4 keeps every column type cross-dialect so the same migration runs
on both:

| Need              | Used in Segment 4              | Postgres-specific upgrade in Segment 14A |
|-------------------|-------------------------------|-----------------------------------------|
| JSON blob         | `sqlalchemy.JSON`             | `JSONB`                                  |
| UUID column       | `String(36)` (where used)     | native `UUID`                            |
| Datetime          | `DateTime(timezone=True)`     | n/a                                      |
| Enum-like field   | `String` + Python enum check  | optional DB-level `ENUM`                 |

Do **not** import from `sqlalchemy.dialects.postgresql` in `app/db/models/`
in this segment — those imports break SQLite tests and tie us to one
dialect prematurely.

## Tests

Tests live under `tests/db/`. The session-scoped `engine` fixture in
`tests/db/conftest.py` creates an in-memory SQLite database and applies
**`alembic upgrade head`** against it — exercising the real migration on
every test session, not `Base.metadata.create_all()`. Any drift between
models and migrations surfaces immediately.

Each test gets a per-test transactional session that rolls back on
teardown, so tests do not pollute each other.

## Where Postgres lives

- **Local Postgres for development** — deferred (see §3.5 of
  `guide/archive/segment_05A.md`). SQLite is the local default; install your own
  Postgres only when a Postgres-only bug demands it.
- **Azure Database for PostgreSQL Flexible Server** — provisioned in
  Segment 5. The dev App Service runs migrations against it on every
  deploy via the `migrate` job in
  `.github/workflows/main_app-review-robin-web-dev.yml`.
- **Postgres-against-Docker CI** — `ci-postgres.yml` applies and
  round-trips migrations *and* runs the full pytest suite against a
  `postgres:16` service container on every PR. The `engine` fixture
  in `tests/conftest.py` honours `TEST_DATABASE_URL` / `DATABASE_URL`
  so the same test bodies cover both dialects.

## Adding a new model

1. Add a new file in `app/db/models/`.
2. Re-export the class in `app/db/models/__init__.py` (Alembic autogenerate
   only sees what's been imported onto `Base.metadata`).
3. Run `alembic revision --autogenerate -m "add <thing>"`.
4. Review the generated migration; tighten anything autogenerate got wrong.
5. Apply locally (`alembic upgrade head`), confirm round-trip
   (`alembic downgrade -1 && alembic upgrade head`).
6. Add tests under `tests/db/`.

## Indexes

Most indexes are implicit: every `ForeignKey` column declares
`index=True`, every natural key (`sessions.code`, `users.email`,
`invitations.token_hash`, …) is `unique=True, index=True`, and a
multi-column `UniqueConstraint` (e.g. `assignments
(session_id, reviewer_id, reviewee_id, instrument_id)`,
`session_operators (session_id, user_id)`) also serves as a
B-tree index whose **leading-column prefixes** cover prefix
lookups.

### §5.5 query-path review (Segment 14A PR 3)

The main workflow queries were reviewed against the indexes
above:

| Query path | Covered by |
|---|---|
| Sessions for an operator | `session_operators.user_id` index (join), `sessions.id` PK |
| Reviewers / reviewees by session | `reviewers.session_id` / `reviewees.session_id` FK indexes |
| Assignments by reviewer / session | `uq_assignment_unique` prefix `(session_id, reviewer_id, …)` + FK indexes |
| Responses by assignment | `responses.assignment_id` FK index |
| Monitoring counts | session-scoped selects on the FK indexes above |
| Export queries | per-session `WHERE session_id = ?` selects on FK indexes |
| Audit events by session / date | **`ix_audit_events_session_created`** — added by this review |

Only the audit-log path lacked an index. `audit_events` had a
single-column `session_id` index but nothing covering the
`created_at` predicate the CSV exporter
(`ORDER BY created_at, id`) and the in-app viewer's date-range
filter both use — so PR 3 added the composite
`ix_audit_events_session_created (session_id, created_at)`.

Index work here stays **plain cross-dialect B-tree**. Postgres-only
index types (e.g. `JSONB` GIN) wait on the deferred type
migrations — see `guide/deferred_infra.md`.
