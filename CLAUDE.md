# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@AGENTS.md

## Common commands

Run all of these from the repository root with the project virtualenv activated (`pip install -e .[dev]` once).

```bash
pytest                                   # full suite (SQLite, ~12s)
pytest tests/integration/test_X.py       # one file
pytest tests/integration/test_X.py::test_name   # one test
pytest -k "expression"                   # match by name
ruff check .                             # lint (configured in pyproject.toml)

alembic upgrade head                     # apply migrations to local SQLite (./review_robin_web.db)
alembic downgrade -1                     # roll back one
alembic revision --autogenerate -m "..." # after editing models — ALWAYS hand-review the file

uvicorn app.main:app --reload            # local dev server on http://127.0.0.1:8000
```

`pytest` collection imports `app/`, so `PYTHONPATH=.` is sometimes needed when invoking from outside the venv (e.g. `PYTHONPATH=. pytest`). Tests use an in-memory SQLite that runs `alembic upgrade head` once per session via `tests/conftest.py`.

Local auth shortcut: set `ALLOW_FAKE_AUTH=true` plus `FAKE_AUTH_EMAIL`/`FAKE_AUTH_NAME` in `.env`. In deployed environments Azure Easy Auth supplies the identity headers and this flag must remain `false`.

## Architecture at a glance

The app is a server-rendered FastAPI + Jinja monolith with a strict three-layer split:

1. **Route handlers** (`app/web/routes_*.py`) parse the request, resolve identity via dependencies, and call into services. They stay thin — no SQL, no business rules.
2. **Service modules** (`app/services/*.py`) hold all business logic — querying, mutation, validation, lifecycle transitions, audit-event emission. Routes import these; templates do not.
3. **Models** (`app/db/models/`) are SQLAlchemy 2.x declarative classes using `Mapped[]` / `mapped_column`. **Do not import `sqlalchemy.dialects.postgresql` here** — Postgres-specific column types are deferred to Segment 14.

A small but important fourth seam:

- **`app/web/views.py`** holds **view-shape adapters** that translate domain objects into the dataclasses / row tuples templates iterate over (e.g. `build_setup_rows` for the session-detail Session Setup card). Keep services business-logic-only and templates markup-only — anything in between (e.g. computing a status label string from instrument state) belongs in `views.py`.

### Identity and auth

- `app/auth/identity.py` parses Azure Easy Auth headers (`X-MS-CLIENT-PRINCIPAL` and friends) into an `AuthenticatedUser`. When `ALLOW_FAKE_AUTH=true`, a fake user is injected.
- `app/web/deps.py` exposes `get_current_user` and `get_or_create_user` (the latter ensures the auth principal has a row in `users`). Routes depend on these, not on the headers directly.
- Operator authorization goes through `require_session_operator` (also in `deps.py`), which combines `get_or_create_user` with a per-session permission check from `app/services/permissions.py`.

### Templating conventions

- Templates extend `app/web/templates/base.html`. The base owns inline CSS for the entire app (no separate stylesheet, no JS build step). When adding new visual primitives, add a class to `base.html` rather than inline styles on individual templates.
- The four canonical button styles (Primary, Primary Outline, Danger, Danger Outline) and the two-column / bottom-grid layout patterns are documented in `assumptions.md` and `spec/operator_map.md` — refer to those names when editing UI.
- Operator pages render breadcrumbs via `app/web/breadcrumbs.py` helpers (`operator_root`, `operator_session_child`). Don't hand-roll breadcrumb HTML — call these.

### Database

- One `database_url` in `app/config.py` (Pydantic settings). Production reads Azure Postgres via `psycopg[binary]`; local dev uses SQLite. The same `alembic env.py` works for both.
- CI runs migrations against a real `postgres:16` service container (`ci-postgres-migration` job) on every PR, so dialect-only failures show up in CI even though tests run on SQLite.

## Where to look

- **`docs/status.md`** — current implementation state and segment history. Authoritative.
- **`guide/segment_*.md`** — segment-by-segment plans (current and upcoming). The latest one names the current segment's contract. Older / shipped segment plans live in `guide/archive/`.
- **`spec/operator_map.md`** — operator-page surface and cross-page conventions (chrome, breadcrumbs, layout patterns).
- **`assumptions.md`** — UI vocabulary (button styles, typography knob, layout defaults).
- **`docs/authentication.md`** / **`docs/database.md`** — deeper dives on those subsystems.

## Workflow notes

- The human author does not run Python locally for routine work. The agent's session container is the pre-PR gate — `pytest` (and `ruff` once wired into CI) must pass there before pushing. End-to-end verification happens on the Azure dev slot after deploy; if a change touches UI/redirects/auth that the test suite can't exercise, say so explicitly in the PR description rather than claiming verification.
- Land changes as small, reviewable slices following the plans in `guide/`. Don't bundle independent concerns (e.g. an unrelated bug fix) into a feature PR.
