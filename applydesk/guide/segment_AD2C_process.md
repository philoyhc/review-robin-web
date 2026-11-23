# Segment AD2C — Process

**Opened:** 2026-11-22 · **Theme:** an exercise's timeline (stages, the form's window and state, gates, outcomes, rules) and its Candidates move into the database; Process's *Save* keeps them for every exercise, and the rule engine runs on the server alone · **Related:** `applydesk/guide/ad2_series.md`, `applydesk/guide/ad2_deferred_findings.md`, `applydesk/spec/applications.md` ("The Process page"), rulings 13–16, 23, 24, 31, 35, 37, 38 and 76–78 (`applydesk/guide/todo_master.md`)

## Opportunity

- **Process keeps nothing an exercise can rely on.**
  - On a sample exercise, *Save* is disabled.
  - On a scratch exercise, *Save* writes into the browser's in-memory store (`scratch.page(…, "process")`). A deploy, a restart or eight idle hours drops it.
  - Since AD2 reached production (Cordware run 49, 2026-11-22), every exercise made there is a scratch exercise, so its Process is lost on the next deploy.
- **The pages hold the timeline as text and positions.** The 2026-11-18 assessment's rows say where:
  - AD-36, AD-59 and AD-60: form state comes from `Exercise.state` and `form_open`; the form window lives in three places; "Dates not set" is stored as text.
  - AD-48 and AD-51: gate keys are minted in the browser; the gate number, a position, is the public handle; result keys are positional and field keys are synthesized.
  - AD-57 and AD-34: outcome values are bare labels; release is free text with no model home.
  - AD-61 and AD-62: rules are evaluated only in page JS, and name their targets by loose strings.
  - AD-52: *Invitation only* has no list of who is invited.
- **The AD2A bug sweep's rows had no segment:**
  - AD-129: `process_save`'s digit check, which this segment rewrites.
  - AD-128: Apply Desk's tests never run on Postgres. AD2O's Codex rounds found three lock races that SQLite could not show.
  - AD-126: the same-site check is written twice.

## Decision

- **Tables,** each keyed per exercise (ruling 37). Rows are retired, never deleted (ruling 74).
  - `stage`:
    - position, name, `starts_at` and `ends_at` (NULL when unset), `status` (`draft` or `published`, ruling 35) and `shown`;
    - on the stage holding the form: `form_opens_at`, `form_closes_at`, and `form_state` (`draft`, `open` or `closed`), each move timed.
    - That stage is the one source of the form's window (AD-36, AD-59).
  - `gate`:
    - a surrogate id, and a `key` unique per exercise and never reused;
    - its stage and position, label, description, confidential, mode, Total and review window;
    - `rule` (JSON).
    - Its number is computed, for display only.
  - `gate_field`: a stable key, label, type, bounds or options, required, help.
  - `gate_result`: a key, a position (1 is the headline), an FK to the `gate_field` it collates, its derivation, value, at-least and ignore-zero (AD-51).
  - `gate_source`: rank, kind, `ref`, min and max, and all-members. `ref` is a panel key or a Form question key until AD2E or AD2D stores those.
  - `outcome`: key, stage, label, `due_at`, `rule`.
  - `outcome_value`: key, label, position, `advances` (AD-57).
  - `outcome_weight`: the outcome, a gate FK and the weight.
  - ~~`outcome_audience` and~~ `outcome_release`: ~~whom the outcome is released to, and~~ who released it to which audience when (ruling 38, AD-34). *Decided* stays derived. *Whom an outcome opens to is ruling 79's views, in AD2V (2026-11-23).*
  - `candidate_list` and `candidate`: the Candidates item (ruling 77). The list sits on a stage; each candidate is a person FK, added by whom and when, and how (search or CSV).
- **Rules are validated JSON with typed references.**
  - The `Rule` shape stays, with every target named by key: gate, result, outcome, value, form question.
  - Saving builds a dependency index and checks scope: a gate never reads a gate.
  - A rule naming a target the snapshot drops is **refused**, with the rule and the target named (AD-62). Today's `removed` marker goes.
  - Form questions stay a string reference until AD2D keys them.
