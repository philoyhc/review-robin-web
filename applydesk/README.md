# applydesk/

ApplyDesk: applications, assessment through Review Robin, and applicant
communication, mounted under Cordware at `/applydesk`. Segment AD1 item 1
built the package and its health path; nothing else answers yet. Rulings
and the MVP roadmap are in `guide/todo_master.md`.

| Path | Holds |
|---|---|
| `main.py`, `routes_health.py` | The factory and `/health` |
| `templates/applydesk/` | Templates; `base.html` carries the favicon |
| `tests/` | ApplyDesk's tests, with a host harness (`tests/_host.py`) |
| `docs/applydesk_functional_spec_v0.6b_agent_handoff.md` | The functional baseline (v0.6b, 2 November 2026); where a ruling in `guide/todo_master.md` differs, the ruling wins |
| `spec/applications.md` | ApplyDesk as the host sees it: registry entry, health, running alone, the URL map |
| `spec/architecture.md` | Package layout, import boundaries, packaging, tests and CI |
| `guide/todo_master.md` | Rulings, the MVP roadmap and open decisions |
| `guide/segment_AD1_skeleton.md` | Segment AD1 plan: the package and mount, then the URL map as placeholders |
