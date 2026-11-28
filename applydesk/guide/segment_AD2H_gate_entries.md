# Segment AD2H — Gate entries and outcomes

**Opened:** 2026-11-28 · **Theme:** the Dossiers grid's cells kept in the database: who enters each gate, each gate's results, each outcome's decision, and its release · **Related:** `applydesk/guide/ad2_series.md` (AD2H), rulings 13, 23, 38 and 52 (`applydesk/guide/todo_master.md`), AD-58, AD-35 and AD-34 (`applydesk/guide/ad2_deferred_findings.md`), `applydesk/docs/data_and_visibility_model.md` §2

## Opportunity

- **The Dossiers page is the last placeholder** in the operator's setup-to-decision path: its line says the cells "work on screen, but are not saved". *Lock* keeps changes on the page only, and a reload restores the sample. Nothing an operator decides on Dossiers survives.
- **The cells have no model** (AD-58). `stages.Cell.value` holds a gate's admittance or an outcome's value as display text, with two "nothing" values ("" and "—"). `note` mixes dates, reasons and result summaries. `result` is a float while the other results are text in `extra`. There is no who, no when and no history (ruling 13).
- **The model exercise's cells are generated** on every read (`stages._model_rows`, a seeded random draw over the applications). An ordinary exercise's cells are all blank (`_blank_cells`), so a hand-made dossier can never be entered or decided.
- **Release is a checkbox on the page** (AD-34). `outcome_release` exists (AD2C) but nothing writes it, and *Decided* (ruling 38) shows nowhere.

## Decision

