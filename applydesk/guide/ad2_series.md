# Apply Desk — the AD2 series: from sample data to a database

**Opened:** 2026-11-21 · **Rulings:** 72–75 (`applydesk/guide/todo_master.md`) · **Work list:** `applydesk/guide/ad2_deferred_findings.md` · **Model:** `applydesk/docs/data_and_visibility_model.md`

The roadmap's AD2 row ("Database and identity") is a series of segments, each its own plan in this folder, not one segment (author, 2026-11-21). Each moves one area from sample data and the scratch store to Apply Desk's own database. The pages keep working between segments. This file holds what the series shares; each plan holds its own work.

## What every AD2 segment holds to

- **Its own database**, `applydesk`, at `APPLYDESK_DATABASE_URL`, with its own Alembic history (`applydesk/alembic.ini`, version table `applydesk_alembic_version`), as Utilities' (`utilityapps/db.py`). Models use SQLAlchemy 2.x with no Postgres-only types. Migrations survive SQLite and Postgres 16 in both directions; `ci-postgres.yml` round-trips the history.
- **Checkable on localhost** (author, 2026-11-21), as RRW is. The URL defaults to `sqlite:///./applydesk.db`, `alembic -c applydesk/alembic.ini upgrade head` builds it, and `python -m applydesk.seed` loads the sample exercises. A fresh checkout reaches every page under Cordware's fake auth. Tests build the schema from the models on a fresh SQLite file per test, so two sessions can race in them; the Postgres job round-trips the history.
- **RRW's layering** (`spec/architecture.md`, "Three-layer split"): thin routes, services holding the rules, models with no logic.
- **People by tenant and object ID** (ruling 73), never by email after binding.
- **Every addition of a person searches** by name or email, people on record first, then the institution's directory through Graph (ruling 75, `cordware/graph.py`); a local run searches Cordware's fake directory.
- **Every change audited**, in RRW's envelope, through Apply Desk's own copy (ruling 74).
- **A save names the revision it started from** and is refused, *changed since you opened it; reload*, if a newer one exists (ruling 74).
- **Nothing is hard-deleted**: `retired_at` / `withdrawn_at` (ruling 74).
- **The samples are seeds**: loaded on localhost and in tests, never in production (ruling 74).

## The segments, in order

