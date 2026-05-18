# Local Setup

This guide covers everything needed to run Review Robin Web locally for
development. It is the source of truth for developer setup; the README only
shows the minimal happy path.

If you only want to run the tests once, jump to [§4 First-time setup](#4-first-time-setup).

---

## 1. What you need installed

### Required

| Tool      | Minimum version | Notes                                     |
|-----------|-----------------|-------------------------------------------|
| Git       | any recent      | For cloning and committing.               |
| Python    | **3.12**        | The project is pinned to 3.12+ in `pyproject.toml`. Earlier versions will not install. |
| pip       | bundled with Python | Used via `python -m pip`.             |

### Optional but useful

| Tool          | Why                                                       |
|---------------|-----------------------------------------------------------|
| VS Code       | Recommended editor; works well with the FastAPI / Pydantic / SQLAlchemy stack. |
| GitHub CLI (`gh`) | Easier branch and PR workflows.                       |
| Azure CLI (`az`) | Needed only if you administer the dev App Service (e.g. tweaking Easy Auth settings via `az webapp auth`). Not needed for day-to-day app development. |

### Not needed yet

- **Docker** — only required from Segment 5 onward when local PostgreSQL
  enters the picture. SQLite covers Segment 4.
- **PostgreSQL client** — same reasoning. SQLite needs no client tools.
- **MSAL / Azure SDK** — authentication is handled by Azure App Service
  Easy Auth in deployed environments and a fake-auth fallback locally;
  the app never runs an OAuth/OIDC flow itself.

---

## 2. Repository layout (developer's-eye view)

```text
review-robin-web/
  app/                      Application code
    main.py                 FastAPI app factory
    config.py               Pydantic settings (env vars)
    auth/                   Easy Auth identity parser
    db/                     SQLAlchemy 2.x base, session, models
      models/               12 domain models (User, ReviewSession, ...)
    web/                    Routes and Jinja templates

  alembic/                  Database migrations
    versions/               Migration files (do not edit after merge)
    env.py                  Reads database_url from app.config.settings
  alembic.ini               Alembic config (sqlalchemy.url left blank by design)

  tests/                    pytest suite
    db/                     Database/model tests with in-memory SQLite

  guide/                    Workplan and segment-level planning docs
  docs/                     Project documentation (auth, database, ...)

  .env.example              Template for local environment variables
  .env                      Your local env vars (NOT committed)
  pyproject.toml            Dependencies + tool config
  requirements.txt          Mirror of runtime deps for Azure deploy
  AGENTS.md / CLAUDE.md     Conventions for AI coding agents
  CONTRIBUTING.md           Human contributor workflow
```

---

## 3. Files you need to create locally

The repo intentionally does not commit machine-specific files. You'll need:

### `.env` (required for `/me` and `/me/debug` to work locally)

Copy the template and turn on fake auth so the auth-gated routes return a
user instead of a 401:

```bash
cp .env.example .env
```

Edit `.env`:

```text
APP_ENV=local
APP_NAME=Review Robin Web
DEBUG=true

ALLOW_FAKE_AUTH=true
FAKE_AUTH_EMAIL=operator@example.edu
FAKE_AUTH_NAME=Local Operator

# Optional. Defaults to sqlite:///./review_robin_web.db.
# DATABASE_URL=sqlite:///./review_robin_web.db
```

> **Never** set `ALLOW_FAKE_AUTH=true` in any deployed environment. The
> default in `app/config.py` is `False`; the variable only takes effect if
> a `.env` (local) or App Setting (deployed, **don't**) overrides it.

### `review_robin_web.db` (created automatically)

Alembic creates this SQLite file on the first `alembic upgrade head`. It is
gitignored. Delete it any time to start fresh; the migration will recreate
it.

### Virtual environment (`.venv/`)

Recommended but not required. Gitignored.

---

## 4. First-time setup

```bash
# 1. Clone
git clone https://github.com/philoyhc/review-robin-web.git
cd review-robin-web

# 2. Virtual environment
python3.12 -m venv .venv
source .venv/bin/activate          # macOS/Linux
# .\.venv\Scripts\Activate.ps1     # Windows PowerShell
# .venv\Scripts\activate.bat       # Windows CMD

# 3. Dependencies (runtime + dev)
python -m pip install --upgrade pip
pip install -e .[dev]

# 4. Local environment variables
cp .env.example .env
# edit .env: set ALLOW_FAKE_AUTH=true (see §3)

# 5. Apply database migrations
alembic upgrade head

# 6. Run the app
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/health` — expect `{"status": "ok"}`.

---

## 5. Running the test suite

```bash
pytest
```

Expected: **24 passed**, ~1 second. The `tests/db/` fixtures spin up an
in-memory SQLite engine and run `alembic upgrade head` against it, so the
real migration is exercised on every test session.

---

## 6. Verifying each surface area

After the app is running on `http://127.0.0.1:8000/`:

| URL                         | Expected (with `ALLOW_FAKE_AUTH=true`)                       |
|-----------------------------|--------------------------------------------------------------|
| `/health`                   | `200` JSON `{"status": "ok"}`                                |
| `/`                         | `200` JSON service metadata.                                 |
| `/me`                       | `200` JSON for the fake user (`is_fake: true`).              |
| `/me/debug`                 | `200` HTML page; "fake auth" pill shown; "No claims found".  |
| `/docs`                     | FastAPI's automatic Swagger UI.                              |

If `/me` returns `401`, your `.env` is missing or `ALLOW_FAKE_AUTH` is not
set to `true`.

---

## 7. Database tasks

See `docs/database.md` for the full database guide. Quick reference:

```bash
# Apply all pending migrations
alembic upgrade head

# Roll back one migration
alembic downgrade -1

# Generate a new migration after editing models
alembic revision --autogenerate -m "describe the change"
# Then ALWAYS hand-review the generated file before committing.

# Drop everything (delete the SQLite file and re-migrate)
rm review_robin_web.db && alembic upgrade head
```

---

## 8. Common issues

### `ERROR: Package 'review-robin-web' requires a different Python: 3.11.x not in '>=3.12'`
Your venv was created with Python 3.11 or older. Recreate with
`python3.12 -m venv .venv`.

### `ModuleNotFoundError: No module named 'pytest'`
Either the venv is not activated or `pip install -e .[dev]` was not run.

### `/me` returns 401 locally
`ALLOW_FAKE_AUTH=true` is missing in `.env`. Easy Auth headers don't exist
locally, so without fake auth there is no identity to return.

### Alembic complains about `sqlalchemy.url`
`alembic.ini` deliberately leaves `sqlalchemy.url` blank — `alembic/env.py`
reads it from `app.config.settings.database_url`. Make sure your `.env`
either uses the default SQLite URL or sets `DATABASE_URL` to something the
driver can reach.

### Pre-existing `review_robin_web.db` after pulling new migrations
If you pulled new migrations and `alembic upgrade head` reports schema
mismatches, the simplest fix in development is `rm review_robin_web.db &&
alembic upgrade head`. There's nothing valuable in a local SQLite file at
this stage.

---

## 9. Where to look next

- `docs/authentication.md` — how Easy Auth identity is parsed; what the
  `/me` and `/me/debug` routes do.
- `docs/database.md` — model conventions, migration generation rules, the
  cross-dialect type policy, where Postgres lands.
- `docs/deployment_dev.md` — the dev Azure App Service deployment.
- `guide/` — segment-by-segment workplan (current and upcoming);
  shipped segment plans live in `guide/archive/`.
- `CONTRIBUTING.md` — branch and PR workflow.
- `AGENTS.md` / `CLAUDE.md` — conventions if you are pairing with an AI
  coding agent.

---

## 10. What is intentionally not in this segment yet

If you are looking for something below and can't find it, that's because
it's deferred to a later segment:

| Item                                | Lands in   |
|-------------------------------------|------------|
| Local Postgres (Docker Compose)     | Segment 5  |
| Azure PostgreSQL Flexible Server    | Segment 5  |
| Operator-facing UI / forms          | Segment 5  |
| Reviewer / reviewee CSV import      | Segment 6  |
| Assignment generation               | Segment 7  |
| Reviewer tabular response surface   | Segment 8  |
| Email invitations + reminders       | Segment 9  |
| Multi-instrument sessions           | Shipped in Segment 10D Slice 5; remainder at `guide/archive/unfinished_business.md` #27 / #28 / #29 |
| Cleaning up unfinished business     | Segment 11 |
| CSV / Excel exports                 | Segment 12 |
| Rule-based assignment builder       | Segment 13 |
| Production hardening (structured logging, error handling, index review, permission audit, accessibility, runbooks) | Segment 14A |
