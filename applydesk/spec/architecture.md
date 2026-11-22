# Apply Desk architecture

> **Built:** everything below. The pages read sample data; who may reach them, who operates an exercise, the people and the audit trail are in the database, the rest moving there area by area (`applydesk/guide/ad2_series.md`).

How `applydesk/` is laid out, what it may import, and how its tests run.
Its contract with the host is `applydesk/spec/applications.md`.

## Package layout

| Path | Holds |
|---|---|
| `applydesk/main.py` | The factory, `create_app` |
| `applydesk/routes_health.py` | `/health` |
| `applydesk/routes_home.py`, `routes_operator.py`, `routes_me.py` | The entry points (landing by role), the operator's pages and the participant's |
| `applydesk/routes_admin.py`, `allowlist.py` | The platform super-admin's pages, `/admin/…`, behind `gate.require_super_admin`: Admin → Accounts Management, the operator list. `routes_admin.py` is the thin route, also for the Exercises Diagnostics and System Status scaffolds, whose tabs share `admin/_tabs.html`; `allowlist.py` is the page's adapter: `accounts` (Workspace users: a category per person from `CATEGORIES`, the counts, the `ROLES` filter and the search), the Overview's counts, `Me` / `me()` (the signed-in super-admin's read-only *(self)* row), the people search (people on record, then the directory) and `suggest` / `suggestions` (the typeahead's offers, listed people left out before the limit, labels unique), and *Admit* (a directory pick is found again by address and matched on its object ID, nothing taken from the form), `bulk` (*Admit* or *Revoke* every ticked row, a refusal skipping that person) through `operators.py` |
| `applydesk/team.py` | An exercise's Operators card on Home, the adapter between `routes_operator.py` and `operators.py`: the card (current operators, the Owner first, whether the viewer may change them, whether the exercise has a row), the add search (the operator list only, current operators left out) and add, remove and hand over |
| `applydesk/lookups.py` | Path lookups the routes share: an ID's shape checked, then a 404 or the record |
| `applydesk/gate.py` | Who reaches the pages. `require_exercise_operator` on the operator router: 404 unless the viewer is the super-admin or on the allowlist and, on a path with an `exercise_id`, operates that exercise. `require_super_admin` on the admin router. `landing` on `/` and `/operator`: any operator, else the placeholders' gate. `placeholders_only` on the participant's pages until a later AD2 segment, on `reaches_placeholders`: anyone on a local run, deployed only the super-admin; `web.render` offers a link to those pages (`participant_pages`) only where it holds. `viewer` resolves the viewer once per request, binding them (`people.resolve`), and keeps the answer on `request.state`; `is_operator` and `operates` read it. `own_new_exercise` makes a new scratch exercise's row and Owner |
| `applydesk/db.py` | Apply Desk's own database, `applydesk` ("The database"); `is_busy` and `lost_a_race` tell a concurrent change (SQLite busy, or a unique clash) from a bug |
| `applydesk/models.py` | Its tables, on Apply Desk's own `Base`: `person`, `exercise`, `exercise_operator`, `audit_event` ("The database") |
| `applydesk/alembic.ini`, `applydesk/alembic/` | Its migration history ("The database") |
| `applydesk/people.py` | People and their binding: `resolve` at sign-in, `from_directory` for a directory find, `pending` for an address the directory did not find ("Binding") |
| `applydesk/directory.py` | The people search every place that adds people uses: people on record first, then the directory through `cordware/graph.py`; a failed directory search is reported, never read as nobody there |
| `applydesk/operators.py` | The rules of who may operate and who operates each exercise: the allowlist (`admit`, `revoke`) and an exercise's Owner and operators (`create_exercise`, `add_operator`, `remove_operator`, `hand_over`, `can_operate`, `is_owner`; `owner_labels` names each exercise's Owner for the Owner columns), refusing with `Refused` and its `key` ("Operators"); `_allowed` re-reads the allowlist row, under `FOR SHARE` where a change rests on it |
| `applydesk/audit.py` | `write_event` in Review Robin's envelope, copied, and `EVENT_SCHEMAS` ("Audit") |
| `applydesk/seed.py` | `python -m applydesk.seed`: the sample exercises' rows and their Owner; refused unless `APP_ENV=local` |
| `applydesk/ids.py` | Public IDs: generation and the shape check; `row_id` and `RowId` for a database row ID in a form or path |
| `applydesk/web.py` | Templates, mount-aware URLs (`url()`, `is_here()`, `host_url()`) and the page chrome |
| `applydesk/sample_data.py` | The sample exercises, applications, form cards and panels (`Panel`: key, name, members; ruling 19) |
| `applydesk/stages.py` | Stages, gates, outcomes and their rules; each row's cells; evaluators, assignments and pairs |
| `applydesk/workflow.py` | Each item's state, the status row, the emails owed, the counts and the steps |
| `applydesk/locks.py` | A stage's status and what a published stage fixes (ruling 35); `status_tally`, the exercises counted by status |
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

## Layering

RRW's three-layer split (`spec/architecture.md` "Three-layer split"),
with SQLAlchemy 2.x models and no Postgres-only types:

- **Routes** (`routes_admin.py`, `routes_operator.py`) parse the request, call
  `allowlist.py` or `team.py`, and turn the outcome into a redirect or a page.
  A refusal's `Refused.key` selects a status line from a fixed map in the
  route (`SAID`, `OPS_SAID`); text never travels in a URL.
- **`allowlist.py` and `team.py`** shape a page's lists and searches and call
  the rules; they hold none.
- **The rules** are `operators.py`, `people.py` and `directory.py`, over
  `models.py` and `audit.py`. They flush and never commit: the caller owns
  the transaction and rolls back on `Refused`.
