# Segment 1 Plan — Repository Setup and AI-Friendly Project Skeleton

**Project:** Review Robin Web  
**Repository:** <https://github.com/philoyhc/review-robin-web>  
**Segment:** 1 of the low-intensity workplan  
**Purpose:** Create a clean, conventional repository that can support FastAPI development, GitHub Actions, and AI-assisted coding workflows

---

## 1. Segment goal

Segment 1 establishes the project home.

By the end of this segment, the repository should contain:

- a minimal FastAPI application skeleton;
- a clear folder structure;
- basic project documentation;
- AI-agent instructions;
- Python dependency configuration;
- a minimal test setup;
- a first passing smoke test;
- a simple GitHub workflow for continuous integration;
- a working branch / pull request rhythm.

This segment should not attempt to build Review Robin features yet. Its job is to make the repository ready for later work.

---

## 2. Success criteria

Segment 1 is complete when:

1. The GitHub repository exists at `https://github.com/philoyhc/review-robin-web`.
2. The project can be cloned locally.
3. Python dependencies can be installed.
4. A minimal FastAPI app can run locally.
5. A `/health` endpoint returns a successful response.
6. At least one pytest smoke test passes.
7. GitHub Actions runs the test workflow successfully.
8. The repository contains initial project guidance documents.
9. Future AI-assisted coding tasks have clear conventions to follow.
10. The first pull request has been created, reviewed, and merged.

---

## 3. What this segment deliberately does not do

Do not include any of the following in Segment 1:

- Azure deployment;
- Microsoft authentication;
- database setup;
- SQLAlchemy models;
- Alembic migrations;
- reviewer/reviewee import;
- session creation;
- email sending;
- frontend grid work;
- background jobs;
- production configuration;
- Blob Storage;
- Application Insights.

Those belong to later segments.

Segment 1 is only about creating a clean starting point.

---

## 4. Recommended branch strategy

Use a simple, low-friction branch pattern.

### Main branch

`main` should always contain working code.

### Segment branch

Create one branch for this segment:

```bash
git checkout -b segment-1-repo-skeleton
```

### Pull request

Open one pull request from `segment-1-repo-skeleton` into `main`.

Suggested PR title:

```text
Segment 1: Add project skeleton and CI
```

Suggested PR description:

```text
Adds the initial Review Robin Web repository skeleton:

- FastAPI app skeleton
- /health route
- pytest setup
- basic CI workflow
- initial documentation
- AI agent guidance

No Review Robin domain functionality is included yet.
```

---

## 5. Local prerequisites

Install or confirm these tools locally:

- Git
- Python 3.12 or later
- VS Code or another editor
- GitHub CLI, optional but useful
- A terminal shell

Optional but helpful:

- `uv` for Python dependency management; or
- standard `python -m venv` + `pip`

For the first skeleton, do not spend too much time optimizing the Python toolchain. A conventional virtual environment is sufficient.

---

## 6. Proposed initial repository structure

Create this minimal structure first:

```text
review-robin-web/
  README.md
  AGENTS.md
  CONTRIBUTING.md
  ARCHITECTURE.md
  FUNCTIONAL_SPEC.md
  TECH_STACK.md
  .env.example
  .gitignore
  pyproject.toml

  app/
    __init__.py
    main.py
    config.py

    web/
      __init__.py
      routes_health.py

  tests/
    __init__.py
    test_health.py

  .github/
    workflows/
      ci.yml
```

This is deliberately smaller than the full target repository structure. Later segments can add `db/`, `schemas/`, `services/`, `auth/`, `templates/`, `static/`, `functions/`, and `alembic/` when they become necessary.

---

## 7. File-by-file plan

## 7.1 `README.md`

Purpose: explain the project to a human opening the repo for the first time.

Suggested contents:

- What Review Robin Web is.
- What problem it solves.
- Current status: early skeleton.
- How to run locally.
- How to run tests.
- Link to functional and technology specs.

Suggested draft structure:

