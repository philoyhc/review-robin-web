# Segment AD2F — Dossiers

**Opened:** 2026-11-26 · **Theme:** the dossier becomes its own stored record, with or without an application · **Related:** `applydesk/guide/ad2_series.md`, `applydesk/guide/ad2_deferred_findings.md` (AD-44), `applydesk/docs/data_and_visibility_model.md`, `applydesk/spec/applications.md`, rulings 24–26, 32, 43, 77 and 81 (`applydesk/guide/todo_master.md`)

## Opportunity

- **The dossier is a field on the application** (AD-44). `sample_data.Application.dossier_id` is a string written in code, kept since AD2J in `sample_data.sample_dossier_id`. Nothing can make a new one.
- **A dossier without an application cannot exist.** Ruling 81 mints one per candidate where the Candidates item feeds gates, but the Dossiers grid, gate pages, Extract and the handoff all walk `stages.Row.application`: 34 reads in 7 modules. A candidate with no application has no row to sit in.
- **AD2H, AD2P and AD2T hang off the dossier** (ruling 32): entries, pairs and the frozen copy at send all need a key to point at.

## Decision

- **One table, `dossier`**, keyed per exercise:
  - `public_id` (unique, ten characters, ruling 7; never the application's, ruling 53) and its exercise;
  - its source: `application_id` (FK, NULL for none) or `candidate_id` (FK to Candidates' row), exactly one of the two;
  - `created_at`, and `retired_at` for a dossier whose candidate is removed before any gate holds it (ruling 74: nothing deleted).
- **Minting** (ruling 81, author 2026-11-26):
  - **Candidates feed gates when the timeline holds no form** (ruling 24's "an exercise with no form loads its candidates as dossiers"). With a form, Candidates is only the form's roster and mints nothing.
  - Such a Candidates item mints each candidate's dossier **when the exercise is published** (its first stage published by a Process save) and **on each later add**, by search or CSV.
  - **From the form:** the at-submit or at-close choice (ruling 24) and its minting come with AD4, when applicants submit (author, 2026-11-26). Until then the only form dossiers are the samples'.
- **The seed records the samples' dossiers** with the IDs they carry today, so links and the alias key do not move.
- **Rows are dossiers.** `stages.Row` carries a `Dossier` view (its ID, the candidate's name and address, and its application or None). The Dossiers grid, gate pages, Extract, rules and the handoff read the dossier; what only an application has (state, submitted day, form answers) is read through it where present. A draft application, which has no dossier, stays a row as today, its dossier ID blank (ruling 32).
- **No dossier items table.** What a dossier shows is read from the store as today (form answers, gate results, outcomes); who sees which item is AD2V's (ruling 79).

**Rejected:**
- **A stand-in application for a candidate's dossier**, so `Row.application` keeps its shape: it would carry an empty state and a fake public ID into every reader, and AD2H's entries would key on it.
- **The frozen copy at send (ruling 25) here.** Sending is AD2T's, with the transfer record; a snapshot with nothing yet able to send it would be untested shape.
- **Minting a form's dossiers at its close now.** No setting holds the choice, and no applicant submits before AD4 (author, 2026-11-26).

## Semantics

- **Exactly one source.** A check constraint: `application_id` or `candidate_id`, never both, never neither.
- **One live dossier per source.** A candidate removed and added again gets the dossier they had back (`retired_at` cleared), as Candidates' own row does.
- **Removal after entry.** A candidate removed while a gate holds their dossier keeps it: retiring is refused once AD2H records an entry. Until AD2H, nothing holds one, so removal retires it.
- **No form appearing later.** A form added to a timeline whose Candidates already minted leaves those dossiers; Candidates is a roster from then on and mints no more. Recorded, not prevented.
- **IDs.** Minted by `ids` in the exercise and application namespace (ruling 53), unique by index, retried on a clash.

## Judgment calls — decided

- **"No form" is read from the stored timeline** (2026-11-26): a stage that `holds_form`. A sample's timeline in code counts as having a form.
- **The candidate's name** is Candidates' person's display name, else their address, as Candidates' list shows it (2026-11-26).

## Blast radius (measured)

Taken 2026-11-26 at `dcd9bec6f`.

| What | Count | Command |
|---|---|---|
| Modules reading `dossier_id` | 9 | `grep -rln "dossier_id" applydesk --include=*.py \| grep -v /tests/ \| wc -l` |
| Reads of `Row.application` | 34, in 7 modules | `grep -rn "\.application\b" applydesk --include=*.py \| grep -v /tests/ \| wc -l` |
| Templates naming a dossier ID | 5 | `grep -rln "dossier_id\|by_dossier" applydesk/templates` |
| Test files naming dossiers | 61 | `grep -rln dossier applydesk/tests \| wc -l` |
| Specs | 3 (`applications.md`, `architecture.md`, `permissions.md`) | `grep -rli dossier applydesk/spec/*.md` |

## PR ladder

1. **Plan** (this file), the series row. Prose only.
2. **The table and the seed.** `Dossier` model, migration `ad2f1_dossiers`, the seed recording the samples' dossiers by their IDs, audited. Must not touch: any reader.
3. **Dossier IDs from the store.** `sample_dossier_id` goes; `applications.from_row` and `by_dossier` read the table. Tests: an ID read back; a draft with none.
4. **Rows are dossiers.** The `Dossier` view on `stages.Row`, and its 34 readers. Must not change what a sample's pages show.
5. **Candidates mint.** At publish and on add, when the timeline holds no form; retiring on removal. Tests: no form mints, a form mints nothing, re-adding revives.
   - **Last build rung:** `diff-reviewer` on the cumulative diff from rung 2's base.
6. **Close:** `spec-writer` on `applydesk/spec/`; AD-44 struck; the data model draft updated; Status compacted; the plan archived.

## Definition of done

- `dossier` round-trips on SQLite and Postgres 16 (`ci-postgres.yml`).
- `sample_data.sample_dossier_id` is gone (`grep -rn sample_dossier_id applydesk --include=*.py` finds nothing).
- An exercise with Candidates and no form shows its candidates' dossiers on Dossiers once published (a test).
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD2F` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **A candidate dossier's page** (`/me/.../dossiers/<id>`, the operator's dossier): shows the candidate's name and nothing from a form. What else it shows is AD2V's views; decided there.

## Out of scope

- The form's at-submit / at-close minting and its setting: AD4.
- The frozen copy a sent gate keeps (ruling 25): AD2T.
- Entries, results and outcome decisions per dossier: AD2H. Pairs: AD2P.
- Who sees which item: AD2V.

## Doc impact

- `applydesk/spec/applications.md` — Dossiers' rows are dossiers; Candidates mint dossiers where the timeline holds no form.
- `applydesk/spec/architecture.md` — the `dossier` table, the module map, the seed.
- `applydesk/spec/permissions.md` — a candidate's dossier, opened by its ID.
- `applydesk/docs/data_and_visibility_model.md` — §2's dossier as built.
- `applydesk/guide/ad2_deferred_findings.md` — AD-44 struck (at close).
- `applydesk/guide/ad2_series.md` — the AD2F row closed (at close).
