# CLAUDE.md / AGENTS.md

Guidance for Claude Code (claude.ai/code), OpenAI Codex, Cursor, and any
other AI coding agent working in this repository.

> **`AGENTS.md` and `CLAUDE.md` are byte-identical twins.** Edit one,
> copy it to the other — they must stay in sync. No automation enforces
> this yet; if you change one, run `cp CLAUDE.md AGENTS.md` (or the
> reverse) before committing.

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
- When working on a page, migrate any inline-styled buttons on it
  to the canonical `.btn` modifier classes defined in
  `spec/assumptions.md` (Primary / Primary Outline / Alert / Alert
  Outline / Danger / Danger Outline). Ask first if a button
  doesn't cleanly fit one of those six named styles — don't invent
  a new one without confirmation.
- Do not implement Microsoft authentication in app code unless
  explicitly requested; assume Azure App Service Easy Auth will provide
  authenticated identity headers in deployed environments.
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

### Audit events

Every mutating service writes an `audit_events` row via
`app.services.audit.write_event(...)`. The `detail` JSON follows the
canonical envelope schema documented in `spec/architecture.md`
"Audit-event detail schema" — pick exactly one payload envelope
(`audit.changes(...)` / `.snapshot(...)` / `.counts(...)` /
`.set_changes(...)`), pass `session=` for top-level identity slots,
and use the orthogonal slots (`reason=` / `refs=` / `context=`) for
event-triggering cause / cross-entity int PKs / descriptive scalars.
A per-event-type allowlist in `EVENT_SCHEMAS` validates each emit
on write — strict mode in tests fails any drift; production mode
logs and writes through. **When you add a new emitter, register its
event_type in `EVENT_SCHEMAS`** or the strict-mode test gate will
reject it.

### Identity and auth

- `app/auth/identity.py` parses Azure Easy Auth headers (`X-MS-CLIENT-PRINCIPAL` and friends) into an `AuthenticatedUser`. When `ALLOW_FAKE_AUTH=true`, a fake user is injected.
- `app/web/deps.py` exposes `get_current_user` and `get_or_create_user` (the latter ensures the auth principal has a row in `users`). Routes depend on these, not on the headers directly.
- Operator authorization goes through `require_session_operator` (also in `deps.py`), which combines `get_or_create_user` with a per-session permission check from `app/services/permissions.py`.

### Templating conventions

- Templates extend `app/web/templates/base.html`. The base owns inline CSS for the entire app (no separate stylesheet, no JS build step beyond targeted progressive-enhancement scripts inline in templates). When adding new visual primitives, add a class to `base.html` rather than inline styles on individual templates.
- The six canonical button styles (Primary, Primary Outline, Alert, Alert Outline, Danger, Danger Outline) and the `.page-grid` / `.bottom-grid` layout patterns are documented in `spec/assumptions.md` and `spec/operator_ui_concept.md` — refer to those names when editing UI.
- Operator pages render breadcrumbs via `app/web/breadcrumbs.py` helpers (`operator_root`, `operator_session_child`). Don't hand-roll breadcrumb HTML — call these.

### Database

- One `database_url` in `app/config.py` (Pydantic settings). Production reads Azure Postgres via `psycopg[binary]`; local dev uses SQLite. The same `alembic env.py` works for both.
- CI runs migrations *and* the full pytest suite against a real `postgres:16` service container (`ci-postgres` job in `.github/workflows/ci-postgres.yml`) on every PR, so dialect-only failures show up in CI alongside the SQLite pytest job.

## Stack summary

- **Language.** Python 3.12+.
- **Web framework.** FastAPI on Starlette ASGI; uvicorn for local
  dev, gunicorn + uvicorn workers in production.
- **Templates.** Jinja2, server-rendered. **No frontend framework
  and no JS build step.** Forms are plain `<form method="post">`;
  navigation state lives in URL fragments / query params
  (e.g. `?validated=1`, `#upload-csv`). Targeted inline JS for
  progressive enhancement (e.g. the Save/Edit lock toggle and
  live-preview render on the Instruments page) is fine; framework
  / build pipeline is not. Inline `<style>` in `base.html`; CSS
  extraction is a Segment 14 concern.
