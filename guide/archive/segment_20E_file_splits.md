# Segment 20E — File splits from the 2026-11-02 assessment

**Opened:** 2026-11-03, at the author's request ("open series 20 segments
to log the larger follow up actions coming from the recent codebase
assessment, including the file splits") · **Theme:** the largest
modules cut along the seams they already have, with no behavior change ·
**Related:** `guide/archive/codebase_assessment_02nov.md` §9,
`guide/archive/findings_2026-11-02_assessment.md`, `spec/architecture.md`
(the per-package module map)

## Opportunity

Two files passed the triggers the 22 October watchlist set, and a third
has a clean cut waiting (`guide/archive/codebase_assessment_02nov.md` §9):

- `app/services/csv_imports.py` is 2,258 lines, the largest file in
  `app/`, and holds four concerns: parsing, identity checks, the append
  and merge modes, and the save.
- `app/web/routes_operator/_shared.py` is 1,677 lines; `_handle_import`
  alone is 417, and it carries the upload-hold and directory helpers
  beside the package's guards.
- `app/services/responses/_core.py` is 1,605 lines; its last ~380 are
  read-only tallies the save path never calls back into.

Each shared module accretes a feature's second half (19W's hold, 19Z's
modes and directory): the pattern the last two snapshots named.

## Decision

**Cut along existing seams, one module per PR, with the public surface
unchanged.** A service module becomes a package behind an explicit
re-export wall, as `app/services/responses/` already is; callers keep
`from app.services import csv_imports` and `csv_imports.<name>`.

- **Rung 1, the template:** `responses/_core.py`'s tallies
  (`RollupParts`, `rollup_parts_from_assignments`,
  `responses_by_assignment`, `reviewer_session_state_per_instrument`,
  `session_response_count`) to `responses/_rollups.py`.
- **Rung 2:** `csv_imports.py` to a package: `_parse.py` (decode, row
  reading, cell checks, the three `parse_*_csv`), `_identity.py` (the
  same-person and cross-roster checks), `_modes.py` (append and merge),
  `_save.py` (`DirectoryCheck`, `save_*`, `_save`, `delete_all_*`).
- **Rung 3:** `_handle_import` and the upload-hold helpers
  (`read_upload`, `UploadIn`, `hold_for_ask`, `release_hold`,
  `dismiss_held_upload`, `acknowledged_loss`) to `app/web/roster_import.py`,
  **outside** the routes package, beside `app/web/urls.py` and
  `app/web/downloads.py`. `CLAUDE.md` lets route slices import only from
  `_shared.py` and from outside the package, so a sibling module inside it
  would break the rule. `directory_or_none` stays in `_shared.py`.

Rejected: *one PR for all three.* Each is a large mechanical diff, and a
reviewer models one move at a time. Rejected: *splitting by size alone*
(e.g. `_instrument_crud.py`, `assignments/_generate.py`,
`views/_instruments.py`): each is long but one concern.

## Semantics

- **No behavior change.** Each rung moves code and its imports only; the
  full suite, unchanged, is the proof. A rename in passing is out.
- **Monkeypatch targets.** A test that patches a name on the package
  (`monkeypatch.setattr(csv_imports, "append_conflicts", …)`) no longer
  reaches a call made inside the package; such tests are repointed to the
  submodule in the same rung, not weakened.
- **Private names** (`_count`, `_save`, `_parse_email`,
  `_identity_holders`, used from tests and `_count` from seven sites)
  are re-exported where a caller outside the package uses them, and the
  wall's docstring says which.
- **Import cycles:** each new module imports only downward (parse ←
  identity ← modes ← save); a cycle refuses the rung.

## Judgment calls — decided

- `responses/_rollups.py` first: read-only, no writes, so the safest
  template for the re-export pattern (2026-11-03).
- `roster_import.py` outside the routes package rather than a second
  shared module inside it (2026-11-03).

## Blast radius (measured)

Taken 2026-11-03 at `a2d95aff`.

| What | Count | Command |
|---|---|---|
| Files naming `csv_imports` (app + tests) | 54 | `grep -rln csv_imports app tests --include=*.py \| wc -l` |
| Tests patching `csv_imports` in place | 2 | `grep -rn "monkeypatch.setattr(csv_imports" tests --include=*.py \| wc -l` |
| Route slices using the upload-hold helpers | 6 | `grep -rlE "read_upload\|hold_for_ask\|release_hold\|dismiss_held_upload\|acknowledged_loss\|_handle_import" app/web/routes_operator/*.py \| grep -v _shared.py \| wc -l` |
| Tests using them | 3 | the same over `tests` |
| Tests patching `_shared` | 12 | `grep -rn "setattr(_shared" tests --include=*.py \| wc -l` |
| Call sites of the five tallies outside `responses/` | 22 | `grep -rnE "rollup_parts_from_assignments\|responses_by_assignment\(\|reviewer_session_state_per_instrument\|session_response_count\|RollupParts" app --include=*.py \| grep -v "responses/_core.py\|responses/__init__.py" \| wc -l` |
| `spec/architecture.md` lines naming the moved modules | 14 | `grep -n "csv_imports\|_shared.py\|responses/_core\|validation.py\|_band1" spec/architecture.md \| wc -l` |

