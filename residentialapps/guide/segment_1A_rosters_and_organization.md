# Segment 1A — RA Operations: rosters and organization setup

**Opened:** 2026-10-26 · **Theme:** the Residential scaffold and the shared core's people, structure and rosters, administered under `/residentialops` · **Related:** `residentialapps/guide/todo_master.md` (rulings, ruling 11 sequence), `residentialapps/docs/residentialapps_identity.md`, `residentialapps/docs/residentialapps_roster_structure.md`, `residentialapps/docs/residentialapps_roles.md`

## Opportunity

Residential has rulings and specs but no code: `residentialapps/` holds only prose. Every later step (Support Logs, RA Leave, RA Events) needs the package, both mounts and databases, a way to recognize who signed in, a Unit's organization tree and its Staff and RA rosters. Segment 1A is step 1 of the author's sequence (ruling 11).

## Decision

**Four items, built in order, each read once by `diff-reviewer` at its last build rung; the segment closes as a whole.** Each UI item lands scaffold-first (a placeholder page with real copy and inert controls), as RRW does.

| Item | Lands | Why here |
|---|---|---|
| 1. Scaffold | The package; `/residentialops` and `/supportlogs` as empty apps with health paths; two databases and Alembic histories; the `residential` CI lane; the import boundaries | Everything else sits on it |
| 2. Identity | Cordware's identity gains tenant ID and UPN; Person with `person_id`; first-sign-in binding; the not-registered page; Administrator granted by the super-admin | Items 3 and 4 need a signed-in Administrator |
| 3. Organization setup | Per-Unit level labels; the node tree with floor segments; the structure CSV with preview, retire and warnings; the admin screen | Rosters attach to nodes |
| 4. Rosters | Staff and RA appointments; the per-Unit appointment-to-level map; roster CSVs; derived reporting with dated backups; the roster screens | Needs people and nodes |

**Rejected: one ladder for the whole segment.** About twenty rungs would put a single `diff-reviewer` read over code, schema and UI together. Four items keep each read sized for one sitting.

**Rejected: rosters before organization.** An appointment points at a node (ruling: appointment type maps to a level), so the tree has to exist first.

## Semantics

- **Health without sign-in:** `/residentialops/health` and `/supportlogs/health` answer before any database is reachable, as RRW's does. They are already excluded from Easy Auth in Azure (Cordware `spec/cordware_setup.md`).
- **Each app alone:** `CORDWARE_APPS=residentialops` and `CORDWARE_APPS=supportlogs` each start; `/supportlogs` needs both database URLs, `/residentialops` one (ruling 4).
- **Binding:** see `residentialapps_identity.md` §6. No trusted (tenant, object ID) means no link and no roster-based access. The match is exact on email/UPN against exactly one unlinked Person, and the database's uniqueness check guards concurrent first sign-ins.
- **Not registered:** the page names nothing and shows no roster content. Its diagnostics go to the audit trail only.
- **Structure import:** the file is the Unit's complete tree. A missing node is end-dated, and a node with a current appointment blocks the import. Floor gaps and overlaps warn rather than block (`todo_master.md`, organization rulings).
- **Reporting:** derived from the tree. An explicit record exists only for a dated backup arrangement.
- **Fake auth:** `RES_` fake roles seed both layers locally (ruling 8), and only while Cordware's fake auth is on.

## Judgment calls — decided

- The structure CSV comes before the roster CSVs (item 3 before 4): a roster row resolves its node by code.
- The appointment-to-level map lives on the Unit, configured on the organization screen, not per appointment.
- Item 1 ships no Residential page beyond `health`; Cordware's landing lists both apps once item 2 can render a page.

## Blast radius (measured)

Taken 2026-10-26 at `7e0ba5d`.

