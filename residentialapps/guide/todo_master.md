# Residential Apps — open work

**Opened 2026-10-25** (author). Residential's own to-do: what is ruled, what it depends on from the Cordware deployment strategy (v1.0, held privately with the deployment), and what is still to decide or revise. RRW's `guide/todo_master.md` covers RRW and the Cordware host only. Residential's specs are in `residentialapps/docs/`; shared UX guidance is RRW's `docs/cordware_mobile_to_desktop.md`.

## Rulings (author, 2026-10-25)

1. **One package, two applications.** One `residentialapps/` package (`core/`, `leave/`, `events/`, `supportlogs/`, `web/`), mounted as two applications: **RA Operations at `/residentialops`** and **Support Logs at `/supportlogs`**, each with its own factory, landing-page entry, health path (`/residentialops/health`, `/supportlogs/health`), database and permissions. **Nothing is mounted at `/residentialapps`**, which names only the package. The two may share code; neither imports the other's routes.
2. **The shared core's admin** (Staff and RA rosters, appointments, units) lives under `/residentialops`, beside the core's own database. Support Logs only reads it.
3. **No neutral Residential screens.** Cordware's landing page lists both applications; the neutral sign-in landing and switcher in `residentialapps/docs/support_logs_ui_spec_v0.1.md` are dropped.
4. **Database URLs per mount.** `/residentialops` needs `RES_OPS_DATABASE_URL` only. `/supportlogs` needs both: it reads `residentialops` through the shared core as `residentialops_app`, and it is the only code that opens a `supportlogs` session.
5. **Each application runs with Cordware alone.** `CORDWARE_APPS=supportlogs` and `CORDWARE_APPS=residentialops` each start and work, locally and in CI.
6. **Registry entries** `residentialops` and `supportlogs`; logger prefixes `residentialapps.ops` and `residentialapps.supportlogs`, neither nested in the other; lifespan state keys prefixed per application.
7. **Import boundaries** in RRW's existing `cordware/tests/test_import_boundary.py`, extended: neither application imports the other's routes; Leave and Events stay apart; only Support Logs opens `supportlogs`.
8. **Fake roles** use one `RES_` prefix, over a role list reconciled across both functional specs (below), written in the first segment plan.
9. **Alembic:** one `alembic.ini`, two histories (`residentialapps/alembic/residentialops/`, `residentialapps/alembic/supportlogs/`). The core's first migration lands in the scaffold segment.
10. **Stale text:** the deployment strategy and RRW's `guide/todo_master.md` are corrected now; the functional specs carry a banner and are revised at their next version.
11. **Segment shape** (sequence revised the same day): first, RA Operations' rosters: the scaffold (package, both mounts, CI with both databases) and the core's admin under `/residentialops` for the Staff and RA rosters, appointments and units; then Support Logs; then RA Leave, which adds cycles and leave on the finished core; then RA Events. The RA Events spec is written before RA Leave is built.

## Roles

Ruled 2026-10-25: `residentialapps/docs/residentialapps_roles.md`.

## What Residential takes from the deployment strategy

- **Built here from scratch**, in this public repository, imported into production as allowlisted runtime code (its `spec/`, `docs/`, `guide/` and tests are not imported).
- **Every RRW baseline item applies:** runs with Cordware alone, on localhost with fake roles; its own tests and CI; mount-aware URLs with a leak test and a GET crawl; RRW's practice (plan in, spec out; maker ≠ checker).
- **Import boundary:** `residentialapps` never imports `app` (RRW), and `app` and `cordware` never import `residentialapps`.
- **Databases:** `residentialops` (core, Leave, Events, their permissions and audit, the email outbox; module table prefixes `core_`, `leave_`, `events_`) and `supportlogs` (students, encounters, follow-ups, assignments, safety records, review results, authorizations, peer-view grants, their audit). Runtime roles `residentialops_app` and `supportlogs_app` hold DML only; migrations run as the owner; `PUBLIC` holds no `CONNECT` or `TEMPORARY`. Cross-database references use stable IDs, never deleted, checked by a test. Locally `./residentialops.db` and `./supportlogs.db`; CI round-trips both histories on Postgres with two Residential-only databases.
- **Identity** comes from Cordware (email, display name, Entra object ID). Residential maps it to its own people by email and records the object ID at first sign-in. Appointments are not permissions. Support Logs needs an active Staff-roster entry **and** an active Support Logs authorization, both checked on every request; RAs never see Support Logs. The platform super-admin administers Residential, but in Support Logs holds administration only (no support content or support-activity audit), and named decisions stay with the named person.
- **Presentation:** each application its own name, entry point, navigation and accent (Support Logs teal `#0f766e`, RA Operations fuchsia `#a21caf`, RRW blue), on RRW's design system; server-rendered, no frontend framework; each surface classed by device (`docs/cordware_mobile_to_desktop.md`).
- **Email:** RA Leave sends as the actor with delegated `Mail.Send` through an outbox in `residentialops`; Support Logs v1 sends no email. Directory lookup uses delegated `User.ReadBasic.All`. Both grants are deployment prerequisites.
- **Audit:** business actions only, each pillar's in its own database, on RRW's envelope-and-registered-types model. In Support Logs reads of identifiable data are audited, and support content never reaches operational logs.
- **Order** (ruling 11): RA Operations' rosters, Staff and RA, with the scaffold → Support Logs (most urgent, simplest, needs no email) → RA Leave (adds cycles) → RA Events.

## Decide before Support Logs goes live

- `supportlogs` retention, backup and export, and who may run them (`residentialapps/docs/resident_support_log_functional_spec_v0.3.md` §17 Q3, Q16).
- The policy questions in the same §17: Q4, Q8 and Q11, which bear on the authorization types.
- Core admin and Support Logs authorization admin both working.

## Reconcile in the first segment plan

- **Role names:** administrator is "Administrator", "System Administrator", "Leave administrator" and "Residential admin" across the specs; who administers the shared core is not named.
- **Appointments:** RF, RSLM, Master, RA, and the Master's admin delegate; a Support Logs delegate is granted at the Master's request.
- **Unit vocabulary:** unit, team, house and cluster (`cluster_id` is a core unit).
- **RA Events** has no functional spec yet.

## Revise at each spec's next version

- `residentialapps/docs/ra_leave_management_functional_spec_v0.4.md`: the header and introduction ("a single application", `/residentialapps`), the implementation and Platform sections (`/residentialapps`), the open-items list, scenario Q ("Cordware + Residential Apps"); the strategy version its header cites (v0.9).
- `residentialapps/docs/resident_support_log_functional_spec_v0.3.md`: header and §1.1 (`/residentialapps`, "share one application"), §14 hosting, the v0.9 reference in §12.
- `residentialapps/docs/support_logs_ui_spec_v0.1.md`: §1 item 6 ("stays one Residential application"), and the neutral shared Residential screens in the colour sections (ruling 3).
