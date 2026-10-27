# Segment 1B — Residential Operations: rosters and organization

**Opened:** 2026-10-26 · **Theme:** the shared core's admin screens, settled on placeholders first, then wired to its databases, identity, organization tree and rosters · **Related:** `residentialapps/guide/archive/segment_1A_package_and_mounts.md` (the package and mounts this builds on; closed 2026-10-26), `residentialapps/guide/todo_master.md`, `residentialapps/docs/residentialapps_identity.md`, `residentialapps/docs/residentialapps_roster_structure.md`, `residentialapps/docs/residentialapps_roles.md`

## Opportunity

After 1A both applications mount and answer `health`, and nothing else exists. Step 1 of the sequence (ruling 11; revised by ruling 13) needs the shared core's admin screens: organization, Staff and RA rosters, identity status and sys admin grants. Those screens share filters, labels and layout, so they are cheapest to settle together before any service exists to constrain them.

## Status

**Paused after item 1** (author, 2026-10-27, `residentialapps/guide/todo_master.md` ruling 13). Item 1, the screens, is built (`#3289`, `#3290`, `#3291`; read once, at rung 3) and awaits the author's approval. RA Leave's placeholder screens come next, to firm up the UX conventions; items 2–5 resume after them, as the core RA Leave is built on.

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
- **Sys admin** is granted and revoked by the super-admin only, with no-self-action and last-sys-admin floors (`residentialapps_roles.md`).

## Judgment calls — decided

- Databases come before identity: the Person table needs a database.
- The structure CSV comes before the roster CSVs: a roster row resolves its node by code.
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

**Item 1 — Screens.** 1. Organization page: level labels, the tree with floors, the structure-CSV card with a sample preview. 2. Roster pages: level filters, link status, read-only access chips, the roster-CSV card. 3. Identity and access pages: not-registered, person detail, sys admin grants. Last build rung. 4+. Iteration until approved, each with its own read.

**Item 2 — Databases.** 1. Settings, engines, both histories. 2. CI round-trip of both on Postgres. Last build rung.

**Item 3 — Identity.** 1. Cordware: `tid` and UPN on `Identity`, tests in `cordware/tests`. 2. Person and institutional-identity models, binding service, audit events. 3. Sign-in flow and `RES_` fake roles; wire not-registered and person detail. 4. sys admin grant and revoke; wire its page. Last build rung.

**Item 4 — Organization.** 1. Models and migration. 2. Structure CSV: parse, preview, commit, export. 3. Wire the organization page. Last build rung.

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
- `residentialapps/docs/residentialapps_roster_structure.md` — revised to the per-Unit levels, node tree and structure CSV (Item 4).
- `residentialapps/guide/todo_master.md` — the entries this segment finishes, deleted at close.