| What | Count | Command |
|---|---|---|
| Residential code today | 0 files outside `docs/`, `guide/`, `README.md` | `git ls-files residentialapps \| grep -v -e /docs/ -e /guide/ -e README` |
| Host registry entries to add | 2, in `cordware/main.py` `REGISTRY` (line 53) | `grep -n REGISTRY cordware/main.py` |
| Import-boundary rules already naming `residentialapps` | 3 (`app`, `residentialapps`, `cordware` keys) | `grep -n residentialapps cordware/tests/test_import_boundary.py` |
| Packaging | `packages.find` includes `app*`, `cordware*` only | `grep -n include pyproject.toml` |
| Identity claims exposed | `principal_id`, `email`, `name`; no tenant or UPN | `sed -n 40,46p cordware/identity.py` |
| CI lane rule to extend | `tools/ci_lanes.py` (`SHIPPED_DIRS`, the lane list) | `grep -n SHIPPED_DIRS tools/ci_lanes.py` |

## PR ladder

**Item 1 — Scaffold.** Base SHA recorded in its rung-1 PR.
1. Package, factories and both mounts with `health`; registry entries; `packages.find`; boundary tests extended.
2. Both databases: settings, engines, one `alembic.ini` with two histories, an empty first migration each; the Postgres round-trip of both in CI.
3. The `residential` lane in `tools/ci_lanes.py` and both workflows. Last build rung: `diff-reviewer` reads the item.

**Item 2 — Identity.**
1. Cordware: `tid` and UPN on `Identity`, with tests in `cordware/tests`; `cordware/spec/identity.md`.
2. Person and institutional-identity models, migration, the binding service and its audit events.
3. Sign-in flow: binding on first request, the not-registered page, the `RES_` fake roles.
4. Administrator grant and revoke, super-admin only (`residentialapps_roles.md`), with no-self-action and last-Administrator floors. Last build rung.

**Item 3 — Organization setup.**
1. Scaffold: the organization page with level labels, tree and import card as placeholders.
2. Models and migration: Unit, level labels, nodes, floor segments, appointment-to-level map.
3. Structure CSV: parse, preview (new, changed, retire, warnings), commit; export with labels.
4. Wire the page: labels editor, tree view, import. Last build rung.

**Item 4 — Rosters.**
1. Scaffold: Staff and RA roster pages as placeholders.
2. Appointments, backup reporting, migration; derived reporting service.
3. Roster CSVs (Staff, RA) resolving nodes by code; preview and commit.
4. Wire the pages: filters by level, link status, read-only access chips, edit actions. Last build rung.

## Definition of done

- `CORDWARE_APPS=residentialops` and `CORDWARE_APPS=supportlogs` each start locally and in CI; both health paths answer `200` signed out.
- Both Alembic histories round-trip on Postgres in CI; the `residential` lane runs Residential's tests on a Residential-only PR.
- The identity spec's acceptance scenarios 1–11 each have a test.
- Unit 1's ten-row structure file imports, previews and re-imports with a retire.
- Staff and RA roster CSVs import against that tree; an RA's reporting RF is derived.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 1A` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **`close_check.py` reads only RRW's `guide/`.** Either it learns `residentialapps/guide/`, or this plan's close is checked by hand. Decided at item 1's close, by the author.
- **Where Residential's specs live.** `residentialapps/spec/` (as RRW's `spec/`), or the existing `residentialapps/docs/` specs revised in place. Decided before item 2's first spec edit, by the author.

## Out of scope

- Support Logs content and authorizations: step 2 of the sequence. Item 1 mounts the app empty.
- Leave cycles, entitlements and RA Events: steps 3 and 4.
- Multi-Unit authorization: still open (`todo_master.md`), needed before a second Unit is exposed.
- Cordware's import rules for the new folders: classified in the first import that carries Residential code (Cordware `tools/import_rules.toml`).

## Doc impact

- `cordware/spec/identity.md` — tenant ID and UPN on the identity (Item 2).
- `cordware/spec/host.md` — the two registry entries and their health paths (Item 1).
- `residentialapps/docs/residentialapps_identity.md` — revised to what shipped (Item 2).
- `residentialapps/docs/residentialapps_roster_structure.md` — revised to the per-Unit levels, node tree and structure CSV (Item 3).
- `residentialapps/guide/todo_master.md` — ruling 11 points here; the entries this segment finishes are deleted at close.
- `residentialapps/README.md` — the package layout once code exists (Item 1).
- `tools/README.md` — the `residential` lane in the `ci_lanes.py` row (Item 1).
