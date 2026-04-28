# AGENTS.md

## Project conventions

- Use Python 3.12+.
- Use FastAPI for the backend.
- Use Pydantic for request/response schemas.
- Use SQLAlchemy 2.x declarative style with `Mapped[]` and `mapped_column`.
  Do not import from `sqlalchemy.dialects.postgresql` in `app/db/models/` —
  Postgres-specific column types are deferred to Segment 13.
- Keep route handlers thin.
- Put business logic in service modules.
- Add or update tests for every behavior change.
- Prefer explicit types and clear names.
- Do not introduce a full frontend framework unless explicitly requested.
- Do not implement Microsoft authentication in app code unless explicitly requested; assume Azure App Service Easy Auth will provide authenticated identity headers in deployed environments.
- Keep changes small and PR-sized.

## Current stage

Segments 1–7 complete. See `docs/status.md` for the authoritative
snapshot of what ships today; this section summarises only what an
agent needs before opening files.

The project has:

- FastAPI app on Azure App Service, deploy-on-push to `main` with a
  `build → migrate → deploy` pipeline.
- Azure Postgres Flexible Server with `alembic upgrade head` running
  in CI before every deploy. PR CI runs SQLite pytest plus a
  `postgres-migration` smoke job.
- Microsoft Entra ID via Azure Easy Auth in deployed envs;
  `ALLOW_FAKE_AUTH=true` fallback for local dev. `User` rows are
  created on first sign-in.
- 12-table SQLAlchemy 2.x schema with Alembic migrations.
- Operator MVP: session CRUD, reviewer/reviewee CSV import + Manage
  views, setup validation, FullMatrix + Manual assignment generation,
  per-session Default Instrument placeholder, audit log on every
  destructive op.

Not yet implemented (do not add unless an issue explicitly asks):
operator-editable instruments, the reviewer-facing review surface,
session activation, invitations & reminders, responses, export,
RuleBased assignment, multi-instrument sessions, production hardening
(Key Vault, VNet, soft-delete). These map to Segments 8–13 — see
`guide/segment_NN_*` and `docs/status.md` "What's deliberately not
yet there."

Update `docs/status.md` at the end of each segment; keep the summary
above in sync.

## Testing expectations

Before considering a change complete, run:

```bash
pytest
```

If dependencies or tooling change, update `README.md`.
