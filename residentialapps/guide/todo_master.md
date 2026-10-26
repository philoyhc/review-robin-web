# Residential Apps — open work

**Opened 2026-10-25** (author). Residential's own to-do: what is ruled, what it depends on from the Cordware deployment strategy (v1.0, held privately with the deployment), and what is still to decide or revise. RRW's `guide/todo_master.md` covers RRW and the Cordware host only. Residential's functional specs and working designs are in `residentialapps/docs/`, and its contracts in `residentialapps/spec/` (ruled 2026-10-26, segment 1A); shared UX guidance is RRW's `docs/cordware_mobile_to_desktop.md`.

## Stubs

- **`tools/close_check.py` learns Residential's plans** *(filed 2026-10-26, at 1A's close)*: it finds a plan only in RRW's `guide/` and `guide/archive/`, so 1A's close was checked by hand. Searching `residentialapps/guide/` and its `archive/` too lets 1B close with the tool. One `tools/` PR with tests, before 1B closes.

## Rulings (author, 2026-10-25)

1. **One package, two applications.** One `residentialapps/` package (`core/`, `leave/`, `events/`, `supportlogs/`, `web/`), mounted as two applications: **Residential Operations at `/residentialops`** and **Support Logs at `/supportlogs`**, each with its own factory, landing-page entry, health path (`/residentialops/health`, `/supportlogs/health`), database and permissions. **Nothing is mounted at `/residentialapps`**, which names only the package. The two may share code; neither imports the other's routes.
2. **The shared core's admin** (Staff and RA rosters, appointments, units) lives under `/residentialops`, beside the core's own database. Support Logs only reads it.
3. **No neutral Residential screens.** Cordware's landing page lists both applications; the neutral sign-in landing and switcher in `residentialapps/docs/support_logs_ui_spec_v0.1.md` are dropped.
4. **Database URLs per mount.** `/residentialops` needs `RES_OPS_DATABASE_URL` only. `/supportlogs` needs both: it reads `residentialops` through the shared core as `residentialops_app`, and it is the only code that opens a `supportlogs` session.
5. **Each application runs with Cordware alone.** `CORDWARE_APPS=supportlogs` and `CORDWARE_APPS=residentialops` each start and work, locally and in CI.
6. **Registry entries** `residentialops` and `supportlogs`; logger prefixes `residentialapps.ops` and `residentialapps.supportlogs`, neither nested in the other; lifespan state keys prefixed per application.
7. **Import boundaries** in RRW's existing `cordware/tests/test_import_boundary.py`, extended: neither application imports the other's routes; Leave and Events stay apart; only Support Logs opens `supportlogs`.
8. **Fake roles** use one `RES_` prefix, over a role list reconciled across both functional specs (below), written in the first segment plan.
9. **Alembic:** one `alembic.ini`, two histories (`residentialapps/alembic/residentialops/`, `residentialapps/alembic/supportlogs/`). The core's first migration lands in the scaffold segment.
10. **Stale text:** the deployment strategy and RRW's `guide/todo_master.md` are corrected now; the functional specs carry a banner and are revised at their next version.
11. **Segment shape** (sequence revised the same day): first, Residential Operations' rosters: the scaffold (package, both mounts, CI with both databases) and the core's admin under `/residentialops` for the Staff and RA rosters, appointments and units; then Support Logs; then RA Leave, which adds cycles and leave on the finished core; then RA Events. The RA Events spec is written before RA Leave is built. Step 1 is planned as segments 1A, the package and mounts (closed 2026-10-26, `residentialapps/guide/archive/segment_1A_package_and_mounts.md`), and 1B, the admin screens and their wiring (`residentialapps/guide/segment_1B_rosters_and_organization.md`).
12. **Rename** (author, 2026-10-26): the application at `/residentialops` is **Residential Operations**, formerly RA Operations. The name was replaced wherever it appeared, these rulings included; mount, package, database and route names are unchanged.

## Roles

Ruled 2026-10-25: `residentialapps/docs/residentialapps_roles.md`.

## What Residential takes from the deployment strategy

