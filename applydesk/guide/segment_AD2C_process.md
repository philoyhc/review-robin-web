# Segment AD2C — Process

**Opened:** 2026-11-22 · **Theme:** an exercise's timeline (stages, the form's window and state, gates, outcomes, rules) and who is invited move into the database, and Process's *Save* keeps them for every exercise · **Related:** `applydesk/guide/ad2_series.md`, `applydesk/guide/ad2_deferred_findings.md`, `applydesk/spec/applications.md` ("The Process page"), rulings 13–16, 23, 24, 31, 35, 37, 38 (`applydesk/guide/todo_master.md`)

## Opportunity

- **Process keeps nothing an exercise can rely on.**
  - On a sample exercise, *Save* is disabled.
  - On a scratch exercise it saves into the browser's in-memory store (`scratch.page(…, "process")`), which a deploy, a restart or eight idle hours drops.
  - Since AD2 reached production (Cordware run 49, 2026-11-22), every exercise an operator makes there is a scratch exercise, so its Process is lost on the next deploy.
- **The pages hold the timeline as text and positions,** and the 2026-11-18 assessment's rows say where:
  - **AD-36, AD-59, AD-60:** form state from `Exercise.state` and `form_open`; the form window in three places; "Dates not set" stored as text.
  - **AD-48, AD-51:** gate keys minted in the browser and numbered by position, the number being the public handle; result keys positional, with synthesized field keys.
  - **AD-57, AD-34:** outcome values as bare labels; release as free text with no model home.
  - **AD-61, AD-62:** no rule evaluator on the server; rules naming targets by loose strings.
  - **AD-52:** *Invitation only* with no invitee list. The author ruled it a stage item on 2026-11-22.
- **Bug-sweep rows with no segment:**
  - **AD-129:** `process_save`'s digit check, rewritten here.
  - **AD-128:** Apply Desk's tests never run on Postgres. AD2O's Codex rounds found three lock races SQLite could not show.
  - **AD-126:** the same-site check, written twice.

## Decision

- **Tables,** each keyed per exercise (ruling 37). Rows are retired, never deleted (ruling 74):
  - `stage`:
    - position, name and dates (`starts_at` and `ends_at`, NULL for unset);
    - `status` (`draft` or `published`, ruling 35) and `shown`;
    - for the stage holding the form: `form_opens_at` and `form_closes_at`, plus `form_state` (`draft`, `open` or `closed`, each move timed).
    - That stage is the one source for the form's window (AD-36, AD-59).
  - `gate`:
    - a surrogate id plus a `key` unique per exercise and never reused, and its stage and position;
    - label, description, confidential, mode, Total, review window;
    - `rule` (JSON, below).
    - Its number is computed for display only.
  - `gate_field`: a stable key, plus label, type, bounds or options, required and help.
  - `gate_result`: a key, a position (1 is the headline) and an FK to the `gate_field` it collates, plus derivation, value, at-least and ignore-zero (AD-51).
  - `gate_source`:
    - rank, kind, min and max, and *all members*;
    - `ref`, which stays a panel key or a Form question key until AD2E or AD2D stores those.
  - `outcome`: key, stage, label, `due_at` and `rule`.
  - `outcome_value`: key, label, position and `advances` (AD-57).
  - `outcome_weight`: the outcome and a gate FK, with the weight.
  - Release per audience (ruling 38, AD-34):
    - `outcome_audience` records whom an outcome is released to;
    - `outcome_release` records who released it to which audience, and when;
    - *Decided* stays derived.
  - `exercise_invitee`: the exercise, a person FK, and who added them and when (AD-52).
- **Rules are validated JSON with typed references:**
  - The current `Rule` shape, with each target named by key: gate, result, outcome, value, form question.
  - Saving builds a dependency index and checks scope (a gate never reads a gate).
  - A rule naming a target the snapshot drops is **refused**, with the rule and the target named (AD-62). Today's `removed` marker goes.
  - A form question stays a string reference until AD2D keys it.
- **One Save, replacing the draft (ruling 23):**
  - The page's snapshot is checked whole and written in one transaction under the exercise's row lock, guarded by the revision (ruling 74, as Details).
  - Existing keys are kept; the server mints new ones, so `gnew1` never reaches a row.
  - Ruling 15's shape is re-checked.
  - Audited as `exercise.process_saved`, with counts.
  - A sample exercise's timeline is recorded at its first save, as AD2B recorded its settings.
  - A scratch exercise saves to the database like any other.
