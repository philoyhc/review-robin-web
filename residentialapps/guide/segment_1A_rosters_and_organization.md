# Segment 1A — RA Operations: skeleton and UX scaffold

**Opened:** 2026-10-26 · **Theme:** the Residential package, both mounts, and every shared-core admin screen as a placeholder, settled before any service is built · **Related:** `residentialapps/guide/segment_1B_rosters_and_organization_wiring.md` (the innards that wire these screens), `residentialapps/guide/todo_master.md` (rulings, ruling 11 sequence), `residentialapps/docs/residentialapps_identity.md`, `residentialapps/docs/residentialapps_roster_structure.md`, `residentialapps/docs/residentialapps_roles.md`

## Status

**Restructured 2026-10-26, before any build** (author): the original four-item plan (`#3274`), with each item's screens inside it, became two segments. 1A builds the skeleton and scaffolds every screen first; 1B (`residentialapps/guide/segment_1B_rosters_and_organization_wiring.md`) builds the innards and wires them. This applies RRW's "consequential UI lands scaffold-first" to the whole segment, so the services are shaped by screens already settled.

## Opportunity

Residential has rulings and specs but no code: `residentialapps/` holds only prose. The admin screens (organization, Staff and RA rosters, identity status, Administrator grants) share filters, labels and layout, so they are cheapest to settle together, on placeholders, before any model or service exists to constrain them. Step 1 of the author's sequence (ruling 11) starts here.

## Decision

**A thin technical skeleton, then every screen as a placeholder**: real RRW templates on its design system, filled with Unit 1's example data (one Wing, three Precincts, ten Neighborhoods), controls inert. The author reviews in a browser and the shape is iterated until approved; 1B then replaces the sample data with real data, page by page.

**Rejected: services first, screens after** (the plan as first merged). Services built before the screens are seen get reshaped when they are.

**Rejected: mockups on the design canvas instead of templates.** A canvas mockup is redrawn when built; a placeholder template is the page 1B wires, and it runs under the real mount, chrome and fake auth.

## Semantics

- **Health without sign-in:** `/residentialops/health` and `/supportlogs/health` answer before any database exists, as RRW's does; both are already excluded from Easy Auth in Azure.
- **Each app alone:** `CORDWARE_APPS=residentialops` and `CORDWARE_APPS=supportlogs` each start. `/supportlogs` serves only `health` in 1A.
- **Who sees the placeholders:** any signed-in user, locally under Cordware's fake auth. No gate is faked; the Administrator check arrives with 1B's identity item.
- **Sample data is labelled:** each placeholder page says it shows example data, so a screenshot is never mistaken for a working screen.
- **No root-path URLs:** pages emit app paths through the mount, as RRW's `app/web/urls.py` rule requires.

## Judgment calls — decided

- Sample data lives in one module beside the templates, so 1B can delete it in one place.
- The not-registered page is scaffolded in 1A, though only 1B can reach it for real; its wording is a UX decision.
- The `residential` CI lane lands in rung 1 with the first Residential test, not later.

## Blast radius (measured)

Taken 2026-10-26 at `eb7d5d9`.

| What | Count | Command |
|---|---|---|
| Residential code today | 0 files outside `docs/`, `guide/`, `README.md` | `git ls-files residentialapps \| grep -v -e /docs/ -e /guide/ -e README` |
| Host registry entries to add | 2, in `cordware/main.py` `REGISTRY` | `grep -n REGISTRY cordware/main.py` |
| Import-boundary rules naming `residentialapps` | 3 | `grep -n residentialapps cordware/tests/test_import_boundary.py` |
| Packaging | `packages.find` includes `app*`, `cordware*` only | `grep -n include pyproject.toml` |
| CI lane rule to extend | `tools/ci_lanes.py` | `grep -n SHIPPED_DIRS tools/ci_lanes.py` |

## PR ladder

Base SHA recorded in rung 1's PR; `diff-reviewer` reads the cumulative diff once, at rung 4.

1. **Skeleton.** Package and app factories; both mounts with `health`; registry entries; `packages.find`; boundary tests extended; the `residential` lane in `tools/ci_lanes.py` and both workflows.
2. **Organization page.** Level labels; the tree with floors; the structure-CSV card with a sample preview (new, changed, retire, warnings).
3. **Roster pages.** Staff and RA rosters with level filters, link status, read-only access chips; the roster-CSV card with a sample preview.
4. **Identity and access pages.** The not-registered page; person detail (enterprise and Entra names, identity status); Administrator grants. Last build rung.
5. **Iteration**, as many rungs as the author's review needs; each one is template and sample-data only.

## Definition of done

- Both apps start alone and together; both health paths answer `200` signed out.
- Every page in rungs 2–4 renders under `/residentialops` with Unit 1's example data, and RRW's URL-leak and crawl conventions hold for it.
- The author has approved the screens in a browser.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 1A` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **`close_check.py` reads only RRW's `guide/`.** Either it learns `residentialapps/guide/`, or this plan's close is checked by hand. The author decides by 1A's close.
- **Where Residential's specs live:** `residentialapps/spec/`, or the `residentialapps/docs/` specs revised in place. The author decides before 1B's first spec edit.

## Out of scope

- Databases, models, identity binding, CSV parsing and every service: segment 1B.
- Support Logs screens: step 2 of the sequence.
- Cordware's import rules for the new folders: classified in the first import that carries Residential code.

## Doc impact

- `cordware/spec/host.md` — the two registry entries and their health paths (rung 1).
- `residentialapps/README.md` — the package layout (rung 1).
- `tools/README.md` — the `residential` lane in the `ci_lanes.py` row (rung 1).
- `residentialapps/guide/todo_master.md` — the entries this segment finishes, deleted at close.