- **Built here from scratch**, in this public repository, imported into production as allowlisted runtime code (its `spec/`, `docs/`, `guide/` and tests are not imported).
- **Every RRW baseline item applies:** runs with Cordware alone, on localhost with fake roles; its own tests and CI; mount-aware URLs with a leak test and a GET crawl; RRW's practice (plan in, spec out; maker ≠ checker).
- **Import boundary:** `residentialapps` never imports `app` (RRW), and `app` and `cordware` never import `residentialapps`.
- **Databases:** `residentialops` (core, Leave, Events, their permissions and audit, the email outbox; module table prefixes `core_`, `leave_`, `events_`) and `supportlogs` (students, encounters, follow-ups, assignments, safety records, review results, authorizations, peer-view grants, their audit). Runtime roles `residentialops_app` and `supportlogs_app` hold DML only; migrations run as the owner; `PUBLIC` holds no `CONNECT` or `TEMPORARY`. Cross-database references use stable IDs, never deleted, checked by a test. Locally `./residentialops.db` and `./supportlogs.db`; CI round-trips both histories on Postgres with two Residential-only databases.
- **Identity** comes from Cordware (email, display name, Entra object ID). Residential maps it to its own people by email and records the object ID at first sign-in. Appointments are not permissions. Support Logs needs an active Staff-roster entry **and** an active Support Logs authorization, both checked on every request; RAs never see Support Logs. The platform super-admin administers Residential, but in Support Logs holds administration only (no support content or support-activity audit), and named decisions stay with the named person.
- **Presentation:** each application its own name, entry point, navigation and accent (Support Logs teal `#0f766e`, Residential Operations fuchsia `#a21caf`, RRW blue), on RRW's design system; server-rendered, no frontend framework; each surface classed by device (`docs/cordware_mobile_to_desktop.md`).
- **Email:** RA Leave sends as the actor with delegated `Mail.Send` through an outbox in `residentialops`; Support Logs v1 sends no email. Directory lookup uses delegated `User.ReadBasic.All`. Both grants are deployment prerequisites.
- **Audit:** business actions only, each pillar's in its own database, on RRW's envelope-and-registered-types model. In Support Logs reads of identifiable data are audited, and support content never reaches operational logs.
- **Order** (ruling 11): Residential Operations' rosters, Staff and RA, with the scaffold → Support Logs (most urgent, simplest, needs no email) → RA Leave (adds cycles) → RA Events.

## Decide before Support Logs goes live

- `supportlogs` retention, backup and export, and who may run them (`residentialapps/docs/resident_support_log_functional_spec_v0.3.md` §17 Q3, Q16).
- The policy questions in the same §17: Q4, Q8 and Q11, which bear on the authorization types.
- Core admin and Support Logs authorization admin both working.

## Reconcile in the first segment plan

