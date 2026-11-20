# Segment 23I — Split `_quick_setup.py`

**Opened:** 2026-11-20 · **Theme:** move the upload pipeline out of the
Quick Setup slice, then the handoff routes into `_handoffs.py`; no behavior
change · **Related:** `guide/codebase_assessment_20nov.md` §9,
`spec/architecture.md`, `spec/handoffs.md`

## Opportunity

`app/web/routes_operator/_quick_setup.py` is the largest file in `app/`, at
1,867 lines. It grew by 355 lines in the window the 2026-11-20 assessment
measured, and §9 of that assessment names it the one split candidate. It
holds three things:

- Quick Setup's routes and New session's `create_session`;
- the upload pipeline that stages, checks and saves every slot in one unit;
- the two handoff routes (segments 23A and 23F), which run that pipeline.

The handoffs' other routes are already in `_handoffs.py`. Its docstring
says why the POST routes are not: "slices do not import one another"
(`spec/architecture.md`, the operator routes package). So the handoff
routes cannot move until the pipeline leaves the slice. Every handoff
change since 23A has landed in the Quick Setup file.

## Decision

The split takes two moves, each a pure relocation.

1. **The pipeline leaves the package.** It moves to
   `app/web/quick_setup_pipeline.py`, on the terms
   `app/web/roster_import.py` already holds:
   - it sits outside `app/web/routes_operator/`;
   - the slices import it;
   - it reads `_shared.py` only inside the functions that need it;
   - it is listed in `tests/unit/test_import_order.py`'s `FIRST_IMPORTS`.

   The names other modules call lose their leading underscore.
2. **The handoff routes join `_handoffs.py`.** That covers create, re-send
   and their response helpers, which import the pipeline as Quick Setup
   does.

**Rejected: the pipeline into `_shared.py`.** That file is already 1,159
lines. It would become the next split candidate, and it would mix request
guards with a multi-slot save engine.

**Rejected: only the handoff routes, importing `_quick_setup`.** That
breaks the no-slice-to-slice rule the package is built on.

**Rejected: the pipeline as a service.** It renders responses, holds
uploads and reads requests, which is web-layer work.
`roster_import.py` is the precedent for exactly this kind of shared web
code.

## Semantics

- **Routes:** paths, methods, status codes and bodies are unchanged.
  - `_handoffs.router` is included after `_quick_setup.router`
    (`app/web/routes_operator/__init__.py`).
  - No path and method pair is shared between them, so the order the
    routes are matched in is unchanged.
- **Import order:** the pipeline imports `app.web.routes_operator._shared`
  inside functions, never at module top. `test_import_order.py` imports
  it alone, in a fresh interpreter.
- **Tests that patch module attributes.** Tests patch
  `_quick_setup.directory_or_none` and `_quick_setup.session_guard`. After
  the move, a patch reaches the code only if it targets the module that
  now looks the name up. Each such test is moved to the new module's
  name; none is deleted or skipped.
- **Spec registry:** `app/web/spec_registry.py` maps `_quick_setup` to
  `spec/handoffs.md` because it holds "the handoff create". That entry
  goes once the routes move, and `_handoffs` keeps `spec/handoffs.md`.

## Judgment calls — decided

- The module is named `quick_setup_pipeline`, after what `spec/csv_contracts.md`
  already calls it: "the pipeline every Quick Setup upload route shares".
- `_single_slot`, `_slot_response`, `_quick_setup_session` and
  `_settings_import_session` stay in `_quick_setup.py`: only Quick Setup's
  routes use them.
- Public names: `run`, `run_contents`, `SlotRefusal`, `SlotFailure`, plus
  the hold helpers the routes call. `pyright`'s `reportPrivateUsage`
  decides any others.
- No behavior change rides along. A defect found in the move is filed
  separately rather than fixed in it, so the diff stays a move.

## Blast radius (measured)

Taken 2026-11-20 at `2b3b1aed4`.

| What | Count | Command |
|---|---|---|
| `_quick_setup.py` lines | 1,867 | `wc -l app/web/routes_operator/_quick_setup.py` |
| Pipeline (lines 430–1223) | 794 | `sed -n 430,1223p … \| wc -l` |
| Handoff block (lines 1572–1867) | 296 | `sed -n 1572,1867p … \| wc -l` |
| Pipeline names used outside it | 9 (2 by the handoff routes) | per-name `grep -c` over the rest of the file |
| `_shared` names the pipeline reads | 5 | `grep` of the `_shared` import list over lines 430–1223 |
| Test files that import or patch `_quick_setup` | 7 | `grep -rln "_quick_setup\b" tests --include=*.py` (`test_handoffs`, `test_session_new_tags_card`, `test_quick_setup_turns_tabs_on`, `test_directory_rosters`, `test_quick_setup_directory_renew`, `test_upload_paths_keep_friendly_labels`, `conftest`) |
| Specs naming the file or the pipeline | 7 | `grep -rln "_quick_setup\b\|_run_quick_setup" spec docs` (`architecture`, `handoffs`, `csv_contracts`, `lifecycle`, `permissions`, `session_owners`, `quick_setup_card_spec`) |

