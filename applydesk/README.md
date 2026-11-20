# applydesk/

Apply Desk: applications, assessment through Review Robin, and applicant
communication, mounted under Cordware at `/applydesk`. Segments AD1 to
AD1K built every page of its URL map as a working scaffold on sample data:
moves work on screen, nothing is saved until AD2. Rulings and the MVP
roadmap are in `guide/todo_master.md`.

| Path | Holds |
|---|---|
| `main.py`, `routes_*.py`, `lookups.py` | The factory, `/health`, the pages, and the path lookups they share |
| `gate.py`, `ids.py`, `web.py`, `sample_data.py` | Who reaches the pages until AD2, public IDs, templates and chrome, sample data |
| `stages.py`, `workflow.py`, `locks.py` | Stages, gates, outcomes and rules; each item's state, the status row and emails owed; what a published stage fixes |
| `timeline.py`, `home_ops.py` | The timeline Home and the applicant's page share; Home's operator part |
| `extract.py`, `paging.py` | Extract data's files; a long table's pages and sort |
| `templates/applydesk/` | Templates; `base.html` carries the favicon and the bar |
| `tests/` | Apply Desk's tests, with a host harness (`tests/_host.py`) |
| `docs/applydesk_functional_spec_v0.6b_agent_handoff.md` | The functional baseline (v0.6b, 2 November 2026); where a ruling in `guide/todo_master.md` differs, the ruling wins |
| `docs/photo_field_design.md`, `docs/photo_field/` | The applicant photo field's design and mock-ups (2026-11-12), from Utilities' photo proof of concept; in the MVP since ruling 12, built on Form with a ratio per question |
| `docs/chrome/` | Mock-ups of the exercise chrome (2026-11-13), for segment AD1D; its Workflow card was removed on 2026-11-15 |
| `docs/home/` | Mock-ups of Exercise Home (2026-11-17), for segment AD1I: the timeline horizontal (v1, Details locked and unlocked), vertical (v2, desktop and phone) and equal-width (v3, three and five stages and a phone, the one built), and the operator's part below or beside it (v4) |
| `docs/extract/` | Mock-ups of Extract data (2026-11-18), for segment AD1J: download cards after Review Robin's, desktop and phone (v1) |
| `spec/applications.md` | Apply Desk as the host sees it: registry entry, health, running alone, the URL map, and each page's contract |
| `spec/architecture.md` | Package layout, import boundaries, packaging, tests and CI |
| `guide/todo_master.md` | Rulings, the MVP roadmap and open decisions |
| `guide/findings_2026-11-18_assessment.md` | Findings register from the 2026-11-18 assessment of every Apply Desk screen: UI consistency, intended actions, data model and spec gaps, 125 rows (AD-01 to AD-125) to clear, with the rulings it needs |
| `guide/findings_2026-11-20.md` | Apply Desk's findings from RRW's corpus sweep and codebase assessment of 2026-11-20 (the first to read the packages' prose): 7 rows, the spec against rulings 26, 28, 33, 36, 38, 39 and 59, and the layout table |
| `guide/archive/README.md` | Closed segment plans: AD1 (the package and URL map), AD1B (the Form page), AD1C (Dossiers), AD1D (the exercise's chrome), AD1E (Process), AD1F (Gates and Panels), AD1G (Evaluators and Evaluations), AD1H (the RA model exercise), AD1I (Exercise Home), AD1J (Extract data), AD1K (a status per stage, and what locks) |