```markdown
# Review Robin Web

Review Robin Web is a web-based successor concept for Review Robin, a structured review-cycle tool for configuring reviewer/reviewee assignments, collecting tabular review responses, and exporting clean datasets for downstream analysis.

This repository is currently at the project skeleton stage.

## Local development

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows PowerShell/CMD variant may differ
pip install -e .[dev]
uvicorn app.main:app --reload
```

## Tests

```bash
pytest
```

## Project documents

- `FUNCTIONAL_SPEC.md`
- `TECH_STACK.md`
- `ARCHITECTURE.md`
- `AGENTS.md`
```

---

## 7.2 `AGENTS.md`

Purpose: guide AI coding agents and future contributors.

This is important. AI assistance works better when the repository tells the agent exactly what conventions to follow.

Suggested contents:

```markdown
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
```

---

## 7.3 `CONTRIBUTING.md`

Purpose: document the human workflow.

Suggested contents:

- Use one branch per issue.
- Keep PRs small.
- Include tests.
- Avoid mixing feature work and refactoring.
- Update docs when behavior changes.

Suggested draft:

```markdown
# Contributing

This is currently a small, experimental project.

## Workflow

1. Create a branch for each bounded task.
2. Keep pull requests small.
3. Add or update tests for behavior changes.
4. Keep route handlers thin and business logic in services.
5. Update documentation when setup or behavior changes.

## Pull request checklist

- [ ] Tests pass locally.
- [ ] New behavior has tests.
- [ ] Documentation is updated if needed.
- [ ] No unrelated refactoring is included.
```

---

## 7.4 `FUNCTIONAL_SPEC.md`

Purpose: store or summarize the technology-neutral functional specification.

For Segment 1, this can be a short placeholder that points to the fuller document.

Suggested contents:

```markdown
# Functional Specification

This document will contain the technology-neutral functional specification for Review Robin Web.

Current high-level scope:

- Operators configure review sessions.
- Operators upload or enter reviewers and reviewees.
- Operators configure assignments and review instruments.
- Reviewers receive individualized links.
- Reviewers complete tabular online review forms.
- The system exports CSV/Excel datasets for downstream analysis.

Detailed specification to be expanded in later planning work.
```

If desired, paste the full technology-neutral functional spec into this file now. That is acceptable, but not required for Segment 1.

---

## 7.5 `TECH_STACK.md`

Purpose: store or summarize the locked technology stack.

Suggested contents:

```markdown
# Technology Stack

Review Robin Web uses the following baseline stack:

- Azure App Service for Linux
- Python 3.12+
- FastAPI
- Pydantic
- SQLAlchemy 2.x + Alembic, when database work begins
- Azure Database for PostgreSQL Flexible Server
- Jinja2 templates
- HTMX for targeted interactivity
- AG Grid or equivalent for reviewer tables
- Azure App Service Easy Auth with Microsoft Entra ID
- Azure Storage Queue + Azure Functions for bulk jobs
- Institutional SMTP relay, with Azure Communication Services Email as fallback
- Azure Blob Storage for uploads and exports
- Application Insights / Azure Monitor
- pytest + FastAPI TestClient
- GitHub Actions CI/CD
```

The full implementation notes can be expanded later.

---

## 7.6 `ARCHITECTURE.md`

Purpose: capture early architecture principles without overcommitting.

Suggested contents:

```markdown
# Architecture Notes

Review Robin Web is organized around explicit domain entities:

- sessions
- reviewers
- reviewees
- instruments
- assignments
- responses
- invitations
- audit events
- exports
- retention actions

Implementation principles:

- Keep routes thin.
- Put business logic in services.
- Use explicit schemas at application boundaries.
- Keep authentication separate from authorization.
- Treat audit events as domain records, not ordinary logs.
- Keep the reviewer tabular surface isolated from the rest of the frontend complexity.
```

---

## 7.7 `.env.example`

Purpose: document expected local environment variables.

At Segment 1, keep this minimal.

Suggested contents:

```text
APP_ENV=local
APP_NAME=Review Robin Web
DEBUG=true
```

Database and Azure settings will be added later.

---

## 7.8 `.gitignore`

Suggested contents:

```text
# Python
__pycache__/
*.py[cod]
*.pyo
*.pyd
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/