- **Schemas / config.** Pydantic 2 (`pydantic` for request /
  response shapes, `pydantic-settings` for env config).
- **ORM + migrations.** SQLAlchemy 2.x declarative
  (`Mapped[]` + `mapped_column`); Alembic for migrations. No
  `sqlalchemy.dialects.postgresql` imports in `app/db/models/`
  per the convention above.
- **Database.** Postgres 16 (Azure Postgres Flexible Server,
  Burstable B1ms, Southeast Asia) in deployed environments;
  in-memory SQLite per test session for `pytest` by default.
  CI also runs the full pytest suite against a `postgres:16`
  service container (the `ci-postgres` workflow), and the
  `engine` fixture in `tests/conftest.py` honours
  `TEST_DATABASE_URL` / `DATABASE_URL` so the same suite covers
  both dialects.
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
- **CI.** SQLite `pytest` job + a `ci-postgres` job that
  round-trips Alembic and runs the full `pytest` suite against
  a `postgres:16` service container on every PR.
- **Tooling.** `pytest` + `httpx` (TestClient), `ruff` (lint).

## Where to look

- **`docs/status.md`** — current implementation state and segment history. Authoritative.
- **`spec/operator_ui_concept.md`** — operator-page surface and cross-page conventions (chrome, setup nav, lock card, layout patterns).
- **`spec/assumptions.md`** — UI vocabulary (button styles, typography knob, layout defaults).
- **`spec/architecture.md`** — domain entities, layering, conceptual hierarchy.
- **`spec/functional_spec.md`** — technology-neutral functional spec.
- **`spec/session_home.md`** / **`spec/sessions_overview.md`** — per-page specs for Session Home and the sessions lobby.
- **`spec/quick_setup_card_spec.md`** — Quick Setup card on Session Home (consolidated Submit, slot layout, lock-on-nav).
- **`spec/setup_pages.md`** — Setup Pages (Reviewers / Reviewees / Assignments / Instruments / Settings) — shared body shape, preview-table column orders, the visibility-toggle pattern.
- **`spec/rule_based_assignment.md`** — Advanced-mode assignment engine + UI (§7.1 covers the Rule Based card on the Assignments page; §7.2 covers the Rule Builder page).
- **`guide/segment_*.md`** — segment-by-segment plans (current and upcoming). The latest one names the current segment's contract. Older / shipped segment plans live in `guide/archive/`.
- **`guide/todo_master.md`** — Done / Upcoming roadmap. Read for the sequence; `guide/unfinished_business.md` is the per-item catalog.
- **`docs/authentication.md`** / **`docs/database.md`** / **`docs/imports.md`** — deeper dives on those subsystems.
- **`docs/local_setup.md`** / **`docs/deployment_dev.md`** — developer setup and dev-deploy notes.

The three doc folders each have their own README (`spec/README.md`,
`docs/README.md`, `guide/README.md`) that spell out the role and list
the contents.

## Workflow notes

- The human author does not run Python locally for routine work. The agent's session container is the pre-PR gate — `pytest` (and `ruff` once wired into CI) must pass there before pushing. End-to-end verification happens on the Azure dev slot after deploy; if a change touches UI/redirects/auth that the test suite can't exercise, say so explicitly in the PR description rather than claiming verification.
- Land changes as small, reviewable slices following the plans in `guide/`. Don't bundle independent concerns (e.g. an unrelated bug fix) into a feature PR.

## Where work runs

- The human author does not run Python, alembic, or a database
  locally. There is no laptop dev loop.
- The agent's session container is the primary pre-PR gate: run
  `pytest` (and lint, once it's wired into CI) there before pushing.
- End-to-end verification happens on the Azure dev slot after deploy,
  not in the agent's sandbox. When a change touches UI or anything
  the test suite can't exercise (templates, redirects, real auth),
  say so in the PR description rather than claiming it was verified.
- `docs/local_setup.md` and `ALLOW_FAKE_AUTH=true` exist for the
  agent's sandbox, not for a human dev loop.

## Testing expectations

Before considering a change complete, run:

```bash
pytest
```

If dependencies or tooling change, update `README.md`.
