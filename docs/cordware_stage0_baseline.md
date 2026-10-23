# Cordware stage 0 — RRW baseline

**Taken:** 2026-10-21 at `b03fd1be` (`main`, after #3193) · **For:**
v0.8 §5 stage 0, the gate before segment 21A's A1
(`guide/archive/segment_21A_cordware_foundations.md`) · **Scope:** RRW only.
Residential's provenance and making the repository private stay the
author's, before stage 3 imports anything.

This is the known-good point the Cordware work starts from. If a later
rung breaks something, compare against this record. Each figure has the
command that produced it, so it can be taken again. It records state
and does not change any. Nothing here is a requirement; v0.8 and the
segment 21 plans hold those.

## Source

| What | Value | Command |
|---|---|---|
| Commit | `b03fd1be6264741262e846fa63f08c49f56dd3cf` | `git rev-parse origin/main` |
| CI on that commit | `CI` (job `test`) and `CI - Postgres` (job `postgres`) both success | `gh api repos/philoyhc/review-robin-web/commits/b03fd1be/check-runs` |
| Alembic head | `c4e9a2f7b1d3`, single head; 96 revision files | `alembic heads`; `ls alembic/versions/*.py \| wc -l` |
| Python | 3.12.3 here; `3.12` in all four workflows | `python --version`; `grep python-version .github/workflows/*.yml` |
| Resolved stack | FastAPI 0.141.1, Starlette 1.6.0, uvicorn 0.53.0, gunicorn 26.2.0, SQLAlchemy 2.0.54, Alembic 1.20.0, Pydantic 2.13.5 | `pip show …`; `requirements.txt` holds 11 lower-bounded, unpinned lines |

## Tests

Run here on SQLite at `b03fd1be`'s tree, with Chromium and Node 22
present. `pytest -n auto -q -rs` gave **6,828 passed, 4 skipped**,
235 warnings, in 229 s.

| Tree | Collected | Command |
|---|---|---|
| `tests/unit` | 1,828 | `pytest --collect-only -q tests/unit` |
| `tests/integration` | 4,764 | same, per tree |
| `tests/browser` | 193, all run (none skipped for want of a browser) | same |
| the rest (`tests/db`, top-level) | 47 | same, ignoring the three above |

The 4 skips are by design. `test_css_parity_dump.py:41` runs only with
`RRW_PARITY_DUMP` set. Three cases in `test_owner_add_lock.py:256, 282`
need Postgres row locks, and the `postgres` job covers them.
`test_inline_scripts_parse.py` ran: it skips only without `node`.
The warnings are deprecations, chiefly Starlette's
`HTTP_422_UNPROCESSABLE_ENTITY` rename and the legacy `detail=`
audit kwarg, plus SQLite's datetime adapter. None fails a test.

## Launch configuration

Both columns record `b03fd1be`, line numbers included; they have moved
since.

| Surface | Command at `b03fd1be` | Where |
|---|---|---|
| Local | `uvicorn app.main:app --reload` | `README.md:115`, `CLAUDE.md:95`, `docs/local_setup.md:159, 507` |
| Codespaces | `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` after `alembic upgrade head` | `.devcontainer/devcontainer.json:23`, `docs/setup_codespaces.md:31, 54`, `docs/local_setup.md:326` |
| Web session container | `.claude/hooks/session-start.sh` builds `.venv/` (3.12+), `pip install -e .[dev]` | the hook; no server started |
| Browser tests | `python -m uvicorn app.main:app` on a free port, fresh SQLite, fake auth | `tests/browser/conftest.py:96` |
| Dev slot | `gunicorn -w 2 -k uvicorn.workers.UvicornWorker app.main:app`, an Azure setting | `docs/deployment_dev.md:38` |
| NUS slot | the same `gunicorn` line, still to be set | `docs/deployment_nus.md:127` |

Settings are read by `app/config.py` (`env_file=".env"`, shell overrides
it). Its 20 fields (`python -c "from app.config import Settings; print(len(Settings.model_fields))"`) are listed in `docs/deployment_dev.md` "Environment
variables".

## Deploy configuration

| Workflow | Trigger | State on GitHub | Last run |
|---|---|---|---|
| `ci.yml` | push and PR to `main` | active | every PR |
| `ci-postgres.yml` | push and PR to `main` | active | every PR |
| `main_app-review-robin-web-dev.yml` | push to `main`, `workflow_dispatch` | **`disabled_manually`** | 2026-06-03, `8b3d5c33`, success |
| `deploy_nus.yml` | `workflow_dispatch` only | active | never run |

Command: `gh api repos/philoyhc/review-robin-web/actions/workflows`, and
`…/workflows/<file>/runs?per_page=3` for the last run.

- The dev workflow builds `antenv/` from `requirements.txt` and uploads
  `app/`, `alembic/`, `alembic.ini`, `requirements.txt`, `pyproject.toml`
  and `antenv/` (`:56–62`). It then runs `alembic upgrade head` against
  the dev Postgres and deploys with OIDC to `app-review-robin-web-dev`.
  The NUS workflow packages the same paths (`deploy_nus.yml:55–61`).
- **The dev slot is not redeployed on merge.** Its workflow has been
  disabled since its last run on 2026-06-03. The slot is still serving
  that build or a later manual deploy; this session cannot tell which.
  Its `/health` could not be reached from here (the agent proxy refuses
  the host). `docs/deployment_dev.md` "CI/CD workflow" still describes
  a push trigger.
- `pyproject.toml` finds the `app*` packages only (`:36`) and collects
  `tests` only (`:39`).

## What this changes downstream

- 21A's switch timing ("after A1 deploys, before A2 merges") assumed the
  dev slot redeploys on merge. A disabled workflow runs on neither push
  nor `workflow_dispatch`, so nothing reaches the slot until the author
  re-enables it. The start command must then name an object the deployed
  build has. The author has ruled that the slot stays dormant and all
  testing is on localhost until the Azure work settles (2026-10-21).
  The steps to bring it back are in `docs/deployment_dev.md` "Resuming
  the dev slot".