- **`gate.py`** is the one place that decides who reaches a page, from
  `people` and `operators`.
- A route calls Graph (a directory search or lookup) off the event loop
  (`run_in_threadpool`) and reads the form body on it.

## The database

Apply Desk has its own database, `applydesk`, laid out as Utilities'.

- `db.py`: the URL is `APPLYDESK_DATABASE_URL`, defaulting to
  `sqlite:///./applydesk.db`. The engine is made on first use, so the factory
  and `/health` open none. `get_session` is a request's session and
  `new_session` one for code outside a request; the caller closes it.
- SQLite engines hand transactions to the engine, not the driver (`BEGIN` on
  begin), so savepoints nest as on Postgres. Keep this: without it a
  savepoint opened after a read has no transaction round it, and releasing it
  commits.
- Deployed with no URL set, Apply Desk falls back to its SQLite default; the
  App Setting must exist before it is relied on.
- Migrations: `alembic -c applydesk/alembic.ini`, version table
  `applydesk_alembic_version`. `include_name` limits comparison to Apply
  Desk's own tables, since another application's tables share CI's Postgres.
  The history is `ad2a1foundations` (the four tables), `ad2a2oneowner` and
  `ad2a3onepending`.

| Table (model) | Holds |
|---|---|
| `person` (`Person`) | Tenant ID and object ID, null while pending; email, `email_key` (the casefolded address), UPN and display name as snapshots; `bound_at`; `first_signed_in_at` (the first sign-in, set once; a directory pick is bound without one); `created_at`. The allowlist is on it: `may_operate`, `admitted_by_id`, `admitted_at`, `revoked_at` |
| `exercise` (`Exercise`) | `public_id`, unique, and `created_at`; the rest of an exercise is sample data |
| `exercise_operator` (`ExerciseOperator`) | A grant: (exercise, person) unique, `is_owner`, `added_by_id`, `added_at`, `removed_at` |
| `audit_event` (`AuditEvent`) | `at`, `event_type`, `actor_id`, `exercise_id`, `detail` (JSON) |

The database enforces what a race could otherwise break, each as a partial
unique index defined identically for SQLite and Postgres:

- `uq_person_tenant_object`: one person per (tenant, object ID).
- `uq_person_pending_email` (`email_key` where `object_id` is null): one
  pending person per address. Bound people may share an address, theirs being
  a snapshot.
- `uq_exercise_one_owner` (`exercise_id` where `is_owner`): one Owner row per
  exercise. An Owner is never removed, only replaced, so the row is never
  marked removed.

### Binding

A signed-in identity is bound by (tenant, object ID); an identity with no
tenant or object ID cannot be bound and has no person.

- `resolve`: the bound person; else the one pending person whose `email_key`
  matches the UPN, then the mail, who is bound and audited; else a new bound
  person. Once bound, email is a snapshot and nothing matches on it again.
  Only a pending person is ever matched by address.
  A bound person with no `first_signed_in_at` has it stamped once, by a
  conditional update so two first requests agree, and audited
  (`person.signed_in`) by whoever stamped it.
- Two different pending people matching (one by UPN, one by mail) fail
  closed: neither is bound, and a new bound person is made without their
  access, for the super-admin to settle.
- `from_directory` stores a directory find bound (the searcher's tenant, the
  find's object ID); an existing bound row is reused and a matching pending
  one bound. `pending` makes or reuses a pending person for an address the
  directory did not find.
- A binding is a conditional update or a savepointed insert, retried a few
  times when another request took the row first.

### Operators

- Only the platform super-admin keeps the allowlist (`admit`, `revoke`). Only
  an allowlisted person may make an exercise, be added to one or own one; the
  super-admin needs no allowlisting but needs a person row, so one whose
  sign-in cannot be bound cannot make an exercise.
- Every check re-reads the allowlist row, so a revoke another request
  committed counts. A check a change rests on (an add, a handover, making an
  exercise) reads it `FOR SHARE`, so a revoke committing meanwhile waits for
  the change. Revoking ends access at once and keeps the grants. Admit and
  revoke are conditional updates: of two at once, one changes the row and is
  audited, the other is refused.
- Each change to an exercise's operators takes the exercise's row lock,
  checks fresh rows, and restates its rule in a conditional update; the loser
  of two concurrent changes is refused. A change and its audit event share
  one transaction. A route binds the actor (`people.resolve`) and commits
  before taking the lock, so no person row is held while it waits.
- A route reports a lost race (`db.lost_a_race`) as a concurrent change, not
  an error; any other integrity or operational error propagates.
- Making an exercise makes its Owner's grant in the same transaction. An
  exercise always has exactly one current Owner; a handover clears the former
  Owner's flag before setting the new one's.

### Audit

`write_event` takes one payload envelope (`changes`, `snapshot`, `counts` or
`set_changes`) and any of `reason`, `refs` (integer values, keys ending in
`_id`) and `context` (scalars). Each event type's allowed keys are in
`EVENT_SCHEMAS`: a new emitter registers its type there. Under pytest a
detail that breaks its schema raises; otherwise the row is written and the
breach logged by name. The detail names an exercise by its public ID.

Events: `person.created`, `person.bound`, `person.signed_in`, `person.admitted`,
`person.revoked`, `exercise.created`, `exercise.operator_added`,
`exercise.operator_removed`, `exercise.ownership_handed_over`. A directory
find is audited to the searcher, not the person found.

### The seed

`python -m applydesk.seed` is idempotent and refused unless `APP_ENV=local`.
It goes through `people` and `operators`, so its rows are matched and
audited as any others: it binds Cordware's fake identity (or, with
`--owner EMAIL`, leaves that address pending), admits the person as the
platform, and makes each sample exercise's row with them its Owner. Tests
seed through the same function.

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
