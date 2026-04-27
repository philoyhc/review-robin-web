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

Segments 1–4 complete. The project has a FastAPI app skeleton, Azure
deployment, Easy Auth identity, and a SQLAlchemy 2.x core data model with
Alembic migrations. No DB-backed routes yet; that comes in Segment 5.

Do not add Review Robin domain functionality unless an issue explicitly asks for it.

## Testing expectations

Before considering a change complete, run:

```bash
pytest
```

If dependencies or tooling change, update `README.md`.