# Virtual environments
.venv/
venv/

# Environment files
.env
.env.*
!.env.example

# IDE/editor
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
```

If using VS Code settings deliberately, do not ignore `.vscode/`, or selectively include `.vscode/extensions.json` later.

---

## 7.9 `pyproject.toml`

Purpose: define dependencies and test configuration.

Suggested minimal version:

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "review-robin-web"
version = "0.1.0"
description = "Web-based structured review-cycle application"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "jinja2>=3.1",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2",
    "httpx>=0.27",
    "ruff>=0.5",
]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"
```

This can be refined later.

---

## 7.10 `app/main.py`

Purpose: create the FastAPI app.

Suggested initial content:

```python
from fastapi import FastAPI

from app.web.routes_health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="Review Robin Web")
    app.include_router(health_router)
    return app


app = create_app()
```

This uses an app factory pattern, which will be useful later for tests and configuration.

---

## 7.11 `app/config.py`

Purpose: centralize app settings.

Suggested initial content:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    app_name: str = "Review Robin Web"
    debug: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
```

This is intentionally small. Database and Azure settings will be added later.

---

## 7.12 `app/web/routes_health.py`

Purpose: simple health endpoint.

Suggested content:

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

---

## 7.13 `tests/test_health.py`

Purpose: prove the app starts and the health route works.

Suggested content:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

---

## 7.14 `.github/workflows/ci.yml`

Purpose: run tests on push and pull request.

Suggested content:

```yaml
name: CI

on:
  push:
    branches: ["main"]
  pull_request:
    branches: ["main"]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e .[dev]

      - name: Run tests
        run: pytest
```

Later CI can add linting, formatting checks, type checking, migration checks, and security scanning.

---

## 8. Step-by-step execution checklist

### Step 1 — Clone or initialize repository

If the repository already exists:

```bash
git clone https://github.com/philoyhc/review-robin-web.git
cd review-robin-web
```

If starting from an empty local folder:

```bash
mkdir review-robin-web
cd review-robin-web
git init
git remote add origin https://github.com/philoyhc/review-robin-web.git
```

### Step 2 — Create segment branch

```bash
git checkout -b segment-1-repo-skeleton
```

### Step 3 — Add files and folders

Create the structure listed in section 6.

### Step 4 — Create virtual environment

Windows PowerShell example:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .[dev]
```

Windows CMD example:

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -e .[dev]
```

macOS/Linux example:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .[dev]
```

### Step 5 — Run app locally

```bash
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

### Step 6 — Run tests

```bash
pytest
```

Expected result:

```text
1 passed
```

### Step 7 — Commit changes

```bash
git add .
git commit -m "Add initial FastAPI project skeleton"
```

### Step 8 — Push branch

```bash
git push -u origin segment-1-repo-skeleton
```

### Step 9 — Open pull request

Open PR on GitHub:

```text
segment-1-repo-skeleton → main
```

### Step 10 — Confirm CI passes

Wait for the GitHub Actions CI workflow.

If it fails, inspect the log, fix the issue, commit, and push again.

### Step 11 — Merge PR

Once CI passes, merge the PR.

---

## 9. AI-assisted workflow for this segment

### 9.1 First prompt to AI coding agent

Use something like:

```text
Read the repository goal below and create only the Segment 1 project skeleton.

Repository: https://github.com/philoyhc/review-robin-web

Goal:
Create a minimal FastAPI project with:
- app/main.py
- app/config.py
- app/web/routes_health.py
- tests/test_health.py
- pyproject.toml
- README.md
- AGENTS.md
- CONTRIBUTING.md
- ARCHITECTURE.md
- FUNCTIONAL_SPEC.md
- TECH_STACK.md
- .env.example
- .gitignore
- .github/workflows/ci.yml

