# AGENTS.md

## Project conventions

- Use Python 3.12+.
- Use FastAPI for the backend.
- Use Pydantic for request/response schemas.
- Use SQLAlchemy 2.x declarative style with `Mapped[]` and `mapped_column`.
  Do not import from `sqlalchemy.dialects.postgresql` in `app/db/models/` —
  Postgres-specific column types are deferred to Segment 14.
- Keep route handlers thin.
- Put business logic in service modules.
- Add or update tests for every behavior change.
- Prefer explicit types and clear names.
- Do not introduce a full frontend framework unless explicitly requested.
- Do not implement Microsoft authentication in app code unless explicitly requested; assume Azure App Service Easy Auth will provide authenticated identity headers in deployed environments.
- Keep changes small and PR-sized.

## Working approach

Land changes as small, reviewable slices. The natural unit is one
coherent feature step — e.g. a migration + its seed code, a service
helper set + the routes that call it, a template refactor + its
tests — sized so a reviewer can model the full contract in one
sitting.

When a segment plan in `guide/` calls out internal slices, land
them in order across multiple PRs rather than collapsing them; use
the plan's "land X first as a self-contained Y" risk notes as the
cut points. Don't bundle independent changes (e.g. an unrelated bug
fix) into the same PR.

## Stack summary

- **Language.** Python 3.12+.
- **Web framework.** FastAPI on Starlette ASGI; uvicorn for local
  dev, gunicorn + uvicorn workers in production.
- **Templates.** Jinja2, server-rendered. **No frontend framework,
  no HTMX, no JS build step.** Forms are plain `<form method="post">`;
  navigation state lives in URL fragments / query params
  (e.g. `?validated=1`, `#upload-csv`). Inline `<style>` in
  `base.html`; CSS extraction is a Segment 14 concern.
- **Schemas / config.** Pydantic 2 (`pydantic` for request /
  response shapes, `pydantic-settings` for env config).
- **ORM + migrations.** SQLAlchemy 2.x declarative
  (`Mapped[]` + `mapped_column`); Alembic for migrations. No
  `sqlalchemy.dialects.postgresql` imports in `app/db/models/`
  per the convention above.
- **Database.** Postgres 16 (Azure Postgres Flexible Server,
  Burstable B1ms, Southeast Asia) in deployed environments;
  in-memory SQLite per test session for `pytest`. Both
  round-tripped on every PR via the `ci-postgres-migration`
  smoke job.
- **Postgres driver.** psycopg 3 (`psycopg[binary]`).
- **Auth.** Microsoft Entra ID via Azure Easy Auth in deployed
  environments; `ALLOW_FAKE_AUTH=true` fallback for local dev.
  Identity headers (`X-MS-CLIENT-PRINCIPAL` /
  `X-MS-CLIENT-PRINCIPAL-{NAME,ID,IDP}`) parsed by
  `app/auth/identity.py`.
- **Hosting.** Azure App Service (Linux, Python 3.12) + Azure
  Postgres Flexible Server. Public access with firewall
  allow-list; VNet integration is a Segment 14 concern.
- **Deploy.** GitHub Actions, OIDC-authenticated; three jobs
  (`build` → `migrate` → `deploy`). Migrations land via
  `alembic upgrade head` against Azure Postgres before the App
  Service swap; deploy is skipped if migration fails.
- **CI.** SQLite `pytest` job + a `postgres-migration` smoke job
  that round-trips Alembic against a `postgres:16` service
  container on every PR.
- **Tooling.** `pytest` + `httpx` (TestClient), `ruff` (lint).

## Current status

See `docs/status.md` for full implementation status and
architectural notes.

Current segment: **10B-2** (operator display-field builder — plan
drafted in `guide/segment_10B_2.md`, not yet implemented).

## Testing expectations

Before considering a change complete, run:

```bash
pytest
```

If dependencies or tooling change, update `README.md`.
