# applydesk/

Apply Desk: applications, assessment through Review Robin, and applicant
communication, mounted under Cordware at `/applydesk`. Segment AD1 built
the package, its health path and its URL map as placeholders on sample
data. Rulings
and the MVP roadmap are in `guide/todo_master.md`.

| Path | Holds |
|---|---|
| `main.py`, `routes_*.py` | The factory, `/health` and the placeholder pages |
| `gate.py`, `ids.py`, `web.py`, `sample_data.py` | The placeholders' gate, public IDs, templates and chrome, sample data |
| `templates/applydesk/` | Templates; `base.html` carries the favicon and the bar |
| `tests/` | Apply Desk's tests, with a host harness (`tests/_host.py`) |
| `docs/applydesk_functional_spec_v0.6b_agent_handoff.md` | The functional baseline (v0.6b, 2 November 2026); where a ruling in `guide/todo_master.md` differs, the ruling wins |
| `docs/photo_field_design.md`, `docs/photo_field/` | The applicant photo field's design and mock-ups (2026-11-12), from Utilities' photo proof of concept; not scheduled |
| `docs/chrome/` | Mock-ups of the exercise chrome and Workflow card (2026-11-13), for segment AD1D |
| `docs/home/` | Mock-ups of Exercise Home (2026-11-17), for segment AD1I: the timeline horizontal (v1, Details locked and unlocked), vertical (v2, desktop and phone) and equal-width (v3, three and five stages and a phone, the one built), and the operator's part below or beside it (v4) |
| `docs/extract/` | Mock-ups of Extract data (2026-11-18), for segment AD1J: download cards after Review Robin's, desktop and phone (v1) |
| `spec/applications.md` | Apply Desk as the host sees it: registry entry, health, running alone, the URL map |
| `spec/architecture.md` | Package layout, import boundaries, packaging, tests and CI |
| `guide/todo_master.md` | Rulings, the MVP roadmap and open decisions |
| `guide/segment_AD1_skeleton.md` | Segment AD1 plan: the package and mount, then the URL map as placeholders |
| `guide/segment_AD1C_applications.md` | Segment AD1C plan: the Applications page as the control surface, rounds of gates and outcomes as columns, nothing saved |
| `guide/segment_AD1D_chrome.md` | Segment AD1D plan: an exercise's pages in Review Robin's chrome (Home, Setup, Operations) and the Workflow card |
| `guide/findings_2026-11-18_assessment.md` | Findings register from the 2026-11-18 assessment of every Apply Desk screen: UI consistency, intended actions, data model and spec gaps, 125 rows (AD-01 to AD-125) to clear, with the rulings it needs |
| `guide/archive/README.md` | Closed segment plans: AD1B (the Form page), AD1E (Process), AD1F (Gates and Panels), AD1G (Evaluators and Evaluations), AD1H (the RA model exercise), AD1I (Exercise Home), AD1J (Extract data) |
