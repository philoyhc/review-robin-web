# CLAUDE.md / AGENTS.md

Guidance for Claude Code (claude.ai/code), OpenAI Codex, Cursor, and any
other AI coding agent working in this repository.

> **`AGENTS.md` and `CLAUDE.md` are byte-identical twins.** Edit one,
> then run `cp CLAUDE.md AGENTS.md` (or the reverse) before committing.
> `tests/unit/test_doc_references.py` fails if they diverge.

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
- **US spelling in new prose** (author's preference, 2026-09-07):
  *color*, *behavior*, *materialized*, *anonymized*. New or rewritten
  prose is US. Existing prose is left alone — live prose measured a dead
  heat between the two on that date, so this is a tie-breaker, not a
  campaign: fix a form when you are editing that line anyway, never as a
  sweep, and nothing enforces it, deliberately. Identifiers, filenames,
  DB columns and shipped labels are never renamed for spelling.
  **Where prose names a control, quote the control**: the visibility
  modes are `Anonymized` / `Summarized`
  (`app/services/visibility_policies.py`), so prose spells them that way
  whatever the surrounding convention.
- Keep changes small and PR-sized.

## Working approach

Land changes as small, reviewable slices. The natural unit is one
coherent feature step — a migration + its seed code, a service helper
set + the routes that call it, a template refactor + its tests — sized
so a reviewer can model the full contract in one sitting.

When a segment plan in `guide/` calls out internal slices, land them in
order across multiple PRs rather than collapsing them; use the plan's
"land X first as a self-contained Y" risk notes as the cut points. Don't
bundle independent changes (e.g. an unrelated bug fix) into the same PR.

**Consequential UI lands scaffold-first.** When a change adds a new
page, a new card, or a new navigation affordance, land the scaffold as
its own reviewable slice before wiring any behavior: the nav / button
plus the page with every card as a static placeholder — real copy and
layout, inert controls. Iterate the page shape on that placeholder, then
wire each card / action in follow-up slices.

**Write the `guide/` artefact shorter than feels complete.** A plan, a
sweep record or a findings register is read under pressure by someone
checking one thing. Budgets: a segment plan under ~250 lines, an item
under ~120, one line per file in a sweep record. `## Status` and
answered open questions **compact at close** rather than accumulating
(the `segment-plan` skill, "Revising a plan" and "Closing a segment"
step 4). Say it once, in the section that owns it; keep the conclusion
and the command that proves it, not the search that found it; cite a
section rather than reproducing it.

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
   services. **No business rules** — a scoped entity lookup that
   resolves a path parameter is fine and common; a floor, a quota, a
   cascade, or a multi-row computation that a service or a view would
   otherwise own is not (`spec/architecture.md` "Three-layer split").
   New operator routes belong in
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
- **Static assets** live in `app/web/static/`, served by the single `StaticFiles` mount at `/static` in `app/main.py`. It exists for the Guide's screencaps (`app/web/static/guide/`) — the first assets too large to inline — and is deliberately not a general asset pipeline; CSS stays inline in `base.html`. `app/` ships wholesale in the deploy artefact, so anything added here is shipped: `tests/integration/test_guide_screencaps.py` fails on a referenced-but-missing file *and* on a committed-but-unreferenced one.
- The canonical `.btn` roles and the `.page-grid` / `.bottom-grid` layout patterns live in `spec/ui_elements.md` — buttons in §6, layout primitives in §10. Refer to those roles when editing UI; see also `spec/operator_ui_concept.md` for page-level chrome.
- Operator pages render breadcrumbs via `app/web/breadcrumbs.py` helpers (`operator_root`, `operator_session_child`). Don't hand-roll breadcrumb HTML — call these.

### Database

- One `database_url` in `app/config.py` (Pydantic settings). Production reads Azure Postgres via `psycopg[binary]`; local dev uses SQLite. The same `alembic env.py` works for both.
- CI runs migrations *and* the full pytest suite against a real `postgres:16` service container (`ci-postgres` job in `.github/workflows/ci-postgres.yml`) on every PR, so dialect-only failures show up in CI alongside the SQLite pytest job.

## Where to look

- **`docs/status.md`** — implementation state + segment history from 2026-09-12. Authoritative. Older timeline rows are verbatim in `docs/status_history.md`.
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
  locally. There is no laptop dev loop. `docs/local_setup.md` and
  `ALLOW_FAKE_AUTH=true` exist for the agent's sandbox.
- The agent's session container is the pre-PR gate: `pytest -n auto`
  and `ruff check .` must both pass there before pushing, with `node`
  present so `tests/integration/test_inline_scripts_parse.py` runs
  rather than skips — the suite's only tool-gated skip, and a silent
  one, so read the skip list, not just the exit code. Both also run in
  CI (`ci.yml`) on every PR, alongside `ci-postgres.yml`.
- **The install belongs in whatever step has network**: `pip install
  -e .[dev]` before the agent phase. `requirements.txt` is the Azure
  deploy manifest and yields neither `pytest` nor `httpx`.
- **The web container builds itself.** `.claude/hooks/session-start.sh`
  is a SessionStart hook that does exactly that install: it resolves a
  3.12+ interpreter by name (the image's default `python3` is older than
  the floor `pyproject.toml` pins), builds `.venv/` from it, and exports
  `.venv/bin` on PATH for the session, so `pytest` and `ruff` are the
  project's own. It reuses a cached `.venv/` and rebuilds only when that
  one is missing or too old. It no-ops unless `CLAUDE_CODE_REMOTE=true`,
  so a local checkout keeps whatever environment its owner made.
- **A green `ruff` is not evidence.** Much of what gates a merge reads
  no Python and only `pytest` runs it: `tests/unit/test_doc_references.py`
  (the twins, every anchored backticked repo path in live prose —
  top-level `.md` in `spec/`, `docs/`, `guide/` **and the root**, this
  file included — and every `§N` pointer), `tests/unit/test_doc_conventions.py`
  (the checks derived from `app` constants), `tests/unit/test_guide_indexes.py` (a
  README row per `guide/` document), and
  `tests/unit/test_generated_tools_are_current.py` plus
  `tests/unit/test_contrast_audit.py` (both read `base.html`'s inline
  stylesheet). A lint-only run passes all of them by not running them.
- **Deleting a file can fail a doc gate in the rung that deletes it**,
  not the later rung that owns the spec sweep: an anchored backticked
  path in live prose dangles immediately, so plan that bullet forward
  in the manifest. Deleting a whole routing module trips
  `tests/unit/test_spec_coverage.py` the same way; deleting a single
  handler trips nothing.
- **If the suite could not run at all, say so in the PR body** and name
  what did. A disclosed gap beats an implied gate.
- **Stamping the instruction time is a campaign, not a standing rule.**
  `tools/pace_audit.py` can split *turn* (previous merge → first commit,
  `rrw_sdd_in_practice.md` §6.4) into the wait for an instruction and
  the build that followed it, when a slice's first commit carries
  `Instruction-Received: 2026-09-20T01:02:03Z`. One campaign has run,
  `#2495`–`#2516`, and §6.4 records what it found. **Stamp only when a
  figure is being re-taken** — start the slice with `date -u +%FT%TZ`
  and put the trailer on its first commit, not on fix commits answering
  a reader or CI. Otherwise don't; a slice without it is not wrong.
  **If you do stamp, put the trailer in the commit message's final
  block, beside `Co-Authored-By`**, so git's own trailer parser sees it:
  21 of the first 38 stamps sat in a paragraph of their own and were
  lost to that parser (19R Item 7). `tools/pace_audit.py` has read the
  line anywhere in the message since 2026-09-22, so a misplaced stamp
  still counts there; no gate checks a missing one.
- **Two cold readers, different cadences.** A slice is read cold before
  it is marked **ready for review** — not before it is pushed: a draft
  PR is not a merge, and an unpushed commit in an ephemeral container is
  a loss risk. The gates above are owed on **every** push regardless of
  what follows.

  `diff-reviewer`'s cadence is **per item, not per slice** (author's
  ruling, 2026-09-18, on a merge-history audit: the read catches real
  defects on code rungs, overclaimed only prose on plan and close rungs,
  and roughly doubles a slice's elapsed time — the figures are in
  `rrw_sdd_in_practice.md` §6.4 and `tools/pace_audit.py` re-takes
  them). Four rules:

  - **Prose-only slices take no read.** A slice is prose-only when its
    diff touches nothing under `app/`, `tests/` or `alembic/` — plan
    opens, rung closes, `Status` compaction, `docs/status.md` rows,
    README rows, registers, spec sweeps. Push, CI, merge. The
    doc-convention tests cover the pointers and `spec-writer` at the
    close covers the spec prose.
  - **Code slices inside an item ladder are read once per item.** Mark
    the rung you expect to be the item's last build rung; at that rung,
    before marking it ready for review, run `diff-reviewer` on the
    item's **cumulative** diff rather than the rung's —
    `git diff <main SHA before the item's rung 1 merged>..HEAD`. Record
    that base SHA in the rung-1 PR body so the last rung can cite it.
    Act on the findings in that PR. If a later rung reopens `app/` or
    `tests/` after the read, that rung takes its own read.
  - **A code slice outside any ladder** — a one-off fix, a CI repair, a
    scaffold — still takes a read on its own diff.
  - **Say what the reads found.** At each item close, the `Status` block
    records how many reads the item took and what they turned up, so the
    next practice audit can re-measure `constitution.md` III's "when
    run" against this cadence rather than the one it replaced.

  `spec-writer` is unchanged: **at the close** (`segment-plan`, "Closing
  a segment" step 3), and earlier only when the slice touches `spec/`,
  touches a path its plan's `Doc impact` names, or is the closing slice.
  Outside a close `spec-writer` may not re-align a spec to the code, so
  a deferred slice loses a report, not an alignment — and a later slice
  can falsify what an earlier pass verified.
- End-to-end verification happens on the Azure dev slot after deploy,
  not in the agent's sandbox. When a change touches UI or anything
  the test suite can't exercise (templates, redirects, real auth),
  say so explicitly in the PR description rather than claiming it was
  verified.
- If dependencies or tooling change, update `README.md`.
