# residentialapps/

Residential Apps: one package, mounted under Cordware as two applications, **RA Operations** at `/residentialops` and **Support Logs** at `/supportlogs` (author, 2026-10-25). Nothing is built yet; open work, rulings and what Residential depends on are in `guide/todo_master.md`.

| Path | Holds |
|---|---|
| `docs/ra_leave_management_functional_spec_v0.4.md` | RA Leave functional spec (RA Operations) |
| `docs/resident_support_log_functional_spec_v0.3.md` | Support Logs functional spec |
| `docs/residentialapps_identity.md` | Identity and roster linking: permanent `person_id`, Entra binding at first matching sign-in, the not-registered response (adopted 2026-10-26) |
| `docs/residentialapps_roles.md` | Roles in both applications, read across from RRW's super-admin, admin and operator (ruled) |
| `docs/residentialapps_roster_structure.md` | Rosters, appointments and residential geography: Unit, Wing, Tower, RF Zone, RA Neighborhood, coverage and reporting (working design; §10 open) |
| `docs/support_logs_ui_spec_v0.1.md` | Support Logs UI spec (draft): RF / RSLM phone screens on RRW's design system |
| `guide/segment_1A_rosters_and_organization.md` | Segment 1A plan: the package, both mounts, and every shared-core admin screen as a placeholder (step 1, first half) |
| `guide/segment_1B_rosters_and_organization_wiring.md` | Segment 1B plan: databases, identity, organization and rosters, wiring 1A's screens (step 1, second half) |
| `guide/todo_master.md` | Rulings, dependencies, open decisions and pending revisions |

Shared UX guidance for every Cordware application is RRW's `docs/cordware_mobile_to_desktop.md`.
