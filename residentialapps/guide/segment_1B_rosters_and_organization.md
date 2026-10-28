# Segment 1B — Residential Operations: rosters and organization

**Opened:** 2026-10-26 · **Theme:** the shared core's admin screens, settled on placeholders first, then wired to its databases, identity, organization tree and rosters · **Related:** `residentialapps/guide/archive/segment_1A_package_and_mounts.md` (the package and mounts this builds on; closed 2026-10-26), `residentialapps/guide/todo_master.md`, `residentialapps/docs/residentialapps_identity.md`, `residentialapps/docs/residentialapps_roster_structure.md`, `residentialapps/docs/residentialapps_roles.md`

## Opportunity

After 1A both applications mount and answer `health`, and nothing else exists. Step 1 of the sequence (ruling 11; revised by ruling 13) needs the shared core's admin screens: organization, Staff and RA rosters, identity status and sys admin grants. Those screens share filters, labels and layout, so they are cheapest to settle together before any service exists to constrain them.

## Status

**Paused after item 1** (author, 2026-10-27, `residentialapps/guide/todo_master.md` ruling 13). Item 1, the screens, is built (`#3289`, `#3290`, `#3291`; read once, at rung 3) and awaits the author's approval. RA Leave's placeholder screens come next, to firm up the UX conventions; items 2–5 resume after them, as the core RA Leave is built on.