- **One Save replaces the draft** (ruling 23).
  - The page's whole snapshot is checked and written in one transaction under the exercise's row lock, guarded by the revision (ruling 74, as Details is).
  - Existing keys are kept and the server mints new ones, so `gnew1` never reaches a row.
  - Ruling 15's shape is re-checked.
  - The save is audited as `exercise.process_saved`, with counts.
  - A sample exercise's timeline is recorded at its first save, as AD2B recorded its settings. A scratch exercise saves like any other.
- **`stages.plan_of` reads the stored timeline** when there is one, else the sample. Pages keep their dataclasses, which `process_store` builds. Dossiers' cells stay the sample's until AD2F.
- **The rule engine is server-only** (ruling 78, AD-61).
  - `rules.py` evaluates every condition kind and is the only evaluator.
  - Process asks it for a rule's problems; Dossiers asks it for proposals over the current cells.
  - The pages' JS evaluators (`_dossiers.html`, `_process.html`) are deleted.
  - Before deleting them, one parity run on shared fixtures proves the server answers as the JS did.
- **A gate's handle is its key** (ruling 37, AD-48): `/evaluations/<key>` and Extract's file names. A `gate_<n>` URL redirects once to the keyed one.
- **New controls land scaffold-first:**
  - **Candidates** (ruling 77): a stage item listing people, added by search (ruling 75) or by CSV, removed in the list. It is the form's roster when Who may apply is `invitation`; feeding gates as dossiers is AD2F's.
  - ***Open form* and *Close form*** (ruling 76): the action of Home's next step, moving `form_state` (ruling 24).
- **Placed with this segment:**
  - AD-128 first: Apply Desk's tests run in `ci-postgres`, since this segment adds locks.
  - AD-126: one same-site helper.
  - AD-129: with the save's rewrite.
  - AD-127 goes to AD2E, whose people search it serves.
  - Process's half of AD-35 is here; the other surfaces stay with AD2F.

**Rejected:**
- **One JSON document per exercise.** It is simpler to save, but AD-48, AD-51 and AD-57 want keyed rows that pairs, cells and emails will reference by FK.
- **Cascading a removed target into its rules.** It silently changes what a saved rule means.
- **Keeping the JS as the evaluator or as a preview** (ruling 78). It would mean two engines to keep in step.

## Semantics

- **Dates.** Unset dates are NULL, and the pages print *Dates not set*. A reversed pair is refused at save; today it is kept as "no dates".
- **Keys.** A key is never reused within an exercise. A removed gate's key stays on its retired row, so an old link 404s rather than reaching a new gate. Keys are `g<n>` and `o<n>`, with a counter per exercise.
- **Concurrent saves.** The second save is refused (*changed since you opened it; reload*), as Details' is. Nothing merges.
- **Published stages** (ruling 35). The server refuses the edits the page already disables. Reverting a stage to draft is its own audited move.
- **Form state** moves only forward: `draft` → `open` → `closed`. It opens only once the exercise is published (ruling 24), and each move is audited. Reopening is not in the MVP.
- **Candidates.**
  - A person is listed once.
  - Removing someone retires their row.
  - **CSV:**
    - One email per row, plus an optional name.
    - Each row is matched to a person on record, then the directory, else made pending (`people.pending`).
    - Rows that are malformed or duplicated are reported back, not saved. The rest are saved in one transaction.
  - The list stays if Who may apply returns to `open`; it is then simply unused as a roster.
  - Checking it at apply time is AD4's.
- **Proposals.** The server answers for the cells as they stand, and an unsaved Process edit is not seen until saved. Dossiers waits on the request; past about 2 s it says it is working.
- **Release.** Release rows are written only by a release, which is AD2F's *Release*. AD2C stores the audiences and the empty table.
- **Samples.** A sample exercise not yet saved reads the sample; once saved it reads only its rows. The seed writes no timeline.

## Judgment calls — decided

- A rule naming a removed target is refused, neither cascaded nor marked: a saved rule means what it says (AD-62).
- The form's window sits on its stage, not in a `form` table. AD2D's `form_version` holds the questions.
- An old `gate_<n>` URL redirects once rather than 404, because sent emails and bookmarks hold them.
- AD-127 goes to AD2E, which needs Unicode-aware people search for panel members first.
- The Candidates CSV saves its good rows and reports the bad ones, rather than refusing the whole file. This matches how the Panels roster imports.

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

