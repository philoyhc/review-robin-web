# CLAUDE.md / AGENTS.md

Guidance for Claude Code (claude.ai/code), OpenAI Codex, Cursor, and any
other AI coding agent working in this repository.

> **`AGENTS.md` and `CLAUDE.md` are byte-identical twins.** Edit one,
> then run `cp CLAUDE.md AGENTS.md` (or the reverse) before committing.
> `tests/unit/test_doc_conventions.py` fails if they diverge.

## Project conventions

- Use Python 3.12+.
- Use FastAPI for the backend.
- Use Pydantic for request/response schemas.
- Use SQLAlchemy 2.x declarative style with `Mapped[]` and `mapped_column`.
  Do not import from `sqlalchemy.dialects.postgresql` in `app/db/models/` —
  Postgres-specific column types are deferred infrastructure (`guide/deferred_consolidated.md`).
- Keep route handlers thin.
- Put business logic in service modules.
- Add or update tests for every behavior change.
- Prefer explicit types and clear names.
- Do not introduce a full frontend framework unless explicitly requested.
- When working on a page, migrate any inline-styled buttons on it
  to the canonical `.btn` roles defined in `spec/ui_elements.md` §6
  (Primary / Secondary / Destructive [outline red] / Alert [filled
  amber] / Outline-amber [lock-card recovery]). Ask first if a button
  doesn't cleanly fit one of those roles — don't invent a new one
  without confirmation. (The pre-19B six-name scheme — Primary Outline /
  Alert Outline / Danger Outline — is superseded; `.alert-solid`
  collapses to Primary and `.danger` is a context class.) This and the
  lifecycle display-label mapping are enforced by
  `tests/unit/test_doc_conventions.py`.
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

**Consequential UI lands scaffold-first.** When a change adds a new
page, a new card, or a new navigation affordance, land the
**scaffold as its own reviewable slice before wiring any
behaviour**: the nav / button plus the page with every card as a
static placeholder — real copy and layout, inert controls (buttons
present but no-op or disabled). Iterate the page shape on that
placeholder, then wire each card / action in follow-up slices.
Agreeing the surface before attaching logic keeps UI churn out of
the wiring PRs and gives a cheap, early look at the real thing.

## Common commands

Run all of these from the repository root with the project virtualenv activated (`pip install -e .[dev]` once).

```bash
pytest                                   # full suite (SQLite, ~35s with -n auto)
pytest tests/integration/test_X.py       # one file
pytest tests/integration/test_X.py::test_name   # one test
pytest -k "expression"                   # match by name
ruff check .                             # lint (configured in pyproject.toml)

alembic upgrade head                     # apply migrations to local SQLite (./review_robin_web.db)
alembic downgrade -1                     # roll back one
alembic revision --autogenerate -m "..." # after editing models — ALWAYS hand-review the file

uvicorn app.main:app --reload            # local dev server on http://127.0.0.1:8000
```

`pytest` collection imports `app/`, so `PYTHONPATH=.` is sometimes needed when invoking from outside the venv (e.g. `PYTHONPATH=. pytest`). Tests use an in-memory SQLite whose schema is built directly from the ORM metadata (`Base.metadata.create_all`) per `tests/conftest.py` — the Alembic migration chain is still round-tripped on every PR by the `ci-postgres` job. `pytest-xdist` runs the suite in parallel (`pytest -n auto`).

**Migration portability matters.** Alembic migrations run against both SQLite (default; tests) and Postgres 16 (production + the `ci-postgres` job). SQLite is more permissive than Postgres in several places that have bitten us — `BOOLEAN DEFAULT 1` (use `sa.true()` / `sa.false()`), `WHERE bool_col = 1` (use `IS TRUE`), FK constraints not enforced at `DROP TABLE` time (drop FKs explicitly first, or recreate them on downgrade), and index / FK name mismatches between upgrade and downgrade (use the *original* names so downgrades further back in the chain can drop them). The `ci-postgres` job runs `alembic upgrade head` *and* the full `downgrade base + upgrade head` round-trip, so every migration must survive both directions on Postgres.

Local auth shortcut: set `ALLOW_FAKE_AUTH=true` plus `FAKE_AUTH_EMAIL`/`FAKE_AUTH_NAME` in `.env`. In deployed environments Azure Easy Auth supplies the identity headers and this flag must remain `false`.

## Architecture at a glance

A server-rendered FastAPI + Jinja monolith with a strict three-layer
split, plus a fourth seam. `spec/architecture.md` carries the layering
in full, including the per-package module map; the rules that bind
every change are:

1. **Route handlers** (`app/web/routes_*.py`, plus the
   `app/web/routes_operator/` and `app/web/routes_reviewer/` packages)
   parse the request, resolve identity via dependencies, and call
   services. No SQL, no business rules. New operator routes belong in
   their feature-area sub-module; slices import only from `_shared.py`
   and from outside the package — **no slice-to-slice imports**.
2. **Service modules** (`app/services/`) hold all business logic. Routes
   import these; templates never do.
3. **Models** (`app/db/models/`) are SQLAlchemy 2.x declarative
   (`Mapped[]` / `mapped_column`). **No `sqlalchemy.dialects.postgresql`
   imports here** — Postgres-specific column types are deferred
   infrastructure (`guide/deferred_consolidated.md`).
