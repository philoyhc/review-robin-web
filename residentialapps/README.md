# residentialapps/

Residential Apps: one package, mounted under Cordware as two applications, **Residential Operations** at `/residentialops` and **Support Logs** at `/supportlogs` (author, 2026-10-25). Both mount and answer `/health`, and nothing else is built yet; open work, rulings and what Residential depends on are in `guide/todo_master.md`.

| Path | Holds |
|---|---|
| `ops/` | Residential Operations: its factory (`main.py`, `create_app`) and routes |
| `supportlogs/` | Support Logs: its factory and routes |
| `tests/` | Residential's tests, including the mounted ones through its own host harness (`tests/_host.py`) |
| `docs/ra_leave_management_functional_spec_v0.4.md` | RA Leave functional spec (Residential Operations) |
| `docs/resident_support_log_functional_spec_v0.3.md` | Support Logs functional spec |
| `docs/residentialapps_identity.md` | Identity and roster linking: permanent `person_id`, Entra binding at first matching sign-in, the not-registered response (adopted 2026-10-26) |
| `docs/residentialapps_roles.md` | Roles in both applications, read across from RRW's super-admin, admin and operator (ruled) |
| `docs/residentialapps_roster_structure.md` | Rosters, appointments and residential geography: Unit, Wing, Tower, RF Zone, RA Neighborhood, coverage and reporting (working design; §10 open) |
| `docs/sample_data/README.md` | Mock rosters for browser tests: Example College's structure, Staff and RA CSVs (clean, re-import and error cases) and fake sign-in scenarios, each with its expected outcome |
| `docs/support_logs_ui_spec_v0.1.md` | Support Logs UI spec (draft): RF / RSLM phone screens on RRW's design system |
| `spec/applications.md` | The two applications as the host sees them: registry entries, factories, health, running alone, logging and lifespan |
| `spec/architecture.md` | Package layout, import boundaries, packaging, tests and the `residential` CI lane |
| `guide/archive/segment_1A_package_and_mounts.md` | Segment 1A, closed 2026-10-26 (`#3274`→`#3281`): the package, both mounts with health paths, and the `residential` CI lane. **Read `Status`** for the restructures and what the reads caught |
| `guide/segment_1B_rosters_and_organization.md` | Segment 1B plan: the shared core's admin screens scaffolded, then databases, identity, organization and rosters wired to them (step 1, second) |
| `guide/todo_master.md` | Rulings, dependencies, open decisions and pending revisions |

Shared UX guidance for every Cordware application is RRW's `docs/cordware_mobile_to_desktop.md`.
