# Segment 1A — Residential: package and mounts

**Opened:** 2026-10-26 · **Theme:** the `residentialapps/` package and both applications mounted under Cordware, with nothing behind them yet · **Related:** `residentialapps/guide/segment_1B_rosters_and_organization.md` (the admin screens and their wiring), `residentialapps/guide/todo_master.md` (rulings 1, 4–7; ruling 11 sequence)

## Status

**Closed 2026-10-26, as planned after two restructures before any build** (author): first four items with screens inside each (`#3274`), then a skeleton plus every screen (`#3275`), then the package and mounts alone, with the screens and their wiring moved to 1B. Specs were drafted first for inspection (`#3277`) and ruled the same day: specs in `residentialapps/spec/`, an `ops/` package, Residential's logs and tests kept in `residentialapps/`. Built in `#3279` (rung 1) and `#3281` (rung 2); `#3280`, the landing page's sign-in details, merged between them on the author's request.

Decisions confirmed at build: route names carry the application's prefix (Codex, `#3277`: a shared name resolves to the first mount); `residentialapps/tests/` builds the host and is exempt from the `cordware.main` check only; the host harness passes the registry's names for "unset", so a developer's `CORDWARE_APPS` cannot fail it.

Reads: one `diff-reviewer` read of `b99583d..b6ed40d` at rung 2, nothing blocking; it found the harness's `.env` dependence, a stale `CONTRIBUTING.md`, an overclaiming lane comment, and the dormant dev slot's artefact missing `residentialapps/`, all fixed in `#3281`, and raised 1B's open question on the lane once Residential has databases. Codex found one issue, the route-name collision, on the draft specs.

The close was checked by hand against `tools/close_check.py`'s checks C1 to C7 (all pass), since the tool reads only RRW's `guide/` (open question, below).

## Opportunity

`residentialapps/` holds only prose. Nothing can render a Residential page, pass the import boundaries or run in CI until the package exists, both applications are mounted, and CI knows to test them.

## Decision

**The smallest skeleton that later work can build on:** the package, two app factories, two registry entries with health paths, packaging, the boundary tests, and the `residential` CI lane. It has no database, no pages beyond `health`, and no identity work.

**Rejected: folding in the screens** (`#3275`'s 1A). It would make 1A a long iterative segment and hold up a skeleton that is otherwise quick to close.

## Semantics

- **Health without sign-in:** `/residentialops/health` and `/supportlogs/health` answer `200` with no database, as RRW's does. Both are already excluded from Easy Auth in Azure.
- **Each app alone:** `CORDWARE_APPS=residentialops` and `CORDWARE_APPS=supportlogs` each start, and so does the pair with RRW.
- **Logger prefixes** `residentialapps.ops` and `residentialapps.supportlogs`, neither nested in the other. Lifespan state keys are prefixed per app (ruling 6).
- **Boundaries** (ruling 7): neither app imports the other's routes; `app` and `cordware` never import `residentialapps`, and it never imports `app`.
- **The `residential` lane** runs Residential's tests and `cordware/tests` on a PR that touches `residentialapps/` code. Anything shared still runs everything, failing toward running (`guide/archive/segment_22A_ci_lanes.md`).

## Judgment calls — decided

- Both apps get a factory even though `/supportlogs` serves only `health`. It is ruled to be independently mountable from the start (ruling 5).
- The lane lands with the first Residential test, in the same PR.

## Blast radius (measured)

Taken 2026-10-26 at `b63604f`.

| What | Count | Command |
|---|---|---|
| Residential code today | 0 files outside `docs/`, `guide/`, `README.md` | `git ls-files residentialapps \| grep -v -e /docs/ -e /guide/ -e README` |
| Host registry entries to add | 2, in `cordware/main.py` `REGISTRY` | `grep -n REGISTRY cordware/main.py` |
| Import-boundary rules naming `residentialapps` | 3 | `grep -n residentialapps cordware/tests/test_import_boundary.py` |
| Packaging | `packages.find` includes `app*`, `cordware*` only | `grep -n include pyproject.toml` |
| CI lane rule to extend | `tools/ci_lanes.py` | `grep -n SHIPPED_DIRS tools/ci_lanes.py` |

## PR ladder

1. **Package and mounts.** Package and both factories with `health`; registry entries; `packages.find`; boundary tests extended; Residential's first tests. Base SHA `b99583d` (`main` before rung 1).
2. **The `residential` lane** in `tools/ci_lanes.py` and both workflows; `residentialapps/spec/` joins `PROSE_DIRS`. This is the last build rung, so `diff-reviewer` reads the cumulative diff from `b99583d` here.

## Definition of done

- Both apps start alone, together, and with RRW; both health paths answer `200` signed out.
- A PR touching only `residentialapps/` code runs the `residential` lane.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 1A` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **`close_check.py` reads only RRW's `guide/`:** 1A's close was checked by hand (2026-10-26); teaching the tool Residential's plans is a stub in `residentialapps/guide/todo_master.md`, due before 1B closes.

## Out of scope

- Every screen, database, model and service: segment 1B.
- Cordware's import rules for the new folders: they are classified in the first import that carries Residential code.

## Doc impact

- `residentialapps/spec/applications.md`, `residentialapps/spec/architecture.md` — drafted before rung 1; the banners go and each section says what shipped (rungs 1 and 2).
- `cordware/spec/host.md` — the two registry entries and their health paths (rung 1).
- `residentialapps/README.md` — the package layout (rung 1).
- `tools/README.md` — the `residential` lane in the `ci_lanes.py` row (rung 2).
- `residentialapps/guide/todo_master.md` — the entries this segment finishes, deleted at close.