## Status

- **2026-11-23, ruling 79:** visibility moves to its own segment (AD2V). `outcome_audience` leaves rung 3's tables; `outcome_release` stays (ruling 38).
- **2026-11-23, rung 5 split:** 5a lands the store's wiring (`plan_of` reads it, *Save* on every exercise, keys kept and minted past every key held, a sample's included). 5b lands `/evaluations/<key>` and Extract's names. The form's window and state (AD-36, AD-59, AD-60) move with rung 9's *Open form*.
- **Decisions confirmed at build (rung 5a):**
  - A sample's saved timeline keeps the sample's cells; a column it never had is blank until AD2F.
  - Email ticks stay in the scratch store until Emails is stored; on a sample they stay the sample's.
  - A panel made on a sample's Process is refused until AD2E stores panels.
- **2026-11-23, cumulative read on rungs 2-5** (`diff-reviewer`, base `1d09637c2`): a removed field or result could not be added back (fixed in rung 4: revived); times read back in the database's zone (fixed: UTC); a concurrent first save reached the operator as a 500 (fixed in rung 5). Left for later:
  - Published stages: the save refuses only their removal. Refusing other edits to them, and an audited revert to draft, move to rung 9 with the form's state.
  - `plan_of` reads the store on every call, without a per-request cache: about 200 queries on a saved sample's Process, 0.17 s locally. AD2G's request-scoped loading.
  - Sources and weights are replaced on each save, not retired: they are parts of a gate or an outcome, never named on their own.
  - An outcome value renamed on the page takes a new key (Codex on #4154): its values are one list of labels. **Ruled 2026-11-23 (author):** a values editor that carries each value's key through a rename is built within AD2C, as its own rung after rung 9 and before the close.
  - `applydesk/spec/applications.md` still describes renumbering and `removed`: the close's spec pass.
  - Rung 9: re-adding a removed candidate revives its row (`uq_candidate_pair`); the Decision's `candidate_list` became `stage.holds_candidates`.
- **2026-11-23, rung 10 (values editor):** values are rows on Process, each carrying its key; a rename keeps it and the page rewrites the rules naming it. Carried keys are assigned before label matches.
- **2026-11-23, cumulative reads at rung 10**, split at rung 6 (over ~1,500 lines; bases `cae6108d6` and `875d1535a`). Fixed in rung 10:
  - Rung 6: `_is_number` accepted `1_000`, `nan` and `inf`; a failed older check dropped a newer answer; a too-deep body was a 500.
  - Rungs 7-9: a published stage's end could not be extended; adds and a changed start or `shown` were not refused; a revert's reason was not audited; moving the form reseeded its state; a rename typed through a sibling's label merged their rules; three minor messages.
  - Left: a CSV row not on record is made pending without a directory lookup, deliberately (the directory is searched one person at a time, from the search). A published stage's rule and value edits are not refused by the save; the page leaves them editable too.

## PR ladder

1. **PR 1 — this plan.**
   - Rulings 76–78.
   - AD-126 to AD-129, AD-60 and AD-35 placed in the register and in `ad2_series.md`.
2. **PR 2 — Apply Desk's tests on Postgres (AD-128).**
   - `applydesk/tests` runs in `ci-postgres`, with a race test from AD2O's Revoke.
   - Must not touch `applydesk/` code.
3. **PR 3 — the tables.**
   - Models and a migration, round-tripped on Postgres.
   - Nothing reads them yet.
4. **PR 4 — `process_store`.**
   - Loads into the pages' dataclasses.
   - Saves with validation, keys, the revision guard and the audit (AD-62, AD-129).
   - Must not change a page.
5. **PR 5 — Process saves for every exercise.**
   - `plan_of` reads the stored timeline; *Save* is enabled; the scratch timeline moves to the database.
   - Keys and typed values reach every reader (AD-36, AD-48, AD-51, AD-57, AD-59, AD-60).
   - `/evaluations/<key>` and Extract's names.
6. **PR 6 — the server's rule engine** (ruling 78, AD-61).
   - `rules.py`, with one parity run against the JS fixtures.
   - Process and Dossiers ask the server; the JS evaluators are deleted.
7. **PR 7 — one same-site helper (AD-126).**
8. **PR 8 — scaffold, inert, with real copy.**
   - The *Candidates* item on Process: search, CSV upload and list.
   - *Open form* / *Close form* as Home's next-step action.
9. **PR 9 — wired.**
   - Candidates saved, imported and removed (ruling 77, AD-52).
   - The form's state moves (ruling 76, AD-36).
   - ~~Release audiences (AD-34).~~ *To AD2V, ruling 79.*
   - Last build rung: the cumulative `diff-reviewer` read, split at a rung boundary past about 1,500 lines.
10. **PR 10 — close.**

## Definition of done

- **The tables** exist for stages, gates (with fields, results and sources), outcomes (with values, weights and releases) and Candidates. The migration round-trips in `ci-postgres`.
- **A saved Process:**
  - survives a restart;
  - is refused on a stale revision, or when a rule names a removed target;
  - keeps its keys (`applydesk/tests/test_process_store.py`).
- **`rules.py`** answered every parity fixture as the JS did before it was deleted (`applydesk/tests/test_rules.py`). No rule evaluator remains in a template: `grep -rn` for its entry points in `applydesk/templates` finds none.
- **Gate handles:** `/evaluations/<key>` serves a gate, `gate_<n>` redirects, and Extract's names use keys.
- **Candidates** can be added by search and by CSV (with bad rows reported) and removed.
- ***Open form* and *Close form*** on Home move `form_state` and are audited.
- `applydesk/tests` runs in `ci-postgres`.
- **The register:** AD-126, AD-128, AD-129, AD-34, AD-36, AD-48, AD-51, AD-52, AD-57, AD-59, AD-61 and AD-62 are struck in `applydesk/guide/ad2_deferred_findings.md`, each with its PR.
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD2C` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

1. ~~Where *Open form* and *Close form* sit~~: Home's next step (ruling 76).
2. ~~How invitees are kept~~: the Candidates stage item, by search and CSV (ruling 77).
3. ~~Where the rule engine runs~~: on the server alone, with the JS retired (ruling 78).
4. ~~Where Candidates sits under ruling 15~~: at most one per exercise, with the form, with gates or alone; *+ Candidates* disabled with its reason once there is one (author, 2026-11-22; ruling 77).

## Out of scope

- **Dossiers' cells, decisions and pairs, the *Release* action, and Candidates loaded as dossiers:** AD2F. AD2C stores the list.
- **Who sees what in a dossier** (ruling 79): AD2V.
- **Form questions and their keys:** AD2D. Rules naming a question keep a string until then.
- **Panels:** AD2E. Sources keep panel keys until then.
- **The applicant's check against Candidates:** AD4.
- **Retiring the scratch store, and an expired scratch exercise's row:** AD2G (author, 2026-11-22).
- **Reopening a closed form:** not in the MVP.

## Doc impact

- `applydesk/spec/applications.md` — the Process page's Save for every exercise, its refusals and keys; the *Candidates* item; Home's *Open form* / *Close form*; Evaluations' `/evaluations/<key>` and Extract's file names; server-side rule checks and Dossiers' proposals; Unset dates.
- `applydesk/spec/architecture.md` — the Process and Candidates tables, `process_store.py`, `rules.py`, the audit events, and Apply Desk's tests in `ci-postgres`.
- `applydesk/spec/permissions.md` — the *Invitee* row becomes Candidates as a form's roster, marked built (the apply-time check stays AD4's).
- `applydesk/guide/ad2_deferred_findings.md` — strike the findings AD2C clears; AD-127 marked for AD2E (plan PR).
- `applydesk/guide/ad2_series.md` — AD2C's row gains AD-60's stage half, AD-35's Process half, AD-126, AD-128 and AD-129; AD2E's gains AD-127 (plan PR); AD2C's plan pointer, then its archived copy.
- `applydesk/guide/todo_master.md` — rulings 76–78 (plan PR); the roadmap's AD2 row names AD2C's plan while open (at close: removed).
- `applydesk/README.md` — the plan's index row, moved at close.
