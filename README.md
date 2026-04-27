# Review Robin Web

Review Robin Web is a web-based successor concept for Review Robin, a structured review-cycle tool for configuring reviewer/reviewee assignments, collecting tabular review responses, and exporting clean datasets for downstream analysis.

This repository is currently at the project skeleton stage.

## Local development

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows PowerShell/CMD variant may differ
pip install -e .[dev]
uvicorn app.main:app --reload
