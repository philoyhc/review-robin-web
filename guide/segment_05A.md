# Segment 5A — Operator Session Setup MVP (Agreed Plan)

**Project:** Review Robin Web
**Repository:** <https://github.com/philoyhc/review-robin-web>
**Parent plan:** `guide/segment_05_operator_session_setup_mvp_plan.md`
**Purpose:** Lock in the implementation choices for Segment 5 — including
the infrastructure work inherited from Segment 4A — so the next sessions
can implement without re-litigating the design.

This document is a **delta** on the parent plan. The parent plan still
governs scope, success criteria, and out-of-scope items. The §3.1
"Inherited from Segment 4A" block in the parent plan is folded into the
infra PR below.

> **Amendment, 2026-04-28:** §3.5 (local Docker Compose for Postgres)
> has been deferred. Local development continues to use SQLite; Postgres
> parity is enforced via CI (§3.6) and the migration-on-deploy step
> (§3.4). See §3.5 for full reasoning. Other sections updated to match:
> §4 (file layout), §8 (docs), §9 (deferrals), §10 (PR 1 checklist),
> §11 (risks).

---

## 1. Scope (unchanged from parent plan + 4A inheritance)

The first operator-facing workflow plus the live-database infrastructure
that supports it:

- Provision dev Postgres (Azure + local Docker Compose).
- Run migrations on deploy.
- Operator session list / create / detail pages.
- Server-side permission checks.
- Session creation audit event.
- Tests covering create / list / detail / access-denial.

---

## 2. Branch and PR strategy

Segment 5 is too large for a single PR. Split into **two** PRs against
`main`, in order:

### PR 1 — Infrastructure (`claude/segment-5-postgres-infra`)

Postgres provisioning, secret config, local Docker Compose,
migration-on-deploy step, Postgres CI smoke. **No app code changes.** The
existing app continues to run on its current SQLite default; only the
deployed App Service flips over to Postgres after the new App Setting is
applied.

### PR 2 — Operator surface (`claude/segment-5-operator-sessions`)

Routes, services, templates, tests. Lands once PR 1 is merged and a
real-Postgres smoke test on the dev environment has confirmed migrations
apply cleanly.

A third PR for any UI polish is fine but not required up front.

---

## 3. Decisions

### 3.1 Azure Postgres

- **Resource type:** Azure Database for PostgreSQL **Flexible Server**.
- **Region:** **Southeast Asia**, matching the dev App Service.
- **Tier:** **Burstable B1ms** (1 vCore, 2 GB RAM). Smallest dev tier.
- **Storage:** 32 GB (smallest).
- **Postgres version:** 16.
- **High availability:** disabled (dev tier).
- **Backups:** default 7-day retention; this is fine for dev.

### 3.2 Networking

- **Public access** with firewall rules:
  - "Allow public access from Azure services and resources within Azure
    to this server" — **enabled** (the easiest way to let the App Service
    reach the DB without VNet integration).
  - Add the developer's current public IP to the firewall list for
    running migrations and one-off psql connections.
- **VNet / private endpoints:** deferred to **Segment 13**. Public
  access with firewall rules is acceptable for an internal-only dev pilot.

### 3.3 Secret management

- **`DATABASE_URL` is stored as an App Service App Setting**, not in Key
  Vault. Format:
  ```text
  postgresql+psycopg://<user>:<password>@<server>.postgres.database.azure.com:5432/<dbname>?sslmode=require
  ```
- **GitHub Actions secret** `DATABASE_URL` (same value) is added to the
  repository for the migration-on-deploy step.
- **Key Vault references** for App Settings are deferred to **Segment 13**.

### 3.4 Migration on deploy

- A new job runs **between build and deploy** in
  `.github/workflows/main_app-review-robin-web-dev.yml`:
  1. Install Python + dependencies.
  2. Run `alembic upgrade head` against Azure Postgres using the
     `DATABASE_URL` secret.
  3. **Fail the workflow if the migration fails** — the deploy job is
     skipped, so the app never ships against a stale schema.
- Migrations always run before the App Service swap. There is no startup
  hook running migrations; that pattern is fragile under concurrent
  deploys.