| Segment | Moves to the database | Findings it takes | Plan |
|---|---|---|---|
| AD2A — Foundations | The database and its history; people and their binding; the operator allowlist and its admin page; exercise operators (Owner and operators); audit; the seed command | AD-43, AD-53 | `applydesk/guide/archive/segment_AD2A_foundations.md` (closed 2026-11-21) |
| AD2B — Exercises and Details | The exercise and its settings: public ID, code, description, eligibility, help contact and time zone over the operator settings; NULL for unset; one date helper; the Operator Lobby's wiring, after AD1T's scaffold (sorting, tags and the tag filter, the filter box, *Go to Archive*, and the tick panel's actions), with each exercise's creator and creation time | AD-54, AD-55, AD-60, AD-97, AD-40 (AD-52 to AD2C, 2026-11-22) | `applydesk/guide/archive/segment_AD2B_exercises.md` (closed 2026-11-22) |
| AD2O — Owners and operators | An exercise's several Owners and their moves, the last-Owner guard, Revoke refused for a sole Owner; the Lobby's *Your role* and Home's *Owners and operators* card (`applydesk/spec/permissions.md` §3, §7, §8) | — | `applydesk/guide/archive/segment_AD2O_owners.md` (closed 2026-11-22) |
| AD2C — Process | Stages with date-times, the form's state, gates (stable keys, fields, results), outcomes (keyed values, state, release per audience); rules as validated JSON, evaluated by one server-side service; Process's Save | AD-52 (invitees, a stage item), AD-36, AD-48, AD-51, AD-57, AD-59, AD-61, AD-62, AD-34; AD-60's stage dates and AD-35's Process half; AD-126, AD-128, AD-129 (the AD2A bug sweep's, placed 2026-11-22) | `applydesk/guide/archive/segment_AD2C_process.md` (closed 2026-11-23) |
| AD2D — Form and applications | Version 1: the form's questions with stable keys, versioned on publish, and per-field visibility grants (rulings 68–71); the Select people question's Institution-wide pool as a directory search. Later: applications and their states, answers and nominations | AD-45, AD-38, AD-46, AD-42 (from AD2E, 2026-11-23) | `applydesk/guide/archive/segment_AD2D_form.md` (version 1, closed 2026-11-23) |
| AD2E — Panels | Version 1: panels, the Panels roster and memberships, retiring, size caps; *+ New panel…* stored with Form's and Process's save | AD-50 (its shapes and caps; `Assessor` and `Evaluator` with AD2F), AD-127 (Unicode-aware people search, placed 2026-11-22); AD-42 to AD2D (2026-11-23) | `applydesk/guide/archive/segment_AD2E_panels.md` (closed 2026-11-23) |
| AD2L — Email templates | Version 1, split from AD2F (2026-11-23): Emails' templates per item and audience, and the send ticks. Sending stays AD7's | — | `applydesk/guide/archive/segment_AD2L_emails.md` (version 1, closed 2026-11-23) |
| AD2F — Dossiers, pairs and gates | Dossiers, parts and snapshots; gate entries, results and outcome decisions with who and when; stored pairs and the roster an opened gate keeps; the gate lifecycle and its transfer record; Lock as one audited transaction; `Assessor` and `Evaluator` dropped for pairs (AD-50's rest). May split in two. | AD-44, AD-58, AD-47, AD-32, AD-39, AD-35 | — |
| AD2V — Dossier visibility | Ruling 79's views: what each gate × panel's evaluators see during its window, what each outcome opens to candidates and past evaluators (continue, add or reset), each field's ceiling, and the flag for an item no view shows; after AD2F stores dossiers | — | — |
| AD2S — A scale on a Review Robin gate | `gate_field`'s `scale` and `scale_labels`; the gate's *Response fields* offer *Integer (scale)* and *Decimal (scale)*, and the handoff carries them (moved from Review Robin's 20P Item 2, 2026-11-25) | — | `applydesk/guide/archive/segment_AD2S_gate_scale.md` (closed 2026-11-25) |
| AD2G — Retire the simulation | In two parts. First, once AD2E, AD2D and AD2L store their pages: the browser's scratch store removed, *New exercise* and *Duplicate* making ordinary exercises, and test exercises seeded instead (`python -m applydesk.seed` with a reset and blank exercises; Admin's *Load sample exercises* for Azure). Then request-scoped loading with SQL paging, and the sample-data path off production | S10 follow-up, AD-125 | — |

**The order from AD2C** (author, 2026-11-23): **AD2E** panels, then **AD2D** version 1 (the form's questions), then **AD2L** email templates, then **AD2G**'s first part (the browser store removed, test exercises seeded). Each moves its page off the browser store, which goes once nothing reads it, so no stopgap table is needed. AD2F, AD2V, the rest of AD2D and the rest of AD2G follow.

Each segment that adds a page's controls lands scaffold-first (`CLAUDE.md`, "Consequential UI lands scaffold-first"). Each closes on its own: Status compacted, `spec-writer` on `applydesk/spec/`, the plan archived, its findings struck in `applydesk/guide/ad2_deferred_findings.md` with the PR that cleared them.

## Outside the series

- **Cordware provisioning:** done 2026-11-21. The `applydesk` database, its runtime role `applydesk_app`, its Key Vault secret and the App Setting `APPLYDESK_DATABASE_URL` were made by the private repository's `postgres-applydesk-database.yml` and `app-settings-database-urls.yml`. AD2 reaches Cordware with the import of RRW `48b225a` (rules v16, 2026-11-22), and each release migrates `applydesk` before the upload, from its own row in `release.yml`.
- **AD3 onward** add behavior to the stored data: exercise transitions and what a published exercise fixes (AD3, G2), applicants submitting (AD4), dossier access (AD5), sending to Review Robin (AD6), release (AD7).
