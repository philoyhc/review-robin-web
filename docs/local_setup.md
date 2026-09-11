# Local Setup

This guide covers everything needed to run Review Robin Web locally for
development. It is the source of truth for developer setup; the README only
shows the minimal happy path.

If you only want to run the tests once, jump to [§4 First-time setup](#4-first-time-setup).

On a brand-new **Windows** machine with nothing installed yet (Python, Git,
GitHub Desktop, PowerShell), start at
[§10 Windows: setting up a new machine from scratch](#10-windows-setting-up-a-new-machine-from-scratch)
— it walks the whole install-to-first-test path, then hands back to the
sections below.

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
| GitHub Desktop | GUI for clone / branch / commit / push / PR without the command line; handles GitHub sign-in for you. See [§10](#10-windows-setting-up-a-new-machine-from-scratch) for the Windows walkthrough. |
| GitHub CLI (`gh`) | Easier branch and PR workflows.                       |
| Azure CLI (`az`) | Needed only if you administer the dev App Service (e.g. tweaking Easy Auth settings via `az webapp auth`). Not needed for day-to-day app development. |

### Not needed for day-to-day work

- **Docker** — only for reproducing a Postgres-dialect issue locally
  (the `ci-postgres` job already covers this on every PR). Day-to-day
  dev and the full test suite run on SQLite with no client tools. See
  [§9](#9-running-in-a-github-codespace) § Postgres parity for the
  throwaway-container recipe.
- **PostgreSQL client** — same reasoning; SQLite needs none.
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
      models/               the domain models (User, ReviewSession, ...)
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

### `.env` (required for `/auth/me` and `/auth/me/debug` to work locally)

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

Under fake auth the local `operator@example.edu` carries **operator +
sys-admin + super-admin** rights — `fake_auth_operator` /
`fake_auth_sys_admin` / `fake_auth_super_admin` all default to `True` in
`app/config.py`. Super-admin (Segment 18S) is derived, so you don't set
`SUPER_ADMIN_EMAILS` locally; the fake toggle covers it and self-heals your
existing local row on the next sign-in. All three are inert in deployed
envs (where `ALLOW_FAKE_AUTH` is false).

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
pytest -n auto        # full suite, ~35s (pytest-xdist parallelism)
```

The suite builds its schema straight from the ORM metadata
(`Base.metadata.create_all`) into an **in-memory SQLite** engine
(`tests/conftest.py`) — the fast path, so there's nothing to provision.
The Alembic migration chain is still round-tripped on every PR by the
`ci-postgres` job (and locally if you point the suite at Postgres — see
[§9 Running in a GitHub Codespace](#9-running-in-a-github-codespace) §
Postgres parity). Other useful runs:

```bash
pytest tests/integration/test_X.py            # one file
pytest tests/integration/test_X.py::test_name # one test
pytest -k "expression"                         # match by name
ruff check .                                   # lint
```

---

## 6. Verifying each surface area

After the app is running on `http://127.0.0.1:8000/`:

| URL                         | Expected (with `ALLOW_FAKE_AUTH=true`)                       |
|-----------------------------|--------------------------------------------------------------|
| `/health`                   | `200` JSON `{"status": "ok"}`                                |
| `/`                         | `200` JSON service metadata.                                 |
| `/auth/me`                       | `200` JSON for the fake user (`is_fake: true`).              |
| `/auth/me/debug`                 | `200` HTML page; "fake auth" pill shown; "No claims found".  |
| `/docs`                     | FastAPI's automatic Swagger UI.                              |

If `/auth/me` returns `401`, your `.env` is missing or `ALLOW_FAKE_AUTH` is not
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

### `/auth/me` returns 401 locally
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

## 9. Running in a GitHub Codespace

RRW's test suite and dev server need **no external services** — the tests
run against in-memory SQLite and the app runs against a local SQLite file
with a fake-auth fallback — so a Codespace is a first-class place to run
the suite and click through the app. The one thing a Codespace *can't* do
is exercise **real Entra / Easy Auth sign-in** (those headers are injected
by the Azure platform), which still needs the Azure dev slot.

| Task | In a Codespace? |
|---|---|
| Full `pytest` suite (business logic, routes, services) | ✅ Yes — SQLite in-memory, no setup |
| Alembic migration round-trip on SQLite | ✅ Yes |
| Run the app + click through operator / reviewer surfaces | ✅ Yes — fake auth + forwarded port |
| `ruff` lint | ✅ Yes |
| Postgres-dialect parity (what `ci-postgres` catches) | ⚙️ Optional — add a Postgres service (below) |
| Real Entra / Easy Auth sign-in, redirect flows, tenant allowlist | ❌ No — needs the Azure dev slot |

**Start.** From the repo on GitHub: **Code ▸ Codespaces ▸ Create codespace
on `main`** (or a feature branch). The default image ships **Python 3.12**,
Git, and the GitHub CLI. There is **no `.devcontainer/` in the repo yet**,
so the first-run setup is the same manual sequence as [§4](#4-first-time-setup)
(skip the clone — the Codespace arrives with the repo). `.env.example`
already ships `ALLOW_FAKE_AUTH=true` + a fake operator, so `cp .env.example
.env` needs no editing.

**Open the app.** `uvicorn app.main:app --reload` — Codespaces auto-forwards
port **8000** (a private `*.app.github.dev` URL in the **Ports** tab). If it
isn't auto-forwarded, bind explicitly: `uvicorn app.main:app --reload --host
0.0.0.0 --port 8000` and add port 8000 in the **Ports** tab. You land signed
in as the fake `operator@example.edu` (operator + sys-admin + super-admin,
per §3); surface-check `/health`, `/`, `/auth/me`, `/auth/me/debug`, `/docs`
as in [§6](#6-verifying-each-surface-area).

**Postgres parity (optional).** Docker is available in the default image, so
you can reproduce a dialect-only issue (the `BOOLEAN DEFAULT 1` /
`WHERE bool_col = 1` / FK-drop-order / index-name traps in `CLAUDE.md`):

```bash
docker run -d --name rrw-pg -e POSTGRES_PASSWORD=pw -p 5432:5432 postgres:16
export TEST_DATABASE_URL="postgresql+psycopg://postgres:pw@localhost:5432/postgres"
pytest -n auto        # the engine fixture honours TEST_DATABASE_URL; unset to return to SQLite
```

**One-click boot (optional).** Dropping a `.devcontainer/devcontainer.json`
makes a Codespace boot fully provisioned. A minimal one:

```jsonc
{
  "name": "review-robin-web",
  "image": "mcr.microsoft.com/devcontainers/python:3.12",
  "postCreateCommand": "python -m pip install --upgrade pip && pip install -e .[dev] && cp -n .env.example .env && alembic upgrade head",
  "forwardPorts": [8000],
  "portsAttributes": { "8000": { "label": "RRW app", "onAutoForward": "notify" } },
  "customizations": { "vscode": { "extensions": ["ms-python.python", "charliermarsh.ruff"] } }
}
```

Adding it is a project decision — it's not in the repo, so both the manual
path above and this snippet are offered.

---

## 10. Windows: setting up a new machine from scratch

The sections above lean on macOS/Linux shell syntax. This section is the
**complete path for a fresh Windows 10 / 11 machine with nothing installed**
— PowerShell, Python 3.12, Git, GitHub Desktop, and optionally VS Code —
ending at a passing test run. Do the steps in order; the later steps assume
the tools from the earlier ones are on `PATH`.

Everything here is free. Each tool lists a one-line **winget** command (the
built-in Windows Package Manager) *and* a manual download link — use
whichever you prefer.

> **About `winget`.** It ships with the "App Installer" package (preinstalled
> on Windows 11 and recent Windows 10). If `winget` is "not recognized",
> install **App Installer** from the Microsoft Store, then reopen the
> terminal — or just use the manual download links.

> **Reopen your terminal after each install.** Installers that add to `PATH`
> only affect terminals opened *afterwards*. A "command not found" right
> after an install almost always means the terminal predates it.

### A. PowerShell 7 + Windows Terminal (recommended shell)

Windows ships with **Windows PowerShell 5.1**, which runs everything in this
guide fine. But **PowerShell 7** (the current version, invoked as `pwsh`) is
worth installing, and **Windows Terminal** gives you a modern tabbed host.

```powershell
winget install --id Microsoft.PowerShell -e        # PowerShell 7 (pwsh)
winget install --id Microsoft.WindowsTerminal -e   # tabbed terminal (preinstalled on Win 11)
```

Manual downloads: [PowerShell releases](https://github.com/PowerShell/PowerShell/releases)
· [Windows Terminal](https://aka.ms/terminal). From here on, "PowerShell"
means either 5.1 or 7 — the commands are identical.

### B. Python 3.12 (install this version specifically)

The project is pinned to **3.12+** in `pyproject.toml`. Install **3.12
specifically** rather than grabbing whatever "latest Python" is — a newer
minor (3.13 / 3.14) can lack wheels for a dependency and break the install.

```powershell
winget install --id Python.Python.3.12 -e
```

Or from python.org: [Windows downloads](https://www.python.org/downloads/windows/)
→ take the latest **3.12.x** "Windows installer (64-bit)". In the installer,
tick both:

- ✅ **Add python.exe to PATH** (checkbox at the bottom of the first screen)
- ✅ **py launcher** (installs the `py` version selector)

Verify in a **new** terminal:

```powershell
py -0p                # lists every installed Python and its path
py -3.12 --version    # -> Python 3.12.x
```

If 3.12 doesn't show up, re-run the installer with the two boxes ticked.

> **Why `py -3.12` and not `python`.** A machine can carry several Pythons.
> `py -3.12` always targets 3.12 no matter the `PATH` order, which is exactly
> what you want when creating the virtualenv in step G.

### C. Git

```powershell
winget install --id Git.Git -e
```

Or [Git for Windows](https://git-scm.com/download/win). The installer
defaults are fine; two prompts worth a glance:

- **Default branch name** — leave it as `main`.
- **Line endings** — accept the default *"Checkout Windows-style, commit
  Unix-style"* (`core.autocrlf=true`). The repo ships no `.gitattributes`,
  so this keeps LF in history while letting Windows editors work normally.

Verify, then set your identity once (use the email on your GitHub account):

```powershell
git --version
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"
```

### D. GitHub Desktop (optional — GUI for clone / commit / push)

If you'd rather not drive Git from the command line, GitHub Desktop handles
clone / branch / commit / push / PR and signs you in to GitHub without any
personal-access-token setup.

```powershell
winget install --id GitHub.GitHubDesktop -e
```

Or [desktop.github.com](https://desktop.github.com/). First run:

1. **File ▸ Options ▸ Accounts ▸ Sign in** to GitHub.
2. **File ▸ Clone repository…** → pick `philoyhc/review-robin-web` (or paste
   the URL) and set the local path, e.g. `C:\GitHub\review-robin-web`.

GitHub Desktop bundles its own Git, but installing Git for Windows (step C)
as well puts `git` on your `PATH` for terminal use. The two coexist fine.

### E. VS Code (optional editor)

```powershell
winget install --id Microsoft.VisualStudioCode -e
```

Or [code.visualstudio.com](https://code.visualstudio.com/). Recommended
extensions: **Python** (`ms-python.python`) and **Ruff**
(`charliermarsh.ruff`). After you create the venv (step G), VS Code will
prompt to use `.venv\Scripts\python.exe` as the interpreter — accept it, or
pick it via **Ctrl+Shift+P ▸ Python: Select Interpreter**.

### F. Clone the repo (skip if you used GitHub Desktop)

```powershell
mkdir C:\GitHub -Force        # or wherever you keep code
cd C:\GitHub
git clone https://github.com/philoyhc/review-robin-web.git
cd review-robin-web
```

### G. Create the venv, install, configure, migrate

From the repo root (e.g. `C:\GitHub\review-robin-web`), in **PowerShell**:

```powershell
# 1. Virtualenv with Python 3.12 specifically
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Dependencies (runtime + dev) — QUOTE the extras in PowerShell
python -m pip install --upgrade pip
pip install -e ".[dev]"

# 3. Local env vars (fake auth is already enabled in the template)
Copy-Item .env.example .env

# 4. Create + migrate the local SQLite DB (.\review_robin_web.db)
alembic upgrade head
```

CMD equivalents: `.venv\Scripts\activate.bat` and `copy .env.example .env`.

When the venv is active your prompt shows `(.venv)`, and `where.exe python`
points inside `...\review-robin-web\.venv\Scripts`.

### H. Run the tests / the app

```powershell
pytest -n auto                    # full suite, ~35s
ruff check .                      # lint
uvicorn app.main:app --reload     # then open http://127.0.0.1:8000/health
```

Expect `{"status": "ok"}` at `/health`. That's the whole loop; from here the
rest of this guide ([§5](#5-running-the-test-suite) onward) applies as
written.

### Windows-specific gotchas

- **`Activate.ps1` blocked** — *"running scripts is disabled on this
  system"*: PowerShell's execution policy. Loosen it for the current session
  with `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`,
  or once for your user with `-Scope CurrentUser`. Alternatively use CMD and
  `.venv\Scripts\activate.bat`.
- **`pip install -e .[dev]` installs no dev tools** — PowerShell glob-expands
  the bare `[dev]`. Quote it: `pip install -e ".[dev]"`. The symptom shows up
  later as `No module named 'pytest'`.
- **`py` or `python` "not recognized" in a fresh terminal** — the *Add
  python.exe to PATH* box was missed, or the terminal predates the install.
  Open a new terminal; if still missing, re-run the Python installer with the
  box ticked.
- **Long-path errors** during `pip install` or `clone` — enable long paths
  (elevated PowerShell: `git config --system core.longpaths true`) and keep
  the clone near the drive root (`C:\GitHub\...`) to keep paths short.
- **Reset the local DB** — `Remove-Item .\review_robin_web.db` (PowerShell)
  or `del review_robin_web.db` (CMD), then `alembic upgrade head`. There's
  nothing valuable in a local SQLite file.

---

## 11. Where to look next

- `docs/security_posture.md` — how Easy Auth identity is parsed; what the
  `/auth/me` and `/auth/me/debug` routes do.
- `docs/database.md` — model conventions, migration generation rules, the
  cross-dialect type policy, where Postgres lands.
- `docs/deployment_dev.md` — the dev Azure App Service deployment.
- `guide/` — segment-by-segment workplan (current and upcoming);
  shipped segment plans live in `guide/archive/`.
- `CONTRIBUTING.md` — branch and PR workflow.
- `AGENTS.md` / `CLAUDE.md` — conventions if you are pairing with an AI
  coding agent.