- **`stages.plan_of` reads the stored timeline** when there is one, else the sample. The pages keep their dataclasses: `process_store` builds them. Dossiers' cells stay the sample's until AD2F.
- **A gate's handle is its key:**
  - `/evaluations/<key>` and Extract's file names (ruling 37, AD-48);
  - the old `gate_<n>` URLs redirect once to the keyed one.
- **The rule engine on the server (ruling 31, AD-61):**
  - `rules.py` evaluates every condition kind.
  - It is tested for parity with the page's JS on shared fixtures.
  - It is the authority at save (validity) and, from AD2F, at *Lock*; the JS stays as the page's preview.
- **Invitees and the form's state are new controls,** so they land scaffold-first:
  - An *Invitees* item on the form's stage, shown when Who may apply is `invitation`. People are added by search (ruling 75) and removed in the list.
  - *Open form* and *Close form*, where the open question below places them, follow ruling 24.
- **Placed with this segment:**
  - **AD-128:** Apply Desk's tests in `ci-postgres`. This comes first, since this segment adds locks.
  - **AD-126:** one same-site helper for every post.
  - **AD-129:** goes with the save's rewrite.
  - **AD-127:** moves to AD2E, whose people search it serves.
  - **AD-35:** Process's half is here; the other surfaces stay with AD2F.

Rejected:
- **One JSON document per exercise.** It's simpler to save, but AD-48, AD-51 and AD-57 want keyed rows that later tables (pairs, cells, emails) reference by FK, and AD2F would have to unpick it.
- **Cascading a removed target into the rules that name it.** It silently changes what a saved rule means.

## Semantics

