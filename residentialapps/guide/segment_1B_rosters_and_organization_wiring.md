# Segment 1B — RA Operations: rosters and organization, wired

**Opened:** 2026-10-26 · **Theme:** the databases, identity, organization tree and rosters behind the screens 1A settled · **Related:** `residentialapps/guide/segment_1A_rosters_and_organization.md` (the skeleton and screens), `residentialapps/guide/todo_master.md`, `residentialapps/docs/residentialapps_identity.md`, `residentialapps/docs/residentialapps_roster_structure.md`, `residentialapps/docs/residentialapps_roles.md`

## Opportunity

After 1A, every shared-core screen exists with example data and an approved shape, and nothing behind it is real. 1B builds the innards, each item replacing a page's sample data with real data.

## Decision

**Four items, in order, each read once by `diff-reviewer` at its last build rung; the segment closes as a whole.**

| Item | Lands | Wires |
|---|---|---|
| 1. Databases | `residentialops` and `supportlogs` settings and engines; one `alembic.ini` with two histories; an empty first migration each; the Postgres round-trip of both in CI | — |
| 2. Identity | Cordware's identity gains tenant ID and UPN; Person with `person_id`; first-sign-in binding; Administrator granted by the super-admin; `RES_` fake roles | Not-registered page, person detail, Administrator grants |
| 3. Organization | Unit, level labels, nodes, floor segments, appointment-to-level map; the structure CSV (preview, retire, warnings; export with labels) | Organization page |
| 4. Rosters | Appointments, dated backup reporting, derived reporting; Staff and RA roster CSVs resolving nodes by code | Roster pages |

**Rejected: wiring all pages in one item.** Identity, organization and rosters each carry their own schema and rules; one read over all three is too much for one sitting.

## Semantics

- **Binding:** as `residentialapps_identity.md` §6. No trusted (tenant, object ID) means no link and no access. The match is exact on email or UPN against exactly one unlinked Person, and uniqueness constraints guard concurrent first sign-ins.
- **Databases per app:** `/residentialops` needs one URL and `/supportlogs` needs both (ruling 4). Runtime roles hold DML only.
- **Structure import:** the file is the Unit's complete tree. A missing node is end-dated, and a node with a current appointment blocks the import. Floor gaps and overlaps warn.
- **Reporting:** derived from the tree; only dated backups are stored.
- **Administrator:** granted and revoked by the super-admin only, with no-self-action and last-Administrator floors (`residentialapps_roles.md`).

## Judgment calls — decided

- Item 1 precedes identity: the Person table needs a database to live in.
- The structure CSV precedes the roster CSVs: a roster row resolves its node by code.
- The appointment-to-level map lives on the Unit, edited on the organization page.

## Blast radius (measured)

Taken 2026-10-26 at `eb7d5d9`; 1A's pages are counted when 1A closes.

| What | Count | Command |
|---|---|---|
| Identity claims exposed today | `principal_id`, `email`, `name`; no tenant or UPN | `sed -n 40,46p cordware/identity.py` |
| Alembic configs | 1 (RRW's root `alembic.ini`) | `ls alembic.ini residentialapps/alembic.ini 2>/dev/null` |
| Identity spec acceptance scenarios to test | 11 | `grep -c "^[0-9]*\. \*\*" residentialapps/docs/residentialapps_identity.md` |

## PR ladder

**Item 1 — Databases.** 1. Settings, engines, both histories with empty first migrations. 2. CI round-trip of both on Postgres. Last build rung.

**Item 2 — Identity.** 1. Cordware: `tid` and UPN on `Identity`, tests in `cordware/tests`. 2. Person and institutional-identity models, binding service, audit events. 3. Sign-in flow and the `RES_` fake roles; wire the not-registered page and person detail. 4. Administrator grant and revoke; wire its page. Last build rung.

**Item 3 — Organization.** 1. Models and migration. 2. Structure CSV: parse, preview, commit, export. 3. Wire the organization page. Last build rung.

**Item 4 — Rosters.** 1. Appointments, backup reporting, derived reporting. 2. Roster CSVs. 3. Wire the roster pages. Last build rung.

## Definition of done

- Both Alembic histories round-trip on Postgres in CI.
- The identity spec's acceptance scenarios 1–11 each have a test.
- Unit 1's ten-row structure file imports, previews, and re-imports with a retire.
- Staff and RA roster CSVs import against that tree, and an RA's reporting RF is derived.
- No page approved in 1A shows sample data.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 1B` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- None of its own; it inherits 1A's two (the close check, and where Residential's specs live).

## Out of scope

- Support Logs authorizations and content: step 2 of the sequence.
- Leave cycles, entitlements and RA Events: steps 3 and 4.
- Multi-Unit authorization: open in `todo_master.md`, needed before a second Unit is exposed.

## Doc impact

- `cordware/spec/identity.md` — tenant ID and UPN on the identity (Item 2).
- `residentialapps/docs/residentialapps_identity.md` — revised to what shipped (Item 2).
- `residentialapps/docs/residentialapps_roster_structure.md` — revised to the per-Unit levels, node tree and structure CSV (Item 3).
- `residentialapps/guide/todo_master.md` — the entries this segment finishes, deleted at close.