- **Three tables, one row per decided thing** (AD-58's fix):
  - `gate_entry`: a dossier at a gate, *Entered* or *Not entered*. It records how it was set: by the column's rule, by hand (with a reason), or by a CSV.
  - `gate_result_value`: a gate's finished result for a dossier, one row per result key (ruling 21). The number or text is typed by the result's derivation.
  - `outcome_decision`: a dossier's value at an outcome (a value key of `outcome_value`), with the same *how*, reason, by and at.

  Each row records who set it and when. A cell with no row is *—* for a gate and *Pending* for an outcome. Absence is the one "nothing" value.
- **Lock saves** (ruling 23 unchanged on screen): *Unlock* opens the grid; *Lock* sends every changed cell in one transaction. The transaction carries a revision guard, refused with *changed since you opened it; reload* (ruling 74), and writes one audit event per Lock with its counts. *Discard changes* still puts the table back as it was unlocked.
- **The samples are seeds:** the seed records the model exercise's cells into the tables once, from today's `_model_rows`. The readers then read the store, so `_model_rows` and `_small_rows` leave the request path. Every exercise, sample or ordinary, reads the same way.
- **Release writes `outcome_release`**: ticking *Released* on an outcome records an audience and a time. The audiences are as Process sets them; who it opens to is AD2V's. *Decided* is derived, not stored (ruling 38): it shows on the outcome's header once every reached cell has a value.
- **Results are read-only here** (author, 2026-11-28): they arrive from the seed today and from Review Robin's pull in AD6. The grid shows them; it never writes them.

**Rejected:**
- **One `cell` table with a kind column.** One shape for three different values would bring back AD-58's mixed `note` and `extra`.
- **A proposal table** for each rule run or CSV (AD-35's sketch). A proposal is reviewed on screen and either applied or not. The audit event per Lock keeps what changed, and the rows keep how each cell was set. A record of proposals no one applied buys nothing yet.
- **Saving each cell as it changes.** Ruling 23 makes Dossiers a control surface worked down its columns, so a batch is kept at *Lock*.

## Semantics

- **Reached cells:** a gate's cell exists only for an enterable dossier (submitted, or created by hand once minted). A draft, a withdrawn application and a *No dossier yet* row have no cells and show *—*.
- **A rule's or a CSV's proposal** writes nothing until *Apply* and then *Lock*. Its cells are saved as `rule` or `csv`. A hand change is saved as `hand` with its reason. A rule that runs again replaces `rule` cells only, unless *Also replace cells set by hand* is ticked, as now.
- **A retired dossier** keeps its rows; its row leaves the grid. A gate or outcome removed on Process keeps its rows, retired with it (AD2C's `retired_at`).
- **A fixed column** (its Review Robin session opened, ruling 35) refuses changes on the server, not only on the page.
- **Concurrent Locks:** the second is refused by the revision guard, and nothing partial is written.
- **A release withdrawn** (unticked) deletes nothing: the release row gains `withdrawn_at`.

## Judgment calls — decided

- **The revision is the exercise's** `dossiers_revision`, one counter per grid, as Process and Panels each keep theirs (2026-11-28).
- **`note` is not stored.** It is derived on read from the rows: a date, a reason, or a result summary (2026-11-28).

## Blast radius (measured)

Taken 2026-11-28 at `f38a6a7c2`.

| What | Count | Command |
|---|---|---|
| Readers of a row's cells | 30 lines in 8 files | `grep -rn "\.cells\b\|\.cells\[" applydesk --include=*.py --include=*.html \| grep -v tests` |
| `Cell(` built | 20 | `grep -rn "Cell(" applydesk --include=*.py \| grep -v tests` |
| Readers of an outcome's `released` | 16 | `grep -rn "\.released\b" applydesk --include=*.py --include=*.html \| grep -v tests` |
| The Dossiers page (template and script) | 829 lines | `wc -l applydesk/templates/applydesk/operator/_dossiers.html` |
| Test files on the grid's cells | 22 | `grep -rln "data-ap-adm\|data-ap-oc\|\.cells\|data-ap-lock" applydesk/tests` |
| Specs naming Lock, release or *Decided* | 4 | `grep -rln "Lock\b\|Unlock\|outcome_release\|Decided" applydesk/spec applydesk/docs` |

## PR ladder

1. **Plan** (this file), the series row. Prose only.
2. **The tables and the seed.** Models and migration `ad2h1_cells` (`gate_entry`, `gate_result_value`, `outcome_decision`, `outcome_release.withdrawn_at`, `exercise.dossiers_revision`). The seed records the model exercise's cells from `_model_rows`, audited. Must not touch: any reader.
3. **Cells from the store.** `plan_of` builds each row's cells from the tables, and `_model_rows` / `_small_rows` leave the request path. `Cell` gains the *how*, who and when, and `note` is derived. Must not change what a sample's pages show (a test compares them before and after).
4. **Lock saves.** `POST …/dossiers/cells` takes the changed cells and the revision, and refuses a fixed column, an unreached cell or an unknown value. The page's *Lock* posts them. The placeholder line goes from Dossiers.
5. **Release and Decided.** *Released* writes and withdraws `outcome_release` per audience. The outcome's header shows *Decided* when it holds.
   - **Last build rung:** `diff-reviewer` on the cumulative diff from rung 2's base.
6. **Close:** `spec-writer` on `applydesk/spec/`; AD-58 struck, AD-35 and AD-34 narrowed; Status compacted; the plan archived.

## Definition of done

- `gate_entry`, `gate_result_value` and `outcome_decision` round-trip on SQLite and Postgres 16 (`ci-postgres.yml`).
- The model exercise's Dossiers page is the same before and after rung 3 (a test).
- A hand change, locked, survives a reload, with who and when; a stale Lock is refused (tests).
- A hand-made dossier, once minted, can be entered and decided (a test).
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD2H` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- ~~Results entered by hand~~: none in AD2H; results arrive with AD6's pull (author, 2026-11-28).
- **A reason for every hand change**, or optional? Today it is optional. The author decides.

## Out of scope

- Pairs and the gate page's edits (AD2P).
- The gate's own state, and the dossiers frozen at send (AD2T).
- Whom a release opens to, and what each audience sees (AD2V).
- *Return to draft* (ruling 49), still marked not built.

## Doc impact

- `applydesk/spec/applications.md` — the Dossiers page's Lock saving, release per audience, *Decided*; the placeholder line gone.
- `applydesk/spec/architecture.md` — the three tables, the migration, the seed, the readers.
- `applydesk/docs/data_and_visibility_model.md` — §2's evaluators' results and outcome decisions, as built.
- `applydesk/guide/ad2_deferred_findings.md` — AD-58 struck, AD-35 and AD-34 narrowed (at close).
- `applydesk/guide/ad2_series.md` — the AD2H row (at plan and close).
