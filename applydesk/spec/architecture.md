# Apply Desk architecture

> **Built:** everything below. The pages read sample data; who may reach them, who operates an exercise, an exercise's own settings, its Process (the timeline, gates, outcomes and rules), its Candidates, the people and the audit trail are in the database, the rest moving there area by area (`applydesk/guide/ad2_series.md`).

How `applydesk/` is laid out, what it may import, and how its tests run.
Its contract with the host is `applydesk/spec/applications.md`.

## Package layout

| Path | Holds |
|---|---|
| `applydesk/main.py` | The factory, `create_app` |
| `applydesk/routes_health.py` | `/health` |
| `applydesk/routes_home.py`, `routes_operator.py`, `routes_me.py` | The entry points (landing by role), the operator's pages and the participant's |
| `applydesk/routes_admin.py`, `allowlist.py` | The pages of Admins and the platform super-admin, `/admin/…`, behind `gate.require_admin`: Admin → Accounts Management, the operator list. `routes_admin.py` is the thin route, also for the Exercises Diagnostics and System Status scaffolds, whose tabs share `admin/_tabs.html`; `allowlist.py` is the page's adapter: `accounts` (Workspace users: a category per person from `CATEGORIES`, the counts, the `ROLES` filter and the search), the Overview's counts, `Me` / `me()` (the signed-in super-admin's read-only *(self)* row), the people search (people on record, then the directory) and `suggest` / `suggestions` (the typeahead's offers, listed people left out before the limit, labels unique), and *Admit* (a directory pick is found again by address and matched on its object ID, nothing taken from the form), `bulk` (*Admit*, *Revoke*, *Promote* or *Demote* every ticked row, a refusal skipping that person) through `operators.py`, the actions named in `BULK_ACTIONS`; `actor_for` builds the acting `Actor` |
| `applydesk/team.py` | An exercise's *Owners and operators* card on Home, the adapter between `routes_operator.py` and `operators.py`: the card (current operators, Owners first, whether the viewer may change them, the viewer's own row, whether the exercise has a row), the add search (the operator list only, current operators left out) and add, remove, transfer, make Owner, demote, step down and leave |
| `applydesk/lookups.py` | Path lookups the routes share: an ID's shape checked, then a 404 or the record |
| `applydesk/gate.py` | Who reaches the pages. `require_exercise_operator` on the operator router: 404 unless the viewer is the super-admin or on the allowlist and, on a path with an `exercise_id`, holds a current grant on that exercise (the super-admin's reach is their grants too). `require_admin` on the admin router: the super-admin or an Admin. `landing` on `/` and `/operator`: any operator, else the placeholders' gate. `placeholders_only` on the participant's pages until a later AD2 segment, on `reaches_placeholders`: anyone on a local run, deployed only the super-admin; `web.render` offers a link to those pages (`participant_pages`) only where it holds. `viewer` resolves the viewer once per request, binding them (`people.resolve`), and keeps the answer on `request.state`; `is_operator` and `operates` read it; `forget_viewer` drops it after the viewer's grants change. `own_new_exercise` makes a new scratch exercise's row and Owner |
| `applydesk/db.py` | Apply Desk's own database, `applydesk` ("The database"); `is_busy` and `lost_a_race` tell a concurrent change (SQLite busy, or a unique clash) from a bug |
| `applydesk/models.py` | Its tables, on Apply Desk's own `Base`: `person`, `exercise`, `exercise_tag`, `exercise_operator`, `audit_event`, and the Process and Candidates tables ("The database") |
| `applydesk/exercises.py` | An exercise's stored settings and the rules over them ("Exercises"): `overlay` and `stored` read them over the sample, `save_details` is Details' *Lock*, `save_panel`, `retag`, `archive`, `restore`, `delete` and `copy_settings` are the Lobby's, `record_sample` is the seed's. Flushes, never commits; refuses with `Refused` and its `key` |
| `applydesk/clock.py` | The one clock (`today`, `midday`) and the date wording (`short`, `span`, `stamp`): no page reads the wall clock or words a date itself |
| `applydesk/lobby.py` | The Operator Lobby's and the Archive's query string: `Query` (`sort`, `dir`, `tag`, `any`, `q`) and `apply` / `matches`, which sort and filter the rows |
| `applydesk/alembic.ini`, `applydesk/alembic/` | Its migration history ("The database") |
| `applydesk/people.py` | People and their binding: `resolve` at sign-in, `from_directory` for a directory find, `pending` for an address the directory did not find ("Binding") |
| `applydesk/directory.py` | The people search every place that adds people uses: people on record first, then the directory through `cordware/graph.py`; a failed directory search is reported, never read as nobody there |
| `applydesk/operators.py` | The rules of who may operate and who operates each exercise: the allowlist (`admit`, `revoke`), the Admin tier (`promote`, `demote`; `is_admin`; `is_protected` marks a super-admin's row, which no Revoke, Promote or Demote acts on; `keeps_the_list` says who admits and revokes, `makes_admins` who promotes and demotes) and an exercise's Owners and operators (`create_exercise`, `add_operator`, `remove_operator`, `hand_over`, `adopt`, `can_operate`, `is_owner`, `owners_of`; `owner_labels` names each exercise's Owners, comma-separated, for the Owners columns). `Actor` is the person, whether they are the super-admin, and `platform`, the seed acting as no one with every exercise, never built from a sign-in. Refusing with `Refused` and its `key` ("Operators"); `_allowed` re-reads the allowlist row, under `FOR SHARE` where a change rests on it |
| `applydesk/audit.py` | `write_event` in Review Robin's envelope, copied, and `EVENT_SCHEMAS` ("Audit") |
| `applydesk/seed.py` | `python -m applydesk.seed`: the sample exercises' rows, their settings and their Owner; refused unless `APP_ENV=local` |
| `applydesk/ids.py` | Public IDs: generation and the shape check; `row_id` and `RowId` for a database row ID in a form or path |
| `applydesk/web.py` | Templates, mount-aware URLs (`url()`, `is_here()`, `host_url()`) and the page chrome |
| `applydesk/sample_data.py` | The sample exercises, applications, form cards and panels (`Panel`: key, name, members; ruling 19) |
| `applydesk/stages.py` | Stages, gates, outcomes and their rules; each row's cells; evaluators, assignments and pairs. `plan_of` reads the stored timeline (`process_store.stored_stages`) once Process has saved the exercise, else the sample (a new exercise's one stage); `gate_keyed` and `gate_numbered` find a gate by its key or its old number; `rule_problems` is what a rule reads amiss |
| `applydesk/process_store.py` | An exercise's timeline in the database ("Process"): `load` and `stored_stages` build the dataclasses the pages read, `save` keeps a page's snapshot whole (the revision guard, keys, the references check, the audit), `move_form` is Home's *Open form* and *Close form*. Flushes, never commits; refuses with `Refused` and its `key` |
| `applydesk/rules.py` | The rule engine, the only rule evaluator: `propose` answers what each rule would change in a table of dossiers (Dossiers' *Apply rules…*), over `Dossier`, `Column` and `Cell` rows built by `columns_of` and `rows_of`. Pure: reads no database |
| `applydesk/candidates.py` | An exercise's Candidates ("Candidates"): `listing`, `add`, `remove` and `import_csv`. Flushes, never commits |
| `applydesk/workflow.py` | Each item's state, the status row, the emails owed, the counts and the steps |
| `applydesk/locks.py` | A stage's status and what a published stage fixes (ruling 35); `status_tally`, the exercises counted by status |
| `applydesk/timeline.py` | The timeline Home and the applicant's page share: nothing operator-only |
| `applydesk/home_ops.py` | The operator's part of Home's timeline |
| `applydesk/extract.py` | Extract data's files: names, columns and rows |
| `applydesk/handoff.py` | The bundle a gate is sent to Review Robin with: the reviewers, reviewees, relationships and settings CSVs |
| `applydesk/scratch.py` | Scratch exercises: the per-browser in-memory store, its cookie and limits, and each page's saved state |
| `applydesk/process_save.py` | Process's *Save*, before the store: the page's snapshot shape-checked and built back into stages (`build`), minting the keys of what the page added; `build(checking=True)` serves the rules check |
| `applydesk/panels_store.py` | An exercise's panels and the Panels roster in the database (segment AD2E): `load`, `save` under the exercise's row lock guarded by `exercise.panels_revision`, and `adopt` for the panels Form and Process make |
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
  The history is `ad2a1foundations` (the four tables), `ad2a2oneowner`,
  `ad2a3onepending`, `ad2w1firstsignin`, `ad2m1admins` (`person.is_admin`),
  `ad2m2manyowners` (drops `uq_exercise_one_owner`), `ad2b1exercisesettings`
  (the `exercise` columns below, `uq_exercise_live_code` and `exercise_tag`)
  and `ad2c1process` (the Process and Candidates tables and
  `exercise.process_revision`; new tables only).

| Table (model) | Holds |
|---|---|
| `person` (`Person`) | Tenant ID and object ID, null while pending; email, `email_key` (the casefolded address), UPN and display name as snapshots; `bound_at`; `first_signed_in_at` (the first sign-in, set once; a directory pick is bound without one); `created_at`. The allowlist is on it: `may_operate`, `admitted_by_id`, `admitted_at`, `revoked_at`, `is_admin` (an Admin, always also listed) |
| `exercise` (`Exercise`) | `public_id`, unique, and `created_at`; `name`, `code` and `code_key` (the code casefolded), `description`, `eligibility` (`open`, `invitation` or NULL), `blind`, `help_contact` and `timezone` (NULL takes the operator settings' default), `created_by_id` (the person who made it), `archived_at`, `deleted_at`, `revision` ("Exercises") and `process_revision` ("Process"). Its form and applications are sample data |
| `exercise_tag` (`ExerciseTag`) | One tag on an exercise: `exercise_id`, `label` (the case first typed) and `label_key` (casefolded); (exercise, `label_key`) unique |
| `exercise_operator` (`ExerciseOperator`) | A grant: (exercise, person) unique, `is_owner`, `added_by_id`, `added_at`, `removed_at` |
| `audit_event` (`AuditEvent`) | `at`, `event_type`, `actor_id`, `exercise_id`, `detail` (JSON) |
| `stage` (`Stage`) | One stage: `key` (`s<n>`), `position`, `name`, `starts_at` and `ends_at` (NULL when unset), `status` (`draft` or `published`), `shown`; `holds_form` and `holds_candidates`; on the stage holding the form, its window (`form_opens_at`, `form_closes_at`) and state (`form_state`: `draft`, `open`, `closed`; NULL elsewhere) with `form_opened_at` and `form_closed_at`; `retired_at`. (exercise, `key`) unique |
| `gate` (`Gate`) | One gate: its `stage_id`, `key` (`g<n>`), `position` in its stage, `label`, `via`, `description`, `confidential`, `mode`, `total_min` and `total_max`, `review_from` and `review_to`, `rule` (JSON), `retired_at`. (exercise, `key`) unique. Its number is computed, for display only |
| `gate_field` (`GateField`) | A response field: `gate_id`, `key` (`f<n>`), `position`, `label`, `type`, `min`, `max`, `step`, `options`, `required`, `help`, `retired_at`. (gate, `key`) unique |
| `gate_result` (`GateResult`) | A result: `gate_id`, `key` (`r<n>`), `position` (1 is the headline), `name`, `field_id` (the `gate_field` it collates, nullable), `derive`, `value`, `at_least`, `ignore_zero`, `retired_at`. (gate, `key`) unique |
| `gate_source` (`GateSource`) | An evaluator source: `gate_id`, `rank`, `kind`, `ref` (a panel key or a Form question key, strings until panels and questions are stored), `min`, `max`, `all_members` |
| `outcome` (`Outcome`) | `stage_id`, `key` (`o<n>`), `label`, `due_at`, `rule` (JSON), `retired_at`. (exercise, `key`) unique |
| `outcome_value` (`OutcomeValue`) | A value of an outcome: `outcome_id`, `key` (`v<n>`), `position`, `label`, `advances`, `retired_at`. (outcome, `key`) unique |
| `outcome_weight` (`OutcomeWeight`) | A weight in an outcome's combined result: `outcome_id`, `gate_id`, `result_key`, `weight`. (outcome, gate, result) unique |
| `outcome_release` (`OutcomeRelease`) | Who released an outcome to which audience, when: `outcome_id`, `audience`, `released_at`, `released_by_id`; (outcome, `audience`) unique. Written only by a release, which is not built; the table is empty |
| `candidate` (`Candidate`) | One person on an exercise's Candidates: `exercise_id`, `person_id`, `via` (`search` or `csv`), `added_by_id`, `added_at`, `removed_at`. (exercise, `person_id`) unique, so removing sets `removed_at` and adding again clears it |

The database enforces what a race could otherwise break, each as a partial
unique index defined identically for SQLite and Postgres:

- `uq_person_tenant_object`: one person per (tenant, object ID).
- `uq_person_pending_email` (`email_key` where `object_id` is null): one
  pending person per address. Bound people may share an address, theirs being
  a snapshot.
- `uq_exercise_live_code` (`code_key` where it is set and the exercise is
  neither archived nor deleted): one live exercise per code, ignoring case.

An exercise may have several Owners, so there is no one-Owner index: changes
to its Owners and operators take its row lock (`operators._lock`) instead,
and an Owner is never removed directly.

### Exercises

`applydesk/exercises.py` reads and writes an exercise's settings. The pages
keep `sample_data.Exercise`'s shape: `overlay` lays the stored settings over
the sample's, whose stages, form and applications stay sample data, and
`lookups.exercise_or_404` is the one reader, a 404 for a deleted exercise.
`revision` 0 means no settings are recorded and the sample's stand; the seed,
or the first change, records them (`exercise.settings_recorded`).

- **NULL is unset.** "Not set" is a page word, never stored. Choosing the
  default timezone or help contact stores NULL.
- **Revision.** It rises on every saved change; a save names the revision its
  page opened at and is refused, saving nothing, if a newer one exists.
- **Code.** Unique among live exercises, ignoring case, by
  `uq_exercise_live_code`; a clash is refused naming the holder. Archiving or
  deleting frees it; restoring is refused if it is taken.
- **Tags.** Trimmed, unique per exercise ignoring case, at most 20 an exercise
  and 40 characters each.
- **Nothing is hard-deleted.** Delete sets `deleted_at`: the row, its grants
  and its audit trail stay, and the exercise leaves every page.
- **Owner-only.** Archive, restore and delete require an Owner
  (`operators.is_owner`); a ticked set is done whole or not at all.
- **Locks.** Each change takes the exercise's row lock. The route, not the
  service, refuses what the page locks: a published exercise's code and
  eligibility, and blind review once a gate's stage is published.
- **Dates.** `applydesk/clock.py`: today is the sample's fixed day while the
  sample's stages stand (`clock.FROZEN`), else the wall clock's in the
  exercise's timezone.

### Process

`applydesk/process_store.py` keeps an exercise's timeline. The pages keep
`stages`' dataclasses, which `load` builds; `stages.plan_of` reads the stored
timeline once the exercise has one (`process_revision` of 1 or more) and
otherwise the sample's (or, for a scratch exercise not yet saved, a new
one's). Dossiers' cells stay the sample's.

- **One save replaces the draft.** `save` takes the exercise's row lock,
  refuses an archived exercise, refuses a snapshot built on an older
  `process_revision` (`Refused`, key `stale`), checks it whole, writes it and
  raises the revision, in the caller's transaction with the audit event. The
  route reports a lost race (`db.lost_a_race`) as a concurrent change.
- **Keys** are per exercise and never reused: a stage, gate or outcome the
  snapshot drops is retired (`retired_at`), never deleted, and a retired key
  is refused if sent again. A gate's field, result and value are parts of
  their gate or outcome and revive on return. Sources and weights are
  replaced on each save. `taken_keys` includes a sample's own keys, which its
  cells are keyed by.
- **References.** A rule stores every target by key; an outcome value is its
  key, read back as its label by the pages. `check_references` refuses a
  rule naming a gate, result or outcome the snapshot lacks, an outcome
  weighing one, and a gate's rule reading a gate. Other problems are
  `stages.rule_problems`', flagged and saved as left.
- **Published stages** (`status` `published`): the save refuses removing one,
  changing its name, start or `shown`, and adding to it; a revert to draft
  is audited with its reason.
- **Dates.** Unset is NULL, never text; a reversed pair is refused.
- **The form's state** is `stage.form_state`. `move_form` takes the lock,
  records an unsaved timeline first, and moves `draft` to `open` (the
  exercise published) or `open` to `closed`, never otherwise, stamping
  `form_opened_at` or `form_closed_at`.
- **The rule engine** is `rules.py` and nothing else: no template evaluates
  a rule. A Process snapshot posted to `…/process/problems` is answered by
  `stages.rule_problems` for the page's flags, and a Dossiers table posted to
  `…/dossiers/proposal` by `rules.propose`; neither writes.

### Candidates

`applydesk/candidates.py` lists an exercise's people (the form's roster on an
*Invitation only* exercise). `add` and `remove` flush and audit; a person is
listed once (`uq_candidate_pair`), and removing then adding revives the same
row. `import_csv` adds each good row, matching an address to a person on
record or making a pending one (`people.pending`), and returns the rows it
could not read, not saved. An archived or deleted exercise refuses every
change.

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
  exercise always has at least one current Owner; adopting adds one, and a
  handover clears the handing-over Owner's flag before setting the new one's.

### Audit

`write_event` takes one payload envelope (`changes`, `snapshot`, `counts` or
`set_changes`) and any of `reason`, `refs` (integer values, keys ending in
`_id`) and `context` (scalars). Each event type's allowed keys are in
`EVENT_SCHEMAS`: a new emitter registers its type there. Under pytest a
detail that breaks its schema raises; otherwise the row is written and the
breach logged by name. The detail names an exercise by its public ID.

Events: `person.created`, `person.bound`, `person.signed_in`, `person.admitted`,
`person.revoked`, `exercise.created`, `exercise.operator_added`,
`exercise.operator_removed`, `exercise.ownership_handed_over`,
`exercise.owner_added`, `exercise.owner_demoted` (`context.stepped_down`),
`exercise.operator_left`, `exercise.adopted`, `person.promoted`, `person.demoted`,
`exercise.settings_recorded` (a snapshot), `exercise.details_changed` (a
changes envelope and the new `revision`, from Details' *Lock* and the Lobby's
*Save* and tag actions), `exercise.archived`, `exercise.restored`,
`exercise.deleted` and `exercise.duplicated` (`refs.source_exercise_id`),
`exercise.process_saved` (a counts envelope: stages, gates and outcomes kept
and `retired`; `context.revision`), `exercise.stage_reverted` (`reason`,
`refs.stage_id`), `exercise.form_opened`, `exercise.form_closed`,
`candidate.added` (`refs.person_id`, `context.via`) and `candidate.removed`
(`refs.person_id`). A directory find is audited to the searcher, not the
person found.

### The seed

`python -m applydesk.seed` is idempotent and refused unless `APP_ENV=local`.
It goes through `people` and `operators`, so its rows are matched and
audited as any others: it binds Cordware's fake identity (or, with
`--owner EMAIL`, leaves that address pending), admits the person as the
platform (`Actor(platform=True)`, the one actor with every exercise), and
makes each sample exercise's row with them its Owner. Tests
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
- Both CI workflows' unit shards run `applydesk/tests`. In `ci-postgres.yml` they run against Postgres: each worker's database is derived from `TEST_DATABASE_URL` as `rrw_ad` and `rrw_ad_gw0` on (`applydesk/tests/conftest.py`), and `applydesk/tests/test_postgres_locks.py` exercises the row locks, which SQLite cannot show. `ci-postgres.yml` also round-trips Apply Desk's history (`upgrade head`, `downgrade base`, `upgrade head`, `check`) on Postgres, beside RRW's and Utilities', sharing the database through its own version table.
- `tools/ci_lanes.py` lists `applydesk/` in `APP_DIRS`: its `docs/`,
  `guide/`, `spec/` and `README.md` are prose, and a code change runs the
  full lane. Apply Desk has no lane of its own.
