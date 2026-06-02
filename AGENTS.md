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
  Postgres-specific column types are deferred infrastructure (`guide/deferred_infra.md`).
- Keep route handlers thin.
- Put business logic in service modules.
- Add or update tests for every behavior change.
- Prefer explicit types and clear names.
- Do not introduce a full frontend framework unless explicitly requested.
- When working on a page, migrate any inline-styled buttons on it
  to the canonical `.btn` modifier classes defined in
  `spec/domain_assumptions.md` (Primary / Primary Outline / Alert / Alert
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

The app is a server-rendered FastAPI + Jinja monolith with a strict three-layer split:

1. **Route handlers** (`app/web/routes_*.py` plus the
   `app/web/routes_operator/` and `app/web/routes_reviewer/`
   packages) parse the request, resolve
   identity via dependencies, and call into services. They stay thin
   — no SQL, no business rules. The operator routes are split by
   feature area into sibling sub-modules (`_lobby.py`,
   `_settings.py`, `_session_home.py`, `_quick_setup.py`,
   `_setup_reviewers.py`, `_setup_reviewees.py`,
   `_setup_relationships.py`, `_setup_observers.py`,
   `_setup_invite.py`, `_assignments.py`, `_operations.py`,
   `_preview_surface.py`, `_workflow.py`, `_instruments.py`,
   `_instruments_band2.py` + `_instruments_pagination.py`
   (Segment 18N PR 3 carve — Band 2 routes + 18M page-break /
   reorder routes), `_extracts.py`, `_extract_data.py` (the
   Operations-strip Extract data tab — per-instrument lens
   cards + Data shaper), `_sys_admin.py`), with shared plumbing
   (the `Jinja2Templates` instance, lifecycle / edit-lock guards,
   Quick Setup cookie naming, the cross-slice Setup-roster
   import / redirect / field-label helpers, and per-instrument
   resolver + redirect helpers shared by the three instruments
   slices) in `_shared.py`. New operator routes belong in their
   feature-area sub-module. Slices import only from `_shared.py`
   and from outside the package — no slice-to-slice imports. The
   reviewer-side package (`app/web/routes_reviewer/`) carries the
   participant-facing surfaces under the `/me/` prefix: `_dashboard.py`
   (the cross-role lobby), `_surface.py` (the multi-page response
   form), `_summary.py` (post-submit summary), `_results.py` (the
   reviewee `/me/sessions/{id}/results` body), `_collation.py`
   (the observer `/me/sessions/{id}/collation` per-instrument
   3-row table + per-instrument CSV download; see
   `guide/observers.md`), `_invite.py`
   (magic-link landing), `_shared.py`. See
   `guide/archive/major_refactor.md` for the full split rationale and
   slice boundaries.
2. **Service modules** (`app/services/*.py`) hold all business logic — querying, mutation, validation, lifecycle transitions, audit-event emission. Routes import these; templates do not. The two big service packages are `app/services/instruments/` (split by concern: `_state.py` cross-slice plumbing including `_instrument_label`, `_display_fields.py`, `_response_fields.py` incl. `bulk_save_fields` + `validation_block_from_inline`, `_band1.py` link-rule editor, `_band2.py` Band 2 state save + Band 3 dual-write [Segment 18N PR 2 carve], `_pagination.py` 18M reorder + page-break helpers [Segment 18N PR 2 carve], `_instrument_crud.py` lifecycle + group/unit-of-review + column-widths + bulk toggles, `_field_presets.py`) and `app/services/responses/` (`_core.py` save / submit / state-rollup, `_group_reconciliation.py` Segment 13C / 18H group fan-out + reconcile machinery [Segment 18N PR 4 carve]). Each package's `__init__.py` re-exports the public surface so callers write `from app.services import instruments` / `from app.services import responses` unchanged. The Response Type Definitions slice (`_rtds.py`) retired 2026-05-26 alongside the `response_type_definitions` table. See `guide/archive/major_refactor.md` §12.A.
3. **Models** (`app/db/models/`) are SQLAlchemy 2.x declarative classes using `Mapped[]` / `mapped_column`. **Do not import `sqlalchemy.dialects.postgresql` here** — Postgres-specific column types are deferred infrastructure (`guide/deferred_infra.md`).

A small but important fourth seam:

- **`app/web/views/`** holds **view-shape adapters** that translate domain objects into the dataclasses / row tuples templates iterate over (e.g. `build_setup_rows` for the session-detail Session Setup card). Keep services business-logic-only and templates markup-only — anything in between (e.g. computing a status label string from instrument state) belongs here. The package is split by page / entity into sibling sub-modules (`_setup.py`, `_instruments.py`, `_validate.py`, `_quick_setup.py`, `_extract_data.py`, `_invitations.py`, `_responses.py`, `_filters.py`, `_previews.py`, `_assignments.py`, `_audit_log.py`, `_sort.py`, `_workflow_card.py`, `_reviewer_summary.py` (reviewer post-submit summary), `_reviewee_results.py` (reviewee `/results` body — Raw / Anonymized / Summarized aggregate primitives in `summarize_field`)); `__init__.py` re-exports the public surface so callers continue to write `from app.web import views` unchanged. See `guide/archive/major_refactor.md` §12.B.

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
- The six canonical button styles (Primary, Primary Outline, Alert, Alert Outline, Danger, Danger Outline) and the `.page-grid` / `.bottom-grid` layout patterns are documented in `spec/domain_assumptions.md` and `spec/operator_ui_concept.md` — refer to those names when editing UI.
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
  extraction is deferred.
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
  allow-list; VNet integration is deferred infrastructure (`guide/deferred_infra.md`).
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
- **`spec/domain_assumptions.md`** — UI vocabulary (button styles, typography knob, layout defaults).
- **`spec/architecture.md`** — domain entities, layering, conceptual hierarchy.
- **`spec/session_home.md`** / **`spec/sessions_overview.md`** — per-page specs for Session Home and the sessions lobby.
- **`spec/quick_setup_card_spec.md`** — Quick Setup card on Session Home (consolidated Submit, slot layout, lock-on-nav).
- **`spec/setup_pages.md`** — Setup Pages (Reviewers / Reviewees / Assignments / Instruments / Settings) — shared body shape, preview-table column orders, the visibility-toggle pattern.
- **`spec/assignments.md`** — Assignment engine + the Assignments operator page. Rule model, where the rule lives (Band 1 only post-Wave-5), synthetic Full Matrix default, self-review policy, group-scoped fan-out, reconcile + regenerate. (Replaces the retired `rule_based_assignment.md`; pre-2026-05-26 doc preserved at `spec/archive/rule_based_assignment.md`.)
- **`spec/instruments.md`** — Instrument entity + per-session Instruments operator page. Per-instrument card (Identity / Bands 1+2+3), "Not set" pill safety gate, group-scoped variant, Response Type Definitions card. (Consolidates the retired `instrument_builder.md` + `group_scoped_instruments.md`; pre-2026-05-26 docs preserved at `spec/archive/`.)
- **`spec/settings_inventory.md`** — Single-stop index of every operator- / per-session setting Review Robin Web persists, plus the browser-local UI-state primitives (cookies / localStorage / URL params).
- **`spec/visibility_policy.md`** — Per-instrument visibility policy (the 3 × 2 chip grid: Reviewers / Reviewees / Observers × Session-ongoing / Responses-released; Raw / Anonymized / Summarized modes; `instrument_view_policies` storage; `resolve_mode` view-time resolver). Cited by both the reviewee `/results` and the (paused) observer `/collation` surfaces.
- **`spec/participant_model.md`** — Active spec covering the participant-model behavior shipped 2026-05-30 → 2026-06-02: observer roster + per-session toggle + reviewee `/results` body across all three modes + Acknowledge gesture + observer collation MVP (cohort rule editor + per-instrument 3-row table + cohort-scoped CSV downloads). The umbrella design rationale + the S/P/W identifier glossary live in `guide/archive/participant_model_upgrade.md` (Appendix A); the W17 + W5 observer surface shipped 2026-06-02 (see `guide/observers.md` "Status"); remaining participant-model items (W20 / W21 email-side) sit in `guide/segment_14B_email_infrastructure.md` appendix.
- **`spec/audience_and_identity_model.md`** — Audience taxonomy (operator / reviewer / reviewee / observer / sysadmin) and auth posture.
- **`guide/segment_*.md`** — segment-by-segment plans (current and upcoming). The latest one names the current segment's contract. Older / shipped segment plans live in `guide/archive/`.
- **`guide/todo_master.md`** — Done / Upcoming roadmap. Read for the sequence. (The earlier `unfinished_business.md` catalog retired 2026-05-10 once all open items shipped or got absorbed into named segments; lives at `guide/archive/unfinished_business.md` for historical reference.)
- **`guide/observers.md`** — Standing notes for the observer participant role; the cohort editor (operator side) + the collation surface body + Anonymized CSV download (consumer side) shipped 2026-06-02 as the MVP.
- **`guide/clean_up.md`** — Standing punch-list of small-to-medium follow-ups identified by code review but not yet shipped. Pick from the top in idle moments; each item has its own context.
- **`guide/codebase_assessment_*.md`** — Snapshot of code state vs spec. Only the latest stays here; older snapshots retire to `guide/archive/`. The 2026-06-01 snapshot's Appendix §9 has concrete file-split proposals for the three production files at or near the 18N housekeeping threshold (`assignments.py`, `scheduled_events.py`, `session_config_io/_apply.py`).
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
