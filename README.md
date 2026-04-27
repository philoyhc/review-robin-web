# Review Robin Web

Review Robin Web is a web-based successor concept for Review Robin, a structured review-cycle tool for configuring reviewer/reviewee assignments, collecting tabular review responses, and exporting clean datasets for downstream analysis.

This repository is currently at the project skeleton stage.

## Local development

```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows PowerShell/CMD
pip install -e .[dev]
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/health` and expect:

```json
{"status":"ok"}
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
- `CONTRIBUTING.md`
- `doc/deployment_dev.md`
