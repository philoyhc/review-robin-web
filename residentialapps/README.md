# residentialapps/

Residential Apps: one package, mounted under Cordware as two applications, **Residential Operations** at `/residentialops` and **Support Logs** at `/supportlogs` (author, 2026-10-25). Both mount and answer `/health`, and nothing else is built yet; open work, rulings and what Residential depends on are in `guide/todo_master.md`.

| Path | Holds |
|---|---|
| `residentialops/` | Residential Operations: its factory (`main.py`, `create_app`) and routes |
| `supportlogs/` | Support Logs: its factory and routes |
| `tests/` | Residential's tests, including the mounted ones through its own host harness (`tests/_host.py`) |
| `docs/graph_learnings.md` | Microsoft Graph as RRW and Utilities found it on the institutional host: reuse the host's client, sign-in name vs mail and aliases, token renewal, who can send email, and the limits to design around (learning notes, 2026-11-01) |
| `docs/ra_leave_management_functional_spec_v0.4.md` | RA Leave functional spec (Residential Operations) |
| `docs/resident_support_log_functional_spec_v0.3.md` | Support Logs functional spec |
| `docs/residentialapps_email_identity_matching.md` | Email aliases and institutional identity matching: the email is a provisional hint, the Entra tenant/object ID the account key; exact trusted UPN and primary-email matching only, administrator correction otherwise (design note, 2026-10-30) |
| `docs/residentialapps_identity.md` | Identity and roster linking: permanent `person_id`, Entra binding at first matching sign-in, the not-registered response (adopted 2026-10-26) |
| `docs/residentialapps_roles.md` | Roles in both applications, read across from RRW's super-admin, admin and operator (ruled) |
| `docs/residentialapps_roster_structure.md` | Rosters, appointments and residential geography: Unit, Wing, Tower, RF Zone, RA Neighborhood, coverage and reporting (working design; §10 open) |
| `docs/sample_data/README.md` | Mock data for browser tests: Example College's 30 Neighborhoods (the author's breakdown), its terms, Staff and RA rosters and Assignments CSVs (clean and error cases), and fake sign-in scenarios, each with its expected outcome |
| `docs/support_logs_ui_spec_v0.1.md` | Support Logs UI spec (draft): RF / RSLM phone screens on RRW's design system |
| `spec/applications.md` | The two applications as the host sees them: registry entries, factories, health, running alone, logging and lifespan |
| `spec/architecture.md` | Package layout, import boundaries, packaging, tests and the `residential` CI lane |
| `spec/residentialops_ui.md` | Residential Operations' UI conventions: widths, chrome, color, buttons, row builders, roster tables, placeholders, accessibility |
| `spec/supportlogs_ui.md` | Support Logs' UI conventions: devices, chrome and tabs by grant, color and safety, controls, lists and tables, what the screens say about privacy, sample data |
| `guide/archive/segment_1A_package_and_mounts.md` | Segment 1A, closed 2026-10-26 (`#3274`→`#3281`): the package, both mounts with health paths, and the `residential` CI lane. **Read `Status`** for the restructures and what the reads caught |
| `guide/segment_1B_rosters_and_organization.md` | Segment 1B plan: the shared core's admin screens scaffolded, then databases, identity, organization and rosters wired to them (paused after item 1 for RA Leave's screens, ruling 13) |
| `guide/segment_1C_ra_leave.md` | Segment 1C plan: RA Leave's screens, phone first, settling Residential's UX conventions (item 1, next); then wired on 1B's core (items 2–5) |
| `guide/1B_browser_checks.md` | Segment 1B item 1's browser walkthrough: the landing, Rosters and setup, a person's page and Sys admin, step by step; deleted when the screens are approved |
| `guide/1C_browser_checks.md` | Segment 1C item 1's browser walkthrough: RA Leave's RA, staff and admin screens and the appeal-mode previews, step by step; deleted when item 1 closes |
| `guide/1D_browser_checks.md` | Segment 1D item 1's browser walkthrough: every Support Logs screen, step by step, with the PowerShell fake-auth commands; deleted when item 1 closes |
| `guide/fake_ids.md` | Every command the browser walkthroughs need: copy-and-paste PowerShell blocks that run Residential Apps locally as each sample viewer, the sample-viewer tables, and the browser settings |
| `guide/todo_master.md` | Rulings, dependencies, open decisions and pending revisions |

Shared UX guidance for every Cordware application is RRW's `docs/cordware_mobile_to_desktop.md`.
