# Residential architecture

> **Draft for inspection, 2026-10-26.** Nothing here is built. Segment 1A
> builds the skeleton described here; later segments fill the packages it
> names. Each section says which segment brings it.

How `residentialapps/` is laid out, what each part may import, and how
its tests run. The two applications' contract with the host is
`residentialapps/spec/applications.md`.

## Package layout

| Package | Holds | Arrives |
|---|---|---|
| `residentialapps/` | The package root. It has no code of its own. | 1A |
| `residentialapps/ops/` | RA Operations: its factory (`main.py`), its routes and pages | 1A (factory and health) |
| `residentialapps/supportlogs/` | Support Logs: its factory, routes, pages, models and services | 1A (factory and health) |
| `residentialapps/core/` | The shared core: people, identity binding, organization, rosters | 1B |
| `residentialapps/web/` | What both applications' pages share: base template, styles, URL helper | 1B |
| `residentialapps/leave/`, `residentialapps/events/` | RA Leave and RA Events, served by RA Operations | Steps 3 and 4 |
| `residentialapps/tests/` | Residential's tests, a package with its own `__init__.py` | 1A |

**`ops/` beside ruling 1's list** (author, 2026-10-26). Ruling 1 names `core/`,
`leave/`, `events/`, `supportlogs/` and `web/`, and gives RA Operations no
package of its own. The logger prefix `residentialapps.ops` (ruling 6)
reads most simply as a package, and a package per application keeps each
one's routes in one place to fence off. Support Logs' application and
pillar share `supportlogs/`; RA Operations' application is `ops/`, and its
pillars are `core/`, `leave/` and `events/`.

Inside each application the layering is RRW's (`spec/architecture.md`
"Three-layer split"): thin routes, services hold the rules, SQLAlchemy 2.x
models with no Postgres-only types. That starts in 1B.

## Import boundaries

Read from the source by `cordware/tests/test_import_boundary.py`, at any
depth and including literal dynamic imports.

| Package | May not import |
|---|---|
| `residentialapps` (all of it) | `app`; and the module `cordware.main` |
| `residentialapps.ops` | `residentialapps.supportlogs` |
| `residentialapps.supportlogs` | `residentialapps.ops`, `residentialapps.leave`, `residentialapps.events` |
| `residentialapps.leave` | `residentialapps.events`, either application |
| `residentialapps.events` | `residentialapps.leave`, either application |
| `residentialapps.core`, `residentialapps.web` | Any application or pillar |
| `app`, `cordware` | `residentialapps` (already enforced) |

- `cordware.main` is forbidden for the same reason as in RRW: importing it
  builds the host. `residentialapps/tests/` is exempt from that one rule,
  never from `app`, because Residential's mounted tests build the host
  there, as RRW's do from its root `tests/`. Cordware's own tests stay the
  host's and identity's; the boundary file is the one Residential rule
  they hold (ruling 7).
- 1A adds the rows the skeleton can break, the first two and the
  `cordware.main` check; the rest join with their packages, each with a
  planted-import test as the existing rules have.
- Only `residentialapps.supportlogs` opens a `supportlogs` database session
  (ruling 7). That check needs the database code, so it lands in 1B.

## Packaging

`pyproject.toml`'s `packages.find` includes `residentialapps*`, and
`testpaths` adds `residentialapps/tests`.

## Tests and CI

- `residentialapps/tests/` holds every Residential test, needing no
  database in 1A: each application built from its factory, unmounted;
  and, through a host harness of Residential's own (after RRW's
  `tests/_mounted.py`), each combination in
  `residentialapps/spec/applications.md` "Running alone", with both
  health paths, the landing page, the route-name resolution and the log
  stamps.
- **The `residential` lane** (1A rung 2, `tools/ci_lanes.py`): a pull
  request whose every path is prose or under `residentialapps/` runs
  `residentialapps/tests`, `cordware/tests` (for the boundary file and
  the host it mounts on) and the prose lane's tests,
  and skips RRW's suite and its Postgres round-trip. A path anywhere else,
  `pyproject.toml` included, runs everything; every push to `main` runs
  everything. From 1B the lane also round-trips Residential's two
  histories on Postgres.