### 3.5 Local Postgres — deferred

**Original decision (superseded):** add a `docker-compose.yml` at the
repo root for a local Postgres 16 container so contributors can
reproduce Postgres-only issues on their own machine.

**Amended decision:** local Docker Compose is **deferred**. Reasons:

- The developer works across multiple machines (home, office, laptop);
  installing and maintaining Docker on each is friction we don't yet
  need.
- For Segment 5 the new code is pure SQLAlchemy ORM with no raw SQL or
  dialect-specific features, so the Postgres-vs-SQLite divergence risk
  is small.
- Postgres parity is still enforced — by the CI smoke job (§3.6) on
  every PR, and by the migration-on-deploy step (§3.4) on every deploy.

**What this means in practice:**

- **SQLite remains the local default** in `app/config.py`. Local
  development and `pytest` continue to run against
  `sqlite:///./review_robin_web.db`.
- **No `docker-compose.yml` is added in PR 1.**
- **No new local-Postgres documentation** is added to
  `guide/local_setup.md` or `docs/database.md` beyond a short note that
  local Postgres setup is intentionally deferred and that contributors
  who want it can run any local Postgres they prefer and set
  `DATABASE_URL` accordingly.
- `.env.example` still shows a commented-out `DATABASE_URL` line as a
  reference for "switch to Postgres if you want to."

**When to revisit:** install Docker (or another local Postgres) on
whichever machine the developer is at, *if and only if* a
Postgres-specific bug appears that can't be diagnosed from CI logs or
Azure App Service logs. Until then, CI is the portability guard.

### 3.6 CI

With local Docker deferred (§3.5), the CI Postgres smoke job becomes
the **primary** portability guard rather than a secondary check.

- **`ci.yml` keeps running pytest against SQLite** (fast, ~1s, runs on
  every PR).
- **A new `ci-postgres-migration.yml` job** is added that:
  - spins up a `postgres:16` service container;
  - runs `alembic upgrade head` against it;
  - then runs `alembic downgrade base && alembic upgrade head` to
    confirm round-trip on Postgres.
- This job is **required to pass** before merging any PR that touches
  models or migrations.
- The full Postgres-against-Docker pytest matrix is deferred to
  **Segment 13**.

### 3.7 Permission model

- Access to a session is granted via a `SessionOperator` row. The
  Segment 4 model already supports this.
- On session creation: insert a `SessionOperator(user, session,
  role="owner")` in the same transaction.
- On session view: `permissions.user_can_view_session(db, user, session)`
  returns `True` iff a `SessionOperator` row exists for that
  `(user, session)`. No `created_by_user_id` shortcut — keep one source
  of truth.
- Multi-operator support is **structurally allowed** but no UI exists
  to add a second operator until a later segment.

### 3.8 UI / templates

- **Jinja2 templates only**, no CSS framework.
- A new `app/web/templates/base.html` provides shared layout (head,
  styling, sign-out link). All operator pages extend it.
- `app/web/templates/me_debug.html` is **not** migrated to extend
  `base.html` in this segment — that's a cosmetic refactor and out of
  scope here.
- Inline `<style>` block in `base.html` for now. CSS extraction is a
  Segment 13 concern.

### 3.9 Service / schema layout

- Services live in `app/services/` (new package): `sessions.py`,
  `permissions.py`, `audit.py`. Names are deliberately shorter than the
  parent plan's `*_service.py` — `from app.services.sessions import
  create_session` reads better than
  `from app.services.session_service import create_session`.
- Pydantic request/response schemas live in `app/schemas/`:
  `sessions.py` for `SessionCreate` and `SessionRead`.

### 3.10 Test strategy

- `tests/integration/test_operator_sessions.py` uses the FastAPI
  `TestClient`.
- A new `tests/integration/conftest.py` reuses the migrated in-memory
  SQLite engine from `tests/db/conftest.py`, then **overrides the FastAPI
  `get_db` and `get_current_user` dependencies** in `app.dependency_overrides`.
- **Tests run against SQLite, not Postgres.** The migration round-trip
  on real Postgres happens in CI (§3.6) and on first deploy. This keeps
  unit / integration tests fast.

---

## 4. File and folder layout

### Added in PR 1 (infra)

```text
.github/workflows/
  main_app-review-robin-web-dev.yml     # MODIFIED: migrate-on-deploy step
  ci-postgres-migration.yml             # NEW: Postgres migration smoke