After the split, about 880 lines stay in `_quick_setup.py`, the pipeline
holds about 700, and `_handoffs.py` grows to about 425.

## Status

**Closed 2026-11-20.** Opened in #4072; the ladder held as planned:
rung 1 #4073, rung 2 #4074, this close. `_quick_setup.py` went from
1,867 lines to 779; `app/web/quick_setup_pipeline.py` holds 810 and
`_handoffs.py` 458. Both moves are verbatim apart from the renames and
the deferred `_shared` imports, each shown by a `diff`.

- **Moved with the pipeline:** `_read_settings_csv`, its only caller.
- **Found by CI at rung 1:** outside `routes_operator/`, the pipeline is
  a reader `test_linked_lock_signals.py` must name, and nothing pinned
  its observers refusal (Quick Setup is off on a linked session and the
  handoff refuses observers first). A test now calls the pipeline
  directly and fails with the check disabled.
- **Left as found:** `_handoffs.py` keeps `_refused` beside the moved
  `_handoff_refused` (folding them changes behavior); the versioned
  `cordware/docs/cordware_interoperability_agent_handoff_v0.3.md`.
- **Reads:** one cumulative `diff-reviewer` read at rung 2's head
  (base `c416ab377`) confirmed the moves and found stale locations in
  four specs and a package comment, fixed in their rung;
  `spec/quick_setup_card_spec.md` and `spec/lifecycle.md` joined Doc
  impact. One `spec-writer` verify over the doc-impact specs at that
  head found them matching the code, and stands as the close pass: no
  doc-impact file changed after it.

## PR ladder

Cumulative read: `diff-reviewer` reads the diff from rung 1's base to
rung 2's head at rung 2, as the last build rung. Rung 1's PR records the
base SHA.

1. **PR 1 — The pipeline leaves the slice.**
   - **Lands:**
     - `app/web/quick_setup_pipeline.py` with the pipeline moved verbatim,
       renamed to public names;
     - `_quick_setup.py` importing it;
     - the `FIRST_IMPORTS` entry;
     - the tests' private-name and patch-target updates;
     - the spec names that change: `handoffs.md` lines 84 and 224,
       `csv_contracts.md` near line 821, and `architecture.md`'s module
       map beside `roster_import.py`.
   - **Must not touch:** the handoff routes, or any behavior.
2. **PR 2 — The handoff routes join `_handoffs.py`.**
   - **Lands:**
     - create, re-send and their helpers moved verbatim;
     - `_handoffs.py`'s docstring;
     - the `spec_registry.py` entry;
     - the patch targets in the handoff tests;
     - `spec/handoffs.md`'s "create route lives in" line.
   - **Must not touch:** Quick Setup's routes.
   - **Read:** the cumulative read happens here.
3. **PR 3 — Close.** Prose only: `close_check`, `spec-writer`, `Status`,
   archive.

## Definition of done

- `app/web/quick_setup_pipeline.py` exists, and `_quick_setup.py` holds no
  handoff route: `grep -n "handoffs/" app/web/routes_operator/_quick_setup.py`
  prints nothing.
- `_quick_setup.py` is under 1,000 lines: `wc -l`.
- `tests/unit/test_import_order.py` lists `app.web.quick_setup_pipeline`.
- `tests/unit/test_spec_coverage.py` passes with `_quick_setup` mapped to
  `spec/quick_setup_card_spec.md` alone.
- The full gate passes on each rung, with no test deleted or skipped:
  `git diff --stat <base>..HEAD -- tests` shows edits only.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 23I` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

None.

## Out of scope

- **`create_session`** (lines 93–429, 337 lines) stays in `_quick_setup.py`.
  It is New session's route, and Quick Setup's slots ride on its form.
- **The other §9 watchlist files**: `_instrument_crud.py`, the two large
  templates and Apply Desk's `stages.py`. They are watched, not split
  (`guide/codebase_assessment_20nov.md` §9).
- **Any change to the pipeline's behavior.** That includes the stub "A
  linked re-send may leave an instrument's name out", which stays in
  `guide/todo_master.md` for AD6.

## Doc impact

- `spec/architecture.md` — the operator routes package paragraph names `app/web/quick_setup_pipeline.py` beside `roster_import.py`, on the same import terms (PR 1).
- `spec/handoffs.md` — the pipeline's new names at the create and re-send steps (PR 1); the create and re-send routes live in `_handoffs.py` (PR 2).
- `spec/csv_contracts.md` — the pipeline's name in the commit-ownership note (PR 1).
- `spec/quick_setup_card_spec.md` — the pipeline's name at Per-slot dispatch and Submission semantics (PR 1; found at build).
- `spec/lifecycle.md` — §7's Quick Setup exception names the pipeline as where `is_editable` is tested (PR 1; found by the cumulative read).
- `guide/todo_master.md` — the queue entry added at open, deleted at close.