## Status

**Closed 2026-11-03.** Five splits shipped in five PRs, none changing
behavior: #3527 (rung 1), #3528 (2), #3529 (3), #3530 (4a), #3531 (4b).
Rung 4's other two splits were skipped at the author's ruling.

| Module before | Lines | After |
|---|---|---|
| `responses/_core.py` | 1,605 | 1,194, plus `_rollups.py` 433 |
| `csv_imports.py` | 2,258 | package: `_parse` 904, `_identity` 436, `_modes` 302, `_saving` 710 |
| `routes_operator/_shared.py` | 1,677 | 1,050, plus `app/web/roster_import.py` 657 |
| `instruments/_band1.py` | 1,395 | 1,020, plus `_preview.py` 392 |
| `validation.py` | 1,506 | package: `_registry` 472, `_rosters` 433, `_instruments` 275, `_assignments` 252, `_inputs` 180 |

Divergences from the plan:
- **`_core.py`'s target** was "under 1,000", an estimate; the cut left 1,194
  and the definition of done reads under 1,200.
- **`csv_imports/`:** `DirectoryCheck` sits in `_identity.py`, since
  `_modes.py` needs it and imports only downward. The save module is
  `_saving.py`, because a `_save.py` would be shadowed on the package by the
  re-exported `_save` function.
- **`acknowledged_loss` stayed in `_shared.py`**: Instruments and Quick
  Setup use it, so it is a form helper, not upload handling.
- **`roster_import.py` imports `_shared` inside the functions that use
  it.** A top-level import was a cycle through the routes package's
  `__init__`, hidden by `app.main`'s import order; it calls
  `_shared.directory_or_none` through the module, so tests that replace it
  there still reach it.

Tests repointed, none weakened: one `append_conflicts` patch also targets
`_saving`; the identity-fold gate lists the five `csv_imports` modules; a
source-reading test reads `_preview`; the readiness-report cost guard
matches the validation package by prefix. New:
`tests/unit/test_import_order.py` imports every split module alone in a
fresh process.

**Reads: two `diff-reviewer` reads**, one per item (rungs 1–3 since
`8505fd8c`; rung 4 since `6232070a`). Both compared every moved definition
by `ast.dump`. They found one defect, the import cycle above, and one
literal departure from "unchanged" (a function-local `TypeAdapter` import
hoisted to `_preview.py`'s top, no behavior change). The rest were stale
pointers and an orphaned comment, all fixed. The close's `spec-writer`
pass found `spec/architecture.md`'s module map current and fixed one
pointer in `spec/assignments.md`. `close_check`'s notes on five route slices touched
outside the manifest are adjudicated: their change is the import line
naming `roster_import`, no contract.

## PR ladder

1. **`responses/_rollups.py`.** The five tallies move; `responses/__init__.py`
   re-exports them. Must not touch any caller.
2. **`csv_imports/` package.** The four modules and the wall; the two
   patching tests repointed. Must not touch a route.
3. **`app/web/roster_import.py`.** The handler and the hold helpers; the
   six slices import from it. Last build rung of the first three:
   `diff-reviewer` on the cumulative diff since rung 1's base.
4. **Later, each at the author's word** (the 2026-11-02 watchlist's
   second tier):
   - `validation.py` to a package: the input loader, then the 26 rules
     grouped by rosters, assignments and instruments;
   - `instruments/_band1.py`'s `find_sample_in_scope_reviewee` (310 lines)
     and `_preview_group_boundary` to `instruments/_preview.py`;
   - `operator/instruments_index.html`'s three large scripts (560, 2,198
     and 1,562 lines) to included partials. Three tests in
     `tests/integration/test_inline_scripts_parse.py` read the template
     source by path and slice it by text, so they move with the script
     they read.

   ~~Each takes its own read.~~ One read for 4a and 4b together, at 4b
   (per item, `CLAUDE.md`).
5. **Close.** `spec/architecture.md`'s module map, the watchlist settled
   in the next assessment.

## Definition of done

- `app/services/csv_imports.py` has no module over 1,000 lines,
  `app/services/responses/_core.py` is under 1,200 and `_shared.py` under
  1,200 (`wc -l`).
- The full suite passes unchanged at each rung, but for repointed patch
  targets (PR bodies list them).
- `spec/architecture.md`'s module map names every new module.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 20E` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- ~~**Rung 4's three:** which, and when.~~ Answered 2026-11-03 (author:
  "do band1 preview and validation splits; skip the rest"): `_band1.py`'s
  preview and `validation.py`; `instruments_index.html`'s scripts skipped.
- ~~**`base.html`'s stylesheet.**~~ Answered 2026-11-03: skipped with the
  rest; `CLAUDE.md` keeps it inline.

## Out of scope

- `_quick_setup.py`'s 317-line `create_session` and
  `routes_operator/_instruments.py`'s two long routes (273 and 346 lines):
  a refactor of long functions, not a file split.
- Any behavior change, including the findings register's rows.

## Doc impact

- `spec/architecture.md` — the module map: `csv_imports/` and its four modules, `responses/_rollups.py`, `app/web/roster_import.py` (rungs 1–3); rung 4's modules if they land.
- `guide/todo_master.md` — delete the segment's entry at close.
