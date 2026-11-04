# Segment 22D — Pyright over test code

**Opened:** 2026-11-04, filed at the author's request as 22C's first
follow-up · **Theme:** the type gate covers the code that checks the
code · **Related:** `guide/archive/segment_22C_pyright.md` (the gate this
extends), `CONTRIBUTING.md`, `tools/ci_lanes.py`

## Opportunity

22C gates application code only (`[tool.pyright]` excludes `**/tests`).
Test code is checked by running it, which proves the paths it runs and
nothing about the rest: a fixture typed `Foo | None` and read as `Foo`,
or a helper called with the wrong argument, passes until the branch that
trips it runs. Measured over the four test trees, pyright in basic mode
finds **1,917 errors in 262 files**. Most are the fixture shape above,
not defects, so the gate cannot simply widen; it needs the rules relaxed
first and ratcheted back.

## Decision

**Widen `include` to the test trees with the two optional-access rules
off for tests only, fix the rest, gate it, then turn those two rules back
on directory by directory** (`tests/unit/` first, then
`cordware/tests`, the apps' `tests/`, `tests/db`, `tests/browser`,
`tests/integration`).

Pyright's `executionEnvironments` (or a nested config under `tests/`)
scopes the relaxation, so application code keeps every rule it has.

Rejected: *gate tests at full strength now with a baseline file.* 1,917
entries is a second list to keep in step, and most of them are
`reportOptional*` noise; relaxing two rules removes 844 of them by
design rather than by list. Rejected: *leave tests out for good.* The
other 1,073 (argument types, attribute access) include real wrong calls,
and a test that calls a helper wrongly can pass for the wrong reason.

## Semantics

- **Relaxed means off, not warning.** A warning nobody reads is a
  baseline in another form; each relaxation is listed in the config with
  the rung that removes it.
- **Fixtures, not asserts.** Where a fixture returns `Foo | None` but
  always yields `Foo`, the fixture's annotation changes; a blanket
  `assert x is not None` in every test is the wrong fix.
- **A test helper that genuinely accepts a loose shape** (a
  `SimpleNamespace` standing in for a model) takes a Protocol or the
  model's type, as 22C did for `BranchField`.
- **Test behavior never changes.** A fix that changes what a test
  asserts is its own PR, outside this segment.

## Judgment calls — decided

- Directory order follows error density, smallest first, so the ratchet
  proves itself on `tests/unit/` (453) before `tests/integration/`
  (1,302) (2026-11-04).

## Blast radius (measured)

Taken 2026-11-04 at `9b45a9c1`, pyright 1.1.414, basic mode, `include`
set to the four test trees.

| What | Count | Command |
|---|---|---|
| Errors, test code | 1,917 in 262 files (658 analyzed) | `pyright --outputjson` with `include = ["tests", "cordware/tests", "residentialapps/tests", "utilityapps/tests"]` |
| `reportOptionalMemberAccess` + `reportOptionalSubscript` | 533 + 311 | `collections.Counter` over `rule` |
| `reportArgumentType` / `reportAttributeAccessIssue` | 708 / 278 | the same |
| By tree | `tests/integration` 1,302, `tests/unit` 453, `tests/browser` 70, `residentialapps/tests` 43, `utilityapps/tests` 29, `cordware/tests` 16, `tests/db` 2, `tests/*.py` 2 | `Counter` over the path's first two parts |
| `reportMissingImports` | 8 | the same; likely optional browser dependencies, to check in rung 1 |

## Status

- **Rung 1** (2026-11-04): the test trees get their own config,
  `pyrightconfig.tests.json`, run as `pyright -p pyrightconfig.tests.json`,
  not a wider `include` in `pyproject.toml`. 22C's gate already runs
  `pyright` in CI, so widening it before the fixes would turn every PR
  red. Rung 6 folds this file into `pyproject.toml`. `extraPaths:
  ["tools"]` resolves the tests that import from `tools/` (8 missing
  imports). With the two rules off: **1,065 errors in 163 files**
  (`tests/integration` 555, `tests/unit` 404, `tests/browser` 44, the
  rest 62).
- **Rung 2:** the small trees clean, 1,065 → 995 (70). `cordware.graph`
  gains `Finder` (`find_users` alone), the protocol `look_up_all` and
  the email checker's `run` actually need: the tests' fake directories
  never had `search_users`. Log-record extras read through
  `record.__dict__`; pydantic-settings' `_env_file` takes a
  `pyright: ignore` with its reason (pyright cannot see the option).
- **Rung 3:** `tests/unit/` clean, 995 → 599 (396). Duck-typed fakes
  (`SimpleNamespace`, `_FakeSession`) come from a factory typed as the
  model they stand in for, by `cast`; the rule engine's `object` pairs
  are read through an asserting `_typed` helper; an Optional lookup
  takes an `assert` beside it; `_make_args` returns `dict[str, Any]`;
  `_maps` a `TypedDict`. Two application annotations widen to what the
  code reads: `sort_from_positions` / `widths_from_positions` take
  `object` (they drop a non-list, non-dict from a hand-edited CSV) and
  `validate_page_n` takes `Sequence[object]` (only the length). The
  three `Settings(_env_file=None)` lines take 22D's one ignore.

## PR ladder

1. **Config.** Widen `include`; scope the two optional-access rules off
   for the test trees; re-measure. No fixes, no gate. *(Built as a
   separate config file: `## Status`.)*
2. **Small trees.** `cordware/tests`, `residentialapps/tests`,
   `utilityapps/tests`, `tests/db`, the root `tests/*.py`.
3. **`tests/unit/`.**
4. **`tests/browser/`.**
5. **`tests/integration/`**, split by area if it is large.
6. **The gate.** `pyright` already runs in CI; this rung is the config
   change that keeps tests in its scope, with the docs that say
   "application code only" updated.
7. **Ratchet.** The two rules back on per directory, one PR each, in the
   Decision's order.
8. **Close.**

## Definition of done

- `pyright` exits 0 with the test trees included and neither
  optional-access rule relaxed anywhere.
- `README.md`, `CLAUDE.md` / `AGENTS.md` and `CONTRIBUTING.md` no longer
  say pyright checks application code only.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 22D` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **Order against 22E:** tests first (this plan), or strict mode on
  `cordware` first? Neither depends on the other. Author.

## Out of scope

- Strict mode, for tests or application code: `guide/segment_22E_pyright_strict.md`.
- Changing what any test asserts.

## Doc impact

- `pyproject.toml` — `[tool.pyright]` takes in the test trees from `pyrightconfig.tests.json` (rung 6); the relaxations' removal (rung 7).
- `pyrightconfig.tests.json` — the test trees' config until the gate takes them in (rung 1; deleted at rung 6).
- `README.md` — pyright's scope (rung 6).
- `CLAUDE.md` — "Common commands" and the pre-PR gate: pyright's scope (rung 6); `AGENTS.md` copied.
- `AGENTS.md` — the twin, copied from `CLAUDE.md` (rung 6).
- `CONTRIBUTING.md` — the checklist's pyright scope (rung 6).
- `guide/todo_master.md` — delete the segment's entry at close.