.env.example                            # MODIFIED: add Postgres URL example (commented)
docs/database.md                        # MODIFIED: note that local Postgres is deferred
deployment_dev.md                       # MODIFIED: Postgres + migration step

# No app/ changes in PR 1.
# No docker-compose.yml — local Docker is deferred (§3.5).
```

### Added in PR 2 (app)

```text
app/
  schemas/
    __init__.py
    sessions.py                         # SessionCreate, SessionRead
  services/
    __init__.py
    sessions.py                         # create_session, list_for_user, get_for_user
    permissions.py                      # user_can_view_session
    audit.py                            # write_event helper
  web/
    routes_operator.py                  # /operator/sessions* routes
    templates/
      base.html                         # shared layout
      operator/
        sessions_list.html
        session_new.html
        session_detail.html

tests/
  integration/
    __init__.py
    conftest.py                         # TestClient + dependency overrides
    test_operator_sessions.py           # 7 tests per parent plan §8
```

`app/main.py` mounts the new operator router.

---

## 5. Routes (PR 2)

| Method | Path                              | Auth     | What it does                                |
|--------|-----------------------------------|----------|---------------------------------------------|
| GET    | `/operator/sessions`              | required | HTML list of sessions where user is operator|
| GET    | `/operator/sessions/new`          | required | Empty create form                           |
| POST   | `/operator/sessions`              | required | Create session + SessionOperator + audit, redirect to detail |
| GET    | `/operator/sessions/{session_id}` | required | HTML detail view (403 if not operator)      |

All routes use the existing `get_current_user` dependency from Segment 3
(so they get either real Easy Auth identity in Azure or a fake user in
local dev with `ALLOW_FAKE_AUTH=true`). They additionally depend on the
new `get_db` dependency.

`get_current_user` returns `AuthenticatedUser` (a frozen dataclass with
no DB id). For DB operations, the route dependency
`get_or_create_user(current_user, db)` maps it to a `User` row, creating
one on first sign-in. This is the **first time we persist a user**, and
this segment is the natural place to do it.

---

## 6. Audit event shape

```python
AuditEvent(
    session_id=session.id,
    actor_user_id=user.id,
    event_type="session.created",
    severity="info",
    summary=f"Session {session.code} created",
    detail={"session_id": session.id, "code": session.code, "name": session.name},
    correlation_id=request_correlation_id(),  # cheap uuid4 hex per request
)
```

`event_type` strings follow the pattern `<resource>.<action>` to keep
log/dashboard queries simple later.

---

## 7. Tests (parent plan §8 + one extra)

`tests/integration/test_operator_sessions.py`, eight tests:

1. Authenticated user can `POST /operator/sessions` and is redirected to
   detail.
2. Creating a session inserts a `SessionOperator` row.
3. Creating a session writes a `session.created` audit event.
4. Operator sees their session in `GET /operator/sessions`.
5. Operator can `GET /operator/sessions/{id}` for their own session.
6. Another user gets **403** on `GET /operator/sessions/{id}` for a
   session they do not operate.
7. `POST /operator/sessions` with missing `name` returns **422** (or the
   form re-renders with an error — pick one and stick to it; 422 is
   simpler).
8. Listing sessions for an authenticated user with no sessions returns a
   200 page with an empty state.

---

## 8. Documentation

- `docs/database.md` gets a short section noting that local Postgres
  setup is deliberately deferred (§3.5) and pointing contributors who
  want it at any local Postgres install with the appropriate
  `DATABASE_URL`.
- `deployment_dev.md` gets a section on the Postgres resource, the
  `DATABASE_URL` App Setting, and the migration-on-deploy step.
- `guide/local_setup.md` is **not** modified in this segment — local
  setup is unchanged (still SQLite).
- A new `docs/operator_session.md` is **not** added in this segment —
  the routes are simple enough that route-level docstrings + the route
  table in §5 above are enough. A user-facing operator guide can land
  with Segment 9 or 10.

---

## 9. Out of scope (per parent plan §3 + new deferrals)

Carried over from parent plan:

- Reviewer or reviewee upload, assignment modes, full instrument config,
  activation, invitations, reviewer pages, role management UI, rich
  dashboard cards, production styling.

Newly deferred to specific later segments:

| Item                                                | Deferred to |
|-----------------------------------------------------|-------------|
| Local Docker Compose / local Postgres setup         | When needed (see §3.5); no fixed segment |
| Key Vault references for App Settings               | Segment 13  |
| VNet integration / private endpoints for Postgres   | Segment 13  |
| Full Postgres-against-Docker pytest matrix in CI    | Segment 13  |
| CSS extraction / framework / design system          | Segment 13  |
| Migrating `me_debug.html` to extend `base.html`     | Segment 13  |
| Multi-operator add/remove UI                        | Segment 11+ |

---

## 10. Verification checklist

### PR 1 (infra)

- [ ] Azure Postgres firewall rules allow the dev App Service ("Allow
  Azure services") and the developer's current public IP.
- [ ] `psql` from the developer machine to the Azure dev DB succeeds
  (sanity-checks firewall + app user credentials before touching CI).
- [ ] `DATABASE_URL` is set as an App Service App Setting on
  `app-review-robin-web-dev`.
- [ ] `DATABASE_URL` is set as a GitHub Actions secret on the repo.
- [ ] `ci-postgres-migration.yml` passes on the PR (migration applies +
  round-trips against a `postgres:16` service container).
- [ ] After merge: the dev deploy workflow runs the new migration step
  successfully against Azure Postgres.
- [ ] `curl https://.../health` (anonymous) still returns 200 after deploy
  — i.e. the app starts even though it doesn't yet read the DB.