- **Unset dates are NULL.** The pages print *Dates not set*.
- **A reversed pair** is refused at save. Today it is kept as "no dates".
- **A key is never reused within an exercise.** A removed gate's key stays on its retired row, so an old link 404s rather than reaching a new gate. Keys are `g<n>` and `o<n>`, with the counter per exercise.
- **Concurrent saves:** the second is refused, *changed since you opened it; reload*, as Details is. Nothing merges.
- **A published stage (ruling 35):**
  - The server refuses the same edits the page already disables (its items' removal, reordering across it).
  - Reverting it to draft is its own audited move, not a save side effect.
- **Form state moves only forward:** `draft` → `open` → `closed`. It opens only once the exercise is published (ruling 24); each move is audited. Reopening is not in the MVP.
- **Invitees:**
  - A person is invited once.
  - Removing someone retires their row.
  - The list is kept even if Who may apply returns to `open`; it is then simply unused.
  - Checking at apply time is AD4's.
- **Release rows are written only by a release** (Dossiers' *Release*, AD2F). AD2C stores the audiences and the empty table.
- **A sample exercise not yet saved** reads the sample. Once saved, it reads only its rows. Seeding writes no timeline.
- **Size limits are kept,** as today's `MAX_STAGES` and `MAX_GATES`.

## Judgment calls — decided

- A rule naming a removed target is refused, not cascaded or marked: a saved rule means what it says (AD-62).
- The form's window is on the stage holding it, not in a `form` table. AD2D's `form_version` holds the questions, not the window.
- The old `gate_<n>` URLs redirect once rather than 404, because links to them are in sent emails and bookmarks.
- AD-127 goes to AD2E, which first needs Unicode-aware people search for panel members.

## Blast radius (measured)

Taken 2026-11-22 at `1ceb1d592`.

| What | Count | Command |
|---|---|---|
| Modules calling `stages.plan_of` | 7 (33 calls) | `grep -rln 'plan_of(' applydesk/*.py \| grep -v stages.py` |
| Modules calling `process_save` | 2 | `grep -rln 'process_save' applydesk/*.py \| grep -v process_save.py` |
| Scratch `"process"` page reads and writes | 6 | `grep -rn '"process"' applydesk/*.py` |
| Code and templates using `gate_<n>` handles | 10 in 7 files | `grep -rn 'gate_{\|/gate_' applydesk --include=*.py --include=*.html \| grep -v tests` |
| Templates naming Process | 9 | `grep -rln process applydesk/templates` |
| Test files on Process or its save | 13 | `grep -rln 'process_save\|/process' applydesk/tests --include=*.py` |
| Test files reading `stages.` | 25 | `grep -rln 'stages\.' applydesk/tests` |
| `_same_site` definitions | 2 | `grep -n 'def _same_site' applydesk/*.py` |

## PR ladder

1. **PR 1 — this plan.** Also places AD-126 to AD-129, AD-60 and AD-35 in the register and in `ad2_series.md`.
2. **PR 2 — Apply Desk's tests on Postgres (AD-128).**
   - `applydesk/tests` run in `ci-postgres`.
   - A race test from AD2O's Revoke runs there.
   - Must not touch `applydesk/` code.
3. **PR 3 — the tables.**
   - Models and a migration, round-tripped on Postgres.
   - Nothing reads them yet.
4. **PR 4 — `process_store` and `rules.py`.**
   - Load the timeline into the pages' dataclasses.
   - Save with validation, keys, the revision guard and the audit (AD-62, AD-129).
   - The evaluator and its parity fixtures (AD-61).
   - Must not change a page.
5. **PR 5 — Process saves for every exercise.**
   - `plan_of` reads the stored timeline.
   - Save is enabled.
   - The scratch timeline moves to the database.
   - Typed values and keys reach every reader (AD-36, AD-48, AD-51, AD-57, AD-59, AD-60).
   - `/evaluations/<key>` and Extract's names.
6. **PR 6 — one same-site helper (AD-126).** Its own small rung.
7. **PR 7 — scaffold:** the *Invitees* item and *Open form* / *Close form*, inert, with real copy.
8. **PR 8 — wired:**
   - Invitees saved and removed (AD-52).
   - The form's state moves (AD-36, ruling 24).
   - Release audiences (AD-34).
   - Last build rung: the cumulative `diff-reviewer` read, split at a rung boundary past about 1,500 lines.
9. **PR 9 — close.**

## Definition of done

- **The tables:** stages, gates, their fields, results and sources, and outcomes, their values, weights and audiences all exist. The migration round-trips on Postgres (`ci-postgres`).
- **Saving a Process:**
  - It survives a restart.
  - A stale revision is refused.
  - A rule naming a removed target is refused.
  - Keys persist across saves.
  - Tested in `applydesk/tests/test_process_store.py`.
- **`rules.py`** agrees with the page's JS on every shared fixture (`applydesk/tests/test_rules.py`).
- **Gate handles:** `/evaluations/<key>` serves a gate, `gate_<n>` redirects, and Extract's names use keys.
- **Invitees** can be added and removed. *Open form* and *Close form* move `form_state` and are audited.
- **Postgres:** `applydesk/tests` run in `ci-postgres`.
- **AD-126 to AD-129, AD-34, AD-36, AD-48, AD-51, AD-52, AD-57, AD-59, AD-61 and AD-62** are struck in `applydesk/guide/ad2_deferred_findings.md`, each with its PR.
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD2C` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

1. **Where *Open form* and *Close form* sit.** Proposed: as the action of Home's next step, which `workflow.steps` already words (*Open form…*, *Close form…*). The alternative is on the form's item in Process. *The author.*
2. **How the invitee list is kept.** Proposed: people search only for the MVP. The register notes that CSV upkeep has no home. *The author.*
3. **Where the rule engine runs (ruling 31).** Proposed: the Python evaluator is the authority at save and, from AD2F, at *Lock*; the JS stays as the page's preview. Ruling 31 asked for this to be thought through before AD2. *The author.*

## Out of scope

- **Dossiers' cells, decisions, pairs and the *Release* action:** AD2F. AD2C stores the audiences, not the release.
- **Form questions and their keys:** AD2D. Rules naming a question keep a string until then.
- **Panels:** AD2E. Sources keep panel keys until then.
- **The applicant's check against the invitee list:** AD4.
- **Retiring the scratch store and an expired scratch exercise's row:** AD2G (author, 2026-11-22).
- **Reopening a closed form:** not in the MVP.

## Doc impact

- `applydesk/spec/applications.md` — the Process page's Save for every exercise, its refusals and keys; the *Invitees* item; *Open form* / *Close form*; Evaluations' `/evaluations/<key>` and Extract's file names; Unset dates.
- `applydesk/spec/architecture.md` — the Process tables, `process_store.py`, `rules.py`, the audit events, and Apply Desk's tests in `ci-postgres`.
- `applydesk/spec/permissions.md` — the *Invitee* row marked built (stored list; the apply-time check stays AD4's).
- `applydesk/guide/ad2_deferred_findings.md` — strike the findings AD2C clears; AD-127 marked for AD2E (plan PR).
- `applydesk/guide/ad2_series.md` — AD2C's row gains AD-60's stage half, AD-35's Process half, AD-126, AD-128 and AD-129; AD2E's gains AD-127 (plan PR); AD2C's plan pointer, then its archived copy.
- `applydesk/guide/todo_master.md` — the roadmap's AD2 row names AD2C's plan while open (at close: removed).
- `applydesk/README.md` — the plan's index row, moved at close.
