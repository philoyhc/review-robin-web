# Segment 22J — The Setup routes' shared handler

**Opened:** 2026-11-06 · **Theme:** one body for what the four Setup roster
route modules each repeat, no behavior change · **Related:**
`guide/codebase_assessment_06nov.md` §2, §5, §9; `spec/setup_pages.md`;
`spec/architecture.md`

## Opportunity

The four Setup roster route modules (`app/web/routes_operator/_setup_reviewers.py`,
`_setup_reviewees.py`, `_setup_observers.py`, `_setup_relationships.py`)
each declare the same route families, and each spells the body out again:
import and its dismiss, bulk inactivate / reactivate / delete, delete all,
field labels and self fields. `tools/code_metrics.py` measures a quarter to
a third of each module as blocks of 10+ lines repeated elsewhere (Blast
radius). Two codebase assessments in a row carried "plan the shared
handler" as a next move (3 November move 3, 6 November §9) and neither
started it.

The cost is not size but drift: a fix to one copy has to be found and
made in three more. That has happened. Observers' import mirrored
Reviewers' and skipped the cross-table identity check until 19Q Item 7
(its docstring says so), and Reviewers and Reviewees already share
`roster_import._handle_import` (20E rung 3) while Observers (201 lines)
and Relationships (170 lines) keep their own.

## Decision

**A roster-kind descriptor and shared action functions, in a new module
outside the package; the routes stay declared in their own modules.** The
new module, `app/web/roster_actions.py`, sits beside `roster_import.py`
and on the same terms (`spec/architecture.md`: slices import only `_shared`
and modules outside the package). It holds:

- a frozen `RosterKind` per roster: its noun and slug, model, operation
  error, list path, and the service functions each family calls;
- one function per identical family: bulk set-active, bulk delete,
  delete all, dismiss a held upload, save self fields. The route keeps
  its decorator and signature and calls one of these.

Observers' import then moves onto `roster_import._handle_import`, the
seam the assessment names, and Relationships' import follows if its
differences fit as parameters the handler already takes.

**Rejected: a route factory** (`register_roster_routes(router, kind)`).
It would generate the routes. But each roster's form field names differ
(`reviewer_ids`, `observer_ids`, …) and are the form's contract, so the
signatures cannot be shared. Generated routes would also vanish from a
grep, and from the tests that read route modules' source
(`tests/integration/test_pager_anchor.py`,
`tests/integration/test_upload_paths_keep_friendly_labels.py`).

**Rejected: flags on a shared body.** Where a roster genuinely differs, its
route keeps its own body. Relationships' bulk inactivate / reactivate
acknowledge a response loss and refuse a group clear; a
`has_response_loss=` switch would turn one body into four disguised as one.

## Semantics

- **No behavior change, by contract.** Every route keeps its path, form
  field names, status codes, redirect targets and anchors, audit events,
  and error copy. The suite as it stands is the proof: no existing test
  is edited to pass, except where it names a moved function (below).
- **Lazy import, as `roster_import` does.** `roster_actions` reads the
  package's guards from `_shared` inside its functions, never at its top,
  so the two never import each other at load.
- **Tests that patch a module attribute** keep working:
  `test_directory_rosters.py` patches `_setup_observers.directory_or_none`.
  Once Observers' import calls `_handle_import`, the patch target is
  `_shared`'s, which `roster_import` already reads through the module.
  The test moves to that target in the same rung.
- **Source-reading tests** follow the code. `test_pager_anchor.py` maps
  route modules to templates by file name. An anchor that moves into
  `roster_actions.py` joins that map under its templates, or the check
  stops seeing it.

## Judgment calls — decided

- The descriptor carries callables, not a service module. The four
  services name their functions alike but not identically, and passing
  `reviewers_service` would make `roster_actions` guess. (2026-11-06)
- Page renders (`_render_*_page`, 227–315 lines each) stay. They are each
  roster's own page and the largest roster-specific code; they are not
  the duplication measured. (2026-11-06)
- Create and update stay. Their fields are each roster's own, and their
  shared lines are a guard and a redirect. (2026-11-06)

## Blast radius (measured)

Taken 2026-11-06 at `fe84c007`.

| What | Count | Command |
|---|---|---|
| Module lines (`_setup_reviewers` / `reviewees` / `observers` / `relationships`) | 815 / 830 / 1,152 / 1,213 | `wc -l app/web/routes_operator/_setup_*.py` |
| Duplicated code lines, 10+ line blocks | 198/635 (31%) · 169/647 (26%) · 239/897 (27%) · 310/956 (32%) | `python3 tools/code_metrics.py --dup-only` |
| Identical families | dismiss ×4 (17 lines each); bulk inactivate / reactivate ×3 (29 each); bulk delete ×4 (46–60); delete all ×4 (31–42); field labels ×3 (29–36); self fields ×3 (31–36) | function lengths by `ast` over the four modules |
| Imports off the shared handler | Observers 201 lines, Relationships 170 | same |
| Test files posting to these routes | 94 (import); 12 (delete-all); 7 (bulk-inactivate); 5 (field-labels); 4 (bulk-delete, self-fields) | `grep -rlE "(reviewers\|reviewees\|observers\|relationships)/<family>" tests/` |
| Tests naming a module attribute or its source | 2 files: `test_directory_rosters.py`, `test_upload_paths_keep_friendly_labels.py` (+ `test_pager_anchor.py` by file name) | `grep -rn "_setup_(reviewers\|reviewees\|observers\|relationships)\." tests/` |
| Specs naming these modules | 5: `spec/architecture.md`, `setup_pages.md`, `csv_contracts.md`, `lifecycle.md`, `participant_model.md` | `grep -rln "_setup_…\|roster_import" spec/` |