- **Iteration rung 4, 2026-10-27** (author's browser check): the tree is approved; Level labels gain a *Used* flag per level, and the Appointments card becomes five editable slots of title, type and level (`residentialapps/guide/todo_master.md`, organization levels, amended).
- **Iteration rung 5, 2026-10-27** (author's browser check): levels and appointments become rows with **+** and **X** (no fixed count, no *Used* flag), after RRW's response-field rows; Appointments gains an *Abbrev* column; Admin is *Residential Admin*, and *Other Staff* joins the defaults; up to five levels and ten appointments (the same ruling, amended).
- **Iteration rung 6, 2026-10-27** (author's browser check): both row builders take RRW's Band 3 measures — 16px text in 30px boxes, 32px glyph buttons, 4px cells, a rule under each row.
- **Iteration rung 7, 2026-10-27** (author's browser check): boxes, selects and buttons in the row builders all 30px tall; the tree's Floors column becomes *Area*, and Level and Area indent with Node; the tree says its appointees come from the two rosters.
- **Iteration rung 8, 2026-10-27** (author): the tree's columns are Level, Dorms (was Area), Node, Appointed; node codes become abbreviation-hyphen-number (`RSLM-01`, `RF-01`, `RA-01`) in the sample data and the mock CSVs.
- **Iteration rung 9, 2026-10-27** (author): only Level indents with the hierarchy; Dorms and Node sit flush, and no cell in the tree is bold.
- **Iteration rung 10, 2026-10-27** (author): Node becomes *Post* on the tree and the Staff roster; the Unit's posts read Master, Admin-01; Appointments becomes *Appointment types*, with Master and Admin as abbreviations. Posts ruled in `residentialapps/guide/todo_master.md` (organization levels, amended). A backup is a dated second post (Grace Ho on RF-04 beside RF-02), so RA-04–RA-06 report to both. The appointment-types CSV is next.
- **Iteration rung 11, 2026-10-27** (author): the setup CSVs — appointment types first (`Title,Abbrev,Type,Level`, which sets the level labels), then structure, one row per post (`Level,Dorms,Post`), the tree derived from Dorms; ruled in `residentialapps/guide/todo_master.md` (organization setup CSVs), superseding the 2026-10-26 structure CSV. The RA roster appoints to posts too. Mock files reworked; `residentialapps/tests/test_sample_data.py` keeps them coherent.
- **Iteration rung 12, 2026-10-27** (author): the roster tables after RRW's roster pages — a tick box per row opening an expander of row actions, a lobby-style filter box beside the filter selects, the CSV actions in the CSV card (`residentialapps/spec/residentialops_ui.md` §6). Edit fades when more than one row is ticked, after RRW.
- **Iteration rung 13, 2026-10-27** (author): the Organization tree takes the roster tables' tick boxes and expander, with Retire for End appointment; Expand all goes, the tree having nothing to fold.
- **Iteration rung 14, 2026-10-27** (author): a value repeated across the three tables is a pill where it is derived and plain text where it is set (`residentialapps/spec/residentialops_ui.md` §6); the RA roster splits its post from its Precinct.
- **Iteration rung 15, 2026-10-27** (author): setup runs in order. Rosters gains a Home (`/rosters/`: each step's state, Checks, and first-run help after RRW's lobby), and Organization moves to `/rosters/organization` with the appointment types first, the levels to their right and the tree below; the tree opens once types and levels are saved, the rosters once the tree has a node at every level (`residentialapps/spec/residentialops_ui.md` §7). Placeholders preview each state with `?stage=`.
- **Iteration rung 16, 2026-10-27** (author): the placeholders follow organization by units (`residentialapps/guide/todo_master.md`). The rosters hold people and appointments, each page with its appointment types; Organization is the Unit's levels and 30 slots (the author's breakdown, buildings renamed) with Staff and RA cells; person detail shows their slots as pills; Home's steps are slots, the Staff roster, the RA roster, then the cells. The sample module is the mock data, held to it by `residentialapps/tests/test_sample_data.py`.
- **Ruled 2026-10-28** (author): rosters, terms and assignments (`residentialapps/guide/todo_master.md`): appointment types tables go, roster uploads append, Organization becomes Assignments by term with a Terms page and moded uploads; Quick setup held. The placeholders follow in three slices: the rosters' Abbrev column and append copy (rung 17), the Terms page with the Organization → Assignments rename and Home's five steps, then the Assignments page by term.
- **Rung 18** (2026-10-28): the Terms page (`/rosters/assignments/terms`, a detour with `?return_to=`) with mock terms, Organization renamed Assignments (`/rosters/assignments`), and Home's five steps. The term selector, Copy from Term N and the upload modes follow in rung 19; the Organization CSV and its files are renamed there with their Term column.
- **Rung 19** (2026-10-28): Assignments by term: the term card (a live selector, Copy from, Set up terms), past terms read-only, an upcoming term empty until copied or uploaded, the partial-overlap warning (Umairah Salleh, 14 days), and the Assignments CSV with its `Term` column and upload-mode select. The `organization*.csv` mocks become `assignments*.csv`, plus `assignments_term2.csv` for Add a term. Quick setup is held, its file unchanged but for Umairah's start date.
- **Rung 20** (2026-10-28, author's refinements): Home's Terms and Slots steps merge into one, 1 Setup; the Assignments CSV's upload mode is a radio group.

## Decision

**One segment, five items, in order.** Item 1 scaffolds every screen. Items 2–5 wire them, each replacing a page's example data with real data. The segment closes as a whole.

| Item | Lands | Wires |
|---|---|---|
| 1. Screens | Placeholders on RRW's templates and design system, filled with Unit 1's example data (one Wing, three Precincts, ten Neighborhoods), controls inert; iterated until the author approves | — |
| 2. Databases | Both databases' settings and engines; one `alembic.ini` with two histories; empty first migrations; the Postgres round-trip of both in CI | — |
| 3. Identity | Cordware's identity gains tenant ID and UPN; Person with `person_id`; first-sign-in binding; sys admin granted by the super-admin; `RES_` fake roles | Not-registered page, person detail, sys admin grants |
| 4. Organization | Unit, level labels, nodes, floor segments, appointment-to-level map; the structure CSV | Organization page |
| 5. Rosters | Appointments, dated backup reporting, derived reporting; Staff and RA roster CSVs | Roster pages |

**Rejected: the screens as their own segment** (the author's three-segment option). Its close would have nothing to record before wiring; the screens-before-services order is held by item 1's approval gate instead.

**Rejected: wiring before screens** (`#3274`'s shape). Services built before the screens are seen get reshaped once they are.

**Rejected: canvas mockups instead of templates.** A mockup is redrawn when built; a placeholder template is the page the wiring items fill.

## Semantics

- **Item 1's gate:** no wiring item starts until the author approves the screens. Each later item may change a page only as far as real data requires; any further change goes back to the author.
- **Sample data is labelled** on every placeholder, and lives in one module so it can be deleted in one place.
- **Binding** follows `residentialapps_identity.md` §6. No trusted (tenant, object ID) means no link and no access. The match is exact on email or UPN against exactly one unlinked Person, and uniqueness constraints guard concurrent first sign-ins.
- **Databases per app:** `/residentialops` needs one URL, `/supportlogs` both (ruling 4). Runtime roles hold DML only.
- **Structure import:** the file is the Unit's complete tree. A missing node is end-dated, and a node with a current appointment blocks the import. Floor gaps and overlaps warn.
- **Reporting** is derived from the tree; only dated backups are stored.
- **Across the tables**: organization by units, ruled in `residentialapps/guide/todo_master.md` (2026-10-27), superseding posts and the inter-table rules; items 4 and 5 implement it, and the placeholders follow it next.
- **Sys admin** is granted and revoked by the super-admin only, with no-self-action and last-sys-admin floors (`residentialapps_roles.md`).

## Judgment calls — decided

- Databases come before identity: the Person table needs a database.
- The setup CSVs come before the roster CSVs: a roster row appoints a person to a post the tree holds.
- The appointment-to-level map lives on the Unit and is edited on the organization page.
- Item 1 takes its `diff-reviewer` read on the item's cumulative diff at rung 3, its last build rung. An iteration rung after that read reopens `app/`-style code (templates, sample data), so each takes its own read, as `CLAUDE.md` "Where work runs" requires.

## Blast radius (measured)

Taken 2026-10-26 at `b63604f`; 1A's files are counted when 1A closes.

| What | Count | Command |
|---|---|---|
| Identity claims exposed today | `principal_id`, `email`, `name`; no tenant or UPN | `sed -n 40,46p cordware/identity.py` |
| Alembic configs | 1 (RRW's root `alembic.ini`) | `ls alembic.ini residentialapps/alembic.ini 2>/dev/null` |
| Identity spec acceptance scenarios to test | 11 | `grep -c "^[0-9]*\. \*\*" residentialapps/docs/residentialapps_identity.md` |

## PR ladder

**Item 1 — Screens.** 1. Organization page: level labels, the tree with floors, the structure-CSV card with a sample preview. 2. Roster pages: level filters, link status, ~~read-only access chips~~ (no Access column, ruled 2026-10-28), the roster-CSV card. 3. Identity and access pages: not-registered, person detail, sys admin grants. Last build rung. 4+. Iteration until approved, each with its own read.

**Item 2 — Databases.** 1. Settings, engines, both histories. 2. CI round-trip of both on Postgres. Last build rung.

**Item 3 — Identity.** 1. Cordware: `tid` and UPN on `Identity`, tests in `cordware/tests`. 2. Person and institutional-identity models, binding service, audit events. 3. Sign-in flow and `RES_` fake roles; wire not-registered and person detail. 4. sys admin grant and revoke; wire its page. Last build rung.

**Item 4 — Organization.** 1. Models and migration. 2. Setup CSVs, appointment types then structure: parse, preview, commit, export. 3. Wire the organization page. Last build rung.

**Item 5 — Rosters.** 1. Appointments and reporting. 2. Roster CSVs. 3. Wire the roster pages. Last build rung.

## Definition of done

- The author approved item 1's screens; no page shows sample data at close.
- Both Alembic histories round-trip on Postgres in CI.
- The identity spec's acceptance scenarios 1–11 each have a test.
- Unit 1's ten-row structure file imports, previews, and re-imports with a retire.
- Staff and RA roster CSVs import against that tree, and an RA's reporting RF is derived.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 1B` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **The `residential` lane once Residential has databases** (1A's cold read, 2026-10-26): it skips RRW's suite and the Postgres job, but RRW's tests build every registered factory through `cordware.main`, so a Residential side effect on shared state (an engine hook, a setting read at build) would first fail on `main`. Item 2 decides whether the lane runs those RRW tests or Residential's factories stay side-effect free.

Where Residential's specs live was ruled with 1A's drafts: `residentialapps/spec/` (author, 2026-10-26).

## Out of scope

- Leave cycles, entitlements and applications: RA Leave, next (ruling 13).
- Support Logs authorizations and content, then RA Events: after RA Leave.
- Multi-Unit authorization: open in `todo_master.md`, needed before a second Unit is exposed.

## Doc impact

- `cordware/spec/identity.md` — tenant ID and UPN on the identity (Item 3).
- `residentialapps/docs/residentialapps_identity.md` — revised to what shipped (Item 3).
- `residentialapps/docs/residentialapps_roster_structure.md` — revised to organization by units: levels, slots and their Staff and RA cells (Item 4).
- `residentialapps/spec/organization_and_rosters.md` — new: the whole contract for the levels, slots, rosters, appointment types and cells, their inter-table rules and CSV precedence, Quick setup included, written as items 4 and 5 ship (author, 2026-10-27).
- `residentialapps/guide/todo_master.md` — the entries this segment finishes, deleted at close.
