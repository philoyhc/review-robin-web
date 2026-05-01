# Review Robin Web

Review Robin Web is a web-based successor concept for Review Robin, a structured review-cycle tool for configuring reviewer/reviewee assignments, collecting tabular review responses, and exporting clean datasets for downstream analysis.

This repository is currently at the project skeleton stage.

## Local development

```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows PowerShell/CMD
pip install -e .[dev]
alembic upgrade head
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/health` and expect:

```json
{"status":"ok"}
```

To exercise the authenticated `/me` (JSON) and `/me/debug` (HTML) endpoints
locally, set `ALLOW_FAKE_AUTH=true` in your `.env` (see `.env.example`). In
Azure, Easy Auth provides the identity instead — see `docs/authentication.md`.

## Tests

```bash
pytest
```

## Project documents

Documentation is split across three folders, each with its own README:

- **`spec/`** — surface specifications and design intent (`spec/README.md`).
  Includes `architecture.md`, `functional_spec.md`, `assumptions.md`,
  `operator_map.md`.
- **`docs/`** — reference material about the running system (`docs/README.md`).
  Includes `status.md`, `authentication.md`, `database.md`, `imports.md`,
  `local_setup.md`, `deployment_dev.md`.
- **`guide/`** — forward-looking plans, segment workplans, todos
  (`guide/README.md`). Shipped segment plans are in `guide/archive/`.

Top-level docs at the repo root: `CLAUDE.md` / `AGENTS.md` (kept as
byte-identical twins; AI-agent guidance), `CONTRIBUTING.md`,
`README.md` (this file).
