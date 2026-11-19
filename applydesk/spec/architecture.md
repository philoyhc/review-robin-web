# Apply Desk architecture

> **Built so far:** everything below. Segment AD1 built the package, its
> health path and packaging; AD1B to AD1K added the modules behind each
> page, all on sample data until AD2's database.

How `applydesk/` is laid out, what it may import, and how its tests run.
Its contract with the host is `applydesk/spec/applications.md`.

## Package layout

| Path | Holds |
|---|---|
| `applydesk/main.py` | The factory, `create_app` |
| `applydesk/routes_health.py` | `/health` |
| `applydesk/routes_home.py`, `routes_operator.py`, `routes_me.py` | The entry points (landing by role), the operator's pages and the participant's |
| `applydesk/lookups.py` | Path lookups the routes share: an ID's shape checked, then a 404 or the record |
| `applydesk/gate.py` | Who reaches the pages until AD2 (`placeholders_only`, `is_operator`) |
| `applydesk/ids.py` | Public IDs: generation and the shape check |
| `applydesk/web.py` | Templates, mount-aware URLs (`url()`, `is_here()`, `host_url()`) and the page chrome |
| `applydesk/sample_data.py` | The sample exercises, applications, form cards and panels (`Panel`: key, name, members; ruling 19) |
| `applydesk/stages.py` | Stages, gates, outcomes and their rules; each row's cells; evaluators, assignments and pairs |
| `applydesk/workflow.py` | Each item's state, the status row, the emails owed, the counts and the steps |
| `applydesk/locks.py` | A stage's status and what a published stage fixes (ruling 35) |
| `applydesk/timeline.py` | The timeline Home and the applicant's page share: nothing operator-only |
| `applydesk/home_ops.py` | The operator's part of Home's timeline |
| `applydesk/extract.py` | Extract data's files: names, columns and rows |
| `applydesk/paging.py` | A long table's pages, 200 rows each, and its sort read from the query |
| `applydesk/templates/applydesk/` | Its templates; `base.html` carries the favicon and the bar |
| `applydesk/tests/` | Apply Desk's tests, a package with its own `__init__.py`; `_host.py` builds the Cordware host with the real registry |
| `applydesk/docs/`, `applydesk/guide/`, `applydesk/spec/` | Prose, as RRW's three folders |

Inside the application the layering will be RRW's (`spec/architecture.md`
"Three-layer split"): thin routes, services holding the rules, SQLAlchemy
2.x models with no Postgres-only types, from AD2's database on.

## Import boundaries

Read from the source by `cordware/tests/test_import_boundary.py`, at any
depth and including literal dynamic imports.

- `applydesk` imports none of `app` (Review Robin), `residentialapps` and
  `utilityapps`, and none of them imports it. It may import `cordware`,
  never `cordware.main`, except in `applydesk/tests/`, which builds the
  host.
- `cordware` imports it only through the registry's factory string.
- Shared conventions with Review Robin, such as the public-ID alphabet,
  are copied, not imported.

## Packaging, tests and CI

- `pyproject.toml` lists `applydesk*` in `packages.find`, `applydesk/tests`
  in pytest's `testpaths`, and `applydesk` in pyright's strict include,
  with a relaxed execution environment for `applydesk/tests`, as each
  application's tests have.
- Both CI workflows' unit shards run `applydesk/tests`.
- `tools/ci_lanes.py` lists `applydesk/` in `APP_DIRS`: its `docs/`,
  `guide/`, `spec/` and `README.md` are prose, and a code change runs the
  full lane. Apply Desk has no lane of its own.
