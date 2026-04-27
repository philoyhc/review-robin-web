# AGENTS.md

## Project conventions

- Use Python 3.12+.
- Use FastAPI for the backend.
- Use Pydantic for request/response schemas.
- Use SQLAlchemy 2.x style when database models are introduced.
- Keep route handlers thin.
- Put business logic in service modules.
- Add or update tests for every behavior change.
- Prefer explicit types and clear names.
- Do not introduce a full frontend framework unless explicitly requested.
- Do not implement Microsoft authentication in app code unless explicitly requested; assume Azure App Service Easy Auth will provide authenticated identity headers in deployed environments.
- Keep changes small and PR-sized.

## Current stage

The project is currently in Segment 1: repository setup and skeleton app.

Do not add Review Robin domain functionality unless an issue explicitly asks for it.

## Testing expectations

Before considering a change complete, run:

```bash
pytest
```

If dependencies or tooling change, update `README.md`.