The assessment's estimate is −200 to −400 production lines (§7).

## Status

**Closed 2026-11-06.** Three build rungs (#3697, #3698, #3699) and this
close; rung 4 is a recorded no.

- **Built:** `app/web/roster_actions.py` holds Reviewers', Reviewees'
  and Observers' bulk inactivate, reactivate and delete, their delete
  all, and the self-fields save, driven by a `RosterKind` per roster.
  It also holds the field-labels save for Reviewers, Reviewees and
  Relationships, and `back_to_panel`. Observers' import calls
  `_handle_import`.
- **Kept, with reasons:** `RosterKind` covers three rosters, not four.
  Relationships' bulk actions and delete all acknowledge a response loss
  and refuse a group clear. Dismiss was already one call to
  `dismiss_held_upload`.
- **Rung 4, no:** Relationships' import shares too little. Its parse
  needs both rosters; it runs no identity or directory check; it has no
  response-loss ask (the save takes the loss and refuses a group clear);
  its asks re-render without the ticks' state; and it runs no
  merge-conflict check. Six more switches would make one body into two.
- **Decision bent at rung 3:** `_handle_import` gained a `render_page`
  parameter and three branches on `kind == "observers"`, which the
  Decision's "flags on a shared body" warned against. This was accepted
  over the 200-line copy that had drifted once already (19Q Item 7). The
  handler asserts the pair.
- **Retired:** `participant_info.set_reviewer_self_fields` (one caller).
- **Tests edited:** only the moved `directory_or_none` patch target, in
  `test_directory_rosters.py` and `test_directory_recheck.py` (plus a
  conftest note). `test_import_order.py` gained `roster_actions`.
- **Measured at close** (`a989a7f6`, same commands as Blast radius):
  - Module lines: 734 / 753 / 933 / 1,188, against 815 / 830 / 1,152 /
    1,213.
  - 10+ line duplication:
    - Reviewers: 126/571 (22%), from 198/635.
    - Observers: 183/737 (25%), from 239/897.
    - Relationships: 299/943 (32%), from 310/956.
    - Reviewees: off the tool's top-five list, from 169/647.
  - Net production lines: the four modules lost 402. `roster_actions.py`
    (326) and `roster_import.py` (+43) took most of them back, leaving
    about −33. That falls short of the assessment's −200 to −400: the
    bodies moved with their docstrings, and the gain is one copy to fix
    rather than four.
- **Reads:** one cumulative `diff-reviewer` pass at rung 3 found no
  behavior change and six fixes, all made in rung 3: `test_import_order`
  coverage, a false `settings_inventory` line, four stale comments, the
  `kind`/`render_page` assert and an unused query. Codex found nothing
  on any rung. `spec-writer` at the close found the Doc impact specs
  true as edited and made no change.
- **The close** lowered `test_index_currency.py`'s `**Plan:**` floor
  to 1, as its comment directs: the queue holds 14G alone.

## PR ladder

One item; `diff-reviewer` reads the cumulative diff once, at rung 4.

1. **`roster_actions.py` and the bulk families.** It lands `RosterKind`
   for the four rosters, with bulk set-active and bulk delete. The routes
   for Reviewers, Reviewees and Observers call it; Relationships' bulk
   set-active keeps its own body (Decision), while its bulk delete shares
   if it fits. Its own read is deferred to rung 4's. It must not touch
   imports or pages.
2. **Delete all, dismiss, field labels, self fields** onto the same
   module, for every roster each applies to. It must not touch imports.
3. **Observers' import onto `_handle_import`.** The handler gains what
   Observers needs, if anything, as a parameter it already has the shape
   for. `test_directory_rosters.py` follows the patch target (Semantics).
4. **Relationships' import onto `_handle_import`**, or a recorded no if
   its group-clear and pair handling do not fit as parameters. This is
   the last build rung: `diff-reviewer` on the cumulative diff.
5. **Close.** The specs below, `close_check`, `spec-writer`, the
   duplication and line counts taken again and recorded in `Status`.

## Definition of done

- `app/web/roster_actions.py` exists, and the bulk, delete-all, dismiss,
  field-label and self-field routes of the four rosters call it, except
  those `Status` names as kept with a reason.
- Observers' import calls `roster_import._handle_import`; Relationships'
  does too, or `Status` records why not.
- No existing test edited except for a moved patch target or source map,
  each named in the rung's PR body; the full suite, `ruff` and `pyright`
  pass on every rung.
- `python3 tools/code_metrics.py --dup-only` and `wc -l` taken at the
  close and recorded against the Blast radius; the four modules' lines
  net down.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 22J` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- ~~Whether Relationships' import fits `_handle_import`~~ — no, decided
  from the code at rung 4 (Status).

## Out of scope

- The page renders and create / update (Judgment calls).
- Quick Setup's slots (`_quick_setup.py`), which already call the
  per-entity primitives.
- Any change a reader could see: copy, layout, a route, a form field.

## Doc impact

- `spec/architecture.md` — the module map and its paragraph on `app/web/roster_import.py` gain `app/web/roster_actions.py` and what it holds.
- `spec/setup_pages.md` — the pointers that name a Setup module as where an import or gate lives follow the code (§ on Observers and Relationships imports, and the `is_editable` gate's citation).
- `spec/settings_inventory.md` — `reviewer_self_fields` is saved through `participant_info.set_self_fields`; rung 2 retired the `set_reviewer_self_fields` wrapper.
- `guide/todo_master.md` — delete the 22J queue entry (at close).