### PR 2 (app)

- [ ] `pytest` green locally (24 existing + 8 new = 32 minimum).
- [ ] CI green on PR.
- [ ] After deploy: signed-in browser → `/operator/sessions` →
  empty-state page renders.
- [ ] After deploy: create-session form → submit → redirect to detail
  page → session visible in list.
- [ ] After deploy: a second user (or signed-out incognito then signed
  in as a different account, if available) gets **403** on the first
  user's session detail URL.

---

## 11. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Migration runs on SQLite but breaks on Postgres | PR 1's CI smoke job catches it before any deploy. |
| Postgres-only bug reaches Azure with no local way to reproduce it (consequence of §3.5 deferral) | Diagnose first from CI logs and Azure App Service logs. If that's not enough, install a local Postgres on the current machine *then* — we accept this one-off cost rather than pay the multi-machine Docker setup cost up front. |
| `DATABASE_URL` leaks to logs | Pydantic settings doesn't log values; gunicorn / uvicorn don't log env vars; never echo the URL in app code. |
| Migration-on-deploy fails halfway | The migration step fails the workflow before the deploy job runs. The dev DB may be in a partial state — fix the migration, push, redeploy. (Production migrations would need more care; that's S13.) |
| First operator user is created without explicit consent | Acceptable — the user has already authenticated through Easy Auth. The User row is just persistence of the same identity Azure has already verified. |
| Permission check missed on a new route in a future segment | Add a small "permission required" comment standard in `routes_operator.py`; later: a dependency-injection pattern (`Depends(require_session_operator)`) once the pattern stabilizes (Segment 6 or 7). |

---

## 12. Done when

### PR 1

- Azure Postgres exists and is reachable from the dev App Service.
- `DATABASE_URL` is set as both an App Service App Setting and a GitHub
  Actions secret.
- The migration-on-deploy step has run successfully at least once.
- Local Docker Compose setup is documented and works.

### PR 2

- All four operator routes work in the deployed dev environment.
- A signed-in user can create, list, and view their own sessions.
- A signed-in user is blocked from sessions they do not operate.
- `session.created` audit events are written.
- All 8 integration tests pass.

Next segment after both PRs merge: **Segment 6 — Import and validation
MVP**.