4. **`app/web/views/`** — the fourth seam — holds view-shape adapters — anything between a
   business rule and markup (e.g. computing a status label from
   instrument state) lives here, not in a service or a template.

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
- **Operator authorization** goes through `require_session_operator` (in `deps.py`), which combines `get_or_create_user` with a per-session permission check from `app/services/permissions.py`.
- **Participant authorization** goes through `require_reviewee_in_session` (W2) or `require_observer_in_session` (W3) for the reviewee `/me/sessions/{id}/results` and observer `/me/sessions/{id}/collation` surfaces. Both match the signed-in user's email (case-insensitive) against the session's roster + gate on `Reviewee.status` / `Observer.status` being `"active"`. Reviewees with non-email identifiers (anonymous IDs for analysis-only sessions) fail the reachability check — flagged on the Validate page by the `reviewees.unreachable_for_results` soft warning (W8).

### Templating conventions

- Templates extend `app/web/templates/base.html`. The base owns inline CSS for the entire app (no separate stylesheet, no JS build step beyond targeted progressive-enhancement scripts inline in templates). When adding new visual primitives, add a class to `base.html` rather than inline styles on individual templates.
- The canonical `.btn` roles and the `.page-grid` / `.bottom-grid` layout patterns live in `spec/ui_elements.md` — buttons in §6, layout primitives in §10. Refer to those roles when editing UI; see also `spec/operator_ui_concept.md` for page-level chrome.
- Operator pages render breadcrumbs via `app/web/breadcrumbs.py` helpers (`operator_root`, `operator_session_child`). Don't hand-roll breadcrumb HTML — call these.

### Database

- One `database_url` in `app/config.py` (Pydantic settings). Production reads Azure Postgres via `psycopg[binary]`; local dev uses SQLite. The same `alembic env.py` works for both.
- CI runs migrations *and* the full pytest suite against a real `postgres:16` service container (`ci-postgres` job in `.github/workflows/ci-postgres.yml`) on every PR, so dialect-only failures show up in CI alongside the SQLite pytest job.

## Where to look

- **`docs/status.md`** — implementation state + segment history. Authoritative.
- **`spec/README.md`** / **`docs/README.md`** / **`guide/README.md`** — the full, current index of each folder. Start here when the entry below isn't specific enough.
- **`spec/architecture.md`** — domain entities, layering, the per-package module map.
- **`spec/operator_ui_concept.md`** — operator chrome, setup nav, cross-page conventions.
- **`spec/ui_elements.md`** — the canonical `.btn` roles (§6) and layout primitives (§10).
- **`spec/session_home.md`** / **`spec/sessions_overview.md`** — Session Home and the lobby.
- **`spec/setup_pages.md`** — the five Setup pages: shared body shape, column orders.
- **`spec/assignments.md`** — assignment engine + the Assignments page.
- **`spec/instruments.md`** — Instrument entity + the per-session Instruments page.
- **`spec/settings_inventory.md`** — every persisted setting, plus browser-local UI state.
- **`spec/visibility_policy.md`** — the 3 × 2 audience × phase grid and `resolve_mode`.
- **`spec/participant_model.md`** — reviewee `/results` + observer `/collation` contracts.
- **`spec/audience_and_identity_model.md`** — audience taxonomy and auth posture.
- **`spec/lifecycle.md`** — the five-state session machine and its transitions.
- **`guide/todo_master.md`** — Done / Upcoming roadmap. Read for the sequence.
- **`guide/segment_*.md`** — current and upcoming segment plans; shipped ones in `guide/archive/`.
- **`guide/codebase_assessment_*.md`** — latest code-vs-spec snapshot.
- **`guide/deferred_consolidated.md`** — everything scoped but not scheduled.
- **`docs/practice-audit-2026-09-04.md`** — what gates a merge here, and which conventions are enforced by a check rather than by noticing.
- **`constitution.md`** — the six rules every change is held to (plan in / spec out; constant-derived gates only; maker ≠ checker; human verifier, no autonomous loop; reasoning travels with the change; retire rather than mechanise badly). Derived from `rrw_sdd_in_practice.md` §6.
- **`docs/security_posture.md`** / **`docs/database.md`** — deeper dives on those subsystems.
- **`docs/local_setup.md`** / **`docs/deployment_dev.md`** — developer setup and dev-deploy notes.

## Where work runs

- The human author does not run Python, alembic, or a database
  locally. There is no laptop dev loop.
- The agent's session container is the pre-PR gate: `pytest` and
  `ruff check .` must both pass there before pushing. Both run in CI
  (`ci.yml`) on every PR, alongside `ci-postgres.yml`, which
  round-trips the Alembic chain and runs the full suite against
  Postgres 16.
- End-to-end verification happens on the Azure dev slot after deploy,
  not in the agent's sandbox. When a change touches UI or anything
  the test suite can't exercise (templates, redirects, real auth),
  say so explicitly in the PR description rather than claiming it was
  verified.
- `docs/local_setup.md` and `ALLOW_FAKE_AUTH=true` exist for the
  agent's sandbox, not for a human dev loop.
- If dependencies or tooling change, update `README.md`.
