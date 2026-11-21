# Apply Desk architecture

> **Built:** everything below. The pages read sample data; who operates an exercise moves to the database in segment AD2A, the rest area by area (`applydesk/guide/ad2_series.md`).

How `applydesk/` is laid out, what it may import, and how its tests run.
Its contract with the host is `applydesk/spec/applications.md`.

## Package layout

| Path | Holds |
|---|---|
| `applydesk/main.py` | The factory, `create_app` |
| `applydesk/routes_health.py` | `/health` |
| `applydesk/routes_home.py`, `routes_operator.py`, `routes_me.py` | The entry points (landing by role), the operator's pages and the participant's |
| `applydesk/routes_admin.py`, `allowlist.py` | The platform super-admin's pages, `/admin/…`: the operator list (segment AD2A, ruling 75), behind `gate.require_super_admin`, in the switcher for the super-admin only. The search (people on record, then the directory), *Admit* and *Revoke*; a directory pick is found again at admission, nothing taken from the form |
| `applydesk/team.py` | An exercise's Operators card on Home (segment AD2A, ruling 73): its current operators, the Owner first, and whether the viewer may change them; the Owner's (or the super-admin's) add from the operator list, remove and hand over, through `operators.py` |
| `applydesk/lookups.py` | Path lookups the routes share: an ID's shape checked, then a 404 or the record |
| `applydesk/gate.py` | Who reaches the pages: `require_exercise_operator` on the operator's (the super-admin, or the allowlisted with a current grant; 404 otherwise), `placeholders_only` on the participant's until a later AD2 segment; `is_operator` for the switcher; a new scratch exercise's row and Owner (segment AD2A) |
| `applydesk/db.py` | Apply Desk's own database, `applydesk`: `APPLYDESK_DATABASE_URL` (locally `sqlite:///./applydesk.db`), the engine made on first use, a request's session |
| `applydesk/models.py` | Its tables (segment AD2A): `person` (bound by tenant and object ID, or pending by casefolded email; the operator allowlist), `exercise` (its key and public ID), `exercise_operator` (a grant, its Owner marked), `audit_event` |
| `applydesk/alembic.ini`, `applydesk/alembic/` | Its migration history, version table `applydesk_alembic_version`, comparing only its own tables |
| `applydesk/people.py` | People bound by tenant and object ID: `resolve` at sign-in (a pending person bound by UPN, then mail), `from_directory`, `pending` (ruling 73) |
| `applydesk/directory.py` | The people search: on record first, then the directory through `cordware/graph.py`; a failed directory search says so (ruling 75) |
| `applydesk/operators.py` | The allowlist (`admit`, `revoke`, the super-admin's) and an exercise's Owner and operators (`create_exercise`, `add_operator`, `remove_operator`, `hand_over`, `can_operate`), refusing with `Refused` (rulings 73, 75) |
| `applydesk/audit.py` | `write_event` in Review Robin's envelope, copied, and `EVENT_SCHEMAS`, strict under pytest (ruling 74) |
| `applydesk/seed.py` | `python -m applydesk.seed`: the sample exercises' rows and their Owner, on localhost only (ruling 74) |
| `applydesk/ids.py` | Public IDs: generation and the shape check |
| `applydesk/web.py` | Templates, mount-aware URLs (`url()`, `is_here()`, `host_url()`) and the page chrome |
| `applydesk/sample_data.py` | The sample exercises, applications, form cards and panels (`Panel`: key, name, members; ruling 19) |
| `applydesk/stages.py` | Stages, gates, outcomes and their rules; each row's cells; evaluators, assignments and pairs |
| `applydesk/workflow.py` | Each item's state, the status row, the emails owed, the counts and the steps |
| `applydesk/locks.py` | A stage's status and what a published stage fixes (ruling 35) |
| `applydesk/timeline.py` | The timeline Home and the applicant's page share: nothing operator-only |
| `applydesk/home_ops.py` | The operator's part of Home's timeline |
| `applydesk/extract.py` | Extract data's files: names, columns and rows |
| `applydesk/handoff.py` | The bundle a gate is sent to Review Robin with: the reviewers, reviewees, relationships and settings CSVs |
| `applydesk/scratch.py` | Scratch exercises: the per-browser in-memory store, its cookie and limits, and each page's saved state |
| `applydesk/process_save.py` | Process's *Save* on a scratch exercise: the snapshot checked and built back into stages |
| `applydesk/scratch_panels.py` | Panels' *Save* on a scratch exercise, and the panels Form and Process make |
| `applydesk/tones.py` | Each state's chip tone, one map for every page |
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
- Both CI workflows' unit shards run `applydesk/tests`. `ci-postgres.yml` round-trips Apply Desk's history (`upgrade head`, `downgrade base`, `upgrade head`, `check`) on Postgres, beside RRW's and Utilities', sharing the database through its own version table.
- `tools/ci_lanes.py` lists `applydesk/` in `APP_DIRS`: its `docs/`,
  `guide/`, `spec/` and `README.md` are prose, and a code change runs the
  full lane. Apply Desk has no lane of its own.
