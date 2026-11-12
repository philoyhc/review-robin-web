# applydesk/

ApplyDesk: applications, assessment through Review Robin, and applicant
communication, mounted under Cordware at `/applydesk`. Segment AD1 built
the package, its health path and its URL map as placeholders on sample
data. Rulings
and the MVP roadmap are in `guide/todo_master.md`.

| Path | Holds |
|---|---|
| `main.py`, `routes_*.py` | The factory, `/health` and the placeholder pages |
| `gate.py`, `ids.py`, `web.py`, `sample_data.py` | The placeholders' gate, public IDs, templates and chrome, sample data |
| `templates/applydesk/` | Templates; `base.html` carries the favicon and the bar |
| `tests/` | ApplyDesk's tests, with a host harness (`tests/_host.py`) |
| `docs/applydesk_functional_spec_v0.6b_agent_handoff.md` | The functional baseline (v0.6b, 2 November 2026); where a ruling in `guide/todo_master.md` differs, the ruling wins |
| `docs/photo_field_design.md`, `docs/photo_field/` | The applicant photo field's design and mock-ups (2026-11-12), from Utilities' photo proof of concept; not scheduled |
| `spec/applications.md` | ApplyDesk as the host sees it: registry entry, health, running alone, the URL map |
| `spec/architecture.md` | Package layout, import boundaries, packaging, tests and CI |
| `guide/todo_master.md` | Rulings, the MVP roadmap and open decisions |
| `guide/segment_AD1_skeleton.md` | Segment AD1 plan: the package and mount, then the URL map as placeholders |
| `guide/segment_AD1B_form_builder.md` | Segment AD1B plan: the Form page as a working scaffold, cards that move on screen, nothing saved |