- **Identity and roster structure** (2026-10-26): `residentialapps/docs/residentialapps_identity.md` §12 lists what it changes in this file, the RA Leave spec and the roles doc; `residentialapps/docs/residentialapps_roster_structure.md` §10 lists the decisions still to confirm.
- **Roster structure, ruled 2026-10-26** (author, on `residentialapps/docs/residentialapps_roster_structure.md` §10):
  1. The area an RF oversees is a **Precinct** (tentative; the doc's working name was "RF Zone"). RA **Neighborhood** stays.
  2. **Both exceptions from the start:** a Precinct may span more than one Tower (so it is a set of floor-range segments, not one range), and an RA may report to another RF for a dated period (a backup reporting assignment beside the primary one).
  3. **Neighborhoods warn, not block:** gaps and overlaps against their Precinct are flagged for administrator review; real-world exceptions still save.
  4. **Cordware's identity gains the tenant ID and UPN** (`tid` and the UPN claim), so Residential binds on (tenant, object ID) as the identity spec says; a small Cordware change in the scaffold segment, tested in `cordware/tests`.
  - Still open: multi-Unit authorization (§10's last item), before more than one Residential Unit is exposed.
- **Organization levels, ruled 2026-10-26** (author; supersedes the roster doc's fixed Wing / Tower / RF Zone / Neighborhood, and turns rulings 1 and 2 above into configuration). After RRW's renamable roster tags (`spec/csv_contracts.md` §1a):
  1. **Three fixed level slots per Unit** (`level_1`, `level_2`, `level_3`), each with the Unit's own friendly label; Unit 1's are Wing, Precinct, Neighborhood. Code and data use the slots, never the labels, so renaming a level is a label edit. A fourth slot, if ever needed, is a migration.
  2. **One tree of organization nodes** (unit, level, parent one level up, code, name, dated), not a table per term.
  3. **Floors only on the bottom level**: a node carries one or more floor-range segments (building + floors), which is how a node spans towers; Tower is part of a segment, not a level. Higher levels cover the union of their children; gaps and overlaps warn (ruling 3 above).
  4. **Appointment type → level is configured per Unit**; Unit 1's are RSLM → level 1, RF → level 2, RA → level 3, with Master and the administrators covering the whole Unit.
  5. **Reporting is derived**: an RA reports to the RF holding the parent node. Only the dated backup and temporary arrangements are stored explicitly.
  6. **CSV headers carry the labels** as RRW's do (`Level1.Wing`); headcount norms (3 RFs + 1 RSLM per Wing, 3–4 RAs per RF) are per-Unit warnings, never constraints.
- **Organization-structure CSV, ruled 2026-10-26** (author): a Unit's whole tree uploads as one file, **one row per bottom-level node**, naming positions, never people (people attach through appointments):

  | `Level1.Wing` | `Level2.Precinct` | `Level3.Neighborhood` | `Floors` |
  |---|---|---|---|
  | Cypress | RF1 | RA1 | Cypress A 04-05-06 |
  | Cypress | RF1 | RA2 | Cypress A 07-08-09 |
  | Cypress | RF1 | RA3 | Cypress A 10-11-12 |

  1. **Every level is its own column**, headed with the Unit's label (which the import sets and the export writes back); higher nodes exist because a row names them.
  2. **Floors are a building and its floors joined by hyphens**; several buildings in one cell are separated by `;` (`Cypress A 10-11-12; Cypress B 01-02`). Every floor is listed, so no gap hides in a range.
  3. **The file is the Unit's complete structure.** The preview lists new, changed and to-retire nodes, unknown or duplicate codes, and floor gaps and overlaps (warnings); on confirm a missing node is end-dated, never deleted, and a node with a current appointment blocks the import until the appointment is ended or moved.

- **Role names** (terms ruled 2026-10-26: *sys admin* the system role, *admin* the appointment, `residentialapps/docs/residentialapps_roles.md`): administrator is "Administrator", "System Administrator", "Leave administrator" and "Residential admin" across the specs; who administers the shared core is not named.
- **Appointments:** RF, RSLM, Master, RA, and the Master's admin delegate; a Support Logs delegate is granted at the Master's request.
- **Unit vocabulary:** unit, team, house and cluster (`cluster_id` is a core unit).
- **RA Events** has no functional spec yet.

## Revise at each spec's next version

- `residentialapps/docs/ra_leave_management_functional_spec_v0.4.md`: §2.5 classes approver actions mobile-critical, not responsive (page map, `residentialapps/spec/applications.md`, author 2026-10-26); the header and introduction ("a single application", `/residentialapps`), the implementation and Platform sections (`/residentialapps`), the open-items list, scenario Q ("Cordware + Residential Apps"); the strategy version its header cites (v0.9).
- `residentialapps/docs/resident_support_log_functional_spec_v0.3.md`: header and §1.1 (`/residentialapps`, "share one application"), §14 hosting, the v0.9 reference in §12. §3.5 gains the Other Staff view authorization (roles doc rule 8), and "Administrator" becomes *sys admin* (roles doc, "Terms").
- `residentialapps/docs/support_logs_ui_spec_v0.1.md`: whether Support Logs keeps its bottom bar (its §2 and §5) or takes Residential Operations' slim top bar (`residentialapps/spec/applications.md`, "One chrome, phone first"); §1 item 6 ("stays one Residential application"), and the neutral shared Residential screens in the colour sections (ruling 3).