Constraints:
- Python 3.12+
- FastAPI
- pytest
- No database yet
- No Azure deployment yet
- No authentication yet
- No Review Robin domain functionality yet
- Keep code minimal and conventional
- Add a /health endpoint
- Add one passing smoke test
```

### 9.2 Review prompt after code is generated

```text
Review the Segment 1 skeleton for consistency with AGENTS.md.

Check specifically:
- Does the app run locally?
- Does pytest have a simple passing test?
- Is there any premature database/auth/domain code?
- Is the folder structure clear?
- Is the GitHub Actions workflow minimal and likely to pass?
- Are the docs accurate for the current stage?

Do not add new features. Suggest only small fixes.
```

### 9.3 Debug prompt if tests fail

```text
The Segment 1 pytest run failed. Here is the full error output:

[paste output]

Explain the cause and propose the smallest fix. Do not restructure the project unless necessary.
```

### 9.4 Debug prompt if GitHub Actions fails

```text
The GitHub Actions CI workflow failed. Here is the log:

[paste relevant log]

Diagnose the failure and propose the smallest correction to ci.yml or pyproject.toml.
```

---

## 10. Suggested GitHub issues for Segment 1

This segment can be run as one pull request, but if splitting into smaller issues later, use these:

### Issue 1 — Add FastAPI skeleton

Scope:

- `app/main.py`
- `app/web/routes_health.py`
- `/health` route
- smoke test

Acceptance criteria:

- app runs locally;
- `/health` returns `{ "status": "ok" }`;
- pytest passes.

### Issue 2 — Add project configuration

Scope:

- `pyproject.toml`
- `.gitignore`
- `.env.example`

Acceptance criteria:

- dependencies install;
- local test command works;
- no local environment files are committed.

### Issue 3 — Add repository documentation

Scope:

- `README.md`
- `AGENTS.md`
- `CONTRIBUTING.md`
- `ARCHITECTURE.md`
- `FUNCTIONAL_SPEC.md`
- `TECH_STACK.md`

Acceptance criteria:

- repo purpose is understandable;
- AI-agent conventions are explicit;
- docs do not claim features that are not built yet.

### Issue 4 — Add CI workflow

Scope:

- `.github/workflows/ci.yml`

Acceptance criteria:

- workflow runs on PR;
- Python 3.12 is used;
- dependencies install;
- pytest runs successfully.

---

## 11. Common mistakes to avoid

### 11.1 Adding too much too early

Do not add database models, authentication, or session features yet. Segment 1 should be boring.

### 11.2 Overcomplicating the tooling

Do not spend too much time choosing between `pip`, `uv`, Poetry, PDM, or other tools. A standard `pyproject.toml` plus `pip install -e .[dev]` is enough.

### 11.3 Making CI stricter than the codebase is ready for

Do not add heavy linting, type checking, and coverage gates before the app has structure. Start with tests only. Add stricter checks later.

### 11.4 Writing misleading documentation

Docs should say the project is a skeleton. Do not imply that session setup, imports, authentication, or exports already exist.

### 11.5 Putting secrets in the repo

Do not commit `.env`, publish profiles, Azure credentials, SMTP credentials, or any real institutional settings.

---

## 12. Segment 1 completion note template

At the end of the segment, add a short note to the PR or project log:

```markdown
## Segment 1 completion note

Completed:
- FastAPI skeleton
- /health route
- pytest smoke test
- CI workflow
- initial documentation
- AI-agent guidance

Verified:
- app runs locally
- pytest passes locally
- GitHub Actions CI passes

Deferred:
- Azure deployment
- authentication
- database
- Review Robin domain functionality

Notes:
- [any setup issues or decisions]
```

---

## 13. Segment 1 final checkpoint

Before moving to Segment 2, confirm:

- [ ] Repository exists on GitHub.
- [ ] `main` contains the Segment 1 skeleton.
- [ ] CI passes on `main`.
- [ ] Local setup instructions work.
- [ ] `/health` endpoint works locally.
- [ ] `AGENTS.md` gives clear AI-agent instructions.
- [ ] No secrets are committed.
- [ ] No premature database/auth/domain code was added.

When all boxes are checked, Segment 1 is complete.

Next segment: **Azure hello-world deployment**.

